"""Shared utilities for triage-coordinator subagent scripts.

Provides:
- Module DB resolution via helpers
- Module characteristic fingerprinting for routing decisions
- JSON parsing utilities
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
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
    find_skill_script,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
)
from helpers.api_taxonomy import classify_api_fingerprint, DISPATCH_KEYWORDS  # noqa: E402
from helpers.errors import db_error_handler  # noqa: E402
from helpers.config import get_config_value  # noqa: E402
from helpers.db_paths import (  # noqa: E402
    resolve_db_path_auto as resolve_db_path,
    resolve_module_db_auto as _resolve_module_db_auto,
    resolve_tracking_db_auto as _resolve_tracking_db_auto,
)

_AGENT_BASE = AgentBase(
    default_timeout=int(get_config_value("triage.step_timeout_seconds", 180))
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


def list_available_modules() -> list[dict]:
    """List all available modules with their DB paths and status."""
    tracking = _resolve_tracking_db_auto()
    if not tracking:
        return []

    modules = []
    with db_error_handler(tracking, "loading tracking database"):
        with open_analyzed_files_db(tracking) as db:
            for rec in db.get_all():
                abs_path = None
                if rec.analysis_db_path:
                    candidate = WORKSPACE_ROOT / rec.analysis_db_path
                    if candidate.exists():
                        abs_path = str(candidate)
                modules.append({
                    "file_name": rec.file_name or "(unknown)",
                    "extension": rec.file_extension or "",
                    "status": rec.status,
                    "db_path": abs_path or rec.analysis_db_path,
                })
    return modules


# API prefix lookup tables for categorization are now centralized in
# helpers.api_taxonomy -- imported as classify_api_fingerprint and
# DISPATCH_KEYWORDS at the top of this file.


# ---------------------------------------------------------------------------
# Module characteristics fingerprinting
# ---------------------------------------------------------------------------
@dataclass
class ModuleCharacteristics:
    """Quick fingerprint of module characteristics for routing decisions."""
    file_name: str = ""
    file_description: str = ""
    total_functions: int = 0
    export_count: int = 0
    import_count: int = 0
    com_density: int = 0       # COM-related functions
    rpc_density: int = 0       # RPC-related functions
    security_density: int = 0  # security-related functions
    crypto_density: int = 0    # crypto-related functions
    dispatch_density: int = 0  # dispatch/routing functions
    rpc_interface_count: int = 0
    rpc_procedure_count: int = 0
    rpc_remote_reachable: bool = False
    rpc_service_name: str = ""
    rpc_risk_tier: str = ""
    com_server_count: int = 0
    com_method_count: int = 0
    com_can_elevate: bool = False
    com_risk_tier: str = ""
    winrt_server_count: int = 0
    winrt_method_count: int = 0
    winrt_risk_tier: str = ""
    named_function_pct: float = 0.0
    class_count: int = 0
    dangerous_api_count: int = 0

    @property
    def is_com_heavy(self) -> bool:
        if self.com_server_count > 0 or self.com_method_count > 0:
            return True
        if self.total_functions == 0:
            return False
        return self.com_density > 5 or (self.com_density / self.total_functions > 0.1)

    @property
    def is_rpc_heavy(self) -> bool:
        if self.rpc_interface_count > 0:
            return True
        return self.rpc_density > 3

    @property
    def is_winrt_heavy(self) -> bool:
        return self.winrt_server_count > 0 or self.winrt_method_count > 0

    @property
    def is_security_relevant(self) -> bool:
        return (self.security_density > 3 or self.crypto_density > 2
                or self.dangerous_api_count > 10)

    @property
    def is_dispatch_heavy(self) -> bool:
        return self.dispatch_density > 5

    @property
    def is_class_heavy(self) -> bool:
        return self.class_count > 3

    @property
    def has_ipc_surface(self) -> bool:
        """True when any IPC index (RPC/COM/WinRT) confirms entry points."""
        return (self.rpc_interface_count > 0
                or self.com_server_count > 0
                or self.winrt_server_count > 0)

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "file_description": self.file_description,
            "total_functions": self.total_functions,
            "export_count": self.export_count,
            "import_count": self.import_count,
            "com_density": self.com_density,
            "rpc_density": self.rpc_density,
            "security_density": self.security_density,
            "crypto_density": self.crypto_density,
            "dispatch_density": self.dispatch_density,
            "named_function_pct": self.named_function_pct,
            "class_count": self.class_count,
            "dangerous_api_count": self.dangerous_api_count,
            "rpc_interface_count": self.rpc_interface_count,
            "rpc_procedure_count": self.rpc_procedure_count,
            "rpc_remote_reachable": self.rpc_remote_reachable,
            "rpc_service_name": self.rpc_service_name,
            "rpc_risk_tier": self.rpc_risk_tier,
            "com_server_count": self.com_server_count,
            "com_method_count": self.com_method_count,
            "com_can_elevate": self.com_can_elevate,
            "com_risk_tier": self.com_risk_tier,
            "winrt_server_count": self.winrt_server_count,
            "winrt_method_count": self.winrt_method_count,
            "winrt_risk_tier": self.winrt_risk_tier,
            "is_com_heavy": self.is_com_heavy,
            "is_rpc_heavy": self.is_rpc_heavy,
            "is_winrt_heavy": self.is_winrt_heavy,
            "has_ipc_surface": self.has_ipc_surface,
            "is_security_relevant": self.is_security_relevant,
            "is_dispatch_heavy": self.is_dispatch_heavy,
            "is_class_heavy": self.is_class_heavy,
        }


def get_module_characteristics(db_path: str) -> ModuleCharacteristics:
    """Quick fingerprint of a module for routing decisions.

    Uses direct DB access (not subprocess) for speed.
    """
    chars = ModuleCharacteristics()

    # Query IPC indexes for ground-truth interface data
    rpc_idx = None
    com_idx = None
    winrt_idx = None
    try:
        from helpers.rpc_index import get_rpc_index
        rpc_idx = get_rpc_index()
    except Exception:
        pass
    try:
        from helpers.com_index import get_com_index
        com_idx = get_com_index()
    except Exception:
        pass
    try:
        from helpers.winrt_index import get_winrt_index
        winrt_idx = get_winrt_index()
    except Exception:
        pass

    _tier_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    with db_error_handler(db_path, "loading module characteristics"):
        with open_individual_analysis_db(db_path) as db:
            # File info
            fi = db.get_file_info()
            if fi:
                chars.file_name = fi.file_name or ""
                chars.file_description = fi.file_description or ""

                # RPC index enrichment
                if rpc_idx and rpc_idx.loaded and chars.file_name:
                    ifaces = rpc_idx.get_interfaces_for_module(chars.file_name)
                    if ifaces:
                        chars.rpc_interface_count = len(ifaces)
                        chars.rpc_procedure_count = len(rpc_idx.get_procedures_for_module(chars.file_name))
                        chars.rpc_remote_reachable = any(i.is_remote_reachable for i in ifaces)
                        svcs = [i.service_name for i in ifaces if i.service_name]
                        chars.rpc_service_name = svcs[0] if svcs else ""
                        tiers = [i.risk_tier for i in ifaces]
                        chars.rpc_risk_tier = min(tiers, key=lambda t: _tier_priority.get(t, 99))

                # COM index enrichment
                if com_idx and com_idx.loaded and chars.file_name:
                    try:
                        com_servers = com_idx.get_servers_for_module(chars.file_name)
                        if com_servers:
                            chars.com_server_count = len(com_servers)
                            chars.com_method_count = len(com_idx.get_procedures_for_module(chars.file_name))
                            chars.com_can_elevate = any(s.can_elevate for s in com_servers)
                            com_tiers = [s.risk_tier for s in com_servers if hasattr(s, "risk_tier") and s.risk_tier]
                            if com_tiers:
                                chars.com_risk_tier = min(com_tiers, key=lambda t: _tier_priority.get(t, 99))
                    except Exception:
                        pass

                # WinRT index enrichment
                if winrt_idx and winrt_idx.loaded and chars.file_name:
                    try:
                        winrt_servers = winrt_idx.get_servers_for_module(chars.file_name)
                        if winrt_servers:
                            chars.winrt_server_count = len(winrt_servers)
                            chars.winrt_method_count = len(winrt_idx.get_procedures_for_module(chars.file_name))
                            winrt_tiers = [s.risk_tier for s in winrt_servers if hasattr(s, "risk_tier") and s.risk_tier]
                            if winrt_tiers:
                                chars.winrt_risk_tier = min(winrt_tiers, key=lambda t: _tier_priority.get(t, 99))
                    except Exception:
                        pass

                # Import/export counts
                chars.import_count = len(db.get_imports())
                exports = parse_json_safe(fi.exports) or []
                chars.export_count = len(exports) if isinstance(exports, list) else 0

            # Aggregate stats via single SQL query (avoids loading all records)
            stats = db.compute_stats()
            chars.total_functions = stats["total_functions"]

            # Named/unnamed ratio from lightweight name-only query
            all_names = db.get_function_names()
            named = sum(1 for n in all_names if not n.startswith("sub_"))
            unnamed = len(all_names) - named
            total = named + unnamed
            chars.named_function_pct = round(named / total * 100, 1) if total > 0 else 0.0

            # Class detection via vtable analysis (avoids scanning all mangled names)
            vtable_classes = db.get_vtable_classes()
            chars.class_count = len(vtable_classes)

            # Per-function scanning for COM/RPC/security/crypto density and
            # dangerous API counts.  These fields contain JSON blobs
            # (simple_outbound_xrefs, dangerous_api_calls, vtable_contexts)
            # that must be parsed per-record; no aggregate DB query can
            # replace this loop.
            for func in db.iter_functions():
                fname = func.function_name or ""
                mangled = func.mangled_name or ""

                # COM density
                if any(x in fname for x in ("QueryInterface", "AddRef", "Release")):
                    chars.com_density += 1
                if any(x in mangled for x in ("RuntimeClassImpl", "ComPtr", "WRL")):
                    chars.com_density += 1
                vtable = parse_json_safe(func.vtable_contexts)
                if isinstance(vtable, list) and vtable:
                    chars.com_density += 1

                # Dispatch detection (uses shared DISPATCH_KEYWORDS from api_taxonomy)
                if any(x in fname for x in DISPATCH_KEYWORDS):
                    chars.dispatch_density += 1

                # API-based categorization from outbound xrefs
                # Uses centralized classify_api_fingerprint() from api_taxonomy
                outbound = parse_json_safe(func.simple_outbound_xrefs) or []
                for xref in outbound:
                    if not isinstance(xref, dict):
                        continue
                    api_name = xref.get("function_name", "")
                    if not api_name:
                        continue

                    fp_cat = classify_api_fingerprint(api_name)
                    if fp_cat == "com" or fp_cat == "rpc":
                        chars.rpc_density += 1
                    if fp_cat == "security":
                        chars.security_density += 1
                    if fp_cat == "crypto":
                        chars.crypto_density += 1

                # Dangerous APIs
                dangerous = parse_json_safe(func.dangerous_api_calls) or []
                if isinstance(dangerous, list):
                    chars.dangerous_api_count += len(dangerous)

    return chars


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def get_module_code_dir(module_name: str) -> Optional[Path]:
    """Find the extracted_code directory for a module."""
    if not EXTRACTED_CODE_DIR.is_dir():
        return None

    # Normalize: appinfo.dll -> appinfo_dll
    normalized = module_name.replace(".", "_").lower()

    for d in EXTRACTED_CODE_DIR.iterdir():
        if d.is_dir() and d.name.lower() == normalized:
            return d

    # Fuzzy match
    for d in EXTRACTED_CODE_DIR.iterdir():
        if d.is_dir() and normalized in d.name.lower():
            return d

    return None


def load_module_identity(module_name: str) -> dict[str, Any]:
    """Load module identity and security posture from file_info.json and module_profile.json.

    Returns a flat dict suitable for merging into coordinator output as
    ``module_identity``.  Missing files or fields are silently skipped --
    the returned dict contains only what was successfully loaded.
    """
    identity: dict[str, Any] = {}
    code_dir = get_module_code_dir(module_name)
    if code_dir is None:
        return identity

    # -- file_info.json --
    fi_path = code_dir / "file_info.json"
    if fi_path.is_file():
        try:
            fi = json.loads(fi_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            fi = {}

        basic = fi.get("basic_file_info", {})
        if basic:
            identity["file_path"] = basic.get("file_path", "")
            identity["file_size_bytes"] = basic.get("size_bytes")
            identity["md5_hash"] = basic.get("md5_hash", "")
            identity["sha256_hash"] = basic.get("sha256_hash", "")

        ver = fi.get("pe_version_info", {})
        if ver:
            identity["file_version"] = ver.get("file_version", "")
            identity["company_name"] = ver.get("company_name", "")
            identity["product_name"] = ver.get("product_name", "")
            identity["file_description"] = ver.get("file_description", "")

        meta = fi.get("pe_metadata", {})
        if meta:
            identity["pdb_path"] = meta.get("pdb_path", "")
            identity["compilation_timestamp"] = meta.get("compilation_timestamp", "")

    # -- module_profile.json --
    mp_path = code_dir / "module_profile.json"
    if mp_path.is_file():
        try:
            mp = json.loads(mp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            mp = {}

        posture = {k: v for k, v in mp.get("security_posture", {}).items()
                   if k != "canary_coverage_pct"}
        if posture:
            identity["security_posture"] = posture

    return identity


def truncate(text: str, max_len: int = 120) -> str:
    """Truncate a string with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
