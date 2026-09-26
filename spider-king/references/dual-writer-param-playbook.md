# Dual-Writer Param Playbook

Use this playbook when one request field name can be written by more than one client path, and a short offline token shape is not the same as the live wire-success shape.

## Route here when

- the same query, header, or body key sometimes carries a short token and sometimes a long token
- offline recovery of one writer (hash, LZW, short signer) succeeds, but live replay still returns a challenge or empty shell
- call stacks show more than one path touching the field: open rewrite, send retry, challenge navigate, cookie-to-query injection
- sample exact-URL replay works, but fresh timestamps with the recovered short generator fail
- a session-stable prefix plus a URL-bound body appears on success, while research samples only produce compact compressed tokens

## Core idea

A parameter name is not a single algorithm.

Prove the **wire-success writer** before deep-porting any candidate writer.
Offline self-check on a secondary path is research evidence, not delivery proof.

## Fast execution path

1. Freeze two or more successful wire values for the same field.
   Record for each value:
   - length
   - fixed prefix / session segment
   - separators (`-`, `|`, `_`)
   - alphabet membership
   - URL, timestamp, page, or body binding
   - which request attempt produced it (first miss vs retry)

2. Classify writers, not just values.
   Common classes:
   - **short signer**: compact compress/hash of `url|ts|flag` style plaintexts
   - **long body**: session or environment prefix plus high-entropy or multi-segment body
   - **challenge rewrite**: challenge HTML/JS navigates or retries with a rewritten business URL
   - **cookie projection**: cookie material injected into query by an open hook

3. Map each class to a call stack.
   Prefer initiator stacks from live open/send/fetch hooks over source-only guesses.
   One field may be written by different classes under different gates (`kn`-style mode switches, captcha loaded, first failure HTML).

4. Live-accept only the class present on successful business responses.
   If short tokens never appear on successful wire samples, do not deliver a short-token generator as the product path.
   If long tokens appear only after challenge HTML, route to challenge artifact harvest first.

5. Prove binding and refresh separately.
   - URL-bound: changing timestamp/page invalidates the body
   - session-bound: prefix stable inside one challenge/session chain
   - cookie-bound: requires companion cookies
   - echo-bound: replay may need the original URL reflected in an extra field

6. Report dual-writer status explicitly.
   Name:
   - the research writer that was recovered but rejected live
   - the delivery writer that actually clears the gate
   - the remaining uncertainty if more than one success class still exists

## High-value checks

- Do successful samples share one length band, or two disjoint bands?
- Does the short path exist in SDK source but only run when a mode flag is zero/one?
- Does the long path appear only on the second attempt after HTML challenge?
- Does app-layer HMAC/sign exclude the verifier param while still being required on browser XHR?
- Can the challenge path succeed without the app signer, or the reverse?

## Common traps

- treating the only fully decompiled writer as the only real writer
- concatenating a known session prefix onto a short body and calling it long-token recovery
- declaring protocol automation done after sample exact replay
- continuing encrypt reverse after a challenge helper already emits the rewritten URL
- merging app signer recovery and verifier recovery into one unfinished ticket

## Delivery guidance

Preferred order:

1. identify the wire-success class
2. harvest or regenerate that class on a fresh URL
3. only then paginate
4. keep rejected writers in analysis notes as misleading signals

Helper I/O, when the success class is challenge rewrite:

- Python owns live HTTP
- local helper returns `redirectUrl` and/or `cookieString`
- Python replays and validates business JSON/HTML anchors

## Minimal handoff notes

Report:

- field name and success shape summary (length bands, prefix rule)
- writer classes found
- which class is live-accepted
- which class is misleading
- binding: URL / session / cookie / echo
- whether app signer and verifier gates are independent
