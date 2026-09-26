#!/usr/bin/env python3
"""Analyze detailed outbound xrefs for indirect calls, jump tables, and confidence.

Uses the rich ``outbound_xrefs`` field (as opposed to ``simple_outbound_xrefs``)
to surface indirect call resolution, jump table dispatch patterns, vtable-based
polymorphic dispatch, and call-confidence scoring.

Usage:
    python analyze_detailed_xrefs.py <db_path>
    python analyze_detailed_xrefs.py <db_path> --function <name>
    python analyze_detailed_xrefs.py <db_path> --id <function_id>
    python analyze_detailed_xrefs.py <db_path> --summary
    python analyze_detailed_xrefs.py <db_path> --json

Output:
    Per-function analysis of indirect calls, jump table targets, vtable dispatch,
    and confidence-weighted call edges.  Module-wide summary in --summary mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from _common import (
    WORKSPACE_ROOT,
    emit_error,
    parse_json_safe,
)

from helpers import (
    load_function_index_for_db,
    open_individual_analysis_db,
    resolve_function,
)
from helpers.cache import get_cached, cache_result
from helpers.db_paths import resolve_db_path
from helpers.errors import ErrorCode, db_error_handler, safe_parse_args
from helpers.json_output import emit_json


# ---------------------------------------------------------------------------
# Xref classification
# ---------------------------------------------------------------------------

def classify_xref(xref: dict) -> dict[str, Any]:
    """Classify a single detailed xref entry and extract key properties."""
    result: dict[str, Any] = {
        "target": xref.get("function_name", xref.get("target_name", "(unknown)")),
        "target_id": xref.get("function_id"),
        "call_type": "direct",
        "confidence": xref.get("call_confidence", 1.0),
        "flags": [],
    }

    if xref.get("is_indirect_call"):
        result["call_type"] = "indirect"
        info = xref.get("indirect_call_info", {})
        if isinstance(info, dict):
            result["indirect_type"] = info.get("call_type", "unknown")
            result["indirect_confidence"] = info.get("confidence", 0.0)
            result["analysis_method"] = info.get("analysis_method", "")
        result["flags"].append("indirect")

    if xref.get("is_jump_table_target"):
        result["call_type"] = "jump_table"
        result["jump_confidence"] = xref.get("jump_table_detection_confidence", 0.0)
        result["flags"].append("jump_table")

    if xref.get("is_vtable_call"):
        result["call_type"] = "vtable"
        vt = xref.get("vtable_info", {})
        if isinstance(vt, dict):
            result["vtable_address"] = vt.get("vtable_address")
            result["method_offset"] = vt.get("method_offset")
            result["vtable_size"] = vt.get("size")
        result["flags"].append("vtable")

    # Validation issues
    warnings = xref.get("validation_warnings", [])
    if warnings:
        result["validation_warnings"] = warnings
        result["flags"].append("has_warnings")

    checks = xref.get("validation_checks", [])
    if checks:
        result["validation_checks"] = checks

    return result


# ---------------------------------------------------------------------------
# Per-function analysis
# ---------------------------------------------------------------------------

def analyze_function_xrefs(func) -> dict[str, Any]:
    """Analyze detailed xrefs for a single function."""
    detailed = parse_json_safe(func.outbound_xrefs) or []
    simple = parse_json_safe(func.simple_outbound_xrefs) or []

    if not isinstance(detailed, list):
        detailed = []
    if not isinstance(simple, list):
        simple = []

    classified = [classify_xref(x) for x in detailed if isinstance(x, dict)]

    # Partition by call type
    direct = [c for c in classified if c["call_type"] == "direct"]
    indirect = [c for c in classified if c["call_type"] == "indirect"]
    vtable = [c for c in classified if c["call_type"] == "vtable"]
    jump_table = [c for c in classified if c["call_type"] == "jump_table"]

    # Low-confidence edges (below 0.8)
    low_confidence = [c for c in classified if c["confidence"] < 0.8]

    return {
        "function_name": func.function_name or f"sub_{func.function_id}",
        "function_id": func.function_id,
        "total_detailed_xrefs": len(detailed),
        "total_simple_xrefs": len(simple),
        "detail_delta": len(detailed) - len(simple),
        "direct_calls": len(direct),
        "indirect_calls": len(indirect),
        "vtable_calls": len(vtable),
        "jump_table_targets": len(jump_table),
        "low_confidence_edges": len(low_confidence),
        "classified_xrefs": classified,
        "indirect_details": indirect,
        "vtable_details": vtable,
        "jump_table_details": jump_table,
        "low_confidence_details": low_confidence,
    }


# ---------------------------------------------------------------------------
# Module-wide summary
# ---------------------------------------------------------------------------

def analyze_module_xrefs(db_path: str, *, no_cache: bool = False) -> dict[str, Any]:
    """Scan all functions for detailed xref intelligence."""
    if not no_cache:
        cached = get_cached(db_path, "detailed_xref_analysis")
        if cached is not None:
            return cached

    with db_error_handler(db_path, "analyzing module xrefs"):
        with open_individual_analysis_db(db_path) as db:
            all_funcs = db.get_all_functions()
            file_info = db.get_file_info()

    module_name = file_info.file_name if file_info else Path(db_path).stem

    total_indirect = 0
    total_vtable = 0
    total_jump_table = 0
    total_low_confidence = 0
    total_detailed = 0
    total_simple = 0
    functions_with_indirect: list[dict] = []
    functions_with_vtable: list[dict] = []
    functions_with_jump_table: list[dict] = []
    indirect_type_counts: Counter = Counter()
    vtable_addresses: set = set()

    for func in all_funcs:
        analysis = analyze_function_xrefs(func)
        total_detailed += analysis["total_detailed_xrefs"]
        total_simple += analysis["total_simple_xrefs"]
        total_indirect += analysis["indirect_calls"]
        total_vtable += analysis["vtable_calls"]
        total_jump_table += analysis["jump_table_targets"]
        total_low_confidence += analysis["low_confidence_edges"]

        if analysis["indirect_calls"] > 0:
            functions_with_indirect.append({
                "function_name": analysis["function_name"],
                "function_id": analysis["function_id"],
                "count": analysis["indirect_calls"],
                "types": [d.get("indirect_type", "unknown") for d in analysis["indirect_details"]],
            })
            for d in analysis["indirect_details"]:
                indirect_type_counts[d.get("indirect_type", "unknown")] += 1

        if analysis["vtable_calls"] > 0:
            functions_with_vtable.append({
                "function_name": analysis["function_name"],
                "function_id": analysis["function_id"],
                "count": analysis["vtable_calls"],
            })
            for d in analysis["vtable_details"]:
                addr = d.get("vtable_address")
                if addr is not None:
                    vtable_addresses.add(addr)

        if analysis["jump_table_targets"] > 0:
            functions_with_jump_table.append({
                "function_name": analysis["function_name"],
                "function_id": analysis["function_id"],
                "count": analysis["jump_table_targets"],
            })

    result = {
        "module_name": module_name,
        "total_functions_scanned": len(all_funcs),
        "total_detailed_xrefs": total_detailed,
        "total_simple_xrefs": total_simple,
        "detail_delta": total_detailed - total_simple,
        "summary": {
            "indirect_calls": total_indirect,
            "vtable_calls": total_vtable,
            "jump_table_targets": total_jump_table,
            "low_confidence_edges": total_low_confidence,
            "unique_vtable_addresses": len(vtable_addresses),
        },
        "indirect_type_distribution": dict(indirect_type_counts.most_common()),
        "functions_with_indirect_calls": sorted(
            functions_with_indirect, key=lambda x: x["count"], reverse=True,
        )[:50],
        "functions_with_vtable_calls": sorted(
            functions_with_vtable, key=lambda x: x["count"], reverse=True,
        )[:50],
        "functions_with_jump_tables": sorted(
            functions_with_jump_table, key=lambda x: x["count"], reverse=True,
        )[:50],
    }

    cache_result(db_path, "detailed_xref_analysis", result)
    return result


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def print_function_analysis(analysis: dict, as_json: bool = False) -> None:
    """Print per-function detailed xref analysis."""
    if as_json:
        emit_json(analysis, default=str)
        return

    fname = analysis["function_name"]
    print(f"\n{'=' * 70}")
    print(f"  Detailed Xref Analysis: {fname} (ID {analysis['function_id']})")
    print(f"{'=' * 70}")
    print(f"  Total detailed xrefs: {analysis['total_detailed_xrefs']}")
    print(f"  Total simple xrefs:   {analysis['total_simple_xrefs']}")
    print(f"  Delta:                 {analysis['detail_delta']:+d}")
    print(f"  Direct calls:          {analysis['direct_calls']}")
    print(f"  Indirect calls:        {analysis['indirect_calls']}")
    print(f"  Vtable calls:          {analysis['vtable_calls']}")
    print(f"  Jump table targets:    {analysis['jump_table_targets']}")
    print(f"  Low confidence edges:  {analysis['low_confidence_edges']}")

    if analysis["indirect_details"]:
        print(f"\n  Indirect Calls:")
        for d in analysis["indirect_details"]:
            itype = d.get("indirect_type", "unknown")
            conf = d.get("indirect_confidence", 0)
            print(f"    -> {d['target']}  type={itype}  confidence={conf:.2f}")

    if analysis["vtable_details"]:
        print(f"\n  Vtable Dispatch Calls:")
        for d in analysis["vtable_details"]:
            addr = d.get("vtable_address", "?")
            offset = d.get("method_offset", "?")
            print(f"    -> {d['target']}  vtable={addr}  offset={offset}")

    if analysis["jump_table_details"]:
        print(f"\n  Jump Table Targets:")
        for d in analysis["jump_table_details"]:
            conf = d.get("jump_confidence", 0)
            print(f"    -> {d['target']}  confidence={conf:.2f}")

    if analysis["low_confidence_details"]:
        print(f"\n  Low Confidence Edges:")
        for d in analysis["low_confidence_details"]:
            print(f"    -> {d['target']}  confidence={d['confidence']:.2f}  type={d['call_type']}")


def print_module_summary(summary: dict, as_json: bool = False) -> None:
    """Print module-wide detailed xref summary."""
    if as_json:
        emit_json(summary, default=str)
        return

    print(f"\n{'=' * 70}")
    print(f"  Detailed Xref Analysis: {summary['module_name']}")
    print(f"{'=' * 70}")
    print(f"  Functions scanned:       {summary['total_functions_scanned']}")
    print(f"  Total detailed xrefs:    {summary['total_detailed_xrefs']}")
    print(f"  Total simple xrefs:      {summary['total_simple_xrefs']}")
    print(f"  Detail delta:            {summary['detail_delta']:+d}")
    print()

    s = summary["summary"]
    print(f"  Indirect calls:          {s['indirect_calls']}")
    print(f"  Vtable dispatch calls:   {s['vtable_calls']}")
    print(f"  Jump table targets:      {s['jump_table_targets']}")
    print(f"  Low confidence edges:    {s['low_confidence_edges']}")
    print(f"  Unique vtable addresses: {s['unique_vtable_addresses']}")

    if summary["indirect_type_distribution"]:
        print(f"\n  Indirect Call Type Distribution:")
        for itype, count in summary["indirect_type_distribution"].items():
            print(f"    {itype}: {count}")

    if summary["functions_with_indirect_calls"]:
        print(f"\n  Top Functions with Indirect Calls:")
        for f in summary["functions_with_indirect_calls"][:10]:
            print(f"    {f['count']:>3}x  {f['function_name']} (ID {f['function_id']})")

    if summary["functions_with_vtable_calls"]:
        print(f"\n  Top Functions with Vtable Dispatch:")
        for f in summary["functions_with_vtable_calls"][:10]:
            print(f"    {f['count']:>3}x  {f['function_name']} (ID {f['function_id']})")

    if summary["functions_with_jump_tables"]:
        print(f"\n  Functions with Jump Tables:")
        for f in summary["functions_with_jump_tables"][:10]:
            print(f"    {f['count']:>3}x  {f['function_name']} (ID {f['function_id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze detailed outbound xrefs for indirect calls, jump tables, and confidence.",
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument("--function", dest="function_name", help="Analyze a specific function")
    parser.add_argument("--id", "--function-id", type=int, dest="function_id", help="Function ID")
    parser.add_argument("--summary", action="store_true", help="Module-wide summary")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path, WORKSPACE_ROOT)

    if args.summary or (not args.function_name and args.function_id is None):
        result = analyze_module_xrefs(db_path, no_cache=args.no_cache)
        print_module_summary(result, as_json=args.json)
        return

    function_index = load_function_index_for_db(db_path)
    with db_error_handler(db_path, "resolving function for xref analysis"):
        with open_individual_analysis_db(db_path) as db:
            func, err = resolve_function(
                db, name=args.function_name, function_id=args.function_id,
                function_index=function_index,
            )
            if err:
                emit_error(f"[{Path(db_path).stem}] {err}", ErrorCode.NOT_FOUND)

            analysis = analyze_function_xrefs(func)
            print_function_analysis(analysis, as_json=args.json)


if __name__ == "__main__":
    main()
