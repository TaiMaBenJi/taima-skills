#!/usr/bin/env python3
"""Reconstruct a Bangcle/libDexHelper inner ELF from an outer shell SO.

This helper is intentionally parameterized. Offsets, lengths, and keys must
come from the current sample's IDA/Ghidra analysis or runtime evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def parse_int(text: str) -> int:
    return int(text, 0)


def rc4_like(data: bytes, key: bytes) -> bytes:
    if not key:
        raise SystemExit("RC4-like key must not be empty")
    sbox = list(range(256))
    j = 0
    for i in range(256):
        j = (j + sbox[i] + key[i % len(key)]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]

    out = bytearray(len(data))
    i = 0
    j = 0
    for idx, value in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + sbox[i]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]
        out[idx] = value ^ sbox[(sbox[i] + sbox[j]) & 0xFF]
    return bytes(out)


def read_key(data: bytes, key_hex: str | None, key_offset: int | None, key_len: int | None) -> bytes:
    if key_hex:
        return bytes.fromhex(key_hex.replace(":", "").replace(" ", ""))
    if key_offset is None or key_len is None:
        raise SystemExit("provide either --header-key-hex or both --key-material-offset/--header-key-len")
    return data[key_offset : key_offset + key_len]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outer_so", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument("--payload-offset", type=parse_int, required=True)
    parser.add_argument("--payload-size", type=parse_int, help="optional encrypted payload size; default reads to EOF")
    parser.add_argument("--header-decrypt-len", type=parse_int, default=0x40)
    parser.add_argument("--header-key-hex", help="hex bytes for the RC4-like header key")
    parser.add_argument("--key-material-offset", type=parse_int)
    parser.add_argument("--header-key-len", type=parse_int)
    parser.add_argument("--xor-key", type=parse_int, required=True, help="single-byte body XOR key")
    parser.add_argument("--json", type=Path, help="write reconstruction metadata")
    args = parser.parse_args()

    source = args.outer_so.read_bytes()
    if args.payload_offset >= len(source):
        raise SystemExit("--payload-offset is past EOF")
    payload_end = len(source) if args.payload_size is None else args.payload_offset + args.payload_size
    encrypted = source[args.payload_offset : payload_end]
    if len(encrypted) < args.header_decrypt_len:
        raise SystemExit("payload is shorter than --header-decrypt-len")

    header_key = read_key(source, args.header_key_hex, args.key_material_offset, args.header_key_len)
    header = rc4_like(encrypted[: args.header_decrypt_len], header_key)
    body = bytes(value ^ (args.xor_key & 0xFF) for value in encrypted[args.header_decrypt_len :])
    inner = header + body

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(inner)

    meta = {
        "schema": "android-native-auto-reverse.bangcle_dexhelper_inner_decrypt.v1",
        "outer_so": str(args.outer_so),
        "outer_sha256": hashlib.sha256(source).hexdigest(),
        "out": str(args.out),
        "inner_sha256": hashlib.sha256(inner).hexdigest(),
        "payload_offset": hex(args.payload_offset),
        "payload_size": len(encrypted),
        "header_decrypt_len": args.header_decrypt_len,
        "header_key_len": len(header_key),
        "key_material_offset": hex(args.key_material_offset) if args.key_material_offset is not None else None,
        "xor_key": hex(args.xor_key & 0xFF),
        "magic": inner[:4].hex(),
        "looks_like_elf": inner.startswith(b"\x7fELF"),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    status = "ELF" if meta["looks_like_elf"] else "not-ELF"
    print(f"wrote {args.out} size={len(inner)} magic={inner[:4].hex()} status={status}")
    if not meta["looks_like_elf"]:
        print("warning: output does not start with ELF magic; verify offsets/key/algorithm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
