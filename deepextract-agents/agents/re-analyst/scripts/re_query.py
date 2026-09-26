#!/usr/bin/env python3
"""Unified module query: overview, function lookup, class listing, exports.

Combines identity + classification + key callees + strings + dangerous APIs
in one pass. Replaces the pattern of running extract_function_data.py then
classify_function.py then chain_analysis.py sequentially.

Usage:
    python re_query.py <db_path> --overview
    python re_query.py <db_path> --function <name> --context
    python re_query.py <db_path> --class <ClassName>
    python re_query.py <db_path> --exports --with-classification
    python re_query.py <db_path> --search <pattern>

Examples:
    python re_query.py extracted_dbs/appinfo_dll_e98d25a9e8.db --overview
    python re_query.py extracted_dbs/appinfo_dll_e98d25a9e8.db --function AiCheckSecureApplicationDirectory --context
    python re_query.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor
    python re_query.py extracted_dbs/appinfo_dll_e98d25a9e8.db --exports --with-classification
    python re_query.py extracted_dbs/cmd_exe_6d109a3a00.db --search BatLoop

Output:
    Combined identity + classification + key callees + strings + dangerous
    APIs in one pass. Human-readable by default, --json for structured output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Shared utilities (workspace root, bootstrap, DB resolution, helpers)
# ---------------------------------------------------------------------------
from _common import (  # noqa: E402
    WORKSPACE_ROOT as _WORKSPACE_ROOT,
    emit_error,
    get_classify_function as _get_classify,
    get_function_id,
    load_function_index_for_db,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_db_path as _resolve_db_path,
    resolve_function,
    search_functions_by_pattern,
)
from helpers.errors import ErrorCode, db_error_handler, log_warning, safe_parse_args  # noqa: E402
from helpers.json_output import emit_json, emit_json_list  # noqa: E402
from helpers.script_runner import get_workspace_args  # noqa: E402
from helpers.validation import validate_function_id  # noqa: E402


# ---------------------------------------------------------------------------
# Module overview
# ---------------------------------------------------------------------------
def module_overview(db_path: str, as_json: bool = False) -> None:
    """Print comprehensive module overview."""
    with open_individual_analysis_db(db_path) as db:
        fi = db.get_file_info()
        # Aggregate counts via single SQL query (avoids loading all records)
        stats = db.compute_stats()
        func_count = stats["total_functions"]

        # Lightweight name-only query for class/standalone/unnamed breakdown
        all_names = db.get_function_names()

        # Only load functions with dangerous APIs for detailed stats
        dangerous_funcs_list = db.search_functions(has_dangerous_apis=True)

        from helpers.individual_analysis_db import import_source_dll

        import_rows = db.get_imports()
        import_func_count = len(import_rows)
        import_dlls_all = sorted({
            import_source_dll(row) for row in import_rows if import_source_dll(row)
        })
        import_dll_count = len(import_dlls_all)

    if fi is None:
        emit_error("No file_info record found in database", ErrorCode.NO_DATA)

    # Parse key metadata
    exports = parse_json_safe(fi.exports) or []
    entry_points = parse_json_safe(fi.entry_point) or []
    export_count = len(exports) if isinstance(exports, list) else 0
    entry_count = len(entry_points) if isinstance(entry_points, list) else 0

    # Function statistics from compute_stats()
    with_decompiled = stats["decompiled_count"]
    with_assembly = stats["has_assembly_count"]

    # Class breakdown from lightweight name-only query
    classes: dict[str, list[str]] = defaultdict(list)
    standalone: list[str] = []
    unnamed_count = 0
    for name in all_names:
        if name.startswith("sub_"):
            unnamed_count += 1
        if "::" in name:
            cls_name = name.split("::")[0]
            classes[cls_name].append(name)
        else:
            standalone.append(name)

    # Dangerous API stats (only iterates functions that have dangerous APIs)
    dangerous_funcs = len(dangerous_funcs_list)
    total_dangerous_refs = 0
    for f in dangerous_funcs_list:
        dapis = parse_json_safe(f.dangerous_api_calls) or []
        if isinstance(dapis, list):
            total_dangerous_refs += len(dapis)

    data = {
        "module": {
            "file_name": fi.file_name,
            "file_description": fi.file_description or "",
            "company_name": fi.company_name or "",
            "product_name": fi.product_name or "",
            "file_version": fi.file_version or "",
            "pdb_path": fi.pdb_path or "",
            "md5_hash": fi.md5_hash or "",
            "sha256_hash": fi.sha256_hash or "",
            "file_size_bytes": fi.file_size_bytes,
            "analysis_timestamp": fi.analysis_timestamp or "",
        },
        "counts": {
            "total_functions": func_count,
            "with_decompiled": with_decompiled,
            "with_assembly": with_assembly,
            "unnamed_sub": unnamed_count,
            "classes": len(classes),
            "standalone": len(standalone),
            "exports": export_count,
            "imports_functions": import_func_count,
            "imports_dlls": import_dll_count,
            "entry_points": entry_count,
            "functions_with_dangerous_apis": dangerous_funcs,
            "total_dangerous_api_refs": total_dangerous_refs,
        },
        "top_classes": sorted(
            [{"class": k, "method_count": len(v)} for k, v in classes.items()],
            key=lambda x: -x["method_count"]
        )[:15],
        "import_dlls": import_dlls_all[:30],
    }

    if as_json:
        emit_json(data)
        return

    # Human-readable output
    mi = data["module"]
    ct = data["counts"]
    print(f"{'#' * 80}")
    print(f"  MODULE OVERVIEW")
    print(f"{'#' * 80}")
    print(f"  File:          {mi['file_name']}")
    if mi["file_description"]:
        print(f"  Description:   {mi['file_description']}")
    if mi["company_name"]:
        print(f"  Company:       {mi['company_name']}")
    if mi["product_name"]:
        print(f"  Product:       {mi['product_name']}")
    if mi["file_version"]:
        print(f"  Version:       {mi['file_version']}")
    if mi["pdb_path"]:
        print(f"  PDB:           {mi['pdb_path']}")
    if mi["md5_hash"]:
        print(f"  MD5:           {mi['md5_hash']}")
    if mi["file_size_bytes"]:
        print(f"  Size:          {mi['file_size_bytes']:,} bytes")
    print()
    print(f"  Functions:     {ct['total_functions']} total")
    print(f"    Decompiled:  {ct['with_decompiled']}")
    print(f"    With ASM:    {ct['with_assembly']}")
    print(f"    Unnamed:     {ct['unnamed_sub']} (sub_XXXX)")
    print(f"    Classes:     {ct['classes']} ({sum(len(v) for v in classes.values())} methods)")
    print(f"    Standalone:  {ct['standalone']}")
    print(f"  Exports:       {ct['exports']}")
    print(f"  Imports:       {ct['imports_functions']} functions from {ct['imports_dlls']} DLLs")
    print(f"  Entry Points:  {ct['entry_points']}")
    print(f"  Dangerous API: {ct['functions_with_dangerous_apis']} functions ({ct['total_dangerous_api_refs']} refs)")
    print()

    if data["top_classes"]:
        print(f"  TOP CLASSES (by method count):")
        print(f"  {'Class':<40}  {'Methods':>7}")
        print(f"  {'-' * 40}  {'-' * 7}")
        for c in data["top_classes"]:
            name = c["class"]
            if len(name) > 40:
                name = name[:37] + "..."
            print(f"  {name:<40}  {c['method_count']:>7}")
        print()

    if data["import_dlls"]:
        print(f"  IMPORTED DLLs ({min(30, len(data['import_dlls']))} of {ct['imports_dlls']}):")
        for dll in data["import_dlls"]:
            print(f"    {dll}")
        print()


# ---------------------------------------------------------------------------
# Function with context
# ---------------------------------------------------------------------------
def function_with_context(
    db_path: str,
    function_name: Optional[str] = None,
    function_id: Optional[int] = None,
    as_json: bool = False,
) -> None:
    """Print function data combined with classification and call context."""
    function_index = load_function_index_for_db(db_path)
    with open_individual_analysis_db(db_path) as db:
        func, err = resolve_function(
            db,
            name=function_name,
            function_id=function_id,
            function_index=function_index,
        )
        if err:
            if "Multiple matches" in err:
                emit_error(f"[{Path(db_path).stem}] {err}", ErrorCode.AMBIGUOUS)
            emit_error(f"[{Path(db_path).stem}] {err}", ErrorCode.NOT_FOUND)

        # Also get file_info for module context
        fi = db.get_file_info()

    # Classification (if available)
    classify_func = _get_classify()
    classification = None
    if classify_func:
        try:
            result = classify_func(func)
            classification = result.to_dict()
        except Exception as exc:
            log_warning(f"Classification failed for function: {exc}", ErrorCode.UNKNOWN)

    # Parse xrefs
    outbound = parse_json_safe(func.simple_outbound_xrefs) or []
    inbound = parse_json_safe(func.simple_inbound_xrefs) or []
    strings = parse_json_safe(func.string_literals) or []
    dangerous = parse_json_safe(func.dangerous_api_calls) or []
    loops = parse_json_safe(func.loop_analysis) or {}
    stack = parse_json_safe(func.stack_frame) or {}

    # Classify outbound calls
    outbound_classified = []
    for xref in outbound:
        if not isinstance(xref, dict):
            continue
        ftype = xref.get("function_type", 0)
        if ftype in (4, 8):  # skip data/vtable refs
            continue
        entry = {
            "function_name": xref.get("function_name", "?"),
            "module_name": xref.get("module_name", ""),
            "function_id": xref.get("function_id"),
            "is_internal": xref.get("function_id") is not None,
        }
        outbound_classified.append(entry)

    data = {
        "identity": {
            "function_id": func.function_id,
            "function_name": func.function_name,
            "function_signature": func.function_signature,
            "function_signature_extended": func.function_signature_extended,
            "mangled_name": func.mangled_name,
            "module": fi.file_name if fi else "(unknown)",
        },
        "classification": classification,
        "decompiled_code": func.decompiled_code,
        "assembly_code": func.assembly_code,
        "outbound_calls": outbound_classified,
        "inbound_callers": [
            {
                "function_name": x.get("function_name", "?"),
                "function_id": x.get("function_id"),
            }
            for x in inbound if isinstance(x, dict)
        ],
        "strings": strings if isinstance(strings, list) else [],
        "dangerous_apis": dangerous if isinstance(dangerous, list) else [],
        "loops": loops,
        "stack_frame": stack,
    }

    if as_json:
        emit_json(data)
        return

    # Human-readable
    ident = data["identity"]
    print(f"{'#' * 80}")
    print(f"  FUNCTION: {ident['function_name']}")
    print(f"  Module:   {ident['module']}")
    print(f"  ID:       {ident['function_id']}")
    print(f"{'#' * 80}")

    print(f"\n{'=' * 60}")
    print(f"  SIGNATURES")
    print(f"{'=' * 60}")
    if ident["function_signature"]:
        print(f"  Demangled: {ident['function_signature']}")
    if ident["function_signature_extended"]:
        print(f"  Extended:  {ident['function_signature_extended']}")
    if ident["mangled_name"]:
        print(f"  Mangled:   {ident['mangled_name']}")

    if classification:
        print(f"\n{'=' * 60}")
        print(f"  CLASSIFICATION")
        print(f"{'=' * 60}")
        print(f"  Category:  {classification['primary_category']}")
        if classification.get("secondary_categories"):
            print(f"  Secondary: {', '.join(classification['secondary_categories'])}")
        print(f"  Interest:  {classification['interest_score']}/10")
        if classification.get("signals"):
            for cat, sigs in classification["signals"].items():
                for sig in sigs:
                    print(f"    [{cat}] {sig}")

    if data["dangerous_apis"]:
        print(f"\n{'=' * 60}")
        print(f"  DANGEROUS APIs ({len(data['dangerous_apis'])})")
        print(f"{'=' * 60}")
        for api in data["dangerous_apis"]:
            print(f"  !! {api}")

    if data["strings"]:
        shown = data["strings"][:20]
        print(f"\n{'=' * 60}")
        print(f"  STRINGS ({len(data['strings'])} total, showing {len(shown)})")
        print(f"{'=' * 60}")
        for s in shown:
            display = s if len(s) <= 80 else s[:77] + "..."
            print(f"  \"{display}\"")
        if len(data["strings"]) > 20:
            print(f"  ... and {len(data['strings']) - 20} more")

    if outbound_classified:
        print(f"\n{'=' * 60}")
        print(f"  OUTBOUND CALLS ({len(outbound_classified)})")
        print(f"{'=' * 60}")
        for c in outbound_classified:
            loc = f" ({c['module_name']})" if c["module_name"] else ""
            tag = " [internal]" if c["is_internal"] else " [external]"
            print(f"  -> {c['function_name']}{loc}{tag}")

    if data["inbound_callers"]:
        shown_callers = data["inbound_callers"][:15]
        print(f"\n{'=' * 60}")
        print(f"  INBOUND CALLERS ({len(data['inbound_callers'])} total)")
        print(f"{'=' * 60}")
        for c in shown_callers:
            fid = f" [ID={c['function_id']}]" if c["function_id"] else ""
            print(f"  <- {c['function_name']}{fid}")

    if data["decompiled_code"] and data["decompiled_code"].strip():
        code = data["decompiled_code"]
        lines = code.splitlines()
        print(f"\n{'=' * 60}")
        print(f"  DECOMPILED CODE ({len(lines)} lines)")
        print(f"{'=' * 60}")
        if len(lines) > 100:
            for line in lines[:80]:
                print(line)
            print(f"\n... ({len(lines) - 80} more lines, {len(lines)} total)")
        else:
            print(code)

    if isinstance(data["loops"], dict):
        lcount = data["loops"].get("loop_count", 0)
        if lcount:
            print(f"\n  Loops: {lcount}")


# ---------------------------------------------------------------------------
# Class listing
# ---------------------------------------------------------------------------
def class_listing(db_path: str, class_name: str, as_json: bool = False) -> None:
    """List all methods of a class with optional classification."""
    with open_individual_analysis_db(db_path) as db:
        # Search for methods using ClassName:: prefix
        funcs = db.search_functions(name_contains=f"{class_name}::")
        if not funcs:
            # Try without ::
            funcs = db.search_functions(name_contains=class_name)
            funcs = [f for f in funcs if class_name.lower() in (f.function_name or "").lower()]

        if not funcs:
            emit_error(f"No methods found for class '{class_name}'", ErrorCode.NOT_FOUND)

        fi = db.get_file_info()

    classify_func = _get_classify()
    methods = []
    for f in funcs:
        entry = {
            "function_id": f.function_id,
            "function_name": f.function_name,
            "function_signature": f.function_signature,
            "has_decompiled": bool(f.decompiled_code and f.decompiled_code.strip()),
        }
        if classify_func:
            try:
                result = classify_func(f)
                entry["category"] = result.primary_category
                entry["interest"] = result.interest_score
            except Exception as exc:
                log_warning(f"Classification failed for {f.function_name}: {exc}", ErrorCode.UNKNOWN)
        methods.append(entry)

    data = {
        "class_name": class_name,
        "module": fi.file_name if fi else "(unknown)",
        "method_count": len(methods),
        "methods": methods,
    }

    if as_json:
        emit_json(data)
        return

    print(f"{'#' * 80}")
    print(f"  CLASS: {class_name}")
    print(f"  Module: {data['module']}  |  {data['method_count']} method(s)")
    print(f"{'#' * 80}")
    print()
    print(f"  {'ID':>6}  {'Int':>3}  {'Cat':<22}  {'Dec':>3}  {'Method'}")
    print(f"  {'-' * 6}  {'-' * 3}  {'-' * 22}  {'-' * 3}  {'-' * 40}")
    for m in methods:
        name = m["function_name"] or "(unnamed)"
        # Strip class prefix for readability
        if "::" in name:
            name = name.split("::", 1)[1]
        if len(name) > 40:
            name = name[:37] + "..."
        cat = m.get("category", "?")
        interest = m.get("interest", "?")
        dec = "yes" if m["has_decompiled"] else "no"
        print(f"  {m['function_id']:>6}  {interest:>3}  {cat:<22}  {dec:>3}  {name}")


# ---------------------------------------------------------------------------
# Export listing with classification
# ---------------------------------------------------------------------------
def export_listing(db_path: str, with_classification: bool = False, as_json: bool = False) -> None:
    """List all exports, optionally with classification data."""
    function_index = load_function_index_for_db(db_path)
    with open_individual_analysis_db(db_path) as db:
        fi = db.get_file_info()
        if fi is None:
            emit_error("No file_info record found", ErrorCode.NO_DATA)

        exports = parse_json_safe(fi.exports) or []
        if not exports:
            print("No exports found in this module.")
            return

        # If classification requested, look up each export's function record
        classify_func = _get_classify() if with_classification else None
        export_data = []
        for exp in exports:
            if not isinstance(exp, dict):
                continue
            entry = {
                "function_name": exp.get("function_name", "?"),
                "ordinal": exp.get("ordinal", "?"),
                "is_forwarded": exp.get("is_forwarded", False),
                "forwarded_to": exp.get("forwarded_to"),
            }
            if classify_func:
                fname = exp.get("function_name", "")
                func_record = None
                if function_index:
                    entry_idx = function_index.get(fname)
                    if entry_idx:
                        function_id = get_function_id(entry_idx)
                        if function_id is not None:
                            func_record = db.get_function_by_id(function_id)
                if func_record is None:
                    func_records = db.get_function_by_name(fname)
                    if func_records:
                        func_record = func_records[0]
                if func_record:
                    try:
                        result = classify_func(func_record)
                        entry["category"] = result.primary_category
                        entry["interest"] = result.interest_score
                        entry["dangerous_apis"] = result.dangerous_api_count
                    except Exception as exc:
                        log_warning(f"Classification failed for export {fname}: {exc}", ErrorCode.UNKNOWN)
            export_data.append(entry)

    data = {
        "module": fi.file_name if fi else "(unknown)",
        "export_count": len(export_data),
        "exports": export_data,
    }

    if as_json:
        emit_json(data)
        return

    print(f"{'#' * 80}")
    print(f"  EXPORTS: {data['module']}  ({data['export_count']} exports)")
    print(f"{'#' * 80}")
    print()
    if with_classification:
        print(f"  {'Ord':>5}  {'Int':>3}  {'Dng':>3}  {'Category':<22}  {'Name'}")
        print(f"  {'-' * 5}  {'-' * 3}  {'-' * 3}  {'-' * 22}  {'-' * 40}")
        for e in export_data:
            name = e["function_name"]
            if e.get("is_forwarded") and e.get("forwarded_to"):
                name += f" -> {e['forwarded_to']}"
            if len(name) > 50:
                name = name[:47] + "..."
            cat = e.get("category", "?")
            interest = e.get("interest", "?")
            dng = e.get("dangerous_apis", 0)
            print(f"  {e['ordinal']:>5}  {interest:>3}  {dng:>3}  {cat:<22}  {name}")
    else:
        print(f"  {'Ord':>5}  {'Fwd':>3}  {'Name'}")
        print(f"  {'-' * 5}  {'-' * 3}  {'-' * 50}")
        for e in export_data:
            name = e["function_name"]
            if e.get("is_forwarded") and e.get("forwarded_to"):
                name += f" -> {e['forwarded_to']}"
            if len(name) > 60:
                name = name[:57] + "..."
            fwd = "yes" if e.get("is_forwarded") else ""
            print(f"  {e['ordinal']:>5}  {fwd:>3}  {name}")


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------
def search_functions(db_path: str, pattern: str, as_json: bool = False) -> None:
    """Search for functions matching a name pattern."""
    function_index = load_function_index_for_db(db_path)
    with open_individual_analysis_db(db_path) as db:
        results = search_functions_by_pattern(db, pattern, function_index=function_index)

    if not results:
        if as_json:
            from helpers.errors import emit_error, ErrorCode
            emit_error(f"No functions matching '{pattern}'", ErrorCode.NO_DATA)
        print(f"No functions matching '{pattern}' found.")
        return

    classify_func = _get_classify()
    entries = []
    for f in results:
        entry = {
            "function_id": f.function_id,
            "function_name": f.function_name,
            "function_signature": f.function_signature,
            "has_decompiled": bool(f.decompiled_code and f.decompiled_code.strip()),
        }
        if classify_func:
            try:
                result = classify_func(f)
                entry["category"] = result.primary_category
                entry["interest"] = result.interest_score
            except Exception as exc:
                log_warning(f"Classification failed for {f.function_name}: {exc}", ErrorCode.UNKNOWN)
        entries.append(entry)

    if as_json:
        emit_json_list("matches", entries, extra={"match_count": len(entries)})
        return

    print(f"Found {len(entries)} function(s) matching '{pattern}':\n")
    print(f"  {'ID':>6}  {'Int':>3}  {'Cat':<22}  {'Dec':>3}  {'Name'}")
    print(f"  {'-' * 6}  {'-' * 3}  {'-' * 22}  {'-' * 3}  {'-' * 40}")
    for e in entries:
        name = e["function_name"] or "(unnamed)"
        if len(name) > 40:
            name = name[:37] + "..."
        cat = e.get("category", "?")
        interest = e.get("interest", "?")
        dec = "yes" if e["has_decompiled"] else "no"
        print(f"  {e['function_id']:>6}  {interest:>3}  {cat:<22}  {dec:>3}  {name}")

    print(f"\nUse --function <name> --context for full details, or --id <ID>.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified module/function query for the re-analyst subagent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--overview", action="store_true", help="Module overview (identity, stats, classes)")
    group.add_argument("--function", dest="function_name", help="Look up a specific function")
    group.add_argument("--class", dest="class_name", help="List all methods of a class")
    group.add_argument("--exports", action="store_true", help="List all exports")
    group.add_argument("--search", dest="search_pattern", help="Search for functions by name pattern")

    # Modifiers
    parser.add_argument("--context", action="store_true",
                        help="Include full context (classification, strings, callees) with --function")
    parser.add_argument("--with-classification", action="store_true",
                        help="Include classification data with --exports")
    parser.add_argument("--id", type=int, dest="function_id",
                        help="Look up function by ID (alternative to --function <name>)")

    args = safe_parse_args(parser)

    if args.function_id is not None:
        args.function_id = validate_function_id(args.function_id)

    db_path = _resolve_db_path(args.db_path)

    ws_args = get_workspace_args(args)
    force_json = args.json or bool(ws_args["workspace_dir"])

    with db_error_handler(db_path, "re_query"):
        if args.overview:
            module_overview(db_path, as_json=force_json)
        elif args.function_name or args.function_id:
            function_with_context(
                db_path,
                function_name=args.function_name,
                function_id=args.function_id,
                as_json=force_json,
            )
        elif args.class_name:
            class_listing(db_path, args.class_name, as_json=force_json)
        elif args.exports:
            export_listing(db_path, with_classification=args.with_classification, as_json=force_json)
        elif args.search_pattern:
            search_functions(db_path, args.search_pattern, as_json=force_json)


if __name__ == "__main__":
    main()
