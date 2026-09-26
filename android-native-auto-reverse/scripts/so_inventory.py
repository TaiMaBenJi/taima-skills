#!/usr/bin/env python3
"""Inventory Android ELF shared libraries and categorize useful strings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


CATEGORY_PATTERNS = {
    "jni": re.compile(
        r"JNI_OnLoad|RegisterNatives|JNINativeMethod|Java_[A-Za-z0-9_]+|FindClass|GetMethodID|GetStringUTFChars",
        re.I,
    ),
    "crypto": re.compile(
        r"\bAES\b|\bRSA\b|\bDES\b|\bHMAC\b|SHA-?1|SHA-?256|SHA-?512|\bMD5\b|encrypt|decrypt|cipher|sign|signature|nonce|timestamp|token",
        re.I,
    ),
    "anti_debug": re.compile(
        r"ptrace|TracerPid|anti.?debug|isDebuggerConnected|ro\.debuggable|SIGTRAP|waitpid|wait4|inotify_add_watch|fork|pipe|tracing stop|zombie|stopped",
        re.I,
    ),
    "anti_frida_hook": re.compile(
        r"frida|gum-js-loop|gmain|linjector|xposed|lsposed|zygisk|substrate|hook",
        re.I,
    ),
    "root_emulator": re.compile(
        r"magisk|\bsu\b|/su\b|test-keys|qemu|goldfish|ranchu|ro\.secure|ro\.kernel\.qemu|emulator",
        re.I,
    ),
    "loader_memory": re.compile(
        r"dlopen|android_dlopen_ext|dlsym|mmap|mprotect|memfd_create|prctl|DexClassLoader|loadDex|OpenMemory|OpenDexFilesFromOat|DexFileVerifier|makeDexElements|\.dex\b|\.apk\b",
        re.I,
    ),
    "procfs_integrity": re.compile(
        r"/proc/|/maps\b|/status\b|/cmdline\b|/fd\b|crc|checksum|integrity|self.?check",
        re.I,
    ),
    "crash_exit": re.compile(
        r"exit_group|\bexit\b|kill|tgkill|abort|raise|SIGABRT|SIGKILL|SIGSEGV",
        re.I,
    ),
    "network_tls": re.compile(
        r"https?://|wss?://|SSL|TLS|X509|Certificate|HostnameVerifier|OkHttp|curl|socket",
        re.I,
    ),
    "packer_shell": re.compile(
        r"jiagu|legu|bangcle|secneo|ijiami|nqshield|dexprotector|secshell|shell|stub|protect|libDexHelper|libdatajar|libdexjni|apkwrapper|JniLib",
        re.I,
    ),
    "vmp": re.compile(
        r"vmp|opcode|handler|JniLib|cV|cI|cL|cS|cB|cJ|Call.*Method|CallNonvirtual|FindClass|GetMethodID",
        re.I,
    ),
}


ELF_MACHINES = {
    3: "x86",
    40: "ARM",
    62: "x86_64",
    183: "AArch64",
}


def iter_so_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path.is_file() and path.name.endswith(".so"):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path
        elif path.is_dir():
            for candidate in sorted(path.rglob("*.so")):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_ascii_strings(data: bytes, min_len: int = 4) -> list[str]:
    pattern = rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}"
    return [match.group(0).decode("ascii", errors="replace") for match in re.finditer(pattern, data)]


def infer_abi(path: Path) -> str | None:
    known = {"armeabi-v7a", "arm64-v8a", "x86", "x86_64", "armeabi"}
    for part in reversed(path.parts):
        if part in known:
            return part
    return None


def parse_elf(data: bytes) -> dict:
    if len(data) < 20 or data[:4] != b"\x7fELF":
        return {"is_elf": False}
    elf_class = {1: "ELF32", 2: "ELF64"}.get(data[4], f"unknown({data[4]})")
    endian = {1: "little", 2: "big"}.get(data[5], f"unknown({data[5]})")
    byteorder = "little" if data[5] == 1 else "big"
    machine = int.from_bytes(data[18:20], byteorder=byteorder, signed=False)
    return {
        "is_elf": True,
        "class": elf_class,
        "endian": endian,
        "machine": ELF_MACHINES.get(machine, f"unknown({machine})"),
    }


def categorize(strings: list[str], max_hits: int) -> tuple[dict[str, int], dict[str, list[str]]]:
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for category, pattern in CATEGORY_PATTERNS.items():
        matched: list[str] = []
        for text in strings:
            if pattern.search(text):
                matched.append(text[:240])
        deduped = list(dict.fromkeys(matched))
        counts[category] = len(deduped)
        samples[category] = deduped[:max_hits]
    return counts, samples


def analyze_so(path: Path, max_hits: int) -> dict:
    data = path.read_bytes()
    strings = extract_ascii_strings(data)
    counts, samples = categorize(strings, max_hits=max_hits)
    elf = parse_elf(data[:128])
    return {
        "path": str(path),
        "name": path.name,
        "abi": infer_abi(path),
        "size": len(data),
        "sha256": sha256_file(path),
        "elf": elf,
        "hint_counts": counts,
        "hint_strings": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="APK extraction dirs, JADX dirs, or .so files")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON to this path instead of stdout")
    parser.add_argument("--max-hints", type=int, default=12, help="Max sample strings per category")
    args = parser.parse_args()

    libraries = [analyze_so(path, args.max_hints) for path in iter_so_files(args.paths)]
    result = {
        "schema": "android-native-auto-reverse.so_inventory.v1",
        "inputs": [str(path) for path in args.paths],
        "library_count": len(libraries),
        "libraries": libraries,
    }

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
