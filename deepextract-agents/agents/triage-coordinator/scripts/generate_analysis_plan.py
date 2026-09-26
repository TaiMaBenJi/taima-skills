#!/usr/bin/env python3
"""Generate a structured analysis plan for parent agent execution.

Given a module and goal, outputs a plan specifying which subagents to launch
(in parallel or sequentially) with appropriate parameters.  Used in "plan
generation mode" where the triage-coordinator doesn't run analysis itself
but produces a plan for the parent agent to orchestrate specialist subagents.

Usage:
    python generate_analysis_plan.py <db_path> --goal triage
    python generate_analysis_plan.py <db_path> --goal security
    python generate_analysis_plan.py <db_path> --goal full
    python generate_analysis_plan.py <db_path> --goal understand-function --function <name>
    python generate_analysis_plan.py <db_path> --goal types
    python generate_analysis_plan.py <db_path> --goal triage --json

Output:
    Structured JSON plan with parallel and sequential phases,
    adapted based on module characteristics (COM-heavy, RPC-heavy, etc.).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the script directory is on sys.path for sibling imports
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from _common import (
    WORKSPACE_ROOT,
    get_module_characteristics,
    resolve_db_path,
)
from helpers.errors import ErrorCode, emit_error, safe_parse_args
from helpers.json_output import emit_json


# ---------------------------------------------------------------------------
# Agent routing: maps skills to the best-fit subagent for delegation.
# Tasks with a matching entry get an "agent" field in the plan output.
# The parent can use this to dispatch to a subagent or run the skill directly.
# ---------------------------------------------------------------------------
SKILL_TO_AGENT: dict[str, str] = {
    "reconstruct-types": "type-reconstructor",
    "com-interface-reconstruction": "type-reconstructor",
    "batch-lift": "code-lifter",
}


# ---------------------------------------------------------------------------
# Plan generation per goal
# ---------------------------------------------------------------------------
def _with_workspace_args(args: list[str], output_key: str) -> list[str]:
    """Append workspace handoff args to a task args list."""
    return list(args) + [
        "--workspace-dir", "{workspace_run_dir}",
        "--workspace-step", output_key,
    ]


def _attach_workspace_protocol(plan: dict) -> None:
    """Attach workspace handoff metadata and agent routing to all tasks."""
    for phase in plan.get("phases", []):
        for task in phase.get("tasks", []):
            if "skill" not in task or "script" not in task:
                continue
            output_key = task.get("output_key") or Path(task["script"]).stem
            task["output_key"] = output_key
            if "args" in task:
                task["args"] = _with_workspace_args(task["args"], output_key)
            if "args_template" in task:
                task["args_template"] = _with_workspace_args(task["args_template"], output_key)
            task["workspace"] = {
                "workspace_dir_arg": "--workspace-dir {workspace_run_dir}",
                "workspace_step_arg": f"--workspace-step {output_key}",
                "results_path": f"{{workspace_run_dir}}/{output_key}/results.json",
                "summary_path": f"{{workspace_run_dir}}/{output_key}/summary.json",
            }
            agent = SKILL_TO_AGENT.get(task["skill"])
            if agent:
                task["agent"] = agent

    plan["workspace_protocol"] = {
        "workspace_root": ".claude/workspace",
        "workspace_run_dir_template": "{module}_{goal}_{timestamp}",
        "execution": "all skill tasks run with --workspace-dir and --workspace-step",
        "context_policy": "use summaries in context, read results.json only on demand",
    }


def _triage_plan(db_path: str, chars) -> list[dict]:
    """Triage plan: classify + report + attack surface."""
    return [
        {
            "phase": 1,
            "name": "parallel_classification_and_discovery",
            "mode": "parallel",
            "tasks": [
                {
                    "skill": "classify-functions",
                    "script": "triage_summary.py",
                    "args": [db_path, "--json", "--top", "20"],
                    "task": "Classify all functions and generate triage summary",
                    "output_key": "classify_triage",
                },
                {
                    "skill": "classify-functions",
                    "script": "classify_module.py",
                    "args": [db_path, "--json"],
                    "task": "Full classification (unfiltered for downstream security analysis)",
                    "output_key": "classify_full",
                },
                {
                    "skill": "map-attack-surface",
                    "script": "discover_entrypoints.py",
                    "args": [db_path, "--json"],
                    "task": "Discover all entry points",
                    "output_key": "discover_entrypoints",
                },
            ],
        },
        {
            "phase": 2,
            "name": "synthesize_triage",
            "mode": "sequential",
            "tasks": [
                {
                    "action": "synthesize",
                    "task": "Combine classification and entry point data "
                            "into triage report with prioritized function list",
                    "inputs": ["classify_triage", "classify_full", "discover_entrypoints"],
                },
            ],
        },
    ]


def _security_plan(db_path: str, chars) -> list[dict]:
    """Security plan: triage + rank + dossiers + vulnerability scanning."""
    phases = _triage_plan(db_path, chars)

    # Phase 3: Rank and graph (parallel)
    phases.append({
        "phase": 3,
        "name": "security_ranking",
        "mode": "parallel",
        "depends_on": "parallel_classification_and_discovery",
        "tasks": [
            {
                "skill": "map-attack-surface",
                "script": "rank_entrypoints.py",
                "args": [db_path, "--json", "--top", "10"],
                "task": "Rank entry points by attack value",
                "output_key": "rank_entrypoints",
            },
            {
                "skill": "callgraph-tracer",
                "script": "build_call_graph.py",
                "args": [db_path, "--stats"],
                "task": "Compute call graph statistics",
                "output_key": "call_graph_stats",
                "note": "Text output; no --json flag available",
            },
        ],
    })

    # Phase 4: Build dossiers for top entries (sequential -- depends on ranking)
    phases.append({
        "phase": 4,
        "name": "security_dossiers",
        "mode": "sequential",
        "depends_on": "security_ranking",
        "tasks": [
            {
                "skill": "security-dossier",
                "script": "build_dossier.py",
                "args_template": [db_path, "{function_name}",
                                  "--callee-depth", "2", "--json"],
                "task": "Build security dossier for top-5 ranked entry points",
                "iterate_over": "rank_entrypoints.top_5",
                "output_key": "security_dossiers",
            },
        ],
    })

    # Phase 5: Synthesis
    phases.append({
        "phase": 5,
        "name": "synthesize_security",
        "mode": "sequential",
        "tasks": [
            {
                "action": "synthesize",
                "task": "Combine security rankings, dossiers, "
                        "and call graph into risk-prioritized report with "
                        "specific findings and recommended manual audit targets",
                "inputs": ["classify_triage", "classify_full",
                           "discover_entrypoints", "rank_entrypoints",
                           "call_graph_stats", "security_dossiers"],
            },
        ],
    })

    return phases


def _full_plan(db_path: str, chars) -> list[dict]:
    """Full plan: broad analysis -> specialized -> deep -> synthesis."""
    phases = []

    # Phase 1: Parallel broad analysis
    phase1_tasks = [
        {
            "skill": "classify-functions",
            "script": "triage_summary.py",
            "args": [db_path, "--json", "--top", "20"],
            "task": "Classify all functions",
            "output_key": "classify_triage",
        },
        {
            "skill": "classify-functions",
            "script": "classify_module.py",
            "args": [db_path, "--json"],
            "task": "Full classification (unfiltered for downstream security analysis)",
            "output_key": "classify_full",
        },
        {
            "skill": "map-attack-surface",
            "script": "discover_entrypoints.py",
            "args": [db_path, "--json"],
            "task": "Discover entry points",
            "output_key": "discover_entrypoints",
        },
        {
            "skill": "callgraph-tracer",
            "script": "build_call_graph.py",
            "args": [db_path, "--stats"],
            "task": "Build call graph",
            "output_key": "call_graph_stats",
            "note": "Text output; no --json flag available",
        },
        {
            "skill": "reconstruct-types",
            "script": "list_types.py",
            "args": [db_path, "--json"],
            "task": "List types and classes",
            "output_key": "list_types",
        },
    ]

    phases.append({
        "phase": 1,
        "name": "broad_analysis",
        "mode": "parallel",
        "tasks": phase1_tasks,
    })

    # Phase 2: Security ranking + specialized (parallel, depends on Phase 1)
    phase2_tasks = [
        {
            "skill": "map-attack-surface",
            "script": "rank_entrypoints.py",
            "args": [db_path, "--json", "--top", "15"],
            "task": "Rank entry points by attack value",
            "output_key": "rank_entrypoints",
        },
    ]

    if chars.is_com_heavy:
        phase2_tasks.append({
            "skill": "com-interface-reconstruction",
            "script": "scan_com_interfaces.py",
            "args": [db_path, "--json"],
            "task": "Reconstruct COM interfaces",
            "output_key": "com_interfaces",
        })

    phases.append({
        "phase": 2,
        "name": "specialized_analysis",
        "mode": "parallel",
        "depends_on": "broad_analysis",
        "tasks": phase2_tasks,
    })

    # Phase 3: Deep analysis of top functions (sequential)
    phases.append({
        "phase": 3,
        "name": "deep_analysis",
        "mode": "sequential",
        "depends_on": "specialized_analysis",
        "tasks": [
            {
                "skill": "security-dossier",
                "script": "build_dossier.py",
                "args_template": [db_path, "{function_name}",
                                  "--callee-depth", "2", "--json"],
                "task": "Build dossiers for top-5 ranked functions",
                "iterate_over": "rank_entrypoints.top_5",
                "output_key": "security_dossiers",
            },
        ],
    })

    # Phase 4: Synthesis
    phases.append({
        "phase": 4,
        "name": "synthesize_full",
        "mode": "sequential",
        "tasks": [
            {
                "action": "synthesize",
                "task": "Combine all analysis results into comprehensive report: "
                        "security findings enriched with type information, "
                        "call graph topology explaining the module's architecture, "
                        "and function-level deep analysis for top-priority targets",
                "inputs": [
                    "classify_triage", "classify_full",
                    "discover_entrypoints", "rank_entrypoints",
                    "call_graph_stats", "list_types",
                    "module_context", "com_interfaces",
                    "security_dossiers",
                ],
            },
        ],
    })

    return phases


def _function_plan(db_path: str, function_name: str, chars) -> list[dict]:
    """Understand-function plan: context + call graph + data flow + security."""
    return [
        {
            "phase": 1,
            "name": "function_context",
            "mode": "parallel",
            "tasks": [
                {
                    "skill": "classify-functions",
                    "script": "classify_function.py",
                    "args": [db_path, function_name, "--json"],
                    "task": f"Classify {function_name}",
                    "output_key": "classification",
                },
                {
                    "skill": "decompiled-code-extractor",
                    "script": "extract_function_data.py",
                    "args": [db_path, function_name],
                    "task": f"Extract full data for {function_name}",
                    "output_key": "function_data",
                    "note": "No --json flag; output is text-formatted",
                },
                {
                    "skill": "callgraph-tracer",
                    "script": "build_call_graph.py",
                    "args": [db_path, "--neighbors", function_name],
                    "task": f"Get direct callers and callees of {function_name}",
                    "output_key": "neighbors",
                },
                {
                    "skill": "callgraph-tracer",
                    "script": "build_call_graph.py",
                    "args": [db_path, "--reachable", function_name,
                             "--max-depth", "2"],
                    "task": f"Functions reachable from {function_name}",
                    "output_key": "reachable",
                },
            ],
        },
        {
            "phase": 2,
            "name": "deep_function_analysis",
            "mode": "parallel",
            "depends_on": "function_context",
            "tasks": [
                {
                    "skill": "security-dossier",
                    "script": "build_dossier.py",
                    "args": [db_path, function_name,
                             "--callee-depth", "2", "--json"],
                    "task": f"Build security dossier for {function_name}",
                    "output_key": "security_dossier",
                },
            ],
        },
        {
            "phase": 3,
            "name": "synthesize_function",
            "mode": "sequential",
            "tasks": [
                {
                    "action": "synthesize",
                    "task": f"Build comprehensive understanding of "
                            f"{function_name}: purpose, data flow, "
                            "call chain, security implications",
                    "inputs": ["classification", "function_data", "neighbors",
                               "reachable",
                               "security_dossier"],
                },
            ],
        },
    ]


def _types_plan(db_path: str, chars) -> list[dict]:
    """Types plan: discover + analyze + generate headers."""
    phases = [
        {
            "phase": 1,
            "name": "type_discovery",
            "mode": "parallel",
            "tasks": [
                {
                    "skill": "reconstruct-types",
                    "script": "list_types.py",
                    "args": [db_path, "--json"],
                    "task": "List all types and classes",
                    "output_key": "types",
                },
                {
                    "skill": "classify-functions",
                    "script": "triage_summary.py",
                    "args": [db_path, "--json"],
                    "task": "Classify functions to identify class patterns",
                    "output_key": "classification",
                },
            ],
        },
    ]

    phase2_tasks = [
        {
            "skill": "reconstruct-types",
            "script": "scan_struct_fields.py",
            "args": [db_path, "--all-classes", "--json"],
            "task": "Scan memory access patterns for all classes",
            "output_key": "struct_fields",
        },
    ]

    if chars.is_com_heavy:
        phase2_tasks.append({
            "skill": "com-interface-reconstruction",
            "script": "scan_com_interfaces.py",
            "args": [db_path, "--json"],
            "task": "Reconstruct COM interfaces",
            "output_key": "com_interfaces",
        })

    phases.append({
        "phase": 2,
        "name": "type_analysis",
        "mode": "parallel",
        "depends_on": "type_discovery",
        "tasks": phase2_tasks,
    })

    phases.append({
        "phase": 3,
        "name": "header_generation",
        "mode": "sequential",
        "depends_on": "type_analysis",
        "tasks": [
            {
                "skill": "reconstruct-types",
                "script": "generate_header.py",
                "args": [db_path, "--all-classes"],
                "task": "Generate compilable header files",
                "output_key": "headers",
            },
            {
                "action": "synthesize",
                "task": "Combine type information with COM interfaces "
                        "into comprehensive type documentation",
                "inputs": ["types", "struct_fields", "com_interfaces", "headers"],
            },
        ],
    })

    return phases


# ---------------------------------------------------------------------------
# Main plan generator
# ---------------------------------------------------------------------------
def generate_plan(
    db_path: str,
    goal: str,
    function_name: str = None,
) -> dict:
    """Generate a structured analysis plan."""
    chars = get_module_characteristics(db_path)

    plan: dict = {
        "module": chars.file_name,
        "db_path": db_path,
        "goal": goal,
        "module_characteristics": chars.to_dict(),
        "workspace_run_dir_template": "{module}_{goal}_{timestamp}",
        "phases": [],
        "synthesis": "",
    }

    if goal == "triage":
        plan["phases"] = _triage_plan(db_path, chars)
        plan["synthesis"] = (
            "Combine classification results with attack surface data to "
            "produce a prioritized list of functions for further analysis. "
            "Recommend next analysis steps based on module characteristics "
            "(COM-heavy -> COM reconstruction, security-relevant -> security "
            "audit, class-heavy -> type reconstruction)."
        )

    elif goal == "security":
        plan["phases"] = _security_plan(db_path, chars)
        plan["synthesis"] = (
            "Combine ranked entry points with security dossiers to produce "
            "a risk-prioritized finding list. Cross-reference dangerous "
            "operation paths with type information. Flag functions requiring "
            "manual audit with evidence from multiple analysis passes."
        )

    elif goal == "full":
        plan["phases"] = _full_plan(db_path, chars)
        plan["synthesis"] = (
            "Combine all analysis results into a comprehensive report: "
            "security findings enriched with type information, call graph "
            "topology explaining the module's architecture, and function-level "
            "deep analysis for top-priority targets. Generate a prioritized "
            "analysis roadmap with specific follow-up commands."
        )

    elif goal == "understand-function":
        if not function_name:
            emit_error("Function name required for understand-function goal", ErrorCode.INVALID_ARGS)
        plan["phases"] = _function_plan(db_path, function_name, chars)
        plan["synthesis"] = (
            f"Build a complete understanding of {function_name}: its purpose, "
            "how it processes data, what it calls, what calls it, security "
            "implications, and its role in the module's architecture."
        )

    elif goal == "types":
        plan["phases"] = _types_plan(db_path, chars)
        plan["synthesis"] = (
            "Merge type information from multiple sources (mangled names, "
            "vtable contexts, memory access patterns, COM interfaces) into "
            "compilable header files. Document class hierarchies and interface "
            "inheritance."
        )

    else:
        emit_error(f"Unknown goal: {goal}", ErrorCode.INVALID_ARGS)

    _attach_workspace_protocol(plan)
    return plan


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def print_text_plan(plan: dict) -> None:
    """Print a human-readable analysis plan."""
    print(f"\n{'=' * 80}")
    print(f"  ANALYSIS PLAN: {plan.get('module', '?')}")
    print(f"  Goal: {plan.get('goal', '?')}")
    print(f"{'=' * 80}\n")

    chars = plan.get("module_characteristics", {})
    flags = []
    for flag_key in ["is_com_heavy", "is_rpc_heavy", "is_security_relevant",
                      "is_dispatch_heavy", "is_class_heavy"]:
        if chars.get(flag_key):
            flags.append(flag_key.replace("is_", "").replace("_", "-"))
    if flags:
        print(f"  Module traits: {', '.join(flags)}")
        print()

    for phase in plan.get("phases", []):
        mode = phase.get("mode", "sequential").upper()
        depends = ""
        if phase.get("depends_on"):
            depends = f" (depends on: {phase['depends_on']})"
        print(f"  Phase {phase['phase']}: {phase['name']} [{mode}]{depends}")

        for task in phase.get("tasks", []):
            if "action" in task:
                print(f"    -> [SYNTHESIZE] {task['task']}")
                if task.get("inputs"):
                    print(f"       Inputs: {', '.join(task['inputs'])}")
            else:
                iterate = ""
                if task.get("iterate_over"):
                    iterate = f" (iterate: {task['iterate_over']})"
                agent_hint = ""
                if task.get("agent"):
                    agent_hint = f" -> agent: {task['agent']}"
                print(f"    -> [{task['skill']}] {task['task']}{iterate}{agent_hint}")
                print(f"       Script: {task['script']}")
        print()

    print(f"  SYNTHESIS STRATEGY:")
    print(f"    {plan.get('synthesis', '(none)')}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a structured analysis plan for parent agent "
                    "execution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="Output as JSON (default: human-readable text)",
    )
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)
    plan = generate_plan(db_path, args.goal, args.function_name)

    if args.json:
        emit_json(plan, default=str)
    else:
        print_text_plan(plan)


if __name__ == "__main__":
    main()
