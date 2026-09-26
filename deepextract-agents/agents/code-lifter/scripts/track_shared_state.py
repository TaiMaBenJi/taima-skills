#!/usr/bin/env python3
"""Manage accumulated shared state across methods during batch lifting.

The code-lifter subagent calls this script to record and retrieve state as
it lifts each method. State persists in a JSON file under
.claude/agents/code-lifter/state/<ClassName>_state.json.

Operations:

  --dump                       Print the current shared state (struct + constants + naming map)
  --record-field <class> <offset> <name> <c_type>   Record a struct field discovered during lifting
  --record-constant <name> <value>                  Record a constant (#define / enum value)
  --record-naming <ida_name> <clean_name>           Record a naming mapping (field_30 -> pDacl)
  --mark-lifted <func_name_or_id>                   Mark a function as lifted
  --record-signature <func_name_or_id> <signature>  Record the clean lifted signature for a function
  --init <class_name>                               Initialize empty state for a class (if not exists)
  --reset <class_name>                              Delete existing state and start fresh
  --list                                            List all active state files

Usage:
    # Record a struct field discovered during lifting
    python track_shared_state.py --record-field CSecurityDescriptor 0x30 pDacl PACL

    # Record a constant
    python track_shared_state.py --record-constant POLICY_DISABLED 1

    # Record a naming mapping
    python track_shared_state.py --record-naming field_30 pDacl

    # Mark a function as lifted
    python track_shared_state.py --mark-lifted CSecurityDescriptor::SetDacl

    # Record the clean signature for a lifted function
    python track_shared_state.py --record-signature CSecurityDescriptor::SetDacl \\
        "HRESULT CSecurityDescriptor::SetDacl(PACL pDacl, BOOL bDefaulted)"

    # Get current shared state
    python track_shared_state.py --dump

    # Initialize state (normally done by batch_extract.py --init-state)
    python track_shared_state.py --init CSecurityDescriptor

    # List all active state files
    python track_shared_state.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from _common import (
    STATE_DIR,
    TYPE_SIZES,
    WORKSPACE_ROOT,
    atomic_update_state,
    create_initial_state,
    get_state_file_path,
    load_state,
    save_state,
)
from helpers.errors import ErrorCode, emit_error, safe_parse_args
from helpers.json_output import emit_json
from helpers.script_runner import get_workspace_args


# ---------------------------------------------------------------------------
# State query/mutation operations
# ---------------------------------------------------------------------------


def _find_active_class() -> Optional[str]:
    """Find the most recently modified state file and return its class name.

    Reads the ``class_name`` field from the JSON content so that both
    old-format (``Name_state.json``) and new-format
    (``Name_hash8_state.json``) files are handled correctly.
    """
    if not STATE_DIR.exists():
        return None
    state_files = sorted(
        STATE_DIR.glob("*_state.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not state_files:
        return None
    try:
        data = json.loads(state_files[0].read_text(encoding="utf-8"))
        name = data.get("class_name")
        if name:
            return name
    except (json.JSONDecodeError, OSError):
        pass
    # Fallback: strip suffix from filename (legacy files without class_name key)
    return state_files[0].stem.replace("_state", "")


def _resolve_class(explicit: Optional[str] = None) -> Optional[str]:
    """Resolve the class name: use explicit if given, otherwise find active."""
    if explicit:
        return explicit
    return _find_active_class()


def dump_state(class_name: Optional[str], as_json: bool = False) -> None:
    """Print the current shared state."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state found. Specify a class name or run --init first.", ErrorCode.NOT_FOUND)

    state = load_state(class_name)
    if not state:
        emit_error(f"No state found for class '{class_name}'.", ErrorCode.NOT_FOUND)

    if as_json:
        emit_json(state)
        return

    # Human-readable output
    print(f"{'=' * 80}")
    print(f"  Shared State: {state.get('class_name', class_name)}")
    print(f"  Module: {state.get('module_name', '?')}")
    print(f"  DB: {state.get('db_path', '?')}")
    print(f"{'=' * 80}")

    # Struct definition
    struct_def = state.get("struct_definition", {})
    fields = struct_def.get("fields", [])
    print(f"\nStruct: {struct_def.get('name', class_name)} ({len(fields)} fields)")
    if fields:
        print(f"{'  Offset':<10} {'Type':<20} {'Name':<25} {'Size':<8} {'Source'}")
        print(f"  {'-' * 75}")
        for field in sorted(fields, key=lambda f: f.get("offset", 0)):
            offset = field.get("offset", 0)
            c_type = field.get("c_type", "?")
            name = field.get("name", f"field_{offset:02X}")
            size = field.get("size", "?")
            source = field.get("discovered_in", "")
            asm_tag = " [asm]" if field.get("asm_verified") else ""
            print(f"  +0x{offset:02X}    {c_type:<20} {name:<25} {size}B{asm_tag:<6} {source}")

    # Constants
    constants = state.get("constants", {})
    if constants:
        print(f"\nConstants ({len(constants)}):")
        for name, info in sorted(constants.items()):
            val = info if not isinstance(info, dict) else info.get("value", "?")
            src = info.get("discovered_in", "") if isinstance(info, dict) else ""
            print(f"  #define {name:<30} {val}" + (f"  // from {src}" if src else ""))

    # Naming map
    naming = state.get("naming_map", {})
    if naming:
        print(f"\nNaming map ({len(naming)}):")
        for ida_name, clean_name in sorted(naming.items()):
            print(f"  {ida_name:<30} -> {clean_name}")

    # Function status
    functions = state.get("functions", {})
    if functions:
        lifted = sum(1 for f in functions.values() if f.get("lifted"))
        total = len(functions)
        print(f"\nFunctions: {lifted}/{total} lifted")
        dep_order = state.get("dependency_order", [])
        ordered_ids = dep_order if dep_order else sorted(functions.keys())
        for fid_str in [str(x) for x in ordered_ids]:
            f = functions.get(fid_str, functions.get(int(fid_str) if fid_str.isdigit() else fid_str, {}))
            if not f:
                continue
            status = "[LIFTED]" if f.get("lifted") else "[      ]"
            name = f.get("function_name", f"ID={fid_str}")
            role = f.get("role", "")
            sig = f.get("clean_signature", "")
            role_str = f"  ({role})" if role else ""
            print(f"  {status} {name}{role_str}")
            if sig:
                print(f"           {sig}")

    # Lifted code snippets
    lifted_code = state.get("lifted_code", {})
    if lifted_code:
        print(f"\nLifted code stored for: {', '.join(sorted(lifted_code.keys()))}")


