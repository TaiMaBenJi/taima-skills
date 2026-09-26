# Hook Techniques

Use this file when runtime proof is faster than static reading.

## Highest-value hook targets

- `fetch`
- `XMLHttpRequest.prototype.open`
- `XMLHttpRequest.prototype.send`
- transport wrapper functions
- bootstrap helpers
- signer helpers
- storage reads and writes when session state is changing

## Hook goals

- capture pre-sign strings
- capture final payloads after wrapper mutation
- capture response-side refresh fields
- capture cookies or globals that change between requests

## Hook timing and recovery matrix

Treat preload as a capability, not a promised method name. Preserve a clean baseline before any controlled reload or invasive hook.

| Observed state | Smallest next move | Claim boundary and recovery |
|---|---|---|
| `preload available` and the page is not initialized | install the narrow observe-only hook through the schema-confirmed before-document capability, then navigate once | record injection order and prove that original arguments, `this`, return values, and promises are preserved |
| `preload unavailable` | use the earliest stable breakpoint, a controlled refresh with a post-bundle stable boundary, or an offline local runtime | do not claim constructors, bootstrap writes, or early requests were observed; record the missing capability in the snapshot |
| `page already initialized` | treat a late hook as evidence for subsequent events only; save current state before deciding whether refresh is replayable | if refresh would destroy unique state, use `RETAINED_EXCEPTION` and switch to source, breakpoint, or egress evidence instead |
| `hook miss` | verify install time, target frame, execution world, replacement order, and whether a prototype, constructor wrapper, ingress, or egress is more authoritative | a miss clears only that boundary during that window; do not delete the hypothesis yet |
| `page-owned world` miss from console or an isolated world | repeat the narrow proof in the page-owned world when the installed capability exposes it | if it does not, use source, call-frame, or wire-egress evidence and record the world gap |
| `sibling transport` remains possible | inspect XHR, fetch, wrappers, beacon, WebSocket, worker, service-worker, and message relays one channel at a time | correlate every hit to method, URL, field, caller, and request id; silence on one channel is not whole-transport proof |
| tool disconnect, restart, or registry change | stop target actions, persist the evidence already obtained, and perform a `capability snapshot` refresh | record the last confirmed lifecycle state plus control loss; never infer `PARKED`, `CLOSED`, or restored `TARGET_ACTIVE` ownership, then resume through `sequential handoff` |

Change one timing, world, or transport variable at a time. If the hook changes target behavior, restore the clean baseline and treat the failure as observer-effect evidence before escalating.

## Evidence interpretation

- a silent hook only disproves that exact boundary
- a quiet `document.cookie` hook does not clear `Set-Cookie`, returned JS, redirect wrappers, workers, or other writers
- a quiet storage setter hook does not clear direct property assignment or sibling state writers
- a quiet `fetch` hook does not clear XHR, wrapper, worker, or message-based transport
- if a console or isolated-world probe misses a page-owned helper, repeat the proof in the page-owned world before abandoning the lead

## Logging shape

- bind captures to target, event, method, URL, field, and a short caller hint when possible
- one request-bound log line is worth more than a dump of naked values

## Hooking order

1. wire-level hooks
2. wrapper-level hooks
3. helper-level hooks
4. local-variable breakpoints only if hooks still leave ambiguity

Rule:

- if instance-level hooks get replaced or skipped, move upward to the shared boundary that every call must cross such as the prototype, constructor wrapper, or transport egress

## Behavior safety

- default hooks to observe only
- forward original args, preserve `this`, and return the original result or promise
- if a hook changes behavior, treat the new failure mode as possible observer effect until proven otherwise

## Common traps

- hooking business-layer functions while missing the transport wrapper
- hooking one convenient object instance when the runtime keeps rebinding or cloning the real caller
- pausing too early with breakpoints and drowning in noise
- capturing only final hashes without the input string that produced them

## Paste-ready profile

For a known observation boundary that only needs a Console/Snippets script, use `references/profiles/browser-hook-snippets/index.md` instead of expanding into full protocol discovery.
