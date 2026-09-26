# Local Challenge Executor Playbook

Use this playbook when challenge HTML or challenge JS must run locally to emit a replayable artifact, and the final collector must stay browser-free.

## Contents

- [Route here when](#route-here-when)
- [Core idea](#core-idea)
- [Contract](#contract)
- [Minimal host requirements](#minimal-host-requirements)
- [Fast execution path](#fast-execution-path)
- [Local bridge containment](#local-bridge-containment)
- [Artifact priority](#artifact-priority)
- [Post-artifact noise](#post-artifact-noise)
- [Coupling with other gates](#coupling-with-other-gates)
- [Delivery shape](#delivery-shape)
- [Version-randomized helper boundary](#version-randomized-helper-boundary)
- [Common traps](#common-traps)
- [Minimal handoff notes](#minimal-handoff-notes)

## Route here when

- a business JSON API returns `text/html` challenge chrome instead of data
- a document route returns non-final HTML plus linked challenge scripts
- success depends on a rewritten URL, derived cookie header, or storage-seeded module produced by challenge execution
- full offline crypto rebuild is slower than executing the challenge blob in a minimal host
- anti-debug or missing DOM APIs make browser harvest noisy, but a stubbed local executor still emits the artifact

## Core idea

Python owns live HTTP.
The helper only restores the missing challenge artifact.

Success is not "the script finished cleanly".
Success is a **Python-replayable** `redirectUrl`, composed `Cookie` header, or equivalent wire artifact.

## Contract

### Helper input

```json
{
  "url": "https://example.invalid/api/business?...",
  "html": "<!doctype html>...",
  "externalScriptUrl": "https://example.invalid/challenge.js",
  "externalScriptText": "/* challenge source */",
  "seedCookies": "a=1; b=2",
  "timeoutMs": 5000
}
```

### Helper output

```json
{
  "redirectUrl": "https://example.invalid/api/business?...&decode=...",
  "cookieString": "a=1; c=3",
  "navigationAttempts": ["..."],
  "errors": ["optional noise"],
  "xhrRequests": [],
  "fetchCalls": [],
  "resourceRequests": []
}
```

At least one of `redirectUrl` or a replayable `cookieString` must be present.

## Minimal host requirements

Implement the smallest host that preserves challenge progress:

1. **Document URL** equals the challenged business or document URL.
2. **Script injection** serves the captured challenge script for the expected URL; other subresources may 404 unless proven required.
3. **Cookie jar** seeded from the first-hop response on the same session chain.
4. **Location capture** on navigate / assign / replace / href setter.
5. **Canvas / WebGL stubs** when fingerprint probes exist.
6. **XHR and fetch stubs** that record calls and return empty success unless a real local response is required.
7. **Timer compression** so long `setTimeout` chains still finish inside `timeoutMs`.
8. **Anti-debug tolerance**: ignore or neutralize `debugger` loops when they only delay artifact emission.

Do not pin the skill to one host brand.
`jsdom`, `happy-dom`, `iv8`, or another minimal host is acceptable when it preserves the needed semantics.

## Fast execution path

1. Python GETs the business or document URL with the admitted transport profile.
2. If the body is challenge HTML, freeze HTML, linked script URL, script body, and seed cookies on one session chain.
3. Run the local helper with the contract above.
4. Prefer artifacts in this order:
   - rewritten navigation / redirect URL with decisive query params
   - full outbound `Cookie` header or cookie string
   - storage module only if it is later proven necessary for regeneration
5. Python merges cookies, applies any original-URL echo field required by replay evidence, and performs the real HTTP replay.
6. Validate business anchors (JSON schema keys, list length, HTML markers), not merely HTTP 200.

## Local bridge containment

Treat challenge or collector-like JavaScript as untrusted code. If a local host
needs to observe XHR or fetch intent, Python must still own every real HTTP
request and the bridge must be narrowly contained.

Enforce these controls:

- build an allowlist from exact URLs already discovered by Python on the same session chain
- require HTTPS and the expected origin unless live evidence proves another route is part of the contract
- restrict methods to the observed contract
- disable redirects, or reject any unexpected redirect before following it
- strip collector-controlled `Cookie`, `Authorization`, `Proxy-Authorization`, `Host`, `Connection`, and forwarding headers
- make the Python session jar the only cookie authority
- cap request count, body size, response size, and per-request timeout
- reject `file:`, `data:`, localhost, loopback, link-local, private-network, and arbitrary hostnames
- log blocked requests with structural metadata, not raw secrets

Do not resolve or forward a helper-selected hostname merely because it is
same-origin-looking. The exact URL discovered from the live page, the effective
origin, and the Python session chain are the authority.

## Artifact priority

1. navigation / redirect URL
2. composed Cookie header / cookie string
3. single named cookie
4. localStorage / sessionStorage module
5. full encrypt-chain reverse

Stop escalating once Python can replay.

## Post-artifact noise

These are not automatic failures after a valid artifact exists:

- `navigation to another Document` / not implemented
- missing analytics endpoints
- later timer exceptions
- partial fingerprint API gaps that did not block artifact emission

## Coupling with other gates

- If the same param also has a short offline signer path, use `references/dual-writer-param-playbook.md` before choosing the product writer.
- If transport impersonation changes whether you receive JS challenge HTML versus another wall, fix transport admission first.
- If app-layer HMAC/sign is independent, prove whether challenge replay needs it at all.

## Delivery shape

```text
bare business request
  -> challenge HTML + script (same session)
  -> local challenge executor
  -> Python replay(redirectUrl or Cookie)
  -> pagination / concurrency
```

Report browser-free status as:

- browser-free collector with local challenge executor
- not fully runtime-free if a JS host remains

## Version-randomized helper boundary

When challenge scripts or dynamic VM assets change path every round:

1. hash the active asset
2. compare the public helper or VM call boundary, not only the URL
3. rerun fixed vectors from a clean success sample
4. if the boundary is stable, a tiny local opcode or wrapper scan helper may remain acceptable
5. rebuild a new helper version only when framing, vectors, or outputs diverge

Python still owns live HTTP, session order, waits, and acceptance. The helper must not become a browser.

## Common traps

- using Playwright or CDP page-driving as the product path
- letting the local helper choose arbitrary network destinations or own live HTTP
- requiring zero helper errors instead of a replayable artifact
- redownloading challenge scripts on a detached client after first-hop cookies already bound the chain
- rebuilding the whole encryptor after redirect URL already carries the decisive param
- forgetting original-URL echo fields on replay when evidence shows them

## Minimal handoff notes

Report:

- challenged route and content type
- helper host family
- which artifact won (`redirectUrl` / cookie / both)
- whether original-URL echo was required
- transport profile used for admission
- live regeneration proof on a fresh timestamp or page
