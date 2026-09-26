"""Shared utilities for reconstruct-types scripts.

Provides workspace root resolution, mangled name parsing, JSON helpers,
and IDA type size mappings used across all skill scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

_AGENT_DIR = str(Path(__file__).resolve().parents[3])
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from skills._shared import bootstrap, make_db_resolvers

WORKSPACE_ROOT = bootstrap(__file__)
resolve_db_path, resolve_tracking_db = make_db_resolvers(WORKSPACE_ROOT)

from helpers import parse_json_safe  # noqa: E402
from helpers.calling_conventions import (  # noqa: E402
    ASM_PTR_SIZES,
    ASM_REG_SIZES,
    PARAM_REGS_X64,
    STACK_REGS,
)
from helpers.type_constants import IDA_TO_C_TYPE, SIZE_TO_C_TYPE, TYPE_SIZES  # noqa: E402
from helpers.mangled_names import parse_class_from_mangled  # noqa: E402


__all__ = [
    "ASM_PTR_SIZES",
    "ASM_REG_SIZES",
    "IDA_TO_C_TYPE",
    "PARAM_REGS_X64",
    "parse_class_from_mangled",
    "parse_json_safe",
    "resolve_db_path",
    "resolve_tracking_db",
    "SIZE_TO_C_TYPE",
    "STACK_REGS",
    "TYPE_SIZES",
    "WORKSPACE_ROOT",
]
