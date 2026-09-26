# Cursor Subagents

Subagents are specialized AI agents that run in isolated context windows. In an
installed workspace they live under `.claude/agents/` inside a
`DeepExtractIDA_output_root`; in this source checkout they live in `agents/`.
The parent agent delegates complex, context-heavy tasks to them and receives
compact results back. The live registry currently defines 8 subagents.

**Registry**: `registry.json` in this directory is the machine-readable source of truth for all agents -- listing type, entry scripts with accepted parameters, skills used, and JSON output support. It is loaded by `inject-module-context.py` at session start and validated by the infrastructure test suite.

Documentation: https://cursor.com/docs/context/subagents

## Architecture

```
Parent Agent (main conversation)
  │
  ├─ re-analyst                  Explain and analyze decompiled functions
  ├─ triage-coordinator          Orchestrate multi-skill analysis workflows
  ├─ type-reconstructor          Reconstruct C++ structs/classes from memory patterns
  ├─ security-auditor            Vulnerability scanning and security assessment
  ├─ code-lifter                 Lift/rewrite class methods with shared context
  ├─ memory-corruption-scanner   AI-driven memory corruption vulnerability scanner (LLM-only)
  ├─ logic-scanner               AI-driven logic vulnerability scanner (LLM-only)
  └─ taint-scanner               AI-driven taint analysis scanner (LLM-only)
```

Subagents **cannot launch other subagents**. The parent agent orchestrates all delegation. Multiple subagents can run in parallel when their work is independent.

## Subagents

### re-analyst

**Purpose:** General reverse engineering analyst. Explains decompiled functions, answers "what does this do?" questions, traces call chains, and classifies code using IDA Pro domain knowledge. System prompt includes IDA naming glossary, Hex-Rays artifact recognition, Windows internals cheat sheet (x64 calling convention, COM vtable layout, SEH, HRESULT), and a catalog of all available scripts across skills.

**When to use:**
- Understanding what a function or module does
- Explaining IDA Pro naming conventions and decompiler artifacts
- Answering Windows internals questions in context of decompiled code
- Getting a quick module overview (identity, classes, exports)
- Any "explain this" or "what does this do" query about extracted binaries

**Scripts:**

| Script | Purpose |
|--------|---------|
| `re_query.py` | Unified module/function query: overview, function lookup with classification, class listing, export listing, name search -- all in one pass |
| `explain_function.py` | Deep function explanation: module context + identity + classification + decompiled code + assembly + call chain (internal/external/resolvable) + strings (categorized) + dangerous APIs + callee code excerpts |

**re_query.py** -- 5 query modes, all with optional `--json`:

```bash
# Module overview (identity, stats, classes, import DLLs)
python .claude/agents/re-analyst/scripts/re_query.py <db_path> --overview

# Function with full context (classification + strings + outbound calls + callers)
python .claude/agents/re-analyst/scripts/re_query.py <db_path> --function <name> --context

# List all methods of a C++ class with classification
python .claude/agents/re-analyst/scripts/re_query.py <db_path> --class <ClassName>

# Exports with per-export classification, interest score, dangerous API count
python .claude/agents/re-analyst/scripts/re_query.py <db_path> --exports --with-classification

# Search functions by name pattern
python .claude/agents/re-analyst/scripts/re_query.py <db_path> --search <pattern>
```

**explain_function.py** -- everything-in-one for function explanation:

```bash
# Full explanation context (module + identity + classification + code + callees + strings)
python .claude/agents/re-analyst/scripts/explain_function.py <db_path> <function_name>

# By function ID
python .claude/agents/re-analyst/scripts/explain_function.py <db_path> --id <function_id>

# Include callee code (depth 2 = direct callees + their callees)
python .claude/agents/re-analyst/scripts/explain_function.py <db_path> <function_name> --depth 2

# Without assembly (shorter output)
python .claude/agents/re-analyst/scripts/explain_function.py <db_path> <function_name> --no-assembly

# JSON output
python .claude/agents/re-analyst/scripts/explain_function.py <db_path> <function_name> --json
```

**Skills leveraged:** classify-functions, generate-re-report, decompiled-code-extractor, callgraph-tracer, ai-taint-scanner (scripts referenced in the system prompt catalog).

