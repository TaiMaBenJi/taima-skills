"""Shared utilities for code-lifter subagent scripts.

Provides:
- Workspace root and skill/agent script path resolution
- JSON parsing and DB path resolution
- Mangled name parsing (reuses batch-lift _common)
- Struct access pattern scanning and merging
- Topological sort for dependency ordering
- State file path management
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Generator, Optional

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

SKILLS_DIR = WORKSPACE_ROOT / ".claude" / "skills"
AGENTS_DIR = WORKSPACE_ROOT / ".claude" / "agents"
EXTRACTED_DBS_DIR = WORKSPACE_ROOT / "extracted_dbs"
STATE_DIR = SCRIPT_DIR.parent / "state"

from helpers import (  # noqa: E402
    AgentBase,
    load_skill_module,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
)
from helpers.db_paths import (  # noqa: E402
    resolve_db_path_auto as resolve_db_path,
    resolve_module_db_auto as _resolve_module_db_auto,
    resolve_tracking_db_auto as resolve_tracking_db,
)

_AGENT_BASE = AgentBase(default_timeout=300)

# ---------------------------------------------------------------------------
# Import batch-lift _common via shared load_skill_module (avoids path collisions)
# ---------------------------------------------------------------------------
_blc = load_skill_module("batch-lift", "_common")

# Re-export batch-lift utilities needed by code-lifter scripts
parse_class_from_mangled = _blc.parse_class_from_mangled
scan_struct_accesses = _blc.scan_struct_accesses
merge_struct_fields = _blc.merge_struct_fields
format_struct_definition = _blc.format_struct_definition
topological_sort_functions = _blc.topological_sort_functions
TYPE_SIZES = _blc.TYPE_SIZES
SIZE_TO_C_TYPE = _blc.SIZE_TO_C_TYPE


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
# JSON / Path helpers
# ---------------------------------------------------------------------------


# parse_json_safe imported from helpers


def resolve_module_db(module_name_or_path: str) -> Optional[str]:
    """Resolve a module name or DB path to an absolute DB path."""
    return _resolve_module_db_auto(module_name_or_path, require_complete=False)


# ---------------------------------------------------------------------------
# State file management
# ---------------------------------------------------------------------------


def _sanitize_class_name(class_name: str) -> str:
    """Sanitize a class name for safe use in filesystem paths."""
    return class_name.replace("::", "_").replace("<", "_").replace(">", "_")


def _class_name_hash(class_name: str) -> str:
    """Return the first 8 hex chars of the SHA-256 of *class_name*."""
    return hashlib.sha256(class_name.encode("utf-8")).hexdigest()[:8]


def get_state_file_path(class_name: str) -> Path:
    """Get the path for a class's shared state file.

    The filename encodes both a human-readable sanitized name and an 8-char
    SHA-256 hash of the *original* unsanitized name to prevent collisions
    when different names sanitize to the same string (e.g.
    ``ClassA::Nested`` vs ``ClassA_Nested``).

    Format: ``{sanitized}_{hash8}_state.json``

    For backward compatibility, if an old-format file (without the hash
    suffix) exists and the new-format file does not, the old file is
    automatically renamed to the new location.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_class_name(class_name)
    hash8 = _class_name_hash(class_name)
    new_path = STATE_DIR / f"{safe_name}_{hash8}_state.json"

    # Backward compatibility: migrate old-format file if present
    old_path = STATE_DIR / f"{safe_name}_state.json"
    if old_path.exists() and not new_path.exists():
        old_path.rename(new_path)

    return new_path


