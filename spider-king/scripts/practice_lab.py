#!/usr/bin/env python3
"""Run deterministic local hostile-protocol cases with decisive controls."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import http.client
import json
import secrets
import sys
import threading
import zlib
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlsplit


EXACT_BODY = b"page=1&empty=&name=alpha%20beta"
DECODE_DOCUMENT = {
    "anchor": "decode-chain-accepted",
    "items": [{"id": 1, "value": "alpha"}, {"id": 2, "value": "beta"}],
}
MAX_REQUEST_BODY_BYTES = 1024 * 1024
MAX_DECODE_COMPRESSED_BYTES = 1024 * 1024
MAX_DECODED_JSON_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 128
MAX_JSON_VALUES = 100_000
MAX_ACTIVE_SESSIONS = 1024
MAX_EXPORT_TASKS = 1024
MAX_EXPORT_FIELDS = 256


class RequestBodyError(ValueError):
    def __init__(self, message: str, *, too_large: bool = False) -> None:
        super().__init__(message)
        self.too_large = too_large


def validate_json_limits(document: Any, *, label: str) -> None:
    stack: list[tuple[Any, int]] = [(document, 1)]
    count = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if count > MAX_JSON_VALUES:
            raise ValueError(f"{label} contains too many values")
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"{label} exceeds the JSON nesting limit")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)


@dataclass(frozen=True)
class LabResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def header(self, name: str) -> Optional[str]:
        lowered = name.casefold()
        for key, value in reversed(self.headers):
            if key.casefold() == lowered:
                return value
        return None


@dataclass(frozen=True)
class SessionMaterial:
    cookie: str
    token: str


class PracticeState:
    def __init__(
        self,
        secret: Optional[bytes] = None,
        *,
        max_sessions: int = MAX_ACTIVE_SESSIONS,
        max_exports: int = MAX_EXPORT_TASKS,
    ) -> None:
        if max_sessions < 1 or max_exports < 1:
            raise ValueError("practice state limits must be positive")
        self._lock = threading.Lock()
        self._next_session = 1
        self._secret = secret or secrets.token_bytes(32)
        self.tokens: dict[str, str] = {}
        self.contexts: dict[str, dict[str, Any]] = {}
        self.exports: dict[str, dict[str, Any]] = {}
        self._next_export = 1
        self.max_sessions = max_sessions
        self.max_exports = max_exports
        # Pre-seed one historical successful export that must not be reused blindly.
        self.exports["t0001"] = {
            "task_id": "t0001",
            "status": 2,
            "start": "2025-01-01",
            "end": "2025-01-02",
            "fields": ["a"],
        }

    def issue_session(self) -> tuple[str, str]:
        with self._lock:
            if len(self.tokens) + len(self.contexts) >= self.max_sessions:
                raise RuntimeError("practice session limit reached")
            session_id = f"s{self._next_session:04d}"
            self._next_session += 1
            token = hmac.new(
                self._secret,
                session_id.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()[:24]
            self.tokens[session_id] = token
        return session_id, token

    def issue_context_session(self) -> str:
        with self._lock:
            if len(self.tokens) + len(self.contexts) >= self.max_sessions:
                raise RuntimeError("practice session limit reached")
            session_id = f"c{self._next_session:04d}"
            self._next_session += 1
            self.contexts[session_id] = {
                "account": True,
                "tenant": "",
                "role": "",
                "range_type": "",
                "range_value": "",
            }
        return session_id

    def issue_export_task(self, *, start: str, end: str, fields: list[str]) -> str:
        with self._lock:
            if len(self.exports) >= self.max_exports:
                raise RuntimeError("practice export task limit reached")
            task_id = f"t{self._next_export:04d}"
            self._next_export += 1
            # avoid colliding with seeded t0001
            while task_id in self.exports:
                task_id = f"t{self._next_export:04d}"
                self._next_export += 1
            self.exports[task_id] = {
                "task_id": task_id,
                "status": 2,
                "start": start,
                "end": end,
                "fields": list(fields),
            }
        return task_id



class PracticeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SpiderKingPracticeLab/1"

    @property
    def state(self) -> PracticeState:
        return self.server.practice_state  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send_bytes(
        self,
        status: int,
        body: bytes,
        *,
        content_type: str = "application/json",
        headers: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def send_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        headers: tuple[tuple[str, str], ...] = (),
    ) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        self.send_bytes(status, body, headers=headers)

    def read_body(self) -> bytes:
        raw = self.headers.get("Content-Length", "0")
        try:
            length = int(raw)
        except ValueError:
            raise RequestBodyError("invalid Content-Length") from None
        if length < 0:
            raise RequestBodyError("invalid Content-Length")
        if length > MAX_REQUEST_BODY_BYTES:
            raise RequestBodyError("request body exceeds limit", too_large=True)
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestBodyError("request body ended before Content-Length")
        return body

    def session_id(self) -> Optional[str]:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get("lab_session")
        return None if morsel is None else morsel.value

    def context_session_id(self) -> Optional[str]:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get("lab_ctx")
        return None if morsel is None else morsel.value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            self.send_json(200, {"ok": True})
            return

        if parsed.path == "/digest/vector":
            token = correct_modded_token()
            self.send_json(
                200,
                {
                    "path": DIGEST_PATH,
                    "now": DIGEST_NOW,
                    "page": DIGEST_PAGE,
                    "token": token,
                    "anchor": "modded-digest-vector",
                },
            )
            return

        if parsed.path == "/digest/data":
            path_value = (query.get("path") or [""])[0]
            now_value = (query.get("now") or [""])[0]
            page_value = (query.get("page") or [""])[0]
            token_value = (query.get("token") or [""])[0]
            expected = correct_modded_token(path_value, now_value, page_value)
            if token_value != expected:
                self.send_json(403, {"error": "modded-digest-mismatch"})
                return
            self.send_json(200, {"anchor": "modded-digest-accepted", "page": page_value})
            return

        if parsed.path == "/session/entry":
            try:
                session_id, _token = self.state.issue_session()
            except RuntimeError:
                self.send_json(503, {"error": "session-capacity-reached"})
                return
            self.send_json(
                200,
                {"next": "/session/bootstrap"},
                headers=(("Set-Cookie", f"lab_session={session_id}; Path=/; HttpOnly"),),
            )
            return

        if parsed.path == "/session/bootstrap":
            session_id = self.session_id()
            token = self.state.tokens.get(session_id or "")
            if token is None:
                self.send_json(401, {"error": "missing-session"})
                return
            self.send_json(200, {"token": token, "next": "/session/data"})
            return

        if parsed.path == "/decode/data":
            raw = json.dumps(DECODE_DOCUMENT, separators=(",", ":")).encode("utf-8")
            encoded = b"LAB1." + base64.b64encode(zlib.compress(raw))
            self.send_bytes(200, encoded, content_type="application/octet-stream")
            return

        if parsed.path == "/page/list" and query.get("page") == ["1"]:
            self.send_json(
                200,
                {"items": [{"id": 1}], "next": "/ui?page=2", "anchor": "page-one"},
            )
            return

        if parsed.path == "/page/list" and query.get("page") == ["2"]:
            self.send_json(404, {"error": "guessed-route-family"})
            return

        if parsed.path == "/ui" and query.get("page") == ["2"]:
            self.send_json(
                200,
                {
                    "items": [{"id": 2}],
                    "next": None,
                    "anchor": "route-pivot-accepted",
                },
            )
            return


        if parsed.path == "/ctx/auth-list":
            self.send_json(200, {"rows": list(CTX_AUTH_ROWS)})
            return

        if parsed.path == "/ctx/identity":
            session_id = self.context_session_id()
            context = self.state.contexts.get(session_id or "")
            if context is None:
                self.send_json(401, {"error": "missing-context-session"})
                return
            self.send_json(200, {"account": True, **context, "anchor": "context-identity"})
            return

        if parsed.path == "/ctx/data":
            session_id = self.context_session_id()
            context = self.state.contexts.get(session_id or "")
            if context is None:
                self.send_json(401, {"error": "missing-context-session"})
                return
            if not context_matches_target(context):
                self.send_json(409, {"error": "identity-mismatch", "context": context})
                return
            self.send_json(
                200,
                {
                    "anchor": "multi-context-accepted",
                    "rows": [{"shop": CTX_TARGET["range_value"], "amount": 12}],
                },
            )
            return


        if parsed.path == "/export/history":
            tasks = sorted(self.state.exports.values(), key=lambda item: item["task_id"])
            self.send_json(200, {"task_list": tasks, "anchor": "export-history"})
            return

        if parsed.path == "/export/status":
            task_id = (query.get("task_id") or [""])[0]
            task = self.state.exports.get(task_id)
            if task is None:
                self.send_json(404, {"error": "unknown-task"})
                return
            self.send_json(200, {"task": task, "anchor": "export-status"})
            return

        if parsed.path == "/export/download":
            task_id = (query.get("task_id") or [""])[0]
            task = self.state.exports.get(task_id)
            if task is None:
                self.send_json(404, {"error": "unknown-task"})
                return
            # File columns equal the task field set; thinner old tasks fail completeness gates.
            self.send_json(
                200,
                {
                    "task_id": task_id,
                    "columns": list(task["fields"]),
                    "rows": [{"a": 1}],
                    "anchor": "export-download",
                },
            )
            return

        self.send_json(404, {"error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        try:
            body = self.read_body()
        except RequestBodyError as exc:
            self.send_json(
                413 if exc.too_large else 400,
                {"error": "request-body-too-large" if exc.too_large else "invalid-request-body"},
            )
            return

        if parsed.path == "/exact/data":
            duplicate_order = self.headers.get_all("X-Order") or []
            accepted = (
                body == EXACT_BODY
                and self.headers.get("X-Wire-Slot") == "blob-v1"
                and duplicate_order == ["first", "second"]
                and self.headers.get("ETag") is None
            )
            if not accepted:
                self.send_json(422, {"error": "wire-contract-mismatch"})
                return
            self.send_json(200, {"anchor": "exact-wire-accepted"})
            return

        if parsed.path == "/session/data":
            session_id = self.session_id()
            expected = self.state.tokens.get(session_id or "")
            supplied = self.headers.get("X-Bootstrap-Token")
            if expected is None or not hmac.compare_digest(expected, supplied or ""):
                self.send_json(403, {"error": "session-chain-mismatch"})
                return
            self.send_json(200, {"anchor": "same-chain-accepted"})
            return


        if parsed.path == "/ctx/login":
            try:
                session_id = self.state.issue_context_session()
            except RuntimeError:
                self.send_json(503, {"error": "session-capacity-reached"})
                return
            self.send_json(
                200,
                {"ok": True, "handoff": "CTX-TICKET", "anchor": "context-login"},
                headers=(("Set-Cookie", f"lab_ctx={session_id}; Path=/; HttpOnly"),),
            )
            return

        if parsed.path == "/ctx/activate":
            session_id = self.context_session_id()
            context = self.state.contexts.get(session_id or "")
            if context is None:
                self.send_json(401, {"error": "missing-context-session"})
                return
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                validate_json_limits(payload, label="context activation payload")
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
                self.send_json(400, {"error": "invalid-json"})
                return
            if not isinstance(payload, dict):
                self.send_json(400, {"error": "invalid-json"})
                return
            # Always accept tenant/role when present.
            if payload.get("tenant"):
                context["tenant"] = str(payload["tenant"])
            if payload.get("role"):
                context["role"] = str(payload["role"])
            range_type = str(payload.get("range_type") or "")
            range_value = str(payload.get("range_value") or "")
            # Silent incomplete activation: missing type leaves previous/empty range.
            if range_type and range_value:
                context["range_type"] = range_type
                context["range_value"] = range_value
            self.send_json(200, {"success": True, "anchor": "context-activate"})
            return


        if parsed.path == "/export/create":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                validate_json_limits(payload, label="export creation payload")
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
                self.send_json(400, {"error": "invalid-json"})
                return
            if not isinstance(payload, dict):
                self.send_json(400, {"error": "invalid-json"})
                return
            if payload.get("force_empty_success"):
                self.send_json(200, {"success": True, "anchor": "export-empty-success"})
                return
            start = str(payload.get("start") or "")
            end = str(payload.get("end") or "")
            fields = payload.get("fields") or []
            if not start or not end or not isinstance(fields, list) or not fields:
                self.send_json(400, {"error": "missing-export-filters"})
                return
            try:
                validated_fields = validate_field_names(fields, label="export fields")
                task_id = self.state.issue_export_task(
                    start=start,
                    end=end,
                    fields=list(validated_fields),
                )
            except ValueError:
                self.send_json(400, {"error": "invalid-export-fields"})
                return
            except RuntimeError:
                self.send_json(503, {"error": "export-capacity-reached"})
                return
            self.send_json(
                200,
                {"success": True, "task_id": task_id, "anchor": "export-created"},
            )
            return

        self.send_json(404, {"error": "not-found"})


class PracticeLab:
    def __init__(self, port: int = 0) -> None:
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> str:
        if self.server is not None:
            raise RuntimeError("practice lab is already running")
        server = ThreadingHTTPServer(("127.0.0.1", self.port), PracticeHandler)
        server.practice_state = PracticeState()  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.server = server
        self.thread = thread
        host, port = server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        server, thread = self.server, self.thread
        self.server = None
        self.thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)

    def serve_forever(self) -> str:
        base_url = self.start()
        thread = self.thread
        if self.server is None or thread is None:
            raise RuntimeError("practice lab did not start")
        print(f"practice_lab_url={base_url}", flush=True)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
        return base_url

    def __enter__(self) -> str:
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()


def simple_request(
    base_url: str,
    method: str,
    path: str,
    *,
    headers: tuple[tuple[str, str], ...] = (),
    body: bytes = b"",
) -> LabResponse:
    target = urlsplit(base_url)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=5)
    try:
        connection.putrequest(method.upper(), path)
        for name, value in headers:
            connection.putheader(name, value)
        if body and not any(name.casefold() == "content-length" for name, _ in headers):
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body if body else None)
        response = connection.getresponse()
        return LabResponse(response.status, tuple(response.getheaders()), response.read())
    finally:
        connection.close()


def exact_bytes_request(
    base_url: str,
    *,
    correct: bool,
    failure: Optional[str] = None,
) -> LabResponse:
    if correct and failure is not None:
        raise ValueError("a correct request cannot select a failure control")
    if not correct and failure is None:
        failure = "wrong-slot"

    headers: tuple[tuple[str, str], ...]
    headers = (
        ("Content-Type", "application/x-www-form-urlencoded"),
        ("X-Wire-Slot", "blob-v1"),
        ("X-Order", "first"),
        ("X-Order", "second"),
    )
    body = EXACT_BODY
    if failure == "wrong-slot":
        headers = (
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("ETag", "blob-v1"),
            ("X-Order", "first"),
            ("X-Order", "second"),
        )
    elif failure == "wrong-body":
        body = b"page=1&empty=&name=alpha+beta"
    elif failure == "wrong-order":
        headers = (
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("X-Wire-Slot", "blob-v1"),
            ("X-Order", "second"),
            ("X-Order", "first"),
        )
    elif failure is not None:
        raise ValueError(f"unknown exact-wire failure control: {failure}")
    return simple_request(base_url, "POST", "/exact/data", headers=headers, body=body)


def acquire_session(base_url: str) -> SessionMaterial:
    entry = simple_request(base_url, "GET", "/session/entry")
    set_cookie = entry.header("Set-Cookie")
    if entry.status != 200 or not set_cookie:
        raise RuntimeError("practice session entry failed")
    cookie = set_cookie.split(";", 1)[0]
    bootstrap = simple_request(
        base_url,
        "GET",
        "/session/bootstrap",
        headers=(("Cookie", cookie),),
    )
    if bootstrap.status != 200:
        raise RuntimeError("practice session bootstrap failed")
    token = json.loads(bootstrap.body)["token"]
    return SessionMaterial(cookie=cookie, token=token)


def session_business_request(base_url: str, cookie: str, token: str) -> LabResponse:
    return simple_request(
        base_url,
        "POST",
        "/session/data",
        headers=(("Cookie", cookie), ("X-Bootstrap-Token", token)),
        body=b"{}",
    )


def decode_payload(payload: bytes) -> dict[str, Any]:
    if not payload.startswith(b"LAB1."):
        raise ValueError("decode payload is missing the LAB1 prefix")
    if len(payload) > 5 + ((MAX_DECODE_COMPRESSED_BYTES + 2) // 3) * 4:
        raise ValueError("encoded practice decode payload exceeds limit")
    try:
        compressed = base64.b64decode(payload[5:], validate=True)
        if len(compressed) > MAX_DECODE_COMPRESSED_BYTES:
            raise ValueError("compressed practice decode payload exceeds limit")
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_DECODED_JSON_BYTES + 1)
        if len(raw) > MAX_DECODED_JSON_BYTES or decompressor.unconsumed_tail:
            raise ValueError("decoded practice payload exceeds limit")
        raw += decompressor.flush(MAX_DECODED_JSON_BYTES + 1 - len(raw))
        if len(raw) > MAX_DECODED_JSON_BYTES:
            raise ValueError("decoded practice payload exceeds limit")
        if not decompressor.eof or decompressor.unused_data:
            raise ValueError("invalid compressed practice payload")
        document = json.loads(raw)
        validate_json_limits(document, label="decoded practice payload")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid practice decode payload: JSON is not valid UTF-8") from exc
    except binascii.Error as exc:
        raise ValueError("invalid practice decode payload: invalid base64") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("invalid practice decode payload: invalid JSON") from exc
    except RecursionError as exc:
        raise ValueError("invalid practice decode payload: JSON nesting exceeds limit") from exc
    except zlib.error as exc:
        raise ValueError("invalid practice decode payload: invalid compression") from exc
    if not isinstance(document, dict):
        raise ValueError("decoded practice payload must be a JSON object")
    return document



MASK32 = 0xFFFFFFFF
DIGEST_PATH = "/api/question/lab"
DIGEST_NOW = "1700000000000"
DIGEST_PAGE = "1"


def _rotl(x: int, n: int) -> int:
    x &= MASK32
    n %= 32
    if n == 0:
        return x
    return ((x << n) | (x >> (32 - n))) & MASK32


def _mask_bytes(message: bytes, *, apply_mask: bool) -> bytes:
    if apply_mask:
        return bytes(b & 0xFE for b in message)
    return message


def modded_digest(message: bytes, *, apply_mask: bool = True, fix_rotl_zero: bool = True) -> str:
    """Toy modified digest used only for offline porting controls.

    It is intentionally not a real national algorithm. The useful invariants are:
    - per-byte packing masks
    - ROTL(x, 0) identity under JS-like uint32 semantics
    - divergence from stock hashlib digests
    """
    data = _mask_bytes(message, apply_mask=apply_mask)
    state = [0x7380067C, 0x7634D2C9, 0x170042D6, 0xDA887534]
    for index, value in enumerate(data):
        word = state[index % 4]
        shift = value % 32
        if fix_rotl_zero:
            word = _rotl(word, shift)
        else:
            # Deliberately wrong port: zero the word on shift==0 instead of preserving uint32 identity.
            # This mirrors the class of JS/Python rotate edge mistakes that only fail on some inputs.
            if shift == 0:
                word = 0
            else:
                word = ((word << shift) | (word >> (32 - shift))) & MASK32
        word = (word + value + 0x79DD4519) & MASK32
        word ^= 0xFCFFFFFF
        state[index % 4] = word
    return "".join(f"{item:08x}" for item in state) + "".join(
        f"{(item ^ 0xA5A5A5A5) & MASK32:08x}" for item in state
    )


def digest_preimage(path: str = DIGEST_PATH, now: str = DIGEST_NOW, page: str = DIGEST_PAGE) -> bytes:
    return f"{path}{now}{page}".encode("utf-8")


def correct_modded_token(path: str = DIGEST_PATH, now: str = DIGEST_NOW, page: str = DIGEST_PAGE) -> str:
    return modded_digest(digest_preimage(path, now, page), apply_mask=True, fix_rotl_zero=True)


def standard_digest_token(path: str = DIGEST_PATH, now: str = DIGEST_NOW, page: str = DIGEST_PAGE) -> str:
    return hashlib.sha256(digest_preimage(path, now, page)).hexdigest()


def missing_mask_token(path: str = DIGEST_PATH, now: str = DIGEST_NOW, page: str = DIGEST_PAGE) -> str:
    return modded_digest(digest_preimage(path, now, page), apply_mask=False, fix_rotl_zero=True)


def broken_rotl_token(path: str = DIGEST_PATH, now: str = DIGEST_NOW, page: str = DIGEST_PAGE) -> str:
    return modded_digest(digest_preimage(path, now, page), apply_mask=True, fix_rotl_zero=False)


def digest_request(
    base_url: str,
    *,
    token: str | None = None,
    mode: str = "correct",
    path: str = DIGEST_PATH,
    now: str = DIGEST_NOW,
    page: str = DIGEST_PAGE,
) -> LabResponse:
    if token is None:
        if mode == "correct":
            token = correct_modded_token(path, now, page)
        elif mode == "standard":
            token = standard_digest_token(path, now, page)
        elif mode == "missing-mask":
            token = missing_mask_token(path, now, page)
        elif mode == "broken-rotl":
            token = broken_rotl_token(path, now, page)
        else:
            raise ValueError(f"unknown digest mode: {mode}")
    query = urlencode({"path": path, "now": now, "page": page, "token": token})
    return simple_request(base_url, "GET", f"/digest/data?{query}")



CTX_TARGET = {
    "tenant": "tenant-a",
    "role": "supplier",
    "range_type": "SHOP",
    "range_value": "shop-100",
}
CTX_AUTH_ROWS = (
    {"label": "Alpha Shop", "value": "shop-100"},
    {"label": "Alpha Shop East", "value": "shop-200"},
    {"label": "Beta Shop", "value": "shop-300"},
)


def context_matches_target(context: dict[str, Any]) -> bool:
    return all(str(context.get(key) or "") == value for key, value in CTX_TARGET.items())


def resolve_protocol_id(label: str, rows: list[dict[str, str]] | tuple[dict[str, str], ...]) -> str:
    matches = [row["value"] for row in rows if row.get("label") == label]
    if len(matches) != 1:
        raise ValueError(f"label resolution requires exactly one match; got {len(matches)}")
    return matches[0]


def multi_context_request(
    base_url: str,
    *,
    mode: str = "correct",
) -> dict[str, LabResponse]:
    """Exercise login + activation + identity + data on one cookie chain."""
    login = simple_request(base_url, "POST", "/ctx/login", body=b"{}")
    cookie_header = login.header("Set-Cookie") or ""
    # Extract lab_ctx=<id>
    cookie_value = ""
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("lab_ctx="):
            cookie_value = part
            break
    if not cookie_value:
        raise AssertionError("context login did not set lab_ctx")

    if mode == "correct":
        payload = dict(CTX_TARGET)
    elif mode == "missing-range-type":
        payload = {
            "tenant": CTX_TARGET["tenant"],
            "role": CTX_TARGET["role"],
            "range_value": CTX_TARGET["range_value"],
        }
    elif mode == "label-as-value":
        payload = {
            "tenant": CTX_TARGET["tenant"],
            "role": CTX_TARGET["role"],
            "range_type": CTX_TARGET["range_type"],
            "range_value": "Alpha Shop",
        }
    else:
        raise ValueError(f"unknown multi-context mode: {mode}")

    body = json.dumps(payload, separators=(",", ":")).encode("ascii")
    activate = simple_request(
        base_url,
        "POST",
        "/ctx/activate",
        headers=(
            ("Content-Type", "application/json"),
            ("Cookie", cookie_value),
        ),
        body=body,
    )
    identity = simple_request(
        base_url,
        "GET",
        "/ctx/identity",
        headers=(("Cookie", cookie_value),),
    )
    data = simple_request(
        base_url,
        "GET",
        "/ctx/data",
        headers=(("Cookie", cookie_value),),
    )
    return {"login": login, "activate": activate, "identity": identity, "data": data}



EXPORT_TARGET = {
    "start": "2026-01-01",
    "end": "2026-01-02",
    "fields": ["a", "b", "c"],
}


def validate_field_names(values: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a list")
    if not values or len(values) > MAX_EXPORT_FIELDS:
        raise ValueError(f"{label} must contain between 1 and {MAX_EXPORT_FIELDS} names")
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"{label} must contain non-empty canonical strings")
        if value in seen:
            raise ValueError(f"{label} must not contain duplicates")
        seen.add(value)
        output.append(value)
    return tuple(output)


def export_history(base_url: str) -> list[dict[str, Any]]:
    response = simple_request(base_url, "GET", "/export/history")
    if response.status != 200:
        raise AssertionError(f"export history failed: {response.status}")
    payload = json.loads(response.body)
    return list(payload.get("task_list") or [])


def export_create(
    base_url: str,
    *,
    mode: str = "correct",
    start: str = EXPORT_TARGET["start"],
    end: str = EXPORT_TARGET["end"],
    fields: list[str] | None = None,
) -> LabResponse:
    payload: dict[str, Any]
    if mode == "correct":
        payload = {"start": start, "end": end, "fields": list(fields or EXPORT_TARGET["fields"])}
    elif mode == "empty-success":
        payload = {
            "start": start,
            "end": end,
            "fields": list(fields or EXPORT_TARGET["fields"]),
            "force_empty_success": True,
        }
    else:
        raise ValueError(f"unknown export create mode: {mode}")
    body = json.dumps(payload, separators=(",", ":")).encode("ascii")
    return simple_request(
        base_url,
        "POST",
        "/export/create",
        headers=(("Content-Type", "application/json"),),
        body=body,
    )


def export_download(base_url: str, task_id: str) -> LabResponse:
    return simple_request(base_url, "GET", f"/export/download?task_id={task_id}")


def select_export_task(
    *,
    before_ids: set[str],
    after_tasks: list[dict[str, Any]],
    create_task_id: str | None,
    start: str,
    end: str,
    fields: list[str],
) -> str:
    """Isolate this run's task; never accept pre-create history alone."""
    requested_fields = frozenset(validate_field_names(fields, label="requested fields"))
    candidates: list[dict[str, Any]] = []
    for index, task in enumerate(after_tasks):
        if not isinstance(task, dict):
            raise ValueError(f"after_tasks[{index}] must be an object")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id != task_id.strip():
            raise ValueError(f"after_tasks[{index}].task_id must be a non-empty string")
        if task_id in before_ids or task.get("start") != start or task.get("end") != end:
            continue
        try:
            candidate_fields = frozenset(
                validate_field_names(task.get("fields"), label=f"after_tasks[{index}].fields")
            )
        except ValueError:
            continue
        if candidate_fields == requested_fields:
            candidates.append(task)

    if create_task_id is not None:
        if (
            not isinstance(create_task_id, str)
            or not create_task_id
            or create_task_id != create_task_id.strip()
        ):
            raise ValueError("create task_id must be a non-empty string")
        candidates = [task for task in candidates if task["task_id"] == create_task_id]
    if len(candidates) != 1:
        raise ValueError(f"export task isolation requires one new matching task; got {len(candidates)}")
    return str(candidates[0]["task_id"])


