# SO Analysis Workflow

Use this reference when the task depends on JNI, native signing, anti-debug,
anti-Frida, packed loaders, self-decrypting libraries, crash offsets, or a
large APK with many native libraries. The goal is to reduce the native surface
to a small ranked target list, then correlate Java, runtime, and IDA/Ghidra
evidence.

## Output Contract

Keep these files in the analysis folder when the work is more than a quick
single-library inspection:

- `so_inventory.json`: all discovered `.so` files, ABI, size, SHA-256, ELF
  identity, hint categories, and notable strings.
- `native_bridge_index.json`: Java/Kotlin native declarations, loadLibrary
  sites, RegisterNatives hints, and class-to-library guesses. This can come
  from `scripts/jadx_triage.py`, manual notes, or an external indexer.
- `so_target_candidates.json`: ranked native libraries with score reasons.
- `selected_so_target.json`: the current primary target and why it was chosen.
- `so_static_triage.json`: exports/imports/strings/functions/sections from
  readelf, objdump, nm, IDA, or Ghidra.
- `jni_map.json`: native method name/signature/class to function or offset.
- `so_analysis_report.md`: evidence chain, findings, unresolved items, and
  next experiments.

## Target Selection

Start with all native libraries, including dumped or repaired files. Rank a
library higher when it has any of these signals:

- Loaded directly by app code: `System.loadLibrary`, `System.load`, or a
  loader class references the library name.
- JNI bridge: `JNI_OnLoad`, `RegisterNatives`, exported `Java_...` functions,
  `JNINativeMethod`, Java signatures, or native method strings.
- Business logic: request signing, crypto, device fingerprinting, token
  generation, `sign`, `encrypt`, `decrypt`, `AES`, `RSA`, `Hmac`, `MD5`,
  `SHA`, or timestamp/nonce fields.
- Protection logic: `ptrace`, `TracerPid`, `/proc/self/maps`, `frida`,
  `gum-js-loop`, `xposed`, `magisk`, `qemu`, `kill`, `tgkill`, `exit_group`,
  signal handlers, or suspicious thread names.
- Loader behavior: `dlopen`, `android_dlopen_ext`, `mmap`, `mprotect`,
  `memfd_create`, `prctl`, asset extraction, encrypted payload names, or
  anonymous executable ranges.
- ART hook behavior: `DexFileVerifier`, `OpenDexFilesFromOat`, `OpenMemory`,
  `makeDexElements`, `DexCache`, or `dexFile` references.
- VMP behavior: `libdexjni`, `JniLib`, `cV/cI/cL/cS/cB/cJ`, opcode/handler
  tables, JNI method dispatch, or type-specific native bridge methods.
- Runtime evidence: crash `pc/lr` resolves into the library, RegisterNatives
  logs point to its offsets, maps show a modified/unlinked mapping, or a dump
  window is tied to its constructor or `JNI_OnLoad`.
- Size and role: unusually large stripped libraries, shell/protector names,
  or app-specific names are usually better first targets than generic SDK
  libraries.

Do not pick a library only because it has many strings. Pick it because it has
the shortest evidence path to the user's goal.

## Static SO Pass

For each high-ranked target:

1. Record file path, ABI, SHA-256, size, ELF class, machine, build-id if
   available, stripped state, and whether section headers are present.
2. Inspect imports and exports:
   - JNI: `JNI_OnLoad`, `RegisterNatives`, `FindClass`, `GetMethodID`,
     `GetStaticMethodID`, `GetStringUTFChars`, exported `Java_...`.
   - Loader: `dlopen`, `android_dlopen_ext`, `dlsym`, `mmap`, `mprotect`,
     `memfd_create`, `prctl`, `pthread_create`.
   - Process and syscall: `ptrace`, `syscall`, `kill`, `tgkill`,
     `exit`, `exit_group`, `fork`, `clone`, `waitpid`.
   - Filesystem and procfs: `open`, `openat`, `readlink`, `stat`,
     `/proc`, `maps`, `fd`, `cmdline`, `status`, `mounts`.
   - Crypto/TLS: OpenSSL/BoringSSL symbols, hash/cipher names, certificate
     or pinning strings.
3. Inspect load-time code: `.init_array`, constructors, `JNI_OnLoad`, and
   early worker threads. Protected apps often fail or decrypt here.
