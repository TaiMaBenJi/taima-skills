#!/usr/bin/env python3
"""Compare staged transform traces without printing secret-bearing payload bytes."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _bounded_input import (  # noqa: E402
    BoundedInputError,
    ensure_distinct_output,
    parse_json_text,
    read_utf8_text,
)


SUPPORTED_ENCODINGS = {"base64", "hex", "utf8"}


class TraceError(ValueError):
    pass


@dataclass(frozen=True)
class Payload:
    length: int
    sha256: str
    data: bytes | None


@dataclass(frozen=True)
class Stage:
    name: str
    occurrence: int
    input: Payload | None
    output: Payload | None


@dataclass(frozen=True)
class Difference:
    stage_index: int
    left_stage: str | None
    right_stage: str | None
    field: str
    detail: str
    byte_offset: int | None = None
    left_length: int | None = None
    right_length: int | None = None
    left_sha256: str | None = None
    right_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_index": self.stage_index,
            "left_stage": self.left_stage,
            "right_stage": self.right_stage,
            "field": self.field,
            "detail": self.detail,
            "byte_offset": self.byte_offset,
            "left_length": self.left_length,
            "right_length": self.right_length,
            "left_sha256": self.left_sha256,
            "right_sha256": self.right_sha256,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TraceError(f"{label}: sha256 must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise TraceError(f"{label}: sha256 must contain 64 hexadecimal characters")
    return normalized


def validate_length(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TraceError(f"{label}: length must be a non-negative integer")
    return value


def decode_data(encoding: Any, value: Any, label: str) -> bytes:
    if not isinstance(encoding, str) or encoding not in SUPPORTED_ENCODINGS:
        choices = ", ".join(sorted(SUPPORTED_ENCODINGS))
        raise TraceError(f"{label}: encoding must be one of {choices}")
    if not isinstance(value, str):
        raise TraceError(f"{label}: data must be a string")
    try:
        if encoding == "base64":
            return base64.b64decode(value, validate=True)
        if encoding == "hex":
            return bytes.fromhex(value)
        return value.encode("utf-8")
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise TraceError(f"{label}: invalid {encoding} data: {exc}") from exc


def parse_payload(value: Any, label: str) -> Payload:
    if not isinstance(value, dict):
        raise TraceError(f"{label}: payload descriptor must be an object")

    if "data" in value:
        data = decode_data(value.get("encoding"), value["data"], label)
        length = len(data)
        digest = sha256_bytes(data)
        if "length" in value and validate_length(value["length"], label) != length:
            raise TraceError(f"{label}: declared length does not match decoded data")
        if "sha256" in value and validate_sha256(value["sha256"], label) != digest:
            raise TraceError(f"{label}: declared sha256 does not match decoded data")
        return Payload(length=length, sha256=digest, data=data)

    if "length" not in value or "sha256" not in value:
        raise TraceError(f"{label}: redacted payload requires length and sha256")
    return Payload(
        length=validate_length(value["length"], label),
        sha256=validate_sha256(value["sha256"], label),
        data=None,
    )


def parse_trace(document: Any, label: str) -> list[Stage]:
    if not isinstance(document, dict):
        raise TraceError(f"{label}: trace root must be a JSON object")
    version = document.get("trace_version", 1)
    if version != 1:
        raise TraceError(f"{label}: unsupported trace_version {version!r}")
    stages = document.get("stages")
    if not isinstance(stages, list) or not stages:
        raise TraceError(f"{label}: stages must be a non-empty list")

    parsed: list[Stage] = []
    occurrences: dict[str, int] = {}
    for index, item in enumerate(stages):
        stage_label = f"{label}.stages[{index}]"
        if not isinstance(item, dict):
            raise TraceError(f"{stage_label}: stage must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise TraceError(f"{stage_label}: name must be a non-empty string")
        name = name.strip()
        derived_occurrence = occurrences.get(name, 0)
        occurrence = item.get("occurrence", derived_occurrence)
        if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 0:
            raise TraceError(f"{stage_label}: occurrence must be a non-negative integer")
        occurrences[name] = derived_occurrence + 1

        input_payload = (
            parse_payload(item["input"], f"{stage_label}.input")
            if "input" in item
            else None
        )
        output_payload = (
            parse_payload(item["output"], f"{stage_label}.output")
            if "output" in item
            else None
        )
        if input_payload is None and output_payload is None:
            raise TraceError(f"{stage_label}: stage must contain input or output")
        parsed.append(
            Stage(
                name=name,
                occurrence=occurrence,
                input=input_payload,
                output=output_payload,
            )
        )
    return parsed


def load_trace(path: Path) -> list[Stage]:
    try:
        document = parse_json_text(read_utf8_text(path), label=str(path))
    except BoundedInputError as exc:
        raise TraceError(str(exc)) from exc
    return parse_trace(document, str(path))


def first_byte_difference(left: bytes, right: bytes) -> int | None:
    for index, (left_byte, right_byte) in enumerate(zip(left, right)):
        if left_byte != right_byte:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def compare_payloads(
    left: Payload | None,
    right: Payload | None,
    *,
    stage_index: int,
    left_stage: str,
    right_stage: str,
    field: str,
) -> Difference | None:
    if left is None or right is None:
        if left is right:
            return None
        return Difference(
            stage_index=stage_index,
            left_stage=left_stage,
            right_stage=right_stage,
            field=field,
            detail="payload descriptor is missing on one side",
            left_length=None if left is None else left.length,
            right_length=None if right is None else right.length,
            left_sha256=None if left is None else left.sha256,
            right_sha256=None if right is None else right.sha256,
        )
    if left.length == right.length and left.sha256 == right.sha256:
        return None
    byte_offset = None
    if left.data is not None and right.data is not None:
        byte_offset = first_byte_difference(left.data, right.data)
    return Difference(
        stage_index=stage_index,
        left_stage=left_stage,
        right_stage=right_stage,
        field=field,
        detail="payload bytes differ",
        byte_offset=byte_offset,
        left_length=left.length,
        right_length=right.length,
        left_sha256=left.sha256,
        right_sha256=right.sha256,
    )


def compare_traces(left: list[Stage], right: list[Stage]) -> list[Difference]:
    differences: list[Difference] = []
    shared = min(len(left), len(right))
    for index in range(shared):
        left_stage = left[index]
        right_stage = right[index]
        if left_stage.name != right_stage.name:
            differences.append(
                Difference(
                    stage_index=index,
                    left_stage=left_stage.name,
                    right_stage=right_stage.name,
                    field="name",
                    detail="stage names differ",
                )
            )
        if left_stage.occurrence != right_stage.occurrence:
            differences.append(
                Difference(
                    stage_index=index,
                    left_stage=left_stage.name,
                    right_stage=right_stage.name,
                    field="occurrence",
                    detail=(
                        f"stage occurrences differ: {left_stage.occurrence} != "
                        f"{right_stage.occurrence}"
                    ),
                )
            )
        for field in ("input", "output"):
            difference = compare_payloads(
                getattr(left_stage, field),
                getattr(right_stage, field),
                stage_index=index,
                left_stage=left_stage.name,
                right_stage=right_stage.name,
                field=field,
            )
            if difference is not None:
                differences.append(difference)

    for index in range(shared, len(left)):
        differences.append(
            Difference(
                stage_index=index,
                left_stage=left[index].name,
                right_stage=None,
                field="stage",
                detail="stage exists only on the left",
            )
        )
    for index in range(shared, len(right)):
        differences.append(
            Difference(
                stage_index=index,
                left_stage=None,
                right_stage=right[index].name,
                field="stage",
                detail="stage exists only on the right",
            )
        )
    return differences


def short_hash(value: str | None) -> str:
    return "<missing>" if value is None else value[:16]


def render_difference(difference: Difference) -> None:
    print(
        f"- stage[{difference.stage_index}] "
        f"{difference.left_stage or '<missing>'} / "
        f"{difference.right_stage or '<missing>'}: {difference.field}"
    )
    print(f"  detail: {difference.detail}")
    if difference.byte_offset is not None:
        print(f"  first_byte_offset: {difference.byte_offset}")
    if difference.left_length is not None or difference.right_length is not None:
        print(f"  lengths: {difference.left_length} / {difference.right_length}")
    if difference.left_sha256 is not None or difference.right_sha256 is not None:
        print(
            f"  sha256: {short_hash(difference.left_sha256)} / "
            f"{short_hash(difference.right_sha256)}"
        )


def payload_descriptor(data: bytes) -> dict[str, Any]:
    return {
        "encoding": "base64",
        "data": base64.b64encode(data).decode("ascii"),
    }


def run_self_test() -> None:
    base = {
        "trace_version": 1,
        "stages": [
            {
                "name": "normalize",
                "input": payload_descriptor(b"abc"),
                "output": payload_descriptor(b"def"),
            },
            {
                "name": "pack",
                "input": payload_descriptor(b"def"),
                "output": payload_descriptor(b"ghi"),
            },
        ],
    }
    left = parse_trace(base, "left")
    if compare_traces(left, parse_trace(copy.deepcopy(base), "same")):
        raise AssertionError("identical trace comparison failed")

    redacted = copy.deepcopy(base)
    redacted["stages"][0]["output"] = {
        "length": 3,
        "sha256": sha256_bytes(b"def"),
    }
    if compare_traces(left, parse_trace(redacted, "redacted")):
        raise AssertionError("redacted descriptor comparison failed")

    changed = copy.deepcopy(base)
    changed["stages"][0]["output"] = payload_descriptor(b"dXf")
    differences = compare_traces(left, parse_trace(changed, "changed"))
    if len(differences) != 1:
        raise AssertionError(f"expected one changed payload; got {len(differences)}")
    if differences[0].stage_index != 0:
        raise AssertionError("changed payload stage index was not preserved")
    if differences[0].field != "output":
        raise AssertionError("changed payload field was not preserved")
    if differences[0].byte_offset != 1:
        raise AssertionError("first changed byte offset was not detected")

    malformed = copy.deepcopy(base)
    malformed["stages"][0]["input"]["length"] = 2
    try:
        parse_trace(malformed, "malformed")
    except TraceError:
        pass
    else:
        raise AssertionError("mismatched declared payload length must be rejected")
    print("self_test=PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare ordered transform-stage traces without printing payload bytes."
    )
    parser.add_argument("left", nargs="?", help="Reference transform trace JSON")
    parser.add_argument("right", nargs="?", help="Candidate transform trace JSON")
    parser.add_argument("--max-diffs", type=int, default=20, help="Maximum differences to print")
    parser.add_argument("--json-output", type=Path, help="Optional machine-readable report path")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic built-in tests")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        try:
            run_self_test()
        except AssertionError as exc:
            print(f"self_test=FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    if not args.left or not args.right:
        parser.error("left and right trace paths are required unless --self-test is used")
    if args.max_diffs < 1:
        parser.error("--max-diffs must be greater than zero")

    left_path = Path(args.left)
    right_path = Path(args.right)
    try:
        if args.json_output:
            ensure_distinct_output(args.json_output, (left_path, right_path))
        left = load_trace(left_path)
        right = load_trace(right_path)
    except (BoundedInputError, TraceError) as exc:
        print(f"trace_error={exc}", file=sys.stderr)
        return 2

    differences = compare_traces(left, right)
    report = {
        "left": str(left_path),
        "right": str(right_path),
        "left_stage_count": len(left),
        "right_stage_count": len(right),
        "equivalent": not differences,
        "difference_count": len(differences),
        "first_difference": None if not differences else differences[0].as_dict(),
        "differences": [difference.as_dict() for difference in differences],
    }
    print(f"equivalent={str(report['equivalent']).lower()}")
    print(f"left_stages={len(left)}")
    print(f"right_stages={len(right)}")
    print(f"difference_count={len(differences)}")
    for difference in differences[: args.max_diffs]:
        render_difference(difference)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main())
