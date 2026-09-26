#!/usr/bin/env python3
"""List all class/struct types discovered in a module's analysis database.

Usage:
    python list_types.py <db_path>
    python list_types.py <db_path> --with-vtables
    python list_types.py <db_path> --json

Examples:
    python list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db
    python list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db --with-vtables
    python list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db --json

Output:
    Discovered class/struct types with method counts, constructor/destructor
    indicators, and optional vtable availability.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import WORKSPACE_ROOT, parse_class_from_mangled, parse_json_safe, resolve_db_path

from helpers import open_individual_analysis_db, load_function_index_for_db, filter_by_library
from helpers.errors import db_error_handler, safe_parse_args
from helpers.json_output import emit_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List discovered C++ types in a module analysis database.",
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument("--with-vtables", action="store_true",
                        help="Check for vtable contexts (slower, reads all function data)")
    parser.add_argument("--app-only", action="store_true",
                        help="Exclude library/boilerplate classes (WIL/STL/WRL/CRT/ETW)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    with db_error_handler(db_path, "listing types"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            functions = db.get_all_functions()

    # Build library names set for --app-only filtering
    library_names: set[str] = set()
    if args.app_only:
        function_index = load_function_index_for_db(db_path)
        if function_index:
            library_names = {k for k, v in function_index.items() if v.get("library") is not None}

    # Build class map from mangled names
    classes: dict[str, dict] = defaultdict(lambda: {
        "methods": [], "has_constructor": False, "has_destructor": False,
        "has_vdel_destructor": False, "has_vtable_symbol": False,
        "has_vtable_context": False, "namespaces": [], "function_ids": [],
    })

    for func in functions:
        # Skip library functions when --app-only
        if library_names and (func.function_name or "") in library_names:
            continue

        info = parse_class_from_mangled(func.mangled_name)
        if not info:
            continue

        full_name = info["full_qualified_name"]
        cls = classes[full_name]
        cls["namespaces"] = info["namespaces"]
        cls["function_ids"].append(func.function_id)

        role = info["role"]
        if role == "constructor":
            cls["has_constructor"] = True
            cls["methods"].append(f"(ctor) {info['class_name']}")
        elif role == "destructor":
            cls["has_destructor"] = True
            cls["methods"].append(f"(dtor) ~{info['class_name']}")
        elif role == "vdel_destructor":
            cls["has_vdel_destructor"] = True
            cls["methods"].append(f"(vdel) ~{info['class_name']}")
        elif role == "vftable":
            cls["has_vtable_symbol"] = True
        elif role == "method":
            cls["methods"].append(info["method_name"])

        # Check vtable contexts if requested
        if args.with_vtables:
            vtc = parse_json_safe(func.vtable_contexts)
            if vtc and isinstance(vtc, list) and len(vtc) > 0:
                cls["has_vtable_context"] = True

    if not classes:
        if args.json:
            emit_json({
                "module": file_info.file_name if file_info else "(unknown)",
                "total_classes": 0,
                "classes": [],
            })
        else:
            print("No C++ classes found in this module.")
        return

    sorted_classes = sorted(classes.items(), key=lambda x: len(x[1]["methods"]), reverse=True)

    if args.json:
        output = {
            "module": file_info.file_name if file_info else "(unknown)",
            "total_classes": len(sorted_classes),
            "classes": [],
        }
        for name, data in sorted_classes:
            entry = {
                "class_name": name,
                "method_count": len(data["methods"]),
                "methods": data["methods"],
                "has_constructor": data["has_constructor"],
                "has_destructor": data["has_destructor"],
                "has_vdel_destructor": data["has_vdel_destructor"],
                "has_vtable_symbol": data["has_vtable_symbol"],
                "namespaces": data["namespaces"],
                "function_ids": data["function_ids"],
            }
            if args.with_vtables:
                entry["has_vtable_context"] = data["has_vtable_context"]
            output["classes"].append(entry)
        emit_json(output)
    else:
        module_name = file_info.file_name if file_info else "(unknown)"
        print(f"Module: {module_name}")
        print(f"Total functions: {len(functions)}")
        print(f"C++ classes found: {len(sorted_classes)}\n")

        header = f"{'Class Name':<45} {'Methods':>7}  {'Ctor':>4}  {'Dtor':>4}  {'VDel':>4}  {'VTbl':>4}"
        if args.with_vtables:
            header += f"  {'VCtx':>4}"
        print(header)
        print("-" * len(header))

        for name, data in sorted_classes:
            display = name if len(name) <= 45 else name[:42] + "..."
            line = f"{display:<45} {len(data['methods']):>7}"
            line += f"  {'yes' if data['has_constructor'] else '':>4}"
            line += f"  {'yes' if data['has_destructor'] else '':>4}"
            line += f"  {'yes' if data['has_vdel_destructor'] else '':>4}"
            line += f"  {'yes' if data['has_vtable_symbol'] else '':>4}"
            if args.with_vtables:
                line += f"  {'yes' if data['has_vtable_context'] else '':>4}"
            print(line)

        print(f"\n{len(sorted_classes)} class(es) found.")


if __name__ == "__main__":
    main()
