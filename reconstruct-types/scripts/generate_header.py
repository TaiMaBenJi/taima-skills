#!/usr/bin/env python3
"""Generate compilable C/C++ header files from type reconstruction data.

Usage:
    python generate_header.py <db_path> --class <ClassName> [--output <path>]
    python generate_header.py <db_path> --all [--output <path>]
    python generate_header.py <db_path> --from-json <scan_output.json> [--output <path>]

Examples:
    python generate_header.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor
    python generate_header.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all --output types.h
    python generate_header.py --from-json scan_results.json --output reconstructed.h

Output:
    C/C++ header with struct definitions, padding for gaps, and offset comments.
    Includes forward declarations and per-field source annotations.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import IDA_TO_C_TYPE, SIZE_TO_C_TYPE, resolve_db_path
from helpers.errors import ErrorCode, emit_error, safe_parse_args
from helpers.json_output import emit_json
from helpers.progress import status_message

from scan_struct_fields import scan_module
from extract_class_hierarchy import extract_hierarchy


def _field_c_type(field: dict) -> str:
    """Determine the best C type for a field."""
    for t in field.get("access_types", []):
        if t in IDA_TO_C_TYPE:
            return IDA_TO_C_TYPE[t]
    return SIZE_TO_C_TYPE.get(field.get("size", 8), f"uint8_t /* {field.get('size', '?')}B */")


def generate_struct(type_name: str, fields: list[dict], source_count: int) -> str:
    """Generate a C struct definition from field data."""
    lines = [
        f"/**",
        f" * {type_name} -- Reconstructed from {source_count} function(s)",
        f" * Field names are auto-generated placeholders based on byte offset.",
        f" */",
        f"struct {type_name} {{",
    ]

    current_offset = 0
    for field in fields:
        offset = field["byte_offset"]
        size = field["size"]
        c_type = _field_c_type(field)
        sources = field.get("source_functions", [])

        # Padding for gaps between known fields
        if offset > current_offset:
            gap = offset - current_offset
            pad_name = f"_unknown_{current_offset:02X}"
            pad_def = f"    uint8_t {pad_name}[0x{gap:X}];"
            pad_cmt = f"// +0x{current_offset:02X} .. +0x{offset - 1:02X}"
            lines.append(f"{pad_def:<44}{pad_cmt}")

        # Field definition
        field_name = f"field_{offset:02X}"
        src_cmt = ", ".join(sources[:3])
        if len(sources) > 3:
            src_cmt += f" (+{len(sources) - 3})"
        field_def = f"    {c_type} {field_name};"
        field_cmt = f"// +0x{offset:02X} ({size}B) [{src_cmt}]"
        lines.append(f"{field_def:<44}{field_cmt}")

        current_offset = offset + size

    lines.append(f"}};  // total known size >= 0x{current_offset:X} ({current_offset} bytes)")
    lines.append("")
    return "\n".join(lines)


def generate_header_file(
    module_name: str,
    merged_types: dict,
    hierarchy: dict | None = None,
) -> str:
    """Generate a complete .h header file from merged type data."""
    guard = f"__{module_name.upper().replace('.', '_').replace(' ', '_')}_TYPES_H__"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"#pragma once",
        f"#ifndef {guard}",
        f"#define {guard}",
        f"",
        f"/*",
        f" * Auto-generated type definitions from DeepExtractIDA analysis",
        f" * Module : {module_name}",
        f" * Generated: {ts}",
        f" * Tool   : reconstruct-types skill",
        f" *",
        f" * WARNING: Struct layouts are inferred from decompiled memory access",
        f" * patterns. Field names are placeholders -- review and rename.",
        f" * Padding regions (_unknown_XX) represent gaps between known fields.",
        f" */",
        f"",
        f"#include <stdint.h>",
        f"#include <stdbool.h>",
        f"",
    ]

    # Separate named types from anonymous ones
    named = sorted(k for k in merged_types if not k.startswith("_anon_"))
    anon = sorted(k for k in merged_types if k.startswith("_anon_"))

    # Forward declarations
    if named:
        lines.append("/* Forward declarations */")
        for name in named:
            lines.append(f"struct {name};")
        lines.append("")

    # Named struct definitions
    for name in named:
        td = merged_types[name]
        lines.append(generate_struct(name, td["fields"], td.get("total_source_functions", 0)))

    # Anonymous / unresolved types
    if anon:
        lines.extend([
            "/* ============================================================",
            " * Unresolved / Anonymous Types",
            " * (base variable type could not be determined)",
            " * ============================================================ */",
            "",
        ])
        for name in anon:
            td = merged_types[name]
            lines.append(generate_struct(name, td["fields"], td.get("total_source_functions", 0)))

    lines.append(f"#endif /* {guard} */")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate C/C++ header files from type reconstruction.",
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--class", dest="class_name", help="Reconstruct a specific class")
    src_group.add_argument("--all", action="store_true", help="Reconstruct all discovered types")
    src_group.add_argument("--from-json", dest="json_path",
                           help="Load scan results from JSON file (output of scan_struct_fields.py --json)")
    parser.add_argument("db_path", nargs="?", help="Path to the individual analysis DB (not needed with --from-json)")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    if args.json_path:
        json_p = Path(args.json_path)
        if not json_p.exists():
            emit_error(f"JSON input not found: {json_p}", ErrorCode.NOT_FOUND)
        with open(json_p, "r", encoding="utf-8") as f:
            scan_result = json.load(f)
        module_name = scan_result.get("module", "unknown")
    else:
        if not args.db_path:
            emit_error("db_path is required unless using --from-json", ErrorCode.INVALID_ARGS)
        db_path = resolve_db_path(args.db_path)
        status_message("Scanning for memory access patterns...")
        scan_result = scan_module(db_path, class_filter=args.class_name, all_classes=args.all)
        module_name = scan_result.get("module", "unknown")

    merged = scan_result.get("merged_types", {})
    if not merged:
        emit_error("No struct field accesses found.", ErrorCode.NO_DATA)

    status_message(f"Generating header for {len(merged)} type(s)...")

    # Optionally enrich with hierarchy data
    hierarchy = None
    if args.db_path and not args.json_path:
        hierarchy = extract_hierarchy(resolve_db_path(args.db_path), args.class_name)

    header = generate_header_file(module_name, merged, hierarchy)

    if args.json:
        emit_json({
            "status": "ok",
            "header": header,
            "type_count": len(merged),
            "class_name": args.class_name,
        })
    elif args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(header, encoding="utf-8")
        status_message(f"Header written to {out}")
    else:
        print(header)


if __name__ == "__main__":
    main()
