# Verifier Error Localization Playbook

Use this when a verifier-gated flow still fails after packets look structurally
plausible, or when the target returns shifting reject codes/subcodes.

This playbook builds a **task-local** semantic map. Do not promote one vendor's
code table into universal doctrine.

## Contents

- [Goal](#goal)
- [Method](#method)
- [Task-local map template](#task-local-map-template)
- [Diagnostic order](#diagnostic-order)
- [Anti-cargo-cult rules](#anti-cargo-cult-rules)
- [Handoff](#handoff)

## Goal

Answer four questions in order:

1. Is the reject structural?
2. Is the reject missing a required sidecar or stage?
3. Is the reject a shared-state or timeline inconsistency?
4. Only then: is the reject answer/behavior/environment risk?

## Method

### Step 0: Freeze one round skeleton

Keep one ordered transcript id and do not mix fields across rounds.

Record:

- init or load response family
- required sidecars
- final verify request and semantic body
- first downstream consumer

### Step 1: Structure ablations

Create controlled missing or malformed fields one at a time:

- omit final token or device/proof field
- corrupt checksum or envelope framing
- send expired round id while keeping other fields

Expected result family: structural reject.

If the live code never changes under structural corruption, the code path you are reading is not authoritative.

### Step 2: Sidecar ablations

Using `references/verifier-replay-playbook.md`:

- full transcript
- omit or block telemetry/device family
- omit one warm-up or log stage only
- restore one stage at a time

Expected result family: sidecar necessity or risk gate.

### Step 3: Consistency ablations

- regenerate complete baseline and sparse delta independently
- desynchronize counters or gather-cost links
- re-roll fields that should be copied from DeviceConfig or init

Expected result family: shared-state reject.

### Step 4: Timeline ablations

- keep payload timestamps but remove real waits
- invert order of telemetry and final verify if the clean transcript is ordered

Expected result family: timeline or behavior risk reject.

### Step 5: Answer or behavior ablations

Only after steps 1-4:

- change track distance, point count, or answer packing
- swap clean human track versus synthetic track

Expected result family: answer/behavior reject.

### Step 6: Environment surface

If clean ordinary-browser success exists but automation or protocol still fails:

- grade samples with `references/positive-sample-hygiene-playbook.md`
- change exit or reduce consecutive rejects before more algorithm churn
- treat environment risk as first-class, not as track noise

## Task-local map template

Save secret-free notes like:

```markdown
Error Map
- Target family:
- Round scope:
- Code or subcode A:
  - produced by:
  - surface: structure | sidecar | consistency | timeline | answer | environment
  - recovery:
- Code or subcode B:
  - produced by:
  - surface:
  - recovery:
- Accepted semantic:
  - body fields that must hold together
- Downstream consumer pass oracle:
```

## Diagnostic order

Default order when a new reject appears:

```text
structure
  -> sidecar emission and acknowledgement
  -> shared baseline / sparse consistency
  -> real timeline
  -> helper/data packing
  -> answer or track
  -> environment risk
```

Stop at the first surface that controllably reproduces the reject family.

## Anti-cargo-cult rules

- do not hardcode another job's reject codes as universal truth
- do not treat HTTP 200 or a generic success envelope as acceptance
- do not continue trajectory search while structure or sidecar necessity is unknown
- do not call helper load success an oracle

## Handoff

When reporting:

- attach the ablation matrix path
- attach the task-local error map
- state which surface currently blocks delivery
- state the smallest next proof for that surface only
