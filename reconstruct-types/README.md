# Struct & Class Reconstructor

Answer: **"What are the actual struct and class layouts in this binary?"**

Scans every function in a DeepExtractIDA module using **both decompiled C++ and raw x64 assembly** to collect all memory access patterns (`*(TYPE*)(ptr + offset)` in decompiled, `[reg+offseth]` in assembly), decodes class hierarchies from mangled names and vtable contexts, and produces compilable C/C++ header files with struct definitions, padding, and source annotations.

Assembly is the **ground truth** -- instruction operands give exact field sizes, prologue alias detection tracks parameters through callee-saved registers, and accesses the decompiler optimized away are recovered. ~70% of discovered fields are assembly-verified across tested modules.

## Quick Start

```bash
# 1. Find the module DB
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll

# 2. List all C++ classes in the module
python .claude/skills/reconstruct-types/scripts/list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db --with-vtables

# 3. Get the full class hierarchy for a target class
python .claude/skills/reconstruct-types/scripts/extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class BinaryAndStrategy

# 4. Scan struct fields (decompiled + assembly, merged across all methods)
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class BinaryAndStrategy

# 5. Generate a compilable .h header
python .claude/skills/reconstruct-types/scripts/generate_header.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all --output types.h
```

## Scripts

| Script | Purpose |
|--------|---------|
| `list_types.py` | Quick overview: all C++ classes with method counts, ctor/dtor/vtable flags |
| `extract_class_hierarchy.py` | Full class hierarchy: constructors, destructors, virtual methods, vtable skeletons |
| `scan_struct_fields.py` | Core workhorse: scans decompiled + assembly for memory access patterns, merges into field layouts |
| `generate_header.py` | Produces compilable `.h` files with struct definitions, padding, and offset comments |

## Example Output

### list_types.py

```
Module: appinfo.dll
Total functions: 1173
C++ classes found: 236

Class Name                                    Methods  Ctor  Dtor  VDel  VTbl  VCtx
-----------------------------------------------------------------------------------------------
wil::details                                       45
VLUATelemetry::?$ActivityBase                      15   yes   yes              yes
LUATelemetry                                       14   yes
BinaryAndStrategy                                   6   yes   yes        yes   yes
MaxPathAwareString                                   8   yes   yes
```

### scan_struct_fields.py --class

```
Module: appinfo.dll
Functions scanned: 6

Merged Type Layouts (9 types):

=================================================================
  BinaryAndStrategy  (5 source functions)
=================================================================
  Offset     Size   ASM  Type(s)                   Source Functions
  ---------- ------ ---  ------------------------- ------------------------------
  0x00       8      yes  asm_8B                    BinaryAndStrategy::BinaryAndStrategy, ~BinaryAndStrategy, IsAllowed (+2)
  0x08       8      yes  _QWORD                    BinaryAndStrategy::BinaryAndStrategy, ~BinaryAndStrategy, IsAllowed (+2)
  0x10       8      yes  _QWORD                    BinaryAndStrategy::BinaryAndStrategy, ~BinaryAndStrategy, IsAllowed (+2)
```

### generate_header.py

```c
#pragma once
#include <stdint.h>
#include <stdbool.h>

/* Forward declarations */
struct BinaryAndStrategy;

/**
 * BinaryAndStrategy -- Reconstructed from 5 function(s)
 * Field names are auto-generated placeholders based on byte offset.
 */
struct BinaryAndStrategy {
    uint64_t field_00;                      // +0x00 (8B) [ctor, dtor, IsAllowed (+2)]
    uint64_t field_08;                      // +0x08 (8B) [ctor, dtor, IsAllowed (+2)]
    uint64_t field_10;                      // +0x10 (8B) [ctor, dtor, IsAllowed (+2)]
};  // total known size >= 0x18 (24 bytes)
```

## How the Dual Scanner Works

The struct field scanner extracts data from **two independent sources** and merges them:

| Source | What It Finds | Accuracy |
|--------|--------------|----------|
| **Decompiled C++** | `*((_QWORD *)a1 + 14)` patterns with IDA type casts | Good structural context, but decompiler can misrepresent sizes or optimize accesses away |
| **x64 Assembly** | `mov r8d, [r13+14h]` instruction operands | Ground truth: exact sizes from register widths / `ptr` qualifiers, exact hex offsets, no decompiler artifacts |

Assembly scanning also detects **prologue register saves** (`mov r13, rcx`) to track struct pointers through callee-saved registers -- critical because compilers immediately save parameter registers into non-volatile registers.

Fields seen in both sources are marked `asm_verified`. When sizes disagree, assembly wins.

## Data Pipeline

```
scan_struct_fields.py --json ──> scan_results.json ──> generate_header.py --from-json ──> types.h
                                      │
                              (review, edit, rename fields)
```

The `--from-json` pipeline lets you:
1. Run the scan once and save results
2. Edit the JSON to rename fields, fix types, add comments
3. Regenerate the header from the refined JSON

## Tested Performance

| Module | Functions | Types | Fields | ASM-Verified |
|--------|-----------|-------|--------|-------------|
| appinfo.dll | 791 | 273 (153 named) | 1,374 | 999 (72%) |
| cmd.exe | 537 | 220 (107 named) | 1,150 | 816 (70%) |
| coredpus.dll | 792 | 255 (147 named) | 1,404 | 1,026 (73%) |

## Files

```
reconstruct-types/
├── SKILL.md              # Agent skill instructions (read by Cursor)
├── reference.md          # Technical reference: memory patterns, mangled names,
│                         #   assembly scanning, vtable layouts, DB queries
├── README.md             # This file
└── scripts/
    ├── _common.py             # Shared: mangled name parser, type size maps,
    │                          #   x64 register tables, assembly constants
    ├── list_types.py          # Quick class overview from mangled names
    ├── extract_class_hierarchy.py  # Full hierarchy: methods, vtables, ctors/dtors
    ├── scan_struct_fields.py  # Dual scanner: decompiled + assembly field extraction
    └── generate_header.py     # Compilable .h generation with padding and comments
```

## Dependencies

- Python 3.10+
- `.claude/helpers/` module (workspace root) -- provides `open_individual_analysis_db`, `open_analyzed_files_db`
- SQLite analysis databases from DeepExtractIDA

## Related Skills

- [ida_conventions_reference.md](../../docs/ida_conventions_reference.md) -- IDA conventions, struct offset formulas, and analysis patterns
- [callgraph-tracer](../callgraph-tracer/SKILL.md) -- Trace call chains and module dependencies
- [classify-functions](../classify-functions/SKILL.md) -- Categorize functions by purpose
- [com-interface-reconstruction](../com-interface-reconstruction/SKILL.md) -- Reconstruct COM interfaces and vtables
