#!/usr/bin/env python3
"""Summarize high-value anchors in a JADX output tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PATTERNS = {
    "native_load": re.compile(r"\bSystem\.load(?:Library)?\s*\(", re.I),
    "native_decl": re.compile(r"\bnative\b.+\(", re.I),
    "class_loader": re.compile(r"DexClassLoader|PathClassLoader|InMemoryDexClassLoader|DexFile\.loadDex|loadDex", re.I),
    "app_shell": re.compile(r"attachBaseContext|StubApp|ShellApplication|ProxyApplication|com\.stub|jiagu|legu|bangcle|secneo", re.I),
    "register_natives": re.compile(r"RegisterNatives|JNI_OnLoad|JNINativeMethod", re.I),
    "anti_debug": re.compile(r"Debug\.isDebuggerConnected|TracerPid|ptrace|anti.?debug|ro\.debuggable", re.I),
    "root_emulator": re.compile(r"magisk|/su\b|xposed|lsposed|zygisk|test-keys|qemu|goldfish|ranchu|ro\.secure", re.I),
    "tls_pinning": re.compile(r"CertificatePinner|TrustManager|X509TrustManager|HostnameVerifier|SSLContext|checkServerTrusted", re.I),
    "request_crypto": re.compile(r"sign|signature|encrypt|decrypt|AES|RSA|Hmac|MD5|SHA256|Base64|token|nonce|timestamp", re.I),
    "network": re.compile(r"OkHttp|Retrofit|HttpURLConnection|WebView|https?://|wss?://", re.I),
}


def iter_source_files(root: Path):
    for suffix in ("*.java", "*.kt", "*.smali", "*.xml"):
        yield from root.rglob(suffix)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jadx_out", type=Path)
    parser.add_argument("--max-hits", type=int, default=200)
    parser.add_argument("--max-line", type=int, default=260)
    args = parser.parse_args()

    root = args.jadx_out
    if not root.exists():
        raise SystemExit(f"missing jadx output: {root}")

    counts = {name: 0 for name in PATTERNS}
    emitted = 0
    print(f"# JADX triage: {root}")

    for path in iter_source_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            labels = [name for name, pattern in PATTERNS.items() if pattern.search(line)]
            if not labels:
                continue
            for label in labels:
                counts[label] += 1
            if emitted < args.max_hits:
                rel = path.relative_to(root)
                text = line.strip()
                if len(text) > args.max_line:
                    text = text[: args.max_line] + "..."
                print(f"{rel}:{number}: [{','.join(labels)}] {text}")
                emitted += 1

    print("\n# Counts")
    for name, count in sorted(counts.items()):
        print(f"{name}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
