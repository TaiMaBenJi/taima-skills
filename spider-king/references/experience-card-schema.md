# Experience Card Schema

Use an experience card to preserve one repeated decision rule or deterministic operation. A card is not a case report, a target recipe, or permission to trust historical output on a current target.

## Contents

- [Storage Lifecycle](#storage-lifecycle)
- [Candidate Shape](#candidate-shape)
- [Promoted Shape](#promoted-shape)
- [Promotion Gate](#promotion-gate)
- [Consumption Rule](#consumption-rule)

## Storage Lifecycle

Keep a one-job candidate under the task project:

```text
<project>/js_reverse_cache/tasks/<task-id>/experience-candidate.json
```

Promote a card into `references/experience-cards/<card-id>.json` only while maintaining this skill and only after the Reproducible Experience Gate in `references/skill-maintenance.md` passes. Promoted cards and their fixtures must be secret-free. Never copy raw task captures, target URLs, accounts, cookies, tokens, keys, headers, or private responses into the skill.

## Candidate Shape

A one-job candidate is deliberately allowed to be incomplete. Record known facts, use `null` for evidence that does not exist, and list every unmet promotion gate. Never invent a fixture path, oracle, second reproduction, first divergence, or validation command.

```json
{
  "schemaVersion": 1,
  "id": "generic-family-boundary-invariant",
  "status": "candidate",
  "title": "Short structural lesson",
  "invariant": "One provisional binary or measurable statement",
  "scope": {
    "family": "signer-gated | verifier-gated | decode-gated | session-gated | transport-gated",
    "boundary": "request | response | runtime | transport | session | verifier",
    "appliesWhen": ["observed structural condition"],
    "stopsWhen": []
  },
  "reproductions": [
    {
      "jobFingerprint": "sha256 of a non-secret job identity",
      "observedAt": "YYYY-MM-DD",
      "artifactSha256": "64 lowercase hex characters",
      "independent": true
    }
  ],
  "fixture": null,
  "oracles": {
    "positive": null,
    "negative": null
  },
  "firstDivergence": null,
  "decision": {
    "preferredRoute": null,
    "action": "provisional smallest action",
    "fallback": null
  },
  "validation": null,
  "missingPromotionRequirements": [
    "second-independent-reproduction",
    "secret-free-fixture",
    "positive-oracle",
    "negative-control",
    "first-divergence",
    "stops-when-boundary",
    "validation-command"
  ]
}
```

Candidates stay task-local and are never consumed as reusable cards. At minimum, preserve one secret-free invariant, its observed applicability boundary, and the supporting task artifact hash in `reproductions`; put every absent gate name in `missingPromotionRequirements`.

## Promoted Shape

```json
{
  "schemaVersion": 1,
  "id": "generic-family-boundary-invariant",
  "status": "promoted",
  "title": "Short structural lesson",
  "invariant": "One binary or measurable statement",
  "scope": {
    "family": "signer-gated | verifier-gated | decode-gated | session-gated | transport-gated",
    "boundary": "request | response | runtime | transport | session | verifier",
    "appliesWhen": ["observable structural condition"],
    "stopsWhen": ["counter-condition or unsupported boundary"]
  },
  "reproductions": [
    {
      "jobFingerprint": "sha256 of a non-secret job identity",
      "observedAt": "YYYY-MM-DD",
      "artifactSha256": "64 lowercase hex characters",
      "independent": true
    }
  ],
  "fixture": {
    "path": "skill-relative secret-free fixture path",
    "sha256": "64 lowercase hex characters",
    "generator": "optional deterministic generator path",
    "secretFree": true
  },
  "oracles": {
    "positive": "decisive downstream assertion and command",
    "negative": "one intentional mutation and expected protocol failure"
  },
  "firstDivergence": {
    "stage": "ordered stage name or index",
    "path": "redacted structural path",
    "kind": "missing | value | order | framing | state | transport"
  },
  "decision": {
    "preferredRoute": "Spider route name",
    "action": "smallest reusable action",
    "fallback": "named fallback when the boundary does not hold"
  },
  "validation": {
    "lastVerifiedAt": "YYYY-MM-DD",
    "command": "deterministic local validation command"
  }
}
```

## Promotion Gate

A `promoted` card must have:

1. Two or more genuinely independent reproductions with distinct job fingerprints. Each reproduction identifies its supporting artifact hash; hashes may match only when independent provenance is otherwise proved and identical bytes are the invariant under test.
2. One minimal fixture or deterministic generator whose SHA-256 is recorded.
3. A positive oracle that reaches the decisive downstream behavior.
4. A negative control that fails for the expected protocol reason.
5. The first divergent state transition.
6. Explicit `appliesWhen` and `stopsWhen` boundaries.
7. A local validation command that passes from a clean checkout or copied skill directory.

Changing only expected output, timestamp, nonce, or filename does not create an independent reproduction. Prose-only prompts, copied live values, plausible token shape, helper load, or one HTTP `200` do not satisfy the gate.

## Consumption Rule

Use a card as a hypothesis accelerator:

1. Match the current evidence to every `appliesWhen` condition.
2. Run the card fixture and both oracles.
3. Prove one current-target minimal fact at the same boundary.
4. Stop using the card when any `stopsWhen` condition appears.

Historical cards never replace current wire evidence, a fixed vector, or downstream acceptance. Retire a card when its fixture cannot be reproduced, its boundary becomes too broad, or two independent counterexamples invalidate the invariant.
