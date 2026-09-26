# Positive Sample Hygiene Playbook

Use this when verifier-gated recovery needs human or browser oracles, especially
behavior-sensitive sliders, click orders, or risk-scored transcripts.

Browser tooling is for evidence only. Final delivery remains browser-free.

## Why hygiene matters

A real human action inside an automation-owned browser can still fail.

Common contaminants:

- CDP or remote-debugging ownership
- invasive hooks such as global function patches or stringify interceptors
- brand-new empty profiles with no ordinary browsing age
- consecutive reject history on one exit IP
- mixed rounds in one capture dump

Contaminated failures are useful as environment evidence. They are weak as proof
that the answer or track algorithm is wrong.

## Sample grades

Label every oracle:

| grade | meaning | authority |
|---|---|---|
| `clean-success` | ordinary browser or non-instrumented path, verifier accepted, downstream consumer passed | highest positive oracle |
| `clean-failure` | ordinary path failed with no automation ownership | strong negative for protocol or risk policy |
| `contaminated-failure` | automation, hooks, debug ports, or poisoned profile involved | environment evidence first |
| `partial` | missing sidecars, verify body, or downstream consumer | incomplete; do not over-interpret |

Never promote `contaminated-failure` into "trajectory family rejected" without a
clean contrast sample.

## Capture preference order

From best to worst for positive oracles:

1. User or operator ordinary browser, no automation attachment, export HAR or exact verify and consumer requests
2. Non-instrumented browser listen-only capture that does not inject page hooks
3. Automation browser used only to open a page, with no hooking, accepted only if clean ordinary capture is impossible
4. Hooked automation capture for initiator and field discovery, not as final positive truth

If the operator can pass in an ordinary browser and fails under automation, treat
that as environment risk until proved otherwise.

## Collaborative capture protocol

When protocol replay is stuck and a clean success sample is needed:

1. state exactly which URLs and actions the operator should perform
2. prefer the operator's daily browser over any agent-owned profile
3. ask for Network export of the full verifier round plus the first successful business response
4. if live listening is used, disable invasive hooks first
5. store the capture under the task cache and grade it immediately
6. redacted chat reports; raw tokens stay task-local

Ask only for the missing sample. Do not demand broad homework.

## Minimum fields for a usable success sample

- ordered request list with elapsed offsets
- init/load response family
- required sidecar requests and application acknowledgements
- final verify request and semantic success body
- answer or track payload if behavior-sensitive
- first downstream consumer request and business-pass body
- active helper or asset hashes when dynamic scripts are involved
- environment notes: ordinary vs automation, hooks on/off, exit changed or not

## How to use samples

- diff `clean-success` against protocol replay first
- use `contaminated-failure` to avoid false algorithm conclusions
- rebuild fixed vectors from clean success boundaries only when possible
- if only contaminated samples exist, say so and limit claims

## Hard bans

- do not tune tracks solely against automation hand-slide failures
- do not inject broad hooks just to "make capture easier" on the only positive path
- do not mix grants from a success round into a later failed round
- do not call a sample complete when the downstream consumer is missing

## Delivery notes

Report:

- sample grade
- capture path in task cache
- whether environment risk is implicated
- which clean boundaries were promoted into fixed vectors

Final collector still must replay without browser automation.
