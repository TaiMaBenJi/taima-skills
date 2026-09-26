#!/usr/bin/env python3
"""Generate Mermaid or DOT diagrams of call graph subgraphs.

Usage:
    python generate_diagram.py <db_path> --function <name> [--depth N] [--format mermaid|dot]
    python generate_diagram.py <db_path> --id <function_id> [--depth N] [--format mermaid|dot]
    python generate_diagram.py <db_path> --path <source> <target> [--format mermaid|dot]
    python generate_diagram.py --cross-module [--format mermaid|dot]

Examples:
    # Mermaid diagram of all calls reachable from a function (2 levels)
    python generate_diagram.py extracted_dbs/cmd_exe_6d109a3a00.db --function eComSrv --depth 2

    # DOT diagram of a call path
    python generate_diagram.py extracted_dbs/cmd_exe_6d109a3a00.db --path eComSrv ExitProcess --format dot

    # Mermaid diagram of cross-module dependencies
    python generate_diagram.py --cross-module

Output:
    Prints Mermaid or DOT source to stdout. Pipe to a file or paste into a
    Mermaid-compatible renderer.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from _common import (
    SCRIPT_DIR,
    WORKSPACE_ROOT,
    emit_error,
    get_function_id,
    load_function_index_for_db,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_db_path,
    search_index,
)
from helpers.errors import ErrorCode, db_error_handler, emit_error, safe_parse_args
from helpers.json_output import emit_json


def _sanitize_mermaid_id(name: str) -> str:
    """Create a valid Mermaid node ID from a function name."""
    return name.replace("::", "__").replace(" ", "_").replace("-", "_").replace(".", "_").replace("?", "_q_").replace("@", "_at_").replace("<", "_lt_").replace(">", "_gt_").replace("*", "_ptr_").replace("(", "").replace(")", "").replace(",", "_")


def _sanitize_dot_id(name: str) -> str:
    """Create a valid DOT node ID."""
    return '"' + name.replace('"', '\\"') + '"'


def build_subgraph(db_path: str, start_func: str | None = None, max_depth: int = 2,
                   start_func_id: int | None = None) -> tuple[set[tuple[str, str, str]], set[str], set[str]]:
    """Build a subgraph from a starting function. Returns (edges, internal_nodes, external_nodes).
    edges = set of (source, target, edge_label)
    """
    db_path = resolve_db_path(db_path)
    edges: set[tuple[str, str, str]] = set()
    internal_nodes: set[str] = set()
    external_nodes: set[str] = set()
    visited: set[str] = set()

    with db_error_handler(db_path, "generating diagram"):
        with open_individual_analysis_db(db_path) as db:
            file_info = db.get_file_info()
            module_name = file_info.file_name if file_info else ""
            function_index = load_function_index_for_db(db_path)

            queue = deque()
            start = None
            if start_func_id is not None:
                start = db.get_function_by_id(start_func_id)
                if not start:
                    emit_error(f"Function ID {start_func_id} not found.", ErrorCode.NOT_FOUND)
            else:
                if function_index:
                    entry = function_index.get(start_func)
                    if entry:
                        function_id = get_function_id(entry)
                        if function_id is not None:
                            start = db.get_function_by_id(function_id)
                    if start is None:
                        partial = search_index(function_index, start_func)
                        if len(partial) == 1:
                            _, entry = next(iter(partial.items()))
                            function_id = get_function_id(entry)
                            if function_id is not None:
                                start = db.get_function_by_id(function_id)
                if start is None:
                    results = db.get_function_by_name(start_func)
                    if not results:
                        results = db.search_functions(name_contains=start_func)
                    if not results:
                        emit_error(f"Function '{start_func}' not found.", ErrorCode.NOT_FOUND)
                    start = results[0]
            queue.append((start.function_name, start.function_id, 0))
            internal_nodes.add(start.function_name)

            while queue:
                func_name, func_id, depth = queue.popleft()
                if func_name in visited:
                    continue
                visited.add(func_name)

                func = db.get_function_by_id(func_id) if func_id else None
                if not func:
                    if function_index:
                        entry = function_index.get(func_name)
                        if entry:
                            function_id = get_function_id(entry)
                            if function_id is not None:
                                func = db.get_function_by_id(function_id)
                    if not func:
                        results = db.get_function_by_name(func_name)
                        func = results[0] if results else None
                if not func:
                    continue

                outbound = parse_json_safe(func.simple_outbound_xrefs)
                if not outbound:
                    continue

                for xref in outbound:
                    if not isinstance(xref, dict):
                        continue
                    callee = xref.get("function_name", "")
                    if not callee:
                        continue
                    callee_id = xref.get("function_id")
                    module = xref.get("module_name", "")

                    label = module if module and module.lower() != module_name.lower() else ""
                    edges.add((func_name, callee, label))

                    if callee_id is not None:
                        internal_nodes.add(callee)
                        if depth < max_depth and callee not in visited:
                            queue.append((callee, callee_id, depth + 1))
                    else:
                        external_nodes.add(callee)

    return edges, internal_nodes, external_nodes


def build_path_graph(db_path: str, source: str, target: str) -> tuple[set[tuple[str, str, str]], set[str], set[str], list[str]]:
    """Build a graph showing the shortest path between two functions."""
    db_path = resolve_db_path(db_path)

    from helpers.callgraph import CallGraph

    graph = CallGraph.from_db(db_path)
    src = graph.find_function(source)
    tgt = graph.find_function(target)
    if not src or not tgt:
        emit_error("Cannot find source or target function.", ErrorCode.NOT_FOUND)

    path = graph.bfs_path(src, tgt)
    if not path:
        emit_error(f"No path found from '{src}' to '{tgt}'.", ErrorCode.NO_DATA)

    edges: set[tuple[str, str, str]] = set()
    internal: set[str] = set()
    external: set[str] = set()

    for i in range(len(path) - 1):
        edges.add((path[i], path[i + 1], ""))
        for node in [path[i], path[i + 1]]:
            if node in graph.name_to_id:
                internal.add(node)
            else:
                external.add(node)

    return edges, internal, external, path


def build_cross_module_graph(tracking_db: Optional[str] = None) -> tuple[set[tuple[str, str, str]], dict[str, int]]:
    """Build a graph of module-to-module dependencies."""
    tracking = tracking_db
    if not tracking:
        candidate = WORKSPACE_ROOT / "extracted_dbs" / "analyzed_files.db"
        tracking = str(candidate) if candidate.exists() else None

    modules: dict[str, tuple[str, str]] = {}
    with db_error_handler(tracking or "", "generating diagram"):
        with open_analyzed_files_db(tracking) as db:
            tracking_dir = db.db_path.parent
            records = db.get_complete()
        for r in records:
            if r.file_name and r.analysis_db_path:
                abs_path = tracking_dir / r.analysis_db_path
                if abs_path.exists():
                    modules[r.file_name.lower()] = (str(abs_path), r.file_name)

        edges: set[tuple[str, str, str]] = set()
        func_counts: dict[str, int] = {}
        dep_counts: dict[tuple[str, str], int] = defaultdict(int)

        for mod_key, (db_path, file_name) in modules.items():
            with open_individual_analysis_db(db_path) as db:
                functions = db.get_all_functions()
                func_counts[file_name] = len(functions)
                for func in functions:
                    outbound = parse_json_safe(func.simple_outbound_xrefs)
                    if not outbound:
                        continue
                    for xref in outbound:
                        if not isinstance(xref, dict):
                            continue
                        if xref.get("function_id") is not None:
                            continue
                        mod = xref.get("module_name", "")
                        if mod and mod.lower() in modules and mod.lower() != mod_key:
                            target_name = modules[mod.lower()][1]
                            dep_counts[(file_name, target_name)] += 1

        for (src, tgt), count in dep_counts.items():
            edges.add((src, tgt, f"{count} calls"))

    return edges, func_counts


def emit_mermaid(edges: set[tuple[str, str, str]], internal: set[str], external: set[str],
                 title: str = "", highlight_path: Optional[list[str]] = None) -> str:
    """Generate Mermaid flowchart source."""
    lines = ["graph LR"]
    if title:
        lines[0] = f"---\ntitle: {title}\n---\ngraph LR"

    # Define node styles
    seen_nodes = set()
    path_set = set(highlight_path) if highlight_path else set()

    for src, tgt, label in sorted(edges):
        src_id = _sanitize_mermaid_id(src)
        tgt_id = _sanitize_mermaid_id(tgt)

        # Define nodes with shapes
        if src not in seen_nodes:
            seen_nodes.add(src)
            if src in external:
                lines.append(f"    {src_id}[/{src}/]")
            else:
                lines.append(f"    {src_id}[{src}]")
        if tgt not in seen_nodes:
            seen_nodes.add(tgt)
            if tgt in external:
                lines.append(f"    {tgt_id}[/{tgt}/]")
            else:
                lines.append(f"    {tgt_id}[{tgt}]")

        # Edge
        if label:
            lines.append(f"    {src_id} -->|{label}| {tgt_id}")
        else:
            lines.append(f"    {src_id} --> {tgt_id}")

    # Style classes
    if internal:
        int_ids = " & ".join(_sanitize_mermaid_id(n) for n in sorted(internal) if n in seen_nodes)
        if int_ids:
            lines.append(f"    style {int_ids} fill:#d4edda,stroke:#28a745")
    if external:
        ext_ids = " & ".join(_sanitize_mermaid_id(n) for n in sorted(external) if n in seen_nodes)
        if ext_ids:
            lines.append(f"    style {ext_ids} fill:#fff3cd,stroke:#ffc107")
    if path_set:
        path_ids = " & ".join(_sanitize_mermaid_id(n) for n in highlight_path if n in seen_nodes)
        if path_ids:
            lines.append(f"    style {path_ids} fill:#cce5ff,stroke:#004085,stroke-width:3px")

    return "\n".join(lines)


def emit_dot(edges: set[tuple[str, str, str]], internal: set[str], external: set[str],
             title: str = "") -> str:
    """Generate DOT (Graphviz) source."""
    lines = [f'digraph "{title or "callgraph"}" {{']
    lines.append('    rankdir=LR;')
    lines.append('    node [shape=box, style=filled, fontname="Consolas"];')

    seen_nodes = set()
    for src, tgt, label in sorted(edges):
        for node in [src, tgt]:
            if node not in seen_nodes:
                seen_nodes.add(node)
                color = "#d4edda" if node in internal else "#fff3cd"
                lines.append(f'    {_sanitize_dot_id(node)} [fillcolor="{color}"];')

        edge_label = f' [label="{label}"]' if label else ""
        lines.append(f'    {_sanitize_dot_id(src)} -> {_sanitize_dot_id(tgt)}{edge_label};')

    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Mermaid or DOT diagrams of call graph subgraphs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("db_path", nargs="?", help="Path to the analysis DB (not needed for --cross-module)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--function", metavar="NAME", help="Generate subgraph from a function")
    group.add_argument("--id", "--function-id", dest="function_id", type=int,
                       help="Generate subgraph from a function by ID (preferred after initial lookup)")
    group.add_argument("--path", nargs=2, metavar=("SOURCE", "TARGET"), help="Generate path diagram")
    group.add_argument("--cross-module", action="store_true", help="Generate cross-module dependency diagram")
    parser.add_argument("--depth", type=int, default=2, help="Max depth for subgraph (default: 2)")
    parser.add_argument("--format", choices=["mermaid", "dot"], default="mermaid", help="Output format (default: mermaid)")
    parser.add_argument("--tracking-db", help="Path to analyzed_files.db (auto-detected)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    def _output(diagram: str, edges: set, internal: set, external: set, title: str) -> None:
        if args.json:
            emit_json({
                "status": "ok",
                "format": args.format,
                "title": title,
                "diagram": diagram,
                "edge_count": len(edges),
                "node_count": len(internal) + len(external),
                "internal_nodes": sorted(internal),
                "external_nodes": sorted(external),
            })
        else:
            print(diagram)

    if args.function or args.function_id:
        if not args.db_path:
            emit_error("db_path required for --function / --id", ErrorCode.INVALID_ARGS)
        label = args.function or f"ID={args.function_id}"
        edges, internal, external = build_subgraph(
            args.db_path, start_func=args.function,
            max_depth=args.depth, start_func_id=args.function_id,
        )
        title = f"Call graph from {label} (depth={args.depth})"
        diagram = emit_mermaid(edges, internal, external, title) if args.format == "mermaid" else emit_dot(edges, internal, external, title)
        _output(diagram, edges, internal, external, title)

    elif args.path:
        if not args.db_path:
            emit_error("db_path required for --path", ErrorCode.INVALID_ARGS)
        edges, internal, external, path = build_path_graph(args.db_path, args.path[0], args.path[1])
        title = f"Path: {args.path[0]} -> {args.path[1]}"
        diagram = emit_mermaid(edges, internal, external, title, highlight_path=path) if args.format == "mermaid" else emit_dot(edges, internal, external, title)
        _output(diagram, edges, internal, external, title)

    elif args.cross_module:
        edges, func_counts = build_cross_module_graph(args.tracking_db)
        title = "Cross-module dependencies"
        all_nodes = set()
        for s, t, _ in edges:
            all_nodes.add(s)
            all_nodes.add(t)
        diagram = emit_mermaid(edges, all_nodes, set(), title) if args.format == "mermaid" else emit_dot(edges, all_nodes, set(), title)
        _output(diagram, edges, all_nodes, set(), title)


if __name__ == "__main__":
    main()
