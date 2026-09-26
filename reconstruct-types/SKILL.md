---
name: reconstruct-types
description: Reconstruct C/C++ struct and class definitions from IDA Pro decompiled code by scanning memory access patterns, vtable contexts, and mangled names across all functions in a module. Use when the user asks to reconstruct types, build struct layouts, extract class hierarchies, generate header files, improve type information for code lifting, or analyze struct/class definitions from decompiled binaries.
cacheable: true
depends_on: ["decompiled-code-extractor"]
---

# Reconstruct Types

## Purpose

Module-wide type reconstruction from DeepExtractIDA analysis databases. Scans ALL functions in a module using **x64 assembly** to collect every memory access pattern, merges with vtable contexts and mangled name data, and produces compilable C/C++ header files with struct/class definitions.

Assembly is the **sole evidence source** -- it provides exact field sizes from instruction operands and is deterministic across Hex-Rays versions. Functions without assembly data are skipped.

This skill feeds directly into code lifting -- once you have accurate structs, every subsequent lift replaces raw pointer arithmetic with readable field access.

**This is NOT security analysis.** The goal is faithful type reconstruction, not vulnerability research.

## When NOT to Use

- Lifting or rewriting decompiled functions to clean code -- use **batch-lift**
- Scanning for vulnerabilities in functions that use reconstructed types -- use **ai-memory-corruption-scanner** or **ai-logic-scanner**
- Understanding COM interfaces from vtable layouts -- use **com-interface-reconstruction**
- Tracing data flow through struct fields across functions -- use **data-flow-tracer**
- General function explanation -- use **re-analyst** or `/explain`

## Data Sources

### SQLite Databases (primary)

Individual analysis DBs in `extracted_dbs/` contain per-function data:

- `assembly_code` -- sole evidence source: exact offsets/sizes from x64 instructions
- `mangled_name` -- decode class names, namespaces, inheritance
- `vtable_contexts` -- reconstructed class skeletons with virtual method tables
- `function_signature` / `function_signature_extended` -- parameter types

### Generated Code (secondary)

`extracted_code/{module}/file_info.json` has `function_summary` with class/method groupings. Useful for orientation but lacks assembly and detailed xref data.

### Finding a Module DB

Use the decompiled-code-extractor skill's `find_module_db.py` to locate a module's analysis DB:

```bash
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py --list
```

### Quick Cross-Dimensional Search

To search across function names, signatures, strings, APIs, classes, and exports in one call:

```bash
python .claude/helpers/unified_search.py <db_path> --query "SearchTerm"
python .claude/helpers/unified_search.py <db_path> --query "SearchTerm" --json
```

## Utility Scripts

Pre-built scripts in `scripts/` handle all DB extraction and analysis. Run from the workspace root.

### list_types.py -- Quick Overview of All C++ Classes

```bash
# List all classes with method counts
python .claude/skills/reconstruct-types/scripts/list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db

# Include vtable context availability (slower)
python .claude/skills/reconstruct-types/scripts/list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db --with-vtables

# JSON output for programmatic use
python .claude/skills/reconstruct-types/scripts/list_types.py extracted_dbs/appinfo_dll_e98d25a9e8.db --json
```

### extract_class_hierarchy.py -- Full Class Hierarchy with Methods and VTables

```bash
# All classes in a module
python .claude/skills/reconstruct-types/scripts/extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db

# Filter to a specific class
python .claude/skills/reconstruct-types/scripts/extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor

# JSON output
python .claude/skills/reconstruct-types/scripts/extract_class_hierarchy.py extracted_dbs/appinfo_dll_e98d25a9e8.db --json
```

### scan_struct_fields.py -- Core Workhorse: Memory Access Pattern Scanner (Start Here)

```bash
# Scan all methods of a specific class (merges fields across functions)
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor

# Scan a single function
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/cmd_exe_6d109a3a00.db --function BatLoop

# Scan a single function by ID
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/cmd_exe_6d109a3a00.db --id <function_id>

# Scan all classes in a module
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all-classes

# JSON output (can be piped to generate_header.py --from-json)
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all-classes --json
```

### generate_header.py -- Produce Compilable .h Header Files

```bash
# Generate header for one class
python .claude/skills/reconstruct-types/scripts/generate_header.py extracted_dbs/appinfo_dll_e98d25a9e8.db --class CSecurityDescriptor

# Generate header for all types, write to file
python .claude/skills/reconstruct-types/scripts/generate_header.py extracted_dbs/appinfo_dll_e98d25a9e8.db --all --output reconstructed_types.h

# From pre-computed JSON (output of scan_struct_fields.py --json)
python .claude/skills/reconstruct-types/scripts/generate_header.py --from-json scan_results.json --output types.h
```

## Workflows

```
Type Reconstruction Progress:
- [ ] Step 1: Orient -- identify module and find its DB
- [ ] Step 2: Discover -- list all C++ classes in the module
- [ ] Step 3: Extract hierarchy -- get class relationships, vtables, ctors/dtors
- [ ] Step 4: Scan field accesses -- collect memory access patterns per class
- [ ] Step 5: Merge and analyze -- combine data, resolve unknown fields
- [ ] Step 6: Generate headers -- produce compilable .h output
- [ ] Step 7: Refine -- improve field names and types using semantic context
```

**Step 1**: Orient

Find the module's analysis DB:

```bash
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll
```

**Step 2**: Discover Types

Get an overview of all C++ classes:

```bash
python .claude/skills/reconstruct-types/scripts/list_types.py <db_path> --with-vtables
```

