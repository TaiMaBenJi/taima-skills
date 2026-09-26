# Call Graph Tracer & Cross-Module Chain Analysis

Answer: **"How does execution flow across DLL boundaries?"**

Trace call graphs, execution paths, and cross-module xref chains across DeepExtractIDA analysis databases. Builds directed call graphs from xref data, follows function calls across DLL boundaries to retrieve decompiled code at each step, and generates visual diagrams of call subgraphs.

## Quick Start

```bash
# 1. Find the module DB
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll

# 2. See what a function calls (code + classified outbound xrefs)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess

# 3. Follow a specific callee across module boundaries
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess --follow AipCheckForAppPathsKey

# 4. See the full call tree compactly (no code)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess --depth 2 --summary
```

## Scripts

| Script | Purpose |
|--------|---------|
| `build_call_graph.py` | Single-module graph analysis: paths, reachability, SCCs, leaves, roots, neighbors |
| `chain_analysis.py` | **Primary tool** -- cross-module xref chain traversal with decompiled code at each step |
| `cross_module_resolve.py` | Resolve which analyzed module implements a given function |
| `module_dependencies.py` | Map inter-module dependencies, API surfaces, shared functions |
| `generate_diagram.py` | Generate Mermaid or DOT diagrams of call subgraphs |

## What It Does

### Single-Module Graph Queries (`build_call_graph.py`)

```bash
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --stats
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --path <source> <target>
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --reachable <function> --max-depth 5
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --callers <function>
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --scc
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --leaves
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --roots
python .claude/skills/callgraph-tracer/scripts/build_call_graph.py <db_path> --neighbors <function>
```

### Cross-Module Chain Analysis (`chain_analysis.py`)

The main tool. Follows outbound xrefs across DLL boundaries, retrieving decompiled code at each step.

```bash
# Show function code + all outbound calls classified as internal/resolvable/unresolvable
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function>

# Follow a specific callee into another module
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --follow <callee>

# Recursively follow all resolvable calls
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 3

# Compact tree (structure only, no code)
python .claude/skills/callgraph-tracer/scripts/chain_analysis.py <db_path> <function> --depth 3 --summary
```

### Cross-Module Resolution (`cross_module_resolve.py`)

```bash
# Search all modules for a function
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py CreateProcessW

# Show external calls from a function and resolve their modules
python .claude/skills/callgraph-tracer/scripts/cross_module_resolve.py --from-function <db_path> <function>
```

### Module Dependencies (`module_dependencies.py`)

```bash
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --overview
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --surface appinfo.dll
python .claude/skills/callgraph-tracer/scripts/module_dependencies.py --shared-functions appinfo.dll cmd.exe
```

### Diagram Generation (`generate_diagram.py`)

```bash
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --function <name> --depth 2
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py <db_path> --path <source> <target>
python .claude/skills/callgraph-tracer/scripts/generate_diagram.py --cross-module
```

## Xref Filtering

Not all outbound/inbound xrefs are function calls. The scripts automatically filter out:

| module_name | function_type | What it is | Filtered? |
|-------------|---------------|------------|-----------|
| `"internal"` | 1 (gen) | Same-module function call | No -- followable |
| `"static_library"` | 2 (lib) | Statically linked function | No -- followable |
| `"kernel32.dll"`, etc. | 3 (API) | External API call | No -- cross-module resolve |
| `"data"` | 4 (mem) | Global variable / data reference | **Yes** |
| `"vtable"` | 8 (vtable) | VTable dispatch slot | **Yes** |

Tested against 1,672 outbound xrefs and 3,725 inbound xrefs across cmd.exe and coredpus.dll. Filtering removes ~33% of outbound and ~15% of inbound noise (data/vtable references that are not function calls).

## Example Output

```
$ python chain_analysis.py extracted_dbs/appinfo_dll_e98d25a9e8.db AiLaunchProcess --depth 1 --summary

Cross-module call tree:

AiLaunchProcess  (appinfo.dll)  [code]
  -> AiSetMandatoryPolicy  (appinfo.dll)  [code]
    ... 3 callees (0 resolvable) - max depth reached
  -> AipCheckForAppPathsKey  (appinfo.dll)  [code]
    ... 22 callees (1 resolvable) - max depth reached
  -> CreateBnoIsolationPrefix  (appinfo.dll)  [code]
    ... 9 callees (6 resolvable) - max depth reached
  ...
```

```
$ python build_call_graph.py extracted_dbs/cmd_exe_6d109a3a00.db --stats

Module: cmd.exe
Internal functions: 809
Total nodes (incl. external targets): 1041
External targets (imports/APIs): 232
Total edges: 3498
Recursive clusters (SCCs): 7
Leaf functions: 340
Root functions: 84
```

## How Cross-Module Resolution Works

1. Function A in `appinfo.dll` calls `CreateProcessAsUserW` with `module_name: "kernel32.dll"`
2. Script looks up `kernel32.dll` in `analyzed_files.db`
3. If found and `COMPLETE`, opens that module's DB
4. Searches for `CreateProcessAsUserW` by name
5. Retrieves decompiled code, signatures, and outbound xrefs
6. Continues the chain from there

## Files

```
callgraph-tracer/
├── SKILL.md              # Agent instructions and workflows
├── reference.md          # Technical reference (xref formats, algorithms, APIs)
├── README.md             # This file
└── scripts/
    ├── build_call_graph.py      # Single-module graph queries
    ├── chain_analysis.py        # Cross-module chain traversal
    ├── cross_module_resolve.py  # External function resolution
    ├── module_dependencies.py   # Inter-module dependency mapping
    └── generate_diagram.py      # Mermaid/DOT diagram generation
```
