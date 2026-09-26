#!/usr/bin/env python3
"""Extract high-value Android native reverse-engineering evidence lines."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PATTERNS = {
    "jni_loader": re.compile(
        r"JNI_OnLoad|RegisterNatives|System\.load|System\.loadLibrary|dlopen|android_dlopen_ext|\\.init_array",
        re.I,
    ),
    "anti_debug": re.compile(
        r"ptrace|TracerPid|wait4|waitid|SIGTRAP|breakpoint|debugger|anti[-_ ]?debug",
        re.I,
    ),
    "anti_frida": re.compile(
        r"frida|gum-js-loop|gmain|linjector|agent|re\.frida|27042|27043",
        re.I,
    ),
    "root_emulator_hook": re.compile(
        r"magisk|/su\b|/xbin/su|/system/bin/su|xposed|lsposed|zygisk|qemu|goldfish|ranchu|test-keys|ro\.debuggable|ro\.secure",
        re.I,
    ),
    "path_proc": re.compile(
        r"/proc/|maps|/fd/|openat|openat2|faccessat|readlinkat|newfstatat|statx|execve|name_to_handle_at",
        re.I,
    ),
    "exit_signal": re.compile(
        r"SIGKILL|SIGSEGV|SIGTRAP|SIGABRT|SIGBUS|SIGILL|BRK|exit_group|\bexit\(|tgkill|tkill|rt_sigqueueinfo|pidfd_send_signal|Fatal signal",
        re.I,
    ),
    "memory_exec": re.compile(
        r"mmap|mprotect|pkey_mprotect|memfd|PR_SET_VMA|\[anon|rwxp|r-xp|RX|RWX|clone3?|pthread_create",
        re.I,
    ),
    "offset": re.compile(
        r"0x[0-9a-f]+|pc\s+[0-9a-f]+|lr\s+[0-9a-f]+|!0x[0-9a-f]+|\+0x[0-9a-f]+",
        re.I,
    ),
}


def iter_lines(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            yield number, line.rstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--context", type=int, default=0, help="print N lines before and after each hit")
    parser.add_argument("--max-line", type=int, default=400, help="truncate long lines")
    args = parser.parse_args()

    for path in args.files:
        if not path.exists():
            print(f"## {path} [missing]")
            continue

        rows = list(iter_lines(path))
        hit_indexes: set[int] = set()
        labels_by_index: dict[int, list[str]] = {}

        for index, (_, line) in enumerate(rows):
            labels = [name for name, pattern in PATTERNS.items() if pattern.search(line)]
            if labels:
                labels_by_index[index] = labels
                for nearby in range(max(0, index - args.context), min(len(rows), index + args.context + 1)):
                    hit_indexes.add(nearby)

        print(f"## {path} hits={len(labels_by_index)}")
        for index in sorted(hit_indexes):
            number, line = rows[index]
            labels = ",".join(labels_by_index.get(index, ["context"]))
            if len(line) > args.max_line:
                line = line[: args.max_line] + "..."
            print(f"{path}:{number}: [{labels}] {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
