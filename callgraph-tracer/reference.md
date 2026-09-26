# Call Graph Tracer -- Technical Reference

Detailed reference for xref formats, graph algorithms, cross-module resolution, and helper module APIs.

## CLI function targeting

Scripts that start from a named function take `--function <name>` or `--id <N>`:

```bash
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> --function <name> --depth 3 --json
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --function <name> --depth 2
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path> --function <name> --json
```

Prefer `--function` over a bare positional name. After a name lookup, extract or trace with `--id`.

---

## Xref Field Formats

### simple_outbound_xrefs (callee list)

Each entry in `parsed_simple_outbound_xrefs`:

```json
{
    "function_name": "CreateFileW",
    "function_id": null,
    "module_name": "kernel32.dll",
    "function_type": 3,
    "xref_type": "Code_Near_Call",
    "extraction_type": "script"
}
```

| Field | Meaning |
|-------|---------|
| `function_name` | Name of the called function or referenced data |
| `function_id` | If non-null: callee is **internal** (same module), use this ID to query it |
| `module_name` | Target module -- can be a DLL name or a **sentinel value** (see below) |
| `function_type` | Type code (see table below) |
| `xref_type` | IDA xref type: `Call Near`, `Jump Near`, `Offset` |

**Key rules for classification:**
- `function_id != null` → same-module function call (internal). Always followable.
- `function_id == null` + real DLL name → cross-module call. Resolve via `analyzed_files.db`.
- `module_name == "data"` or `function_type == 4` → **NOT a function call**. Data/global variable reference. Skip during graph traversal.
- `module_name == "vtable"` or `function_type == 8` → VTable dispatch reference. Indirect call target, not directly followable.

### module_name Sentinel Values

Not all `module_name` values are real DLL names. The extractor uses sentinel values for non-call references:

| module_name | function_type | Meaning | Example | Follow? |
|-------------|---------------|---------|---------|---------|
| `"internal"` | 1 (gen) | Same-module function | `AiCheckForAdminUser` | Yes (use `function_id`) |
| `"static_library"` | 2 (lib) | Statically linked lib function | `atexit` | Yes (use `function_id`) |
| `"kernelbase.dll"`, etc. | 3 (API) | Windows API import | `CreateProcessW` | Cross-module resolve |
| `"data"` | 4 (mem) | Global variable/data reference | `"SRWLock"`, `stru_18005C380` | **No** -- not a call |
| `"vtable"` | 8 (vtable) | VTable dispatch slot | `wil::TraceLoggingProvider::NotifyFailure` | **No** -- indirect |
| any DLL name | 3 (API) | External API call | `NtQueryInformationToken` | Cross-module resolve |

All scripts in this skill automatically filter out `data` and `vtable` refs from call graph edges and chain traversal.

### simple_inbound_xrefs (caller list)

Same structure. `function_id` non-null means the caller is in the same module.

### Detailed outbound_xrefs (advanced)

For indirect calls, vtable dispatch, and jump tables, use `outbound_xrefs` (not `simple_outbound_xrefs`). Additional fields:

- `is_vtable_call`, `vtable_info`: Virtual method call metadata
- `is_indirect_call`, `indirect_call_info`: Indirect call resolution
- `is_jump_table_target`, `jump_table_detection_confidence`: Jump table targets
- `call_confidence`: Resolution confidence (0-100)

---

## Cross-Module Resolution Algorithm

```
Given: function F in module M, with outbound xref to callee C in module_name "target.dll"

1. Open analyzed_files.db
2. Query: SELECT * FROM analyzed_files WHERE LOWER(file_name) = LOWER("target.dll") AND status = "COMPLETE"
3. If found: get analysis_db_path (relative path to the module's DB)
4. Resolve to absolute: workspace_root / analysis_db_path
5. Open target module's DB
6. Query: SELECT * FROM functions WHERE function_name = "C" (case-insensitive)
7. If found: retrieve decompiled_code, assembly_code, simple_outbound_xrefs
8. Continue chain from callee C's outbound xrefs
```

### Resolution Edge Cases

| Scenario | Handling |
|----------|----------|
| Module not in analyzed_files.db | Unresolvable -- report as "not analyzed" |
| Module analyzed but function not found | Import stub or thunk; report "module analyzed but function not in DB" |
| Multiple functions with same name | Return first match; use mangled_name for disambiguation |
| Cycle detection | Track (db_path, function_name) pairs; skip already-visited |
| API-set resolution | xref `module_name` may be the resolved name (e.g., `kernel32.dll`), not the raw API-set name |

---

## Graph Algorithms

### BFS Shortest Path

Used by `build_call_graph.py --path`. Standard BFS on the outbound adjacency list. Returns the first path found (shortest by hop count).

### Reachability (BFS)

`--reachable` performs BFS from a starting node, recording depth for each discovered node. `--callers` does the same on the inbound adjacency list (reverse graph).

### Strongly Connected Components (Tarjan's)

`--scc` uses iterative Tarjan's algorithm. Only reports components with >1 node (true recursion/mutual recursion). Single self-loops are detected but not reported as SCCs.

### All Paths (DFS with backtracking)

`--all-paths` uses DFS with visited-set backtracking. Capped by `--max-depth` to prevent combinatorial explosion.

---

## Script Architecture

All scripts follow the same pattern:
1. Resolve workspace root (4 levels up from `scripts/`)
2. Add workspace root `.claude/` to `sys.path`
3. Import from `helpers` package
4. Resolve DB paths relative to workspace root
5. Use `open_individual_analysis_db()` and `open_analyzed_files_db()` for DB access