---

### triage-coordinator

**Purpose:** Orchestrates multi-skill analysis workflows. Given a high-level goal (triage, security audit, function understanding, type reconstruction, or full analysis), produces and executes a structured analysis plan by running skill scripts, collecting results, and synthesizing reports. Adapts analysis paths based on module characteristics detected at fingerprinting time.

**When to use:**
- First look at an unknown module ("what is this?")
- Security audit or attack surface assessment
- Comprehensive full-module analysis
- Deep-dive into a specific function
- Type and class reconstruction across a module
- Any task requiring coordination of multiple analysis skills

**Operating modes:**

| Mode | Description | Script |
|------|-------------|--------|
| Direct execution | Run skills, collect data, synthesize report | `analyze_module.py` |
| Plan generation | Produce a phased plan for parallel subagent execution | `generate_analysis_plan.py` |

**Scripts:**

| Script | Purpose |
|--------|---------|
| `_common.py` | Shared utilities (DB resolution, subprocess runner, module fingerprinting) |
| `analyze_module.py` | **Main entry point.** Runs goal-specific pipeline, collects JSON, synthesizes report |
| `generate_analysis_plan.py` | Outputs phased plan with parallel/sequential tasks for parent agent orchestration |

```bash
# Direct execution
python .claude/agents/triage-coordinator/scripts/analyze_module.py <db_path> --goal triage [--json]
python .claude/agents/triage-coordinator/scripts/analyze_module.py <db_path> --goal security [--json]
python .claude/agents/triage-coordinator/scripts/analyze_module.py <db_path> --goal full [--json]
python .claude/agents/triage-coordinator/scripts/analyze_module.py <db_path> --goal understand-function --function <name> [--json]
python .claude/agents/triage-coordinator/scripts/analyze_module.py <db_path> --goal types [--json]

# Plan generation (parent agent executes the plan)
python .claude/agents/triage-coordinator/scripts/generate_analysis_plan.py <db_path> --goal security [--json]
python .claude/agents/triage-coordinator/scripts/generate_analysis_plan.py <db_path> --goal full [--json]
```

**Analysis goals and pipelines:**

| Goal | Skills invoked | Steps | Typical time |
|------|---------------|-------|-------------|
| `triage` | classify-functions, map-attack-surface | 3 | ~6s |
| `security` | triage + map-attack-surface (rank), callgraph-tracer, security-dossier (x5), ai-taint-scanner (x3) | 13 | ~8s |
| `full` | security + reconstruct-types, + conditional COM | 12+ | ~10s |
| `understand-function` | classify-functions, decompiled-code-extractor, callgraph-tracer (x2), security-dossier | 5 | ~1.5s |
| `types` | reconstruct-types, + conditional com-interface-reconstruction | 1-2 | ~2s |

**Adaptive routing:** Before running any pipeline, the coordinator fingerprints the module (fast, direct DB access) and detects 5 traits that add or skip analysis steps:

```
Module fingerprint
  |
  +-- COM-heavy (>5 COM functions or >10%)  -->  + com-interface-reconstruction
  +-- RPC-heavy (>3 RPC functions)          -->  + attack surface focus on RPC handlers
  +-- Security-relevant (>3 security, >2 crypto, or >10 dangerous APIs)
  |                                         -->  + security dossiers for top entries
  +-- Class-heavy (>3 C++ classes)          -->  + reconstruct-types priority
```

**Security goal detail** (the most elaborate pipeline):

```
Phase 1   classify_triage          classify-functions/triage_summary.py
          classify_full            classify-functions/classify_module.py
          discover_entrypoints     map-attack-surface/discover_entrypoints.py

Phase 2   rank_entrypoints         map-attack-surface/rank_entrypoints.py
          call_graph_stats         callgraph-tracer/build_call_graph.py

Phase 3   dossier_{func} x5       security-dossier/build_dossier.py  (top-5 ranked entries)

Phase 4   taint_{func} x3        ai-taint-scanner                   (top-3 ranked entries)
```

Output includes: category distribution, ranked entry points with attack scores, security dossiers per top entry, taint sink reachability with guard bypass analysis, and prioritized next steps (`/explain`, `/audit`, `/taint`, `/search`).

