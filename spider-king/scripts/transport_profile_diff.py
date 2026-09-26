#!/usr/bin/env python3
"""Compare normalized TLS, ALPN, and HTTP/2 transport profiles."""

from __future__ import annotations

import argparse
import copy
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


PROTOCOL_LIST_PATHS = (
    ("tls", "cipher_suites"),
    ("tls", "extensions"),
    ("tls", "supported_groups"),
    ("tls", "key_shares"),
    ("tls", "signature_algorithms"),
    ("tls", "signature_algorithms_cert"),
    ("tls", "supported_versions"),
    ("tls", "compression_methods"),
    ("tls", "ec_point_formats"),
)

GREASE_PATHS = (
    ("tls", "cipher_suites"),
    ("tls", "extensions"),
    ("tls", "supported_groups"),
    ("tls", "key_shares"),
    ("tls", "supported_versions"),
)

PROTOCOL_SCALAR_PATHS = (
    ("tls", "legacy_version"),
    ("http2", "connection_window_update"),
)


@dataclass(frozen=True)
class Difference:
    path: str
    left: Any
    right: Any

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "left": self.left, "right": self.right}


class ProfileError(ValueError):
    pass


def parse_protocol_id(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.lower().startswith("0x"):
                return int(text, 16)
            if text and (text.isdigit() or (text[0] == "-" and text[1:].isdigit())):
                return int(text, 10)
        except ValueError:
            pass
    return value


def is_grease(value: Any) -> bool:
    parsed = parse_protocol_id(value)
    return (
        isinstance(parsed, int)
        and not isinstance(parsed, bool)
        and 0 <= parsed <= 0xFFFF
        and (parsed & 0x0F0F) == 0x0A0A
        and (parsed >> 8) == (parsed & 0xFF)
    )


def get_path(document: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = document
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_path(document: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current: dict[str, Any] = document
    for part in path[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            return
        current = next_value
    if path[-1] in current:
        current[path[-1]] = value


def normalize_settings(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    for item in value:
        if isinstance(item, dict) and "id" in item and "value" in item:
            normalized.append(
                {
                    **item,
                    "id": parse_protocol_id(item["id"]),
                    "value": parse_protocol_id(item["value"]),
                }
            )
        else:
            normalized.append(item)
    return normalized


def normalize_document(
    document: dict[str, Any],
    *,
    family_aware: bool,
    ignore_extension_order: bool,
) -> dict[str, Any]:
    normalized = copy.deepcopy(document)
    for path in PROTOCOL_LIST_PATHS:
        values = get_path(normalized, path)
        if not isinstance(values, list):
            continue
        parsed = [parse_protocol_id(value) for value in values]
        if family_aware and path in GREASE_PATHS:
            parsed = ["GREASE" if is_grease(value) else value for value in parsed]
        if path == ("tls", "extensions") and ignore_extension_order:
            parsed = sorted(parsed, key=lambda value: (str(type(value)), str(value)))
        set_path(normalized, path, parsed)

    for path in PROTOCOL_SCALAR_PATHS:
        value = get_path(normalized, path)
        if value is not None:
            set_path(normalized, path, parse_protocol_id(value))

    settings = get_path(normalized, ("http2", "settings"))
    if settings is not None:
        set_path(normalized, ("http2", "settings"), normalize_settings(settings))
    return normalized


def validate_profile(document: Any, label: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ProfileError(f"{label}: profile root must be a JSON object")
    tls = document.get("tls")
    if not isinstance(tls, dict):
        raise ProfileError(f"{label}: profile must contain a tls object")
    tls_list_fields = tuple(path[-1] for path in PROTOCOL_LIST_PATHS) + ("alpn",)
    for key in tls_list_fields:
        if key in tls and not isinstance(tls[key], list):
            raise ProfileError(f"{label}: tls.{key} must be a list")
    http2 = document.get("http2")
    if http2 is not None and not isinstance(http2, dict):
        raise ProfileError(f"{label}: http2 must be an object when present")
    if isinstance(http2, dict) and "settings" in http2 and not isinstance(http2["settings"], list):
        raise ProfileError(f"{label}: http2.settings must be a list")
    return document


def load_profile(path: Path) -> dict[str, Any]:
    try:
        payload = parse_json_text(read_utf8_text(path), label=str(path))
    except BoundedInputError as exc:
        raise ProfileError(str(exc)) from exc
    return validate_profile(payload, str(path))


def diff_values(left: Any, right: Any, path: str = "$") -> list[Difference]:
    if type(left) is not type(right):
        return [Difference(path, left, right)]
    if isinstance(left, dict):
        differences: list[Difference] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left:
                differences.append(Difference(child, "<missing>", right[key]))
            elif key not in right:
                differences.append(Difference(child, left[key], "<missing>"))
            else:
                differences.extend(diff_values(left[key], right[key], child))
        return differences
    if isinstance(left, list):
        differences = []
        shared = min(len(left), len(right))
        for index in range(shared):
            differences.extend(diff_values(left[index], right[index], f"{path}[{index}]"))
        for index in range(shared, len(left)):
            differences.append(Difference(f"{path}[{index}]", left[index], "<missing>"))
        for index in range(shared, len(right)):
            differences.append(Difference(f"{path}[{index}]", "<missing>", right[index]))
        return differences
    return [] if left == right else [Difference(path, left, right)]


def compare_profiles(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    family_aware: bool,
    ignore_extension_order: bool,
) -> list[Difference]:
    normalized_left = normalize_document(
        left,
        family_aware=family_aware,
        ignore_extension_order=ignore_extension_order,
    )
    normalized_right = normalize_document(
        right,
        family_aware=family_aware,
        ignore_extension_order=ignore_extension_order,
    )
    return diff_values(normalized_left, normalized_right)


def render_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def run_self_test() -> None:
    base = {
        "identity": {"browser_family": "example", "browser_version": "1"},
        "tls": {
            "legacy_version": 0x0303,
            "cipher_suites": [0x0A0A, 4865, 4867],
            "extensions": [0, 0x1A1A, 10, 43],
            "supported_groups": [0x2A2A, 29, 23],
            "key_shares": [0x3A3A, 29],
            "signature_algorithms": [2052, 1027],
            "signature_algorithms_cert": [2052, 1027],
            "supported_versions": [0x4A4A, 772, 771],
            "compression_methods": [0],
            "ec_point_formats": [0],
            "alpn": ["h2", "http/1.1"],
        },
        "http2": {
            "settings": [{"id": 1, "value": 65536}, {"id": 4, "value": 131072}],
            "connection_window_update": 131072,
            "pseudo_header_order": [":method", ":path", ":authority", ":scheme"],
        },
    }
    grease_variant = copy.deepcopy(base)
    grease_variant["tls"]["legacy_version"] = "0x0303"
    grease_variant["tls"]["cipher_suites"] = ["0xfafa", "0x1301", "4867"]
    grease_variant["tls"]["extensions"][1] = "0x3a3a"
    grease_variant["tls"]["supported_groups"][0] = "0x4a4a"
    grease_variant["tls"]["key_shares"] = ["0x5a5a", "29"]
    grease_variant["tls"]["signature_algorithms"] = ["0x0804", "1027"]
    grease_variant["tls"]["signature_algorithms_cert"] = ["2052", "0x0403"]
    grease_variant["tls"]["supported_versions"] = ["0x6a6a", "0x0304", "771"]
    grease_variant["tls"]["compression_methods"] = ["0x00"]
    grease_variant["tls"]["ec_point_formats"] = ["0"]
    grease_variant["http2"]["settings"] = [
        {"id": "0x01", "value": "65536"},
        {"id": "4", "value": "0x20000"},
    ]
    grease_variant["http2"]["connection_window_update"] = "0x20000"
    if compare_profiles(base, grease_variant, family_aware=True, ignore_extension_order=False):
        raise AssertionError("family-aware GREASE normalization failed")
    if not compare_profiles(base, grease_variant, family_aware=False, ignore_extension_order=False):
        raise AssertionError("exact comparison unexpectedly normalized GREASE")
    if is_grease(0x1A2A):
        raise AssertionError("GREASE detection accepted unequal bytes")

    reordered = copy.deepcopy(base)
    reordered["tls"]["extensions"] = [43, 10, 0x1A1A, 0]
    if not compare_profiles(base, reordered, family_aware=True, ignore_extension_order=False):
        raise AssertionError("ordered extension comparison missed a reorder")
    if compare_profiles(base, reordered, family_aware=True, ignore_extension_order=True):
        raise AssertionError("ignore-extension-order comparison failed")

    h2_reordered = copy.deepcopy(base)
    h2_reordered["http2"]["settings"].reverse()
    if not compare_profiles(base, h2_reordered, family_aware=True, ignore_extension_order=False):
        raise AssertionError("HTTP/2 setting reorder was not detected")

    try:
        validate_profile({"tls": {"signature_algorithms": "0x0804"}}, "invalid")
    except ProfileError:
        pass
    else:
        raise AssertionError("invalid TLS list fields must be rejected")
    print("self_test=PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare structured browser and candidate TLS/H2 profiles."
    )
    parser.add_argument("left", nargs="?", help="Browser baseline profile JSON")
    parser.add_argument("right", nargs="?", help="Candidate transport profile JSON")
    parser.add_argument(
        "--family-aware",
        action="store_true",
        help="Normalize GREASE values while preserving their slots",
    )
    parser.add_argument(
        "--ignore-extension-order",
        action="store_true",
        help="Ignore extension order only when repeated captures prove it variable",
    )
    parser.add_argument("--max-diffs", type=int, default=40, help="Maximum differences to print")
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
        parser.error("left and right profile paths are required unless --self-test is used")
    if args.max_diffs < 1:
        parser.error("--max-diffs must be greater than zero")

    left_path = Path(args.left)
    right_path = Path(args.right)
    try:
        if args.json_output:
            ensure_distinct_output(args.json_output, (left_path, right_path))
        left = load_profile(left_path)
        right = load_profile(right_path)
    except (BoundedInputError, ProfileError) as exc:
        print(f"profile_error={exc}", file=sys.stderr)
        return 2

    differences = compare_profiles(
        left,
        right,
        family_aware=args.family_aware,
        ignore_extension_order=args.ignore_extension_order,
    )
    report = {
        "left": str(left_path),
        "right": str(right_path),
        "family_aware": args.family_aware,
        "ignore_extension_order": args.ignore_extension_order,
        "equivalent": not differences,
        "difference_count": len(differences),
        "differences": [difference.as_dict() for difference in differences],
    }
    print(f"equivalent={str(report['equivalent']).lower()}")
    print(f"difference_count={len(differences)}")
    for difference in differences[: args.max_diffs]:
        print(f"- {difference.path}")
        print(f"  left:  {render_value(difference.left)}")
        print(f"  right: {render_value(difference.right)}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main())
