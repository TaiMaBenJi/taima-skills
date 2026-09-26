#!/usr/bin/env python3
"""Extract Android request, endpoint, header, and signing anchors from text trees."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {
    ".java",
    ".kt",
    ".smali",
    ".xml",
    ".json",
    ".properties",
    ".txt",
    ".log",
    ".html",
    ".js",
}

URL_RE = re.compile(r"(?i)\b(?:https?|wss?)://[^\s\"'<>\\)\\]}]+")
HOST_RE = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|cn|net|org|io|me|co|cc|app|top|xyz)\b")
RETROFIT_RE = re.compile(r"@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|HTTP|Headers|Query|Field|Body|Url|Path)\s*(?:\((.*?)\))?", re.I)
REQUEST_RE = re.compile(
    r"OkHttp|Retrofit|HttpURLConnection|Volley|Request\.Builder|addHeader|setRequestProperty|"
    r"CertificatePinner|TrustManager|HostnameVerifier|WebView|loadUrl|postUrl|evaluateJavascript|"
    r"RpcInvoker|HttpCaller|HttpUrlRequest|Serializer|JsonSerializerV2|SignJsonSerializer|PBSerializer",
    re.I,
)
SIGN_RE = re.compile(
    r"\bsign\b|signature|token|nonce|timestamp|deviceId|encrypt|decrypt|\bHmac\b|MessageDigest|Cipher|\bMD5\b|\bSHA-?1\b|\bSHA-?256\b|\bAES\b|\bRSA\b|Base64",
    re.I,
)
HEADER_RE = re.compile(
    r"(?i)\b(?:Authorization|Cookie|User-Agent|Content-Type|Accept|X-[A-Za-z0-9_-]+|api[-_]?key|token)\b"
)
MPAAS_RE = re.compile(
    r"com\.alipay\.mobile\.common\.rpc|com\.alipay\.mobile\.common\.transport|"
    r"RpcInvoker|HttpCaller|HttpUrlRequest|InnerRpcInvokeContext|"
    r"JsonSerializerV2|SignJsonSerializer|SimpleRpcJsonSerializerV2|PBSerializer|SimpleRpcPBSerializer|"
    r"\bSerializer\.packet\b|\bgetSerializer\b|\bgetReqData\b|\bsetReqData\b|\bgetResData\b|\bsetResData\b",
    re.I,
)


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and (item.suffix in TEXT_SUFFIXES or item.suffix == ""):
                    yield item


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def is_generated_noise(path: Path, line: str) -> bool:
    if path.name in {"R.java", "R2.java"}:
        return True
    stripped = line.strip()
    return stripped.startswith("public static final int ") or stripped.startswith("public static final class ")


def is_probable_java_package_host(value: str, line: str) -> bool:
    lowered = value.lower()
    if lowered.startswith(("android.", "androidx.", "java.", "javax.", "kotlin.", "kotlinx.", "dalvik.")):
        return True
    stripped = line.strip()
    if stripped.startswith(("import ", "package ")) and "://" not in stripped:
        return True
    if stripped.startswith("<") and "://" not in stripped and any(attr in stripped for attr in ("android:name=", "package=")):
        return True
    if lowered == "schemas.android.com":
        return True
    return False


def is_signing_noise(line: str) -> bool:
    stripped = line.strip()
    return "protectionLevel=" in stripped or "android:permission=" in stripped


def is_request_api_noise(path: Path, line: str) -> bool:
    parts = set(path.parts)
    stripped = line.strip()
    if "res" in parts and "://" not in stripped:
        return True
    if path.name == "AndroidManifest.xml" and not any(token in stripped for token in ("OkHttp", "WebView", "http://", "https://")):
        return True
    return False


def relpath(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            return str(path.relative_to(root))
        except ValueError:
            continue
    return str(path)


def add_hit(bucket: dict[str, list[dict]], key: str, value: str, path: Path, line: int, roots: list[Path], context: str):
    value = value.strip().strip("\"'")
    if not value:
        return
    bucket.setdefault(key, []).append(
        {
            "value": value[:500],
            "file": relpath(path, roots),
            "line": line,
            "context": context.strip()[:500],
        }
    )


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = (item["value"], item["file"], item["line"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def scan_file(path: Path, roots: list[Path], buckets: dict[str, list[dict]], max_line: int):
    text = read_text(path)
    if text is None:
        return
    for number, line in enumerate(text.splitlines(), 1):
        if is_generated_noise(path, line):
            continue
        short = line if len(line) <= max_line else line[:max_line] + "..."
        for match in URL_RE.finditer(line):
            add_hit(buckets, "urls", match.group(0), path, number, roots, short)
        for match in HOST_RE.finditer(line):
            if is_probable_java_package_host(match.group(0), line):
                continue
            add_hit(buckets, "hosts", match.group(0), path, number, roots, short)
        for match in RETROFIT_RE.finditer(line):
            add_hit(buckets, "retrofit_annotations", match.group(0), path, number, roots, short)
        if REQUEST_RE.search(line) and not is_request_api_noise(path, line):
            add_hit(buckets, "request_api_anchors", line.strip(), path, number, roots, short)
        if MPAAS_RE.search(line):
            add_hit(buckets, "mpaas_rpc_anchors", line.strip(), path, number, roots, short)
        if SIGN_RE.search(line) and not is_signing_noise(line):
            add_hit(buckets, "signing_crypto_anchors", line.strip(), path, number, roots, short)
        for match in HEADER_RE.finditer(line):
            add_hit(buckets, "header_anchors", match.group(0), path, number, roots, short)


def summarize(buckets: dict[str, list[dict]]) -> dict:
    result = {}
    for key, values in buckets.items():
        clean = dedupe(values)
        result[key] = {
            "count": len(clean),
            "items": clean,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JADX/apktool trees, dumped source trees, Burp/r0capture logs, or text files")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-line", type=int, default=300)
    args = parser.parse_args()

    roots = [path.resolve() for path in args.paths if path.exists()]
    buckets: dict[str, list[dict]] = {}
    file_count = 0
    for path in iter_files(args.paths):
        file_count += 1
        scan_file(path, roots, buckets, args.max_line)

    data = {
        "schema": "android-native-auto-reverse.request_endpoints.v1",
        "inputs": [str(path) for path in args.paths],
        "files_scanned": file_count,
        "results": summarize(buckets),
    }
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    print(
        "counts:",
        ", ".join(f"{key}={value['count']}" for key, value in data["results"].items()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