**Plan generation mode** produces structured JSON describing parallel/sequential phases for the parent agent to orchestrate:

```json
{
  "module": "appinfo.dll",
  "goal": "security",
  "phases": [
    {"phase": 1, "name": "parallel_classification_and_discovery", "mode": "parallel", "tasks": [...]},
    {"phase": 3, "name": "security_ranking", "mode": "parallel", "depends_on": "...", "tasks": [...]},
    {"phase": 4, "name": "security_dossiers", "mode": "sequential", "tasks": [{..., "iterate_over": "ranked_entrypoints.top_5"}]},
    {"phase": 5, "name": "synthesize_security", "tasks": [{"action": "synthesize", "inputs": [...]}]}
  ],
  "synthesis": "Combine ranked entry points with security dossiers to produce..."
}
```

---

### type-reconstructor

**Purpose:** Dedicated C++/C struct and class reconstruction from memory access patterns. Scans every function for `*(TYPE*)(base + offset)` patterns in decompiled code and `[reg+offset]` patterns in assembly, merges evidence across the module, resolves vtable and COM interface layouts, and generates compilable C++ header files with per-field confidence annotations.

**When to use:**
- Reconstructing struct/class layouts for a module or specific class
- Generating compilable `.h` header files from binary analysis
- Preparing type definitions to improve code lifting quality
- Understanding COM class object layouts
- Any task where you need to know "what fields does this struct have?"

**Scripts:**

| Script | Purpose |
|--------|---------|
| `_common.py` | Shared utilities (path resolution, subprocess helpers, confidence scoring) |
| `reconstruct_all.py` | **Main entry point.** Full pipeline: discover → hierarchy → scan → merge → COM → header |
| `merge_evidence.py` | Conflict-resolve overlapping fields, infer padding, score confidence |
| `validate_layout.py` | Cross-check generated header against assembly `[base+offset]` patterns |

```bash
# Full module reconstruction
python .claude/agents/type-reconstructor/scripts/reconstruct_all.py <db_path>

# Single class
python .claude/agents/type-reconstructor/scripts/reconstruct_all.py <db_path> --class <ClassName>

# With COM integration
python .claude/agents/type-reconstructor/scripts/reconstruct_all.py <db_path> --include-com --output types.h

# Validate generated header against assembly
python .claude/agents/type-reconstructor/scripts/validate_layout.py <db_path> --header types.h

# Merge raw scan output with confidence scoring
python .claude/agents/type-reconstructor/scripts/merge_evidence.py --scan-output scan.json --com-data com.json
```

**Pipeline phases:**

```
1. Discover    list_types.py              All C++ classes in the module
2. Hierarchy   extract_class_hierarchy.py  Ctors, dtors, vtables, methods
3. Scan        scan_struct_fields.py       Memory access patterns (decompiled + asm)
4. Merge       merge_evidence.py           Conflict-resolve, padding, confidence
5. COM (opt.)  scan_com_interfaces.py      COM vtable layouts, WRL templates
6. Generate    (built-in)                  Compilable C++ header
7. Validate    validate_layout.py          Cross-check header vs assembly
```

---

### security-auditor

**Purpose:** Dedicated security assessment agent for vulnerability scanning. Composes memory corruption detection, logic vulnerability detection, and taint analysis under a security-focused persona with built-in adversarial reasoning methodology.

**When to use:**
- Running a security audit on one or more functions with taint, exploitability, and verification
- Batch-scanning a module for memory corruption or logic vulnerabilities
- Verifying suspected findings against assembly before assigning severity
- Assessing exploitability of taint paths considering guard bypass difficulty

**When NOT to use:**
- Explaining what a function does -- use **re-analyst**
- Lifting decompiled code -- use **code-lifter**
- Orchestrating general analysis pipelines -- use **triage-coordinator**

**Skills used:** decompiled-code-extractor, classify-functions, map-attack-surface, security-dossier, ai-taint-scanner, ai-memory-corruption-scanner, ai-logic-scanner


**Script:** `run_security_scan.py` -- main entry point for module- or
function-scoped security scans that combine classification, attack-surface
discovery, specialized vulnerability detectors, exploitability scoring, and
verification-focused synthesis.

