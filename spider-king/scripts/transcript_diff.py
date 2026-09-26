#!/usr/bin/env python3
"""Find the first meaningful divergence between two ordered protocol chains."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _bounded_input import BoundedInputError, parse_json_text, read_utf8_text  # noqa: E402


DEFAULT_IGNORED_FIELDS = frozenset({"generated_at"})
MISSING = object()


class TranscriptError(ValueError):
    pass


@dataclass(frozen=True)
class Difference:
    step_index: int
    path: str
    kind: str
    left: Any
    right: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "path": self.path,
            "kind": self.kind,
            "left": value_fingerprint(self.left),
            "right": value_fingerprint(self.right),
        }


def stable_bytes(value: Any) -> bytes:
    if value is MISSING:
        return b"<missing>"
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=repr,
    ).encode("utf-8")


def value_fingerprint(value: Any) -> dict[str, Any]:
    if value is MISSING:
        return {"type": "missing"}
    raw = stable_bytes(value)
    result: dict[str, Any] = {
        "type": type(value).__name__,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if isinstance(value, str):
        result["length"] = len(value)
    elif isinstance(value, (list, dict)):
        result["length"] = len(value)
    return result


def load_document(path: Path) -> Any:
    try:
        return parse_json_text(read_utf8_text(path), label=str(path))
    except BoundedInputError as exc:
        raise TranscriptError(str(exc)) from exc


def select_chain(
    document: Any, chain_id: Optional[str], label: str
) -> dict[str, Any]:
    if isinstance(document, dict) and isinstance(document.get("chains"), list):
        chains = document["chains"]
        if chain_id is not None:
            matches = [
                chain
                for chain in chains
                if isinstance(chain, dict)
                and chain.get("chain_id", chain.get("session_chain_id")) == chain_id
            ]
            if len(matches) != 1:
                raise TranscriptError(f"{label}: expected one chain_id={chain_id!r}, found {len(matches)}")
            chain = matches[0]
        elif len(chains) == 1:
            chain = chains[0]
        else:
            raise TranscriptError(f"{label}: package has {len(chains)} chains; select one with --{label}-chain")
    elif isinstance(document, dict) and "steps" in document:
        chain = document
    elif isinstance(document, list):
        chain = {"chain_id": label, "steps": document}
    else:
        raise TranscriptError(f"{label}: expected an evidence package, chain object, or step list")

    if not isinstance(chain, dict) or not isinstance(chain.get("steps"), list):
        raise TranscriptError(f"{label}: selected chain must contain a steps list")
    for index, step in enumerate(chain["steps"]):
        if not isinstance(step, dict):
            raise TranscriptError(f"{label}: steps[{index}] must be an object")
    return chain


def key_path(path: str, key: str) -> str:
    if key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def first_value_difference(
    left: Any,
    right: Any,
    *,
    path: str,
    ignored_fields: frozenset[str],
) -> Optional[Tuple[str, str, Any, Any]]:
    if type(left) is not type(right):
        return path, "type", left, right

    if isinstance(left, dict):
        keys = list(left)
        keys.extend(key for key in right if key not in left)
        for key in keys:
            if key in ignored_fields:
                continue
            left_value = left.get(key, MISSING)
            right_value = right.get(key, MISSING)
            if left_value is MISSING or right_value is MISSING:
                return key_path(path, key), "missing", left_value, right_value
            difference = first_value_difference(
                left_value,
                right_value,
                path=key_path(path, key),
                ignored_fields=ignored_fields,
            )
            if difference is not None:
                return difference
        return None

    if isinstance(left, list):
        common = min(len(left), len(right))
        for index in range(common):
            difference = first_value_difference(
                left[index],
                right[index],
                path=f"{path}[{index}]",
                ignored_fields=ignored_fields,
            )
            if difference is not None:
                return difference
        if len(left) != len(right):
            index = common
            left_value = left[index] if index < len(left) else MISSING
            right_value = right[index] if index < len(right) else MISSING
            return f"{path}[{index}]", "length", left_value, right_value
        return None

    if left != right:
        return path, "value", left, right
    return None


def compare_chains(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    ignored_fields: frozenset[str] = DEFAULT_IGNORED_FIELDS,
) -> dict[str, Any]:
    left_steps = left["steps"]
    right_steps = right["steps"]
    common = min(len(left_steps), len(right_steps))
    first: Optional[Difference] = None

    for index in range(common):
        raw = first_value_difference(
            left_steps[index],
            right_steps[index],
            path=f"$.steps[{index}]",
            ignored_fields=ignored_fields,
        )
        if raw is not None:
            path, kind, left_value, right_value = raw
            first = Difference(index, path, kind, left_value, right_value)
            break

    if first is None and len(left_steps) != len(right_steps):
        index = common
        first = Difference(
            index,
            f"$.steps[{index}]",
            "step-count",
            left_steps[index] if index < len(left_steps) else MISSING,
            right_steps[index] if index < len(right_steps) else MISSING,
        )

    return {
        "mode": "transcript",
        "equal": first is None,
        "left_chain": left.get("chain_id", left.get("session_chain_id")),
        "right_chain": right.get("chain_id", right.get("session_chain_id")),
        "left_steps": len(left_steps),
        "right_steps": len(right_steps),
        "ignored_fields": sorted(ignored_fields),
        "first_divergence": None if first is None else first.as_dict(),
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        "mode=transcript",
        f"equal={str(result['equal']).lower()}",
        f"left_chain={result['left_chain']}",
        f"right_chain={result['right_chain']}",
        f"left_steps={result['left_steps']}",
        f"right_steps={result['right_steps']}",
    ]
    divergence = result["first_divergence"]
    if divergence is not None:
        lines.extend(
            [
                f"first_divergence_step={divergence['step_index']}",
                f"first_divergence_path={divergence['path']}",
                f"first_divergence_kind={divergence['kind']}",
                "left_fingerprint=" + json.dumps(divergence["left"], sort_keys=True),
                "right_fingerprint=" + json.dumps(divergence["right"], sort_keys=True),
            ]
        )
    return "\n".join(lines)


def run_self_test() -> None:
    final = {"request": {"method": "POST", "body": {"sha256": "same"}}}
    left = {
        "chain_id": "left",
        "steps": [
            {"response": {"headers": [["Set-Cookie", "<redacted:a>"]]}},
            final,
        ],
    }
    right = {
        "chain_id": "right",
        "steps": [
            {"response": {"headers": [["Set-Cookie", "<redacted:b>"]]}},
            final,
        ],
    }
    result = compare_chains(left, right)
    divergence = result["first_divergence"]
    if result["equal"] or divergence is None:
        raise AssertionError("self-test did not find a divergence")
    if divergence["step_index"] != 0 or "response.headers[0][1]" not in divergence["path"]:
        raise AssertionError(f"unexpected first divergence: {divergence}")
    if not compare_chains(left, left)["equal"]:
        raise AssertionError("self-test identical chain comparison failed")
    print("transcript_diff_self_test=PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", nargs="?", help="Left evidence package or chain JSON")
    parser.add_argument("right", nargs="?", help="Right evidence package or chain JSON")
    parser.add_argument("--left-chain", help="Chain id to select from the left package")
    parser.add_argument("--right-chain", help="Chain id to select from the right package")
    parser.add_argument(
        "--ignore-field",
        action="append",
        default=[],
        help="Ignore this object field name at every level; may be repeated",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic internal checks")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        try:
            run_self_test()
        except AssertionError as exc:
            print(f"transcript_diff_self_test=FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    if not args.left or not args.right:
        print("error: left and right paths are required unless --self-test is used", file=sys.stderr)
        return 2

    try:
        left_document = load_document(Path(args.left))
        right_document = load_document(Path(args.right))
        left_chain = select_chain(left_document, args.left_chain, "left")
        right_chain = select_chain(right_document, args.right_chain, "right")
        ignored = frozenset(DEFAULT_IGNORED_FIELDS | set(args.ignore_field))
        result = compare_chains(left_chain, right_chain, ignored_fields=ignored)
    except TranscriptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