def record_field(
    class_name: Optional[str],
    offset_str: str,
    field_name: str,
    c_type: str,
    source_func: Optional[str] = None,
    asm_verified: bool = False,
) -> None:
    """Record a struct field discovered during lifting."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state. Run --init first.", ErrorCode.NOT_FOUND)

    # Parse offset (supports 0x30, 48, 30h)
    offset_str = offset_str.strip()
    if offset_str.startswith("0x") or offset_str.startswith("0X"):
        offset = int(offset_str, 16)
    elif offset_str.endswith("h") or offset_str.endswith("H"):
        offset = int(offset_str[:-1], 16)
    else:
        offset = int(offset_str)

    # Determine size from c_type.
    _POINTER_SIZES = {
        "uint8_t": 1, "uint16_t": 2, "uint32_t": 4, "uint64_t": 8,
        "HRESULT": 4, "BOOL": 4, "ULONGLONG": 8,
        "void*": 8, "PVOID": 8, "HANDLE": 8, "LPVOID": 8,
        "PACL": 8, "PSID": 8, "PSECURITY_DESCRIPTOR": 8,
        "LPWSTR": 8, "LPCWSTR": 8, "LPSTR": 8, "LPCSTR": 8,
        "wchar_t*": 8, "char*": 8,
    }
    size = TYPE_SIZES.get(c_type) or _POINTER_SIZES.get(c_type, 8 if "*" in c_type else 4)

    with atomic_update_state(class_name) as state:
        struct_def = state.setdefault("struct_definition", {"name": class_name, "fields": []})
        fields = struct_def.setdefault("fields", [])

        existing = None
        for i, f in enumerate(fields):
            if f.get("offset") == offset:
                existing = i
                break

        field_entry = {
            "offset": offset,
            "size": size,
            "name": field_name,
            "c_type": c_type,
        }
        if source_func:
            field_entry["discovered_in"] = source_func
        if asm_verified:
            field_entry["asm_verified"] = True

        if existing is not None:
            old = fields[existing]
            if old.get("asm_verified") and not asm_verified:
                field_entry["asm_verified"] = True
            fields[existing] = field_entry
        else:
            fields.append(field_entry)

        fields.sort(key=lambda f: f.get("offset", 0))

        ida_name = f"field_{offset:02X}"
        state.setdefault("naming_map", {})[ida_name] = field_name

    print(f"Recorded field: +0x{offset:02X} {c_type} {field_name} ({size}B)")


def record_constant(
    class_name: Optional[str],
    const_name: str,
    value_str: str,
    source_func: Optional[str] = None,
) -> None:
    """Record a constant discovered during lifting."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state. Run --init first.", ErrorCode.NOT_FOUND)

    value_str = value_str.strip()
    try:
        if value_str.startswith("0x") or value_str.startswith("0X"):
            value = int(value_str, 16)
        elif value_str.endswith("h") or value_str.endswith("H"):
            value = int(value_str[:-1], 16)
        else:
            value = int(value_str)
    except ValueError:
        value = value_str

    entry = {"value": value}
    if source_func:
        entry["discovered_in"] = source_func

    with atomic_update_state(class_name) as state:
        state.setdefault("constants", {})[const_name] = entry

    print(f"Recorded constant: #define {const_name} {value}")


