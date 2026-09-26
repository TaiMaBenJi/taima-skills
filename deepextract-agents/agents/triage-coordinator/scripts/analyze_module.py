#!/usr/bin/env python3
"""Run a configurable analysis pipeline and produce a unified report.

This is the triage-coordinator's main tool.  It orchestrates existing skill
scripts to perform comprehensive module analysis based on the specified goal.

Usage:
    python analyze_module.py <db_path> --goal triage
    python analyze_module.py <db_path> --goal security
    python analyze_module.py <db_path> --goal full
    python analyze_module.py <db_path> --goal understand-function --function <name>
    python analyze_module.py <db_path> --goal types

Goals:
    triage:              classify + report summary + attack surface discovery
    security:            triage + rank entrypoints + build dossiers for top-5
    full:                triage + security + type reconstruction + deep research
    understand-function: function context + call graph + data flow + classification
    types:               list types + scan fields + generate headers + COM interfaces

Output:
    Structured JSON with per-step summaries + workspace file references.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure the script directory is on sys.path for sibling imports
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
_AGENTS_ROOT = _SCRIPT_DIR.parent.parent
if str(_AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_ROOT))

from _common import (
    WORKSPACE_ROOT,
    ModuleCharacteristics,
    create_run_dir,
    get_module_characteristics,
    get_module_code_dir,
    load_module_identity,
    read_results,
    resolve_db_path,
    run_skill_script,
)
from _shared.pipeline_helpers import (
    adaptive_top_n,
    extract_top_entrypoints,
    with_flag,
)
from helpers.config import get_config_value
from helpers.errors import ErrorCode, emit_error, log_warning, safe_parse_args
from helpers.json_output import emit_json
from helpers.progress import status_message


# ---------------------------------------------------------------------------
# Adaptive timeout calculation
# ---------------------------------------------------------------------------
def compute_adaptive_timeout(
    function_count: int,
    base_timeout: int | None = None,
    per_function_seconds: float | None = None,
) -> int:
    """Return a timeout in seconds scaled to the module's function count.

    Formula: ``base_timeout + function_count * per_function_seconds``

    Defaults are sourced from config (``triage.step_timeout_seconds`` and
    ``triage.per_function_timeout_seconds``) with hard-coded fallbacks of
    180 s base and 0.2 s per function.
    """
    if base_timeout is None:
        base_timeout = int(get_config_value("triage.step_timeout_seconds", 180))
    if per_function_seconds is None:
        per_function_seconds = float(
            get_config_value("triage.per_function_timeout_seconds", 0.2)
        )
    return max(base_timeout, int(base_timeout + function_count * per_function_seconds))


# ---------------------------------------------------------------------------
# Pipeline step definition
# ---------------------------------------------------------------------------
class PipelineStep:
    """A single step in an analysis pipeline.

    Steps with the same non-``None`` *parallel_group* string are eligible
    to run concurrently via :class:`concurrent.futures.ThreadPoolExecutor`.
    Steps with ``parallel_group=None`` always run sequentially.
    """

    def __init__(
        self,
        name: str,
        skill: str,
        script: str,
        args: list[str],
        json_flag: bool = True,
        description: str = "",
        timeout: int = 180,
        parallel_group: str | None = None,
    ):
        self.name = name
        self.skill = skill
        self.script = script
        self.args = args
        self.json_flag = json_flag
        self.description = description
        self.timeout = timeout
        self.parallel_group = parallel_group


# ---------------------------------------------------------------------------
# Goal -> pipeline step builders
# ---------------------------------------------------------------------------
def _triage_steps(
    db_path: str,
    chars: ModuleCharacteristics,
    *,
    quick: bool = False,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Steps for triage goal: classify + report summary + attack surface."""
    triage_args = [db_path, "--json", "--top", "10" if quick else "20"]
    classify_args = [db_path, "--json"]
    entrypoint_args = [db_path, "--json"]
    return [
        PipelineStep(
            "classify_triage",
            "classify-functions", "triage_summary.py",
            with_flag(triage_args, "--no-cache", no_cache),
            description="Classify all functions and generate triage summary",
            parallel_group="triage_classify",
        ),
        PipelineStep(
            "classify_full",
            "classify-functions", "classify_module.py",
            with_flag(classify_args, "--no-cache", no_cache),
            description="Full classification (unfiltered for downstream security analysis)",
            parallel_group="triage_classify",
        ),
        PipelineStep(
            "discover_entrypoints",
            "map-attack-surface", "discover_entrypoints.py",
            with_flag(entrypoint_args, "--no-cache", no_cache),
            description="Discover all entry points (exports, COM, RPC, callbacks, etc.)",
            parallel_group="triage_classify",
        ),
    ]


