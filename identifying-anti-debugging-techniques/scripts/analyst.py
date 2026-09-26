#!/usr/bin/env python3
"""Scan a binary for anti-debugging indicators.

Looks for anti-debug API names and instruction-byte patterns (rdtsc, int3/int2d, PEB access)
in file bytes, and reports what was found with brief guidance. Static scan only; it never
executes the sample.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ANTIDBG_APIS = [
    b"IsDebuggerPresent", b"CheckRemoteDebuggerPresent", b"NtQueryInformationProcess",
    b"OutputDebugStringA", b"NtSetInformationThread", b"DebugActiveProcess",
    b"SetUnhandledExceptionFilter", b"QueryPerformanceCounter", b"GetTickCount",
    b"NtQuerySystemInformation", b"NtClose", b"BlockInput",
]

# instruction-byte patterns (heuristic)
BYTE_PATTERNS = {
    "rdtsc": rb"\x0f\x31",
    "int3 (0xCC)": rb"\xcc\xcc\xcc",
    "int2d": rb"\xcd\x2d",
    "cpuid": rb"\x0f\xa2",
    "peb_fs30": rb"\x64\xa1\x30\x00\x00\x00",  # mov eax, fs:[30h]
    "peb_gs60": rb"\x65\x48\x8b.{0,2}\x60",     # mov rax, gs:[60h] (x64, loose)
}

GUIDANCE = {
    "IsDebuggerPresent": "force return 0 / hook with ScyllaHide",
    "CheckRemoteDebuggerPresent": "force the out param to FALSE",
    "NtQueryInformationProcess": "watch ProcessDebugPort/Flags classes; fake results",
    "rdtsc": "timing check; patch the delta comparison",
    "int2d": "anti-debug exception trick; handle/skip the exception",
    "peb_fs30": "PEB access; clear BeingDebugged / NtGlobalFlag",
}


def scan(path: str) -> dict:
    data = Path(path).read_bytes()
    apis = sorted({a.decode() for a in ANTIDBG_APIS if a in data})
    patterns = sorted({name for name, pat in BYTE_PATTERNS.items()
                       if re.search(pat, data)})
    findings = apis + patterns
    return {
        "api_checks": apis,
        "instruction_patterns": patterns,
        "guidance": {f: GUIDANCE[f] for f in findings if f in GUIDANCE},
        "anti_debug_likely": len(findings) >= 2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for anti-debugging")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("file")
    args = parser.parse_args(argv)
    print(json.dumps(scan(args.file), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