```bash
# Full module scan
python .claude/agents/security-auditor/scripts/run_security_scan.py <db_path> --json

# Focus on a specific function
python .claude/agents/security-auditor/scripts/run_security_scan.py <db_path> --function <name> --json
```

---


### code-lifter

**Purpose:** Dedicated function and class lifting with maintained context across methods. Rewrites IDA Pro decompiled C/C++ functions into clean, readable, 100% functionally equivalent code while maintaining shared struct definitions, naming conventions, accumulated constants, and already-lifted code in its context across all methods.

**Why a subagent, not a skill or grind-loop:**
1. **Persistent context** -- The grind loop loses state between iterations. The code-lifter holds struct definitions, naming maps, constants, and already-lifted code across all methods.
2. **Different mindset from re-analyst** -- The re-analyst explains code (analytical). The code-lifter rewrites it (constructive, deep on one function at a time).
3. **Shared state accumulation** -- Every `/lift-class` requirement (constructor-first struct discovery, naming propagation, constant accumulation, cross-referencing by clean names) requires maintaining state across methods.

**When to use:**
- Lifting all methods of a C++ class (`/lift-class` delegates here)
- Lifting a related group of functions that share struct definitions
- Rewriting decompiled functions with shared context across methods
- Any batch lifting task where consistency across functions matters

**Skills leveraged:**

| Skill | How it's used |
|-------|---------------|
| decompiled-code-extractor | Core 10-step lifting workflow per function |
| batch-lift | Function collection, dependency ordering |
| reconstruct-types | Struct/class layout from memory access patterns |

**Scripts:**

| Script | Purpose |
|--------|---------|
| `_common.py` | Shared utilities (workspace resolution, DB access, state management, batch-lift import) |
| `batch_extract.py` | **Main extraction tool.** Extract data for ALL methods of a class in one shot with struct scan |
| `track_shared_state.py` | **State tracker.** Record and retrieve struct fields, constants, naming maps across methods |

**batch_extract.py** -- Batch data extraction:

```bash
# All methods of a class (returns JSON with all data + struct scan)
python .claude/agents/code-lifter/scripts/batch_extract.py <db_path> --class <ClassName>

# Specific functions by name or ID
python .claude/agents/code-lifter/scripts/batch_extract.py <db_path> --functions func1 func2
python .claude/agents/code-lifter/scripts/batch_extract.py <db_path> --id-list 12,15,18,22

# Initialize shared state file (required before lifting)
python .claude/agents/code-lifter/scripts/batch_extract.py <db_path> --class <ClassName> --init-state

# Human-readable summary
python .claude/agents/code-lifter/scripts/batch_extract.py <db_path> --class <ClassName> --summary
```

**track_shared_state.py** -- State management during lifting:

```bash
# Record a struct field discovered during lifting
python .claude/agents/code-lifter/scripts/track_shared_state.py \
    --record-field CSecurityDescriptor 0x30 pDacl PACL --source SetDacl --asm-verified

# Record a constant
python .claude/agents/code-lifter/scripts/track_shared_state.py \
    --record-constant POLICY_DISABLED 1 --source CheckAccess

# Record a naming mapping
python .claude/agents/code-lifter/scripts/track_shared_state.py \
    --record-naming field_30 pDacl

# Mark a function as lifted
python .claude/agents/code-lifter/scripts/track_shared_state.py --mark-lifted "CSecurityDescriptor::SetDacl"

# Record a clean lifted signature
python .claude/agents/code-lifter/scripts/track_shared_state.py \
    --record-signature "CSecurityDescriptor::SetDacl" "HRESULT CSecurityDescriptor::SetDacl(PACL pDacl)"

# Get current shared state (human-readable or JSON)
python .claude/agents/code-lifter/scripts/track_shared_state.py --dump
python .claude/agents/code-lifter/scripts/track_shared_state.py --dump --json

# List all active state files
python .claude/agents/code-lifter/scripts/track_shared_state.py --list
```

