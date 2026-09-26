#!/usr/bin/env python3
"""Validate reconstructed struct layouts against assembly access patterns.

Cross-checks a generated C header file against actual ``[base+offset]``
patterns found in the x64 assembly stored in an analysis database.  For
every class method (or other function that takes a struct pointer), the
validator scans the assembly for memory accesses and verifies that each
one corresponds to a field in the header at the correct offset and size.

Reports
-------
* **match** -- assembly access matches a header field at the same offset
  and compatible size.
* **size_mismatch** -- assembly access is at a known offset but with a
  different size than the header declares.
* **missing_in_header** -- assembly accesses an offset not covered by any
  field (possible gap or undiscovered field).
* **header_only** -- a header field has no corresponding assembly access
  in any scanned function (possible false positive in scan).

Usage
-----
::

    python validate_layout.py <db_path> --header types.h --class ClassName
    python validate_layout.py <db_path> --header types.h
    python validate_layout.py <db_path> --header types.h --json

Examples
--------
::

    python validate_layout.py extracted_dbs/appinfo_dll_e98d25a9e8.db \\
        --header reconstructed_types.h --class CSecurityDescriptor
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import (
    WORKSPACE_ROOT,
    resolve_db_path,
    parse_json_safe,
)

from helpers import emit_error, open_individual_analysis_db
from helpers.assembly_prefix import strip_ea_prefix, strip_ea_prefix_multiline
from helpers.errors import ErrorCode, db_error_handler, safe_parse_args
from helpers.json_output import emit_json

# ---------------------------------------------------------------------------
# Header file parser
# ---------------------------------------------------------------------------

# Matches "struct TypeName {" or "struct TypeName\n{"
RE_STRUCT_START = re.compile(r"struct\s+(\w+)\s*\{")
# Matches field lines with offset comments: "type name; // +0xOFFSET (SIZEb)"
RE_FIELD = re.compile(
    r"^\s+(\S.*?)\s+(\w+)(?:\[[\dxXa-fA-F]+\])?;\s*//\s*\+0x([0-9A-Fa-f]+)\s*"
    r"(?:\((\d+)B\))?"
)
# Matches padding: "uint8_t _unknown_XX[0xN];" or "_padding_XX"
RE_PADDING = re.compile(r"_(?:unknown|padding)_[0-9A-Fa-f]+")
# Matches struct end: "};"
RE_STRUCT_END = re.compile(r"^\s*\}")


def parse_header(header_text: str) -> dict[str, list[dict]]:
    """Parse a C header file into struct definitions.

    Returns ``{ "StructName": [ { "offset", "size", "c_type", "field_name", "is_padding" }, ... ] }``
    """
    structs: dict[str, list[dict]] = {}
    current_struct: str | None = None
    current_fields: list[dict] = []

    for line in header_text.splitlines():
        if current_struct is None:
            m = RE_STRUCT_START.search(line)
            if m:
                current_struct = m.group(1)
                current_fields = []
            continue

        if RE_STRUCT_END.match(line):
            structs[current_struct] = current_fields
            current_struct = None
            current_fields = []
            continue

        fm = RE_FIELD.search(line)
        if fm:
            c_type = fm.group(1).strip()
            name = fm.group(2)
            offset = int(fm.group(3), 16)
            size_str = fm.group(4)
            size = int(size_str) if size_str else _guess_size_from_type(c_type)
            is_padding = bool(RE_PADDING.search(name))
            current_fields.append({
                "offset": offset,
                "size": size,
                "c_type": c_type,
                "field_name": name,
                "is_padding": is_padding,
            })

    return structs


def _guess_size_from_type(c_type: str) -> int:
    """Fallback size estimation when the comment doesn't include (NB)."""
    mapping = {
        "uint8_t": 1, "int8_t": 1, "char": 1, "bool": 1,
        "uint16_t": 2, "int16_t": 2,
        "uint32_t": 4, "int32_t": 4, "DWORD": 4, "LONG": 4, "HRESULT": 4,
        "uint64_t": 8, "int64_t": 8, "void*": 8, "size_t": 8,
    }
    return mapping.get(c_type.rstrip(" *"), 8)


# ---------------------------------------------------------------------------
# Assembly access scanning (simplified from scan_struct_fields)
# ---------------------------------------------------------------------------

# x64 registers to exclude (stack-frame accesses)
_STACK_REGS = frozenset({"rsp", "esp", "sp", "rbp", "ebp", "bp"})

