---
name: firmware-bringup
description: Bring up a firmware target in ripcord from opaque binary to an execution-verified hardware-boundary (MMIO) transcript. Use when the user wants to emulate a firmware target, capture how the MCU drives a peripheral or opaque device (FPGA/ASIC), reverse-engineer a hardware protocol, triage why a firmware image won't boot in Renode, or reproduce/extend the FNIRSI scope bring-up. Chains identify → pipeline → boot-triage → decompose → function-level emulation → reconcile.
---

# Firmware bring-up (ripcord)

Drive a firmware target from opaque binary to an **execution-verified
hardware-boundary transcript** in the `mmio_events` warehouse. The full,
authoritative recipe — with the decision points — lives in
`notes/firmware-bringup-runbook.md`. **Read that file first**, then execute
the phases below. The worked example (FNIRSI 2C53T) is in
`notes/renode-at32-bringup.md`; the static protocol it verifies against is
`notes/scope_acquisition_spec.md`.

This skill is the ripcord thesis in miniature: convert a *static* hypothesis
about how the MCU drives its hardware into an *observed* transcript. For an
opaque peripheral, that transcript is the reverse-engineered interface.

## Operating rules

- **Confidence discipline.** Tag every claim by provenance. A value the
  firmware wrote is observed; a reply the stub invented is `unverified` until a
  hardware trace confirms it. Never present an inferred FPGA/peripheral reply as
  fact. (See `notes/confidence-scheme.md`.)
- **Don't fake a cold boot for a two-stage image.** If boot triage shows the
  app isn't independently cold-bootable (Phase B decision), pivot to
  function-level emulation — do not invent bootloader context to force the
  reset path.
- **Prefer empiricism over theory.** When unsure why execution stalls, run it
  and read the trace; each stall names the next thing to model. Don't
  over-reason a disassembly when a 2-second emulation answers it.
- Work the existing tools; don't re-implement what's listed. Add a target via
  `config.yaml` only — no new pipeline stages without the user's ask.

## Phases (see the runbook for the decision points)

1. **Ingest.** `scripts/identify.py <binary>`; add to `config.yaml`
   (`base_addr` + `raw_binary: true` for raw images); run
   `snakemake --cores 4 --resources ghidra=1`.
2. **Boot triage.** Boot from the reset vector with a platform `.repl`
   (reuse `scripts/renode/at32f403a.repl` for STM32F1-class chips). Classify:
   progresses / `configASSERT`-hang / status-poll spin / **two-stage**. Use the
   runbook's red-flag checklist to detect not-cold-bootable images.
3. **Function-level emulation** (if not cold-bootable):
   - find the driver via `peripheral_xrefs`;
   - split monster functions with `scripts/analysis/decompose.py`;
   - recover command bytes + the entry register context with
     `scripts/analysis/disasm.py` (`--filter skeleton` / `--filter calls`);
   - extend the peripheral stub (the `scripts/renode/fpga_protocol.py` pattern);
   - run `scripts/renode/emulate_function.py --target T --entry <lo>
     --stop <after-key-op> --reg <base-regs> --mem <globals> --run`.
4. **Reconcile.** Diff the captured transcript against the static spec; upgrade
   confirmed facts `static-inferred → execution-verified`; iterate the
   poll/assert-satisfaction loop until the boundary runs to completion. Record
   each promoted fact as a contract via `scripts/contracts/ledger.py` (see the
   `execution-verify` skill) — the ledger, not prose, is the durable result.

## Function-level emulation techniques (hard-won)

These generalize to any two-stage / RTOS firmware where you enter a function
without the full boot context:

- **Enter past a blocking RTOS primitive.** A task that opens with
  `xQueueReceive(…, portMAX_DELAY)` spins forever in emulation (the queue is
  empty). Enter at the *post-receive* PC instead and stage the received value
  in memory: `--reg sp=… --reg <base regs> --mem <stack slot>=<cmd byte>`. Read
  the prologue with `disasm.py` to recover the exact register context
  (peripheral base, state base, stack-arg slot) the skipped prologue would have
  set.
- **NOP-patch a boot/scheduler-dependent helper via `--mem`.** A `bl` to a
  FreeRTOS yield/delay (writes `0x10000000` PENDSVSET to ICSR `0xE000ED04`) or
  a timer-list walk needs scheduler state the entry skips, and it spins. Flash
  is a writable `MappedMemory`, so rewrite the call site to two Thumb NOPs:
  `--mem 0x<callsite>=0xBF00BF00`. **Do not** try to skip it with a PC←LR hook —
  Renode does not cleanly redirect PC from a block-begin hook (it desyncs or
  halts). The flash patch is deterministic.
- **Share one peripheral model across stubs.** Renode runs every
  `Python.PythonPeripheral` in one IronPython engine and imports a module once,
  so a module-level singleton (`fpga_protocol.get_model()`) lets e.g. a GPIO
  stub drive `set_cs()` and the SPI stub read the same `FpgaModel` — model the
  real handshake instead of a hardcoded shortcut.
- **Prove a data path with a distinguishable pattern.** Set
  `RIPCORD_FPGA_SAMPLE_PATTERN=1` so idle reads return an incrementing counter;
  a buffer that fills `02 03 04…` proves each clocked-in byte reached the MCU
  buffer. Gate the pattern on a handshake line (CS) to *also* prove a GPIO stub
  drives the model — a counter-filled buffer can then only mean CS was asserted.
- **A spin balloons the trace to multiple GB.** Always cap `--duration` /
  `--timeout`, watch for the "trace still growing" warning, and
  `rm build/*_fn_*_trace.log` after each run. A 240 s spin once wrote a 4.8 GB
  trace.

## Output

Report: where boot triage landed (and why), the isolated driver function/phase,
the captured MMIO/command sequence, what it confirmed vs corrected in the static
spec, and the next stall to satisfy. Log a dated run entry in the relevant
`notes/*-bringup.md` so the loop's progress is durable.
