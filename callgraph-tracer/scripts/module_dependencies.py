#!/usr/bin/env python3
"""Map cross-module dependencies: which modules call into which others.

Builds a dependency graph across all analyzed modules by matching outbound
xrefs (imports) to other analyzed modules' exports/functions.

Usage:
    python module_dependencies.py --overview
    python module_dependencies.py --module <module_name>
    python module_dependencies.py --surface <module_name>
    python module_dependencies.py --shared-functions <module_A> <module_B>

Examples:
    # Show dependency overview for all analyzed modules
    python module_dependencies.py --overview

    # Show what a specific module imports from other analyzed modules
    python module_dependencies.py --module appinfo.dll

    # Show the API surface of a module (exports vs imports)
    python module_dependencies.py --surface appinfo.dll

    # Show functions shared between two modules (A calls into B or vice versa)
    python module_dependencies.py --shared-functions appinfo.dll cmd.exe

Output:
    Module dependency information: what each module imports from and exports to
    other analyzed modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from _common import (
    emit_error,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_tracking_db,
)
from helpers.errors import ErrorCode, db_error_handler, safe_parse_args
from helpers.progress import status_message
from helpers.json_output import emit_json


class ModuleDependencyMapper:
    """Build and query the cross-module dependency graph."""

    def __init__(self, tracking_db: Optional[str] = None):
        self._tracking_db = tracking_db or resolve_tracking_db()
        # module_name (lowercase) -> (db_path, file_name)
        self._modules: dict[str, tuple[str, str]] = {}
        # module -> set of (target_module, function_name) -- imports consumed
        self._imports_from: dict[str, set[tuple[str, str]]] = defaultdict(set)
        # module -> set of exported function names
        self._exports: dict[str, set[str]] = defaultdict(set)
        # module -> total function count
        self._func_counts: dict[str, int] = {}
        self._built = False

    def _load_modules(self):
        with db_error_handler(self._tracking_db or "", "analyzing module dependencies"):
            with open_analyzed_files_db(self._tracking_db) as db:
                tracking_dir = db.db_path.parent
                records = db.get_complete()
            for r in records:
                if r.file_name and r.analysis_db_path:
                    key = r.file_name.lower()
                    abs_path = tracking_dir / r.analysis_db_path
                    if abs_path.exists():
                        self._modules[key] = (str(abs_path), r.file_name)

    def build(self, *, module_filter: set[str] | None = None):
        """Build the dependency graph across modules.

        Parameters
        ----------
        module_filter:
            If given (set of lowercase module keys), only scan these modules.
            Recommended when the workspace has many modules.
        """
        if self._built:
            return
        self._load_modules()

        if module_filter is not None:
            targets = {
                k: v for k, v in self._modules.items() if k in module_filter
            }
        else:
            from helpers.config import get_config_value
            max_scan: int = get_config_value("scale.max_modules_cross_scan", 0)
            targets = self._modules
            if max_scan > 0 and len(targets) > max_scan:
                print(
                    f"  WARNING: {len(targets)} modules exceeds scan limit "
                    f"({max_scan}). Scanning first {max_scan} only. "
                    f"Use --modules to specify a subset.",
                    file=sys.stderr,
                )
                targets = dict(list(targets.items())[:max_scan])

        analyzed_module_names = set(self._modules.keys())

        for mod_key, (db_path, file_name) in targets.items():
            status_message(f"Scanning {file_name}...")
            with db_error_handler(db_path, "analyzing module dependencies"):
                with open_individual_analysis_db(db_path) as db:
                    file_info = db.get_file_info()
                    if file_info and file_info.exports:
                        exports = parse_json_safe(file_info.exports)
                        if exports and isinstance(exports, list):
                            for exp in exports:
                                if isinstance(exp, dict):
                                    name = exp.get("function_name") or exp.get("name")
                                    if name:
                                        self._exports[mod_key].add(name)

                    self._func_counts[mod_key] = db.count_functions()

                    xref_rows = db.get_outbound_xrefs_only()
                    for row in xref_rows:
                        outbound = parse_json_safe(row["simple_outbound_xrefs"])
                        if not outbound:
                            continue
                        for xref in outbound:
                            if not isinstance(xref, dict):
                                continue
                            callee_id = xref.get("function_id")
                            if callee_id is not None:
                                continue
                            callee = xref.get("function_name", "")
                            mod = xref.get("module_name", "")
                            if mod and mod.lower() in analyzed_module_names:
                                self._imports_from[mod_key].add((mod.lower(), callee))

        self._built = True

    def print_overview(self):
        """Print dependency overview for all modules."""
        self.build()

        print(f"Cross-Module Dependency Overview ({len(self._modules)} modules analyzed)\n")
        print(f"{'Module':<30}  {'Functions':>9}  {'Exports':>7}  {'Imports From':>12}  {'Imported By':>11}")
        print(f"{'-' * 30}  {'-' * 9}  {'-' * 7}  {'-' * 12}  {'-' * 11}")

        # Build reverse map: who imports from this module
        imported_by: dict[str, set[str]] = defaultdict(set)
        for mod_key, deps in self._imports_from.items():
            for target_mod, _ in deps:
                imported_by[target_mod].add(mod_key)

        for mod_key in sorted(self._modules.keys()):
            _, file_name = self._modules[mod_key]
            func_count = self._func_counts.get(mod_key, 0)
            export_count = len(self._exports.get(mod_key, set()))
            # Unique modules this one imports from
            import_sources = set(target for target, _ in self._imports_from.get(mod_key, set()))
            import_from_count = len(import_sources)
            imported_by_count = len(imported_by.get(mod_key, set()))

            print(f"  {file_name:<30}  {func_count:>9}  {export_count:>7}  {import_from_count:>12}  {imported_by_count:>11}")

        # Dependency edges
        print(f"\nDependency Edges (A -> B means A imports from B):\n")
        for mod_key in sorted(self._modules.keys()):
            _, file_name = self._modules[mod_key]
            deps = self._imports_from.get(mod_key, set())
            if not deps:
                continue
            # Group by target module
            by_target: dict[str, list[str]] = defaultdict(list)
            for target_mod, func_name in deps:
                target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
                by_target[target_name].append(func_name)

            for target_name, funcs in sorted(by_target.items()):
                print(f"  {file_name} -> {target_name}  ({len(funcs)} functions)")
                for f in sorted(funcs)[:10]:
                    print(f"    - {f}")
                if len(funcs) > 10:
                    print(f"    ... and {len(funcs) - 10} more")

    def print_module_deps(self, module_name: str):
        """Show detailed dependencies for a specific module."""
        self.build()

        key = module_name.lower()
        if key not in self._modules:
            # Try partial match
            matches = [k for k in self._modules if module_name.lower() in k]
            if matches:
                key = matches[0]
            else:
                print(f"Module '{module_name}' not found. Available: {', '.join(m[1] for m in self._modules.values())}")
                return

        _, file_name = self._modules[key]
        print(f"Dependencies for {file_name}\n")

        # What this module imports from analyzed modules
        deps = self._imports_from.get(key, set())
        by_target: dict[str, list[str]] = defaultdict(list)
        for target_mod, func_name in deps:
            target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
            by_target[target_name].append(func_name)

        if by_target:
            print(f"Imports from analyzed modules:")
            for target_name, funcs in sorted(by_target.items()):
                print(f"\n  From {target_name} ({len(funcs)} functions):")
                for f in sorted(funcs):
                    print(f"    - {f}")
        else:
            print("  No imports from other analyzed modules.")

        # Who imports from this module
        print()
        importers: dict[str, list[str]] = defaultdict(list)
        for other_key, other_deps in self._imports_from.items():
            if other_key == key:
                continue
            for target_mod, func_name in other_deps:
                if target_mod == key:
                    other_name = self._modules[other_key][1]
                    importers[other_name].append(func_name)

        if importers:
            print(f"Imported by other modules:")
            for other_name, funcs in sorted(importers.items()):
                print(f"\n  By {other_name} ({len(funcs)} functions):")
                for f in sorted(funcs):
                    print(f"    - {f}")
        else:
            print("  No other analyzed module imports from this one.")

    def print_api_surface(self, module_name: str):
        """Show the API surface of a module: what it exports vs what it consumes."""
        self.build()

        key = module_name.lower()
        if key not in self._modules:
            matches = [k for k in self._modules if module_name.lower() in k]
            if matches:
                key = matches[0]
            else:
                print(f"Module '{module_name}' not found.")
                return

        _, file_name = self._modules[key]
        print(f"API Surface for {file_name}\n")

        # Exports
        exports = self._exports.get(key, set())
        print(f"Exports ({len(exports)} functions):")
        for name in sorted(exports)[:50]:
            print(f"  + {name}")
        if len(exports) > 50:
            print(f"  ... and {len(exports) - 50} more")

        # Unique external functions consumed (from all outbound xrefs)
        deps = self._imports_from.get(key, set())
        consumed: dict[str, set[str]] = defaultdict(set)
        for target_mod, func_name in deps:
            target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
            consumed[target_name].add(func_name)

        print(f"\nConsumed APIs (from analyzed modules):")
        if consumed:
            for target_name, funcs in sorted(consumed.items()):
                print(f"\n  From {target_name}:")
                for f in sorted(funcs)[:30]:
                    print(f"    - {f}")
                if len(funcs) > 30:
                    print(f"    ... and {len(funcs) - 30} more")
        else:
            print("  (none from analyzed modules)")

    def print_shared_functions(self, module_a: str, module_b: str):
        """Show functions shared/called between two modules."""
        self.build()

        key_a = module_a.lower()
        key_b = module_b.lower()
        for key, name in [(key_a, module_a), (key_b, module_b)]:
            if key not in self._modules:
                matches = [k for k in self._modules if name.lower() in k]
                if matches:
                    if key == key_a:
                        key_a = matches[0]
                    else:
                        key_b = matches[0]
                else:
                    print(f"Module '{name}' not found.")
                    return

        name_a = self._modules[key_a][1]
        name_b = self._modules[key_b][1]
        print(f"Cross-module calls between {name_a} and {name_b}\n")

        # A -> B
        a_to_b = set()
        for target_mod, func_name in self._imports_from.get(key_a, set()):
            if target_mod == key_b:
                a_to_b.add(func_name)

        # B -> A
        b_to_a = set()
        for target_mod, func_name in self._imports_from.get(key_b, set()):
            if target_mod == key_a:
                b_to_a.add(func_name)

        if a_to_b:
            print(f"{name_a} -> {name_b} ({len(a_to_b)} functions):")
            for f in sorted(a_to_b):
                print(f"  -> {f}")
        else:
            print(f"{name_a} does not call into {name_b}")

        print()
        if b_to_a:
            print(f"{name_b} -> {name_a} ({len(b_to_a)} functions):")
            for f in sorted(b_to_a):
                print(f"  -> {f}")
        else:
            print(f"{name_b} does not call into {name_a}")

    def get_overview_data(self) -> dict:
        """Return dependency overview as structured data."""
        self.build()
        imported_by: dict[str, set[str]] = defaultdict(set)
        for mod_key, deps in self._imports_from.items():
            for target_mod, _ in deps:
                imported_by[target_mod].add(mod_key)

        modules = []
        for mod_key in sorted(self._modules.keys()):
            _, file_name = self._modules[mod_key]
            func_count = self._func_counts.get(mod_key, 0)
            export_count = len(self._exports.get(mod_key, set()))
            import_sources = set(target for target, _ in self._imports_from.get(mod_key, set()))
            modules.append({
                "name": file_name,
                "functions": func_count,
                "exports": export_count,
                "imports_from_count": len(import_sources),
                "imported_by_count": len(imported_by.get(mod_key, set())),
            })

        edges = []
        for mod_key in sorted(self._modules.keys()):
            _, file_name = self._modules[mod_key]
            deps = self._imports_from.get(mod_key, set())
            if not deps:
                continue
            by_target: dict[str, list[str]] = defaultdict(list)
            for target_mod, func_name in deps:
                target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
                by_target[target_name].append(func_name)
            for target_name, funcs in sorted(by_target.items()):
                edges.append({
                    "source": file_name,
                    "target": target_name,
                    "function_count": len(funcs),
                    "functions": sorted(funcs),
                })

        return {"module_count": len(self._modules), "modules": modules, "edges": edges}

    def get_module_deps_data(self, module_name: str) -> dict:
        """Return module dependencies as structured data."""
        self.build()
        key = module_name.lower()
        if key not in self._modules:
            matches = [k for k in self._modules if module_name.lower() in k]
            if matches:
                key = matches[0]
            else:
                return {"error": "not_found", "code": "NOT_FOUND", "query": module_name,
                        "available": [m[1] for m in self._modules.values()]}

        _, file_name = self._modules[key]

        deps = self._imports_from.get(key, set())
        by_target: dict[str, list[str]] = defaultdict(list)
        for target_mod, func_name in deps:
            target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
            by_target[target_name].append(func_name)
        imports = {name: sorted(funcs) for name, funcs in sorted(by_target.items())}

        importers: dict[str, list[str]] = defaultdict(list)
        for other_key, other_deps in self._imports_from.items():
            if other_key == key:
                continue
            for target_mod, func_name in other_deps:
                if target_mod == key:
                    other_name = self._modules[other_key][1]
                    importers[other_name].append(func_name)
        imported_by = {name: sorted(funcs) for name, funcs in sorted(importers.items())}

        return {"module": file_name, "imports": imports, "imported_by": imported_by}

    def get_api_surface_data(self, module_name: str) -> dict:
        """Return API surface as structured data."""
        self.build()
        key = module_name.lower()
        if key not in self._modules:
            matches = [k for k in self._modules if module_name.lower() in k]
            if matches:
                key = matches[0]
            else:
                return {"error": "not_found", "code": "NOT_FOUND", "query": module_name}

        _, file_name = self._modules[key]
        exports = sorted(self._exports.get(key, set()))

        deps = self._imports_from.get(key, set())
        consumed: dict[str, set[str]] = defaultdict(set)
        for target_mod, func_name in deps:
            target_name = self._modules[target_mod][1] if target_mod in self._modules else target_mod
            consumed[target_name].add(func_name)
        consumed_apis = {name: sorted(funcs) for name, funcs in sorted(consumed.items())}

        return {"module": file_name, "exports": exports, "consumed_apis": consumed_apis}

    def get_shared_functions_data(self, module_a: str, module_b: str) -> dict:
        """Return shared functions data as structured data."""
        self.build()
        key_a = module_a.lower()
        key_b = module_b.lower()
        for key, name in [(key_a, module_a), (key_b, module_b)]:
            if key not in self._modules:
                matches = [k for k in self._modules if name.lower() in k]
                if matches:
                    if key == key_a:
                        key_a = matches[0]
                    else:
                        key_b = matches[0]
                else:
                    return {"error": "not_found", "code": "NOT_FOUND", "query": name}

        name_a = self._modules[key_a][1]
        name_b = self._modules[key_b][1]

        a_to_b = sorted(
            func_name for target_mod, func_name
            in self._imports_from.get(key_a, set()) if target_mod == key_b
        )
        b_to_a = sorted(
            func_name for target_mod, func_name
            in self._imports_from.get(key_b, set()) if target_mod == key_a
        )

        return {"module_a": name_a, "module_b": name_b, "a_to_b": a_to_b, "b_to_a": b_to_a}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map cross-module dependencies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--overview", action="store_true", help="Dependency overview for all modules")
    group.add_argument("--module", metavar="NAME", help="Detailed dependencies for a module")
    group.add_argument("--surface", metavar="NAME", help="API surface of a module (exports vs imports)")
    group.add_argument("--shared-functions", nargs=2, metavar=("MOD_A", "MOD_B"),
                       help="Functions called between two modules")
    parser.add_argument("--tracking-db", help="Path to analyzed_files.db (auto-detected)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    mapper = ModuleDependencyMapper(tracking_db=args.tracking_db)

    if args.json:
        if args.overview:
            data = mapper.get_overview_data()
        elif args.module:
            data = mapper.get_module_deps_data(args.module)
        elif args.surface:
            data = mapper.get_api_surface_data(args.surface)
        elif args.shared_functions:
            data = mapper.get_shared_functions_data(args.shared_functions[0], args.shared_functions[1])
        else:
            data = {}
        if isinstance(data, dict) and "error" in data:
            emit_error(f"{data.get('query', 'item')} not found", ErrorCode.NOT_FOUND)
        emit_json(data)
    else:
        if args.overview:
            mapper.print_overview()
        elif args.module:
            mapper.print_module_deps(args.module)
        elif args.surface:
            mapper.print_api_surface(args.surface)
        elif args.shared_functions:
            mapper.print_shared_functions(args.shared_functions[0], args.shared_functions[1])


if __name__ == "__main__":
    main()