def record_naming(
    class_name: Optional[str],
    ida_name: str,
    clean_name: str,
) -> None:
    """Record a naming mapping (IDA name -> clean lifted name)."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state. Run --init first.", ErrorCode.NOT_FOUND)

    with atomic_update_state(class_name) as state:
        state.setdefault("naming_map", {})[ida_name] = clean_name

    print(f"Recorded naming: {ida_name} -> {clean_name}")


def mark_lifted(class_name: Optional[str], func_identifier: str, as_json: bool = False) -> None:
    """Mark a function as lifted."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state. Run --init first.", ErrorCode.NOT_FOUND)

    with atomic_update_state(class_name) as state:
        functions = state.setdefault("functions", {})

        matched = False
        for fid_str, fdata in functions.items():
            fname = fdata.get("function_name", "")
            if (fname == func_identifier or
                    fid_str == func_identifier or
                    func_identifier in fname):
                fdata["lifted"] = True
                matched = True
                if as_json:
                    emit_json({"marked": True, "function_name": fname, "function_id": fid_str, "class_name": class_name})
                else:
                    print(f"Marked as lifted: {fname} (ID={fid_str})")
                break

        if not matched:
            # Function not in the pre-populated list (e.g. state was initialized via
            # --init without a batch extract). Auto-add a new entry so that
            # --mark-lifted works as a standalone recording operation.
            new_key = func_identifier
            functions[new_key] = {"function_name": func_identifier, "lifted": True}
            if as_json:
                emit_json({"marked": True, "function_name": func_identifier,
                           "function_id": new_key, "class_name": class_name})
            else:
                print(f"Marked as lifted (new entry): {func_identifier}")


def record_signature(
    class_name: Optional[str],
    func_identifier: str,
    signature: str,
) -> None:
    """Record the clean lifted signature for a function."""
    class_name = _resolve_class(class_name)
    if not class_name:
        emit_error("No active state. Run --init first.", ErrorCode.NOT_FOUND)

    with atomic_update_state(class_name) as state:
        functions = state.get("functions", {})
        if not functions:
            emit_error(f"No state found for '{class_name}'.", ErrorCode.NOT_FOUND)

        matched = False
        for fid_str, fdata in functions.items():
            fname = fdata.get("function_name", "")
            if (fname == func_identifier or
                    fid_str == func_identifier or
                    func_identifier in fname):
                fdata["clean_signature"] = signature
                matched = True
                print(f"Recorded signature for {fname}: {signature}")
                break

        if not matched:
            print(f"Warning: Function '{func_identifier}' not found in state.",
                  file=sys.stderr)


def init_state(class_name: str, as_json: bool = False) -> None:
    """Initialize empty state for a class.

    Idempotent: if state already exists, reports the existing path and exits
    successfully (exit 0). Use --reset to start fresh from scratch.
    """
    state_path = get_state_file_path(class_name)
    if state_path.exists():
        if as_json:
            emit_json({"class_name": class_name, "created": False,
                       "message": "State already exists (use --reset to reinitialize)",
                       "path": str(state_path)})
        else:
            print(f"State already exists for '{class_name}' at {state_path} (use --reset to reinitialize)")
        return

    state = create_initial_state(class_name, "", "", [], [])
    save_state(class_name, state)
    if as_json:
        emit_json({"class_name": class_name, "created": True,
                   "message": f"Initialized empty state for '{class_name}'",
                   "path": str(state_path)})
    else:
        print(f"Initialized empty state for '{class_name}' at {state_path}")


def reset_state(class_name: str) -> None:
    """Delete existing state and start fresh."""
    state_path = get_state_file_path(class_name)
    if state_path.exists():
        state_path.unlink()
        print(f"Deleted state for '{class_name}'")
    state = create_initial_state(class_name, "", "", [], [])
    save_state(class_name, state)
    print(f"Initialized fresh state for '{class_name}' at {state_path}")


