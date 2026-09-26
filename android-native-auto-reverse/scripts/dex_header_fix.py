#!/usr/bin/env python3
"""Apply minimal DEX header repair: size, signature, and Adler32 checksum."""

from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path


def fix_dex(data: bytearray) -> bytearray:
    if len(data) < 112:
        raise SystemExit("file is too small for a dex header")
    if not data.startswith(b"dex\n"):
        data[:8] = b"dex\n035\x00"
    if data[7] != 0:
        data[7] = 0
    struct.pack_into("<I", data, 32, len(data))
    struct.pack_into("<I", data, 36, 112)
    struct.pack_into("<I", data, 40, 0x12345678)
    signature = hashlib.sha1(data[32:]).digest()
    data[12:32] = signature
    checksum = zlib.adler32(data[12:]) & 0xFFFFFFFF
    struct.pack_into("<I", data, 8, checksum)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dex", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True)
    args = parser.parse_args()

    data = bytearray(args.dex.read_bytes())
    fixed = fix_dex(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(fixed)
    print(f"wrote {args.out} size={len(fixed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
