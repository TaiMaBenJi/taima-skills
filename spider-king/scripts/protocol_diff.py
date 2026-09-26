#!/usr/bin/env python3
"""
Compare two captured protocol samples and surface meaningful deltas.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _bounded_input import BoundedInputError, read_utf8_text, validate_json_shape  # noqa: E402


def load_text(path: Path) -> str:
    return read_utf8_text(path)


def try_load_json(text: str) -> Any | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    except RecursionError as exc:
        raise BoundedInputError("JSON nesting exceeds the supported limit") from exc
    validate_json_shape(value, label="sample")
    return value


def key_path(prefix: str, key: str) -> str:
    if key.isidentifier():
        return f"{prefix}.{key}"
    return f"{prefix}[{json.dumps(key, ensure_ascii=False)}]"


def flatten_json(value: Any, prefix: str = "$") -> dict[str, str]:
    rows: dict[str, str] = {}
    if isinstance(value, dict):
        if not value:
            rows[prefix] = "{}"
        for key in sorted(value):
            rows.update(flatten_json(value[key], key_path(prefix, key)))
        return rows
    if isinstance(value, list):
        if not value:
            rows[prefix] = "[]"
        for index, item in enumerate(value):
            rows.update(flatten_json(item, f"{prefix}[{index}]"))
        return rows
    rows[prefix] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return rows


def compare_json(left: Any, right: Any, max_diffs: int) -> None:
    left_map = flatten_json(left)
    right_map = flatten_json(right)
    keys = sorted(set(left_map) | set(right_map))

    only_left = [key for key in keys if key not in right_map]
    only_right = [key for key in keys if key not in left_map]
    changed = [key for key in keys if key in left_map and key in right_map and left_map[key] != right_map[key]]

    print("mode=json")
    print(f"left_only={len(only_left)}")
    print(f"right_only={len(only_right)}")
    print(f"changed={len(changed)}")

    for key in only_left[:max_diffs]:
        print(f"- left_only {key} = {left_map[key]}")
    for key in only_right[:max_diffs]:
        print(f"- right_only {key} = {right_map[key]}")
    for key in changed[:max_diffs]:
        print(f"- changed {key}")
        print(f"  left:  {left_map[key]}")
        print(f"  right: {right_map[key]}")


def compare_text(left_text: str, right_text: str, max_diffs: int) -> None:
    print("mode=text")
    diff = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile="left",
            tofile="right",
            lineterm="",
        )
    )
    shown = diff[:max_diffs]
    print(f"diff_lines={len(diff)}")
    for line in shown:
        safe = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8",
            errors="replace",
        )
        print(safe)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two captured protocol samples.")
    parser.add_argument("left", help="Left sample path")
    parser.add_argument("right", help="Right sample path")
    parser.add_argument("--max-diffs", type=int, default=40, help="Maximum diff rows to print")
    args = parser.parse_args()

    if args.max_diffs < 1:
        parser.error("--max-diffs must be greater than zero")

    left_path = Path(args.left)
    right_path = Path(args.right)

    try:
        left_text = load_text(left_path)
        right_text = load_text(right_path)
        left_json = try_load_json(left_text)
        right_json = try_load_json(right_text)
    except BoundedInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"left={left_path}")
    print(f"right={right_path}")

    if left_json is not None and right_json is not None:
        compare_json(left_json, right_json, args.max_diffs)
        return 0

    compare_text(left_text, right_text, args.max_diffs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
