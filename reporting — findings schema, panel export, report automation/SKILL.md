---
name: reporting
description: Turn engagement output (reports, evidence chains, case dirs) into machine-readable findings and an interactive dashboard (ReverseOps panel). Use when writing up findings, generating pentest reports or dashboards, or when the panel shows stale or missing data.
---

# reporting — findings schema, panel export, report automation

**Purpose**: turn raw engagement output (`reports/*.md`, evidence chains, case dirs) into
machine-readable findings and an interactive dashboard — the ReverseOps panel (`panel/`).

## When this skill fires

- "write up the findings", "generate the report", "make a dashboard", "pentest report"
- After any ACT phase completes (Evidence → Finding → Path lands, then this skill renders it)
- When the user opens `panel/index.html` and it shows stale / no data

## Contract

1. **Every finding is data first.** Either:
   - a JSON file conforming to `skills/reporting/finding-schema.json`
     (`work/<case>/findings/HIG-001.json`, one file per finding), or
   - a `## Finding N: title` (or `## vulnerability N：标题`) section inside a markdown report with an
     inline `Severity:` / `risk等级：` line — the exporter parses these heuristically.
2. **Severity vocabulary is fixed**: `critical | high | medium | low | info`
   (Chinese reports' critical / high risk / medium risk / low risk / info map onto these automatically).
3. **IDs are stable**: `<SEV3>-<NNN>` (`HIG-001`). Never renumber a finding that a client has seen.

## Workflow

```text
evidence chain (skills/ops/evidence-finding-path.md)
  → write finding JSON (work/<case>/findings/*.json)        # preferred
    OR structured section in reports/<date>_<case>.md
  → python3 scripts/mkreport.py                             # repo-local defaults
  → python3 panel/serve.py  → http://127.0.0.1:8377          # dashboard + terminal
```

- `mkreport.py` outputs `panel/data/data.js` + `panel/data/data.json`.
  Both are **gitignored** — regeneration is a local step, never commit client data.
- Extra sources: `--findings-dir <dir>`, `--include <file>`, `--cases-root work`.
- Panel from `file://`? It falls back to bundled `panel/data/sample.data.js` when
  `data.js` is missing, tagged `DEMO` in the header. Terminal + report-body view need `serve.py`.

## ACTION REQUIRED

1. Confirm each finding has ≥1 evidence ref (`evidence[]`) before setting
   `status: confirmed` — mirrors `skills/ops/scope-contract.md` (no evidence, no finding).
2. Run `python3 scripts/mkreport.py` and read the warning list; fix unparsed sections.
3. Open the panel, verify severity counts match the markdown report by hand once.
4. Redact before sharing: `grep -Ri 'token\|password\|secret' panel/data/` then delete the export.

## Files

| File | Role |
|------|------|
| `finding-schema.json` | JSON-Schema for a finding |
| `templates/finding.json` | Copy-paste starting point |
| `templates/report.md` | Markdown report skeleton the parser fully understands |
| `../../scripts/mkreport.py` | exporter (stdlib only, py3.8+) |
| `../../panel/` | the dashboard (UI + local server + terminal bridge) |

## Common pitfalls

- Missing `Severity:`/`risk等级` line → finding lands as `info`. Always write it inline.
- In Chinese reports, findings need the `## vulnerability N：` heading form to split sections
  (`## Finding N:` in English reports).
- Timeline chart needs ISO dates — put `Testing日期：`/`Date: YYYY-MM-DD` near the report top.
