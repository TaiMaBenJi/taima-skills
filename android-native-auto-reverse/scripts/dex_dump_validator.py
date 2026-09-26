#!/usr/bin/env python3
"""Validate and rank dex files produced by frida-dexdump or similar tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


HINT_PATTERNS = {
    "shell": re.compile(rb"StubApp|ShellApplication|ProxyApplication|DexHelper|SecShell|Bangcle|secexe", re.I),
    "native": re.compile(rb"System\.loadLibrary|System\.load|native |JNI|RegisterNatives", re.I),
    "crypto": re.compile(rb"AES|RSA|Hmac|MD5|SHA-?256|encrypt|decrypt|sign|signature|token|nonce|timestamp", re.I),
    "network": re.compile(rb"https?://|OkHttp|Retrofit|HttpURLConnection|WebView|wss?://", re.I),
    "business": re.compile(rb"login|auth|account|order|pay|risk|device|user|api|request|response", re.I),
}


def iter_dex_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(path.rglob("*"))
        else:
            continue
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() == ".dex" or candidate.name.startswith("classes"):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_header(data: bytes) -> dict:
    if len(data) < 112:
        return {"valid_magic": False, "reason": "too_small"}
    magic = data[:8]
    valid_magic = magic.startswith(b"dex\n") and magic[7] == 0
    endian = int.from_bytes(data[40:44], "little", signed=False)
    file_size = int.from_bytes(data[32:36], "little", signed=False)
    header_size = int.from_bytes(data[36:40], "little", signed=False)
    string_ids_size = int.from_bytes(data[56:60], "little", signed=False)
    return {
        "valid_magic": valid_magic,
        "magic": magic.decode("ascii", errors="replace"),
        "declared_file_size": file_size,
        "header_size": header_size,
        "string_ids_size": string_ids_size,
        "endian_tag": hex(endian),
        "declared_size_matches": file_size == len(data),
    }


def score_dex(data: bytes, header: dict) -> tuple[int, list[str], dict[str, int]]:
    score = 0
    reasons: list[str] = []
    counts: dict[str, int] = {}

    if header.get("valid_magic"):
        score += 20
        reasons.append("valid dex magic (+20)")
    if header.get("declared_size_matches"):
        score += 8
        reasons.append("declared file size matches (+8)")
    if len(data) >= 1024 * 1024:
        score += 10
        reasons.append("large dex >=1MB (+10)")
    elif len(data) >= 128 * 1024:
        score += 5
        reasons.append("medium dex >=128KB (+5)")

    string_count = int(header.get("string_ids_size", 0) or 0)
    if string_count >= 5000:
        score += 10
        reasons.append("many strings >=5000 (+10)")
    elif string_count >= 500:
        score += 5
        reasons.append("strings >=500 (+5)")

    for name, pattern in HINT_PATTERNS.items():
        count = len(pattern.findall(data))
        counts[name] = count
        if count:
            delta = min(count, 8)
            if name == "shell":
                score -= min(count, 8)
                reasons.append(f"shell hints:{count} (-{min(count, 8)})")
            else:
                score += delta
                reasons.append(f"{name} hints:{count} (+{delta})")

    return score, reasons, counts


def analyze(path: Path) -> dict:
    data = path.read_bytes()
    header = parse_header(data)
    score, reasons, hint_counts = score_dex(data, header)
    return {
        "path": str(path),
        "name": path.name,
        "size": len(data),
        "sha256": sha256_file(path),
        "header": header,
        "score": score,
        "reasons": reasons,
        "hint_counts": hint_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    dexes = [analyze(path) for path in iter_dex_files(args.paths)]
    dexes.sort(key=lambda item: (item["score"], item["size"]), reverse=True)
    result = {
        "schema": "android-native-auto-reverse.dex_dump_validation.v1",
        "inputs": [str(path) for path in args.paths],
        "dex_count": len(dexes),
        "ranked_dex": dexes,
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if dexes:
        print(f"top: {dexes[0]['path']} score={dexes[0]['score']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
