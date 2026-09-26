#!/usr/bin/env python3
"""Merge raw struct field scan results into conflict-resolved struct layouts.

Takes scan output from ``scan_struct_fields.py`` (or reconstruct_all.py
intermediate JSON) and produces unified, conflict-resolved struct definitions
with padding inference and per-field confidence scoring.

Merge rules
-----------
* **Wider type wins** -- when two functions access the same offset with
  different sizes (e.g., ``_DWORD`` and ``_QWORD``), the larger size is kept.
* **Assembly is authoritative** -- if any access is ``asm_verified``, the
  assembly-derived size takes precedence.
* **Padding inference** -- gaps between known fields are filled with
  ``uint8_t _padding_XX[N]`` arrays.
* **Confidence scoring** -- each field receives a confidence level
  (``high`` / ``medium`` / ``low``) based on the number of source functions,
  assembly verification, and access-type diversity.

When COM scan data is provided (``--com-data``), COM vtable layouts are
merged into the corresponding class structs as ``void* vtable`` pointer
fields at offset 0x00 (and secondary vtable pointers for multiple
inheritance at the appropriate offsets).

Usage
-----
::

    python merge_evidence.py --scan-output scan.json
    python merge_evidence.py --scan-output scan.json --class ClassName
    python merge_evidence.py --scan-output scan.json --com-data com_scan.json
    python merge_evidence.py --scan-output scan.json --json
    python merge_evidence.py --scan-output scan.json --output merged.json

Examples
--------
::

    python merge_evidence.py --scan-output appinfo_fields.json --class CSecurityDescriptor
    python merge_evidence.py --scan-output appinfo_fields.json --com-data appinfo_com.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from _common import (
    IDA_TO_C_TYPE,
    MAX_ALIGNMENT,
    SIZE_TO_C_TYPE,
    aligned_offset,
    compute_confidence,
    parse_json_safe,
)
from helpers.errors import emit_error, ErrorCode, safe_parse_args


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

def merge_evidence(
    scan_data: dict,
    com_data: dict | None = None,
    class_filter: str | None = None,
) -> dict:
    """Merge raw per-function field scan results into refined struct layouts.

    Parameters
    ----------
    scan_data : dict
        Output of ``scan_struct_fields.py --json`` (must include
        ``merged_types`` and ``per_function`` keys).
    com_data : dict, optional
        Output of ``scan_com_interfaces.py --json``.  When provided, COM
        vtable information is merged into the struct layouts.
    class_filter : str, optional
        When set, only merge the named class (case-insensitive substring).

    Returns
    -------
    dict
        ``{ "module": str, "merged_types": { TypeName: { ... } }, ... }``
    """
    module = scan_data.get("module", "(unknown)")
    raw_merged = scan_data.get("merged_types", {})

    if class_filter:
        lower = class_filter.lower()
        raw_merged = {
            k: v for k, v in raw_merged.items()
            if lower in k.lower()
        }

    # Build COM vtable map: class_name -> list of vtable method dicts
    com_vtables: dict[str, list[dict]] = {}
    com_classes: set[str] = set()
    if com_data:
        for vtbl in com_data.get("vtable_interfaces", []):
            cls_name = vtbl.get("class_name", "")
            if cls_name and vtbl.get("is_com"):
                com_vtables.setdefault(cls_name, []).append(vtbl)
        com_classes = set(com_data.get("com_classes", []))

    refined: dict[str, dict] = {}

    for type_name, type_data in raw_merged.items():
        raw_fields = type_data.get("fields", [])
        source_count = type_data.get("total_source_functions", 0)

        # Merge overlapping fields at the same offset
        by_offset: dict[int, dict] = {}
        for field in raw_fields:
            off = field["byte_offset"]
            access_types = set(field.get("access_types", []))
            src_funcs = field.get("source_functions", [])
            asm_verified = field.get("asm_verified", False)

            if off not in by_offset:
                by_offset[off] = {
                    "byte_offset": off,
                    "size": field["size"],
                    "access_types": access_types,
                    "source_functions": list(src_funcs),
                    "asm_verified": asm_verified,
                }
            else:
                existing = by_offset[off]
                # Wider type wins; assembly-verified size is authoritative
                if asm_verified and not existing["asm_verified"]:
                    existing["size"] = field["size"]
                elif asm_verified and existing["asm_verified"]:
                    existing["size"] = max(existing["size"], field["size"])
                elif not existing["asm_verified"]:
                    existing["size"] = max(existing["size"], field["size"])
                existing["access_types"] |= access_types
                existing["asm_verified"] = existing["asm_verified"] or asm_verified
                for fn in src_funcs:
                    if fn not in existing["source_functions"]:
                        existing["source_functions"].append(fn)

        # Sort by offset and build annotated field list
        sorted_fields = sorted(by_offset.values(), key=lambda f: f["byte_offset"])

        # Inject COM vtable pointer at offset 0 if applicable
        is_com_class = type_name in com_classes or type_name in com_vtables
        if is_com_class and (not sorted_fields or sorted_fields[0]["byte_offset"] != 0):
            sorted_fields.insert(0, {
                "byte_offset": 0,
                "size": 8,
                "access_types": {"vtable_ptr"},
                "source_functions": ["(COM vtable)"],
                "asm_verified": False,
                "is_vtable_ptr": True,
            })
        elif is_com_class and sorted_fields and sorted_fields[0]["byte_offset"] == 0:
            sorted_fields[0]["is_vtable_ptr"] = True

        # Infer padding and annotate with confidence
        annotated: list[dict] = []
        current_offset = 0

        for field in sorted_fields:
            off = field["byte_offset"]
            size = field["size"]

            # Insert padding for gaps
            if off > current_offset:
                gap = off - current_offset
                annotated.append({
                    "byte_offset": current_offset,
                    "offset_hex": f"0x{current_offset:02X}",
                    "size": gap,
                    "c_type": f"uint8_t",
                    "field_name": f"_padding_{current_offset:02X}",
                    "is_padding": True,
                    "array_size": gap,
                    "confidence": "none",
                    "confidence_score": 0.0,
                    "source_functions": [],
                    "asm_verified": False,
                })

            # Determine C type
            c_type = _best_c_type(field)

            # Compute confidence
            access_types = field.get("access_types", set())
            # Filter out asm_ synthetic types for diversity count
            real_types = {t for t in access_types if not t.startswith("asm_") and t != "vtable_ptr"}
            confidence_label, confidence_score = compute_confidence(
                source_count=len(field.get("source_functions", [])),
                asm_verified=field.get("asm_verified", False),
                access_type_count=len(real_types),
            )

            annotated.append({
                "byte_offset": off,
                "offset_hex": f"0x{off:02X}",
                "size": size,
                "c_type": c_type,
                "field_name": f"field_{off:02X}",
                "is_padding": False,
                "is_vtable_ptr": field.get("is_vtable_ptr", False),
                "access_types": sorted(access_types),
                "confidence": confidence_label,
                "confidence_score": confidence_score,
                "source_functions": field.get("source_functions", []),
                "asm_verified": field.get("asm_verified", False),
            })

            current_offset = off + size

        # Attach COM interface info if available
        com_info = None
        if type_name in com_vtables:
            com_info = []
            for vtbl in com_vtables[type_name]:
                com_info.append({
                    "base_interface": vtbl.get("base_interface"),
                    "slot_count": vtbl.get("slot_count"),
                    "confidence": vtbl.get("confidence"),
                    "methods": vtbl.get("methods", []),
                })

        refined[type_name] = {
            "fields": annotated,
            "total_known_size": current_offset,
            "total_source_functions": source_count,
            "field_count": len([f for f in annotated if not f["is_padding"]]),
            "padding_count": len([f for f in annotated if f["is_padding"]]),
            "is_com_class": is_com_class,
            "com_interfaces": com_info,
        }

    return {
        "module": module,
        "class_filter": class_filter,
        "types_merged": len(refined),
        "merged_types": refined,
    }


def _best_c_type(field: dict) -> str:
    """Determine the best C type for a merged field."""
    if field.get("is_vtable_ptr"):
        return "void*"

    # Prefer IDA decompiled types over raw assembly types
    for t in sorted(field.get("access_types", set())):
        if t in IDA_TO_C_TYPE:
            return IDA_TO_C_TYPE[t]

    return SIZE_TO_C_TYPE.get(field.get("size", 8), f"uint8_t /* {field.get('size', '?')}B */")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge raw scan output into conflict-resolved struct layouts "
            "with confidence scoring."
        ),
    )
    parser.add_argument(
        "--scan-output", required=True,
        help="Path to JSON file from scan_struct_fields.py --json",
    )
    parser.add_argument(
        "--com-data",
        help="Path to JSON file from scan_com_interfaces.py --json (optional)",
    )
    parser.add_argument(
        "--class", dest="class_name",
        help="Filter to a specific class (case-insensitive substring)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", help="Write output to file")
    args = safe_parse_args(parser)

    # Load scan data
    scan_path = Path(args.scan_output)
    if not scan_path.exists():
        emit_error(f"Scan output file not found: {scan_path}", ErrorCode.NOT_FOUND)
    try:
        with open(scan_path, "r", encoding="utf-8") as f:
            scan_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        emit_error(f"Failed to read scan output: {exc}", ErrorCode.PARSE_ERROR)

    # Optionally load COM data
    com_data = None
    if args.com_data:
        com_path = Path(args.com_data)
        if not com_path.exists():
            emit_error(f"COM data file not found: {com_path}", ErrorCode.NOT_FOUND)
        try:
            with open(com_path, "r", encoding="utf-8") as f:
                com_data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            emit_error(f"Failed to read COM data: {exc}", ErrorCode.PARSE_ERROR)

    result = merge_evidence(scan_data, com_data=com_data, class_filter=args.class_name)

    if args.json or args.output:
        output_text = json.dumps(result, indent=2, default=str)
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Merged output written to {out_path}", file=sys.stderr)
        else:
            print(output_text)
        return

    # Human-readable output
    print(f"Module: {result['module']}")
    print(f"Types merged: {result['types_merged']}")

    for type_name in sorted(result["merged_types"]):
        td = result["merged_types"][type_name]
        print(f"\n{'=' * 72}")
        com_tag = "  [COM]" if td.get("is_com_class") else ""
        print(
            f"  {type_name}{com_tag}  "
            f"({td['field_count']} fields, {td['padding_count']} gaps, "
            f"{td['total_source_functions']} source functions)"
        )
        print(f"{'=' * 72}")
        print(
            f"  {'Offset':<10} {'Size':<6} {'Conf':>6} {'ASM':>3}  "
            f"{'C Type':<18} {'Field Name':<22} {'Sources'}"
        )
        print(
            f"  {'-'*10} {'-'*6} {'-'*6} {'-'*3}  "
            f"{'-'*18} {'-'*22} {'-'*25}"
        )
        for field in td["fields"]:
            if field["is_padding"]:
                arr = f"[0x{field['array_size']:X}]" if field.get("array_size") else ""
                print(
                    f"  {field['offset_hex']:<10} {field['size']:<6} {'':>6} {'':>3}  "
                    f"{'uint8_t':<18} {field['field_name'] + arr:<22} (padding)"
                )
            else:
                asm_tag = "yes" if field.get("asm_verified") else ""
                srcs = field.get("source_functions", [])
                srcs_str = ", ".join(srcs[:3])
                if len(srcs) > 3:
                    srcs_str += f" (+{len(srcs) - 3})"
                print(
                    f"  {field['offset_hex']:<10} {field['size']:<6} "
                    f"{field['confidence']:>6} {asm_tag:>3}  "
                    f"{field['c_type']:<18} {field['field_name']:<22} {srcs_str}"
                )

        if td.get("com_interfaces"):
            print(f"\n  COM Interfaces:")
            for iface in td["com_interfaces"]:
                print(
                    f"    Base: {iface.get('base_interface', '?')}, "
                    f"Slots: {iface.get('slot_count', '?')}, "
                    f"Confidence: {iface.get('confidence', '?')}"
                )

    print(f"\n{result['types_merged']} type(s) merged.")


if __name__ == "__main__":
    main()
