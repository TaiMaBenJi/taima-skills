#!/usr/bin/env python3
"""Extract everything needed to explain a function in one pass.

Combines: decompiled code + assembly + classification + call chain summary +
string context + module role. Designed to output exactly what the re-analyst
subagent prompt needs for a comprehensive function explanation.

Usage:
    python explain_function.py <db_path> <function_name>
    python explain_function.py <db_path> --id <function_id>
    python explain_function.py <db_path> <function_name> --depth 2
    python explain_function.py <db_path> <function_name> --depth 4 --output-file /tmp/out.json
    python explain_function.py <db_path> <function_name> --no-assembly
    python explain_function.py <db_path> <function_name> --json

Examples:
    python explain_function.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiCheckSecureApplicationDirectory
    python explain_function.py extracted_dbs/cmd_exe_6d109a3a00.db --id 42 --depth 2
    python explain_function.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess --depth 4 --output-file out.json

Output:
    Structured explanation context including:
    - Module context (what binary, what it does, security features)
    - Function identity (signatures, mangled name, class membership)
    - Classification (category, interest, signals)
    - Decompiled code + assembly
    - Call chain (outbound classified as internal/external/resolvable)
    - Inbound callers (who calls this)
    - String context (categorized)
    - Dangerous API calls
    - Loop/complexity metrics
    - Callee details: BFS recursive traversal of the call chain to --depth
      levels, with boilerplate (WIL/CRT/ETW thunks) filtered out.  Each
      callee includes a depth field (1=direct, 2=callee-of-callee, etc.).
      Use --output-file for large call chains to avoid stdout truncation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Shared utilities (workspace root, bootstrap, DB resolution, helpers)
# ---------------------------------------------------------------------------
from _common import (  # noqa: E402
    WORKSPACE_ROOT as _WORKSPACE_ROOT,
    classify_api_safe as _classify_api_safe,
    emit_error,
    get_classify_function as _get_classify,
    get_function_id,
    load_function_index_for_db,
    load_skill_module,
    open_analyzed_files_db,
    open_individual_analysis_db,
    parse_json_safe,
    resolve_db_path as _resolve_db_path,
    resolve_function,
)
from helpers.errors import ErrorCode, db_error_handler, emit_error, log_warning, safe_parse_args  # noqa: E402
from helpers.function_index import is_library_function  # noqa: E402
from helpers.json_output import emit_json  # noqa: E402
from helpers.script_runner import get_workspace_args  # noqa: E402
from helpers.cross_module_graph import ModuleResolver  # noqa: E402
from helpers.validation import validate_depth, validate_function_id  # noqa: E402


# ---------------------------------------------------------------------------
# Cross-module resolution (delegates to shared ModuleResolver helper)
# ---------------------------------------------------------------------------
_module_resolver: Optional[ModuleResolver] = None


def _get_module_resolver() -> ModuleResolver:
    global _module_resolver
    if _module_resolver is None:
        _module_resolver = ModuleResolver()
    return _module_resolver


def _resolve_external_modules(outbound_xrefs: list[dict]) -> dict[str, Optional[str]]:
    """For external calls, find which analyzed modules implement them."""
    external_modules: dict[str, Optional[str]] = {}
    module_names: set[str] = set()

    for xref in outbound_xrefs:
        fid = xref.get("function_id")
        module_name = xref.get("module_name", "")
        if fid is None and module_name and module_name not in ("data", "vtable", "internal", "static_library"):
            module_names.add(module_name)

    if not module_names:
        return external_modules

    resolver = _get_module_resolver()
    for mod_name in module_names:
        entry = resolver.get_module_db(mod_name)
        external_modules[mod_name] = entry[0] if entry else None

    return external_modules


# ---------------------------------------------------------------------------
# Callee detail extraction -- BFS recursive traversal
# ---------------------------------------------------------------------------

_LINE_LIMITS_BY_DEPTH = {1: 80, 2: 40}
_LINE_LIMIT_DEEP = 20


def _truncate_code(code: str, depth_level: int) -> str:
    """Truncate decompiled code based on call-chain depth level."""
    limit = _LINE_LIMITS_BY_DEPTH.get(depth_level, _LINE_LIMIT_DEEP)
    lines = code.splitlines()
    if len(lines) <= limit:
        return code
    return "\n".join(lines[:limit]) + f"\n// ... ({len(lines) - limit} more lines)"


_WIL_INFRASTRUCTURE_PREFIXES = (
    "wil::", "wistd::", "wil_", "?", "_Tlg", "_lambda_",
)


def _is_boilerplate(fname: str, function_index: Optional[dict]) -> bool:
    """Return True if the function is library/boilerplate (WIL, CRT, ETW, thunks).

    WIL-tagged functions are only treated as boilerplate when their name
    matches known WIL/STL infrastructure patterns (``wil::``, ``wistd::``,
    mangled ``?``-prefix names, ``_Tlg`` trace-logging helpers, etc.).
    Application functions that merely *consume* WIL types (e.g. accept
    ``wil::unique_any_t`` params) are often mis-tagged "WIL" by the
    extraction pipeline and should not be filtered out.
    """
    if function_index:
        entry = function_index.get(fname)
        if entry is not None:
            tag = entry.get("library")
            if tag is None:
                return False
            if tag == "WIL":
                return any(fname.startswith(p) for p in _WIL_INFRASTRUCTURE_PREFIXES)
            return True
    return False


def _fetch_internal_callee(
    db, fname: str, fid: int, depth_level: int,
) -> Optional[dict]:
    """Fetch an internal callee's decompiled code + outbound xrefs."""
    func = db.get_function_by_id(fid)
    if not func or not func.decompiled_code:
        return None
    return {
        "function_name": fname,
        "function_id": fid,
        "location": "internal",
        "depth": depth_level,
        "signature": func.function_signature,
        "decompiled_code_excerpt": _truncate_code(func.decompiled_code, depth_level),
        "_outbound_xrefs": parse_json_safe(func.simple_outbound_xrefs) or [],
    }