# [reg+offset] in IDA assembly
_RE_ASM_MEM = re.compile(r"\[\s*([a-zA-Z]\w*)\s*\+\s*([0-9A-Fa-f]+)h?\s*\]")

# ptr qualifier
_RE_ASM_PTR = re.compile(r"(byte|word|dword|qword)\s+ptr", re.IGNORECASE)

_PTR_SIZES: dict[str, int] = {"byte": 1, "word": 2, "dword": 4, "qword": 8}

# Destination register in load/cmp/test instructions
_RE_ASM_LOAD = re.compile(r"(?:movs?[xz]?x?|lea|cmp|test)\s+(\w+)", re.IGNORECASE)

_REG_SIZES: dict[str, int] = {}
for _r in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rsp", "rbp",
           "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"):
    _REG_SIZES[_r] = 8
for _r in ("eax", "ebx", "ecx", "edx", "esi", "edi", "esp", "ebp",
           "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"):
    _REG_SIZES[_r] = 4
for _r in ("ax", "bx", "cx", "dx", "si", "di", "sp", "bp",
           "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w"):
    _REG_SIZES[_r] = 2
for _r in ("al", "bl", "cl", "dl", "sil", "dil", "spl", "bpl",
           "ah", "bh", "ch", "dh",
           "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"):
    _REG_SIZES[_r] = 1
del _r

# Prologue save: mov CALLEE_SAVED, PARAM_REG
_RE_PROLOGUE_SAVE = re.compile(
    r"mov\s+(\w+)\s*,\s*(rcx|ecx|rdx|edx|r8d?|r9d?)\b", re.IGNORECASE,
)
_PARAM_REGS: dict[str, int] = {}
for _r in ("rcx", "ecx", "cx", "cl", "ch"):
    _PARAM_REGS[_r] = 1
for _r in ("rdx", "edx", "dx", "dl", "dh"):
    _PARAM_REGS[_r] = 2
for _r in ("r8", "r8d", "r8w", "r8b"):
    _PARAM_REGS[_r] = 3
for _r in ("r9", "r9d", "r9w", "r9b"):
    _PARAM_REGS[_r] = 4
del _r


def _scan_asm_for_accesses(asm_code: str) -> list[dict]:
    """Extract struct-field accesses from x64 assembly, returning only
    those via the first parameter register (rcx / aliases).
    """
    if not asm_code:
        return []

    lines = strip_ea_prefix_multiline(asm_code).splitlines()

    # Detect prologue register aliases (e.g., mov r13, rcx)
    param_map: dict[str, int] = dict(_PARAM_REGS)
    for line in lines[:30]:
        m = _RE_PROLOGUE_SAVE.search(strip_ea_prefix(line).lower())
        if m:
            dest, src = m.group(1), m.group(2)
            pn = _PARAM_REGS.get(src, 0)
            if pn and dest not in _PARAM_REGS and dest not in _STACK_REGS:
                param_map[dest] = pn

    accesses: list[dict] = []
    for line_num, line in enumerate(lines, 1):
        low = line.lower().strip()
        if not low:
            continue

        mem = _RE_ASM_MEM.search(low)
        if not mem:
            continue

        base_reg = mem.group(1)
        if base_reg in _STACK_REGS:
            continue

        # Only accept accesses via first parameter (this / struct ptr)
        pn = param_map.get(base_reg, 0)
        if pn != 1:
            continue

        # Skip array-indexed accesses (contain *)
        bracket_start = low.index("[")
        bracket_end = low.index("]", bracket_start)
        if "*" in low[bracket_start:bracket_end]:
            continue

        byte_offset = int(mem.group(2).rstrip("hH"), 16)

        # Determine size
        size = 0
        ptr_m = _RE_ASM_PTR.search(low)
        if ptr_m:
            size = _PTR_SIZES.get(ptr_m.group(1).lower(), 0)
        if not size:
            load_m = _RE_ASM_LOAD.search(low)
            if load_m:
                size = _REG_SIZES.get(load_m.group(1).lower(), 0)
        if not size:
            size = 8

        accesses.append({
            "byte_offset": byte_offset,
            "size": size,
            "line_num": line_num,
        })

    return accesses


# ---------------------------------------------------------------------------
# Mangled name parsing (simplified)
# ---------------------------------------------------------------------------

