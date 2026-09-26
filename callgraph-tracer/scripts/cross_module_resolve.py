#!/usr/bin/env python3
"""Resolve which analyzed module contains a function's implementation.

Maps function names from outbound xrefs to their implementing module DBs by
matching module_name (from xrefs) against file_name in analyzed_files.db.

Usage:
    python cross_module_resolve.py <function_name>
    python cross_module_resolve.py --from-function <db_path> <function_name>
    python cross_module_resolve.py --from-function <db_path> _ --id <function_id>
    python cross_module_resolve.py --resolve-all <db_path> <function_name>
    python cross_module_resolve.py --resolve-all <db_path> _ --id <function_id>

Examples:
    # Find which module implements CreateProcessW
    python cross_module_resolve.py CreateProcessW

    # Show all external calls from a function and resolve their modules
    python cross_module_resolve.py --from-function extracted_dbs/cmd_exe_6d109a3a00.db eComSrv

    # Resolve all outbound xrefs from a function (internal + external)
    python cross_module_resolve.py --resolve-all extracted_dbs/cmd_exe_6d109a3a00.db BatLoop

Output:
    For each resolved function: module name, DB path, and whether the function
    was found in that module's DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from _common import (
    emit_error,
    get_function_id,
    load_function_index_for_db,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_db_path,
    resolve_tracking_db,
    search_index,
)
from helpers.cross_module_graph import ModuleResolver  # shared helper
from helpers.errors import ErrorCode, db_error_handler, emit_error, safe_parse_args
from helpers.json_output import emit_json


def resolve_function_global(function_name: str, tracking_db: Optional[str] = None,
                            as_json: bool = False) -> None:
    """Search all analyzed modules for a function."""
    resolver = ModuleResolver(tracking_db)
    results = resolver.resolve_function(function_name, fuzzy=True)
    if as_json:
        emit_json({
            "query": function_name,
            "found": len(results),
            "results": results,
        })
        return
    if results:
        print(f"Function '{function_name}' found in {len(results)} module(s):\n")
        for r in results:
            dec = "has decompiled" if r.get("has_decompiled") else "no decompiled"
            print(f"  Module: {r['module']}")
            print(f"    DB: {r['db_path']}")
            print(f"    Function ID: {r['function_id']}")
            print(f"    Signature: {r.get('function_signature', '(unknown)')}")
            print(f"    Status: {dec}")
            print()
    else:
        print(f"Function '{function_name}' not found in any analyzed module.")
        print("\nAvailable modules:")
        for fname, dbpath in resolver.list_modules():
            print(f"  {fname}  ->  {Path(dbpath).name}")


def resolve_from_function(db_path: str, function_name: str, tracking_db: Optional[str] = None,
                          as_json: bool = False, function_id: int | None = None) -> None:
    """Show all external calls from a function and resolve their implementing modules."""
    db_path = resolve_db_path(db_path)
    resolver = ModuleResolver(tracking_db)

    with db_error_handler(db_path, "resolving cross-module function"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            module_name = file_info.file_name if file_info else Path(db_path).stem
            function_index = load_function_index_for_db(db_path)
            func = None

            if function_id is not None:
                func = db.get_function_by_id(function_id)
                if not func:
                    emit_error(f"Function ID {function_id} not found in {Path(db_path).name}", ErrorCode.NOT_FOUND)
            else:
                if function_index:
                    entry = function_index.get(function_name)
                    if entry is None:
                        matches = search_index(function_index, function_name)
                        if len(matches) > 1:
                            if as_json:
                                emit_error(f"Multiple matches for '{function_name}'", ErrorCode.AMBIGUOUS)
                            print(f"Multiple matches for '{function_name}':")
                            for name, candidate in sorted(matches.items()):
                                fid = get_function_id(candidate)
                                print(f"  ID {fid if fid is not None else '?'}: {name}")
                            print("Use a more specific name or --id.")
                            return
                        if len(matches) == 1:
                            _, entry = next(iter(matches.items()))
                    if entry is not None:
                        fid = get_function_id(entry)
                        if fid is not None:
                            func = db.get_function_by_id(fid)

                if func is None:
                    results = db.get_function_by_name(function_name)
                    if not results:
                        results = db.search_functions(name_contains=function_name)
                    if not results:
                        emit_error(f"Function '{function_name}' not found in {Path(db_path).name}", ErrorCode.NOT_FOUND)
                    if len(results) > 1:
                        if as_json:
                            emit_error(f"Multiple matches for '{function_name}'", ErrorCode.AMBIGUOUS)
                        print(f"Multiple matches for '{function_name}':")
                        for r in results:
                            print(f"  ID {r.function_id}: {r.function_name}")
                        print("Use a more specific name or --id.")
                        return
                    func = results[0]

    outbound = parse_json_safe(func.simple_outbound_xrefs)

    external = []
    internal = []
    n_data_refs = 0
    n_vtable_refs = 0
    if outbound:
        for xref in outbound:
            if not isinstance(xref, dict):
                continue
            callee = xref.get("function_name", "?")
            callee_id = xref.get("function_id")
            mod = xref.get("module_name", "")
            ftype = xref.get("function_type", 0)

            if mod == "data" or ftype == 4:
                n_data_refs += 1
                continue
            if mod == "vtable" or ftype == 8:
                n_vtable_refs += 1
                continue

            if callee_id is not None:
                internal.append((callee, callee_id, ftype))
            else:
                external.append((callee, mod, ftype))

    if as_json:
        external_resolved = []
        for name, mod, ft in sorted(external):
            resolved = resolver.resolve_xref(mod, name)
            entry = {
                "function_name": name,
                "source_module": mod,
                "function_type": ft,
            }
            if resolved:
                entry["resolved"] = True
                entry["function_id"] = resolved.get("function_id")
                entry["has_decompiled"] = resolved.get("has_decompiled", False)
                if "note" in resolved:
                    entry["note"] = resolved["note"]
            else:
                entry["resolved"] = False
                entry["note"] = f"module '{mod}' not analyzed"
            external_resolved.append(entry)

        emit_json({
            "function": func.function_name,
            "module": module_name,
            "internal_calls": [
                {"function_name": name, "function_id": fid, "function_type": ft}
                for name, fid, ft in sorted(internal)
            ],
            "external_calls": external_resolved,
            "data_refs_count": n_data_refs,
            "vtable_refs_count": n_vtable_refs,
        })
        return

    print(f"External calls from {func.function_name} ({module_name}):\n")

    if not outbound:
        print("  (no outbound xrefs)")
        return

    if internal:
        print(f"Internal calls ({len(internal)}):")
        for name, fid, ft in sorted(internal):
            print(f"  -> {name}  [ID={fid}, type={ft}]")
        print()

    if external:
        print(f"External calls ({len(external)}):")
        print(f"{'Function':<40}  {'Source Module':<20}  {'Resolved':<10}  {'Details'}")
        print(f"{'-' * 40}  {'-' * 20}  {'-' * 10}  {'-' * 40}")
        for name, mod, ft in sorted(external):
            resolved = resolver.resolve_xref(mod, name)
            if resolved:
                if resolved.get("has_decompiled"):
                    status = "YES"
                    detail = f"ID={resolved['function_id']}, has code"
                elif "note" in resolved:
                    status = "DB only"
                    detail = resolved["note"]
                else:
                    status = "partial"
                    detail = f"ID={resolved.get('function_id', '?')}"
            else:
                status = "NO"
                detail = f"module '{mod}' not analyzed"
            print(f"  {name:<40}  {mod:<20}  {status:<10}  {detail}")

    if n_data_refs or n_vtable_refs:
        skipped = []
        if n_data_refs:
            skipped.append(f"{n_data_refs} data/global refs")
        if n_vtable_refs:
            skipped.append(f"{n_vtable_refs} vtable refs")
        print(f"\n  (Filtered out: {', '.join(skipped)} -- not function calls)")


def resolve_all_xrefs(db_path: str, function_name: str, tracking_db: Optional[str] = None,
                      as_json: bool = False, function_id: int | None = None) -> None:
    """Resolve ALL outbound xrefs from a function (both internal and external)."""
    db_path = resolve_db_path(db_path)
    resolver = ModuleResolver(tracking_db)

    with db_error_handler(db_path, "resolving cross-module function"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            module_name = file_info.file_name if file_info else Path(db_path).stem
            function_index = load_function_index_for_db(db_path)
            func = None

            if function_id is not None:
                func = db.get_function_by_id(function_id)
                if not func:
                    emit_error(f"Function ID {function_id} not found in {Path(db_path).name}", ErrorCode.NOT_FOUND)
            else:
                if function_index:
                    entry = function_index.get(function_name)
                    if entry is None:
                        matches = search_index(function_index, function_name)
                        if matches:
                            _, entry = next(iter(matches.items()))
                    if entry is not None:
                        fid = get_function_id(entry)
                        if fid is not None:
                            func = db.get_function_by_id(fid)
                if func is None:
                    results = db.get_function_by_name(function_name)
                    if not results:
                        results = db.search_functions(name_contains=function_name)
                    if not results:
                        emit_error(f"Function '{function_name}' not found", ErrorCode.NOT_FOUND)
                    func = results[0]

    outbound = parse_json_safe(func.simple_outbound_xrefs)

    type_names = {0: "unk", 1: "gen", 2: "lib", 3: "API", 4: "mem", 8: "vtable", 16: "sys"}

    calls = []
    data_refs = []
    if outbound:
        for xref in outbound:
            if not isinstance(xref, dict):
                continue
            mod = xref.get("module_name", "")
            ftype = xref.get("function_type", 0)
            if mod in ("data", "vtable") or ftype in (4, 8):
                data_refs.append(xref)
            else:
                calls.append(xref)

    if as_json:
        resolved_calls = []
        for xref in sorted(calls, key=lambda x: x.get("function_name", "")):
            callee = xref.get("function_name", "?")
            callee_id = xref.get("function_id")
            mod = xref.get("module_name", "")
            ftype = xref.get("function_type", 0)
            entry_data = {
                "function_name": callee,
                "module_name": mod,
                "function_type": ftype,
                "type_label": type_names.get(ftype, str(ftype)),
            }
            if callee_id is not None:
                entry_data["resolution"] = "internal"
                entry_data["function_id"] = callee_id
                entry_data["db"] = Path(db_path).name
            else:
                db_entry = resolver.get_module_db(mod)
                if db_entry:
                    entry_data["resolution"] = "resolvable"
                    entry_data["db"] = Path(db_entry[0]).name
                else:
                    entry_data["resolution"] = "unresolvable"

            resolved_calls.append(entry_data)

        emit_json({
            "function": func.function_name,
            "module": module_name,
            "calls": resolved_calls,
            "data_refs_count": len(data_refs),
        })
        return

    print(f"All outbound xrefs from {func.function_name} ({module_name}):\n")

    if not outbound:
        print("  (no outbound xrefs)")
        return

    print(f"Function calls ({len(calls)}):")
    print(f"{'Function':<40}  {'Module':<20}  {'Type':<8}  {'Resolvable':<10}  {'DB Path'}")
    print(f"{'-' * 40}  {'-' * 20}  {'-' * 8}  {'-' * 10}  {'-' * 50}")

    for xref in sorted(calls, key=lambda x: x.get("function_name", "")):
        callee = xref.get("function_name", "?")
        callee_id = xref.get("function_id")
        mod = xref.get("module_name", "")
        ftype = xref.get("function_type", 0)
        type_str = type_names.get(ftype, str(ftype))

        if callee_id is not None:
            print(f"  {callee:<40}  {module_name:<20}  {type_str:<8}  {'internal':<10}  {Path(db_path).name}")
        else:
            entry = resolver.get_module_db(mod)
            if entry:
                db_p, _ = entry
                print(f"  {callee:<40}  {mod:<20}  {type_str:<8}  {'YES':<10}  {Path(db_p).name}")
            else:
                print(f"  {callee:<40}  {mod:<20}  {type_str:<8}  {'NO':<10}  (not analyzed)")

    if data_refs:
        print(f"\nData/global refs ({len(data_refs)} items, not function calls -- omitted)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve which analyzed module contains a function.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--function", "--name", dest="function_name", metavar="NAME",
                       help="Function name to search globally")
    group.add_argument("--from-function", nargs=2, metavar=("DB_PATH", "FUNC"),
                       help="Show external calls from a function and resolve modules")
    group.add_argument("--resolve-all", nargs=2, metavar=("DB_PATH", "FUNC"),
                       help="Resolve all outbound xrefs from a function")
    parser.add_argument("function_name_pos", nargs="?", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--id", "--function-id", dest="function_id", type=int,
                        help="Function ID (overrides name in --from-function / --resolve-all)")
    parser.add_argument("--tracking-db", help="Path to analyzed_files.db (auto-detected)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)
    if args.function_name_pos and not args.function_name:
        args.function_name = args.function_name_pos

    if args.from_function:
        resolve_from_function(args.from_function[0], args.from_function[1], args.tracking_db,
                              as_json=args.json, function_id=args.function_id)
    elif args.resolve_all:
        resolve_all_xrefs(args.resolve_all[0], args.resolve_all[1], args.tracking_db,
                          as_json=args.json, function_id=args.function_id)
    elif args.function_name:
        resolve_function_global(args.function_name, args.tracking_db, as_json=args.json)
    else:
        emit_error("Provide a function name, --from-function, or --resolve-all", ErrorCode.INVALID_ARGS)


if __name__ == "__main__":
    main()
