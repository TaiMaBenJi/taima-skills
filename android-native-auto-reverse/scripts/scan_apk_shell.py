#!/usr/bin/env python3
"""Scan an APK for packer, shell, dex, and native-loader clues."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


PACKER_PATTERNS = {
    "360_jiagu": [r"libjiagu", r"qihoo", r"stubapp"],
    "bangcle": [r"bangcle", r"libsecexe", r"libsecmain", r"libSecShell"],
    "ijiami": [r"ijiami", r"libexec", r"ijiami\.dat"],
    "tencent_legu": [r"legu", r"libshell", r"tup"],
    "secneo": [
        r"secneo",
        r"libDexHelper",
        r"libDexHelper-x86",
        r"libdatajar",
        r"libdexjni",
        r"resthird\.data",
        r"v1filter\.jar",
        r"com/secneo/apkwrapper",
        r"com/fort/andjni/JniLib",
    ],
    "dexprotector": [r"dexprotector", r"libdexprotector"],
    "alibaba": [r"aliprotect", r"libsg", r"libsgmain"],
    "generic_shell": [r"com/stub", r"StubApp", r"ShellApplication", r"ProxyApplication", r"libprotect", r"libshell"],
}

DEFAULT_RULES = Path(__file__).resolve().parents[1] / "references" / "apkpackdata.json"

LOADER_PATTERNS = [
    rb"DexClassLoader",
    rb"PathClassLoader",
    rb"InMemoryDexClassLoader",
    rb"loadDex",
    rb"openDexFile",
    rb"OpenDexFilesFromOat",
    rb"OpenMemory",
    rb"DexFileVerifier",
    rb"System.loadLibrary",
    rb"System.load",
    rb"attachBaseContext",
    rb"JNI_OnLoad",
    rb"RegisterNatives",
    rb"android_dlopen_ext",
    rb"mprotect",
    rb"inotify_add_watch",
    rb"ptrace",
    rb"TracerPid",
    rb"memfd_create",
    rb"RegisterNatives",
    rb"com/secneo/apkwrapper",
    rb"com/fort/andjni/JniLib",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_read(zf: zipfile.ZipFile, name: str, limit: int = 2_000_000) -> bytes:
    info = zf.getinfo(name)
    if info.file_size > limit:
        with zf.open(info) as handle:
            return handle.read(limit)
    return zf.read(info)


def norm_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def load_pack_rules(path: Path | None) -> dict:
    if path is None:
        path = DEFAULT_RULES
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rules = {}
    for packer, item in raw.items():
        rules[str(packer)] = {
            "sopath": [norm_zip_name(str(x)) for x in item.get("sopath", []) if str(x).strip()],
            "soname": [Path(str(x)).name for x in item.get("soname", []) if str(x).strip()],
            "other": [norm_zip_name(str(x)) for x in item.get("other", []) if str(x).strip()],
            "soregex": [str(x) for x in item.get("soregex", []) if str(x).strip()],
        }
    return rules


def match_rule_database(names: list[str], rules: dict) -> dict:
    normalized = [norm_zip_name(n) for n in names]
    name_set = set(normalized)
    basename_set = {Path(n).name for n in normalized}
    hits = {}

    for packer, rule in rules.items():
        packer_hits = []

        for path in rule.get("sopath", []):
            if path in name_set:
                packer_hits.append({"type": "sopath", "pattern": path, "match": path})

        for soname in rule.get("soname", []):
            if soname in basename_set:
                matches = [n for n in normalized if Path(n).name == soname]
                for match in matches[:10]:
                    packer_hits.append({"type": "soname", "pattern": soname, "match": match})

        for other in rule.get("other", []):
            other_base = Path(other).name
            for n in normalized:
                if n == other or Path(n).name == other_base:
                    packer_hits.append({"type": "other", "pattern": other, "match": n})

        for pattern in rule.get("soregex", []):
            try:
                rx = re.compile(pattern, re.I)
            except re.error as exc:
                packer_hits.append({"type": "bad_regex", "pattern": pattern, "match": str(exc)})
                continue
            for n in normalized:
                base = Path(n).name
                if rx.search(base) or rx.search(n):
                    packer_hits.append({"type": "soregex", "pattern": pattern, "match": n})

        if packer_hits:
            deduped = []
            seen = set()
            for hit in packer_hits:
                key = (hit["type"], hit["pattern"], hit["match"])
                if key not in seen:
                    deduped.append(hit)
                    seen.add(key)
            hits[packer] = deduped

    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES, help="apk packer rule JSON")
    args = parser.parse_args()

    apk = args.apk
    result = {
        "apk": str(apk),
        "sha256": sha256(apk),
        "dex_files": [],
        "native_libs": [],
        "assets_or_blobs": [],
        "packer_hits": {},
        "rule_hits": {},
        "rules_path": str(args.rules) if args.rules else "",
        "loader_hits": {},
        "notes": [],
    }

    with zipfile.ZipFile(apk) as zf:
        names = zf.namelist()
        joined_names = "\n".join(names)
        pack_rules = load_pack_rules(args.rules)

        for name in names:
            info = zf.getinfo(name)
            if re.search(r"(^|/)classes\d*\.dex$", name):
                result["dex_files"].append({"name": name, "size": info.file_size})
            elif name.startswith("lib/") and name.endswith(".so"):
                result["native_libs"].append({"name": name, "size": info.file_size})
            elif name.startswith("assets/") and re.search(r"\.(dat|bin|dex|jar|so|sec|enc)$", name, re.I):
                result["assets_or_blobs"].append({"name": name, "size": info.file_size})

        for packer, patterns in PACKER_PATTERNS.items():
            hits = [p for p in patterns if re.search(p, joined_names, re.I)]
            if hits:
                result["packer_hits"][packer] = hits

        result["rule_hits"] = match_rule_database(names, pack_rules)

        candidate_files = [
            n
            for n in names
            if re.search(r"(^|/)classes\d*\.dex$|\.so$|AndroidManifest\.xml$", n)
        ]
        for name in candidate_files:
            try:
                data = safe_read(zf, name)
            except Exception:
                continue
            hits = sorted({pat.decode("ascii", "ignore") for pat in LOADER_PATTERNS if pat in data})
            if hits:
                result["loader_hits"][name] = hits

    dex_total = sum(item["size"] for item in result["dex_files"])
    native_total = sum(item["size"] for item in result["native_libs"])
    if result["packer_hits"]:
        result["notes"].append("built_in_packer_or_shell_name_hit")
    if result["rule_hits"]:
        result["notes"].append("apkpackdata_rule_hit")
    if native_total > dex_total * 3 and native_total > 1_000_000:
        result["notes"].append("native_code_much_larger_than_dex")
    if result["assets_or_blobs"]:
        result["notes"].append("assets_contain_binary_payload_candidates")
    if not result["dex_files"]:
        result["notes"].append("no_classes_dex_found")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"APK: {result['apk']}")
    print(f"SHA-256: {result['sha256']}")
    print(f"DEX files: {len(result['dex_files'])}")
    for item in result["dex_files"]:
        print(f"  - {item['name']} size={item['size']}")
    print(f"Native libs: {len(result['native_libs'])}")
    for item in sorted(result["native_libs"], key=lambda x: x["size"], reverse=True)[:20]:
        print(f"  - {item['name']} size={item['size']}")
    print("Packer hits:")
    for key, hits in result["packer_hits"].items():
        print(f"  - {key}: {', '.join(hits)}")
    print(f"Rule hits: {result['rules_path']}")
    for key, hits in result["rule_hits"].items():
        print(f"  - {key}:")
        for hit in hits[:20]:
            print(f"      [{hit['type']}] {hit['pattern']} -> {hit['match']}")
    print("Loader hits:")
    for name, hits in result["loader_hits"].items():
        print(f"  - {name}: {', '.join(hits)}")
    print("Notes:")
    for note in result["notes"]:
        print(f"  - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
