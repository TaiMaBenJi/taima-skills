"""Small bounded-input helpers shared by the skill's standalone JSON tools."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MAX_INPUT_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_JSON_DEPTH = 128
DEFAULT_MAX_JSON_NODES = 200_000


class BoundedInputError(ValueError):
    pass


def _reject_linked_output_components(path: Path) -> None:
    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if current.parent == current:
                return
            current = current.parent
            continue
        except OSError as exc:
            raise BoundedInputError("cannot inspect output path") from exc
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or bool(
            getattr(metadata, "st_file_attributes", 0) & reparse_flag
        ):
            raise BoundedInputError("output path must not use a symlink or reparse point")
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
            raise BoundedInputError("output path must not use a hard-linked file")
        if current.parent == current:
            return
        current = current.parent


def read_utf8_text(path: Path, *, max_bytes: int = DEFAULT_MAX_INPUT_BYTES) -> str:
    try:
        with path.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except OSError as exc:
        raise BoundedInputError(f"cannot read {path}") from exc
    if len(payload) > max_bytes:
        raise BoundedInputError(f"{path}: input exceeds {max_bytes} bytes")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BoundedInputError(f"{path}: input is not valid UTF-8") from exc


def parse_json_text(text: str, *, label: str) -> Any:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BoundedInputError(
            f"{label}: invalid JSON at line {exc.lineno} column {exc.colno}"
        ) from exc
    except RecursionError as exc:
        raise BoundedInputError(f"{label}: JSON nesting exceeds the supported limit") from exc
    validate_json_shape(document, label=label)
    return document


def validate_json_shape(
    document: Any,
    *,
    label: str,
    max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    max_nodes: int = DEFAULT_MAX_JSON_NODES,
) -> None:
    stack: list[tuple[Any, int]] = [(document, 1)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise BoundedInputError(f"{label}: JSON contains more than {max_nodes} values")
        if depth > max_depth:
            raise BoundedInputError(f"{label}: JSON nesting exceeds {max_depth} levels")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)


def ensure_distinct_output(output: Path, inputs: Iterable[Path]) -> None:
    _reject_linked_output_components(output)
    output_resolved = output.resolve(strict=False)
    for input_path in inputs:
        input_resolved = input_path.resolve(strict=False)
        if output_resolved == input_resolved:
            raise BoundedInputError("output path must differ from every input path")
        try:
            if output.exists() and input_path.exists() and os.path.samefile(output, input_path):
                raise BoundedInputError("output path must differ from every input path")
        except OSError:
            # Resolution equality above still protects non-existent and inaccessible targets.
            continue