def export_field_gate(*, requested_fields: list[str], downloaded_columns: list[str]) -> None:
    requested = frozenset(validate_field_names(requested_fields, label="requested fields"))
    downloaded = frozenset(validate_field_names(downloaded_columns, label="downloaded columns"))
    if downloaded != requested:
        raise ValueError(
            "export field-completeness gate failed: "
            f"requested={len(requested)} downloaded={len(downloaded)}"
        )


def async_export_flow(base_url: str, *, mode: str = "correct") -> dict[str, Any]:
    before = export_history(base_url)
    before_ids = {str(task["task_id"]) for task in before}
    create = export_create(base_url, mode="empty-success" if mode == "empty-success" else "correct")
    after = export_history(base_url)
    create_payload = json.loads(create.body)
    create_task_id = create_payload.get("task_id")

    result: dict[str, Any] = {
        "create": create,
        "before_ids": sorted(before_ids),
        "after_ids": sorted(str(task["task_id"]) for task in after),
    }

    if mode == "empty-success":
        result["new_task_ids"] = sorted(set(result["after_ids"]) - before_ids)
        return result

    if mode == "pollute-newest":
        # Deliberately reuse a pre-create historical success without isolation rules.
        polluted = sorted(before_ids)[0] if before_ids else sorted(str(task["task_id"]) for task in after)[0]
        download = export_download(base_url, polluted)
        columns = list(json.loads(download.body).get("columns") or [])
        result["selected_task_id"] = polluted
        result["download"] = download
        result["columns"] = columns
        try:
            export_field_gate(requested_fields=list(EXPORT_TARGET["fields"]), downloaded_columns=columns)
            result["gate"] = "passed"
        except ValueError as exc:
            result["gate"] = "failed"
            result["gate_error"] = str(exc)
        return result

    selected = select_export_task(
        before_ids=before_ids,
        after_tasks=after,
        create_task_id=str(create_task_id) if create_task_id else None,
        start=EXPORT_TARGET["start"],
        end=EXPORT_TARGET["end"],
        fields=list(EXPORT_TARGET["fields"]),
    )
    download = export_download(base_url, selected)
    columns = list(json.loads(download.body).get("columns") or [])
    export_field_gate(requested_fields=list(EXPORT_TARGET["fields"]), downloaded_columns=columns)
    result["selected_task_id"] = selected
    result["download"] = download
    result["columns"] = columns
    result["gate"] = "passed"
    return result


