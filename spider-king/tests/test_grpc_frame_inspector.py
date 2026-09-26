from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import grpc_frame_inspector as inspector  # noqa: E402
from grpc_frame_inspector import (  # noqa: E402
    GrpcFrameError,
    decode_segmented_base64,
    parse_grpc_frames,
)


SCRIPT = ROOT / "scripts" / "grpc_frame_inspector.py"


def frame(payload: bytes, flags: int = 0) -> bytes:
    return bytes([flags]) + len(payload).to_bytes(4, "big") + payload


def test_parses_multiple_data_and_trailer_frames() -> None:
    frames = parse_grpc_frames(
        frame(b"alpha") + frame(b"beta") + frame(b"grpc-status: 0\r\n", 0x80),
        grpc_web=True,
    )
    assert [item["kind"] for item in frames] == ["data", "data", "trailer"]
    assert [item["length"] for item in frames] == [5, 4, 16]
    assert all("payloadSha256" not in item for item in frames)

    hashed = parse_grpc_frames(frame(b"alpha"), include_payload_sha256=True)
    assert hashed[0]["payloadSha256"] == hashlib.sha256(b"alpha").hexdigest()


@pytest.mark.parametrize(
    "body, grpc_web, message",
    [
        (b"\x00\x00\x00\x00", False, "truncated frame header"),
        (b"\x00\x00\x00\x00\x04abc", False, "truncated frame payload"),
        (b"\x02\x00\x00\x00\x00", False, "unsupported frame flag"),
        (b"\x80\x00\x00\x00\x00", False, "unsupported frame flag"),
        (b"\x81\x00\x00\x00\x00", True, "trailer cannot be compressed"),
        (frame(b"grpc-status: 0\r\n", 0x80) + frame(b"late"), True, "trailer is not the final frame"),
    ],
)
def test_rejects_invalid_boundaries(body: bytes, grpc_web: bool, message: str) -> None:
    with pytest.raises(GrpcFrameError, match=message):
        parse_grpc_frames(body, grpc_web=grpc_web)


def test_rejects_declared_length_over_limit_before_payload_read() -> None:
    with pytest.raises(GrpcFrameError, match="exceeds limit"):
        parse_grpc_frames(b"\x00\x00\x00\x10\x00", max_frame_bytes=1024)


def test_rejects_total_bytes_and_frame_floods() -> None:
    with pytest.raises(GrpcFrameError, match="decoded input length"):
        parse_grpc_frames(frame(b"abc"), max_total_bytes=7)
    with pytest.raises(GrpcFrameError, match="frame count exceeds limit"):
        parse_grpc_frames(frame(b"") * 3, max_frames=2)


def test_decodes_independently_padded_grpc_web_text_segments() -> None:
    data = frame(b"ab")
    trailer = frame(b"grpc-status: 0\r\n", 0x80)
    encoded = base64.b64encode(data) + base64.b64encode(trailer)
    assert decode_segmented_base64(encoded) == data + trailer


def test_decodes_whitespace_dense_input_in_fixed_quartets(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = frame(b"ab") + frame(b"grpc-status: 0\r\n", 0x80)
    encoded = base64.b64encode(payload)
    whitespace = b" \t\r\n\v\f" * 1024
    dense = whitespace.join(bytes([value]) for value in encoded)
    observed_sizes: list[int] = []
    original_decode = inspector.base64.b64decode

    def observed_decode(data: bytes | bytearray, *, validate: bool = False) -> bytes:
        observed_sizes.append(len(data))
        return original_decode(data, validate=validate)

    monkeypatch.setattr(inspector.base64, "b64decode", observed_decode)
    assert decode_segmented_base64(dense) == payload
    assert observed_sizes
    assert set(observed_sizes) == {4}


def test_segmented_base64_enforces_decoded_size_limit() -> None:
    encoded = base64.b64encode(b"abcd")
    assert decode_segmented_base64(encoded, max_decoded_bytes=4) == b"abcd"
    with pytest.raises(GrpcFrameError, match="decoded input length exceeds limit 3"):
        decode_segmented_base64(encoded, max_decoded_bytes=3)


def test_base64_cli_implies_grpc_web_and_keeps_hashes_off(tmp_path: Path) -> None:
    input_path = tmp_path / "capture.txt"
    input_path.write_bytes(
        base64.b64encode(frame(b"ab"))
        + base64.b64encode(frame(b"grpc-status: 0\r\n", 0x80))
    )
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(input_path), "--base64"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert [item["kind"] for item in payload["frames"]] == ["data", "trailer"]
    assert all("payloadSha256" not in item for item in payload["frames"])


def test_cli_read_error_is_bounded_json_without_absolute_path(tmp_path: Path) -> None:
    missing = tmp_path / "private" / "missing.bin"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload == {"ok": False, "error": "input read failed", "inputFile": "missing.bin"}
    assert str(tmp_path) not in completed.stdout
    assert completed.stderr == ""


def test_cli_reads_at_most_the_configured_input_limit(tmp_path: Path) -> None:
    input_path = tmp_path / "capture.bin"
    input_path.write_bytes(b"1234")
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            str(input_path),
            "--max-input-bytes",
            "3",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload == {
        "ok": False,
        "error": "input length exceeds limit 3",
        "inputFile": "capture.bin",
    }


def test_self_test_survives_python_optimization() -> None:
    completed = subprocess.run(
        [sys.executable, "-O", str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "grpc_frame_inspector_self_test=PASS" in completed.stdout