def _class_from_mangled(mangled: str) -> str | None:
    """Extract the class name from a Microsoft C++ mangled name."""
    if not mangled or not mangled.startswith("?"):
        return None
    is_ctor = mangled.startswith("??0")
    is_dtor = mangled.startswith("??1")
    is_vdel = mangled.startswith("??_G")
    is_vftable = mangled.startswith("??_7")

    if is_vftable or is_vdel:
        rest = mangled[4:]
    elif is_ctor or is_dtor:
        rest = mangled[3:]
    else:
        rest = mangled[1:]

    parts = rest.split("@")
    try:
        end = parts.index("")
    except ValueError:
        return None

    if is_vftable or is_ctor or is_dtor or is_vdel:
        return parts[0] if end >= 1 else None

    # Regular method: ?Method@Class@...
    return parts[1] if end >= 2 else None


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

def validate_layout(
    db_path: str,
    header_structs: dict[str, list[dict]],
    class_filter: str | None = None,
) -> dict:
    """Validate header struct fields against assembly access patterns.

    Returns a per-struct validation report.
    """
    with open_individual_analysis_db(db_path) as db:
        file_info = db.get_file_info()
        # Only load class methods (functions with "::" in their name)
        # instead of all functions, since we only need class methods
        # for struct validation.
        class_methods = db.search_functions(name_contains="::")

    module_name = file_info.file_name if file_info else "(unknown)"

    # Group functions by class name
    funcs_by_class: dict[str, list] = defaultdict(list)
    for func in class_methods:
        cls = _class_from_mangled(func.mangled_name)
        if cls:
            funcs_by_class[cls].append(func)

    reports: dict[str, dict] = {}

    for struct_name, header_fields in header_structs.items():
        if class_filter:
            if class_filter.lower() not in struct_name.lower():
                continue

        # Skip padding-only structs
        real_fields = [f for f in header_fields if not f.get("is_padding")]
        if not real_fields:
            continue

        # Build offset -> header field lookup
        header_by_offset: dict[int, dict] = {f["offset"]: f for f in real_fields}

        # Find matching functions
        class_funcs = funcs_by_class.get(struct_name, [])
        if not class_funcs:
            # Try substring match
            for cls_name, funcs in funcs_by_class.items():
                if struct_name.lower() in cls_name.lower():
                    class_funcs.extend(funcs)

        if not class_funcs:
            reports[struct_name] = {
                "status": "no_functions",
                "message": f"No class methods found for {struct_name}",
                "header_fields": len(real_fields),
                "functions_scanned": 0,
                "matches": [],
                "size_mismatches": [],
                "missing_in_header": [],
                "header_only": list(header_by_offset.keys()),
            }
            continue

        # Scan assembly of all class methods
        all_asm_accesses: dict[int, dict] = {}
        functions_scanned = 0

        for func in class_funcs:
            if not func.assembly_code:
                continue
            functions_scanned += 1
            accesses = _scan_asm_for_accesses(func.assembly_code)
            for acc in accesses:
                off = acc["byte_offset"]
                if off not in all_asm_accesses:
                    all_asm_accesses[off] = {
                        "byte_offset": off,
                        "size": acc["size"],
                        "seen_in_functions": 1,
                    }
                else:
                    existing = all_asm_accesses[off]
                    existing["size"] = max(existing["size"], acc["size"])
                    existing["seen_in_functions"] += 1

        # Compare
        matches: list[dict] = []
        size_mismatches: list[dict] = []
        missing_in_header: list[dict] = []
        matched_offsets: set[int] = set()

        for off, asm_acc in sorted(all_asm_accesses.items()):
            if off in header_by_offset:
                hf = header_by_offset[off]
                matched_offsets.add(off)
                if asm_acc["size"] == hf["size"]:
                    matches.append({
                        "offset": off,
                        "offset_hex": f"0x{off:02X}",
                        "header_size": hf["size"],
                        "asm_size": asm_acc["size"],
                        "header_type": hf["c_type"],
                        "field_name": hf["field_name"],
                        "seen_in_functions": asm_acc["seen_in_functions"],
                    })
                else:
                    size_mismatches.append({
                        "offset": off,
                        "offset_hex": f"0x{off:02X}",
                        "header_size": hf["size"],
                        "asm_size": asm_acc["size"],
                        "header_type": hf["c_type"],
                        "field_name": hf["field_name"],
                        "seen_in_functions": asm_acc["seen_in_functions"],
                    })
            else:
                missing_in_header.append({
                    "offset": off,
                    "offset_hex": f"0x{off:02X}",
                    "asm_size": asm_acc["size"],
                    "seen_in_functions": asm_acc["seen_in_functions"],
                })

        header_only = sorted(set(header_by_offset.keys()) - matched_offsets)

        total_checks = len(matches) + len(size_mismatches) + len(missing_in_header)
        coverage = (len(matches) / total_checks * 100) if total_checks else 0.0

        reports[struct_name] = {
            "status": "validated",
            "header_fields": len(real_fields),
            "functions_scanned": functions_scanned,
            "asm_accesses_found": len(all_asm_accesses),
            "matches": matches,
            "match_count": len(matches),
            "size_mismatches": size_mismatches,
            "size_mismatch_count": len(size_mismatches),
            "missing_in_header": missing_in_header,
            "missing_count": len(missing_in_header),
            "header_only": header_only,
            "header_only_count": len(header_only),
            "coverage_percent": round(coverage, 1),
        }

    return {
        "module": module_name,
        "class_filter": class_filter,
        "structs_validated": len(reports),
        "reports": reports,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate reconstructed struct layouts against assembly.",
    )
    parser.add_argument("db_path", help="Path to the individual analysis DB")
    parser.add_argument(
        "--header", required=True,
        help="Path to generated C header file",
    )
    parser.add_argument(
        "--class", dest="class_name",
        help="Validate only the named class",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = safe_parse_args(parser)

    db_path = resolve_db_path(args.db_path)

    header_path = Path(args.header)
    if not header_path.is_absolute():
        header_path = WORKSPACE_ROOT / args.header
    if not header_path.exists():
        emit_error(f"Header file not found: {header_path}", ErrorCode.NOT_FOUND)

    header_text = header_path.read_text(encoding="utf-8")
    header_structs = parse_header(header_text)

    if not header_structs:
        emit_error("No struct definitions found in header file.", ErrorCode.PARSE_ERROR)

    print(
        f"Parsed {len(header_structs)} struct(s) from header: "
        f"{', '.join(sorted(header_structs))}",
        file=sys.stderr,
    )

    with db_error_handler(db_path, "validating layout"):
        result = validate_layout(db_path, header_structs, class_filter=args.class_name)

    if args.json:
        emit_json(result, default=str)
        return

    # Human-readable output
    print(f"\nModule: {result['module']}")
    print(f"Structs validated: {result['structs_validated']}\n")

    for struct_name, report in sorted(result["reports"].items()):
        print(f"{'=' * 72}")
        print(f"  {struct_name}")
        print(f"{'=' * 72}")

        if report["status"] == "no_functions":
            print(f"  {report['message']}")
            continue

        print(f"  Header fields: {report['header_fields']}")
        print(f"  Functions scanned: {report['functions_scanned']}")
        print(f"  Assembly accesses: {report['asm_accesses_found']}")
        print(
            f"  Coverage: {report['coverage_percent']:.1f}% "
            f"({report['match_count']} matches)"
        )
        print()

        if report["matches"]:
            print(f"  MATCHES ({report['match_count']}):")
            for m in report["matches"][:20]:
                print(
                    f"    {m['offset_hex']:<8} {m['field_name']:<20} "
                    f"{m['header_type']:<12} size={m['header_size']} "
                    f"(seen in {m['seen_in_functions']} func(s))"
                )
            if report["match_count"] > 20:
                print(f"    ... and {report['match_count'] - 20} more")
            print()

        if report["size_mismatches"]:
            print(f"  SIZE MISMATCHES ({report['size_mismatch_count']}):")
            for m in report["size_mismatches"]:
                print(
                    f"    {m['offset_hex']:<8} {m['field_name']:<20} "
                    f"header={m['header_size']}B  asm={m['asm_size']}B  "
                    f"(seen in {m['seen_in_functions']} func(s))"
                )
            print()

        if report["missing_in_header"]:
            print(f"  MISSING IN HEADER ({report['missing_count']}):")
            for m in report["missing_in_header"]:
                print(
                    f"    {m['offset_hex']:<8} asm_size={m['asm_size']}B  "
                    f"(seen in {m['seen_in_functions']} func(s))"
                )
            print()

        if report["header_only"]:
            print(
                f"  HEADER-ONLY FIELDS ({report['header_only_count']}): "
                f"offsets {', '.join(f'0x{o:02X}' for o in report['header_only'][:10])}"
            )
            if report["header_only_count"] > 10:
                print(f"    ... and {report['header_only_count'] - 10} more")
            print()


if __name__ == "__main__":
    main()