4. If IDA/Ghidra is available, export summaries before deep manual work so the
   AI-side evidence map has functions, imports, strings, and xrefs.

When the file appears to be a shell SO, first locate init-array entry
candidates:

```bash
python3 android-native-auto-reverse/scripts/elf_init_array_finder.py libtarget.so --out analysis/libtarget_init_array.json
```

Use those candidates to guide IDA/Ghidra navigation. For protected SOs such as
`libDexHelper.so`, the first init-array routine may call a shell main function
that decrypts an inner image, applies XOR/RC4-like transforms, restores ELF
relocations, and jumps into the reconstructed code.

For SOs that decrypt their own text/data at load time:

- Identify the routine that copies encrypted segments into mapped memory.
- Watch the final `mprotect` calls. Two high-value windows are common:
  code segment permission restoration and data/GOT segment permission
  restoration.
- Dump immediately after those `mprotect` calls or at constructor leave.
- Analyze the dumped/decrypted image, not only the on-disk encrypted shell.

If IDA F5 fails because of OLLVM or stack-pointer damage, switch to
disassembly-first:

- enable stack pointer view and locate the instruction that breaks SP analysis,
- patch or NOP only in a copied analysis database,
- use instruction trace to keep real executed blocks and ignore bogus blocks,
- rename blocks from runtime evidence before trusting pseudocode.

## Java To Native Correlation

Build a bridge table with these columns:

```text
Java class | native method | signature | library guess | registration style | native function/offset | evidence
```

Use static names first, then improve the table with runtime RegisterNatives
logs. For dynamic registration, the function pointer from RegisterNatives is
usually more valuable than the visible Java method name. Convert it to
`lib.so!offset` using `/proc/<pid>/maps`.

## Runtime Correlation

Collect runtime evidence only when it answers a concrete question:

- `dlopen`/`android_dlopen_ext`: when and from where the target is loaded.
- constructors and constructor leave: whether a loader releases anonymous RX
  code, restores an inner image, or must be patched before the next library
  loads.
- RegisterNatives: Java method to native offset mapping.
- `/proc/<pid>/maps`: runtime base, split segments, anonymous executable
  ranges, deleted/unlinked library paths, and dump ranges.
- logcat/tombstone: crash signal, thread, `pc/lr`, and target `so!offset`.
- mprotect/mmap/memfd hooks: unpacking, self-decryption, OLLVM trampolines,
  or transient executable payloads.
- syscall evidence: direct checks that bypass libc wrappers.

Every runtime offset should be normalized as `library_name + offset`, with the
maps snapshot preserved.

## Multi-Library Protection Chains

For apps with several protection or risk-control libraries, do not stop after
the first bypass. Build a stage table:

```text
stage | process | library/range | load trigger | checks seen | patch/dump action | status
```

Common chain roles:

- early shell/exec loader: decrypts anonymous code, starts watcher threads,
  performs direct syscall checks;
- main exec library: coordinates constructor order, integrity checks, and handoff
  to real app code;
- emulator/risk library: checks qemu/nox/bluestacks/device properties, Java
  bridge checks, and timing;
- trust/device library: root, su, Magisk, KernelSU, package manager, and
  `faccessat`/`openat` probes;
- anti-hook library: Frida/Gum/maps/memfd/trampoline/JDWP/inline integrity
  checks.

Use one heavy trace only until the chain is understood. Convert the final bypass
to narrow stage patches and keep per-library patch status logs.

## Anonymous RX Dump And Repair

If the runtime maps show new executable anonymous or memfd ranges after a
constructor, dump those ranges even when the disk `.so` looks analyzable. The
real dispatcher, syscall wrappers, or anti-hook logic may only exist in the
runtime image.

Minimum evidence to keep:

- constructor or `mprotect/mmap` event that created the range;
- maps line with base, end, permissions, and path/name;
- dump command and range;
- rebuilt/fixed file path if an ELF wrapper was generated;
- IDA/Ghidra base used for analysis;
- mapping from runtime offset back to the original stage/library.

Do not over-invest in perfect section restoration. A loadable program-header
wrapper plus strings/functions around confirmed runtime offsets is usually
enough to continue.

## Direct Syscall And Fatal Edge Analysis