def _fetch_external_callee(
    ext_db: str, fname: str, module_name: str, depth_level: int,
) -> Optional[dict]:
    """Fetch an external callee's decompiled code + outbound xrefs."""
    try:
        with open_individual_analysis_db(ext_db) as edb:
            ext_index = load_function_index_for_db(ext_db)
            func = None
            if ext_index:
                entry = ext_index.get(fname)
                if entry and bool(entry.get("has_decompiled", False)):
                    fid = get_function_id(entry)
                    if fid is not None:
                        func = edb.get_function_by_id(fid)
            if func is None:
                results = edb.get_function_by_name(fname)
                if results:
                    func = results[0]
            if func and func.decompiled_code:
                return {
                    "function_name": fname,
                    "function_id": func.function_id,
                    "location": f"external ({module_name})",
                    "module_db": ext_db,
                    "depth": depth_level,
                    "signature": func.function_signature,
                    "decompiled_code_excerpt": _truncate_code(
                        func.decompiled_code, depth_level,
                    ),
                    "_outbound_xrefs": parse_json_safe(func.simple_outbound_xrefs) or [],
                }
    except Exception as exc:
        log_warning(f"Failed to access external module {module_name}: {exc}", ErrorCode.DB_ERROR)
    return None


def _get_callee_details_recursive(
    db_path: str,
    outbound_xrefs: list[dict],
    external_module_dbs: dict[str, Optional[str]],
    max_depth: int = 1,
) -> list[dict]:
    """BFS traversal of the call chain, fetching decompiled code at each level.

    Filters boilerplate (WIL/CRT/ETW thunks) via ``is_library_function``.
    Tracks a global ``seen`` set to avoid cycles.  Each result carries a
    ``depth`` field (1 = direct callee, 2 = callee-of-callee, etc.).
    """
    results: list[dict] = []
    seen: set[str] = set()
    function_index = load_function_index_for_db(db_path)

    queue: list[tuple[list[dict], int, str]] = [
        (outbound_xrefs, 1, db_path),
    ]

    while queue:
        xrefs, current_depth, current_db = queue.pop(0)
        if current_depth > max_depth:
            continue

        internal_xrefs = []
        external_xrefs = []
        for xref in xrefs:
            if not isinstance(xref, dict):
                continue
            ftype = xref.get("function_type", 0)
            if ftype in (4, 8):
                continue
            fname = xref.get("function_name", "")
            if not fname or fname in seen:
                continue
            fid = xref.get("function_id")
            if fid is not None:
                internal_xrefs.append(xref)
            else:
                external_xrefs.append(xref)

        with open_individual_analysis_db(current_db) as db:
            for xref in internal_xrefs:
                fname = xref["function_name"]
                if fname in seen:
                    continue
                if _is_boilerplate(fname, function_index):
                    seen.add(fname)
                    continue
                seen.add(fname)

                fid = xref.get("function_id")
                if fid is None:
                    continue
                entry = _fetch_internal_callee(db, fname, fid, current_depth)
                if entry is None:
                    continue
                child_xrefs = entry.pop("_outbound_xrefs")
                results.append(entry)
                if current_depth < max_depth and child_xrefs:
                    queue.append((child_xrefs, current_depth + 1, current_db))

        for xref in external_xrefs:
            fname = xref.get("function_name", "")
            if not fname or fname in seen:
                continue
            module_name = xref.get("module_name", "")
            if module_name in ("data", "vtable", "internal", "static_library"):
                continue
            seen.add(fname)

            ext_db = external_module_dbs.get(module_name)
            if ext_db is None:
                continue

            entry = _fetch_external_callee(ext_db, fname, module_name, current_depth)
            if entry is None:
                continue
            child_xrefs = entry.pop("_outbound_xrefs")
            results.append(entry)
            if current_depth < max_depth and child_xrefs:
                ext_module_dbs_for_child = _resolve_external_modules(child_xrefs)
                ext_module_dbs_for_child.update(external_module_dbs)
                queue.append((child_xrefs, current_depth + 1, ext_db))

    return results


