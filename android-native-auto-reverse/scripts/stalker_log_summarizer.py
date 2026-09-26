#!/usr/bin/env python3
"""Summarize frida_stalker_ollvm_trace.js logs into offset evidence JSON."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


SUMMARY_RE = re.compile(r"summary callee=([^!\s]+)!([^\s]+)\s+count=(\d+)")
EVENT_RE = re.compile(r"event\s+(\w+)\s+from=([^!\s<]+)!([^\s]+).*?\s+to=([^!\s<]+)!([^\s]+)")
ENTER_RE = re.compile(r"enter\s+([^!\s<]+)!([^\s]+)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    summary_counts: Counter[tuple[str, str]] = Counter()
    events: Counter[tuple[str, str, str, str, str]] = Counter()
    enters: Counter[tuple[str, str]] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        if match := SUMMARY_RE.search(line):
            key = (match.group(1), match.group(2))
            summary_counts[key] += int(match.group(3))
            if len(examples[str(key)]) < 3:
                examples[str(key)].append(line)
        if match := EVENT_RE.search(line):
            key = (match.group(1), match.group(2), match.group(3), match.group(4), match.group(5))
            events[key] += 1
        if match := ENTER_RE.search(line):
            enters[(match.group(1), match.group(2))] += 1

    result = {
        "schema": "android-native-auto-reverse.stalker_log_summary.v1",
        "input": str(args.log),
        "summary_callees": [
            {"module": module, "offset": offset, "count": count}
            for (module, offset), count in summary_counts.most_common()
        ],
        "events": [
            {
                "type": typ,
                "from_module": from_module,
                "from_offset": from_offset,
                "to_module": to_module,
                "to_offset": to_offset,
                "count": count,
            }
            for (typ, from_module, from_offset, to_module, to_offset), count in events.most_common()
        ],
        "target_enters": [
            {"module": module, "offset": offset, "count": count}
            for (module, offset), count in enters.most_common()
        ],
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