def describe_cases() -> list[dict[str, str]]:
    return [
        {
            "id": "exact-wire",
            "invariant": "Exact body bytes, duplicate header order, and final slot all matter",
            "negative_control": "Move the blob to ETag and use semantically equivalent form bytes",
        },
        {
            "id": "same-session-bootstrap",
            "invariant": "Entry cookie and bootstrap token stay on one session chain",
            "negative_control": "Splice a token into a neighboring session",
        },
        {
            "id": "response-decode",
            "invariant": "Strip prefix, Base64 decode, then zlib decompress before JSON parsing",
            "negative_control": "Skip prefix validation or change transform order",
        },
        {
            "id": "pagination-pivot",
            "invariant": "Follow the live next route across a route-family pivot",
            "negative_control": "Guess page 2 from page 1 URL arithmetic",
        },
        {
            "id": "modded-digest",
            "invariant": "Modified digest ports need packing masks and ROTL(0) identity; stock hashes are not enough",
            "negative_control": "Use standard SHA-256, drop the byte mask, or break ROTL(x, 0)",
        },
        {
            "id": "multi-context-activation",
            "invariant": "Account login plus full business-context activation must pass final identity reread",
            "negative_control": "Omit range type, submit UI labels as ids, or accept ambiguous label matches",
        },
        {
            "id": "async-export-isolation",
            "invariant": "Async exports need new-task proof, condition match, and field-completeness gates",
            "negative_control": "Accept empty create success, reuse historical tasks, or persist thinner columns",
        },
    ]


