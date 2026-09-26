#!/usr/bin/env python3
"""Scan x64 assembly for struct/class field access patterns.

Uses x64 assembly as the sole evidence source for struct field layouts.
Assembly provides exact sizes from instruction operands and is deterministic
across Hex-Rays versions, unlike decompiled C++ which varies with
optimization levels, version, and formatting quirks.

Functions without assembly data produce no struct field results.

Usage:
    python scan_struct_fields.py <db_path> --class <ClassName>
    python scan_struct_fields.py <db_path> --function <FuncName>
    python scan_struct_fields.py <db_path> --id <function_id>
    python scan_struct_fields.py <db_path> --all-classes
    python scan_struct_fields.py <db_path> --all-classes --json

Examples:
    python scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor
    python scan_struct_fields.py extracted_dbs/cmd_exe_6d109a3a00.db --function BatLoop
    python scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all-classes --json

Output:
    Struct field layout: byte offsets, sizes, access types, and source functions.
    With --class or --all-classes, merges accesses across functions into unified layouts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import (
    WORKSPACE_ROOT, TYPE_SIZES, parse_class_from_mangled, resolve_db_path,
    ASM_REG_SIZES, PARAM_REGS_X64, ASM_PTR_SIZES, STACK_REGS,
)

from helpers import open_individual_analysis_db, load_function_index_for_db
from helpers.errors import db_error_handler, safe_parse_args
from helpers.progress import progress_iter
from helpers.cache import get_cached, cache_result
from helpers.json_output import emit_json
from helpers.struct_scanner import (
    parse_signature_params as _parse_signature_params,
    scan_assembly_struct_accesses as _scan_assembly_struct_accesses,
)

# ---------------------------------------------------------------------------
# Assembly scanning (sole evidence source for struct field layouts)
# ---------------------------------------------------------------------------


def scan_assembly_code(code: str) -> list[dict]:
    """Extract struct field accesses from x64 assembly code.

    Provides high-accuracy offset and size data directly from instructions.
    Detects parameter register saves in the prologue (e.g., ``mov r13, rcx``)
    to track struct pointer aliases throughout the function.

    Returns list of dicts: base, byte_offset, size, param_num, line_num.
    """
    return _scan_assembly_struct_accesses(
        code,
        param_regs=PARAM_REGS_X64,
        asm_ptr_sizes=ASM_PTR_SIZES,
        asm_reg_sizes=ASM_REG_SIZES,
        stack_regs=STACK_REGS,
    )


def parse_signature_params(sig: str) -> dict[str, str]:
    """Extract param_name -> type_string mapping from a function signature."""
    return _parse_signature_params(sig)


# ---------------------------------------------------------------------------
# Module-level scanning
# ---------------------------------------------------------------------------

def scan_module(
    db_path: str,
    class_filter: str | None = None,
    function_filter: str | None = None,
    all_classes: bool = False,
    app_only: bool = False,
    *,
    no_cache: bool = False,
    function_id: int | None = None,
) -> dict:
    """Scan functions for struct field access patterns using x64 assembly.

    Assembly is the sole evidence source -- it provides deterministic sizes
    and offsets from instruction operands.  Functions without assembly data
    are skipped (no struct field results).

    When *app_only* is True, library/boilerplate functions (WIL/STL/WRL/CRT/ETW)
    are skipped using the function_index.

    Returns dict with per_function results and merged_types (when class/all mode).
    """
    # Cache only the expensive --all-classes scan (per-function / per-class are cheap)
    if all_classes and not no_cache:
        params = {"all_classes": True, "app_only": app_only}
        cached = get_cached(db_path, "scan_struct_fields", params=params)
        if cached is not None:
            return cached

    # Build library names set for --app-only filtering
    library_names: set[str] = set()
    if app_only:
        function_index = load_function_index_for_db(db_path)
        if function_index:
            library_names = {k for k, v in function_index.items() if v.get("library") is not None}

    with db_error_handler(db_path, "scanning struct fields"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            if function_id is not None:
                func = db.get_function_by_id(function_id)
                functions = [func] if func else []
            elif function_filter:
                functions = db.search_functions(name_contains=function_filter, has_decompiled_code=True)
            else:
                functions = db.get_all_functions()

    # Filter for class-specific analysis
    if class_filter:
        filtered = []
        for func in functions:
            cls = parse_class_from_mangled(func.mangled_name)
            if cls and class_filter.lower() in cls["full_qualified_name"].lower():
                filtered.append(func)
                continue
            sig = func.function_signature_extended or func.function_signature or ""
            if class_filter.lower() in sig.lower():
                filtered.append(func)
        functions = filtered

    per_function: dict[str, dict] = {}

    for func in progress_iter(functions, label="scan_struct_fields", json_mode=all_classes):
        if not func.assembly_code:
            continue

        # Skip library functions when --app-only
        if library_names and (func.function_name or "") in library_names:
            continue

        sig = func.function_signature_extended or func.function_signature or ""
        param_types = parse_signature_params(sig)
        if not param_types and func.decompiled_code:
            first_line = func.decompiled_code.split("\n", 1)[0].strip()
            if "(" in first_line:
                param_types = parse_signature_params(first_line)
        param_names = list(param_types.keys())
        func_class_info = parse_class_from_mangled(func.mangled_name)
        func_class = func_class_info["class_name"] if func_class_info else None

        # -- Scan assembly (sole evidence source) -------------------------------
        all_accesses: list[dict] = scan_assembly_code(func.assembly_code)
        for acc in all_accesses:
            pn = acc.get("param_num", 0)
            if 0 < pn <= len(param_names):
                acc["base"] = param_names[pn - 1]
            acc["type"] = f"asm_{acc['size']}B"
        if not all_accesses:
            continue

        # -- Group by base variable, deduplicate by offset ----------------------
        by_base: dict[str, list] = defaultdict(list)
        for acc in all_accesses:
            by_base[acc["base"]].append(acc)

        fields_by_base: dict[str, dict] = {}
        for base_var, base_accs in by_base.items():
            base_type = param_types.get(base_var, "unknown")
            seen: dict[int, dict] = {}
            for acc in base_accs:
                off = acc["byte_offset"]
                is_asm = acc.get("source") == "assembly"
                if off not in seen:
                    seen[off] = {
                        "byte_offset": off,
                        "offset_hex": f"0x{off:02X}",
                        "size": acc["size"],
                        "access_type": acc["type"],
                        "asm_verified": is_asm,
                    }
                else:
                    # Assembly sizes are authoritative -- prefer larger / asm size
                    if is_asm:
                        seen[off]["size"] = acc["size"]
                        seen[off]["asm_verified"] = True
                    else:
                        seen[off]["size"] = max(seen[off]["size"], acc["size"])

            fields_by_base[base_var] = {
                "base_type": base_type,
                "fields": sorted(seen.values(), key=lambda x: x["byte_offset"]),
            }

        func_key = func.function_name or f"id_{func.function_id}"
        per_function[func_key] = {
            "function_name": func.function_name,
            "function_id": func.function_id,
            "class_name": func_class,
            "signature": sig,
            "param_types": param_types,
            "fields_by_base": fields_by_base,
        }

    # Merge across functions for class/all-classes mode
    merged: dict[str, dict] = {}
    if class_filter or all_classes:
        type_fields: dict[str, dict[int, dict]] = defaultdict(lambda: defaultdict(
            lambda: {"byte_offset": 0, "size": 0, "access_types": set(),
                     "source_functions": [], "asm_verified": False}
        ))

        for func_name, fd in per_function.items():
            for base_var, base_info in fd["fields_by_base"].items():
                base_type = base_info["base_type"]
                # Map base to a type name
                if base_var in ("this", "a1") and fd.get("class_name"):
                    type_key = fd["class_name"]
                elif "struct " in base_type or base_type not in ("unknown", "__int64", "__int64 *", ""):
                    type_key = (base_type.replace("struct ", "").replace("const ", "")
                                .replace(" *", "").replace("*", "").strip())
                else:
                    type_key = f"_anon_{base_var}"

                if not type_key:
                    type_key = f"_anon_{base_var}"

                for field in base_info["fields"]:
                    off = field["byte_offset"]
                    entry = type_fields[type_key][off]
                    entry["byte_offset"] = off
                    entry["size"] = max(entry["size"], field["size"])
                    entry["access_types"].add(field["access_type"])
                    if field.get("asm_verified"):
                        entry["asm_verified"] = True
                    if func_name not in entry["source_functions"]:
                        entry["source_functions"].append(func_name)

        for type_name, fields_dict in type_fields.items():
            all_funcs = set()
            for f in fields_dict.values():
                all_funcs.update(f["source_functions"])
            merged[type_name] = {
                "fields": sorted([
                    {
                        "byte_offset": f["byte_offset"],
                        "offset_hex": f"0x{f['byte_offset']:02X}",
                        "size": f["size"],
                        "access_types": sorted(f["access_types"]),
                        "source_functions": f["source_functions"],
                        "asm_verified": f["asm_verified"],
                    }
                    for f in fields_dict.values()
                ], key=lambda x: x["byte_offset"]),
                "total_source_functions": len(all_funcs),
            }

    result = {
        "module": file_info.file_name if file_info else "(unknown)",
        "class_filter": class_filter,
        "function_filter": function_filter,
        "functions_scanned": len(per_function),
        "per_function": per_function,
        "merged_types": merged,
    }

    # Cache only the expensive --all-classes scan
    if all_classes:
        params = {"all_classes": True, "app_only": app_only}
        cache_result(db_path, "scan_struct_fields", result, params=params)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan decompiled code for struct field access patterns.",
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--class", dest="class_name", help="Scan all methods of a class")
    group.add_argument("--function", dest="func_name", help="Scan a specific function")
    group.add_argument("--id", "--function-id", dest="function_id", type=int,
                       help="Scan a specific function by ID (preferred after initial lookup)")
    group.add_argument("--all-classes", action="store_true", help="Scan all class methods")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--app-only", action="store_true",
                        help="Exclude library/boilerplate functions (WIL/STL/WRL/CRT/ETW)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Bypass result cache (only affects --all-classes mode)")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)
    result = scan_module(db_path, class_filter=args.class_name,
                         function_filter=args.func_name, all_classes=args.all_classes,
                         app_only=args.app_only,
                         no_cache=args.no_cache, function_id=args.function_id)

    if args.json:
        emit_json(result, default=lambda x: sorted(x) if isinstance(x, set) else str(x))
        return

    print(f"Module: {result['module']}")
    print(f"Functions scanned: {result['functions_scanned']}")

    if result["merged_types"]:
        print(f"\nMerged Type Layouts ({len(result['merged_types'])} types):")
        for type_name in sorted(result["merged_types"]):
            td = result["merged_types"][type_name]
            print(f"\n{'=' * 65}")
            print(f"  {type_name}  ({td['total_source_functions']} source functions)")
            print(f"{'=' * 65}")
            print(f"  {'Offset':<10} {'Size':<6} {'ASM':>3}  {'Type(s)':<25} {'Source Functions'}")
            print(f"  {'-' * 10} {'-' * 6} {'-' * 3}  {'-' * 25} {'-' * 30}")
            for field in td["fields"]:
                types_str = ", ".join(t for t in field["access_types"] if not t.startswith("asm_"))
                asm_tag = "yes" if field.get("asm_verified") else ""
                if not types_str:
                    # Only assembly types -- show the asm type
                    types_str = ", ".join(field["access_types"])
                funcs = field["source_functions"]
                funcs_str = ", ".join(funcs[:3])
                if len(funcs) > 3:
                    funcs_str += f" (+{len(funcs) - 3})"
                print(f"  {field['offset_hex']:<10} {field['size']:<6} {asm_tag:>3}  {types_str:<25} {funcs_str}")
    else:
        for func_name, fd in result["per_function"].items():
            print(f"\n{'=' * 60}")
            print(f"  {func_name}  (class: {fd.get('class_name', '-')})")
            print(f"{'=' * 60}")
            for base_var, bi in fd["fields_by_base"].items():
                print(f"\n  Base: {base_var}  (type: {bi['base_type']})")
                print(f"  {'Offset':<10} {'Size':<6} {'Type'}")
                print(f"  {'-' * 10} {'-' * 6} {'-' * 15}")
                for field in bi["fields"]:
                    print(f"  {field['offset_hex']:<10} {field['size']:<6} {field['access_type']}")


if __name__ == "__main__":
    main()
