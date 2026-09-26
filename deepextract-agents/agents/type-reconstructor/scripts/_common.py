"""Shared utilities for type-reconstructor subagent scripts.

Provides workspace root resolution, path utilities, subprocess helpers for
calling existing skill scripts, and common type-mapping constants used by
the reconstruction pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

_AGENT_DIR = str(Path(__file__).resolve().parents[3])
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from skills._shared import bootstrap

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = bootstrap(__file__)

from helpers import AgentBase, parse_json_safe  # noqa: E402,F401 -- re-exported for subagent scripts
from helpers.db_paths import resolve_db_path_auto as resolve_db_path  # noqa: E402
from helpers.errors import log_error  # noqa: E402
from helpers.type_constants import IDA_TO_C_TYPE, SIZE_TO_C_TYPE, TYPE_SIZES  # noqa: E402,F401

_AGENT_BASE = AgentBase(default_timeout=300, default_max_retries=1)

# x64 natural alignment: fields align to their own size (capped at 8)
MAX_ALIGNMENT = 8


# ---------------------------------------------------------------------------
# Confidence scoring constants
# ---------------------------------------------------------------------------

# Minimum number of source functions for "high" confidence.
# 4+ functions accessing the same offset strongly suggests a real field.
HIGH_CONFIDENCE_THRESHOLD = 4
# Minimum for "medium". 2 independent observations is moderate evidence.
MEDIUM_CONFIDENCE_THRESHOLD = 2


def compute_confidence(
    source_count: int,
    asm_verified: bool,
    access_type_count: int,
) -> tuple[str, float]:
    """Compute a human-readable confidence label and numeric score (0-1).

    Factors:
    - source_count: how many functions observed this field
    - asm_verified: whether the access was confirmed in assembly
    - access_type_count: how many different IDA type patterns accessed it
    """
    score = 0.0

    # Source function count (0.0 to 0.5)
    if source_count >= HIGH_CONFIDENCE_THRESHOLD:
        score += 0.5
    elif source_count >= MEDIUM_CONFIDENCE_THRESHOLD:
        score += 0.3
    elif source_count >= 1:
        score += 0.15

    # Assembly verification (0.0 or 0.3)
    if asm_verified:
        score += 0.3

    # Multiple access patterns (0.0 or 0.2)
    if access_type_count >= 2:
        score += 0.2
    elif access_type_count >= 1:
        score += 0.1

    score = min(score, 1.0)

    if score >= 0.7:
        label = "high"
    elif score >= 0.4:
        label = "medium"
    else:
        label = "low"

    return label, round(score, 2)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def aligned_offset(offset: int, size: int) -> int:
    """Return the next naturally-aligned offset for a field of *size* bytes.

    x64 rule: fields align to min(size, MAX_ALIGNMENT).
    """
    alignment = min(size, MAX_ALIGNMENT)
    if alignment <= 0:
        return offset
    return (offset + alignment - 1) & ~(alignment - 1)


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
    max_retries: int = 1,
) -> Optional[dict | list]:
    """Run a skill script via subprocess and return parsed JSON output.

    Thin wrapper around ``helpers.run_skill_script`` that preserves the
    original return convention: parsed JSON on success, ``None`` on failure.
    Always requests ``--json`` output from the child script.

    Args:
        max_retries: Number of automatic retries for transient errors.
            Default ``1`` (retry once on DB lock / I/O errors).
    """
    return _AGENT_BASE.run_skill_script(
        skill_name,
        script_name,
        args,
        timeout=timeout,
        workspace_dir=workspace_dir,
        workspace_step=workspace_step,
        max_retries=max_retries,
    )
