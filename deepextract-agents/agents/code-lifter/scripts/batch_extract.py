#!/usr/bin/env python3
"""Extract data for ALL methods of a class (or a list of functions) in one shot.

Avoids running extract_function_data.py N times. Returns a JSON object with:
- Module/class metadata
- Dependency-ordered function list
- Full per-function records (decompiled, assembly, xrefs, strings, etc.)
- Initial shared struct scan across all functions

Usage:
    # All methods of a class
    python batch_extract.py <db_path> --class <ClassName>

    # Specific functions by name
    python batch_extract.py <db_path> --functions func1 func2 func3

    # Specific functions by ID
    python batch_extract.py <db_path> --id-list 12,15,18,22

    # List all C++ classes with method counts
    python batch_extract.py <db_path> --list-classes [--skip-library]

    # Initialize shared state file (for use with track_shared_state.py)
    python batch_extract.py <db_path> --class <ClassName> --init-state

    # Human-readable summary (no code)
    python batch_extract.py <db_path> --class <ClassName> --summary

Examples:
    python .claude/agents/code-lifter/scripts/batch_extract.py \\
        extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor

    python .claude/agents/code-lifter/scripts/batch_extract.py \\
        extracted_dbs/cmd_exe_6d109a3a00.db --id-list 42,43,44,45 --init-state

    python .claude/agents/code-lifter/scripts/batch_extract.py \\
        extracted_dbs/cmd_exe_6d109a3a00.db --list-classes --skip-library
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from _common import (
    WORKSPACE_ROOT,
    create_initial_state,
    format_struct_definition,
    func_to_lift_record,
    has_valid_decompiled_code,
    merge_struct_fields,
    open_individual_analysis_db,
    parse_class_from_mangled,
    parse_json_safe,
    resolve_db_path,
    save_state,
    scan_struct_accesses,
    topological_sort_functions,
)
from helpers import db_error_handler, emit_error, get_workspace_args, load_function_index_for_db, resolve_function, resolve_module_dir, validate_function_id
from helpers.errors import ErrorCode, safe_parse_args
from helpers.json_output import emit_json


# ---------------------------------------------------------------------------
# Collection modes
# ---------------------------------------------------------------------------


def collect_class_methods(db_path: str, class_name: str) -> dict:
    """Collect and extract all methods of a C++ class in one shot."""
    with open_individual_analysis_db(db_path) as db:
        file_info = db.get_file_info()
        module_name = file_info.file_name if file_info else Path(db_path).stem

        # Targeted queries: only load functions matching the class name
        # instead of loading every function in the module.
        name_matches = db.search_functions(name_contains=class_name)
        sig_matches = db.search_functions_by_signature(f"%{class_name}%")

    # Merge candidates, deduplicate by function_id
    seen_ids: set[int] = set()
    all_candidates = []
    for func in name_matches + sig_matches:
        if func.function_id not in seen_ids:
            seen_ids.add(func.function_id)
            all_candidates.append(func)

    # Find methods by mangled name prefix
    method_ids: set[int] = set()
    methods = []

    for func in all_candidates:
        if func.mangled_name:
            parsed = parse_class_from_mangled(func.mangled_name)
            if parsed and parsed["class_name"] == class_name:
                methods.append(func)
                method_ids.add(func.function_id)

    # Also include functions whose signatures reference the class type
    for func in all_candidates:
        if func.function_id in method_ids:
            continue
        sig = func.function_signature or ""
        sig_ext = func.function_signature_extended or ""
        combined = sig + " " + sig_ext
        if (class_name + " " in combined or class_name + "*" in combined or
                class_name + " *" in combined):
            methods.append(func)
            method_ids.add(func.function_id)

    if not methods:
        emit_error(f"No methods found for class '{class_name}' in {module_name}", ErrorCode.NOT_FOUND)

    # Dependency ordering
    dep_order = topological_sort_functions(methods, method_ids)

    # Extract full data for all functions
    func_data = {}
    for func in methods:
        func_data[func.function_id] = func_to_lift_record(func, module_name)

    # Scan shared struct patterns
    structs = _scan_shared_structs(func_data, dep_order, class_name)

    return {
        "mode": "class",
        "class_name": class_name,
        "module_name": module_name,
        "db_path": db_path,
        "function_count": len(methods),
        "dependency_order": dep_order,
        "functions": [func_data[fid] for fid in dep_order if fid in func_data],
        "shared_structs": structs,
        "summary": _build_summary(func_data, dep_order),
    }


def collect_by_ids(db_path: str, function_ids: list[int]) -> dict:
    """Extract data for specific function IDs."""
    with open_individual_analysis_db(db_path) as db:
        file_info = db.get_file_info()
        module_name = file_info.file_name if file_info else Path(db_path).stem

        methods = db.get_functions_by_ids(function_ids)

    if not methods:
        emit_error(f"No functions found for IDs {function_ids}", ErrorCode.NOT_FOUND)

    method_ids = {f.function_id for f in methods}
    dep_order = topological_sort_functions(methods, method_ids)

    func_data = {}
    for func in methods:
        func_data[func.function_id] = func_to_lift_record(func, module_name)

    # Try to infer class name from mangled names
    class_name = _infer_class_name(methods)

    structs = _scan_shared_structs(func_data, dep_order, class_name)

    return {
        "mode": "id_list",
        "class_name": class_name,
        "module_name": module_name,
        "db_path": db_path,
        "function_count": len(methods),
        "dependency_order": dep_order,
        "functions": [func_data[fid] for fid in dep_order if fid in func_data],
        "shared_structs": structs,
        "summary": _build_summary(func_data, dep_order),
    }


def collect_by_names(db_path: str, function_names: list[str]) -> dict:
    """Extract data for specific function names."""
    function_index = load_function_index_for_db(db_path)
    with open_individual_analysis_db(db_path) as db:
        file_info = db.get_file_info()
        module_name = file_info.file_name if file_info else Path(db_path).stem

        methods = []
        not_found = []
        for name in function_names:
            func, _err = resolve_function(
                db, name=name, function_index=function_index,
            )
            if func is not None:
                methods.append(func)
            else:
                not_found.append(name)

    if not methods:
        emit_error(f"No functions found for names: {function_names}", ErrorCode.NOT_FOUND)

    method_ids = {f.function_id for f in methods}
    dep_order = topological_sort_functions(methods, method_ids)

    func_data = {}
    for func in methods:
        func_data[func.function_id] = func_to_lift_record(func, module_name)

    class_name = _infer_class_name(methods)
    structs = _scan_shared_structs(func_data, dep_order, class_name)

    result = {
        "mode": "function_names",
        "class_name": class_name,
        "module_name": module_name,
        "db_path": db_path,
        "function_count": len(methods),
        "dependency_order": dep_order,
        "functions": [func_data[fid] for fid in dep_order if fid in func_data],
        "shared_structs": structs,
        "summary": _build_summary(func_data, dep_order),
    }

    if not_found:
        result["not_found"] = not_found

    return result


def list_classes(db_path: str, skip_library: bool = False) -> dict:
    """Enumerate all C++ classes in a module with per-class method counts.

    Checks for existing ``lifted_<ClassName>.cpp`` files so callers can
    see which classes have already been lifted.
    """
    with open_individual_analysis_db(db_path) as db:
        all_funcs = db.get_all_functions()
        file_info = db.get_file_info()
        module_name = file_info.file_name if file_info else Path(db_path).stem

    function_index = load_function_index_for_db(db_path)
    library_names: set[str] = set()
    if skip_library and function_index:
        library_names = {k for k, v in function_index.items() if v.get("library") is not None}

    class_counter: Counter[str] = Counter()
    for func in all_funcs:
        if library_names and (func.function_name or "") in library_names:
            continue
        if func.mangled_name:
            parsed = parse_class_from_mangled(func.mangled_name)
            if parsed:
                class_counter[parsed["class_name"]] += 1

    mod_dir = resolve_module_dir(module_name)

    classes = []
    for name, count in class_counter.most_common():
        entry: dict = {"name": name, "method_count": count}
        if mod_dir is not None:
            lifted_path = mod_dir / f"lifted_{name}.cpp"
            if lifted_path.is_file():
                entry["already_lifted"] = True
                entry["lifted_file"] = str(lifted_path)
            else:
                entry["already_lifted"] = False
        classes.append(entry)

    return {
        "status": "ok",
        "module_name": module_name,
        "db_path": db_path,
        "classes": classes,
        "total_classes": len(classes),
    }


def print_list_classes(result: dict) -> None:
    """Print human-readable class listing."""
    module = result["module_name"]
    total = result["total_classes"]
    classes = result["classes"]

    print(f"{'=' * 70}")
    print(f"  C++ classes in {module}  ({total} classes)")
    print(f"  DB: {result['db_path']}")
    print(f"{'=' * 70}")

    if not classes:
        print("\n  No C++ classes found.")
        return

    max_name_len = max(len(c["name"]) for c in classes)
    col_width = min(max(max_name_len, 10), 50)

    print(f"\n  {'Class':<{col_width}}  Methods  Status")
    print(f"  {'-' * col_width}  -------  ----------")
    for c in classes:
        lifted = c.get("already_lifted", False)
        tag = "[LIFTED]" if lifted else ""
        print(f"  {c['name']:<{col_width}}  {c['method_count']:>7}  {tag}")

    lifted_count = sum(1 for c in classes if c.get("already_lifted"))
    if lifted_count:
        print(f"\n  {lifted_count}/{total} class(es) already lifted.")

    print(f"\nUse --class <ClassName> to extract methods for lifting.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_class_name(methods: list) -> Optional[str]:
    """Try to infer a class name from a list of function records."""
    for func in methods:
        if func.mangled_name:
            parsed = parse_class_from_mangled(func.mangled_name)
            if parsed:
                return parsed["class_name"]
    return None


def _scan_shared_structs(
    func_data: dict[int, dict],
    dep_order: list[int],
    class_name: Optional[str] = None,
) -> dict:
    """Scan struct access patterns across all functions and merge results."""
    all_accesses: dict[str, list[dict]] = defaultdict(list)
    source_map: dict[str, list[str]] = defaultdict(list)

    for fid in dep_order:
        data = func_data.get(fid)
        if not data or not data.get("has_decompiled"):
            continue
        code = data.get("decompiled_code", "")
        if not code:
            continue

        accesses = scan_struct_accesses(code)
        for acc in accesses:
            base = acc["base"]
            all_accesses[base].append(acc)
            fname = data.get("function_name", f"ID={fid}")
            if fname not in source_map[base]:
                source_map[base].append(fname)

    # Merge and produce struct definitions
    structs = {}
    for base, accesses in sorted(all_accesses.items()):
        if len(accesses) < 2:
            continue

        fields = merge_struct_fields({base: accesses})
        if not fields:
            continue

        # Use class_name for a1/this, otherwise generic
        if base in ("a1", "this") and class_name:
            struct_name = class_name
        else:
            struct_name = f"Struct_{base}"

        struct_def = format_struct_definition(
            struct_name, fields, func_count=len(source_map[base]),
        )

        structs[base] = {
            "struct_name": struct_name,
            "field_count": len(fields),
            "fields": fields,
            "source_functions": source_map[base],
            "struct_definition": struct_def,
        }

    return structs


def _build_summary(func_data: dict[int, dict], dep_order: list[int]) -> dict:
    """Build a compact summary of the extracted function set."""
    total = len(dep_order)
    has_code = sum(1 for fid in dep_order if func_data.get(fid, {}).get("has_decompiled"))
    has_asm = sum(1 for fid in dep_order if func_data.get(fid, {}).get("has_assembly"))

    # Count roles
    roles: dict[str, int] = defaultdict(int)
    for fid in dep_order:
        role = func_data.get(fid, {}).get("role", "unknown")
        roles[role or "unknown"] += 1

    # Total lines of code
    total_code_lines = 0
    total_asm_lines = 0
    for fid in dep_order:
        data = func_data.get(fid, {})
        code = data.get("decompiled_code", "")
        asm = data.get("assembly_code", "")
        total_code_lines += len(code.splitlines()) if code else 0
        total_asm_lines += len(asm.splitlines()) if asm else 0

    return {
        "total_functions": total,
        "with_decompiled": has_code,
        "with_assembly": has_asm,
        "without_decompiled": total - has_code,
        "role_distribution": dict(roles),
        "total_decompiled_lines": total_code_lines,
        "total_assembly_lines": total_asm_lines,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_text_summary(result: dict) -> None:
    """Print a human-readable summary (no code)."""
    mode = result["mode"]
    module = result["module_name"]
    class_name = result.get("class_name", "")
    summary = result.get("summary", {})

    print(f"{'=' * 80}")
    if class_name:
        print(f"  Batch Extract: {class_name}  ({module})")
    else:
        print(f"  Batch Extract: {module}")
    print(f"  Mode: {mode}")
    print(f"  Functions: {summary.get('total_functions', '?')}")
    print(f"  With decompiled code: {summary.get('with_decompiled', '?')}")
    print(f"  With assembly: {summary.get('with_assembly', '?')}")
    print(f"  Total decompiled lines: {summary.get('total_decompiled_lines', '?')}")
    print(f"  Total assembly lines: {summary.get('total_assembly_lines', '?')}")
    print(f"  DB: {result.get('db_path', '?')}")
    print(f"{'=' * 80}")

    # Role distribution
    roles = summary.get("role_distribution", {})
    if roles:
        print(f"\nRole distribution:")
        for role, count in sorted(roles.items()):
            print(f"  {role}: {count}")

    # Lift order
    print(f"\nLift order (callees first -> callers last):")
    print(f"{'-' * 70}")
    for i, func in enumerate(result.get("functions", []), 1):
        name = func.get("function_name", "?")
        has_code = "ok" if func.get("has_decompiled") else "NO CODE"
        has_asm = "asm" if func.get("has_assembly") else "no-asm"
        role = func.get("role", "")
        role_str = f"  [{role}]" if role else ""
        code_lines = len(func.get("decompiled_code", "").splitlines()) if func.get("decompiled_code") else 0
        asm_lines = len(func.get("assembly_code", "").splitlines()) if func.get("assembly_code") else 0
        print(f"  {i:>3}. [{has_code:>7}] [{has_asm:>6}] {name}{role_str}  ({code_lines}L code, {asm_lines}L asm)")

    # Struct definitions
    structs = result.get("shared_structs", {})
    if structs:
        print(f"\nShared struct definitions ({len(structs)}):")
        for base, sdata in structs.items():
            print(f"\n  {sdata['struct_name']}: {sdata['field_count']} fields")
            print(f"  Sources: {', '.join(sdata['source_functions'][:5])}")

    # Functions without code
    no_code = [f for f in result.get("functions", []) if not f.get("has_decompiled")]
    if no_code:
        print(f"\nWarning: {len(no_code)} function(s) lack decompiled code:")
        for f in no_code:
            print(f"  - {f['function_name']} (ID={f['function_id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract data for ALL methods of a class or function set in one shot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("db_path", help="Path to the module's analysis DB")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--class", dest="class_name",
                           help="Extract all methods of a C++ class")
    mode_group.add_argument("--functions", nargs="+", dest="func_names",
                           help="Extract specific functions by name")
    mode_group.add_argument("--id-list", dest="id_list",
                           help="Comma-separated function IDs")
    mode_group.add_argument("--list-classes", action="store_true",
                           help="List all C++ classes with method counts and lifted status")

    parser.add_argument("--skip-library", action="store_true",
                       help="Skip library-tagged functions (WIL/WRL/STL/CRT/ETW)")
    parser.add_argument("--init-state", action="store_true",
                       help="Initialize shared state file for track_shared_state.py")
    parser.add_argument("--summary", action="store_true",
                       help="Print human-readable summary only (no JSON)")
    parser.add_argument("--json", action="store_true",
                       help="Force JSON output (default when not --summary)")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    if args.list_classes:
        with db_error_handler(db_path, "listing classes"):
            result = list_classes(db_path, skip_library=args.skip_library)
        ws_args = get_workspace_args(args)
        force_json = args.json or bool(ws_args["workspace_dir"])
        if force_json:
            emit_json(result)
        else:
            print_list_classes(result)
        return

    with db_error_handler(db_path, "batch extraction"):
        if args.class_name:
            result = collect_class_methods(db_path, args.class_name)
        elif args.func_names:
            result = collect_by_names(db_path, args.func_names)
        elif args.id_list:
            ids = [validate_function_id(x.strip(), "--id-list") for x in args.id_list.split(",")]
            result = collect_by_ids(db_path, ids)
        else:
            emit_error("Specify --class, --functions, --id-list, or --list-classes", ErrorCode.INVALID_ARGS)
            return

    # Optionally initialize shared state
    if args.init_state:
        class_name = result.get("class_name") or "UnknownClass"
        module_name = result.get("module_name", "")
        dep_order = result.get("dependency_order", [])

        # Build initial struct fields from scan
        init_fields = []
        structs = result.get("shared_structs", {})
        for base, sdata in structs.items():
            if sdata.get("struct_name") == class_name or base in ("a1", "this"):
                init_fields = sdata.get("fields", [])
                break

        func_summaries = [
            {
                "function_id": f["function_id"],
                "function_name": f.get("function_name", ""),
                "role": f.get("role"),
            }
            for f in result.get("functions", [])
        ]

        state = create_initial_state(
            class_name=class_name,
            module_name=module_name,
            db_path=db_path,
            functions=func_summaries,
            dependency_order=dep_order,
            struct_fields=init_fields,
        )
        state_path = save_state(class_name, state)
        print(f"State initialized: {state_path}", file=sys.stderr)

    # Output -- force JSON when workspace mode is active so bootstrap captures
    # structured data; --summary still wins in non-workspace standalone usage.
    ws_args = get_workspace_args(args)
    force_json = (args.json or bool(ws_args["workspace_dir"])) and not args.summary
    if force_json:
        emit_json(result)
    elif args.summary:
        print_text_summary(result)
    else:
        emit_json(result)


if __name__ == "__main__":
    main()