### Workspace Layout

```
{workspace_root}/
├── extracted_dbs/
│   ├── analyzed_files.db          # Tracking DB
│   ├── appinfo_dll_e98d25a9e8.db  # Individual module DBs
│   └── cmd_exe_6d109a3a00.db
├── extracted_code/
│   └── {module_name}/             # .cpp files + file_info.json
├── .claude/helpers/
│   ├── __init__.py                # Re-exports: open_analyzed_files_db, open_individual_analysis_db
│   ├── analyzed_files_db/         # AnalyzedFilesDB, AnalyzedFileRecord
│   └── individual_analysis_db/    # IndividualAnalysisDB, FunctionRecord, FileInfoRecord
└── .claude/skills/
    └── callgraph-tracer/
        ├── SKILL.md
        ├── reference.md
        └── scripts/
            ├── build_call_graph.py
            ├── chain_analysis.py
            ├── cross_module_resolve.py
            ├── module_dependencies.py
            └── generate_diagram.py
```

---

## Helper Module API Reference

### AnalyzedFilesDB (tracking database)

```python
from helpers import open_analyzed_files_db

with open_analyzed_files_db() as db:  # auto-detects extracted_dbs/analyzed_files.db
    db.get_all()                      # list[AnalyzedFileRecord]
    db.get_complete()                 # modules with status=COMPLETE
    db.get_by_file_name("cmd.exe")    # case-insensitive by default
    db.get_by_extension(".dll")       # filter by extension
    db.search(status="COMPLETE", extension=".dll", name_contains="kernel")
```

### AnalyzedFileRecord fields

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | str | Absolute path to original binary |
| `file_name` | str | Filename (e.g., `kernel32.dll`) |
| `file_extension` | str | Extension (e.g., `.dll`) |
| `analysis_db_path` | str | **Relative path** to module's analysis DB |
| `status` | str | `PENDING`, `ANALYZING`, `COMPLETE` |
| `md5_hash` | str | MD5 hash |

### IndividualAnalysisDB (per-module)

```python
from helpers import open_individual_analysis_db

with open_individual_analysis_db("extracted_dbs/module.db") as db:
    db.get_file_info()                          # FileInfoRecord (imports, exports, etc.)
    db.get_function_by_id(42)                   # FunctionRecord by ID
    db.get_function_by_name("FunctionName")     # list[FunctionRecord], case-insensitive
    db.search_functions(name_contains="Bat")    # partial name search
    db.get_all_functions()                      # all FunctionRecords
    db.count_functions()                        # total count
    db.get_function_names()                     # list of all function names
```

### FunctionRecord -- Key Fields for Graph Tracing

| Field | Type | Use |
|-------|------|-----|
| `function_id` | int | Unique ID, used for internal xref resolution |
| `function_name` | str | Function name |
| `decompiled_code` | str | Hex-Rays decompiled C++ |
| `simple_outbound_xrefs` | str (JSON) | **Callees** -- use `parsed_simple_outbound_xrefs` |
| `simple_inbound_xrefs` | str (JSON) | **Callers** -- use `parsed_simple_inbound_xrefs` |
| `function_signature` | str | Demangled signature |

All JSON fields have `parsed_*` property accessors that return Python objects.

### FileInfoRecord -- Key Fields for Cross-Module

| Field | Type | Use |
|-------|------|-----|
| `file_name` | str | Module filename (matches xref `module_name`) |
| `imports` | str (JSON) | Imported modules and functions |
| `exports` | str (JSON) | Exported symbols |
| `entry_point` | str (JSON) | Entry points |

Use `db.get_imports()` for the flat PE import table (v3 `imports` table or JSON fallback). `parsed_exports` and `parsed_entry_point` remain JSON properties on `FileInfoRecord`. `parsed_imports` is the raw nested JSON complement, not the reader callers should walk.

---

## function_type Values

| Value | Name | Meaning |
|-------|------|---------|
| 0 | FT_UNK | Unknown |
| 1 | FT_GEN | General (named internal function) |
| 2 | FT_LIB | Library function |
| 3 | FT_API | Windows API |
| 4 | FT_MEM | Memory-based reference |
| 8 | FT_VTB | VTable dispatch |
| 16 | FT_SYS | System function |

For graph tracing, `function_type` helps filter: APIs (3) are typically leaf nodes; general (1) functions are internal logic worth following.

---

## Diagram Format Reference

### Mermaid

Generated diagrams use `graph LR` (left-to-right flow). Node styles:
- Green (`#d4edda`): Internal functions (in the module)
- Yellow (`#fff3cd`): External functions (imports/APIs)
- Blue (`#cce5ff`): Highlighted path nodes

Paste the output into any Mermaid-compatible renderer (GitHub, Mermaid Live Editor, VS Code extension).

### DOT (Graphviz)

Standard `digraph` with `rankdir=LR`. Render with:
```bash
dot -Tpng output.dot -o output.png
dot -Tsvg output.dot -o output.svg
```

---

## Performance Considerations

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Build single-module graph | <1s | Even for 1000+ functions |
| BFS path finding | <1s | |
| Reachability (depth 10) | <1s | |
| Cross-module chain (depth 2) | 1-5s | Opens multiple DBs |
| Module dependency overview | 5-30s | Scans all module DBs |
| SCC computation | <2s | Tarjan's is linear |

For large analyses (10+ modules), `--summary` mode and `--limit` help manage output size.
