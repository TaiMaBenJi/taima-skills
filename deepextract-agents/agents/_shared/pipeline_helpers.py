"""Shared pipeline helpers for agent scripts.

Provides:
- adaptive_top_n: config-based top-N calculation
- with_flag: conditional flag appending for args lists
- extract_top_entrypoints: extract function names from ranked entrypoint results
"""

from __future__ import annotations

from typing import Any, Callable

from helpers.config import get_config_value
from helpers.workspace import read_results


def adaptive_top_n(function_count: int, entry_count: int = 0) -> int:
    """Compute adaptive top-N based on module size and entry point count.

    Uses config keys under ``security_auditor``:
    - ``top_n_base``            (default 5)
    - ``top_n_per_100_functions`` (default 1)
    - ``top_n_max``             (default 25)
    - ``top_n_min``             (default 3)

    The formula adds ``top_n_per_100_functions`` for every 100 functions
    in the module, then clamps to ``[top_n_min, top_n_max]``.  If
    *entry_count* exceeds the computed N, the result is raised to cover
    at least 50% of discovered entry points (still capped by max).
    """
    base = int(get_config_value("security_auditor.top_n_base", 5))
    per_100 = int(get_config_value("security_auditor.top_n_per_100_functions", 1))
    top_max = int(get_config_value("security_auditor.top_n_max", 25))
    top_min = int(get_config_value("security_auditor.top_n_min", 3))

    n = base + (function_count // 100) * per_100
    if entry_count > 0:
        n = max(n, (entry_count + 1) // 2)
    return max(top_min, min(n, top_max))


def with_flag(args: list[str], flag: str, enabled: bool) -> list[str]:
    """Return a copy of *args* with *flag* appended when enabled."""
    if not enabled or flag in args:
        return list(args)
    return list(args) + [flag]


def extract_top_entrypoints(
    results: dict,
    workspace_dir: str,
    *,
    top_n: int | None = None,
    step_name: str = "rank_entrypoints",
    read_results_fn: Callable[[str, str], Any] | None = None,
) -> list[str]:
    """Extract top entry point function names from ranking results.

    Resolves ranked data from:
    - results[step_name] when it is a dict with "json_data" (run_skill_script envelope)
    - results[step_name] when it is the raw ranked list/dict
    - workspace storage via read_results(workspace_dir, step_name)

    Parameters
    ----------
    results : dict
        Pipeline step results (may contain step_name with json_data or raw payload).
    workspace_dir : str
        Workspace run directory for loading stored results.
    top_n : int | None
        If given, return at most this many names.  None returns all.
    step_name : str
        Key in results and workspace step name (default: rank_entrypoints).
    read_results_fn : callable | None
        Optional loader (workspace_dir, step_name) -> payload.  Defaults to
        helpers.workspace.read_results.

    Returns
    -------
    list[str]
        Function names in ranked order.
    """
    loader = read_results_fn or read_results
    ranked: Any = None

    step_result = results.get(step_name)
    if isinstance(step_result, dict):
        if step_result.get("success") and "json_data" in step_result:
            ranked = step_result.get("json_data")
        elif "json_data" not in step_result:
            ranked = step_result

    if ranked is None:
        loaded = loader(workspace_dir, step_name)
        if isinstance(loaded, dict):
            output_type = loaded.get("output_type")
            if output_type == "json":
                ranked = loaded.get("stdout")
            else:
                ranked = loaded.get("stdout_text", loaded)
        else:
            ranked = loaded

    names: list[str] = []
    if isinstance(ranked, list):
        for entry in ranked:
            if isinstance(entry, dict):
                name = entry.get("function_name", entry.get("name", ""))
                if name:
                    names.append(name)
    elif isinstance(ranked, dict):
        for key in ("ranked", "entrypoints", "top_entrypoints", "ranked_entrypoints"):
            entries = ranked.get(key, [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        name = entry.get("function_name", entry.get("name", ""))
                        if name:
                            names.append(name)
                if names:
                    break

    if top_n is not None:
        return names[:top_n]
    return names