# ---------------------------------------------------------------------------
# Main explain function
# ---------------------------------------------------------------------------
def explain_function(
    db_path: str,
    function_name: Optional[str] = None,
    function_id: Optional[int] = None,
    depth: int = 1,
    include_assembly: bool = True,
    as_json: bool = False,
    output_file: Optional[str] = None,
) -> None:
    """Generate complete explanation context for a function."""
    function_index = load_function_index_for_db(db_path)
    with open_individual_analysis_db(db_path) as db:
        func, err = resolve_function(
            db,
            name=function_name,
            function_id=function_id,
            function_index=function_index,
        )
        if err:
            if "Multiple matches" in err:
                emit_error(f"[{Path(db_path).stem}] {err}", ErrorCode.AMBIGUOUS)
            emit_error(f"[{Path(db_path).stem}] {err}", ErrorCode.NOT_FOUND)

        # Get module context
        fi = db.get_file_info()

    # Parse all JSON fields
    outbound = parse_json_safe(func.simple_outbound_xrefs) or []
    inbound = parse_json_safe(func.simple_inbound_xrefs) or []
    strings = parse_json_safe(func.string_literals) or []
    dangerous = parse_json_safe(func.dangerous_api_calls) or []
    loops = parse_json_safe(func.loop_analysis) or {}
    stack = parse_json_safe(func.stack_frame) or {}
    globals_acc = parse_json_safe(func.global_var_accesses) or []
    vtable_ctx = parse_json_safe(func.vtable_contexts) or []

    # Classification
    classify_func = _get_classify()
    classification = None
    if classify_func:
        try:
            result = classify_func(func)
            classification = result.to_dict()
        except Exception:
            pass

    # Classify outbound calls
    call_internal = []
    call_external_resolvable = []
    call_external_unresolvable = []
    for xref in outbound:
        if not isinstance(xref, dict):
            continue
        ftype = xref.get("function_type", 0)
        if ftype in (4, 8):  # data/vtable refs
            continue
        fname = xref.get("function_name", "?")
        fid = xref.get("function_id")
        module_name = xref.get("module_name", "")

        # Classify the API
        api_cat = _classify_api_safe(fname)

        entry = {
            "function_name": fname,
            "function_id": fid,
            "module_name": module_name,
            "api_category": api_cat,
        }

        if fid is not None:
            call_internal.append(entry)
        elif module_name in ("data", "vtable"):
            continue
        else:
            entry["_module"] = module_name
            # Will classify as resolvable/unresolvable after checking modules
            call_external_resolvable.append(entry)  # tentative

    # Resolve external modules
    external_module_dbs = _resolve_external_modules(outbound)
    # Re-classify external calls
    final_external_resolvable = []
    final_external_unresolvable = []
    for call in call_external_resolvable:
        mod = call.get("_module", "")
        db_resolved = external_module_dbs.get(mod)
        call.pop("_module", None)
        if db_resolved:
            call["resolved_db"] = db_resolved
            final_external_resolvable.append(call)
        else:
            final_external_unresolvable.append(call)

    # Pass strings through uncategorized
    string_categories = {"other": list(strings)} if isinstance(strings, list) and strings else {}

    # Get callee details recursively if depth > 0
    callee_details = []
    if depth >= 1:
        callee_details = _get_callee_details_recursive(
            db_path, outbound, external_module_dbs,
            max_depth=depth,
        )

    # Module context
    module_context = {}
    if fi:
        module_context = {
            "file_name": fi.file_name,
            "file_description": fi.file_description or "",
            "company_name": fi.company_name or "",
            "product_name": fi.product_name or "",
            "file_version": fi.file_version or "",
            "pdb_path": fi.pdb_path or "",
        }

    # Determine if function is an export
    is_export = False
    if fi:
        exports = parse_json_safe(fi.exports) or []
        if isinstance(exports, list):
            fname = func.function_name or ""
            for exp in exports:
                if isinstance(exp, dict) and exp.get("function_name") == fname:
                    is_export = True
                    break

    # Build output structure
    data = {
        "module_context": module_context,
        "identity": {
            "function_id": func.function_id,
            "function_name": func.function_name,
            "function_signature": func.function_signature,
            "function_signature_extended": func.function_signature_extended,
            "mangled_name": func.mangled_name,
            "is_export": is_export,
            "class_name": func.function_name.split("::")[0] if "::" in (func.function_name or "") else None,
        },
        "classification": classification,
        "code": {
            "decompiled": func.decompiled_code,
            "assembly": func.assembly_code if include_assembly else "(omitted -- use --no-assembly to exclude)",
        },
        "call_chain": {
            "internal_calls": call_internal,
            "external_resolvable": final_external_resolvable,
            "external_unresolvable": final_external_unresolvable,
            "total_outbound": len(call_internal) + len(final_external_resolvable) + len(final_external_unresolvable),
        },
        "inbound_callers": [
            {"function_name": x.get("function_name", "?"), "function_id": x.get("function_id")}
            for x in inbound if isinstance(x, dict)
        ],
        "string_literals": list(strings) if isinstance(strings, list) else [],
        "strings": {
            "total": len(strings) if isinstance(strings, list) else 0,
            "by_category": string_categories,
        },
        "dangerous_apis": [
            {"api": api} if isinstance(api, str) else api
            for api in (dangerous if isinstance(dangerous, list) else [])
        ],
        "complexity": {
            "loop_count": loops.get("loop_count", 0) if isinstance(loops, dict) else 0,
            "loops": loops.get("loops", []) if isinstance(loops, dict) else [],
            "local_vars_size": stack.get("local_vars_size") if isinstance(stack, dict) else None,
        },
        "global_accesses": globals_acc[:20] if isinstance(globals_acc, list) else [],
        "vtable_contexts": vtable_ctx[:5] if isinstance(vtable_ctx, list) else [],
        "callee_details": callee_details,
    }

    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        callee_count = len(callee_details)
        max_level = max((c.get("depth", 1) for c in callee_details), default=0)
        print(f"Wrote {callee_count} callees across {max_level} levels to {out_path}")
        return

    if as_json:
        emit_json(data)
        return

    # Human-readable output
    _print_text_explain(data, include_assembly)


