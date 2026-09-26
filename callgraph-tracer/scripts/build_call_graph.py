#!/usr/bin/env python3
"""Build and query the call graph for a single module from its analysis DB.

Usage:
    python build_call_graph.py <db_path> --stats
    python build_call_graph.py <db_path> --path <source_func> <target_func>
    python build_call_graph.py <db_path> --reachable <function>
    python build_call_graph.py <db_path> --reachable --id <function_id>
    python build_call_graph.py <db_path> --callers <function>
    python build_call_graph.py <db_path> --callers --id <function_id>
    python build_call_graph.py <db_path> --scc
    python build_call_graph.py <db_path> --leaves
    python build_call_graph.py <db_path> --roots
    python build_call_graph.py <db_path> --neighbors <function>

Examples:
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --stats
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --path DllMain CreateProcessW
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --reachable eComSrv
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --scc
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --leaves --limit 30
    python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --neighbors BatLoop

Output:
    Prints results of the requested graph query. Paths show each hop.
    Reachability shows all reachable functions. SCCs list recursive clusters.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from _common import emit_error, resolve_db_path
from helpers.callgraph import CallGraph
from helpers.errors import ErrorCode, db_error_handler, safe_parse_args
from helpers.json_output import emit_json
from helpers.progress import status_message


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and query call graph from an analysis DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stats", action="store_true", help="Print graph statistics")
    group.add_argument("--path", nargs=2, metavar=("SOURCE", "TARGET"), help="Find path between two functions")
    group.add_argument("--all-paths", nargs=2, metavar=("SOURCE", "TARGET"), help="Find all paths (up to --max-depth)")
    group.add_argument("--reachable", metavar="FUNC", nargs="?", const="__by_id__",
                        help="List all functions reachable from FUNC (use --id instead of name)")
    group.add_argument("--callers", metavar="FUNC", nargs="?", const="__by_id__",
                        help="List all transitive callers of FUNC (use --id instead of name)")
    group.add_argument("--scc", action="store_true", help="Find strongly connected components (recursive clusters)")
    group.add_argument("--leaves", action="store_true", help="Find leaf functions (called but call nothing)")
    group.add_argument("--roots", action="store_true", help="Find root functions (call others but not called)")
    group.add_argument("--neighbors", metavar="FUNC", nargs="?", const="__by_id__",
                        help="Show direct callers and callees of FUNC (use --id instead of name)")
    parser.add_argument("--id", "--function-id", dest="function_id", type=int,
                        help="Resolve function by ID instead of name (for --reachable, --callers, --neighbors)")
    parser.add_argument("--max-depth", type=int, default=10, help="Max depth for reachability/path queries (default: 10)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of results (0 = no limit)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-cache", action="store_true", help="Bypass result cache and recompute from scratch")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)
    status_message(f"Building call graph from {Path(db_path).name}...")
    with db_error_handler(db_path, "building call graph"):
        graph = CallGraph.from_db(db_path, no_cache=args.no_cache)
    status_message(f"Graph built: {len(graph.all_nodes)} nodes, {sum(len(v) for v in graph.outbound.values())} edges")

    def _resolve_func(name_arg: str | None) -> str:
        """Resolve a function by --id or by name argument."""
        if args.function_id is not None:
            resolved = graph.find_function_by_id(args.function_id)
            if not resolved:
                emit_error(f"Function ID {args.function_id} not found in call graph", ErrorCode.NOT_FOUND)
            return resolved
        if not name_arg or name_arg == "__by_id__":
            emit_error("No function name or --id provided", ErrorCode.INVALID_ARGS)
        found = graph.find_function(name_arg)
        if not found:
            emit_error(f"Function '{name_arg}' not found", ErrorCode.NOT_FOUND)
        return found

    if args.stats:
        s = graph.stats()
        if args.json:
            s["recursive_clusters"] = len(graph.strongly_connected_components())
            s["leaf_functions"] = len(graph.leaf_functions())
            s["root_functions"] = len(graph.root_functions())
            emit_json(s)
        else:
            print(f"Module: {s['module']}")
            print(f"Internal functions: {s['internal_functions']}")
            print(f"Total nodes (incl. external targets): {s['total_nodes']}")
            print(f"External targets (imports/APIs): {s['external_targets']}")
            print(f"Total edges: {s['total_edges']}")
            print(f"  Internal edges: {s['internal_edges']}")
            print(f"  External edges: {s['external_edges']}")
            sccs = graph.strongly_connected_components()
            print(f"Recursive clusters (SCCs): {len(sccs)}")
            print(f"Leaf functions: {len(graph.leaf_functions())}")
            print(f"Root functions: {len(graph.root_functions())}")

    elif args.path:
        src = graph.find_function(args.path[0])
        tgt = graph.find_function(args.path[1])
        if not src:
            emit_error(f"Source function '{args.path[0]}' not found", ErrorCode.NOT_FOUND)
        if not tgt:
            emit_error(f"Target function '{args.path[1]}' not found", ErrorCode.NOT_FOUND)
        path = graph.bfs_path(src, tgt)
        if args.json:
            emit_json({
                "source": src,
                "target": tgt,
                "hops": (len(path) - 1) if path else None,
                "path": path or [],
            })
        else:
            if path:
                print(f"Shortest path ({len(path) - 1} hops):\n")
                for i, node in enumerate(path):
                    internal = " [internal]" if node in graph.name_to_id else " [external]"
                    prefix = "  " if i > 0 else ""
                    arrow = "-> " if i > 0 else "   "
                    print(f"{prefix}{arrow}{node}{internal}")
            else:
                print(f"No path found from '{src}' to '{tgt}'.")

    elif args.all_paths:
        src = graph.find_function(args.all_paths[0])
        tgt = graph.find_function(args.all_paths[1])
        if not src or not tgt:
            emit_error("Function not found", ErrorCode.NOT_FOUND)
        paths = graph.all_paths(src, tgt, max_depth=args.max_depth)
        if args.json:
            limit = args.limit if args.limit > 0 else len(paths)
            emit_json({
                "source": src,
                "target": tgt,
                "total_paths": len(paths),
                "paths": [{"hops": len(p) - 1, "path": p} for p in sorted(paths, key=len)[:limit]],
            })
        else:
            if paths:
                paths.sort(key=len)
                limit = args.limit if args.limit > 0 else len(paths)
                print(f"Found {len(paths)} path(s) (showing {min(limit, len(paths))}):\n")
                for i, path in enumerate(paths[:limit]):
                    print(f"Path {i + 1} ({len(path) - 1} hops): {' -> '.join(path)}")
            else:
                print(f"No paths found from '{src}' to '{tgt}' within depth {args.max_depth}.")

    elif args.reachable is not None:
        func = _resolve_func(args.reachable)
        reachable = graph.reachable_from(func, max_depth=args.max_depth)
        items = sorted(reachable.items(), key=lambda x: (x[1], x[0]))
        limit = args.limit if args.limit > 0 else len(items)
        if args.json:
            emit_json({
                "function": func,
                "total": len(items),
                "reachable": [
                    {"name": name, "depth": depth, "type": "internal" if name in graph.name_to_id else "external"}
                    for name, depth in items[:limit]
                ],
            })
        else:
            print(f"Functions reachable from '{func}' ({len(items)} total, showing {min(limit, len(items))}):\n")
            print(f"{'Depth':>5}  {'Function':<60}  {'Type'}")
            print(f"{'-' * 5}  {'-' * 60}  {'-' * 10}")
            for name, depth in items[:limit]:
                ftype = "internal" if name in graph.name_to_id else "external"
                print(f"{depth:>5}  {name:<60}  {ftype}")

    elif args.callers is not None:
        func = _resolve_func(args.callers)
        callers = graph.callers_of(func, max_depth=args.max_depth)
        items = sorted(callers.items(), key=lambda x: (x[1], x[0]))
        limit = args.limit if args.limit > 0 else len(items)
        if args.json:
            emit_json({
                "function": func,
                "total": len(items),
                "callers": [
                    {"name": name, "depth": depth, "type": "internal" if name in graph.name_to_id else "external"}
                    for name, depth in items[:limit]
                ],
            })
        else:
            print(f"Transitive callers of '{func}' ({len(items)} total, showing {min(limit, len(items))}):\n")
            print(f"{'Depth':>5}  {'Function':<60}  {'Type'}")
            print(f"{'-' * 5}  {'-' * 60}  {'-' * 10}")
            for name, depth in items[:limit]:
                ftype = "internal" if name in graph.name_to_id else "external"
                print(f"{depth:>5}  {name:<60}  {ftype}")

    elif args.scc:
        sccs = graph.strongly_connected_components()
        if args.json:
            sccs.sort(key=lambda x: -len(x))
            emit_json({"clusters": sccs})
        else:
            if sccs:
                sccs.sort(key=lambda x: -len(x))
                print(f"Found {len(sccs)} recursive cluster(s):\n")
                for i, scc in enumerate(sccs):
                    print(f"Cluster {i + 1} ({len(scc)} functions):")
                    for name in scc:
                        print(f"  - {name}")
                    print()
            else:
                print("No recursive clusters found (no strongly connected components with >1 node).")

    elif args.leaves:
        leaves = graph.leaf_functions()
        limit = args.limit if args.limit > 0 else len(leaves)
        if args.json:
            emit_json({"functions": leaves[:limit]})
        else:
            print(f"Leaf functions ({len(leaves)} total, showing {min(limit, len(leaves))}):\n")
            for name in leaves[:limit]:
                callers = graph.inbound.get(name, set())
                print(f"  {name}  (called by {len(callers)} function(s))")

    elif args.roots:
        roots = graph.root_functions()
        limit = args.limit if args.limit > 0 else len(roots)
        if args.json:
            emit_json({"functions": roots[:limit]})
        else:
            print(f"Root functions ({len(roots)} total, showing {min(limit, len(roots))}):\n")
            for name in roots[:limit]:
                callees = graph.outbound.get(name, set())
                print(f"  {name}  (calls {len(callees)} function(s))")

    elif args.neighbors is not None:
        func = _resolve_func(args.neighbors)
        callees, callers = graph.neighbors(func)
        if args.json:
            emit_json({
                "function": func,
                "function_id": graph.name_to_id.get(func),
                "callees": sorted(callees),
                "callers": sorted(callers),
            })
        else:
            fid = graph.name_to_id.get(func)
            print(f"Function: {func}" + (f"  (ID: {fid})" if fid else " [external]"))
            print(f"\nCallees ({len(callees)}):")
            for c in sorted(callees):
                ext = ""
                for caller_name, externals in graph.external_calls.items():
                    if caller_name == func:
                        for callee_name, mod in externals:
                            if callee_name == c:
                                ext = f"  [{mod}]"
                                break
                internal = " [internal]" if c in graph.name_to_id else ""
                print(f"  -> {c}{internal}{ext}")
            print(f"\nCallers ({len(callers)}):")
            for c in sorted(callers):
                internal = " [internal]" if c in graph.name_to_id else ""
                print(f"  <- {c}{internal}")


if __name__ == "__main__":
    main()
