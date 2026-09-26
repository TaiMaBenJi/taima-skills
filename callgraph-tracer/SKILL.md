---
name: callgraph-tracer
description: Trace call graphs, execution paths, and cross-module xref chains across DeepExtractIDA analysis databases. Use when the user asks to trace a function's call chain, find paths between functions, understand cross-module dependencies, show what a function calls across DLL boundaries, generate call graph diagrams, find reachable functions from an entry point, identify recursive call clusters, or asks about execution flow across extracted modules.
cacheable: true
depends_on: ["decompiled-code-extractor"]
---

# Call Graph Tracer & Cross-Module Chain Analysis

## Purpose

Trace execution paths and call chains across extracted Windows PE binaries. Builds directed call graphs from `simple_outbound_xrefs` / `simple_inbound_xrefs` in analysis DBs, supports path finding, reachability analysis, and **cross-module chain analysis** -- following function calls across DLL boundaries to retrieve decompiled code at each step.

## When NOT to Use

- Tracing how a specific parameter or data value flows through functions -- use **data-flow-tracer**
- PE-level import/export dependency mapping (loader-level, not code xrefs) -- use **import-export-resolver**
- General function explanation or understanding decompiled code -- use **re-analyst** or `/explain`
- Ranking entry points by attack value -- use **map-attack-surface**
- Tracing attacker-controlled input to dangerous sinks -- use **taint-analysis**

## Data Sources

- **Individual analysis DBs** (`extracted_dbs/{module}_{hash}.db`): Per-function xrefs, decompiled code, signatures
- **Tracking DB** (`extracted_dbs/analyzed_files.db`): Maps module names to their analysis DB paths
- **Xref fields used**: `simple_outbound_xrefs` (callees) and `simple_inbound_xrefs` (callers)

Key xref properties for cross-module resolution:

- `function_id`: non-null = callee is in the **same** module (query by ID)
- `function_id`: null = callee is **external** (use `module_name` to find its DB)
- `module_name`: DLL name (e.g., `kernel32.dll`) matching `file_name` in `analyzed_files.db`

**Not all xrefs are function calls.** The `module_name` field uses sentinel values:

- `"data"` (function_type=4): global variable / data references -- **not calls, skipped automatically**
- `"vtable"` (function_type=8): vtable dispatch references -- indirect, not directly followable
- `"internal"` (function_type=1): same-module function -- followable via `function_id`
- `"static_library"` (function_type=2): statically linked -- followable via `function_id`

All scripts automatically filter out data and vtable refs from call graphs and chain traversal. See [reference.md](reference.md) for the full sentinel value table.

### Finding a Module DB

Reuse the decompiled-code-extractor skill's `find_module_db.py`:

```bash
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py --list
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll
```

### Quick Cross-Dimensional Search

To search across function names, signatures, strings, APIs, classes, and exports in one call:

```bash
python .claude/helpers/unified_search.py <db_path> --query "SearchTerm"
python .claude/helpers/unified_search.py <db_path> --query "SearchTerm" --json
```

## Utility Scripts

All scripts are in the `scripts/` subdirectory. Auto-resolve workspace root and `.claude/helpers/` imports. Run from the workspace root.

### build_call_graph.py -- Single-Module Graph Analysis

Build the call graph for one module and run graph queries.

```bash
# Graph statistics
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --stats

# Shortest path between two functions
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --path <source> <target>

# All paths (up to --max-depth)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --all-paths <source> <target>

# Functions reachable from a starting point
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --reachable <function>

# Transitive callers of a function
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --callers <function>

# Strongly connected components (recursive clusters)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --scc

# Leaf functions (called but call nothing)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --leaves

# Root functions (call others but not called)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --roots

# Direct neighbors (callers + callees) of a function
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --neighbors <function>

# By function ID (for --reachable, --callers, --neighbors)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --reachable --id <function_id>
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --callers --id <function_id>
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --neighbors --id <function_id>
```

Options: `--max-depth N` (default 10), `--limit N` (cap results), `--id N` (resolve by function ID).

### cross_module_resolve.py -- Resolve External Functions