def _print_text_explain(data: dict, include_assembly: bool) -> None:
    """Print human-readable explanation context."""
    mc = data["module_context"]
    ident = data["identity"]
    cls = data["classification"]
    cc = data["call_chain"]
    strings = data["strings"]
    complexity = data["complexity"]

    print(f"{'#' * 80}")
    print(f"  FUNCTION EXPLANATION CONTEXT")
    print(f"{'#' * 80}")

    # Module context
    print(f"\n  Module:        {mc.get('file_name', '?')}")
    if mc.get("file_description"):
        print(f"  Description:   {mc['file_description']}")

    # Identity
    print(f"\n  Function:      {ident['function_name']}")
    print(f"  ID:            {ident['function_id']}")
    if ident.get("class_name"):
        print(f"  Class:         {ident['class_name']}")
    print(f"  Exported:      {'YES' if ident['is_export'] else 'no'}")
    if ident["function_signature"]:
        print(f"  Signature:     {ident['function_signature']}")
    if ident["function_signature_extended"] and ident["function_signature_extended"] != ident["function_signature"]:
        print(f"  Sig Extended:  {ident['function_signature_extended']}")
    if ident["mangled_name"]:
        print(f"  Mangled:       {ident['mangled_name']}")

    # Classification
    if cls:
        print(f"\n{'=' * 60}")
        print(f"  CLASSIFICATION")
        print(f"{'=' * 60}")
        print(f"  Category:      {cls['primary_category']}")
        if cls.get("secondary_categories"):
            print(f"  Secondary:     {', '.join(cls['secondary_categories'])}")
        print(f"  Interest:      {cls['interest_score']}/10")
        if cls.get("signals"):
            for cat, sigs in cls["signals"].items():
                for sig in sigs:
                    print(f"    [{cat}] {sig}")

    # Dangerous APIs
    if data["dangerous_apis"]:
        print(f"\n{'=' * 60}")
        print(f"  DANGEROUS APIs ({len(data['dangerous_apis'])})")
        print(f"{'=' * 60}")
        for api in data["dangerous_apis"]:
            name = api["api"] if isinstance(api, dict) else api
            print(f"  !! {name}")

    # Complexity
    print(f"\n{'=' * 60}")
    print(f"  COMPLEXITY")
    print(f"{'=' * 60}")
    print(f"  Loops:         {complexity['loop_count']}")
    if complexity.get("local_vars_size") is not None:
        print(f"  Stack frame:   {complexity['local_vars_size']} bytes local vars")

    # Call chain
    print(f"\n{'=' * 60}")
    print(f"  CALL CHAIN ({cc['total_outbound']} outbound calls)")
    print(f"{'=' * 60}")
    if cc["internal_calls"]:
        print(f"\n  Internal ({len(cc['internal_calls'])}):")
        for c in cc["internal_calls"]:
            cat_tag = f" [{c['api_category']}]" if c.get("api_category") else ""
            print(f"    -> {c['function_name']}{cat_tag}  [ID={c['function_id']}]")
    if cc["external_resolvable"]:
        print(f"\n  External - RESOLVABLE ({len(cc['external_resolvable'])}):")
        for c in cc["external_resolvable"]:
            cat_tag = f" [{c['api_category']}]" if c.get("api_category") else ""
            print(f"    -> {c['function_name']} ({c['module_name']}){cat_tag}")
    if cc["external_unresolvable"]:
        print(f"\n  External - unresolvable ({len(cc['external_unresolvable'])}):")
        for c in cc["external_unresolvable"]:
            cat_tag = f" [{c['api_category']}]" if c.get("api_category") else ""
            print(f"    -> {c['function_name']} ({c['module_name']}){cat_tag}")

    # Inbound callers
    if data["inbound_callers"]:
        shown = data["inbound_callers"][:10]
        total = len(data["inbound_callers"])
        print(f"\n{'=' * 60}")
        print(f"  INBOUND CALLERS ({total} total)")
        print(f"{'=' * 60}")
        for c in shown:
            fid = f" [ID={c['function_id']}]" if c["function_id"] else ""
            print(f"    <- {c['function_name']}{fid}")
        if total > 10:
            print(f"    ... and {total - 10} more")

    # Strings
    if strings["total"] > 0:
        print(f"\n{'=' * 60}")
        print(f"  STRINGS ({strings['total']} total)")
        print(f"{'=' * 60}")
        for cat, strs in strings["by_category"].items():
            if cat == "other":
                continue
            print(f"\n  [{cat}] ({len(strs)}):")
            for s in strs[:5]:
                display = s if len(s) <= 70 else s[:67] + "..."
                print(f"    \"{display}\"")
            if len(strs) > 5:
                print(f"    ... and {len(strs) - 5} more")
        other = strings["by_category"].get("other", [])
        if other:
            print(f"\n  [other] ({len(other)}):")
            for s in other[:5]:
                display = s if len(s) <= 70 else s[:67] + "..."
                print(f"    \"{display}\"")
            if len(other) > 5:
                print(f"    ... and {len(other) - 5} more")

    # Global accesses
    if data["global_accesses"]:
        print(f"\n{'=' * 60}")
        print(f"  GLOBAL VARIABLE ACCESSES ({len(data['global_accesses'])})")
        print(f"{'=' * 60}")
        for g in data["global_accesses"][:10]:
            if isinstance(g, dict):
                print(f"    {g.get('access_type', '?'):>5}  {g.get('name', g.get('address', '?'))}")

    # VTable contexts
    if data["vtable_contexts"]:
        print(f"\n{'=' * 60}")
        print(f"  VTABLE CONTEXTS ({len(data['vtable_contexts'])})")
        print(f"{'=' * 60}")
        for vt in data["vtable_contexts"]:
            if isinstance(vt, dict):
                classes = vt.get("reconstructed_classes", [])
                for cls_str in classes[:3]:
                    # Truncate long class skeletons
                    if len(cls_str) > 200:
                        cls_str = cls_str[:197] + "..."
                    print(f"    {cls_str}")

    # Decompiled code
    code = data["code"]["decompiled"]
    if code and code.strip():
        lines = code.splitlines()
        print(f"\n{'=' * 60}")
        print(f"  DECOMPILED CODE ({len(lines)} lines)")
        print(f"{'=' * 60}")
        if len(lines) > 120:
            for line in lines[:100]:
                print(line)
            print(f"\n... ({len(lines) - 100} more lines)")
        else:
            print(code)

    # Assembly
    if include_assembly:
        asm = data["code"]["assembly"]
        if asm and asm.strip():
            asm_lines = asm.splitlines()
            print(f"\n{'=' * 60}")
            print(f"  ASSEMBLY ({len(asm_lines)} lines)")
            print(f"{'=' * 60}")
            if len(asm_lines) > 80:
                for line in asm_lines[:60]:
                    print(line)
                print(f"\n... ({len(asm_lines) - 60} more lines)")
            else:
                print(asm)

    # Callee details (grouped by depth level)
    if data["callee_details"]:
        max_level = max((c.get("depth", 1) for c in data["callee_details"]), default=1)
        print(f"\n{'=' * 60}")
        print(f"  CALLEE CODE ({len(data['callee_details'])} functions, {max_level} levels)")
        print(f"{'=' * 60}")
        for callee in data["callee_details"]:
            lvl = callee.get("depth", 1)
            print(f"\n  --- {callee['function_name']} [L{lvl}] ({callee['location']}) ---")
            if callee.get("signature"):
                print(f"  Signature: {callee['signature']}")
            if callee.get("decompiled_code_excerpt"):
                print(callee["decompiled_code_excerpt"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract everything needed to explain a function.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument("function_name", nargs="?", help="Function name to explain")
    parser.add_argument("--id", type=int, dest="function_id", help="Function ID to explain")
    parser.add_argument("--depth", type=int, default=1,
                        help="Recursive call chain depth (0=none, 1=direct callees only, 2=callees of callees, ...). "
                             "Boilerplate (WIL/CRT/ETW) is filtered automatically. Default: 1")
    parser.add_argument("--no-assembly", action="store_true",
                        help="Omit assembly code from output (shorter output)")
    parser.add_argument("--output-file", dest="output_file", default=None,
                        help="Write full JSON output to this file instead of stdout (avoids truncation for large call chains)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    if not args.function_name and args.function_id is None:
        emit_error("Provide a function name or --id", ErrorCode.INVALID_ARGS)

    if args.function_id is not None:
        args.function_id = validate_function_id(args.function_id)

    args.depth = validate_depth(args.depth, max_depth=5)

    ws_args = get_workspace_args(args)
    force_json = args.json or bool(ws_args["workspace_dir"])

    db_path = _resolve_db_path(args.db_path)
    with db_error_handler(db_path, "explain_function"):
        explain_function(
            db_path,
            function_name=args.function_name,
            function_id=args.function_id,
            depth=args.depth,
            include_assembly=not args.no_assembly,
            as_json=force_json,
            output_file=args.output_file,
        )


if __name__ == "__main__":
    main()