When exits are not caught by libc hooks, scan or trace inline syscalls in the
runtime image. For arm64:

- Treat syscall-tracer PC as "after syscall" unless verified; inspect `pc - 4`.
- Look backward from `svc #0` for `mov x8, #nr` or an equivalent register setup.
- Separate benign loader syscalls from fatal edges. `openat`, `read`, `clone`,
  and `mmap` can be normal; `kill`, `tgkill`, `exit`, `exit_group`, `brk`, or
  deliberate SIGSEGV/BRK paths need closer attention.
- For flattened code, patch the state/branch that selects the fatal edge when
  possible. Patching a dispatcher block or returning early from a mixed
  initialization/check function can cause splash hangs.

Record syscall number, address, preceding state/branch, and before/after result.

## IDA/Ghidra Deepening

- Load the original or dumped library with the correct ABI and runtime base.
- If the dump lacks section headers, rely on program headers and mapped
  segments; do not block the analysis on cosmetic section restoration.
- Rename functions from RegisterNatives, exported `Java_...`, crash offsets,
  and high-confidence string xrefs.
- For OLLVM/control-flow flattening, first mark dispatcher, state variable,
  real exits, and indirect branch targets. Pseudocode is secondary to
  disassembly around branches and syscalls.
- For Frida Stalker traces, normalize every runtime address to `module!offset`
  before opening IDA/Ghidra. Use call summary first to rank real callees, then
  call/ret traces to resolve indirect `BLR`/jump-table targets and recover the
  executed path through flattened code.
- For VMP/libdexjni code, build a table:

```text
native entry | return type | vmpId source | codeItem pointer | opcode decode | handler table | JNI side effect
```

Map handlers by observed JNI calls and side effects. A partial handler map is
still useful evidence, but do not present it as fully restored Dalvik bytecode.
- Export function/import/string summaries after each meaningful improvement.

## Frida Stalker For OLLVM

Use Stalker when static decompilation is dominated by flattened dispatchers,
bogus blocks, indirect calls such as `BLR Xn`, or jump tables that hide the
real algorithm.

Recommended workflow:

1. Identify a narrow native function entry from Java/JNI, RegisterNatives,
   request signing, or crash/runtime evidence.
2. Copy and edit the Stalker template:

```bash
cp android-native-auto-reverse/scripts/frida_stalker_ollvm_trace.js analysis/frida_stalker_target.js
# Edit TARGET_LIB and TARGET_OFFSETS.
frida -U -f com.example.app -l analysis/frida_stalker_target.js --no-pause
```

3. Run summary mode first:
   - collect `summary callee=lib.so!offset count=n`,
   - ignore imported/system APIs unless they carry key evidence,
   - rank repeated target-library callees and one-shot key transformation
     functions.
4. Enable call/ret trace only for the narrowed function window:
   - resolve indirect calls from caller offset to callee offset,
   - record real block/call order,
   - identify where interesting output first appears in arguments or return
     values.
5. Hook the high-value callees directly and dump arguments, return values, and
   backtraces. For crypto/signing recovery, look for plaintext, ciphertext,
   key, IV, constants, and buffer length changes.
6. Open the same `.so` in IDA/Ghidra at the correct base and label Stalker
   offsets. Compare:
   - Stalker summary frequency,
   - trace order,
   - static xrefs and constants,
   - argument/retval evidence.

Evidence table:

```text
offset | role guess | call count | first caller | args/retval evidence | IDA/Ghidra note | confidence
```

Pitfalls:

- Stalker is high overhead. Trace only the current thread while the target
  function is executing.
- `exec`/`block` events are noisy; use call summary before instruction traces.
- Arm64 support is generally stronger than arm32.
- Anti-Frida checks may detect Stalker side effects; keep bypass scripts and
  Stalker scripts separate until the stable bypass is known.
- Do not infer an algorithm only from a constant table. Confirm with runtime
  buffers and before/after output.

## Completion Criteria

An SO analysis is complete enough when it can answer:

- Which native library matters most, and why.
- Which Java/Kotlin call reaches the native behavior, or why it only starts
  from a constructor/loader path.
- Which function or offset implements the relevant crypto, detection, loader,
  or crash behavior.
- What runtime evidence confirms or disproves the static hypothesis.
- What exact next experiment would reduce the largest remaining uncertainty.