Find which analyzed module implements a function, or resolve all external calls from a function.

```bash
# Search all modules for a function
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py CreateProcessW

# Show external calls from a function and resolve their modules
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py --from-function <db_path> <function>

# Resolve ALL outbound xrefs (internal + external)
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py --resolve-all <db_path> <function>

# By function ID (overrides function name in --from-function / --resolve-all)
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py --from-function <db_path> _ --id <function_id>
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py --resolve-all <db_path> _ --id <function_id>
```

### chain_analysis.py -- Cross-Module Xref Chain Traversal (Primary Tool)

**The main script for cross-module analysis.** Follows outbound xrefs across DLL boundaries, retrieving decompiled code at each step.

```bash
# Show function code + classify all outbound calls (depth=1)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function>

# Follow a specific callee across module boundaries
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --follow <callee_name>

# Recursively follow ALL resolvable calls up to depth 3
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 3

# Compact call tree (no code, just structure)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 3 --summary

# Follow calls but skip code output (just show xref chains)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 2 --no-code

# By function ID
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> --id 42
```

### module_dependencies.py -- Inter-Module Dependency Mapping

Map cross-module dependencies across all analyzed modules.

```bash
# Overview: all modules, their function counts, and dependency edges
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --overview

# Detailed deps for one module (who it imports from, who imports it)
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --module appinfo.dll

# API surface: exports vs consumed APIs
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --surface appinfo.dll

# Functions called between two specific modules
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --shared-functions appinfo.dll cmd.exe
```

### analyze_detailed_xrefs.py -- Detailed Xref Analysis

Analyze the rich `outbound_xrefs` field (not `simple_outbound_xrefs`) to surface indirect call resolution, jump table dispatch patterns, vtable-based polymorphic dispatch, and call-confidence scoring.

```bash
# Module-wide detailed xref analysis
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path>

# Per-function analysis
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path> --function <name>
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path> --id <function_id>

# Summary mode
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path> --summary

# JSON output
python .claude/skills/callgraph-tracer/scripts/analyze_detailed_xrefs.py <db_path> --json
```

### generate_diagram.py -- Mermaid/DOT Diagram Generation

Generate visual call graph diagrams.

```bash
# Mermaid subgraph from a function (depth=2)
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --function <name> --depth 2

# By function ID
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --id <function_id> --depth 2

# Mermaid path diagram
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --path <source> <target>

# Cross-module dependency diagram
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py --cross-module

# DOT format instead of Mermaid
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --function <name> --format dot
```

## Workflows

### Workflow 1: "What does function X do?" (Cross-Module Deep Dive)

This is the primary use case. Follow a function's execution across module boundaries.

**IMPORTANT -- Explore both internal and cross-module calls:**
The `--depth` flag controls a single counter that increments for every function followed, whether internal or cross-module. Do NOT spend the entire depth budget exploring only internal helpers within one module. When analyzing a function, always check both:

- **Internal callees** (same module): follow the most relevant ones to understand the function's own logic
- **Resolvable external callees** (other analyzed modules): follow these to understand cross-DLL behavior -- this is where the real value of cross-module tracing lies

A good strategy is to first run `--summary` to see the full call tree shape, then use `--follow` to selectively trace the most interesting internal AND cross-module paths rather than relying on blind high-depth recursion.

```
Analysis Progress:
- [ ] Step 1: Find the module DB containing the function
- [ ] Step 2: Get the function's code and classify its outbound calls
- [ ] Step 3: Follow interesting internal callees to understand the function's logic
- [ ] Step 4: Follow resolvable external callees across module boundaries
- [ ] Step 5: Summarize the full execution flow (internal + cross-module)
```

**Step 1**: Find the module

```bash
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py --list
```

**Step 2**: Get the function, its code, and classify all outbound calls

```bash
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function_name>
```

This outputs the decompiled code plus classifies all outbound xrefs as:

- **Internal**: same module, query by function_id
- **Resolvable external**: another analyzed module has the implementation -- **always explore these**
- **Unresolvable**: module not in the analysis set (e.g., ntdll.dll)