Look for classes with: constructors (initialize fields), vtable symbols (polymorphic), many methods (rich field usage).

**Step 3**: Extract Class Hierarchy

For specific target class(es):

```bash
python .claude/skills/reconstruct-types/scripts/extract_class_hierarchy.py <db_path> --class <Name> --json
```

Key data to examine:

- **Constructors** (`??0`) -- initialize all fields in order; inspect decompiled code for field init sequence
- **Destructors** (`??1`, `??_G`) -- cleanup reveals resource-holding fields
- **Virtual methods** -- vtable layout reveals class hierarchy
- **VTable skeletons** -- reconstructed class outlines from IDA

**Step 4**: Scan Field Accesses

Run the struct field scanner:

```bash
python .claude/skills/reconstruct-types/scripts/scan_struct_fields.py <db_path> --class <Name>
```

The scanner:

1. Finds ALL functions belonging to the class (via mangled names) plus functions whose signatures reference the class type
2. Parses **assembly code** for `[reg+offset]` patterns (deterministic sizes and offsets)
4. Detects prologue register saves (e.g., `mov r13, rcx`) to track struct pointers through callee-saved registers
5. Maps base variables/registers to parameter types using function signatures and calling convention
6. Cross-validates and merges fields from both sources -- assembly sizes are authoritative
7. Fields confirmed by assembly are marked `asm_verified` in the output

Use `--no-asm` to skip assembly scanning for faster (but less accurate) results.

**Step 5**: Merge and Analyze

Review the scan output. The agent should:

1. **Rename placeholder fields** -- use context from:
   - String literals in functions that access the field
   - API calls made with the field value
   - Constructor initialization order
   - Mangled name type encodings

2. **Resolve type ambiguity** -- when a field is accessed as both `_DWORD` and `_QWORD`, the larger type is likely correct (or the field may be a union)

3. **Fill unknown gaps** -- check if other modules or cross-references reveal additional fields in padding regions

4. **Identify pointer fields** -- `_QWORD` fields at aligned offsets are often pointers to other structs or vtables

**Step 6**: Generate Headers

```bash
python .claude/skills/reconstruct-types/scripts/generate_header.py <db_path> --class <Name> --output types.h
```

Or for all types at once:

```bash
python .claude/skills/reconstruct-types/scripts/generate_header.py <db_path> --all --output module_types.h
```

**Step 7**: Refine Incrementally

Type reconstruction improves as more functions are analyzed:

1. Lift a function using the [code-lifting](../code-lifting/SKILL.md) skill
2. During lifting, discover new field usages or correct existing ones
3. Update the header file with improved names and types
4. Re-lift with the updated types for cleaner output

## Direct Helper Module Access

For custom queries not covered by the scripts:

```python
from helpers import open_individual_analysis_db

with open_individual_analysis_db("extracted_dbs/module_hash.db") as db:
    # Get all functions for a class
    funcs = db.search_functions(name_contains="ClassName")
    # Get a specific function by mangled name
    funcs = db.get_function_by_mangled_name("??0ClassName@@...")
    # Custom SQL
    rows = db.execute_query("SELECT function_name, vtable_contexts FROM functions WHERE vtable_contexts IS NOT NULL")
```

## Output Format

Generated headers follow this structure:

```cpp
#pragma once
#include <stdint.h>
#include <stdbool.h>

/* Forward declarations */
struct MyClass;

/**
 * MyClass -- Reconstructed from 12 function(s)
 * Field names are auto-generated placeholders based on byte offset.
 */
struct MyClass {
    uint32_t field_00;                      // +0x00 (4B) [Constructor, Init]
    uint8_t _unknown_04[0xC];               // +0x04 .. +0x0F
    uint64_t field_10;                      // +0x10 (8B) [SetValue, GetValue]
    uint32_t field_18;                      // +0x18 (4B) [Process]
};  // total known size >= 0x1C (28 bytes)
```

## Microsoft Mangled Name Quick Reference

| Pattern                  | Meaning                          |
| ------------------------ | -------------------------------- |
| `??0Class@@`             | Constructor `Class::Class()`     |
| `??1Class@@`             | Destructor `Class::~Class()`     |
| `??_GClass@@`            | Scalar deleting destructor       |
| `??_7Class@@6B@`         | VFTable (virtual function table) |
| `?Method@Class@@UEAA...` | Public virtual method            |
| `?Method@Class@@QEAA...` | Public non-virtual method        |
| `?Method@Class@@AEAA...` | Private method                   |
| `?Method@Class@@IEAA...` | Protected method                 |

## Integration with Other Skills

| Task | Recommended Skill |
|------|-------------------|
| Lift functions using reconstructed types | batch-lift |
| Discover COM interfaces from vtable layouts | com-interface-reconstruction |
| Trace data flow through reconstructed struct fields | data-flow-tracer |
| Classify functions that access reconstructed types | classify-functions |
| Build security dossier for type-heavy functions | security-dossier |

## Performance

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Scan struct fields | ~10-20s | Full module memory access pattern scan |
| Extract class hierarchy | ~3-5s | Mangled name and vtable analysis |
| List types | ~2-3s | Summary of discovered types |
| Generate header | ~1-2s | C/C++ header from type data |

## Additional Resources

- For detailed technical reference, see [reference.md](reference.md)
- For DB schema and JSON field formats, see [data_format_reference.md](../../docs/data_format_reference.md)
- For IDA conventions and struct offset formulas, see [ida_conventions_reference.md](../../docs/ida_conventions_reference.md)
