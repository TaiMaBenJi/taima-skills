"""Shared utilities for security-auditor agent scripts.

Provides:
- Workspace root bootstrap and path constants
- Common helper re-exports for security scanning workflows
- Skill script runner with configurable timeout
- Finding normalization and merge utilities
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

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

SKILLS_DIR = WORKSPACE_ROOT / ".claude" / "skills"
EXTRACTED_DBS_DIR = WORKSPACE_ROOT / "extracted_dbs"
EXTRACTED_CODE_DIR = WORKSPACE_ROOT / "extracted_code"

from helpers import (  # noqa: E402
    AgentBase,
    emit_error,
    emit_json,
    find_skill_script,
    log_warning,
    open_individual_analysis_db,
    parse_json_safe,
)
from helpers.config import get_config_value  # noqa: E402
from helpers.db_paths import (  # noqa: E402
    resolve_db_path_auto as resolve_db_path,
    resolve_module_db_auto as _resolve_module_db_auto,
)
from helpers.errors import ErrorCode  # noqa: E402
from helpers.finding_merge import (  # noqa: E402
    deduplicate,
    findings_summary,
    merge_findings,
    rank,
    to_json,
)
from helpers.finding_schema import (  # noqa: E402
    Finding,
    from_logic_finding,
    from_memory_finding,
    from_taint_finding,
    from_verified_finding,
    normalize_scanner_output,
)
from helpers.progress import ProgressReporter, status_message  # noqa: E402

_AGENT_BASE = AgentBase(
    default_timeout=int(get_config_value("security_auditor.step_timeout_seconds", 180))
)


def run_skill_script(
    skill_name: str,
    script_name: str,
    args: list[str],
    timeout: int = 120,
    json_output: bool = False,
    workspace_dir: str | None = None,
    workspace_step: str | None = None,
    max_retries: int = 0,
) -> dict:
    """Run a skill script via subprocess and return full execution envelope."""
    return _AGENT_BASE.run_skill_script_result(
        skill_name,
        script_name,
        args,
        timeout=timeout,
        json_output=json_output,
        workspace_dir=workspace_dir,
        workspace_step=workspace_step,
        max_retries=max_retries,
    )


def resolve_module_db(module_name_or_path: str) -> Optional[str]:
    """Resolve a module name or DB path to an absolute DB path."""
    return _resolve_module_db_auto(module_name_or_path)
