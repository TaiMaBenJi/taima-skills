# Opaque Runtime Profile Playbook

Use this playbook when an opaque signer, fingerprint payload, telemetry sidecar,
verifier proof, or packed request is assembled through multiple runtime stages
and a local port needs captured environment or state inputs to match it.

Route here when:

- the public VM or helper boundary is known but does not expose the first
  divergent transform
- a stable mode, transform, serializer, or packer dispatcher exists
- complete captured runs replay, while fragments from different runs fail
- a Python port matches only when one complete runtime input profile is frozen
- a pool of accepted artifacts risks being mistaken for fresh local generation

Do not route here merely because a bundle is obfuscated. Prove the public
input, output, state write, or request egress first. Use mode-level tracing only
after the outer boundary is proven insufficient.

## Contents

- [Core rules](#core-rules)
- [Truthful delivery classes](#truthful-delivery-classes)
- [Evidence authority](#evidence-authority)
- [Recovery workflow](#recovery-workflow)
- [Pool controls](#pool-controls)
- [Verification gates](#verification-gates)
- [Common traps](#common-traps)
- [Delivery record](#delivery-record)

## Core rules

1. One complete successful run is one atomic evidence unit.
2. Instrument the narrowest stable stage boundary, not every opcode.
3. Preserve unknown bytes as opaque values until evidence names them.
4. Fixed-input byte parity is local proof; live business acceptance is final
   proof.
5. Report whether delivery is algorithmic, snapshot-driven, or pool-backed.

## Truthful delivery classes

Keep these classes separate in code, reports, and completion claims.

### Algorithmic generation

The collector reconstructs every decisive transform and can produce fresh
accepted artifacts from explicit current inputs without a captured artifact or
captured runtime profile.

This class describes issuance independence, not implementation language.
Report separately whether the implementation is pure Python, uses a tiny local
JS or WASM helper, or still depends on another runtime.

### Snapshot-driven generation

The collector runs the recovered transforms locally but still selects a whole
captured runtime profile containing environment, opaque, or version-specific
inputs.

This can be browser-free and runtime-free during normal execution, but it is
capture-dependent. Prove profile freshness, scope, and upgrade behavior. Do not
describe it as fully generative when the profile writer is still unknown.

### Pool-backed replay

The collector selects a previously accepted final artifact or token from a
pool. No local transform necessarily runs.

Treat this as a diagnostic control or an explicitly accepted bounded fallback,
not proof that generation was recovered. A large pool does not solve issuance,
expiry, session binding, single-use behavior, or refresh.

## Evidence authority

Resolve conflicts in this order:

1. final wire artifact and downstream business acceptance
2. clean runtime stage trace from the active asset
3. fixed-input local stage trace
4. decoded final payload and measured segment offsets
5. actively served source and runtime configuration
6. inferred field names, comments, or remembered layouts

Length, prefix, and plausible encoding are triage signals. They are not byte
parity or target acceptance.

## Recovery workflow

### 1. Freeze one clean baseline

Record one successful run before adding broad instrumentation:

- active script, bytecode, WASM, or bundle hash
- helper and runtime version
- route family and request slot that consumes the artifact
- explicit config and session scope
- timestamp, random, nonce, and environment-input policy
- final artifact bytes or a local secret-bearing specimen
- downstream response family and business acceptance anchor

Keep raw secret-bearing traces task-local. Store hashes and redacted structure
in reports.

### 2. Prove the outer boundary

Map:

- public VM or helper inputs
- wrapper return values
- authoritative state writes
- request egress mutation
- final consumer and exact field slot

If this boundary is enough to reproduce the artifact, stop there. Do not open
the interpreter merely because it looks interesting.

### 3. Capture stable stage checkpoints

When the outer boundary is insufficient, prefer a dispatcher, transform table,
serializer entry, or packer call that every decisive stage crosses.

For each call capture:

- sequence index and stable stage name or mode identifier
- occurrence number when one stage repeats
- exact input and output bytes
- input and output lengths
- encoding used to serialize the trace
- explicit side inputs that can change the output
- clean versus instrumented artifact hash

Avoid broad opcode logging until stage-level evidence proves the decisive
transform cannot be isolated. Compare a clean run with an instrumented run to
detect observer effects.

Use this minimal trace shape with `scripts/transform_trace_diff.py`:

```json
{
  "trace_version": 1,
  "source": {
    "artifact_sha256": "redacted-or-hash",
    "runtime": "name-and-version"
  },
  "stages": [
    {
      "name": "normalize",
      "input": {"encoding": "base64", "data": "..."},
      "output": {"encoding": "base64", "data": "..."}
    },
    {
      "name": "pack",
      "input": {"length": 128, "sha256": "..."},
      "output": {"length": 96, "sha256": "..."}
    }
  ]
}
```

Raw descriptors enable first-byte mismatch reporting. Redacted descriptors
with only `length` and `sha256` preserve comparison without copying secret
bytes into reports.

### 4. Build a segment map

Decode the final artifact only as far as evidence supports. Derive segment
boundaries from observed stage output lengths, fixed prefixes, delimiters,
length fields, and wrapper framing.

For every segment record:

- offset and length
- producing stage and occurrence
- whether the segment is transformed output, copied input, wrapper metadata,
  or an unexplained gap
- encoding and endianness
- stability across repeated clean captures

Keep unexplained gaps opaque. Do not rename bytes merely because one sample
resembles a timestamp, platform value, or checksum.

### 5. Build an atomic runtime profile

A runtime profile should preserve one internally consistent run:

- profile id and capture hash
- active asset and runtime versions
- explicit environment and config inputs
- each input's source and semantic-confidence level
- opaque blocks with offsets and hashes
- stage inputs required for local generation
- expected final artifact hash for deterministic proof
- session, route, account, and freshness scope when known

Use confidence labels such as `observed-name`, `behavior-proven`, and `opaque`.
Names copied from source are not behavioral proof.

Store volatile captures in task-local evidence, separate from stable helper
code. Do not hide a large rotating artifact pool inside compressed source and
call it an algorithm.

### 6. Port one transform at a time

Reimplement the smallest stage, compare its fixed input and output, then move
to the next stage. Check common cross-runtime hazards:

- custom Base64 alphabet, padding, or byte-to-text conversion
- UTF-8 versus UTF-16 code-unit behavior
- signed shifts, integer overflow, and endian order
- JavaScript double precision and rounding
- varint, TLV, compact JSON, and length-prefix rules
- object key order and normalization
- source arrays versus returned transformed bytes

Run `scripts/transform_trace_diff.py` after each change. Fix the first
divergent stage instead of compensating in a later segment.

### 7. Prove whole-profile consistency

Do not splice headers, environment blocks, random blocks, gaps, or tails from
neighboring successful runs unless a controlled test proves those parts are
independent.

Use negative controls:

- change one known input and confirm the expected stage changes
- splice one suspected-independent segment and observe whether acceptance or
  byte parity breaks
- tamper one opaque block and confirm the validator can detect rejection

If only whole captures work, select complete profiles as atomic units. Preserve
correlated fields together.

### 8. Separate proof randomness from live generation

Deterministic proof mode freezes profile, timestamp, nonce, random bytes, and
other moving inputs. It must reproduce every stage and the final artifact.

Live-generation mode refreshes only fields whose writers and variability are
proven. Do not independently randomize opaque bytes or correlated profile
segments. Whole-profile selection is safer than segment mixing, but it remains
snapshot-driven unless the profile itself can be regenerated.

### 9. Validate freshness and scope

After full byte parity, test the smallest acceptance matrix that answers the
real uncertainty:

- fresh artifact on the original session
- second use on the same session
- same artifact on a different clean session
- newly generated artifact from the same profile
- different complete profile on the same route
- first downstream business request that consumes the artifact

Change one variable at a time. Do not add concurrency until one fresh
single-request path repeats successfully.

### 10. Stratify failures

Keep these layers separate:

1. capture or trace corruption
2. transform or cross-runtime parity failure
3. final composition, encoding, framing, or slot-placement failure
4. freshness, session, account, route, or transcript mismatch
5. transport, proxy, timeout, or connection failure
6. target rejection, cooldown, or permission failure

Do not merge network exceptions into server rejection counts. A changed error
family can prove progress without proving success.

## Pool controls

Use a prevalidated pool only when it answers a specific diagnostic question or
the user explicitly accepts a bounded fallback.

Require:

- complete artifacts with provenance, not mixed fragments
- known session and freshness scope
- one-shot or least-used consumption only when reuse tests justify it
- explicit exhaustion behavior
- separate statistics for pool acceptance, locally generated acceptance, and
  transport exceptions
- a no-pool test that reveals whether the collector can mint a fresh artifact

If removing the pool stops all successful requests, generation is not solved.

## Verification gates

Pass every applicable gate:

1. clean baseline and active asset hash recorded
2. public boundary proven before stage instrumentation
3. trace schema validates and stage order is stable
4. each ported stage matches on deterministic vectors
5. final decoded bytes and wire artifact match
6. negative splice or tamper controls behave as expected
7. fresh live business replay succeeds repeatedly
8. session, freshness, and reuse scope are stated
9. delivery class is reported truthfully
10. final collector works without a live browser or page context

## Common traps

- instrumenting every opcode before proving the wrapper boundary insufficient
- naming opaque bytes from one sample and then randomizing them
- fixing a later segment to hide the first divergent stage
- mixing complete successful profiles into an unobserved combination
- treating a high pool acceptance rate as proof of fresh generation
- embedding captured artifacts in source without provenance or expiry controls
- calling snapshot-driven generation fully algorithmic
- treating compile success, token shape, or helper load as live acceptance
- scaling concurrency before one fresh no-pool replay is stable

## Delivery record

Report:

- active asset and runtime hashes
- outer boundary and chosen stage checkpoint
- stage trace paths and first-divergence result
- segment map and opaque fields
- deterministic parity vectors
- profile atomicity and negative-control result
- freshness, session, reuse, and route scope
- no-pool test result
- delivery class: algorithmic, snapshot-driven, or pool-backed
- final browser-free and runtime-free status
