# JSVMP Analysis Playbook

Use this file when the target wraps logic inside a custom VM or bytecode interpreter.

## Recognition signals

- opcode arrays
- dispatch loops switching on byte values
- tiny VM runtime with a large encoded program
- helpers hidden behind interpreter calls instead of direct JavaScript

## Working method

1. locate the VM entry point
2. map the public boundary first: identify what inputs go into the VM and what outputs, wrapper returns, state writes, or request egress come out
3. test the smallest closer-to-browser local execution path before full VM recovery; a real embedded engine or host runtime may execute the VM with far less work than devirtualization
4. if output drift still looks like a host-semantic problem, patch the host surface before touching opcode handlers or interpreter internals
5. if the public boundary is proven insufficient and a stable mode, transform, serializer, or packer dispatcher exists, capture ordered stage inputs and outputs there before tracing individual opcodes
6. preserve one complete run as an atomic capture and use `references/opaque-runtime-profile-playbook.md` when the local port depends on captured environment or opaque input blocks
7. avoid full VM recovery unless the protocol truly depends on it
8. prefer isolating the one helper output needed for the request
9. move to local execution or helper wrapping before attempting full devirtualization

## Common traps

- trying to devirtualize the whole VM when only one result matters
- missing side inputs passed into the VM entry point
- instrumenting opcode handlers, dispatch branches, or interpreter internals before proving the public boundary is insufficient
- mixing stage fragments from different successful runs before proving they are independent
- treating a captured final-artifact pool as proof that the VM transform was ported
- treating failure under Node, jsdom, or a thin shim as proof the VM cannot run locally at all

## Delivery rule

If a tiny helper wrapper around the VM output is enough for protocol replay, use that instead of heroic full recovery. Prefer public VM I/O, wrapper returns, state writes, or request egress over interpreter surgery whenever they solve the protocol. If a local port still consumes captured runtime profiles, report it as snapshot-driven rather than fully algorithmic.
