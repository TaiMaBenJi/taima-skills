---
description: Process a ghidra-rpc feedback report — fix bugs, implement features, update docs
argument-hint: "<report-path>"
---

A user using the ghidra-rpc skill submitted a feedback report at `$1`.

## Your task

1. **Read the report** (`$1`) and triage every item into one of:
   - **Fix now** — bugs and small/medium features that are clearly correct and implementable
   - **Add to TODO** — larger features, uncertain design decisions, or items that need human review
   - **Skip** — items that are already fixed, duplicates, or out of scope

2. **Fix bugs first.** For each bug:
   - Read the relevant source files to understand the current behavior
   - Implement the fix
   - Run `python -m pytest tests/test_protocol.py tests/test_client.py -v` to verify nothing is broken
   - Commit with a clear message referencing the bug

3. **Implement reasonable features.** For each feature marked "fix now":
   - Implement the feature following existing patterns (see AGENTS.md for architecture)
   - Add CLI support in `cli.py` if it's a new command
   - Run tests
   - Commit

4. **Update TODO.md:**
   - Add items marked "add to TODO" under `## Open Features` with a date reference
   - Move fixed bugs to `## Fixed Bugs (history)` with the next sequential number
   - Verify the `## Verified Working` table is still accurate

5. **Update documentation:**
   - **SKILL.md** — update command reference tables, FAQ, and behavior descriptions
   - **AGENTS.md** — update project layout, architecture, gotchas, and open items
   - Commit docs separately from code changes

6. **Commit discipline:**
   - Separate commits for: bug fixes, new features, doc updates
   - Clear commit messages that reference the report date and specific items

## Key files to check

- `ghidra_rpc/server/tools/modifications.py` — write operations, transactions
- `ghidra_rpc/server/tools/decompiler.py` — decompilation, function resolution
- `ghidra_rpc/server/main.py` — request dispatch, handler registry
- `ghidra_rpc/cli.py` — CLI commands, `_rpc_command` helper
- `ghidra_rpc/client.py` — socket transport, timeout handling
- `AGENTS.md` — developer guide
- `SKILL.md` — user-facing skill prompt
- `TODO.md` — issue tracker

## Guidelines

- Follow the existing code patterns described in AGENTS.md
- All Ghidra mutations need transactions (`ghidra_transaction` context manager)
- Never import `ghidra.*` at module level — import inside handler functions
- Every write response should include a `verified` boolean
- CLI should emit a stderr warning when `verified` is false
- The report was generated according to the feedback format defined in SKILL.md