**Typical workflow:**
```
1. Parent resolves DB with find_module_db.py
2. Code-lifter runs batch_extract.py --class X --init-state   (extract all + init state)
3. Code-lifter runs scan_struct_fields.py --class X            (deep struct scan)
4. For each function in dependency order:
   a. track_shared_state.py --dump                             (read current state)
   b. Lift the function (10-step workflow)                     (uses decompiled + assembly from step 2)
   c. track_shared_state.py --record-field/constant/naming     (update state)
   d. track_shared_state.py --mark-lifted <func>               (mark done)
5. Assemble all lifted code into output .cpp file
6. Return results to parent agent
```

**Interaction with grind loop:**
The grind loop is a safety net. If the subagent hits context limits mid-class (rare with <20 methods), the parent can see partial results and decide whether to launch a continuation. But the primary mechanism is the subagent's persistent context.

---

### memory-corruption-scanner

**Type:** analyst (LLM-only)
**File:** `memory-corruption-scanner.md`

AI-driven memory corruption vulnerability scanner. Operates as an LLM subagent receiving callgraph + code batches prepared by the `ai-memory-corruption-scanner` skill. Uses adversarial prompting and a type-specific specialist follow-up (BufferOverflowSpecialist, IntegerOverflowSpecialist, UseAfterFreeSpecialist) with a separate skeptic verification pass.

**When to use:** Launched by `/memory-scan` (Phase 3 deep analysis) and `/scan` (Phase 2 memory corruption scanning).

**Skills used:** `ai-memory-corruption-scanner`, `decompiled-code-extractor`, `map-attack-surface`

---

### logic-scanner

**Type:** analyst (LLM-only)
**File:** `logic-scanner.md`

AI-driven logic vulnerability scanner. Operates as an LLM subagent receiving callgraph + code batches prepared by the `ai-logic-scanner` skill. Uses adversarial prompting and type-specific specialists (AuthBypassSpecialist, StateConfusionSpecialist) with a separate skeptic verification pass.

**When to use:** Launched by `/ai-logical-bug-scan` (Phase 3 deep analysis) and `/scan` (Phase 2 logic scanning).

**Skills used:** `ai-logic-scanner`, `decompiled-code-extractor`, `map-attack-surface`

---

### taint-scanner

**Type:** analyst (LLM-only)
**File:** `taint-scanner.md`

AI-driven taint analysis scanner. Operates as an LLM subagent receiving callgraph + code batches prepared by the `ai-taint-scanner` skill. Uses taint-specific context enrichment, trust boundary analysis, and skeptic verification to trace attacker-controlled data to dangerous sinks.

**When to use:** Launched by `/taint` (Phase 3 deep analysis) and `/scan` (Phase 2 taint scanning).

**Skills used:** `ai-taint-scanner`, `decompiled-code-extractor`, `map-attack-surface`

---

## Shared Infrastructure

All subagents share access to the same workspace resources:

### Analysis Databases

```
extracted_dbs/analyzed_files.db        Normal tracking DB location (helper fallback also supports root-level analyzed_files.db)
extracted_dbs/{module}_{hash}.db       Per-module analysis (assembly, decompiled, xrefs, strings, vtables)
```

### Helper Modules

```python
from helpers import open_individual_analysis_db, open_analyzed_files_db

# Module profile helpers (pre-computed fingerprints)
from helpers import load_module_profile, load_all_profiles, load_profile_for_db

# Function index helpers (function-to-file resolution, library filtering)
from helpers import (
    load_function_index, load_function_index_for_db, lookup_function,
    resolve_function_file, filter_by_library, compute_stats,
    list_extracted_modules, resolve_module_dir,
)

# Find a module's DB
with open_analyzed_files_db() as db:
    records = db.get_by_file_name("appinfo.dll")

# Query a module's functions
with open_individual_analysis_db("extracted_dbs/appinfo_dll_e98d25a9e8.db") as db:
    funcs = db.search_functions(name_contains="ClassName")
    func = db.get_function_by_id(42)
    info = db.get_file_info()
```

### Skill Scripts

All registered skills are available under `.claude/skills/`. Skills that ship
scripts expose them at `.claude/skills/<skill-name>/scripts/<script>.py`;
methodology-only skills contribute guidance but no script files. Subagent
scripts call script-backed skills via subprocess with `--json` for structured
output.

### Module DB Resolution

Every workflow starts with finding the DB:

```bash
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py appinfo.dll
python .claude/skills/decompiled-code-extractor/scripts/find_module_db.py --list
```

