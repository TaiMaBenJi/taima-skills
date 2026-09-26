#!/usr/bin/env python3
"""Cross-module xref chain analysis: follow function calls across DLL boundaries.

Given a starting function, follows its outbound xrefs across module boundaries,
retrieving decompiled code at each step. This is the primary tool for
understanding execution flow across the analyzed binary set.

Usage:
    python chain_analysis.py <db_path> <function_name> [--depth N]
    python chain_analysis.py <db_path> <function_name> --follow <callee_name>
    python chain_analysis.py <db_path> <function_name> --summary
    python chain_analysis.py <db_path> --id <function_id> [--depth N]

Examples:
    # Show function's code + all resolvable outbound calls (1 level deep)
    python chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess

    # Follow a specific callee across modules (retrieve its code)
    python chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess --follow CreateProcessAsUserW

    # Auto-follow all resolvable calls recursively up to depth 3
    python chain_analysis.py extracted_dbs/cmd_exe_6d109a3a00.db eComSrv --depth 3

    # Summary mode: just show the call tree without code
    python chain_analysis.py extracted_dbs/cmd_exe_6d109a3a00.db eComSrv --depth 3 --summary

Output:
    At each chain step, prints: module, function name, signature, decompiled code,
    and outbound xrefs. For --follow, resolves the callee and prints its code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from _common import (
    WORKSPACE_ROOT,
    emit_error,
    get_function_id,
    load_function_index_for_db,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_db_path,
    search_index,
    validate_function_id,
)
from helpers.errors import ErrorCode, db_error_handler, emit_error, safe_parse_args
from helpers.json_output import emit_json


class ChainAnalyzer:
    """Follow xref chains across module boundaries."""

    def __init__(self, tracking_db: Optional[str] = None):
        tracking = tracking_db
        if not tracking:
            candidate = WORKSPACE_ROOT / "extracted_dbs" / "analyzed_files.db"
            if candidate.exists():
                tracking = str(candidate)
        self._tracking_db = tracking
        # Cache: module_name (lowercase) -> (db_path, file_name)
        self._module_cache: dict[str, tuple[str, str]] = {}
        self._loaded = False
        # Track visited functions to avoid cycles: set of (db_path, function_name)
        self._visited: set[tuple[str, str]] = set()

    def _ensure_modules_loaded(self):
        if self._loaded:
            return
        if not self._tracking_db:
            return
        with db_error_handler(self._tracking_db, "loading module tracking data"):
            with open_analyzed_files_db(self._tracking_db) as db:
                # analysis_db_path is relative to the tracking DB's directory
                tracking_dir = db.db_path.parent
                records = db.get_complete()
        for r in records:
            if r.file_name and r.analysis_db_path:
                key = r.file_name.lower()
                abs_path = tracking_dir / r.analysis_db_path
                if abs_path.exists():
                    self._module_cache[key] = (str(abs_path), r.file_name)
        self._loaded = True

    def get_module_db(self, module_name: str) -> Optional[tuple[str, str]]:
        """Return (db_path, file_name) for a module."""
        self._ensure_modules_loaded()
        return self._module_cache.get(module_name.lower())

    def get_function(self, db_path: str, function_name: str = None,
                     function_id: int = None) -> Optional[dict]:
        """Get a function's full data from a module DB."""
        function_index = load_function_index_for_db(db_path)
        with db_error_handler(db_path, "loading function for chain analysis"), \
                open_individual_analysis_db(db_path) as db:
            func = None
            if function_id is not None:
                func = db.get_function_by_id(function_id)
            elif function_name:
                if function_index:
                    entry = function_index.get(function_name)
                    if entry is None:
                        matches = search_index(function_index, function_name)
                        if matches:
                            _, entry = next(iter(matches.items()))
                    if entry is not None:
                        resolved_id = get_function_id(entry)
                        if resolved_id is not None:
                            func = db.get_function_by_id(resolved_id)
                if not func:
                    results = db.get_function_by_name(function_name)
                    if not results:
                        results = db.search_functions(name_contains=function_name)
                    if results:
                        func = results[0]

            if not func:
                return None

            file_info = db.get_file_info()
            module_name = file_info.file_name if file_info else Path(db_path).stem

        outbound = parse_json_safe(func.simple_outbound_xrefs)
        inbound = parse_json_safe(func.simple_inbound_xrefs)

        return {
            "function_id": func.function_id,
            "function_name": func.function_name,
            "function_signature": func.function_signature,
            "function_signature_extended": func.function_signature_extended,
            "mangled_name": func.mangled_name,
            "decompiled_code": func.decompiled_code,
            "module_name": module_name,
            "db_path": db_path,
            "outbound_xrefs": outbound or [],
            "inbound_xrefs": inbound or [],
            "string_literals": parse_json_safe(func.string_literals) or [],
        }

    # Sentinel module_name values that are NOT real DLL names
    _DATA_MODULES = {"data"}
    _VTABLE_MODULES = {"vtable"}
    _NON_DLL_MODULES = _DATA_MODULES | _VTABLE_MODULES

    def classify_xrefs(self, xrefs: list[dict], source_db: str) -> dict:
        """Classify outbound xrefs into categories.

        Returns dict with keys:
          internal     - same-module function calls (function_id is set)
          resolvable   - cross-module calls where we have the target module's DB
          unresolvable - cross-module calls where the target module is not analyzed
          data_refs    - data/global variable references (module_name="data", function_type=4)
          vtable_refs  - vtable dispatch references (module_name="vtable", function_type=8)
        """
        internal = []
        resolvable = []
        unresolvable = []
        data_refs = []
        vtable_refs = []

        for xref in xrefs:
            if not isinstance(xref, dict):
                continue
            callee = xref.get("function_name", "?")
            callee_id = xref.get("function_id")
            module = xref.get("module_name", "")
            ftype = xref.get("function_type", 0)

            entry = {
                "function_name": callee,
                "module_name": module,
                "function_type": ftype,
            }

            # Data references (globals, string offsets) -- not function calls
            if module in self._DATA_MODULES or ftype == 4:
                data_refs.append(entry)
                continue

            # VTable dispatch references -- indirect calls, can't follow directly
            if module in self._VTABLE_MODULES or ftype == 8:
                vtable_refs.append(entry)
                continue

            if callee_id is not None:
                entry["function_id"] = callee_id
                entry["db_path"] = source_db
                internal.append(entry)
            else:
                mod_info = self.get_module_db(module)
                if mod_info:
                    entry["db_path"] = mod_info[0]
                    entry["resolved_module"] = mod_info[1]
                    resolvable.append(entry)
                else:
                    unresolvable.append(entry)

        return {
            "internal": internal, "resolvable": resolvable,
            "unresolvable": unresolvable,
            "data_refs": data_refs, "vtable_refs": vtable_refs,
        }

    def print_function_data(self, func_data: dict, depth: int = 0, show_code: bool = True) -> None:
        """Print function information at a given chain depth."""
        indent = "  " * depth
        prefix = f"[Depth {depth}]" if depth > 0 else "[Start]"

        print(f"\n{indent}{'=' * (80 - len(indent))}")
        print(f"{indent}{prefix} {func_data['function_name']}  ({func_data['module_name']})")
        print(f"{indent}{'=' * (80 - len(indent))}")

        if func_data.get("function_signature"):
            print(f"{indent}Signature: {func_data['function_signature']}")
        if func_data.get("function_signature_extended"):
            ext = func_data["function_signature_extended"]
            if ext != func_data.get("function_signature"):
                print(f"{indent}Extended:  {ext}")
        print(f"{indent}DB: {Path(func_data['db_path']).name}")
        print(f"{indent}ID: {func_data['function_id']}")

        if show_code and func_data.get("decompiled_code"):
            code = func_data["decompiled_code"]
            lines = code.splitlines()
            print(f"\n{indent}--- Decompiled Code ({len(lines)} lines) ---")
            for line in lines:
                print(f"{indent}{line}")
            print(f"{indent}--- End Code ---")
        elif show_code:
            print(f"\n{indent}(no decompiled code available)")

        # Classify and display xrefs
        classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])

        if classified["internal"]:
            print(f"\n{indent}Internal calls ({len(classified['internal'])}):")
            for x in sorted(classified["internal"], key=lambda e: e["function_name"]):
                print(f"{indent}  -> {x['function_name']}  [ID={x['function_id']}]")

        if classified["resolvable"]:
            print(f"\n{indent}External calls - RESOLVABLE ({len(classified['resolvable'])}):")
            for x in sorted(classified["resolvable"], key=lambda e: e["function_name"]):
                print(f"{indent}  -> {x['function_name']}  [{x['module_name']}]  (DB: {Path(x['db_path']).name})")

        if classified["unresolvable"]:
            print(f"\n{indent}External calls - not analyzed ({len(classified['unresolvable'])}):")
            for x in sorted(classified["unresolvable"], key=lambda e: e["function_name"]):
                print(f"{indent}  -> {x['function_name']}  [{x['module_name']}]")

        if classified["vtable_refs"]:
            print(f"\n{indent}VTable dispatch refs ({len(classified['vtable_refs'])}):")
            for x in sorted(classified["vtable_refs"], key=lambda e: e["function_name"]):
                print(f"{indent}  ~> {x['function_name']}")

        if classified["data_refs"]:
            # Compact summary -- data refs are globals/strings, not calls to follow
            print(f"\n{indent}Data/global refs ({len(classified['data_refs'])} items, not function calls)")

    def follow_chain(self, db_path: str, function_name: str = None,
                     function_id: int = None, max_depth: int = 1,
                     show_code: bool = True, current_depth: int = 0,
                     follow_filter: Optional[str] = None) -> None:
        """Recursively follow call chains across module boundaries."""
        func_data = self.get_function(db_path, function_name=function_name, function_id=function_id)
        if not func_data:
            indent = "  " * current_depth
            target = function_name or f"ID={function_id}"
            print(f"\n{indent}[NOT FOUND] {target} in {Path(db_path).name}")
            return

        # Use resolved function name for cycle detection
        resolved_name = func_data["function_name"]
        visit_key = (db_path, resolved_name)
        if visit_key in self._visited:
            indent = "  " * current_depth
            print(f"\n{indent}[CYCLE] Already visited {resolved_name} - skipping")
            return
        self._visited.add(visit_key)

        self.print_function_data(func_data, depth=current_depth, show_code=show_code)

        if current_depth >= max_depth:
            return

        classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])

        # Follow internal calls
        for xref in classified["internal"]:
            callee_name = xref["function_name"]
            if follow_filter and follow_filter.lower() not in callee_name.lower():
                continue
            self.follow_chain(
                db_path=xref["db_path"],
                function_id=xref["function_id"],
                max_depth=max_depth,
                show_code=show_code,
                current_depth=current_depth + 1,
                follow_filter=follow_filter,
            )

        # Follow resolvable external calls
        for xref in classified["resolvable"]:
            callee_name = xref["function_name"]
            if follow_filter and follow_filter.lower() not in callee_name.lower():
                continue
            self.follow_chain(
                db_path=xref["db_path"],
                function_name=callee_name,
                max_depth=max_depth,
                show_code=show_code,
                current_depth=current_depth + 1,
                follow_filter=follow_filter,
            )

    def print_summary_tree(self, db_path: str, function_name: str = None,
                           function_id: int = None, max_depth: int = 3,
                           current_depth: int = 0) -> None:
        """Print a compact call tree summary without code."""
        func_data = self.get_function(db_path, function_name=function_name, function_id=function_id)
        if not func_data:
            indent = "  " * current_depth
            target = function_name or f"ID={function_id}"
            print(f"{indent}[NOT FOUND] {target}")
            return

        # Use resolved function name for cycle detection
        resolved_name = func_data["function_name"]
        visit_key = (db_path, resolved_name)
        if visit_key in self._visited:
            indent = "  " * current_depth
            print(f"{indent}[CYCLE] {resolved_name}")
            return
        self._visited.add(visit_key)

        indent = "  " * current_depth
        arrow = "-> " if current_depth > 0 else ""
        fname = func_data["function_name"]
        mod = func_data["module_name"]
        sig = func_data.get("function_signature", "")
        has_code = "code" if func_data.get("decompiled_code") else "no-code"
        print(f"{indent}{arrow}{fname}  ({mod})  [{has_code}]")

        if current_depth >= max_depth:
            classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])
            n_calls = len(classified["internal"]) + len(classified["resolvable"]) + len(classified["unresolvable"])
            n_resolvable = len(classified["internal"]) + len(classified["resolvable"])
            if n_calls > 0:
                print(f"{indent}  ... {n_calls} callees ({n_resolvable} resolvable) - max depth reached")
            return

        classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])

        for xref in sorted(classified["internal"], key=lambda e: e["function_name"]):
            self.print_summary_tree(
                db_path=xref["db_path"],
                function_id=xref["function_id"],
                max_depth=max_depth,
                current_depth=current_depth + 1,
            )

        for xref in sorted(classified["resolvable"], key=lambda e: e["function_name"]):
            self.print_summary_tree(
                db_path=xref["db_path"],
                function_name=xref["function_name"],
                max_depth=max_depth,
                current_depth=current_depth + 1,
            )

        for xref in sorted(classified["unresolvable"], key=lambda e: e["function_name"]):
            next_indent = "  " * (current_depth + 1)
            print(f"{next_indent}-> {xref['function_name']}  ({xref['module_name']})  [not analyzed]")

    def collect_chain_data(self, db_path: str, function_name: str = None,
                           function_id: int = None, max_depth: int = 1,
                           current_depth: int = 0,
                           follow_filter: Optional[str] = None) -> dict:
        """Collect chain data as nested dict instead of printing."""
        func_data = self.get_function(db_path, function_name=function_name, function_id=function_id)
        if not func_data:
            target = function_name or f"ID={function_id}"
            return {"error": "not_found", "code": "NOT_FOUND", "target": target, "db": Path(db_path).name}

        resolved_name = func_data["function_name"]
        visit_key = (db_path, resolved_name)
        if visit_key in self._visited:
            return {"cycle": True, "function_name": resolved_name}
        self._visited.add(visit_key)

        classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])

        node = {
            "function_id": func_data["function_id"],
            "function_name": func_data["function_name"],
            "function_signature": func_data.get("function_signature"),
            "module_name": func_data["module_name"],
            "db_path": func_data["db_path"],
            "depth": current_depth,
            "decompiled_code": func_data.get("decompiled_code"),
            "string_literals": func_data.get("string_literals", []),
            "xrefs": {
                "internal": classified["internal"],
                "resolvable": classified["resolvable"],
                "unresolvable": classified["unresolvable"],
                "data_refs_count": len(classified["data_refs"]),
                "vtable_refs_count": len(classified["vtable_refs"]),
            },
            "children": [],
        }

        if current_depth < max_depth:
            for xref in classified["internal"]:
                callee_name = xref["function_name"]
                if follow_filter and follow_filter.lower() not in callee_name.lower():
                    continue
                child = self.collect_chain_data(
                    db_path=xref["db_path"],
                    function_id=xref["function_id"],
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                    follow_filter=follow_filter,
                )
                node["children"].append(child)

            for xref in classified["resolvable"]:
                callee_name = xref["function_name"]
                if follow_filter and follow_filter.lower() not in callee_name.lower():
                    continue
                child = self.collect_chain_data(
                    db_path=xref["db_path"],
                    function_name=callee_name,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                    follow_filter=follow_filter,
                )
                node["children"].append(child)

        return node

    def collect_summary_data(self, db_path: str, function_name: str = None,
                             function_id: int = None, max_depth: int = 3,
                             current_depth: int = 0) -> dict:
        """Collect summary tree as nested dict instead of printing."""
        func_data = self.get_function(db_path, function_name=function_name, function_id=function_id)
        if not func_data:
            target = function_name or f"ID={function_id}"
            return {"error": "not_found", "code": "NOT_FOUND", "target": target}

        resolved_name = func_data["function_name"]
        visit_key = (db_path, resolved_name)
        if visit_key in self._visited:
            return {"cycle": True, "function_name": resolved_name}
        self._visited.add(visit_key)

        node = {
            "function_name": func_data["function_name"],
            "module_name": func_data["module_name"],
            "has_code": bool(func_data.get("decompiled_code")),
            "depth": current_depth,
            "children": [],
        }

        classified = self.classify_xrefs(func_data["outbound_xrefs"], func_data["db_path"])

        if current_depth >= max_depth:
            n_calls = len(classified["internal"]) + len(classified["resolvable"]) + len(classified["unresolvable"])
            n_resolvable = len(classified["internal"]) + len(classified["resolvable"])
            node["truncated"] = True
            node["total_callees"] = n_calls
            node["resolvable_callees"] = n_resolvable
            return node

        for xref in sorted(classified["internal"], key=lambda e: e["function_name"]):
            child = self.collect_summary_data(
                db_path=xref["db_path"],
                function_id=xref["function_id"],
                max_depth=max_depth,
                current_depth=current_depth + 1,
            )
            node["children"].append(child)

        for xref in sorted(classified["resolvable"], key=lambda e: e["function_name"]):
            child = self.collect_summary_data(
                db_path=xref["db_path"],
                function_name=xref["function_name"],
                max_depth=max_depth,
                current_depth=current_depth + 1,
            )
            node["children"].append(child)

        for xref in sorted(classified["unresolvable"], key=lambda e: e["function_name"]):
            node["children"].append({
                "function_name": xref["function_name"],
                "module_name": xref["module_name"],
                "not_analyzed": True,
            })

        return node


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-module xref chain analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("db_path", help="Path to the starting module's analysis DB")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--function", "--name", dest="function_name", metavar="NAME",
                       help="Starting function name")
    group.add_argument("--id", "--function-id", type=int, dest="function_id", help="Starting function ID")
    parser.add_argument("function_name_pos", nargs="?", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--depth", type=int, default=2, help="Max recursion depth (default: 2)")
    parser.add_argument("--follow", metavar="CALLEE", help="Only follow xrefs matching this name")
    parser.add_argument("--summary", action="store_true", help="Print compact call tree without code")
    parser.add_argument("--no-code", action="store_true", help="Skip printing decompiled code")
    parser.add_argument("--tracking-db", help="Path to analyzed_files.db (auto-detected)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)
    if args.function_name_pos and not args.function_name:
        args.function_name = args.function_name_pos

    if args.function_id is not None:
        args.function_id = validate_function_id(args.function_id)

    db_path = resolve_db_path(args.db_path)
    analyzer = ChainAnalyzer(tracking_db=args.tracking_db)

    if not args.function_name and args.function_id is None:
        emit_error("Provide a function name or --id", ErrorCode.INVALID_ARGS)

    if args.json:
        if args.summary:
            data = analyzer.collect_summary_data(
                db_path=db_path,
                function_name=args.function_name,
                function_id=args.function_id,
                max_depth=args.depth,
            )
        else:
            data = analyzer.collect_chain_data(
                db_path=db_path,
                function_name=args.function_name,
                function_id=args.function_id,
                max_depth=args.depth,
                follow_filter=args.follow,
            )
        if isinstance(data, dict) and "error" in data:
            emit_error(f"{data.get('target', 'item')} not found", ErrorCode.NOT_FOUND)
        else:
            emit_json(data)
    elif args.summary:
        print("Cross-module call tree:\n")
        analyzer.print_summary_tree(
            db_path=db_path,
            function_name=args.function_name,
            function_id=args.function_id,
            max_depth=args.depth,
        )
    else:
        analyzer.follow_chain(
            db_path=db_path,
            function_name=args.function_name,
            function_id=args.function_id,
            max_depth=args.depth,
            show_code=not args.no_code,
            follow_filter=args.follow,
        )


if __name__ == "__main__":
    main()