def run_self_test() -> None:
    lab = PracticeLab()
    base_url = lab.start()
    try:
        exact_good = exact_bytes_request(base_url, correct=True)
        exact_bad = [
            exact_bytes_request(base_url, correct=False, failure=failure)
            for failure in ("wrong-slot", "wrong-body", "wrong-order")
        ]
        if exact_good.status != 200 or any(item.status == 200 for item in exact_bad):
            raise AssertionError("exact-wire controls failed")

        first = acquire_session(base_url)
        second = acquire_session(base_url)
        session_good = session_business_request(base_url, first.cookie, first.token)
        session_bad = session_business_request(base_url, second.cookie, first.token)
        if session_good.status != 200 or session_bad.status == 200:
            raise AssertionError("same-session controls failed")

        encoded = simple_request(base_url, "GET", "/decode/data")
        if decode_payload(encoded.body).get("anchor") != "decode-chain-accepted":
            raise AssertionError("decode positive control failed")
        try:
            decode_payload(encoded.body.removeprefix(b"LAB1."))
        except ValueError:
            pass
        else:
            raise AssertionError("decode negative control failed")

        first_page = simple_request(base_url, "GET", "/page/list?page=1")
        next_path = json.loads(first_page.body)["next"]
        guessed = simple_request(base_url, "GET", "/page/list?page=2")
        actual = simple_request(base_url, "GET", next_path)
        if guessed.status == 200 or actual.status != 200:
            raise AssertionError("pagination route controls failed")

        digest_good = digest_request(base_url, mode="correct")
        digest_bad = [
            digest_request(base_url, mode="standard"),
            digest_request(base_url, mode="missing-mask"),
            digest_request(base_url, mode="broken-rotl"),
        ]
        if digest_good.status != 200 or any(item.status == 200 for item in digest_bad):
            raise AssertionError("modded-digest controls failed")
        if correct_modded_token() == standard_digest_token():
            raise AssertionError("modded digest unexpectedly matched stock sha256")

        ctx_good = multi_context_request(base_url, mode="correct")
        if ctx_good["data"].status != 200:
            raise AssertionError("multi-context positive control failed")
        ctx_bad_type = multi_context_request(base_url, mode="missing-range-type")
        ctx_bad_label = multi_context_request(base_url, mode="label-as-value")
        if ctx_bad_type["activate"].status != 200 or ctx_bad_type["data"].status == 200:
            raise AssertionError("missing-range-type should silently under-activate")
        if ctx_bad_label["data"].status == 200:
            raise AssertionError("label-as-value should fail identity gate")
        try:
            resolve_protocol_id("Alpha Shop", CTX_AUTH_ROWS)
        except ValueError as exc:
            raise AssertionError(f"exact label should resolve: {exc}") from exc
        try:
            resolve_protocol_id("Alpha", CTX_AUTH_ROWS)
        except ValueError:
            pass
        else:
            raise AssertionError("ambiguous/partial label must fail closed")

        export_good = async_export_flow(base_url, mode="correct")
        if export_good.get("gate") != "passed":
            raise AssertionError("async-export positive control failed")
        export_empty = async_export_flow(base_url, mode="empty-success")
        if export_empty["create"].status != 200 or export_empty.get("new_task_ids"):
            raise AssertionError("empty-success should not create tasks")
        export_pollute = async_export_flow(base_url, mode="pollute-newest")
        if export_pollute.get("gate") != "failed":
            raise AssertionError("historical pollution should fail field gate")
    finally:
        lab.stop()
    print("practice_lab_self_test=PASS cases=7 negative_controls=15")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run all positive and negative controls")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("describe", help="Print the practice case contracts")
    serve = subparsers.add_parser("serve", help="Serve the local lab on loopback")
    serve.add_argument("--port", type=int, default=8765, help="Loopback port; use 0 for an ephemeral port")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        try:
            run_self_test()
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            print(f"practice_lab_self_test=FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.command == "describe":
        print(json.dumps(describe_cases(), indent=2))
        return 0
    if args.command == "serve":
        PracticeLab(port=args.port).serve_forever()
        return 0
    build_parser().print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
