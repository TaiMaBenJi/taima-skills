#!/usr/bin/env python3
"""Inspect bounded gRPC or grpc-web frame structure without decoding payloads."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import sys
from pathlib import Path


DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_INPUT_BYTES = 48 * 1024 * 1024
DEFAULT_MAX_FRAMES = 4096


class GrpcFrameError(ValueError):
    """Raised when input violates the bounded frame contract."""


def parse_grpc_frames(
    data: bytes,
    *,
    grpc_web: bool = False,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_frames: int = DEFAULT_MAX_FRAMES,
    include_payload_sha256: bool = False,
) -> list[dict[str, object]]:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    for name, value in (
        ("max_frame_bytes", max_frame_bytes),
        ("max_total_bytes", max_total_bytes),
        ("max_frames", max_frames),
    ):
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if len(data) > max_total_bytes:
        raise GrpcFrameError(
            f"decoded input length {len(data)} exceeds limit {max_total_bytes}"
        )

    frames: list[dict[str, object]] = []
    offset = 0
    trailer_seen = False
    while offset < len(data):
        if trailer_seen:
            raise GrpcFrameError(f"data appears after final grpc-web trailer at offset {offset}")
        if len(frames) >= max_frames:
            raise GrpcFrameError(f"frame count exceeds limit {max_frames} at offset {offset}")

        remaining = len(data) - offset
        if remaining < 5:
            raise GrpcFrameError(
                f"truncated frame header at offset {offset}: {remaining} byte(s) remain"
            )

        flags = data[offset]
        allowed_mask = 0x81 if grpc_web else 0x01
        if flags & ~allowed_mask:
            raise GrpcFrameError(f"unsupported frame flag 0x{flags:02x} at offset {offset}")

        trailer = bool(grpc_web and (flags & 0x80))
        compressed = bool(flags & 0x01)
        if trailer and compressed:
            raise GrpcFrameError(f"grpc-web trailer cannot be compressed at offset {offset}")

        length = int.from_bytes(data[offset + 1 : offset + 5], "big", signed=False)
        if length > max_frame_bytes:
            raise GrpcFrameError(
                f"frame length {length} exceeds limit {max_frame_bytes} at offset {offset}"
            )

        payload_start = offset + 5
        payload_end = payload_start + length
        if payload_end > len(data):
            available = len(data) - payload_start
            raise GrpcFrameError(
                f"truncated frame payload at offset {offset}: declared {length}, available {available}"
            )
        if trailer and payload_end != len(data):
            raise GrpcFrameError(f"grpc-web trailer is not the final frame at offset {offset}")

        frame: dict[str, object] = {
            "index": len(frames),
            "offset": offset,
            "flags": flags,
            "kind": "trailer" if trailer else "data",
            "compressed": compressed,
            "length": length,
        }
        if include_payload_sha256:
            digest = hashlib.sha256()
            digest.update(memoryview(data)[payload_start:payload_end])
            frame["payloadSha256"] = digest.hexdigest()
        frames.append(frame)
        trailer_seen = trailer
        offset = payload_end

    return frames


def decode_segmented_base64(
    raw: bytes,
    *,
    max_decoded_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> bytes:
    """Decode grpc-web-text where independently encoded chunks may contain padding."""
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    if not isinstance(max_decoded_bytes, int) or max_decoded_bytes <= 0:
        raise ValueError("max_decoded_bytes must be a positive integer")

    decoded = bytearray()
    quartet = bytearray()
    for value in raw:
        if value in b" \t\r\n\v\f":
            continue
        quartet.append(value)
        if len(quartet) == 4:
            _append_base64_quartet(decoded, quartet, max_decoded_bytes)
            quartet.clear()

    if quartet:
        raise GrpcFrameError("invalid grpc-web-text Base64 segment length")
    return bytes(decoded)


def _append_base64_quartet(output: bytearray, quartet: bytearray, limit: int) -> None:
    try:
        part = base64.b64decode(quartet, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GrpcFrameError("invalid grpc-web-text Base64 data") from exc
    if len(output) + len(part) > limit:
        raise GrpcFrameError(f"decoded input length exceeds limit {limit}")
    output.extend(part)


def _frame(payload: bytes, flags: int = 0) -> bytes:
    return bytes([flags]) + len(payload).to_bytes(4, "big") + payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def self_test() -> None:
    data = _frame(b"one")
    trailer = _frame(b"grpc-status: 0\r\n", 0x80)
    encoded = base64.b64encode(data) + base64.b64encode(trailer)
    decoded = decode_segmented_base64(encoded)
    frames = parse_grpc_frames(decoded, grpc_web=True)
    _require([frame["kind"] for frame in frames] == ["data", "trailer"], "frame kinds")
    _require([frame["length"] for frame in frames] == [3, 16], "frame lengths")

    invalid_cases = (
        (b"\x00\x00\x00\x00", {}),
        (b"\x00\x00\x00\x00\x04abc", {}),
        (b"\x02\x00\x00\x00\x00", {}),
        (b"\x81\x00\x00\x00\x00", {"grpc_web": True}),
        (trailer + data, {"grpc_web": True}),
    )
    failures = 0
    for invalid, options in invalid_cases:
        try:
            parse_grpc_frames(invalid, **options)
        except GrpcFrameError:
            failures += 1
    _require(failures == len(invalid_cases), "negative controls")
    print("grpc_frame_inspector_self_test=PASS frames=2 negative_controls=5")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Captured binary or grpc-web-text body")
    parser.add_argument("--grpc-web", action="store_true", help="Allow one final grpc-web trailer frame")
    parser.add_argument(
        "--base64",
        action="store_true",
        help="Decode segmented grpc-web-text Base64 and enable grpc-web framing",
    )
    parser.add_argument("--max-input-bytes", type=int, default=DEFAULT_MAX_INPUT_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-frame-bytes", type=int, default=DEFAULT_MAX_FRAME_BYTES)
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    parser.add_argument(
        "--include-payload-sha256",
        action="store_true",
        help="Include stable payload hashes in task-local output; unsafe for publication",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser


def _error(message: str, *, input_file: str | None = None) -> int:
    payload: dict[str, object] = {"ok": False, "error": message}
    if input_file:
        payload["inputFile"] = input_file
    print(json.dumps(payload, ensure_ascii=True))
    return 2


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.input:
        return _error("input is required unless --self-test is used")
    for name, value in (
        ("max-input-bytes", args.max_input_bytes),
        ("max-total-bytes", args.max_total_bytes),
        ("max-frame-bytes", args.max_frame_bytes),
        ("max-frames", args.max_frames),
    ):
        if value <= 0:
            return _error(f"{name} must be positive", input_file=Path(args.input).name)

    input_path = Path(args.input)
    try:
        with input_path.open("rb") as handle:
            raw = handle.read(args.max_input_bytes + 1)
        if len(raw) > args.max_input_bytes:
            return _error(
                f"input length exceeds limit {args.max_input_bytes}",
                input_file=input_path.name,
            )
    except OSError:
        return _error("input read failed", input_file=input_path.name)

    try:
        if args.base64:
            raw = decode_segmented_base64(raw, max_decoded_bytes=args.max_total_bytes)
        frames = parse_grpc_frames(
            raw,
            grpc_web=args.grpc_web or args.base64,
            max_frame_bytes=args.max_frame_bytes,
            max_total_bytes=args.max_total_bytes,
            max_frames=args.max_frames,
            include_payload_sha256=args.include_payload_sha256,
        )
    except (GrpcFrameError, ValueError, TypeError) as exc:
        return _error(str(exc), input_file=input_path.name)

    print(
        json.dumps(
            {
                "ok": True,
                "inputFile": input_path.name,
                "frameCount": len(frames),
                "frames": frames,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
