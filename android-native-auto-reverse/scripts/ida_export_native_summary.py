"""Export an IDA native-analysis summary as JSON.

Run inside IDA/IDAPython:
  idat64 -A -S"ida_export_native_summary.py /tmp/summary.json" libtarget.so
"""

from __future__ import annotations

import json
import re
import sys

import ida_funcs
import ida_name
import ida_nalt
import idaapi
import idautils
import idc


SUSPICIOUS = re.compile(
    r"JNI|RegisterNatives|OnLoad|ptrace|debug|frida|gum|xposed|magisk|root|qemu|"
    r"mmap|mprotect|memfd|dlopen|android_dlopen_ext|kill|tgkill|exit|signal|"
    r"openat|readlink|stat|maps|TracerPid|AES|RSA|MD5|SHA|Hmac|ssl|tls|pin",
    re.I,
)


def ea_hex(ea):
    return "0x%x" % ea


def image_base():
    try:
        return idaapi.get_imagebase()
    except Exception:
        return 0


def collect_imports():
    imports = []
    qty = ida_nalt.get_import_module_qty()
    for i in range(qty):
        modname = ida_nalt.get_import_module_name(i) or ""

        def cb(ea, name, ordinal):
            imports.append({"module": modname, "ea": ea_hex(ea), "name": name or "", "ordinal": ordinal})
            return True

        ida_nalt.enum_import_names(i, cb)
    return imports


def collect_exports():
    exports = []
    for ordinal, ea, name in idautils.Entries():
        exports.append({"ordinal": ordinal, "ea": ea_hex(ea), "offset": ea_hex(ea - image_base()), "name": name})
    return exports


def collect_functions(limit=None):
    funcs = []
    for idx, ea in enumerate(idautils.Functions()):
        if limit is not None and idx >= limit:
            break
        func = ida_funcs.get_func(ea)
        name = ida_name.get_name(ea) or idc.get_func_name(ea) or ""
        funcs.append(
            {
                "ea": ea_hex(ea),
                "offset": ea_hex(ea - image_base()),
                "end_ea": ea_hex(func.end_ea) if func else "",
                "name": name,
                "suspicious": bool(SUSPICIOUS.search(name)),
            }
        )
    return funcs


def collect_strings(max_items=2000):
    out = []
    for idx, s in enumerate(idautils.Strings()):
        if idx >= max_items:
            break
        text = str(s)
        if SUSPICIOUS.search(text):
            out.append({"ea": ea_hex(s.ea), "offset": ea_hex(s.ea - image_base()), "text": text[:500]})
    return out


def collect_name_xrefs(max_items=1000):
    out = []
    names = []
    for ea, name in idautils.Names():
        if SUSPICIOUS.search(name):
            names.append((ea, name))
    for ea, name in names[:max_items]:
        xrefs = []
        for xr in idautils.XrefsTo(ea):
            xrefs.append({"from": ea_hex(xr.frm), "from_offset": ea_hex(xr.frm - image_base()), "type": str(xr.type)})
        out.append({"ea": ea_hex(ea), "offset": ea_hex(ea - image_base()), "name": name, "xrefs_to": xrefs[:50]})
    return out


def main():
    idaapi.auto_wait()
    out_path = sys.argv[1] if len(sys.argv) > 1 else idc.ask_file(True, "*.json", "Export summary JSON")
    if not out_path:
        raise SystemExit("no output path")

    data = {
        "input_file": ida_nalt.get_input_file_path(),
        "image_base": ea_hex(image_base()),
        "processor": idaapi.get_processor_name(),
        "imports": collect_imports(),
        "exports": collect_exports(),
        "functions": collect_functions(),
        "suspicious_strings": collect_strings(),
        "suspicious_name_xrefs": collect_name_xrefs(),
    }

    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print("[ida_export_native_summary] wrote %s" % out_path)


if __name__ == "__main__":
    main()
