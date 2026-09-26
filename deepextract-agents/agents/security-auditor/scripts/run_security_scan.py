#!/usr/bin/env python3
"""Run a multi-phase security scan pipeline and produce a unified findings report.

This is the security-auditor's main entry script. It orchestrates existing
skill scripts to perform a comprehensive security assessment of a module.

Usage:
    python run_security_scan.py <db_path> --goal scan
    python run_security_scan.py <db_path> --goal audit --function <name>
    python run_security_scan.py <db_path> --goal hunt --top 15
    python run_security_scan.py <db_path> --goal scan --json

Goals:
    scan:   full 4-phase vulnerability scan (default)
    audit:  targeted audit on a specific function
    hunt:   hypothesis-driven scan on top entry points

Output:
    Structured JSON with per-phase summaries, merged findings, and
    workspace file references.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
_AGENTS_ROOT = _SCRIPT_DIR.parent.parent
if str(_AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_ROOT))

from _common import (
    WORKSPACE_ROOT,
    Finding,
    ProgressReporter,
    create_run_dir,
    deduplicate,
    findings_summary,
    merge_findings,
    read_results,
    rank,
    resolve_db_path,
    run_skill_script,
    status_message,
    to_json,
)
from _shared.pipeline_helpers import (
    adaptive_top_n,
    extract_top_entrypoints,
    with_flag,
)
from helpers.config import get_config_value
from helpers.errors import ErrorCode, emit_error, safe_parse_args
from helpers.json_output import emit_json
from helpers.findings_store import upsert_finding


# ---------------------------------------------------------------------------
# Step-name to finding-type mapping
# ---------------------------------------------------------------------------
_STEP_FINDING_TYPE: dict[str, str] = {
    "taint_forward": "taint",
    "taint_backward": "taint",
    "taint_cross": "taint",
    "mem_findings": "memory_corruption",
    "logic_findings": "logic_vulnerability",
}


def _get_finding_type(step_name: str) -> str | None:
    """Resolve step name to finding type with prefix matching for taint steps."""
    exact = _STEP_FINDING_TYPE.get(step_name)
    if exact:
        return exact
    if step_name.startswith("taint_"):
        return "taint"
    return None


# ---------------------------------------------------------------------------
# Adaptive timeout
# ---------------------------------------------------------------------------
def _adaptive_timeout(function_count: int) -> int:
    base = int(get_config_value("security_auditor.step_timeout_seconds", 180))
    per_fn = float(get_config_value("security_auditor.per_function_timeout_seconds", 0.2))
    return max(base, int(base + function_count * per_fn))


def _phase_workers(max_workers: int | None, step_count: int, default: int) -> int:
    """Return the worker count for a phase, capped by step count."""
    cap = default if max_workers is None else max(1, max_workers)
    return max(1, min(cap, step_count))


def _should_deepen_scan(findings: list[Finding]) -> bool:
    """Return True if findings warrant deeper re-scan.

    Triggers when:
    - 2+ CRITICAL-severity findings
    - 5+ HIGH-severity findings
    - Top finding score >= 0.75
    """
    if not findings:
        return False
    critical = sum(1 for f in findings if f.severity == "CRITICAL")
    high = sum(1 for f in findings if f.severity == "HIGH")
    top_score = max(f.score for f in findings) if findings else 0.0
    return critical >= 2 or high >= 5 or top_score >= 0.75


# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

def _get_ipc_context(db_path: str) -> dict | None:
    """Gather RPC, COM, and WinRT index context for the module being scanned."""
    from helpers import open_individual_analysis_db
    try:
        with open_individual_analysis_db(db_path) as db:
            fi = db.get_file_info()
            if not fi or not fi.file_name:
                return None
    except Exception:
        return None

    module_name = fi.file_name
    result: dict = {"module_name": module_name}

    # RPC
    try:
        from helpers.rpc_index import get_rpc_index
        idx = get_rpc_index()
        if idx.loaded:
            ifaces = idx.get_interfaces_for_module(module_name)
            if ifaces:
                procs = idx.get_procedures_for_module(module_name)
                result["rpc"] = {
                    "interface_count": len(ifaces),
                    "procedure_count": len(procs),
                    "procedures": procs,
                    "remote_reachable": any(i.is_remote_reachable for i in ifaces),
                    "named_pipe": any(i.is_named_pipe for i in ifaces),
                    "risk_tiers": list({i.risk_tier for i in ifaces}),
                    "interfaces": [i.to_dict() for i in ifaces],
                }
    except Exception:
        pass

    # COM
    try:
        from helpers.com_index import get_com_index
        cidx = get_com_index()
        if cidx.loaded:
            servers = cidx.get_servers_for_module(module_name)
            if servers:
                procs = cidx.get_procedures_for_module(module_name)
                result["com"] = {
                    "server_count": len(servers),
                    "procedure_count": len(procs),
                    "procedures": procs,
                    "can_elevate": any(s.can_elevate for s in servers),
                    "risk_tiers": list({s.risk_tier for s in servers if hasattr(s, "risk_tier") and s.risk_tier}),
                }
    except Exception:
        pass

    # WinRT
    try:
        from helpers.winrt_index import get_winrt_index
        widx = get_winrt_index()
        if widx.loaded:
            servers = widx.get_servers_for_module(module_name)
            if servers:
                procs = widx.get_procedures_for_module(module_name)
                result["winrt"] = {
                    "server_count": len(servers),
                    "procedure_count": len(procs),
                    "procedures": procs,
                    "risk_tiers": list({s.risk_tier for s in servers if hasattr(s, "risk_tier") and s.risk_tier}),
                }
    except Exception:
        pass

    if len(result) <= 1:
        return None
    return result


def _phase_recon(
    db_path: str,
    workspace_dir: str,
    timeout: int,
    *,
    max_workers: int | None = None,
    no_cache: bool = False,
) -> dict:
    """Phase 1: Recon -- classify functions, map attack surface, gather RPC context."""
    results: dict = {}

    ipc_ctx = _get_ipc_context(db_path)
    if ipc_ctx:
        results["ipc_context"] = {"success": True, "json_data": ipc_ctx}
        rpc_ctx = ipc_ctx.get("rpc")
        if rpc_ctx:
            print(f"  [RPC] {rpc_ctx['interface_count']} interfaces, "
                  f"{rpc_ctx['procedure_count']} procedures, "
                  f"risk tiers: {rpc_ctx['risk_tiers']}", file=sys.stderr)
        com_ctx = ipc_ctx.get("com")
        if com_ctx:
            print(f"  [COM] {com_ctx['server_count']} servers, "
                  f"{com_ctx['procedure_count']} procedures"
                  f"{', can elevate' if com_ctx.get('can_elevate') else ''}",
                  file=sys.stderr)
        winrt_ctx = ipc_ctx.get("winrt")
        if winrt_ctx:
            print(f"  [WinRT] {winrt_ctx['server_count']} servers, "
                  f"{winrt_ctx['procedure_count']} procedures",
                  file=sys.stderr)

    steps = [
        ("classify_triage", "classify-functions", "triage_summary.py",
         with_flag([db_path, "--json", "--top", "20"], "--no-cache", no_cache)),
        ("discover_entrypoints", "map-attack-surface", "discover_entrypoints.py",
         with_flag([db_path, "--json"], "--no-cache", no_cache)),
        ("rank_entrypoints", "map-attack-surface", "rank_entrypoints.py",
         [db_path, "--json", "--top", "10"]),
    ]

    with ThreadPoolExecutor(max_workers=_phase_workers(max_workers, len(steps), 3)) as pool:
        future_map = {}
        for step_name, skill, script, args in steps:
            future = pool.submit(
                run_skill_script, skill, script, args,
                timeout=timeout, json_output=True,
                workspace_dir=workspace_dir, workspace_step=step_name,
            )
            future_map[future] = step_name

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                result = future.result()
                results[name] = result
            except Exception as exc:
                status_message(f"[FAIL] {name}: {exc}")
                results[name] = {"success": False, "error": str(exc)}

    return results


def _phase_vuln_scan(
    db_path: str,
    workspace_dir: str,
    timeout: int,
    *,
    max_workers: int | None = None,
    no_cache: bool = False,
) -> dict:
    """Phase 2: Prepare AI scanner contexts (threat models + callgraph data).

    Builds threat models and callgraph context for both the memory-corruption
    scanner and the logic scanner.  The actual LLM-driven scanning happens at
    the command level (the coordinator launches scanner subagents); this phase
    only prepares the workspace artifacts they consume.
    """
    results: dict = {}

    steps: list[tuple[str, str, str, list[str]]] = [
        ("mem_threat_model", "ai-memory-corruption-scanner", "build_threat_model.py",
         [db_path, "--json"]),
        ("mem_context", "ai-memory-corruption-scanner", "prepare_context.py",
         [db_path, "--entry-points", "--with-code", "--json"]),
        ("logic_threat_model", "ai-logic-scanner", "build_threat_model.py",
         [db_path, "--json"]),
        ("logic_context", "ai-logic-scanner", "prepare_context.py",
         [db_path, "--entry-points", "--with-code", "--json"]),
        ("taint_threat_model", "ai-taint-scanner", "build_threat_model.py",
         [db_path, "--json"]),
        ("taint_context", "ai-taint-scanner", "prepare_context.py",
         [db_path, "--entry-points", "--with-code", "--json"]),
    ]

    with ThreadPoolExecutor(max_workers=_phase_workers(max_workers, len(steps), 6)) as pool:
        future_map = {}
        for step_name, skill, script, args in steps:
            future = pool.submit(
                run_skill_script, skill, script, args,
                timeout=timeout, json_output=True,
                workspace_dir=workspace_dir, workspace_step=step_name,
            )
            future_map[future] = step_name

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                result = future.result()
                results[name] = result
            except Exception as exc:
                status_message(f"[WARN] {name}: {exc}")
                results[name] = {"success": False, "error": str(exc)}

    succeeded = [k for k, v in results.items() if isinstance(v, dict) and v.get("success")]
    failed = [k for k, v in results.items() if isinstance(v, dict) and not v.get("success")]
    if succeeded:
        status_message(f"  Scanner context ready: {', '.join(succeeded)}")
    if failed:
        status_message(f"  Scanner context failed: {', '.join(failed)}")

    return results


def _phase_taint(
    db_path: str, workspace_dir: str, timeout: int,
    entrypoints: list[str], function_name: str | None = None,
    *,
    max_workers: int | None = None,
    no_cache: bool = False,
    depth: int = 5,
) -> dict:
    """Phase 3: Per-function taint context preparation for AI taint scanner.

    Builds taint-enriched callgraph context for specific entry points.  The
    actual taint analysis is performed by the taint-scanner LLM agent (launched
    by the coordinator) consuming these workspace artifacts alongside the
    module-level threat model from Phase 2.
    """
    results: dict = {}
    targets = [function_name] if function_name else entrypoints[:5]

    if not targets:
        status_message("[SKIP] No targets for taint context preparation")
        return results

    with ThreadPoolExecutor(max_workers=_phase_workers(max_workers, len(targets), 3)) as pool:
        future_map = {}
        for fname in targets:
            step_name = f"taint_{fname}"
            taint_args = [db_path, "--function", fname, "--depth", str(depth), "--with-code", "--json"]
            future = pool.submit(
                run_skill_script,
                "ai-taint-scanner", "prepare_context.py",
                taint_args,
                timeout=timeout, json_output=True,
                workspace_dir=workspace_dir, workspace_step=step_name,
            )
            future_map[future] = step_name

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                result = future.result()
                results[name] = result
            except Exception as exc:
                status_message(f"[FAIL] {name}: {exc}")
                results[name] = {"success": False, "error": str(exc)}

    return results


def _phase_report(
    all_phase_results: dict,
    workspace_dir: str,
    persist: bool = False,
) -> dict:
    """Phase 4: Merge, deduplicate, and rank all findings into final report."""
    scanner_pairs: list[tuple[dict, str]] = []

    for step_name, result in all_phase_results.items():
        if not isinstance(result, dict) or not result.get("success"):
            continue
        data = result.get("json_data", {})
        if not isinstance(data, dict):
            continue

        finding_type = _get_finding_type(step_name)
        if finding_type:
            scanner_pairs.append((data, finding_type))

    merged = merge_findings(*scanner_pairs) if scanner_pairs else []
    summary = findings_summary(merged)

    report_path = Path(workspace_dir) / "ranked" / "results.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({
            "status": "ok",
            "findings": to_json(merged),
            "summary": summary,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if persist:
        run_id = Path(workspace_dir).name
        for f in merged:
            try:
                upsert_finding(f, run_id=run_id)
            except Exception:
                pass  # Persistence failure must never abort the scan

    return {
        "findings": merged,
        "summary": summary,
        "report_path": str(report_path),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_workspace_json(workspace_dir: str, step_names: list[str]) -> list[dict]:
    """Collect JSON data from multiple workspace step results."""
    collected: list[dict] = []
    for name in step_names:
        loaded = read_results(workspace_dir, name)
        if isinstance(loaded, dict):
            stdout = loaded.get("stdout")
            if isinstance(stdout, dict):
                collected.append(stdout)
            elif isinstance(stdout, list):
                collected.extend(stdout)
    return collected


def _find_step_results_path(workspace_dir: str, step_prefix: str) -> str | None:
    """Find the results.json path for a workspace step by prefix."""
    ws = Path(workspace_dir)
    for d in sorted(ws.iterdir()) if ws.is_dir() else []:
        if d.is_dir() and d.name.startswith(step_prefix):
            results_file = d / "results.json"
            if results_file.exists():
                return str(results_file)
    # Also check for direct step directory match
    exact = ws / step_prefix
    if exact.is_dir():
        results_file = exact / "results.json"
        if results_file.exists():
            return str(results_file)
    return None


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_security_pipeline(
    db_path: str,
    goal: str = "scan",
    function_name: str | None = None,
    top_n: int = 10,
    json_mode: bool = False,
    timeout_override: int | None = None,
    workspace_run_dir: str | None = None,
    max_workers: int | None = None,
    no_cache: bool = False,
) -> dict:
    """Execute the security scan pipeline.

    Returns structured JSON with per-phase summaries, merged findings,
    and workspace file references.
    """
    start_time = time.time()
    module_name = Path(db_path).stem
    workspace_dir = workspace_run_dir or create_run_dir(module_name, f"security_{goal}")

    timeout = timeout_override or _adaptive_timeout(0)

    if top_n <= 0:
        top_n = adaptive_top_n(0)

    progress = ProgressReporter(total=4, label="Security scan")
    all_results: dict = {}
    phase_log: list[dict] = []

    def _log_phase(name: str, phase_start: float, result: dict, success: bool):
        elapsed = round(time.time() - phase_start, 2)
        entry = {"phase": name, "success": success, "elapsed_seconds": elapsed}
        if not success and isinstance(result, dict):
            entry["error"] = result.get("error", "Unknown error")
        phase_log.append(entry)

    # Phase 1: Recon
    status_message("Phase 1/4: Recon -- classifying functions and mapping attack surface")
    t0 = time.time()
    recon = _phase_recon(
        db_path,
        workspace_dir,
        timeout,
        max_workers=max_workers,
        no_cache=no_cache,
    )
    all_results.update(recon)
    _log_phase("recon", t0, recon, any(
        isinstance(v, dict) and v.get("success") for v in recon.values()
    ))
    progress.update(1)

    entrypoints = extract_top_entrypoints(recon, workspace_dir, top_n=top_n)

    # Prioritize confirmed IPC handlers (RPC, COM, WinRT)
    ipc_data = recon.get("ipc_context", {}).get("json_data", {})
    ipc_procs: set[str] = set()
    ipc_priority_list: list[str] = []

    for ipc_key in ("rpc", "com", "winrt"):
        sub = ipc_data.get(ipc_key, {})
        procs = sub.get("procedures", [])
        ipc_procs.update(procs)
        ipc_priority_list.extend(procs[:10])

    if ipc_procs:
        ipc_entries = [e for e in entrypoints if e in ipc_procs]
        non_ipc = [e for e in entrypoints if e not in ipc_procs]
        extra_ipc = [p for p in ipc_priority_list if p not in set(entrypoints)]
        entrypoints = ipc_entries + extra_ipc[:5] + non_ipc
        entrypoints = entrypoints[:top_n]
        if ipc_entries or extra_ipc:
            print(f"  [IPC] Prioritized {len(ipc_entries)} IPC handlers in scan targets "
                  f"(RPC/COM/WinRT)", file=sys.stderr)

    # Phase 2: Vulnerability scan
    status_message("Phase 2/4: Preparing AI scanner contexts (threat models + callgraphs)")
    t0 = time.time()
    vuln = _phase_vuln_scan(
        db_path,
        workspace_dir,
        timeout,
        max_workers=max_workers,
        no_cache=no_cache,
    )
    all_results.update(vuln)
    _log_phase("vuln_scan", t0, vuln, any(
        isinstance(v, dict) and v.get("success") for v in vuln.values()
    ))
    progress.update(2)

    # Phase 3: Taint context preparation for AI taint scanner
    status_message("Phase 3/4: Preparing taint-enriched callgraph context for top entry points")
    t0 = time.time()
    taint = _phase_taint(
        db_path,
        workspace_dir,
        timeout,
        entrypoints,
        function_name,
        max_workers=max_workers,
        no_cache=no_cache,
    )
    all_results.update(taint)
    _log_phase("taint", t0, taint, any(
        isinstance(v, dict) and v.get("success") for v in taint.values()
    ) if taint else True)
    progress.update(3)

    # Phase 4: Report synthesis
    status_message("Phase 4/4: Merging and ranking findings")
    t0 = time.time()
    report = _phase_report(all_results, workspace_dir, persist=True)
    _log_phase("report", t0, report, bool(report.get("findings") is not None))
    progress.update(4)

    total_elapsed = round(time.time() - start_time, 2)
    succeeded = sum(1 for p in phase_log if p["success"])
    failed = sum(1 for p in phase_log if not p["success"])

    return {
        "status": "ok",
        "pipeline_complete": failed == 0,
        "goal": goal,
        "db_path": db_path,
        "module": module_name,
        "workspace_run_dir": workspace_dir,
        "pipeline_summary": {
            "total_phases": len(phase_log),
            "succeeded": succeeded,
            "failed": failed,
        },
        "phase_log": phase_log,
        "findings": to_json(report.get("findings", [])),
        "findings_summary": report.get("summary", {}),
        "report_path": report.get("report_path"),
        "entrypoints_analyzed": entrypoints,
        "total_elapsed_seconds": total_elapsed,
    }


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

def print_text_report(data: dict) -> None:
    """Print a human-readable security scan report."""
    print(f"\n{'=' * 80}")
    print(f"  SECURITY SCAN REPORT: {data.get('module', '?')}")
    print(f"  Goal: {data.get('goal', '?')}")
    print(f"  Elapsed: {data.get('total_elapsed_seconds', 0)}s")
    print(f"{'=' * 80}\n")

    if data.get("workspace_run_dir"):
        print(f"  Workspace: {data['workspace_run_dir']}")

    # Pipeline summary
    summary = data.get("pipeline_summary", {})
    print(f"  Phases: {summary.get('succeeded', 0)} succeeded, "
          f"{summary.get('failed', 0)} failed\n")

    for phase in data.get("phase_log", []):
        status = "OK" if phase["success"] else "FAIL"
        print(f"    [{status:>4}] {phase['phase']:<25} -- {phase['elapsed_seconds']}s")
        if not phase["success"] and phase.get("error"):
            print(f"           Error: {phase['error'][:120]}")
    print()

    # Findings summary
    fs = data.get("findings_summary", {})
    if fs:
        print("  FINDINGS SUMMARY:")
        print(f"    Total: {fs.get('total', 0)}")
        by_sev = fs.get("by_severity", {})
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            count = by_sev.get(sev, 0)
            if count:
                print(f"    {sev}: {count}")
        by_src = fs.get("by_source", {})
        for src, count in by_src.items():
            if count:
                print(f"    [{src}]: {count}")
        print()

    # Top findings table
    findings = data.get("findings", [])
    if findings:
        print("  TOP FINDINGS:")
        print(f"    {'#':>3}  {'Score':>6}  {'Severity':<10}  {'Source':<22}  {'Function'}")
        print(f"    {'-' * 3}  {'-' * 6}  {'-' * 10}  {'-' * 22}  {'-' * 30}")
        for i, f in enumerate(findings[:20], 1):
            fname = f.get("function_name", "?")
            if len(fname) > 30:
                fname = fname[:27] + "..."
            score = f.get("exploitability_score") or f.get("score", 0)
            print(f"    {i:>3}  {score:>6.2f}  {f.get('severity', '?'):<10}  "
                  f"{f.get('source_type', '?'):<22}  {fname}")
        print()

    if not findings:
        print("  No vulnerabilities detected across all pipelines.\n")

    # Entry points
    eps = data.get("entrypoints_analyzed", [])
    if eps:
        print(f"  ENTRY POINTS ANALYZED ({len(eps)}):")
        for ep in eps:
            print(f"    - {ep}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a multi-phase security scan on a DeepExtractIDA module.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Goals:
  scan    Full 5-phase vulnerability scan (default)
  audit   Targeted audit on a specific function
  hunt    Hypothesis-driven scan on top entry points
""",
    )
    parser.add_argument("db_path", help="Path to the module's analysis DB")
    parser.add_argument(
        "--goal", default="scan",
        choices=["scan", "audit", "hunt"],
        help="Security scan goal (default: scan)",
    )
    parser.add_argument(
        "--function", dest="function_name",
        help="Target function (used with --goal audit)",
    )
    parser.add_argument(
        "--top", type=int, default=10,
        help="Number of top entry points to analyze (default: 10)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON (default: human-readable text)",
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="Override per-phase timeout in seconds",
    )
    parser.add_argument(
        "--workspace-run-dir",
        help="Optional existing run directory under .claude/workspace/ to reuse",
    )
    parser.add_argument(
        "--max-workers", type=int, default=None,
        help="Cap phase parallelism across grouped scanner invocations",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass caches for supported skill scripts",
    )
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    if args.goal == "audit" and not args.function_name:
        emit_error("--function is required for audit goal", ErrorCode.INVALID_ARGS)

    status_message(f"Starting security {args.goal} on {Path(db_path).stem}...")

    data = run_security_pipeline(
        db_path=db_path,
        goal=args.goal,
        function_name=args.function_name,
        top_n=args.top,
        json_mode=args.json,
        timeout_override=args.timeout,
        workspace_run_dir=args.workspace_run_dir,
        max_workers=args.max_workers,
        no_cache=args.no_cache,
    )

    if args.json:
        emit_json(data, default=str)
    else:
        print_text_report(data)


if __name__ == "__main__":
    main()
