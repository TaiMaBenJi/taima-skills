#!/usr/bin/env python3
"""Extract class hierarchy from mangled names and vtable contexts.

Usage:
    python extract_class_hierarchy.py <db_path>
    python extract_class_hierarchy.py <db_path> --class <ClassName>
    python extract_class_hierarchy.py <db_path> --json

Examples:
    python extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db
    python extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor
    python extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db --json

Output:
    Class hierarchy: constructors, destructors, virtual/non-virtual methods,
    vtable skeleton strings, and namespace structure.
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

from helpers import open_individual_analysis_db, load_function_index_for_db
from helpers.errors import db_error_handler, safe_parse_args
from helpers.json_output import emit_json


def extract_hierarchy(db_path: str, class_filter: str | None = None, app_only: bool = False) -> dict:
    """Extract full class hierarchy from the database.

    Returns dict with 'module' and 'classes' keys.
    """
    with db_error_handler(db_path, "extracting class hierarchy"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            functions = db.get_all_functions()

    # Build library names set for --app-only filtering
    library_names: set[str] = set()
    if app_only:
        function_index = load_function_index_for_db(db_path)
        if function_index:
            library_names = {k for k, v in function_index.items() if v.get("library") is not None}

    classes: dict[str, dict] = defaultdict(lambda: {
        "class_name": "",
        "namespaces": [],
        "constructors": [],
        "destructors": [],
        "methods": [],
        "virtual_methods": [],
        "vtable_skeletons": [],
        "function_ids": [],
    })

    for func in functions:
        # Skip library functions when --app-only
        if library_names and (func.function_name or "") in library_names:
            continue

        info = parse_class_from_mangled(func.mangled_name)
        if not info:
            continue

        full_name = info["full_qualified_name"]

        # Apply filter if specified
        if class_filter and class_filter.lower() not in full_name.lower():
            continue

        cls = classes[full_name]
        cls["class_name"] = info["class_name"]
        cls["namespaces"] = info["namespaces"]
        cls["function_ids"].append(func.function_id)

        entry = {
            "name": info.get("method_name", info["class_name"]),
            "function_id": func.function_id,
            "signature": func.function_signature,
            "signature_extended": func.function_signature_extended,
            "mangled": func.mangled_name,
        }

        role = info["role"]
        if role == "constructor":
            cls["constructors"].append(entry)
        elif role in ("destructor", "vdel_destructor"):
            entry["role"] = role
            cls["destructors"].append(entry)
        elif role == "vftable":
            pass  # vtable symbol, not a method
        elif role == "method":
            access = info.get("access", "unknown")
            entry["access"] = access
            if access == "public_virtual":
                cls["virtual_methods"].append(entry)
            cls["methods"].append(entry)

        # Extract vtable context skeletons
        vtc = parse_json_safe(func.vtable_contexts)
        if vtc and isinstance(vtc, list):
            for ctx in vtc:
                if isinstance(ctx, dict):
                    for skel in ctx.get("reconstructed_classes", []):
                        if skel and skel not in cls["vtable_skeletons"]:
                            cls["vtable_skeletons"].append(skel)

    return {
        "module": file_info.file_name if file_info else "(unknown)",
        "total_classes": len(classes),
        "classes": dict(classes),
    }


def _print_hierarchy(result: dict) -> None:
    """Print hierarchy in human-readable format."""
    print(f"Module: {result['module']}")
    print(f"Classes: {result['total_classes']}\n")

    for full_name in sorted(result["classes"]):
        cls = result["classes"][full_name]
        ns = "::".join(cls["namespaces"]) + "::" if cls["namespaces"] else ""
        print(f"{'=' * 70}")
        print(f"class {ns}{cls['class_name']}  ({len(cls['function_ids'])} functions)")
        print(f"{'=' * 70}")

        if cls["constructors"]:
            print(f"\n  Constructors ({len(cls['constructors'])}):")
            for c in cls["constructors"]:
                sig = c.get("signature_extended") or c.get("signature") or ""
                print(f"    [{c['function_id']}] {sig}")

        if cls["destructors"]:
            print(f"\n  Destructors ({len(cls['destructors'])}):")
            for d in cls["destructors"]:
                sig = d.get("signature_extended") or d.get("signature") or ""
                role_tag = f" ({d['role']})" if d.get("role") == "vdel_destructor" else ""
                print(f"    [{d['function_id']}] {sig}{role_tag}")

        if cls["virtual_methods"]:
            print(f"\n  Virtual Methods ({len(cls['virtual_methods'])}):")
            for m in cls["virtual_methods"]:
                sig = m.get("signature", "")
                if len(sig) > 65:
                    sig = sig[:62] + "..."
                print(f"    [{m['function_id']}] {m['name']} -- {sig}")

        non_virtual = [m for m in cls["methods"] if m.get("access") != "public_virtual"]
        if non_virtual:
            print(f"\n  Other Methods ({len(non_virtual)}):")
            for m in non_virtual[:25]:
                sig = m.get("signature", "")
                if len(sig) > 65:
                    sig = sig[:62] + "..."
                print(f"    [{m['function_id']}] {m['name']} -- {sig}")
            if len(non_virtual) > 25:
                print(f"    ... {len(non_virtual) - 25} more")

        if cls["vtable_skeletons"]:
            print(f"\n  VTable Skeletons ({len(cls['vtable_skeletons'])}):")
            for skel in cls["vtable_skeletons"][:5]:
                lines = str(skel).split("\n") if isinstance(skel, str) else [str(skel)]
                for line in lines[:12]:
                    print(f"    {line}")
                if len(lines) > 12:
                    print(f"    ... ({len(lines)} lines total)")
            if len(cls["vtable_skeletons"]) > 5:
                print(f"    ... {len(cls['vtable_skeletons']) - 5} more skeletons")

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract class hierarchy from mangled names and vtable contexts.",
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument("--class", dest="class_filter",
                        help="Filter by class name (case-insensitive substring)")
    parser.add_argument("--app-only", action="store_true",
                        help="Exclude library/boilerplate classes (WIL/STL/WRL/CRT/ETW)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)
    result = extract_hierarchy(db_path, args.class_filter, app_only=args.app_only)

    if args.json:
        emit_json(result, default=str)
    else:
        _print_hierarchy(result)


if __name__ == "__main__":
    main()
