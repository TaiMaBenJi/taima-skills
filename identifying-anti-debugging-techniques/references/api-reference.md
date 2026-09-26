# API Reference: Identifying Anti-Debugging Techniques

## Overview

`scripts/analyst.py` scans a binary for anti-debug API names and instruction-byte patterns
(rdtsc, int2d, PEB access) and returns findings with brief neutralization guidance. It is a
static scan and never executes the sample.

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (stdlib) | — | regex, file IO |

## External tools

| Tool | Purpose |
|------|---------|
| x64dbg | Confirm checks at runtime |
| ScyllaHide | Hook and hide common anti-debug checks automatically |

## Core functions

### `scan(path)`
Returns detected API-based checks, instruction-byte patterns, per-finding guidance, and a
likelihood flag.

### `ANTIDBG_APIS` / `BYTE_PATTERNS`
The API-name and instruction-pattern signatures used for detection.

## Usage

```bash
python scripts/analyst.py scan sample.bin
```

## Sources

- Microsoft debug APIs (IsDebuggerPresent, CheckRemoteDebuggerPresent) —
  https://learn.microsoft.com/windows/win32/api/debugapi/
- PEB fields BeingDebugged / NtGlobalFlag (Windows internals documentation)
- Common anti-debug instruction patterns (rdtsc timing, int2d, PEB access)