@contextlib.contextmanager
def _locked_state_file(path: Path, timeout: float = 10.0) -> Generator[Path, None, None]:
    """Acquire an exclusive lock on a state file for atomic read-modify-write.

    Uses an adjacent ``.lock`` file created with ``O_CREAT | O_EXCL`` for
    cross-platform atomicity (works on both Windows and Unix).  If the lock
    cannot be acquired within *timeout* seconds, the lock file is assumed
    stale and forcibly removed.
    """
    lock_path = path.with_suffix(".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            time.sleep(0.05)
    try:
        yield path
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def load_state(class_name: str) -> Optional[dict]:
    """Load the current shared state for a class, or None if not found.

    Acquires an exclusive lock to prevent concurrent corruption.
    """
    state_path = get_state_file_path(class_name)
    if not state_path.exists():
        return None
    try:
        with _locked_state_file(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_state(class_name: str, state: dict) -> Path:
    """Save the shared state for a class. Returns the state file path.

    Acquires an exclusive lock to prevent concurrent corruption.
    """
    state_path = get_state_file_path(class_name)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _locked_state_file(state_path):
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    return state_path


@contextlib.contextmanager
def atomic_update_state(class_name: str) -> Generator[dict, None, None]:
    """Context manager for atomic read-modify-write of shared state.

    Holds the exclusive lock for the entire duration, preventing race
    conditions between concurrent load+modify+save cycles::

        with atomic_update_state("CMyClass") as state:
            state["constants"]["NEW_CONST"] = {"value": 42}
            # state is auto-saved on successful exit

    If the state file does not exist, yields a fresh initial state.
    If the block raises an exception, the state is NOT saved.
    """
    state_path = get_state_file_path(class_name)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _locked_state_file(state_path):
        # Load under lock
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError):
                state = create_initial_state(class_name, "", "", [], [])
        else:
            state = create_initial_state(class_name, "", "", [], [])

        yield state

        # Save under the same lock hold
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)


def create_initial_state(
    class_name: str,
    module_name: str,
    db_path: str,
    functions: list[dict],
    dependency_order: list[int],
    struct_fields: Optional[list[dict]] = None,
) -> dict:
    """Create an initial shared state dict for a new lifting session."""
    return {
        "class_name": class_name,
        "module_name": module_name,
        "db_path": db_path,
        "functions": {
            str(f["function_id"]): {
                "function_id": f["function_id"],
                "function_name": f.get("function_name", ""),
                "role": f.get("role"),
                "lifted": False,
                "clean_signature": None,
            }
            for f in functions
        },
        "dependency_order": dependency_order,
        "struct_definition": {
            "name": class_name,
            "fields": struct_fields or [],
        },
        "constants": {},
        "naming_map": {},
        "lifted_code": {},
    }


# ---------------------------------------------------------------------------
# Function data helpers
# ---------------------------------------------------------------------------


def has_valid_decompiled_code(func) -> bool:
    """Check if a function record has usable decompiled code."""
    code = func.decompiled_code
    if not code or not code.strip():
        return False
    if "Decompiler not available" in code or "Decompilation failed" in code:
        return False
    return True


def func_to_lift_record(func, module_name: str = "") -> dict:
    """Convert a FunctionRecord to a dict with all fields needed for lifting."""
    from helpers.extract_payload import function_record_to_extract_dict

    row = function_record_to_extract_dict(func, strip_has_canary=False)
    for key in (
        "string_literals",
        "outbound_xrefs",
        "inbound_xrefs",
        "vtable_contexts",
        "global_var_accesses",
    ):
        if row.get(key) is None:
            row[key] = []
    row["dangerous_api_calls"] = parse_json_safe(func.dangerous_api_calls) or []
    row["has_decompiled"] = has_valid_decompiled_code(func)
    row["has_assembly"] = bool(func.assembly_code and func.assembly_code.strip())
    row["module_name"] = module_name
    row["role"] = _classify_role(func.mangled_name)
    return row


def _classify_role(mangled_name: Optional[str]) -> Optional[str]:
    """Classify a function's role from its mangled name."""
    if not mangled_name:
        return None
    parsed = parse_class_from_mangled(mangled_name)
    return parsed["role"] if parsed else None


__all__ = [
    "SCRIPT_DIR",
    "WORKSPACE_ROOT",
    "SKILLS_DIR",
    "AGENTS_DIR",
    "EXTRACTED_DBS_DIR",
    "STATE_DIR",
    "create_run_dir",
    "read_results",
    "read_summary",
    "run_skill_script",
    "open_analyzed_files_db",
    "open_individual_analysis_db",
    "parse_class_from_mangled",
    "scan_struct_accesses",
    "merge_struct_fields",
    "format_struct_definition",
    "topological_sort_functions",
    "TYPE_SIZES",
    "SIZE_TO_C_TYPE",
    "parse_json_safe",
    "resolve_db_path",
    "resolve_tracking_db",
    "resolve_module_db",
    "get_state_file_path",
    "load_state",
    "save_state",
    "atomic_update_state",
    "create_initial_state",
    "has_valid_decompiled_code",
    "func_to_lift_record",
]
