#!/usr/bin/env python3
"""Rank Android native libraries from an so_inventory.json file."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


NAME_HINT = re.compile(
    r"sign|crypto|encrypt|secure|guard|protect|shell|stub|jiagu|legu|bangcle|sec|safe|risk|device|token|auth",
    re.I,
)

CATEGORY_WEIGHTS = {
    "jni": 6,
    "crypto": 5,
    "loader_memory": 5,
    "anti_debug": 4,
    "anti_frida_hook": 4,
    "procfs_integrity": 4,
    "crash_exit": 3,
    "root_emulator": 3,
    "packer_shell": 3,
    "network_tls": 2,
}


def score_library(lib: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    counts = lib.get("hint_counts", {}) or {}

    for category, weight in CATEGORY_WEIGHTS.items():
        count = int(counts.get(category, 0) or 0)
        if count <= 0:
            continue
        capped = min(count, 8)
        delta = weight + capped
        score += delta
        reasons.append(f"{category}:{count} (+{delta})")

    name = lib.get("name", "")
    if NAME_HINT.search(name):
        score += 6
        reasons.append("suspicious/app-specific name (+6)")

    size = int(lib.get("size", 0) or 0)
    if size >= 2 * 1024 * 1024:
        score += 3
        reasons.append("large library >=2MB (+3)")
    elif size >= 512 * 1024:
        score += 1
        reasons.append("medium library >=512KB (+1)")

    elf = lib.get("elf", {}) or {}
    if not elf.get("is_elf", True):
        score -= 20
        reasons.append("not an ELF shared object (-20)")

    return score, reasons


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--so-inventory", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    inventory = load_json(args.so_inventory)
    ranked = []
    for lib in inventory.get("libraries", []):
        score, reasons = score_library(lib)
        ranked.append(
            {
                "score": score,
                "path": lib.get("path"),
                "name": lib.get("name"),
                "abi": lib.get("abi"),
                "size": lib.get("size"),
                "sha256": lib.get("sha256"),
                "elf": lib.get("elf"),
                "reasons": reasons,
                "hint_counts": lib.get("hint_counts", {}),
                "high_value_strings": {
                    key: value[:5]
                    for key, value in (lib.get("hint_strings", {}) or {}).items()
                    if value
                },
            }
        )

    ranked.sort(key=lambda item: (item["score"], item.get("size") or 0), reverse=True)
    candidates = {
        "schema": "android-native-auto-reverse.so_target_candidates.v1",
        "source_inventory": str(args.so_inventory),
        "candidate_count": len(ranked),
        "candidates": ranked[: args.top],
    }
    selected = {
        "schema": "android-native-auto-reverse.selected_so_target.v1",
        "source_inventory": str(args.so_inventory),
        "selected": ranked[0] if ranked else None,
        "selection_note": "Review top candidates against Java load sites, runtime maps, RegisterNatives, crash offsets, and the user's goal before committing.",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "so_target_candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "selected_so_target.json").write_text(
        json.dumps(selected, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {args.out_dir / 'so_target_candidates.json'}")
    print(f"wrote {args.out_dir / 'selected_so_target.json'}")
    if ranked:
        print(f"top: {ranked[0]['name']} score={ranked[0]['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
