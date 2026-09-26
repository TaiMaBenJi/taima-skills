#!/usr/bin/env python3
"""Full module type reconstruction -- the subagent's main entry point.

Orchestrates the complete pipeline in a single command:

1. **Discover** -- list all C++ classes in the module via mangled names
2. **Hierarchy** -- extract class relationships, vtables, ctors/dtors
3. **Scan** -- scan decompiled code *and* assembly for memory access patterns
4. **Merge** -- conflict-resolve, infer padding, score confidence
5. **COM** (optional) -- integrate COM vtable layouts and WRL templates
6. **Generate** -- produce a compilable C++ header with offset annotations

The script calls existing skill helper scripts via subprocess (to avoid
``sys.path`` / ``_common.py`` namespace conflicts across skills) and
imports the co-located ``merge_evidence`` module directly.

Usage
-----
::

    python reconstruct_all.py <db_path>
    python reconstruct_all.py <db_path> --class <ClassName>
    python reconstruct_all.py <db_path> --output types.h
    python reconstruct_all.py <db_path> --include-com
    python reconstruct_all.py <db_path> --include-com --json

Examples
--------
::

    python .claude/agents/type-reconstructor/scripts/reconstruct_all.py \\
        extracted_dbs/appinfo_dll_e98d25a9e8.db

    python .claude/agents/type-reconstructor/scripts/reconstruct_all.py \\
        extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor --output types.h

    python .claude/agents/type-reconstructor/scripts/reconstruct_all.py \\
        extracted_dbs/appinfo_dll_e98d25a9e8.db --include-com --json

Output
------
Complete header file with all reconstructed structs, classes, enums, and
COM interfaces.  Each field is annotated with its confidence level and
evidence count.  With ``--json``, emits a structured JSON object with
all intermediate data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import (
    IDA_TO_C_TYPE,
    SIZE_TO_C_TYPE,
    WORKSPACE_ROOT,
    resolve_db_path,
    run_skill_script,
)
from helpers.errors import ErrorCode, db_error_handler, emit_error, log_error, safe_parse_args
from helpers.json_output import emit_json
from helpers.progress import status_message
from helpers.script_runner import get_workspace_args
from merge_evidence import merge_evidence
from validate_layout import parse_header, validate_layout


# ---------------------------------------------------------------------------
# Header generation (self-contained; avoids importing generate_header.py
# which pulls in scan_struct_fields and its _common.py)
# ---------------------------------------------------------------------------

def _field_c_type(field: dict) -> str:
    """Pick the best C type for a merged field."""
    if field.get("is_vtable_ptr"):
        return "void*  /* vtable */"

    c = field.get("c_type")
    if c:
        return c

    for t in field.get("access_types", []):
        if t in IDA_TO_C_TYPE:
            return IDA_TO_C_TYPE[t]
    return SIZE_TO_C_TYPE.get(field.get("size", 8), "uint64_t")


def _generate_struct(type_name: str, type_data: dict) -> str:
    """Render a single struct definition from merged type data."""
    fields = type_data.get("fields", [])
    src_count = type_data.get("total_source_functions", 0)
    is_com = type_data.get("is_com_class", False)

    lines: list[str] = []
    lines.append(f"/**")
    lines.append(f" * {type_name} -- Reconstructed from {src_count} function(s)")
    if is_com:
        lines.append(f" * COM class -- first pointer is vtable")
    lines.append(f" */")
    lines.append(f"struct {type_name} {{")

    for field in fields:
        offset = field["byte_offset"]
        size = field["size"]

        if field.get("is_padding"):
            arr_size = field.get("array_size", size)
            pad_def = f"    uint8_t {field['field_name']}[0x{arr_size:X}];"
            pad_cmt = f"// +0x{offset:02X} .. +0x{offset + arr_size - 1:02X} (padding)"
            lines.append(f"{pad_def:<52}{pad_cmt}")
        else:
            c_type = _field_c_type(field)
            fname = field.get("field_name", f"field_{offset:02X}")
            conf = field.get("confidence", "?")
            asm_tag = " [asm]" if field.get("asm_verified") else ""
            srcs = field.get("source_functions", [])
            src_str = ", ".join(srcs[:3])
            if len(srcs) > 3:
                src_str += f" (+{len(srcs) - 3})"
            field_def = f"    {c_type} {fname};"
            field_cmt = (
                f"// +0x{offset:02X} ({size}B) "
                f"conf={conf}{asm_tag} [{src_str}]"
            )
            lines.append(f"{field_def:<52}{field_cmt}")

    total_size = type_data.get("total_known_size", 0)
    lines.append(
        f"}};  // total known size >= 0x{total_size:X} ({total_size} bytes)"
    )

    # Append COM interface summary as comment
    if type_data.get("com_interfaces"):
        lines.append(f"")
        lines.append(f"/* COM interfaces for {type_name}:")
        for iface in type_data["com_interfaces"]:
            base = iface.get("base_interface", "IUnknown")
            slots = iface.get("slot_count", "?")
            conf = iface.get("confidence", "?")
            lines.append(f" *   Base: {base}, Slots: {slots}, Confidence: {conf}")
            for method in iface.get("methods", [])[:10]:
                lines.append(
                    f" *     [{method.get('slot', '?')}] "
                    f"{method.get('offset_hex', '')} "
                    f"{method.get('method_name', '?')}"
                )
            if len(iface.get("methods", [])) > 10:
                lines.append(
                    f" *     ... and {len(iface['methods']) - 10} more"
                )
        lines.append(f" */")

    lines.append("")
    return "\n".join(lines)


def generate_full_header(
    module_name: str,
    merged_types: dict,
) -> str:
    """Generate a complete compilable .h header from merged type data."""
    guard = f"__{module_name.upper().replace('.', '_').replace(' ', '_')}_TYPES_H__"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = [
        f"#pragma once",
        f"#ifndef {guard}",
        f"#define {guard}",
        f"",
        f"/*",
        f" * Auto-generated type definitions from DeepExtractIDA analysis",
        f" * Module  : {module_name}",
        f" * Generated: {ts}",
        f" * Tool    : type-reconstructor subagent",
        f" *",
        f" * WARNING: Struct layouts are inferred from decompiled memory access",
        f" * patterns and assembly ground truth.  Field names are auto-generated",
        f" * placeholders -- review and rename.  Padding regions mark gaps between",
        f" * known fields.  Confidence annotations indicate evidence strength.",
        f" */",
        f"",
        f"#include <stdint.h>",
        f"#include <stdbool.h>",
        f"",
    ]

    # Separate named vs anonymous types
    named = sorted(k for k in merged_types if not k.startswith("_anon_"))
    anon = sorted(k for k in merged_types if k.startswith("_anon_"))

    # Forward declarations
    if named:
        lines.append("/* Forward declarations */")
        for name in named:
            lines.append(f"struct {name};")
        lines.append("")

    # Named structs
    for name in named:
        lines.append(_generate_struct(name, merged_types[name]))

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
            lines.append(_generate_struct(name, merged_types[name]))

    lines.append(f"#endif /* {guard} */")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline phases
# ---------------------------------------------------------------------------

def _phase_1_discover(
    db_path: str,
    workspace_dir: str | None = None,
) -> dict | None:
    """Phase 1: Discover all C++ types in the module."""
    status_message("Phase 1: Discovering types...")
    return run_skill_script(
        "reconstruct-types", "list_types.py",
        [db_path, "--with-vtables"],
        workspace_dir=workspace_dir,
        workspace_step="discover_types",
    )


def _phase_2_hierarchy(
    db_path: str,
    class_filter: str | None = None,
    workspace_dir: str | None = None,
) -> dict | None:
    """Phase 2: Extract class hierarchy (ctors, dtors, vtables, methods)."""
    status_message("Phase 2: Extracting class hierarchy...")
    args = [db_path]
    if class_filter:
        args.extend(["--class", class_filter])
    return run_skill_script(
        "reconstruct-types", "extract_class_hierarchy.py", args,
        workspace_dir=workspace_dir,
        workspace_step="extract_hierarchy",
    )


def _phase_3_scan(
    db_path: str,
    class_filter: str | None = None,
    workspace_dir: str | None = None,
) -> dict | None:
    """Phase 3: Scan all fields (decompiled + assembly)."""
    status_message("Phase 3: Scanning field access patterns...")
    if class_filter:
        args = [db_path, "--class", class_filter]
    else:
        args = [db_path, "--all-classes"]
    return run_skill_script(
        "reconstruct-types", "scan_struct_fields.py", args,
        timeout=600,  # can be slow for large modules
        workspace_dir=workspace_dir,
        workspace_step="scan_fields",
    )


def _phase_4_merge(
    scan_data: dict, com_data: dict | None = None,
    class_filter: str | None = None,
) -> dict:
    """Phase 4: Merge evidence with confidence scoring."""
    status_message("Phase 4: Merging evidence...")
    return merge_evidence(scan_data, com_data=com_data, class_filter=class_filter)


def _phase_5_com(
    db_path: str,
    workspace_dir: str | None = None,
) -> dict | None:
    """Phase 5 (optional): Scan for COM interfaces."""
    status_message("Phase 5: Scanning COM interfaces...")
    return run_skill_script(
        "com-interface-reconstruction", "scan_com_interfaces.py",
        [db_path],
        workspace_dir=workspace_dir,
        workspace_step="com_interfaces",
    )


def _phase_6_header(module_name: str, merged_types: dict) -> str:
    """Phase 6: Generate compilable C++ header."""
    status_message("Phase 6: Generating header...")
    return generate_full_header(module_name, merged_types)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def reconstruct_all(
    db_path: str,
    class_filter: str | None = None,
    include_com: bool = False,
    output_path: str | None = None,
    json_output: bool = False,
    workspace_dir: str | None = None,
    validate: bool = False,
) -> dict:
    """Run the full reconstruction pipeline.

    When *workspace_dir* is provided, each phase's skill-script invocation
    receives ``--workspace-dir`` / ``--workspace-step`` so intermediate
    results are written to the run directory via the bootstrap.

    Returns a dict containing all intermediate and final results.
    """
    results: dict = {
        "db_path": db_path,
        "class_filter": class_filter,
        "include_com": include_com,
        "phases": {},
    }
    if workspace_dir:
        results["workspace_run_dir"] = workspace_dir

    # Phase 1: Discover types
    type_list = _phase_1_discover(db_path, workspace_dir=workspace_dir)
    results["phases"]["discover"] = {
        "total_classes": type_list.get("total_classes", 0) if type_list else 0,
    }
    if type_list:
        module_name = type_list.get("module", "(unknown)")
    else:
        module_name = "(unknown)"
        status_message("WARNING: Type discovery returned no data.")

    results["module"] = module_name

    # Phase 2: Class hierarchy
    hierarchy = _phase_2_hierarchy(db_path, class_filter, workspace_dir=workspace_dir)
    results["phases"]["hierarchy"] = {
        "total_classes": hierarchy.get("total_classes", 0) if hierarchy else 0,
    }

    # Phase 3: Scan fields
    scan_data = _phase_3_scan(db_path, class_filter, workspace_dir=workspace_dir)
    if scan_data is None:
        log_error("Skill script scan_struct_fields.py failed", ErrorCode.UNKNOWN)
        results["phases"]["scan"] = {"error": "scan failed"}
        results["error"] = "Field scanning returned no data"
        return results

    results["phases"]["scan"] = {
        "functions_scanned": scan_data.get("functions_scanned", 0),
        "types_found": len(scan_data.get("merged_types", {})),
    }

    # Phase 5 (optional): COM interfaces (runs before merge to feed into it)
    com_data = None
    if include_com:
        com_data = _phase_5_com(db_path, workspace_dir=workspace_dir)
        if com_data:
            summary = com_data.get("com_summary", {})
            results["phases"]["com"] = {
                "com_classes": summary.get("unique_com_classes", 0),
                "com_vtables": summary.get("com_vtables", 0),
                "wrl_functions": summary.get("wrl_function_count", 0),
            }
        else:
            results["phases"]["com"] = {"status": "no_data"}

    # Phase 4: Merge evidence
    merged = _phase_4_merge(scan_data, com_data=com_data, class_filter=class_filter)
    merged_types = merged.get("merged_types", {})
    results["phases"]["merge"] = {
        "types_merged": len(merged_types),
    }

    # Phase 6: Generate header
    header_text = _phase_6_header(module_name, merged_types)
    results["phases"]["header"] = {
        "structs_generated": len(merged_types),
        "header_length": len(header_text),
    }

    # Optional validation phase
    if validate:
        status_message("Phase 7: Validating layouts against assembly...")
        header_structs = parse_header(header_text)
        if header_structs:
            validation_result = validate_layout(
                db_path, header_structs, class_filter=class_filter,
            )
            results["validation"] = validation_result
            results["phases"]["validate"] = {
                "structs_validated": validation_result.get("structs_validated", 0),
                "reports_summary": {
                    name: {
                        "coverage_percent": rpt.get("coverage_percent", 0),
                        "match_count": rpt.get("match_count", 0),
                        "size_mismatch_count": rpt.get("size_mismatch_count", 0),
                        "missing_count": rpt.get("missing_count", 0),
                    }
                    for name, rpt in validation_result.get("reports", {}).items()
                    if rpt.get("status") == "validated"
                },
            }
        else:
            results["phases"]["validate"] = {"status": "no_structs_to_validate"}

    # Include full data in results for JSON mode
    if json_output:
        results["type_list"] = type_list
        results["hierarchy"] = hierarchy
        results["scan_data"] = scan_data
        results["com_data"] = com_data
        results["merged"] = merged
        results["header"] = header_text

    # Write output
    if output_path:
        out = Path(output_path)
        if not out.is_absolute():
            out = WORKSPACE_ROOT / output_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(header_text, encoding="utf-8")
        status_message(f"Header written to {out}")
        results["output_path"] = str(out)
    elif not json_output:
        # Print header to stdout
        print(header_text)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Full module type reconstruction.  Orchestrates: discover types -> "
            "extract hierarchy -> scan fields -> merge evidence -> "
            "(optional) COM interfaces -> generate header."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "db_path",
        help="Path to the individual analysis DB",
    )
    parser.add_argument(
        "--class", dest="class_name",
        help="Reconstruct only the named class (case-insensitive substring)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Write the header to this file path (default: print to stdout)",
    )
    parser.add_argument(
        "--include-com", action="store_true",
        help="Include COM interface reconstruction (adds COM vtable data)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output full pipeline results as JSON (includes all intermediate data)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="After reconstruction, validate struct layouts against assembly access patterns",
    )
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    # workspace_dir / workspace_step are set by the bootstrap interceptor
    ws_args = get_workspace_args(args)
    ws_dir = ws_args["workspace_dir"]
    force_json = args.json or bool(ws_dir)

    with db_error_handler(db_path, "type reconstruction"):
        result = reconstruct_all(
            db_path=db_path,
            class_filter=args.class_name,
            include_com=args.include_com,
            output_path=args.output,
            json_output=force_json,
            workspace_dir=ws_dir,
            validate=args.validate,
        )

    if force_json:
        emit_json(result, default=str)
    else:
        # Print summary
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  Type Reconstruction Summary", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"  Module:           {result.get('module', '?')}", file=sys.stderr)
        for phase, data in result.get("phases", {}).items():
            print(f"  {phase:<18} {data}", file=sys.stderr)
        if result.get("error"):
            print(f"  ERROR: {result['error']}", file=sys.stderr)
        elif result.get("output_path"):
            print(f"  Output:           {result['output_path']}", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)


if __name__ == "__main__":
    main()
