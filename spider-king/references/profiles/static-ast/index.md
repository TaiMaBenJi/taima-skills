# Static AST Profile

Use this profile after a supplied JavaScript asset is already an evidence artifact and the next goal is to make a signer, serializer, or decoder boundary readable.

## Safety contract

- Parse and rewrite source structurally; never execute the target source.
- Keep the original and every intermediate file in the task project's `js_reverse_cache/tasks/<task-id>/` directory.
- Use only the generic, conservative pipeline. Site or family adapters require independent fixtures before they can be added.
- Treat `eval`, `Function`, WebAssembly, host-object reads, and opaque decoder calls as observations that require the `env-patch` or another local-runtime route.
- `node:vm` is not an isolation boundary. This profile does not use it.
- Reports contain file basenames, hashes, counts, and bounded error metadata, not source text, tokens, cookies, or environment values.
- The input path must not reuse any generated filename listed below. Invalid UTF-8 stops before parsing; `00_source.js` and `final.js` retain the exact input bytes.

## Entry conditions

For structure-only detection and conservative restoration, the supplied input file plus a bounded inspection goal is sufficient. A fixed request or runtime sample becomes mandatory before claiming algorithm equivalence, evaluating a recovered boundary, executing target code, or escalating to a dynamic route. If the entry or call chain is required by the user's goal but remains unknown, return to the Spider core loop before broad deobfuscation.

## Usage

The Babel dependency graph is pinned in `package-lock.json`. Never install dependencies in this skill profile. After dependency installation and the task-cache path are approved:

1. Create `<project>/js_reverse_cache/tasks/<task-id>/tools/static-ast/` within `allowedPaths`.
2. Copy this profile's `package.json`, `package-lock.json`, `scripts/`, and `tests/` into that task-local tool directory without copying `node_modules`.
3. Record the copied package-lock and script hashes, then run from the task-local copy:

```text
npm ci --ignore-scripts
npm test
```

Do not run `npm ci` from the skill directory. Keep task-local `node_modules` ignored and out of evidence packages and stable delivery; remove it at cleanup unless the approved task-cache retention policy keeps it.

Then run the pipeline:

```text
node <task-local-static-ast>/scripts/run-pipeline.js <input.js> <task-output-dir> [hint]
```

The runner writes:

- `00_source.js`: byte-for-byte source copy
- `01_safe_rewrite.js`: conservative rewrite result
- `detection.json`: structural families and original-source evidence counts
- `metrics.json`: residue metrics for the last-good artifact
- `pipeline-report.json`: status, hashes, step timings, and last-good file
- `final.js`: the last parseable artifact, even when a later step fails

The profile is a readability aid, not proof of an algorithm. Prove the recovered boundary with fixed vectors and wire evidence before handing it to an installed signer specialist confirmed in the capability snapshot; otherwise use the Spider pure-Python route.

## Supported static observations

- string-array and decoder-shaped structures
- dispatcher-shaped objects
- loop/switch control-flow flattening
- opcode-style literal comparisons
- computed member access
- `_0x`-style identifiers
- dynamic execution and WebAssembly markers

Detection is structural and intentionally does not select a site-specific adapter. Ambiguous evidence always stays on `generic-static-safe`.

## Rewrite scope

The first rewrite pass only:

1. converts a computed member with a valid string identifier (`obj['run']`) to a normal member (`obj.run`)
2. removes an `if` whose test is already a Boolean literal while preserving the selected statement block; branches containing `var` or function declarations are retained to preserve hoisting semantics

No calls are evaluated. No aliases, string tables, control-flow state machines, getters, proxies, or host-dependent expressions are folded. Add a new rewrite only with a fixture that proves both positive behavior and a negative boundary.

## Upgrade path

If the report marks `dynamic_execution`, `wasm`, or host-dependent code, stop the static route and hand off to `references/profiles/env-patch/index.md`, `references/offline-inline-deob-playbook.md`, or a dedicated runtime skill. The final collector still remains Python-owned.
