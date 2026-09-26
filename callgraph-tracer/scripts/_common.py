"""Shared utilities for callgraph-tracer skill.

Provides workspace bootstrap, DB/tracking-DB path resolution, and re-exports
of commonly used helper functions so individual scripts can stay concise.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_AGENT_DIR = str(Path(__file__).resolve().parents[3])
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from skills._shared import bootstrap, make_db_resolvers

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = bootstrap(__file__)
resolve_db_path, resolve_tracking_db = make_db_resolvers(WORKSPACE_ROOT)

from helpers import (  # noqa: E402
    emit_error,
    get_function_id,
    load_function_index_for_db,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    search_index,
    validate_function_id,
)

__all__ = [
    "SCRIPT_DIR",
    "WORKSPACE_ROOT",
    "emit_error",
    "get_function_id",
    "load_function_index_for_db",
    "open_analyzed_files_db",
    "open_individual_analysis_db",
    "parse_json_safe",
    "resolve_db_path",
    "resolve_tracking_db",
    "search_index",
    "validate_function_id",
]
