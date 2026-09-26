"""Shared utilities for re-analyst subagent scripts.

Provides:
- Workspace root and bootstrap installation
- DB path resolution
- Workspace pattern utilities (create_run_dir, run_skill_script)
- Common helper re-exports used by explain_function.py and re_query.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_AGENT_DIR = str(Path(__file__).resolve().parents[3])
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from skills._shared import (
    bootstrap,
    create_run_dir,
    read_results,
    read_summary,
)

WORKSPACE_ROOT = bootstrap(__file__)
SCRIPT_DIR = Path(__file__).resolve().parent

from helpers import (  # noqa: E402
    AgentBase,
    emit_error,
    get_function_id,
    load_function_index_for_db,
    load_skill_module,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_function,
    search_functions_by_pattern,
)
from helpers.db_paths import resolve_db_path_auto as resolve_db_path  # noqa: E402
from helpers.errors import log_warning  # noqa: E402

_AGENT_BASE = AgentBase(default_timeout=300)


# ---------------------------------------------------------------------------
# Subprocess-based skill script invocation
# ---------------------------------------------------------------------------

def run_skill_script(
    skill_name: str,
    script_name: str,
    args: list[str],
    timeout: int = 300,
    workspace_dir: str | None = None,
    workspace_step: str | None = None,
) -> Optional[dict | list]:
    """Run a skill script via subprocess and return parsed JSON output.

    Thin wrapper around ``helpers.run_skill_script`` that preserves the
    original return convention: parsed JSON on success, ``None`` on failure.
    Always requests ``--json`` output from the child script.
    """
    return _AGENT_BASE.run_skill_script(
        skill_name,
        script_name,
        args,
        timeout=timeout,
        workspace_dir=workspace_dir,
        workspace_step=workspace_step,
    )


# ---------------------------------------------------------------------------
# Lazy classification utilities (shared by re_query.py and explain_function.py)
# ---------------------------------------------------------------------------
_classify_mod = None


def _ensure_classify_mod():
    """Load the classify-functions skill module lazily (once)."""
    global _classify_mod
    if _classify_mod is None:
        try:
            _classify_mod = load_skill_module("classify-functions", "_common")
        except (FileNotFoundError, ImportError):
            log_warning("classify-functions skill unavailable", "NOT_FOUND")
    return _classify_mod


def get_classify_function():
    """Return the ``classify_function`` callable, or ``None`` if unavailable."""
    mod = _ensure_classify_mod()
    return getattr(mod, "classify_function", None) if mod else None


def classify_api_safe(api_name: str) -> Optional[str]:
    """Classify an API name using the classify-functions skill.

    Returns the category string, or ``None`` if the skill is unavailable.
    """
    mod = _ensure_classify_mod()
    if mod is None:
        return None
    fn = getattr(mod, "classify_api", None)
    return fn(api_name) if fn else None


__all__ = [
    "SCRIPT_DIR",
    "WORKSPACE_ROOT",
    "create_run_dir",
    "read_results",
    "read_summary",
    "run_skill_script",
    "resolve_db_path",
    "emit_error",
    "get_function_id",
    "load_function_index_for_db",
    "load_skill_module",
    "open_analyzed_files_db",
    "open_individual_analysis_db",
    "parse_json_safe",
    "resolve_function",
    "search_functions_by_pattern",
    "get_classify_function",
    "classify_api_safe",
]