def _security_steps(
    db_path: str,
    chars: ModuleCharacteristics,
    *,
    top_n: int = 10,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Additional steps for security goal (on top of triage)."""
    return [
        PipelineStep(
            "rank_entrypoints",
            "map-attack-surface", "rank_entrypoints.py",
            [db_path, "--json", "--top", str(top_n)],
            description="Rank entry points by attack value",
            parallel_group="post_triage",
        ),
        PipelineStep(
            "call_graph_stats",
            "callgraph-tracer", "build_call_graph.py",
            with_flag([db_path, "--stats"], "--no-cache", no_cache),
            json_flag=False,
            description="Compute call graph statistics",
            parallel_group="post_triage",
        ),
    ]


def _security_dossier_steps(
    db_path: str,
    results: dict,
    workspace_run_dir: str,
    *,
    top_n: int = 5,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Build dossiers for top-N ranked entry points (depends on ranking results)."""
    steps: list[PipelineStep] = []
    top_functions = extract_top_entrypoints(results, workspace_run_dir)

    for fname in top_functions[:top_n]:
        steps.append(PipelineStep(
            f"dossier_{fname}",
            "security-dossier", "build_dossier.py",
            with_flag([db_path, fname, "--callee-depth", "2", "--json"], "--no-cache", no_cache),
            description=f"Security dossier for {fname}",
            timeout=120,
            parallel_group="dossiers",
        ))

    return steps


def _full_extra_steps(
    db_path: str,
    chars: ModuleCharacteristics,
    *,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Additional steps for full goal (beyond triage + security).

    All steps use ``parallel_group="post_triage"`` (same as security steps)
    so they merge into a single parallel phase for the ``full`` goal.
    """
    steps = [
        PipelineStep(
            "topology",
            "callgraph-tracer", "build_call_graph.py",
            with_flag([db_path, "--stats"], "--no-cache", no_cache),
            json_flag=False,
            description="Call graph topology analysis",
            parallel_group="post_triage",
        ),
        PipelineStep(
            "list_types",
            "reconstruct-types", "list_types.py",
            [db_path, "--json"],
            description="List all types and classes",
            parallel_group="post_triage",
        ),
    ]

    # Cross-module dependency overview (when tracking DB exists)
    try:
        from helpers.db_paths import resolve_tracking_db_auto
        tracking_db = resolve_tracking_db_auto()
        if tracking_db:
            steps.append(PipelineStep(
                "module_deps_overview",
                "import-export-resolver", "module_deps.py",
                ["--json"],
                description="PE-level module dependency overview",
                parallel_group="post_triage",
            ))
    except Exception as exc:
        log_warning(
            f"Failed to resolve tracking DB for module_deps_overview: {exc}",
            "DB_ERROR",
        )

    # Conditional specialized analysis based on module traits
    if chars.is_com_heavy:
        steps.append(PipelineStep(
            "scan_com",
            "com-interface-reconstruction", "scan_com_interfaces.py",
            with_flag([db_path, "--json"], "--no-cache", no_cache),
            description="COM interface reconstruction",
            parallel_group="post_triage",
        ))

    return steps


def _types_steps(
    db_path: str,
    chars: ModuleCharacteristics,
    *,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Steps for types goal."""
    steps = [
        PipelineStep(
            "list_types",
            "reconstruct-types", "list_types.py",
            [db_path, "--json"],
            description="List all detected types and classes",
            parallel_group="types_scan",
        ),
    ]

    if chars.is_com_heavy:
        steps.append(PipelineStep(
            "scan_com_interfaces",
            "com-interface-reconstruction", "scan_com_interfaces.py",
            with_flag([db_path, "--json"], "--no-cache", no_cache),
            description="Scan for COM interfaces",
            parallel_group="types_scan",
        ))

    return steps


def _function_steps(
    db_path: str,
    function_name: str,
    *,
    no_cache: bool = False,
) -> list[PipelineStep]:
    """Steps for understand-function goal."""
    return [
        PipelineStep(
            "classify_function",
            "classify-functions", "classify_function.py",
            [db_path, function_name, "--json"],
            description=f"Classify function: {function_name}",
            parallel_group="func_analysis",
        ),
        PipelineStep(
            "extract_function_data",
            "decompiled-code-extractor", "extract_function_data.py",
            [db_path, function_name],
            json_flag=False,
            description=f"Extract full function data: {function_name}",
            parallel_group="func_analysis",
        ),
        PipelineStep(
            "call_graph_neighbors",
            "callgraph-tracer", "build_call_graph.py",
            with_flag([db_path, "--neighbors", function_name], "--no-cache", no_cache),
            json_flag=False,
            description=f"Direct callers and callees of {function_name}",
            parallel_group="func_analysis",
        ),
        PipelineStep(
            "call_graph_reachable",
            "callgraph-tracer", "build_call_graph.py",
            with_flag([db_path, "--reachable", function_name, "--max-depth", "2"], "--no-cache", no_cache),
            json_flag=False,
            description=f"Functions reachable from {function_name} (depth 2)",
            parallel_group="func_analysis",
        ),
        PipelineStep(
            "security_dossier",
            "security-dossier", "build_dossier.py",
            with_flag([db_path, function_name, "--callee-depth", "2", "--json"], "--no-cache", no_cache),
            description=f"Security dossier for {function_name}",
            parallel_group="func_analysis",
        ),
    ]


# ---------------------------------------------------------------------------
# Pipeline execution engine
# ---------------------------------------------------------------------------
def _unwrap_workspace_output(full_result: dict | None) -> dict | list | str | None:
    """Extract the original script payload from workspace-captured result data."""
    if not isinstance(full_result, dict):
        return full_result
    output_type = full_result.get("output_type")
    if output_type == "json":
        return full_result.get("stdout")
    if output_type == "text":
        return full_result.get("stdout_text", "")
    return full_result


def _load_workspace_payload(workspace_run_dir: str, step_name: str):
    """Load a full step payload from workspace storage on demand."""
    return _unwrap_workspace_output(read_results(workspace_run_dir, step_name))


def _group_steps(
    steps: list[PipelineStep],
) -> list[list[PipelineStep]]:
    """Group consecutive steps by ``parallel_group``.

    Consecutive steps that share the same non-``None`` ``parallel_group``
    are collected into one group.  Steps with ``parallel_group=None`` each
    become their own single-element group (run sequentially).
    """
    groups: list[list[PipelineStep]] = []
    for key, grp in itertools.groupby(
        steps, key=lambda s: s.parallel_group,
    ):
        group = list(grp)
        if key is None:
            for step in group:
                groups.append([step])
        else:
            groups.append(group)
    return groups


def _run_step_group(
    group: list[PipelineStep],
    workspace_run_dir: str,
    max_workers: int = 4,
) -> list[tuple[dict, dict]]:
    """Execute a group of pipeline steps.

    If the group contains a single step or has no ``parallel_group``, run
    sequentially.  Otherwise use a :class:`ThreadPoolExecutor` to run all
    steps in parallel.
    """
    if len(group) <= 1 or group[0].parallel_group is None:
        return [_execute_step(s, workspace_run_dir) for s in group]

    results: list[tuple[dict, dict]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_step = {
            pool.submit(_execute_step, step, workspace_run_dir): step
            for step in group
        }
        for future in as_completed(future_to_step):
            results.append(future.result())
    return results


def _execute_step(step: PipelineStep, workspace_run_dir: str) -> tuple[dict, dict]:
    """Execute a single pipeline step and return ``(step_entry, result)``.

    Catches all exceptions so that a single step failure never aborts the
    entire pipeline.  On unhandled errors the step is recorded as failed
    with the exception message.
    """
    step_start = time.time()

    try:
        result = run_skill_script(
            step.skill, step.script, step.args,
            json_output=step.json_flag,
            timeout=step.timeout,
            workspace_dir=workspace_run_dir,
            workspace_step=step.name,
            max_retries=1,
        )
    except Exception as exc:
        elapsed = round(time.time() - step_start, 2)
        step_entry = {
            "step": step.name,
            "skill": step.skill,
            "script": step.script,
            "description": step.description,
            "success": False,
            "elapsed_seconds": elapsed,
            "error": f"{type(exc).__name__}: {exc}",
        }
        status_message(
            f"[FAIL] {step.name} ({step.skill}/{step.script}) "
            f"-- {type(exc).__name__}: {exc}"
        )
        return step_entry, {"success": False, "error": str(exc)}

    elapsed = round(time.time() - step_start, 2)

    step_entry = {
        "step": step.name,
        "skill": step.skill,
        "script": step.script,
        "description": step.description,
        "success": result["success"],
        "elapsed_seconds": elapsed,
    }

    if not result["success"]:
        step_entry["error"] = result.get("error", "Unknown error")
        status_message(
            f"[FAIL] {step.name} ({step.skill}/{step.script}) "
            f"-- {step_entry['error'][:120]}"
        )
    elif isinstance(result.get("json_data"), dict):
        step_entry["workspace_results_path"] = result["json_data"].get("results_path")
        step_entry["workspace_summary_path"] = result["json_data"].get("summary_path")

    return step_entry, result


def run_pipeline(
    db_path: str,
    goal: str,
    function_name: str | None = None,
    chars: ModuleCharacteristics | None = None,
    workspace_run_dir: str | None = None,
    timeout_override: int | None = None,
    top_n: int = 10,
    quick: bool = False,
    no_cache: bool = False,
) -> dict:
    """Execute an analysis pipeline for the given goal.

    Parameters
    ----------
    timeout_override : int | None
        If given, every pipeline step uses this timeout instead of its
        own default or the adaptive calculation.

    Returns structured JSON with step summaries + workspace references.
    """
    start_time = time.time()

    if chars is None:
        chars = get_module_characteristics(db_path)
    if workspace_run_dir is None:
        module_name = chars.file_name or Path(db_path).stem
        workspace_run_dir = create_run_dir(module_name, goal)

    # Adaptive top-N when caller uses the default value
    if top_n <= 0:
        top_n = adaptive_top_n(chars.total_functions)

    # Compute adaptive timeout if no explicit override was given
    adaptive_timeout = compute_adaptive_timeout(chars.total_functions)

    # Build step list based on goal
    steps: list[PipelineStep] = []

    if goal == "triage":
        steps = _triage_steps(db_path, chars, quick=quick, no_cache=no_cache)

    elif goal == "security":
        steps = _triage_steps(db_path, chars, quick=quick, no_cache=no_cache) + _security_steps(
            db_path,
            chars,
            top_n=top_n,
            no_cache=no_cache,
        )

    elif goal == "full":
        steps = (
            _triage_steps(db_path, chars, quick=quick, no_cache=no_cache)
            + _security_steps(db_path, chars, top_n=top_n, no_cache=no_cache)
            + _full_extra_steps(db_path, chars, no_cache=no_cache)
        )

    elif goal == "understand-function":
        if not function_name:
            emit_error("Function name required for understand-function goal", ErrorCode.INVALID_ARGS)
        steps = _function_steps(db_path, function_name, no_cache=no_cache)

    elif goal == "types":
        steps = _types_steps(db_path, chars, no_cache=no_cache)

    else:
        emit_error(f"Unknown goal: {goal}", ErrorCode.INVALID_ARGS)

    # Apply timeout: explicit override > adaptive > step default
    for step in steps:
        if timeout_override is not None:
            step.timeout = timeout_override
        else:
            step.timeout = max(step.timeout, adaptive_timeout)

    # Execute steps (parallel groups run concurrently)
    max_workers = int(get_config_value("triage.max_workers", 4))
    results: dict[str, dict] = {}
    step_log: list[dict] = []

    groups = _group_steps(steps)
    for i, g in enumerate(groups, 1):
        names = [s.name for s in g]
        mode = "parallel" if len(g) > 1 and g[0].parallel_group else "sequential"
        status_message(
            f"Phase {i}/{len(groups)} [{mode}, {len(g)} step(s)]: "
            f"{', '.join(names)}"
        )

    for group in groups:
        group_results = _run_step_group(group, workspace_run_dir, max_workers=max_workers)
        for step_entry, result in group_results:
            step_log.append(step_entry)

            step_name = step_entry["step"]
            if isinstance(result.get("json_data"), dict):
                results[step_name] = result["json_data"]
            elif result["success"] and result["stdout"]:
                results[step_name] = {"status": "success", "raw_output": result["stdout"][:400]}

    # Security goal: build dossiers after ranking (depends on results)
    extra_phase_count = 0
    if goal in ("security", "full") and "rank_entrypoints" in results:
        dossier_steps = _security_dossier_steps(
            db_path,
            results,
            workspace_run_dir,
            top_n=min(top_n, 5),
            no_cache=no_cache,
        )
        if dossier_steps:
            dossier_groups = _group_steps(dossier_steps)
            extra_phase_count += len(dossier_groups)
            for i, g in enumerate(dossier_groups, len(groups) + 1):
                names = [s.name for s in g]
                mode = "parallel" if len(g) > 1 and g[0].parallel_group else "sequential"
                status_message(
                    f"Phase {i}/{len(groups) + extra_phase_count} "
                    f"[{mode}, {len(g)} step(s)]: {', '.join(names)}"
                )
        dossiers: list[dict] = []
        for group in _group_steps(dossier_steps):
            group_results = _run_step_group(group, workspace_run_dir, max_workers=max_workers)
            for ds_entry, ds_result in group_results:
                step_log.append(ds_entry)
                if isinstance(ds_result.get("json_data"), dict):
                    dossiers.append(ds_result["json_data"])
                elif ds_result["success"] and ds_result["stdout"]:
                    dossiers.append({"status": "success", "raw_output": ds_result["stdout"][:400]})
        if dossiers:
            results["security_dossiers"] = dossiers

    # Generate next-step recommendations
    next_steps = _generate_next_steps(goal, results, chars, workspace_run_dir)

    total_elapsed = round(time.time() - start_time, 2)
    succeeded = sum(1 for s in step_log if s.get("success"))
    failed = sum(1 for s in step_log if not s.get("success"))

    if failed:
        status_message(
            f"Pipeline finished: {succeeded} succeeded, {failed} failed "
            f"(continuing with partial results)"
        )

    # Merge module identity from file_info.json + module_profile.json
    module_identity = load_module_identity(chars.file_name) if chars.file_name else {}

    return {
        "status": "ok",
        "pipeline_complete": failed == 0,
        "goal": goal,
        "db_path": db_path,
        "module": chars.to_dict(),
        "module_identity": module_identity,
        "workspace_run_dir": workspace_run_dir,
        "workspace_manifest": str(Path(workspace_run_dir) / "manifest.json"),
        "pipeline_summary": {
            "total_steps": len(step_log),
            "succeeded": succeeded,
            "failed": failed,
        },
        "pipeline_steps": step_log,
        "results": results,
        "next_steps": next_steps,
        "total_elapsed_seconds": total_elapsed,
    }


# ---------------------------------------------------------------------------
# Next-step recommendations
# ---------------------------------------------------------------------------
def _generate_next_steps(
    goal: str,
    results: dict,
    chars: ModuleCharacteristics,
    workspace_run_dir: str,
) -> list[dict]:
    """Generate recommended next steps based on analysis results."""
    steps: list[dict] = []

    if goal == "triage":
        if chars.is_security_relevant:
            steps.append({
                "action": "security_audit",
                "description": (
                    f"Module has {chars.dangerous_api_count} dangerous API refs "
                    f"and {chars.security_density} security functions. "
                    "Run security analysis."
                ),
                "command": "analyze_module.py <db_path> --goal security",
                "priority": "HIGH",
            })
        if chars.is_com_heavy:
            steps.append({
                "action": "com_reconstruction",
                "description": (
                    f"Module has high COM density ({chars.com_density} COM "
                    "functions). Reconstruct COM interfaces."
                ),
                "command": "analyze_module.py <db_path> --goal types",
                "priority": "MEDIUM",
            })
        if chars.is_class_heavy:
            steps.append({
                "action": "type_reconstruction",
                "description": (
                    f"Module has {chars.class_count} classes. "
                    "Reconstruct type hierarchies."
                ),
                "command": "analyze_module.py <db_path> --goal types",
                "priority": "MEDIUM",
            })

        # Suggest top functions for deeper analysis
        triage_data = _load_workspace_payload(workspace_run_dir, "classify_triage")
        if not isinstance(triage_data, dict):
            triage_data = {}
        top_funcs = triage_data.get("top_interesting", [])[:5]
        for func in top_funcs:
            if func.get("interest_score", 0) >= 5:
                steps.append({
                    "action": "explain_function",
                    "description": (
                        f"Explain {func['function_name']} "
                        f"(interest: {func['interest_score']}, "
                        f"category: {func['primary_category']})"
                    ),
                    "command": f"/explain <module> {func['function_name']}",
                    "priority": "MEDIUM",
                })

        steps.append({
            "action": "search_module",
            "description": "Search for specific APIs, strings, or patterns",
            "command": "/search <module> <term>",
            "priority": "LOW",
        })

    elif goal == "security":
        ranked = _load_workspace_payload(workspace_run_dir, "rank_entrypoints")
        if ranked is None:
            ranked = results.get("rank_entrypoints")
        entries: list = []
        if isinstance(ranked, list):
            entries = ranked
        elif isinstance(ranked, dict):
            for key in ("ranked", "entrypoints", "top_entrypoints",
                        "ranked_entrypoints"):
                entries = ranked.get(key, [])
                if isinstance(entries, list) and entries:
                    break
        for entry in entries[:5]:
            if isinstance(entry, dict):
                name = entry.get("function_name", entry.get("name", ""))
                score = entry.get("attack_score", entry.get("score", 0))
                if name:
                    steps.append({
                        "action": "audit_function",
                        "description": (
                            f"Security audit {name} "
                            f"(attack score: {score})"
                        ),
                        "command": f"/audit <module> {name}",
                        "priority": "HIGH",
                    })

        steps.append({
            "action": "full_analysis",
            "description": "Run full analysis for comprehensive coverage",
            "command": "analyze_module.py <db_path> --goal full",
            "priority": "LOW",
        })

    elif goal == "full":
        steps.append({
            "action": "lift_top_functions",
            "description": "Lift the most interesting functions for readable code",
            "command": "/lift-class <module> <ClassName>",
            "priority": "MEDIUM",
        })
        steps.append({
            "action": "generate_report",
            "description": "Generate comprehensive RE report document",
            "command": "/full-report <module>",
            "priority": "LOW",
        })

    elif goal == "understand-function":
        steps.append({
            "action": "explain_function",
            "description": "Get a quick structured explanation of this function",
            "command": "/explain <module> <function>",
            "priority": "HIGH",
        })
        steps.append({
            "action": "lift_function",
            "description": "Lift this function to readable code",
            "command": "/lift-class <module> <ClassName>",
            "priority": "MEDIUM",
        })
        steps.append({
            "action": "audit_function",
            "description": "Run security audit on this function",
            "command": "/audit <module> <function>",
            "priority": "MEDIUM",
        })

    elif goal == "types":
        if chars.is_class_heavy:
            steps.append({
                "action": "lift_classes",
                "description": "Lift reconstructed class methods",
                "command": "/lift-class <module> <ClassName>",
                "priority": "MEDIUM",
            })

    return steps


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def print_text_summary(data: dict) -> None:
    """Print a human-readable summary of analysis results."""
    module = data.get("module", {})

    print(f"\n{'=' * 80}")
    print(f"  ANALYSIS REPORT: {module.get('file_name', '?')}")
    print(f"  Goal: {data.get('goal', '?')}")
    print(f"  Elapsed: {data.get('total_elapsed_seconds', 0)}s")
    print(f"{'=' * 80}\n")

    # Module identity (from file_info.json + module_profile.json)
    identity = data.get("module_identity", {})
    if identity:
        print(f"  Module: {identity.get('file_description', module.get('file_name', '?'))}")
        print(f"  Path: {identity.get('file_path', '?')}")
        size = identity.get("file_size_bytes")
        if size is not None:
            print(f"  Size: {size:,} bytes ({size / 1024:.1f} KB)")
        print(f"  Version: {identity.get('file_version', '?')}")
        print(f"  Company: {identity.get('company_name', '?')}")
        print(f"  PDB: {identity.get('pdb_path', '?')}")
        md5 = identity.get("md5_hash", "")
        sha256 = identity.get("sha256_hash", "")
        if md5:
            print(f"  MD5: {md5}")
        if sha256:
            print(f"  SHA256: {sha256}")
        posture = identity.get("security_posture", {})
        if posture:
            flags = [f for f, v in posture.items() if v is True]
            print(f"  Mitigations: {', '.join(flags).upper()}")
    else:
        print(f"  Module: {module.get('file_name', '?')} -- "
              f"{module.get('file_description', '')}")

    # Module characteristics
    print(f"  Functions: {module.get('total_functions', 0)} | "
          f"Exports: {module.get('export_count', 0)} | "
          f"Imports: {module.get('import_count', 0)}")
    print(f"  Classes: {module.get('class_count', 0)} | "
          f"Named: {module.get('named_function_pct', 0)}%")
    if data.get("workspace_run_dir"):
        print(f"  Workspace: {data['workspace_run_dir']}")

    # Characteristic flags
    flags = []
    for flag_key, label in [
        ("is_com_heavy", "COM-heavy"),
        ("is_rpc_heavy", "RPC-heavy"),
        ("is_security_relevant", "Security-relevant"),
        ("is_dispatch_heavy", "Dispatch-heavy"),
        ("is_class_heavy", "Class-heavy"),
    ]:
        if module.get(flag_key):
            flags.append(label)
    if flags:
        print(f"  Traits: {', '.join(flags)}")
    print()

    # Pipeline execution summary
    print("  PIPELINE STEPS:")
    for step in data.get("pipeline_steps", []):
        status = "OK" if step["success"] else "FAIL"
        print(f"    [{status:>4}] {step['step']:<30} "
              f"({step['skill']}/{step['script']}) "
              f"-- {step['elapsed_seconds']}s")
        if not step["success"]:
            print(f"           Error: {step.get('error', '?')[:120]}")
    print()

    # Key results summary
    results = data.get("results", {})
    workspace_run_dir = data.get("workspace_run_dir")

    def _payload(step_name: str):
        if workspace_run_dir:
            loaded = _load_workspace_payload(workspace_run_dir, step_name)
            if loaded is not None:
                return loaded
        return results.get(step_name, {})

    # Triage summary
    triage = _payload("classify_triage")
    if isinstance(triage, dict):
        dist = triage.get("category_distribution", {})
        if dist:
            print("  CATEGORY DISTRIBUTION:")
            total = triage.get("total_functions", 1)
            for cat, count in sorted(dist.items(), key=lambda x: -x[1]):
                pct = count / total * 100 if total else 0
                bar = "#" * int(pct / 2.5)
                print(f"    {cat:<22} {count:>5} ({pct:5.1f}%)  {bar}")
            print()

        top = triage.get("top_interesting", [])[:10]
        if top:
            print("  TOP INTERESTING FUNCTIONS:")
            print(f"    {'Score':>5}  {'Category':<22}  {'Name'}")
            print(f"    {'-' * 5}  {'-' * 22}  {'-' * 40}")
            for f in top:
                name = f.get("function_name", "?")
                if len(name) > 40:
                    name = name[:37] + "..."
                print(f"    {f.get('interest_score', 0):>5}  "
                      f"{f.get('primary_category', '?'):<22}  {name}")
            print()

    # Entry points
    entrypoints = _payload("discover_entrypoints")
    if isinstance(entrypoints, dict):
        ep_summary = entrypoints.get("summary", entrypoints.get("type_counts", {}))
        if ep_summary:
            print("  ENTRY POINT TYPES:")
            if isinstance(ep_summary, dict):
                for etype, count in sorted(ep_summary.items(), key=lambda x: -x[1]):
                    print(f"    {etype:<30} {count:>5}")
            print()

    # Security dossiers
    dossiers = []
    dossier_summaries = results.get("security_dossiers", [])
    if isinstance(dossier_summaries, list):
        for summary in dossier_summaries:
            if isinstance(summary, dict):
                step_name = summary.get("step_name") or summary.get("step")
                if workspace_run_dir and step_name:
                    loaded = _load_workspace_payload(workspace_run_dir, step_name)
                    if isinstance(loaded, dict):
                        dossiers.append(loaded)
                        continue
            dossiers.append(summary)
    if dossiers:
        print(f"  SECURITY DOSSIERS ({len(dossiers)} built):")
        for d in dossiers:
            if isinstance(d, dict):
                fname = d.get("function_name", d.get("identity", {}).get("function_name", "?"))
                risk = d.get("risk_level", d.get("overall_risk", "?"))
                print(f"    {fname} -- risk: {risk}")
        print()

    # Next steps
    next_steps = data.get("next_steps", [])
    if next_steps:
        print("  RECOMMENDED NEXT STEPS:")
        for i, ns in enumerate(next_steps, 1):
            print(f"    {i}. [{ns['priority']}] {ns['description']}")
            print(f"       Command: {ns['command']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a configurable analysis pipeline for a DeepExtractIDA module.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Goals:
  triage              Classify + report summary + attack surface discovery
  security            Triage + rank entrypoints + build dossiers for top-5
  full                Triage + security + type reconstruction + deep research
  understand-function Function context + call graph + data flow + classification
  types               List types + scan fields + generate headers + COM interfaces
""",
    )
    parser.add_argument("db_path", help="Path to the module's analysis DB")
    parser.add_argument(
        "--goal", required=True,
        choices=["triage", "security", "full", "understand-function", "types"],
        help="Analysis goal",
    )
    parser.add_argument(
        "--function", dest="function_name",
        help="Function name (required for understand-function goal)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON (default: human-readable text + JSON on stderr)",
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="Override per-step timeout in seconds (default: adaptive based on function count)",
    )
    parser.add_argument(
        "--top", type=int, default=10,
        help="Number of top ranked entry points to prioritize (default: 10)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use quick triage defaults where supported",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass caches for supported skill scripts",
    )
    parser.add_argument(
        "--workspace-run-dir",
        help="Optional existing run directory under .claude/workspace/ to reuse",
    )
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    # Get module characteristics first (fast, direct DB access)
    status_message("Fingerprinting module...")
    chars = get_module_characteristics(db_path)
    status_message(f"Module: {chars.file_name} ({chars.total_functions} functions)")

    effective_timeout = args.timeout or compute_adaptive_timeout(chars.total_functions)
    max_workers = int(get_config_value("triage.max_workers", 4))
    status_message(
        f"Step timeout: {effective_timeout}s"
        f"{' (explicit)' if args.timeout else ' (adaptive)'}"
        f" | max_workers: {max_workers}"
    )

    status_message(f"Running {args.goal} pipeline...")
    data = run_pipeline(
        db_path=db_path,
        goal=args.goal,
        function_name=args.function_name,
        chars=chars,
        workspace_run_dir=args.workspace_run_dir,
        timeout_override=args.timeout,
        top_n=args.top,
        quick=args.quick,
        no_cache=args.no_cache,
    )

    if args.json:
        emit_json(data, default=str)
    else:
        print_text_summary(data)


if __name__ == "__main__":
    main()
