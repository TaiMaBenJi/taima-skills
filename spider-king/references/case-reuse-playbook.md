# Case Reuse Playbook

Use this when an existing solved helper, prior collector, fixed-vector bundle, experience card, or case-like directory looks reusable for a new or continued target.

## Contents

- [Core Rule](#core-rule)
- [Selection Gate](#selection-gate)
- [Reuse Classes](#reuse-classes)
- [Read Order](#read-order)
- [Verification Loop](#verification-loop)
- [Sanitization](#sanitization)
- [Writeback](#writeback)
- [Failure Modes](#failure-modes)

## Core Rule

Reuse process and structure first, not live state.

A historical helper or case can suggest the next proof. It does not prove the current target until fresh fixed vectors or live acceptance pass under the current scope.

## Selection Gate

Select a reusable case only when one of these is true:

- exact scheme, host, port, route family, product generation, and protocol boundary match
- at least two independent high-confidence signals match, such as SDK family, cookie transition, request field placement, endpoint chain, verifier subtype, transport wrapper, or fixed-vector behavior

Never select from:

- one generic parameter name such as `sign`, `token`, `a_bogus`, or `_0x`
- one status code such as `403`, `412`, or `429`
- one cookie name without writer and transition evidence
- one non-empty helper output
- a comment, README claim, or stale chat transcript

When two cases match the same signals, do not choose by directory order. Ask for or collect a discriminator: product version, runtime family, request route, algorithm subtype, negative signal, or fixed vector.

## Reuse Classes

Label reused material honestly:

| Class | Meaning | Can prove current target? |
|---|---|---|
| `template` | historical process or shape only | no |
| `fixture-proof` | deterministic vectors pass offline | local proof only |
| `current-proof` | fresh target vectors or approved live replay pass | yes, within scope |
| `helper-only` | one narrow artifact generator | only the artifact boundary |

Do not describe snapshot-driven generation, artifact pools, or copied browser exports as pure algorithmic generation. Use the truth labels from `references/opaque-runtime-profile-playbook.md` when opaque state remains.

## Read Order

Prefer the current workspace before the skill library:

1. Existing project `analysis/proof_manifest.json`
2. Existing `js_reverse_cache/tasks/<task-id>/handoff.json`
3. Current stable helper or collector entrypoint
4. Fixed fixtures and tests
5. Minimal verifiable facts or experience card
6. Generic playbook

Read only enough to confirm or reject reuse. Do not load sibling cases after one case mismatches current evidence unless a new discriminator points to that sibling.

## Verification Loop

Before adapting a reusable helper:

1. Freeze the current target inputs and expected output.
2. Run fixed vectors first.
3. Compare the canonical wire boundary, not only the helper return value.
4. Confirm query/body/header/cookie slot placement.
5. Confirm current server-issued state and session scope.
6. Run one approved live replay only when the user requested and authorized it.

If fixed vectors fail, save the first divergence and stop live replay. If live `200` returns a challenge shell, empty business payload, or wrong content type, treat reuse as unproved.

## Sanitization

Reusable material may preserve:

- route shapes
- field names
- state provenance
- transform order
- fixed synthetic vectors
- hashes and lengths
- negative controls
- exact acceptance gates

Reusable material must not preserve:

- cookie/token values
- Authorization headers
- account identifiers
- browser profile exports
- full private HAR bodies
- absolute local paths
- one-time verifier rounds unless redacted and synthetic

When current state is required, pull it at runtime from an explicitly approved session and keep it out of the reusable case.

## Writeback

Offer writeback only after a successful delivery or local-proof that has:

- a stable import-safe entry
- fixed vectors or named checkpoints
- current-target acceptance status
- sanitized artifacts
- a negative control or first-divergence note
- no raw secrets

Default writeback is a small experience card or minimal verifiable facts. Create a structured case registry only when multiple independent tasks would benefit from machine selection.

## Failure Modes

| Trigger | First fix | Stop condition |
|---|---|---|
| Case matches one marker only | collect a second independent signal | no reuse |
| Historical helper emits a plausible token | run fixed vectors and wire slot diff | no live replay |
| Current endpoint changed shape | record mismatch and return to normal loop | no sibling guessing |
| Secret appears in the reusable material | redact and replace with shape/hash/provenance | no writeback until clean |
| Browser profile is required | extract the artifact boundary or mark retained exception | not a reusable collector |