**Step 3**: Follow interesting internal callees to understand the function's own logic:

```bash
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --follow <internal_callee>
```

**Step 4**: Follow resolvable external callees to trace cross-module behavior. For each "Resolvable external" callee, run chain_analysis again starting from **that callee's module DB**:

```bash
# The chain_analysis output shows the callee's DB path -- use it directly
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <callee_db_path> <callee_name>
```

Or use `--follow` from the original function to cross the boundary in one step:

```bash
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --follow <external_callee> --depth 2
```

**Step 5**: Use `--summary` mode to see the full call tree compactly, then dive into specific branches:

```bash
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 3 --summary
```

### Workflow 2: "Trace path from A to B"

Find how function A reaches function B within a module.

```bash
# Find shortest path
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --path DllMain TargetFunc

# Visualize the path
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --path DllMain TargetFunc
```

### Workflow 3: "What's reachable from this entry point?"

```bash
# From an export/entry point, what can it reach?
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --reachable DllMain --max-depth 5

# Visualize it
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --function DllMain --depth 3
```

### Workflow 4: "Map module dependencies"

Understand how extracted modules relate to each other.

```bash
# High-level overview
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --overview

# Deep dive into one module's API surface
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --surface appinfo.dll

# Cross-module dependency diagram
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py --cross-module
```

### Workflow 5: "Find recursive/interesting patterns"

```bash
# Recursive function clusters
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --scc

# Leaf functions (potential utility functions)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --leaves

# Root functions (potential entry points)
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --roots
```

## Cross-Module Resolution Logic

When a function's outbound xref has `function_id = null` (external call):

1. Take `module_name` from the xref (e.g., `"kernel32.dll"`)
2. Look up in `analyzed_files.db` for a record where `file_name` matches (case-insensitive)
3. If found and status is `COMPLETE`, get `analysis_db_path`
4. Open that module's DB and search for the function by name
5. If found, retrieve its decompiled code and continue the chain

This logic is implemented in `cross_module_resolve.py` and `chain_analysis.py`.

## Direct Helper Module Access

For queries not covered by scripts, use `.claude/helpers/` directly:

```python
from helpers import open_individual_analysis_db, open_analyzed_files_db

# Get all analyzed modules
with open_analyzed_files_db() as db:
    for record in db.get_complete():
        print(f"{record.file_name} -> {record.analysis_db_path}")

# Get a function's xrefs
with open_individual_analysis_db("extracted_dbs/module.db") as db:
    func = db.get_function_by_name("FunctionName")[0]
    outbound = func.parsed_simple_outbound_xrefs  # list of dicts
    inbound = func.parsed_simple_inbound_xrefs
```

**Library tagging**: Use `load_function_index_for_db(db_path)` from helpers to annotate call graph nodes with library tags. `filter_by_library(index, app_only=True)` can restrict graph queries to application code.

See [reference.md](reference.md) for complete API details and xref field formats.

## Integration with Other Skills

| Task | Recommended Skill |
|------|-------------------|
| Classify functions discovered in call chains | classify-functions |
| Build security dossier for reachable functions | security-dossier |
| Trace data flow through call chain paths | data-flow-tracer |
| Map attack surface using reachability data | map-attack-surface |
| Lift interesting functions found in chains | batch-lift |

## Performance

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Build call graph | ~2-5s | Single module, scales with function count |
| Path/reachability query | ~1s | After graph is built |
| Chain analysis (depth 1) | ~2-3s | Per-function with code retrieval |
| Chain analysis (depth 3) | ~10-20s | Exponential with depth |
| Cross-module resolution | ~3-5s | Depends on analyzed module count |
| Module dependencies overview | ~10-30s | Scans all modules |

## Additional Resources

- For xref JSON field formats and DB schema, see [data_format_reference.md](../../docs/data_format_reference.md)
- For file_info.json schema (imports/exports), see [file_info_format_reference.md](../../docs/file_info_format_reference.md)
- For IDA conventions and analysis patterns, see [ida_conventions_reference.md](../../docs/ida_conventions_reference.md)