def list_states(as_json: bool = False) -> None:
    """List all active state files."""
    if not STATE_DIR.exists():
        if as_json:
            emit_json({"state_files": []})
        else:
            print("No state directory found.")
        return

    state_files = sorted(STATE_DIR.glob("*_state.json"))
    if not state_files:
        if as_json:
            emit_json({"state_files": []})
        else:
            print("No active state files.")
        return

    entries = []
    for sf in state_files:
        try:
            state = json.loads(sf.read_text(encoding="utf-8"))
            class_name = state.get("class_name") or sf.stem.replace("_state", "")
            functions = state.get("functions", {})
            lifted = sum(1 for f in functions.values() if f.get("lifted"))
            total = len(functions)
            module = state.get("module_name", "?")
            fields = len(state.get("struct_definition", {}).get("fields", []))
            consts = len(state.get("constants", {}))
            entries.append({
                "class_name": class_name,
                "lifted": lifted,
                "total_functions": total,
                "fields": fields,
                "constants": consts,
                "module": module,
                "path": str(sf),
            })
        except Exception:
            class_name = sf.stem.replace("_state", "")
            entries.append({"class_name": class_name, "error": "failed to read state"})

    if as_json:
        emit_json({"state_files": entries, "count": len(entries)})
        return

    print(f"Active state files ({len(state_files)}):")
    for e in entries:
        if "error" in e:
            print(f"  {e['class_name']:<30} (error reading state)")
        else:
            print(f"  {e['class_name']:<30} {e['lifted']}/{e['total_functions']} lifted, "
                  f"{e['fields']} fields, {e['constants']} constants  ({e['module']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage shared state across methods during batch lifting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Query operations
    parser.add_argument("--dump", action="store_true",
                       help="Print current shared state")
    parser.add_argument("--list", action="store_true", dest="list_states",
                       help="List all active state files")

    # Mutation operations
    parser.add_argument("--record-field", nargs=4, dest="record_field",
                       metavar=("CLASS_OR_OFFSET", "OFFSET_OR_NAME", "NAME_OR_TYPE", "TYPE_OR_EXTRA"),
                       help="Record a struct field: <class> <offset> <name> <c_type>")
    parser.add_argument("--record-constant", nargs=2, dest="record_constant",
                       metavar=("NAME", "VALUE"),
                       help="Record a constant")
    parser.add_argument("--record-naming", nargs=2, dest="record_naming",
                       metavar=("IDA_NAME", "CLEAN_NAME"),
                       help="Record a naming mapping")
    parser.add_argument("--mark-lifted", dest="mark_lifted",
                       metavar="FUNC",
                       help="Mark a function as lifted")
    parser.add_argument("--record-signature", nargs=2, dest="record_signature",
                       metavar=("FUNC", "SIGNATURE"),
                       help="Record the clean lifted signature for a function")
    parser.add_argument("--init", dest="init_class",
                       metavar="CLASS",
                       help="Initialize empty state for a class")
    parser.add_argument("--reset", dest="reset_class",
                       metavar="CLASS",
                       help="Delete existing state and start fresh")

    # Common options
    parser.add_argument("--class", dest="class_name",
                       help="Explicit class name (auto-detected from latest state if omitted)")
    parser.add_argument("--source", dest="source_func",
                       help="Source function name (for --record-field and --record-constant)")
    parser.add_argument("--asm-verified", action="store_true",
                       help="Mark field as assembly-verified (for --record-field)")
    parser.add_argument("--json", action="store_true",
                       help="JSON output (works with --dump, --list, --mark-lifted)")
    args = safe_parse_args(parser)

    # Force JSON output when workspace mode is active so bootstrap captures
    # structured data instead of human-readable text.
    ws_args = get_workspace_args(args)
    force_json = args.json or bool(ws_args["workspace_dir"])

    try:
        if args.list_states:
            list_states(as_json=force_json)
        elif args.init_class:
            init_state(args.init_class, as_json=force_json)
        elif args.reset_class:
            reset_state(args.reset_class)
        elif args.dump:
            dump_state(args.class_name, as_json=force_json)
        elif args.record_field:
            # Parse: class offset name c_type
            cls, offset, name, c_type = args.record_field
            record_field(
                class_name=cls,
                offset_str=offset,
                field_name=name,
                c_type=c_type,
                source_func=args.source_func,
                asm_verified=args.asm_verified,
            )
        elif args.record_constant:
            const_name, value = args.record_constant
            record_constant(args.class_name, const_name, value, args.source_func)
        elif args.record_naming:
            ida_name, clean_name = args.record_naming
            record_naming(args.class_name, ida_name, clean_name)
        elif args.mark_lifted:
            mark_lifted(args.class_name, args.mark_lifted, as_json=force_json)
        elif args.record_signature:
            func, sig = args.record_signature
            record_signature(args.class_name, func, sig)
        else:
            # Default: dump state if it exists, otherwise show help
            active = _find_active_class()
            if active:
                dump_state(active, as_json=force_json)
            else:
                parser.print_help()
    except Exception as e:
        emit_error(f"{type(e).__name__}: {e}", ErrorCode.UNKNOWN)


if __name__ == "__main__":
    main()