Each module's `extracted_code/{module}/function_index.json` maps function names to their `.cpp` files and library tags. Use `load_function_index_for_db(db_path)` to load the index directly from a DB path.

Each module also has `extracted_code/{module}/module_profile.json` with pre-computed metrics (library noise ratio, dangerous API categories, complexity stats). Use `load_profile_for_db(db_path)` to load the profile from a DB path. The session context also includes a compact "Module Profiles" section with this data.

## Files

```
.claude/agents/
  registry.json                                 # Machine-readable agent contracts
  README.md                                     # This file
  re-analyst.md                                 # RE analyst subagent definition
  triage-coordinator.md                         # Triage coordinator subagent definition
  type-reconstructor.md                         # Type reconstructor subagent definition
  security-auditor.md                           # Security auditor subagent definition
  code-lifter.md                                # Code lifter subagent definition
  memory-corruption-scanner.md                  # Memory corruption scanner subagent definition
  logic-scanner.md                              # Logic scanner subagent definition
  re-analyst/
    scripts/
      re_query.py                               # Structured RE queries
      explain_function.py                       # Function explanation generator
  triage-coordinator/
    scripts/
      _common.py                                # Shared utilities
      analyze_module.py                         # Direct execution pipeline
      generate_analysis_plan.py                 # Plan generator
  type-reconstructor/
    scripts/
      _common.py                                # Shared utilities
      reconstruct_all.py                        # Full reconstruction orchestrator
      merge_evidence.py                         # Evidence merger with confidence
      validate_layout.py                        # Assembly validation
  security-auditor/
    scripts/
      _common.py                                # Shared utilities
      run_security_scan.py                      # Security scan and synthesis entry point
  code-lifter/
    scripts/
      _common.py                                # Shared utilities (imports batch-lift _common)
      batch_extract.py                          # Batch data extraction for class/function sets
      track_shared_state.py                     # Shared state management across methods
    state/                                      # Runtime-generated, may be absent until lifting runs
      <ClassName>_state.json                    # Per-class lifting state (auto-managed)
  memory-corruption-scanner/
    scripts/
      _common.py                                # Infrastructure stub (LLM-only agent)
  logic-scanner/
    scripts/
      _common.py                                # Infrastructure stub (LLM-only agent)
  taint-scanner/
    scripts/
      _common.py                                # Infrastructure stub (LLM-only agent)
```

## When to Use Which Subagent

| You want to... | Use | How |
|-----------------|-----|-----|
| Understand what a function does | **re-analyst** | `/explain` uses `explain_function.py` script |
| Enrich xref/callgraph with classification | **re-analyst** | `/xref`, `/callgraph` use `re_query.py` for metadata |
| Add behavioral explanations to reports | **re-analyst** | `/full-report` uses `explain_function.py` for entry point explanations |
| Triage an unknown module | **triage-coordinator** | `/triage` uses `analyze_module.py --goal triage` script |
| Run a security audit | **triage-coordinator** | `--goal security` for full security pipeline |
| Generate a comprehensive report | **triage-coordinator** | `/full-report` uses `generate_analysis_plan.py --goal full` script |
| Run a unified vulnerability scan | **security-auditor** | `/scan` uses `run_security_scan.py` script |
| Trace taint / attacker-controlled data to sinks | **taint-scanner** | `/taint`, `/scan` launch as subagent |
| Verify security findings with fresh eyes | **security-auditor** | `/audit`, `/taint`, `/memory-scan`, `/ai-logical-bug-scan` launch as subagent |
| Reconstruct struct/class definitions | **type-reconstructor** | `/reconstruct-types` uses `reconstruct_all.py` script |
| Generate C++ header files from a binary | **type-reconstructor** | `reconstruct_all.py --output types.h` |
| Lift all methods of a C++ class | **code-lifter** | `/lift-class` launches as subagent |
| Lift related functions with shared context | **code-lifter** | Launched as subagent with shared state |

## Subagent vs Skill

Use a **subagent** when the task is context-heavy, requires scanning many functions, or benefits from isolation (e.g., type reconstruction across 500 functions, unbiased verification). Use a **skill** when the task is single-purpose, repeatable, and completes in one shot (e.g., lift one function, classify one function).
