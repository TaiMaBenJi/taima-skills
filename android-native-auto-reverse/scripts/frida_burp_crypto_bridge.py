#!/usr/bin/env python3
"""Bridge Frida plaintext hook points through Burp for authorized testing.

The loaded Frida script should send messages shaped like:

    send({"kind": "request", "id": "req-1", "body": "...", "meta": {...}})
    send({"kind": "response", "id": "req-1", "body": "...", "meta": {...}})

This controller forwards the body as a synthetic HTTP request to Burp. Edit the
body in Burp; the local receiver captures the edited content and posts it back
to Frida as:

    {"kind": "edit-request", "id": "req-1", "body": "..."}
    {"kind": "edit-response", "id": "req-1", "body": "..."}
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

try:
    import frida
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("frida Python module is required: pip install frida-tools frida") from exc


class EditedBodyStore:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._items: dict[tuple[str, str], str] = {}

    def put(self, kind: str, item_id: str, body: str) -> None:
        with self._condition:
            self._items[(kind, item_id)] = body
            self._condition.notify_all()

    def wait(self, kind: str, item_id: str, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        key = (kind, item_id)
        with self._condition:
            while key not in self._items:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            return self._items.pop(key)


def make_receiver(store: EditedBodyStore):
    class Receiver(BaseHTTPRequestHandler):
        server_version = "FridaBurpBridge/1.0"

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("[bridge-http] " + fmt % args + "\n")

        def _handle_edit(self) -> None:
            parsed = urlparse(self.path)
            parts = [unquote(part) for part in parsed.path.split("/") if part]
            if len(parts) < 3 or parts[0] != "bridge":
                self.send_error(404, "expected /bridge/<kind>/<id>")
                return
            _, kind, item_id = parts[:3]
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            charset = self.headers.get_content_charset() or "utf-8"
            body = raw_body.decode(charset, errors="replace")
            store.put(kind, item_id, body)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK\n")

        do_REQUEST = _handle_edit
        do_RESPONSE = _handle_edit
        do_POST = _handle_edit
        do_PUT = _handle_edit

    return Receiver


def start_receiver(host: str, port: int, store: EditedBodyStore) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_receiver(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[bridge] local receiver http://{host}:{port}")
    return server


def send_to_burp(
    *,
    proxy_host: str,
    proxy_port: int,
    receiver_host: str,
    receiver_port: int,
    kind: str,
    item_id: str,
    body: str,
    meta: dict,
    method: str,
) -> None:
    path = f"/bridge/{quote(kind)}/{quote(item_id)}"
    target_url = f"http://{receiver_host}:{receiver_port}{path}"
    headers = {
        "Host": f"{receiver_host}:{receiver_port}",
        "Content-Type": "text/plain; charset=utf-8",
        "X-Frida-Bridge-Kind": kind,
        "X-Frida-Bridge-Id": item_id,
        "X-Frida-Bridge-Meta": json.dumps(meta, ensure_ascii=False, sort_keys=True),
    }
    payload = body.encode("utf-8")
    conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=30)
    try:
        conn.request(method, target_url, body=payload, headers=headers)
        response = conn.getresponse()
        response.read()
        print(f"[bridge] Burp item {kind}/{item_id} -> HTTP {response.status}")
    finally:
        conn.close()


def load_frida_script(args, on_message):
    device = frida.get_usb_device(timeout=args.device_timeout)
    script_source = args.script.read_text(encoding="utf-8")
    if args.spawn:
        pid = device.spawn([args.spawn])
        session = device.attach(pid)
        script = session.create_script(script_source)
        script.on("message", on_message)
        script.load()
        device.resume(pid)
        print(f"[bridge] spawned {args.spawn} pid={pid}")
        return session, script
    if args.attach_name:
        session = device.attach(args.attach_name)
    elif args.attach_pid:
        session = device.attach(args.attach_pid)
    else:
        raise SystemExit("choose one of --spawn, --attach-name, or --attach-pid")
    script = session.create_script(script_source)
    script.on("message", on_message)
    script.load()
    print("[bridge] attached and loaded script")
    return session, script


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, required=True, help="Frida JS file to load")
    parser.add_argument("--spawn", help="package name for early spawn")
    parser.add_argument("--attach-name", help="process/app name to attach")
    parser.add_argument("--attach-pid", type=int, help="PID to attach")
    parser.add_argument("--burp-host", default="127.0.0.1")
    parser.add_argument("--burp-port", type=int, default=8080)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=28081)
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds to wait for edited Burp body")
    parser.add_argument("--request-method", default="REQUEST")
    parser.add_argument("--response-method", default="RESPONSE")
    parser.add_argument("--observe-only", action="store_true", help="do not wait/post edits back to Frida")
    parser.add_argument("--device-timeout", type=int, default=10)
    args = parser.parse_args()

    store = EditedBodyStore()
    server = start_receiver(args.listen_host, args.listen_port, store)
    script_holder = {"script": None}

    def current_script():
        deadline = time.monotonic() + 5.0
        while script_holder["script"] is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return script_holder["script"]

    def on_message(message, data) -> None:
        if message.get("type") != "send":
            print(f"[frida] {message}")
            return
        payload = message.get("payload") or {}
        kind = payload.get("kind") or payload.get("type")
        item_id = str(payload.get("id") or payload.get("uuid") or int(time.time() * 1000))
        body = payload.get("body")
        if body is None:
            body = payload.get("data", "")
        body = str(body)
        meta = payload.get("meta") or {}
        if kind not in {"request", "response"}:
            print(f"[frida] ignored kind={kind} id={item_id}")
            return

        burp_kind = "request" if kind == "request" else "response"
        method = args.request_method if burp_kind == "request" else args.response_method
        print(f"[frida] {burp_kind} id={item_id} len={len(body)} meta={meta}")
        send_to_burp(
            proxy_host=args.burp_host,
            proxy_port=args.burp_port,
            receiver_host=args.listen_host,
            receiver_port=args.listen_port,
            kind=burp_kind,
            item_id=item_id,
            body=body,
            meta=meta,
            method=method,
        )
        if args.observe_only:
            return
        edited = store.wait(burp_kind, item_id, args.timeout)
        if edited is None:
            print(f"[bridge] timeout waiting edited {burp_kind}/{item_id}; original body kept")
            edited = body
        script = current_script()
        if script is None:
            print(f"[bridge] script not ready; cannot post edited {burp_kind}/{item_id}")
            return
        script.post({
            "kind": f"edit-{burp_kind}",
            "type": f"edit-{burp_kind}",
            "id": item_id,
            "body": edited,
            "payload": edited,
        })

    try:
        _session, script = load_frida_script(args, on_message)
        script_holder["script"] = script
        print("[bridge] press Ctrl-C to stop")
        sys.stdin.read()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
