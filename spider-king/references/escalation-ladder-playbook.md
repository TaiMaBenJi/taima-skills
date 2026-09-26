# Escalation Ladder Playbook

Use this file when a partial proof tempts you to jump into a heavier runtime, broader patch surface, or route-specific transport exception.

The goal is to keep reverse work honest:

- prove the cheapest layer first
- move up one rung at a time
- record why the previous rung was insufficient
- stop before browser automation silently becomes the delivery path

## Contents

- [Core rule](#core-rule)
- [Universal ladder](#universal-ladder)
- [Promotion cues](#promotion-cues)
- [Bad jumps](#bad-jumps)
- [Ladder log](#ladder-log)
- [Final rule](#final-rule)

## Core rule

Do not jump multiple rungs.

Before moving up one rung, record all of these:

1. the freshest proof that still works
2. the exact failure or blind spot at the current rung
3. why the next rung is the smallest layer that can answer that failure
4. why the delivery gate still remains browser-free after the move

If you cannot write those four lines, do not escalate yet.

## Universal ladder

### Rung 0: Re-state the baseline

Prove:

- the startup gate is current
- the real request path is still the real request path
- the moving part is classified, not guessed

Stay here when:

- the family may have changed
- the route may be decoyed
- the request that fails was never proven on the real business path

Move up only when:

- the baseline is real, current, and still insufficient

### Rung 1: Fixed-input and wire diff

Prove:

- fixed-input helper parity
- exact query or body serialization
- exact field slot placement
- cookie provenance
- decode order on one frozen payload

Stay here when:

- a helper name may be misleading
- output differs but host dependence is still unproven
- the blob may be right in value but wrong in slot or framing

Move up only when:

- fixed-input or wire diff shows the remaining gap is not simple parity, placement, or decoding

### Rung 2: Narrow boundary observation

Prove:

- the canonical mutation point
- the narrowest stable ingress or egress boundary
- whether the runtime already emits the decisive artifact

Typical moves:

- initiator stacks
- wrapper tracing
- narrow request-bound hooks
- outbound header or body capture

Stay here when:

- the business code is still decoyed
- the mutation point is unknown
- a local runtime may not be needed if one stable harvest boundary exists

Move up only when:

- the boundary is known and the missing logic still depends on local execution

### Rung 3: Pure local reproduction

Prove:

- Python rewrite parity, or
- a tiny local JS or WASM helper with fixed-input checkpoints

Stay here when:

- the remaining logic is standard crypto, compact JSON, packet framing, decode work, or a tiny helper

Move up only when:

- the helper still depends on host-visible semantics such as `document.cookie`, parser order, timers, descriptors, or native-looking surfaces

### Rung 4: Narrow local host bootstrap

Prove:

- a local embedded runtime or bootstrap executor can recover one decisive artifact
- Python still owns the real HTTP replay

Acceptable artifacts:

- signed URL
- wrapped body
- token
- cookie string
- outbound `Cookie` header
- decoded payload

Stay here when:

- one local host-like stage is enough to recover the artifact

Move up only when:

- the runtime loads but the artifact shape is still structurally wrong because a specific host surface is missing

### Rung 5: Narrow host-surface patching

Prove:

- the missing gap is a specific host surface, not vague "browser-ness"

Typical surfaces:

- `canvas`
- WebGL
- layout metrics
- `getComputedStyle`
- `Function.prototype.toString`
- descriptors
- enumeration order
- parser order
- timer scheduling

Stay here when:

- the artifact gets closer as each narrow surface is restored

Stop climbing when:

- the flow still needs live rendering, gestures, or full browser state on each request
- the only remaining path is browser-backed replay

That is not a license to automate. It is a blocker report.

## Promotion cues

Use these cues to decide the next rung.

| Current symptom | Smallest honest next rung |
|---|---|
| Standard helper output differs on frozen inputs | Rung 1 |
| Query or body values look right but replay still fails | Rung 1 |
| You still do not know where the wire payload is mutated | Rung 2 |
| The mutation point is known and looks self-contained | Rung 3 |
| The code reads host objects or depends on timers or parser order | Rung 4 |
| Local runtime artifact is much shorter, simpler, or structurally wrong | Rung 5 |
| Only a real page can keep the flow alive end to end | Stop and report blocker |

## Bad jumps

Do not do these:

- Python mismatch -> jump straight to embedded runtime without fixed-input parity
- local helper loads -> jump straight to pagination scaling without one live replay
- one bad request -> switch to route-wide transport exceptions without an admission matrix
- unknown cookie writer -> hardcode the cookie and blame the signer
- local runtime still empty -> broaden patches randomly before identifying the missing surface

## Ladder log

Use this block when the next move is debatable.

```markdown
Escalation Ladder
- Current rung:
- Last proved artifact:
- Exact failure at this rung:
- Why the next rung is the smallest honest move:
- Browser-free delivery still preserved as:
```

## Final rule

The ladder exists to prevent fake progress.

Do not promote because the heavier layer feels more powerful.
Promote only because the lighter layer was disproven with evidence.
