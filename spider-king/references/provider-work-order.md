# Provider Work Order

Use this compact contract before handing work to a focused route when the next action is gated. It is intentionally lighter than a full project-management schema; the goal is to prevent silent scope growth without slowing normal reverse work.

## Contents

- [When to Use](#when-to-use)
- [Minimal Contract](#minimal-contract)
- [Conditional Implementation Brief](#conditional-implementation-brief)
- [Route Rules](#route-rules)
- [Egress Guard](#egress-guard)
- [Execution Guard](#execution-guard)
- [Write Guard](#write-guard)
- [Result Shape](#result-shape)

## When to Use

Apply this before any of these actions:

- browser navigation or current-target interaction
- live HTTP request, retry, WebSocket handshake, or sent frame
- account/session state use
- executing target-supplied JS, WASM, HTML, or opaque helpers
- dependency installation
- writing task evidence or generated code
- switching from one implementation route to another

Read-only artifact review, fixed-vector transforms, static source inspection, and inline hook advice may stay lightweight as long as they do not write files, contact the target, execute target code, or consume account state.

## Minimal Contract

Record these fields in notes, report, or `js_reverse_cache/tasks/<task-id>/task.json` when a file is already approved:

```json
{
  "shape": "evidence | local-proof | compact-replay | collector",
  "route": "evidence-reuse | chromium-recon | browser-hook | static-ast | env-patch | iv8-local-runtime | verifier | transport | pure-python-rebuild | python-collector",
  "gateFamily": "signer-gated | verifier-gated | decode-gated | session-gated",
  "secondaryGateTags": ["transport-gated"],
  "scope": {
    "scheme": "https",
    "host": "example.com",
    "port": 443,
    "routePrefix": "/api"
  },
  "permissions": {
    "browserRecon": false,
    "liveReplay": false,
    "accountOrSessionUse": "none",
    "targetCodeExecution": "blocked",
    "dependencyInstall": "blocked",
    "writeMode": "no-write"
  },
  "budget": {
    "requestsRemaining": 0,
    "retriesRemaining": 0,
    "websocketFramesRemaining": 0,
    "minDelayMs": 0,
    "concurrency": 1
  },
  "inputs": [],
  "allowedPaths": [],
  "acceptanceTest": "one objective proof for this route"
}
```

Use exact booleans, not vague words. Unknown or omitted permission means blocked/offline for that action.

## Conditional Implementation Brief

Prepare a compact implementation brief only when the declared shape is `compact-replay` or `collector` and at least one material choice remains:

- more than one implementation form is viable, such as pure Python versus a narrow JS, WASM, bootstrap, decoder, or transport helper
- the next step widens the runtime or patch surface
- the dependency choice or installation authority is not already resolved
- the durable path, retention rule, or writable scope for evidence, generated code, fixtures, output, or state is not already resolved
- a meaningful permission choice changes egress, account/session use, target-code execution, or the writable scope

Do not require this brief for `evidence`, `local-proof`, or explicit no-write analysis. If one implementation is already proved and all gated actions are covered by the current work order, a concise route note is sufficient.

The brief is a decision record, not an automatic user-approval gate. It never grants authority and does not replace or widen `permissions`, `budget`, scope, or `allowedPaths`. Pause for user input only when the existing permission gates require new authority or a genuinely material implementation choice cannot be resolved from current evidence.

Keep the brief compact and redacted. Record:

- trigger for the brief and declared delivery shape
- real endpoint as scheme, host, port, and route; method; content type; omit userinfo and raw query values
- each dynamic field with its writer, wire slot, scope, expiry, and refresh path
- decisive evidence and fixed-vector result
- viable implementation forms, their runtime and authority impact, and why the selected form wins
- chosen boundary: Python-owned live HTTP and orchestration versus any narrow local helper responsibility
- required session chain, identity/context scope, and refresh contract
- acceptance oracle, negative control, and required replay count
- planned durable paths, subject to the Write Guard
- residual risk and the evidence that would retire it

Use the matching template in `references/report-templates.md`. Persist it only after the Write Guard passes.

## Route Rules

- One route owns one blocker at a time.
- A route may return evidence, code, or a blocker; it does not redefine the final goal.
- Do not load sibling route manuals or broad playbooks just because the current route is frustrating.
- If a route needs another capability, stop and name the blocker before switching; return the request and result fields from `references/specialist-handoff-contract.md` when ownership changes. Persist them only when the active work order authorizes the exact handoff path.
- Provider completion is not task completion. Spider King accepts only against the recorded acceptance test and the gate for the declared result shape.

## Egress Guard

Before each outbound attempt, verify all of these:

1. The destination matches the recorded scope.
2. The action class is allowed: navigation, request, retry, WebSocket handshake, or sent frame.
3. The remaining budget covers exactly this attempt.
4. Delay and concurrency constraints can be honored.
5. Account/session state, if used, is explicitly in scope.

Consume budget immediately before the attempt. A navigation, initial HTTP request, or WebSocket handshake consumes one `requestsRemaining`. A retry consumes one `requestsRemaining` and one `retriesRemaining`. A sent WebSocket frame consumes one `websocketFramesRemaining`. Do not refund units because transport failed early.

## Execution Guard

Before intentionally executing saved target-supplied code or an opaque helper:

1. Record the exact local path and SHA-256 of the reviewed bytes.
2. Explain why static inspection or fixed-vector parsing is insufficient.
3. Run with network, filesystem, and process access denied unless explicitly needed and approved.
4. Keep final replay egress in Python; JS/WASM/iv8 may return only a narrow artifact.

A scoped baseline browser navigation is evidence collection, not approval to extract and rerun every fetched script as a local helper. It requires `browserRecon`, target scope, and request budget, but automatically loaded page resources do not need a pre-existing local path and hash. Save and hash exact bytes before intentionally replaying any target asset outside that evidence browser.

Loading a helper successfully is runtime health, not protocol proof.

## Write Guard

Before writing:

1. Require a writable `permissions.writeMode`; `no-write`, unknown, or omitted means blocked.
2. Require a non-empty inherited `allowedPaths` and confirm the resolved destination is equal to or below one allowed path.
3. Apply `references/project-artifact-contract.md`; reject symlinks, junctions, reparse points, hard-link aliases, the skill directory, OS temp, and paths outside the bound project.
4. Write volatile captures only under the explicitly allowed `js_reverse_cache/tasks/<task-id>/` path.
5. Promote only verified stable code or fixtures to an explicitly allowed stable path.
6. Never overwrite a user-maintained collector, fixture, helper, or input without explicit path-specific authorization.

## Result Shape

Return or record:

- route and blocker/result
- decisive evidence or artifact path
- fixed-vector result when applicable
- live replay result only when approved
- budget consumed and remaining
- runtime cleanup state
- residual risk

Do not claim complete while task-owned browsers, hooks, profilers, workers, leases, or local runtimes remain live unless a retained exception is explicitly documented.
