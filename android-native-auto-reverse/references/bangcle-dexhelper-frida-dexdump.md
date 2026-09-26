# Bangcle libDexHelper And frida-dexdump Workflow

Use this reference when shell triage finds Bangcle/Bangbang features such as
`libDexHelper.so`, `libDexHelper-x86.so`, `libSecShell.so`, `libsecexe.so`, or
`libsecmain.so`, or when visible Java is only a shell and the user asks for
梆梆, Bangcle, libDexHelper, frida-dexdump, or dex unpacking.

## Recognition

Strong static signs:

- Native libraries: `libDexHelper.so`, `libDexHelper-x86.so`,
  `libSecShell.so`, `libsecexe.so`, `libsecmain.so`.
- Stub Java: shell `Application`, custom `attachBaseContext`, tiny or
  wrapper-only `classes.dex`, reflection-heavy bootstrap, or no useful
  business classes in JADX.
- Encrypted payloads: suspicious files under `assets/`, especially jar/dex/dat
  files that are not normal archives.
- Native loader behavior: `JNI_OnLoad`, constructor/init code, `mmap`,
  `mprotect`, `dlopen`, `android_dlopen_ext`, or class-loader APIs.

Treat `libDexHelper.so` as a high-value loader target. It may decrypt dex,
restore methods, load payloads, or hand control back to the real application.

## Static First Pass

1. Run shell recognition:

```bash
python3 android-native-auto-reverse/scripts/scan_apk_shell.py target.apk --json > shell_scan.json
```

2. Decompile enough to prove the visible dex is a shell:

```bash
apktool d -f target.apk -o apktool_out
jadx --no-debug-info --show-bad-code target.apk -d jadx_out
python3 android-native-auto-reverse/scripts/jadx_triage.py jadx_out > jadx_triage.txt
```

3. Inventory and rank native libraries:

```bash
python3 android-native-auto-reverse/scripts/so_inventory.py apktool_out --out analysis/so_inventory.json
python3 android-native-auto-reverse/scripts/native_target_ranker.py --so-inventory analysis/so_inventory.json --out-dir analysis/native_rank
```

4. If `libDexHelper.so` appears, inspect it as both a loader and a possible
   self-decrypting library. Prioritize `.init_array`, `JNI_OnLoad`,
   `RegisterNatives`, `mmap`, `mprotect`, dex magic/string references, and
   asset extraction paths.

## libDexHelper Shell SO Decryption Pass

Some Bangcle enterprise samples expose only a small outer `libDexHelper.so` in
IDA. The real inner library may be decrypted by the outer loader during
initialization. A practical static route is:

1. Copy the exact installed library from the device or APK extraction and keep
   its SHA-256.
2. Open it in IDA and record the initial function/import count. Very few named
   functions plus loader-heavy code is a shell-so signal.
3. Locate the load-time entry through ELF dynamic metadata:

```bash
python3 android-native-auto-reverse/scripts/elf_init_array_finder.py libDexHelper.so --out analysis/libDexHelper_init_array.json
```

4. In IDA, jump to the first high-confidence `.init_array` target. In the
   article case, `.dynamic` exposed `DT_INIT_ARRAY`, relocation data, and an
   `.init_array[0]` target that led to a small init stub, then the shell main
   routine.
5. In the shell main routine, label high-value call sites by behavior, not just
   by guessed names:
   - stream/block decryptor, often RC4-like
   - XOR or simple byte transform
   - ELF relocation or import restoration
   - memory copy/decompression
   - jump or handoff to the restored image
6. If a script or manual reconstruction produces `libDexHelper_inner.so`, load
   that output in IDA/Ghidra and compare function count, imports, strings, and
   JNI/loader hints against the outer shell. A large jump in function count is
   strong evidence that the shell SO was decrypted.

### Static Outer-SO Reconstruction Pattern

Recent enterprise-style `libDexHelper.so` samples may decrypt an embedded inner
ELF with a two-stage transform:

- a short header window decrypted with an RC4-like stream cipher,
- the remaining payload decrypted with a simple byte transform such as XOR,
- a later relocation/import-restoration routine before control is transferred.

Do not assume these constants are reusable across samples. Extract them from the
current binary:

1. Use `elf_init_array_finder.py` to locate `.init_array` candidates and
   relative relocations that seed the loader entry.
2. In IDA/Ghidra, follow the init stub to the shell main routine. Label calls by
   behavior:
   - key material read or derivation,
   - header decryptor or stream cipher,
   - body decryptor or XOR loop,
   - relocation/import repair,
   - handoff into the restored image.
3. Record payload start, optional payload size, key-material offset, header key
   length, header decrypt length, and byte transform key. Keep all values tied
   to the original file SHA-256.
4. Reconstruct with the bundled helper when the observed algorithm matches the
   RC4-like-header plus XOR-body pattern:

```bash
python3 android-native-auto-reverse/scripts/bangcle_dexhelper_inner_decrypt.py \
  libDexHelper.so \
  -o analysis/libDexHelper_inner.so \
  --payload-offset 0x8000 \
  --key-material-offset 0x104e3d \
  --header-key-len 0x10 \
  --header-decrypt-len 0x40 \
  --xor-key 0x19 \
  --json analysis/libDexHelper_inner_decrypt.json
```

5. Validate the output before using it as evidence:

```bash
file analysis/libDexHelper_inner.so
readelf -hW analysis/libDexHelper_inner.so
python3 android-native-auto-reverse/scripts/so_inventory.py analysis/libDexHelper_inner.so --out analysis/libDexHelper_inner_inventory.json
```

6. Load the inner SO into IDA/Ghidra. Compare outer versus inner function count,
   string richness, imports, JNI registration, dex/class-loader references, and
   anti-analysis routines. Continue offset work against the inner file only
   after noting that its offsets are no longer the same artifact as the outer
   shell.

If the helper output does not begin with ELF magic, do not force it. Re-check
the payload offset, key source, decrypt window, endianness, and whether the
sample uses compression or a different cipher before the XOR/body phase.

Keep both files:

- `libDexHelper_outer.so`: original protected library.
- `libDexHelper_inner.so`: decrypted/reconstructed candidate.

Then run:

```bash
python3 android-native-auto-reverse/scripts/so_inventory.py libDexHelper_outer.so libDexHelper_inner.so --out analysis/dexhelper_outer_inner_inventory.json
idat64 -A -S"android-native-auto-reverse/scripts/ida_export_native_summary.py analysis/libDexHelper_inner_ida.json" libDexHelper_inner.so
```

If the inner SO contains much richer JNI, dex, loader, crypto, or relocation
surface, continue native analysis on the inner SO and keep offsets clearly tied
to the file/base used.

## frida-dexdump Runtime Flow

Use frida-dexdump only on authorized devices and samples.

1. Confirm Frida can attach:

```bash
adb devices
adb shell getprop ro.product.cpu.abi
frida-ps -Uai | grep -i target
```

2. Start from a spawn or attach strategy:

```bash
frida-dexdump -U -f com.example.app -o dumps/com.example.app --sleep 8
frida-dexdump -U -n com.example.app -o dumps/com.example.app -d --sleep 5
python3 -m frida_dexdump -U -f com.example.app --sleep 15 -d -o dumps/com.example.app
```

Use `-f` when the real dex is created during startup. Use `-n` when the app
must be manually driven to a screen before payload dex appears. Use deep search
when normal search produces only shell dex.

3. If dumps are empty or shell-only, increase timing and trigger app flows:

- after shell `attachBaseContext`
- after shell `Application.onCreate`
- after first Activity starts
- after login, feature entry, plugin load, or native loader initialization
- after `libDexHelper.so` maps appear in `/proc/<pid>/maps`

4. Preserve the runtime context:

```bash
adb shell pidof com.example.app
adb shell cat /proc/<pid>/maps > dumps/com.example.app/maps.txt
adb logcat -d -v threadtime > dumps/com.example.app/logcat.txt
```

## Optional Loader Watch

When timing is unclear, run the bundled loader watcher before dexdump:

```bash
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_watch_dex_loading.js --no-pause
```

Watch for:

- `System.loadLibrary` or `System.load` loading `DexHelper`, `SecShell`, or
  `secexe`.
- `DexClassLoader`, `PathClassLoader`, `InMemoryDexClassLoader`, or
  `DexFile.loadDex`.
- `/proc/<pid>/maps` showing the shell library and any anonymous executable
  ranges.

Use those timestamps to choose `--sleep` or the screen/action that should
precede `frida-dexdump`.

## Frida Detection And exit_group Bypass Triage

Use this section when a Bangcle/libDexHelper target starts normally but crashes,
disconnects Frida, or exits after entering the home screen or after Frida
attach/spawn. Treat this as an anti-analysis symptom until logcat/tombstone
proves otherwise.

Common libDexHelper detection surfaces:

- Frida server port probing, especially `127.0.0.1:27042` and nearby ports.
- WebSocket or D-Bus style probes against Frida defaults.
- `/proc/self/maps` scanning for `frida`, `gum-js-loop`, `gum-js-loop`,
  `gadget`, `re.frida`, injected agent paths, suspicious anonymous RX ranges,
  or non-whitelisted mappings.
- `/proc/self/status` `TracerPid`, `ptrace`, `waitpid`, signal, or thread-name
  checks.
- `/proc/self/task/<tid>/status` scanning for thread `Name` values such as
  `gum-js-loop` or `gmain`.
- `/proc/self/fd/<fd>` readlink checks for injected-agent artifacts such as
  `linjector`.
- Process-state scans for `T (stopped)`, `t (tracing stop)`, or `(zombie)`,
  especially when ptrace/fork/child watchdogs are involved.
- `inotify_add_watch` on `/proc/self/mem` or related procfs paths to detect
  memory inspection.
- Parent/child watchdog designs using `fork`, `pipe`, read/write challenge
  bytes, and mutual process-state checks.
- `open`, `openat`, `read`, `fgets`, `strstr`, `strcmp`, `strcasestr`, and
  direct syscall variants that bypass libc-level hooks.
- Direct process termination through `exit`, `_exit`, `kill`, `tgkill`, or
  `svc`-issued `exit_group` rather than a normal Java exception.
- Return-address or caller-signature checks around environment-check functions.
  In observed Bangcle cases, the caller path may be expected to contain a
  hardcoded marker such as `__b_a_n_g_c_l_e__check_env`; jumping into the check
  function from an unnatural caller can trigger the kill path.

Crash/exit evidence to collect before patching:

```bash
adb logcat -c
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_watch_dex_loading.js --no-pause
adb logcat -d -v threadtime > analysis/frida_crash_logcat.txt
adb shell pidof com.example.app
adb shell cat /proc/<pid>/maps > analysis/maps_before_exit.txt
```

If a tombstone exists, normalize the crash PC/LR to `libDexHelper.so!offset`
using the maps base. If there is no tombstone and the process simply vanishes,
suspect `exit_group` or `kill` first.

IDA/Ghidra route for libDexHelper anti-Frida:

1. Copy the exact ABI library from the APK or installed app and record hash.
2. Inspect segments. A protected main segment plus a small executable loader
   segment is a shell-SO clue.
3. Search strings for `27042`, `frida`, `gum`, `gadget`, `/proc/self/maps`,
   `/proc/self/status`, `TracerPid`, `ptrace`, `exit_group`, `kill`, `tgkill`,
   `__b_a_n_g_c_l_e__check_env`, `mmap`, `mprotect`, and `svc`.
4. Follow xrefs from `/proc/self/maps` and Frida strings to the scanning
   routine.
5. Follow the scanning routine's failure edge to the termination routine. In
   arm64, direct `exit_group` may appear as `mov x8, #0x5e; svc #0`; in arm32
   and x86 variants, look for the equivalent raw syscall path.
6. Check whether the scan routine is protected by caller/return-address
   validation. Do not assume that forcing a branch to the middle of the check
   is safe; it may violate the expected caller signature and trigger the kill
   routine.
7. Record function offsets as file/image offsets and later convert to runtime
   addresses using the mapped module base.

Runtime bypass strategy should be layered:

1. Hygiene first:
   - use a non-default Frida server port,
   - when the app crashes merely because frida-server is running, test port
     detection before loading any agent script,
   - distinguish server detection from agent detection: server-only crash
     usually points to port/socket/process artifacts; crash only after `-l`
     points to maps/thread/agent artifacts,
   - rename server/gadget artifacts when in scope,
   - avoid loading obvious agent paths,
   - spawn early when the check runs during startup.
2. Hook common libc surfaces:
   - filter `connect` attempts to `27042`/Frida ports,
   - hide suspicious `/proc/self/maps` lines from `open/openat/read/fgets`,
   - make `strstr/strcasestr/strcmp` miss Frida markers,
   - neutralize `ptrace` checks where safe.
3. Hook termination surfaces:
   - log `exit`, `_exit`, `abort`, `kill`, `tgkill`, and `syscall`,
   - if termination uses direct `svc`, libc hooks may not see it.
4. Patch confirmed native offsets only after evidence:
   - use `Memory.patchCode()` to replace the scanner or kill routine prologue
     with a return instruction,
   - use architecture-aware bytes/writers,
   - patch after the target module is mapped and before the detection thread
     runs if possible,
   - keep offsets sample-specific in the task workspace, not in the skill.

### Server Detection Versus Agent Detection

When a Bangcle enterprise target fails before any script runs, split the test:

```bash
# server-only baseline
frida-ps -H 127.0.0.1:27042
adb shell monkey -p com.example.app 1

# non-default port baseline
frida-ps -H 127.0.0.1:6688
adb shell monkey -p com.example.app 1

# agent-loaded baseline
frida -H 127.0.0.1:6688 -f com.example.app -l analysis/minimal.js --no-pause
```

Interpretation:

- server-only crash at the default port: prioritize `connect`/socket/port
  checks and use a non-default server port for later experiments.
- non-default port works but `-l` crashes: prioritize `/proc/self/maps`,
  thread names, Frida agent strings, injected ranges, and detection threads.
- both fail: root/emulator/debugger checks, process artifacts, or early native
  checks may run before the agent can cleanly install hooks.

Record this as a matrix in the report; it prevents mixing root bypass, server
hygiene, and agent bypass into one noisy script.

### pthread_create And clone Thread-Start Triage

Bangcle detection often runs in native worker threads. A simple
`pthread_create` hook can reveal `start_routine`, but some protectors detect
or race against hooks on `pthread_create` itself. If `pthread_create` tracing
causes an immediate kill, move one layer lower:

1. Hook `clone()` and inspect the call stack. On Android/Bionic, a common flow
   is `pthread_create -> clone(__pthread_start, ..., pthread_internal_t, ...)`.
2. For arm64 Bionic layouts observed in practice, the real user
   `start_routine` can be recovered from the pthread control block at
   `clone args[3] + 0x60`. Verify this offset on the target Android version by
   comparing it with `pthread_create` output when safe.
3. Resolve the recovered start address to `module!offset`. For Bangcle, record
   every `libDexHelper.so!offset` thread start.
4. Patch only offsets with causal evidence:
   - first observe the thread starts,
   - then patch or replace one offset group,
   - compare crash/agent survival/app startup before and after.

Use the dedicated tracer for evidence collection:

```bash
frida -H 127.0.0.1:6688 -f com.example.app \
  -l android-native-auto-reverse/scripts/frida_thread_create_tracer.js --no-pause
```

Or use the Bangcle anti-Frida template and fill
`DETECTION_THREAD_OFFSETS` after the offsets are known:

```javascript
const DETECTION_THREAD_OFFSETS = [
  { offset: 0x54814, action: 'ret', reason: 'confirmed agent maps detector' },
];
```

Do not copy offsets between samples. Different versions may move thread
entries, split one detector into multiple workers, or intentionally crash when
only part of the worker set is patched.

### Root And Environment Surface

For enterprise shells, root detection may be independent from Frida detection.
Evidence-first order:

1. Baseline without Frida: if the app exits on a rooted device, root/environment
   checks are already active.
2. Record visible surfaces: Magisk/KernelSU packages, `su` paths, Zygisk/Riru/
   LSPosed packages, mount entries, `ro.debuggable`, `ro.secure`,
   `ro.build.tags`, `test-keys`, `getprop`, `which su`, `id`, and package
   manager queries.
3. Prefer device-side hiding only when the user explicitly wants environment
   cleanup. Otherwise, keep the device as-is and use targeted hooks so the
   bypass evidence stays tied to the app.
4. Separate root bypass scripts from Frida bypass scripts unless the crash
   evidence shows both checks happen in the same native routine.

Use the bundled template as a starting point:

```bash
cp android-native-auto-reverse/scripts/frida_bangcle_dexhelper_antifrida.js analysis/frida_bangcle_dexhelper_antifrida.target.js
# Edit TARGET_LIB, TARGET_OFFSETS, keywords, and behavior for the sample.
frida -U -f com.example.app -l analysis/frida_bangcle_dexhelper_antifrida.target.js --no-pause
```

Evidence that the bypass worked:

- The app remains stable past the previous crash point.
- Frida stays attached long enough to run loader/dex watches.
- `frida-dexdump` produces non-shell dex candidates.
- Log output shows filtered maps/port checks or patched function offsets.
- No new crash appears at the same `libDexHelper.so!offset`.

Do not report this as a generic permanent bypass. Report the exact sample ABI,
library hash, module base, patched offsets, command, device Android version,
Frida version, and the observed before/after behavior.

## Dump Repair And Business-Code Validation

After `frida-dexdump`, keep raw dumps immutable and write fixed copies to a
separate directory.

1. Validate raw dumps first:

```bash
python3 android-native-auto-reverse/scripts/dex_dump_validator.py dumps/com.example.app --out analysis/dex_dump_validation_raw.json
```

2. Repair only files that are otherwise useful but fail checksum/header loading:

```bash
mkdir -p dumps/com.example.app_fixed
for f in dumps/com.example.app/*.dex; do
  python3 android-native-auto-reverse/scripts/dex_header_fix.py "$f" -o "dumps/com.example.app_fixed/$(basename "$f")"
done
python3 android-native-auto-reverse/scripts/dex_dump_validator.py dumps/com.example.app_fixed --out analysis/dex_dump_validation_fixed.json
```

3. Prove the dump is not just shell code:

```bash
jadx --no-debug-info --show-bad-code dumps/com.example.app_fixed -d analysis/dumped_jadx
python3 android-native-auto-reverse/scripts/jadx_triage.py analysis/dumped_jadx > analysis/dumped_jadx_triage.txt
```

4. Validate with app-specific anchors from the manifest and UI:
   - real `Application` or Activity classes, such as a WebView or launcher
     activity named in `AndroidManifest.xml`,
   - target package business namespaces,
   - request builders, WebView URLs, signature/crypto methods, or native method
     declarations,
   - non-empty method bodies where the visible shell dex had stubs.

Report the class or package names used for validation. Do not call the dump
complete if JADX only shows wrapper/stub code or method bodies remain empty.

## Multi-SO Enterprise Protector Pattern

Some enterprise protectors do not rely on one shell library. Expect a chain such
as:

```text
early loader so -> main loader so -> emulator/risk/root/trust/device so -> app
```

Practical implications:

- Build a native load timeline with `dlopen`/`android_dlopen_ext`, constructor,
  `JNI_OnLoad`, and process/PID evidence before deciding what to patch.
- Treat every later-loaded protection library as a new detection surface. Passing
  the first loader only proves that stage, not the whole app.
- Cover named child processes or remote service processes. A main-process patch
  can be correct while `:remote`, push, or risk-control processes still die.
- Use a full agent for the main process and a lightweight child/process agent for
  repeated loader patches. Avoid loading expensive global hooks into every
  process unless needed.

## Anonymous RX And Constructor-Gated Patching

When a protector releases executable anonymous code, the disk `.so` can be a
wrapper only. Static IDA/Ghidra on the APK library may miss the real checks.

Use this route:

1. Watch the loader constructor and map transitions.
2. Dump executable ranges before and after constructor/JNI milestones.
3. Rebuild only enough ELF wrapper metadata to load the dump in IDA/Ghidra.
4. Analyze the runtime dump, not only the disk file.
5. Patch at constructor leave or immediately after the anonymous RX range appears.

Prefer constructor-gated patch timing over blind polling when startup races are
tight. Polling can work for slow checks, but constructor hooks explain exactly
which load stage created the executable code.

## Direct Syscall Evidence

Many protectors bypass libc hooks with inline `svc #0`. If libc `kill`,
`tgkill`, `exit`, or `syscall` hooks do not fire but the process vanishes,
collect syscall-level evidence or scan runtime code for `svc` instructions.

Arm64 notes:

- `scfilter` or syscall tracing PCs often point to the instruction after the
  syscall. Inspect `pc - 4` for the real `svc #0`.
- Common fatal numbers: `kill=62`, `exit=93`, `exit_group=94`,
  `tgkill=129`, `tkill=130`. Also track `openat=56`, `read=63`,
  `faccessat=48/modern variants`, `getpid=172`, and timing syscalls.
- Patch the syscall site only after proving the syscall number and failure edge.
  A stable runtime patch often changes the fatal `svc` to a benign return value
  or forces the dispatcher to select the safe branch.

Do not assume every `svc` is malicious. Loaders legitimately use `openat`,
`mmap`, `read`, `clone`, and property/file syscalls. Patch only fatal or
causally confirmed checks.

## Dispatcher And Flattening Pitfalls

Do not patch a block just because it appears at a crash-adjacent offset. In
OLLVM or flattened code, a block may only select the next state. Patching such a
block to `ret` can skip necessary initialization and create splash-screen hangs.

Before patching:

- Determine whether the address is a function entry, a state dispatcher, a
  helper, or the actual fatal edge.
- Identify the state variable, comparison value, and safe/fatal indices.
- Prefer changing a conditional select/branch to the safe index over returning
  from the middle of a dispatcher.
- Validate with before/after evidence: same input, same device state, previous
  crash point passed, no new ANR or missing initialization.

## Stable Runtime Patch Shape

For multi-stage protected apps, a stable Frida runtime bypass usually has these
layers:

- pre-script: generic Frida keyword, maps, port, path, root, property, and
  package hiding;
- main-process stage script: constructor-gated loader patch, anonymous RX dump
  and patch, dispatch safe-branch patches, fatal syscall/BRK patches;
- child-process light script: only repeated early loader patches needed by
  secondary processes;
- continued `dlopen` monitoring: later risk/trust/emulator/root libraries get
  their own narrow patches;
- low-noise verification: 120-180 seconds with no SIGSEGV, no fatal Java
  exception, no ANR, and per-library `patched=x/y ok=true` style status logs.

## clone And Detection-Thread Tracing

Use this when `android_dlopen_ext` shows a crash around an SDK/protector library
but simple `pthread_create` logging does not reveal the real detection thread,
or when `pthread_create` only shows libc wrapper addresses.

Why this matters:

- On Android, `pthread_create()` eventually reaches `clone()`.
- The visible `pthread_create` start routine may be an internal wrapper such as
  `__pthread_start`, not the user's real detection routine.
- On common arm64 Bionic layouts, the user-supplied thread function is stored in
  the pthread start argument block. In observed Android 8 style layouts, reading
  `clone` argument 3 plus `0x60` (`args[3].add(96).readPointer()` in Frida)
  recovers the actual `start_routine`.
- That recovered pointer can be normalized to `module!offset`, making it
  possible to identify anti-Frida worker threads in `libDexHelper.so`, OAID
  SDKs such as `libmsaoaidsec.so`, or other native environment-check libraries.

Triage order:

1. Hook `android_dlopen_ext` and log every loaded library. Mark the last
   libraries loaded before the crash or disconnect.
2. Hook `pthread_create` first. Log `args[2]`, module name, and offset when the
   pointer belongs to a real app/protector library.
3. If `pthread_create` does not expose useful module offsets, hook `clone`.
   For each `clone` call:
   - log `args[0]` and its module if valid,
   - when `args[3]` is non-null, try reading `args[3] + 0x60` as the real
     thread start routine,
   - convert that pointer to `module!offset`,
   - capture a short native backtrace.
4. Exercise the startup or feature path until the crash/detection reproduces.
5. Build a candidate list by module and repeated offsets. Detection candidates
   often appear repeatedly before the crash, especially from shell/protector
   libraries or device-ID/OAID/security SDKs.
6. Patch conservatively:
   - prefer replacing only confirmed detection-thread entry functions with
     `RET`,
   - patch after the owning module is loaded and before or at thread creation,
   - keep offsets sample-specific in the task workspace,
   - validate that the app proceeds farther than the previous crash point.

Observed pattern from the attached McDonald's-style case:

- `libDexHelper.so` was loaded before the visible failure.
- `pthread_create` alone did not reveal useful `libDexHelper.so` routines.
- `clone` tracing recovered repeated real thread functions by reading the
  pthread argument block.
- Several `libDexHelper.so` thread function offsets were patched to `RET`.
- A later crash point was attributed to `libmsaoaidsec.so`; its thread-start
  offsets were then patched similarly.

This pattern is reusable, but the exact offsets are not. Always rediscover
offsets for the current APK, ABI, Android version, and library build.

Use the bundled template:

```bash
cp android-native-auto-reverse/scripts/frida_thread_create_tracer.js analysis/frida_thread_create_tracer.target.js
# Edit PATCH_TARGETS only after the trace shows module!offset candidates.
frida -U -f com.example.app -l analysis/frida_thread_create_tracer.target.js
```

For arm64 RET patching, use module image offsets:

```javascript
Memory.patchCode(base.add(0xOFFSET), 4, function (code) {
  const writer = new Arm64Writer(code, { pc: base.add(0xOFFSET) });
  writer.putRet();
  writer.flush();
});
```

Completion evidence:

- before/after crash point or launch stage,
- list of detection-thread candidates as `module!offset`,
- patch list with module hash and ABI,
- Frida log showing `clone`/`pthread_create` traces and patch timing,
- logcat/tombstone proving the old crash disappeared or moved to a new module.

## Dump Validation

Do not claim unpacking succeeded because files were dumped. Validate them:

```bash
python3 android-native-auto-reverse/scripts/dex_dump_validator.py dumps/com.example.app --out analysis/dex_dump_validation.json
jadx --no-debug-info --show-bad-code dumps/com.example.app/classes.dex -d dumped_jadx
python3 android-native-auto-reverse/scripts/jadx_triage.py dumped_jadx > dumped_jadx_triage.txt
```

A useful dump should have:

- valid dex magic and plausible header size
- non-trivial file size and string count
- real package/business classes, not only shell/stub classes
- request, signature, crypto, UI, service, or native bridge logic tied to the
  target app
- better JADX output than the original APK

If multiple dex files appear, rank by size, strings, package names, native
method declarations, request/signature anchors, and app-specific class names.

If a dumped dex has a bad file size, signature, checksum, or magic but contains
plausible dex data, preserve the raw file and create a minimal fixed copy:

```bash
python3 android-native-auto-reverse/scripts/dex_header_fix.py raw.dex -o fixed.dex
python3 android-native-auto-reverse/scripts/dex_dump_validator.py fixed.dex
```

This repair is intentionally conservative. It updates header fields needed by
many tools; it does not reconstruct missing code items or solve method
extraction.

## Failure Modes

- Only shell dex dumped: use deeper search, longer `--sleep`, attach after
  interacting with the app, or hook class-loader events to identify timing.
- Frida attach disconnects: collect logcat/tombstone first; the shell may kill
  the process on instrumentation detection.
- Real code is method-extracted: dex dump may restore class structure but still
  show native-backed or empty methods; pivot to `libDexHelper.so` and
  RegisterNatives/native offset analysis.
- Payload is memory-only or transient: combine class-loader logging with maps,
  `mmap`/`mprotect`, and early-window dumps.

## Report Notes

Include shell rule hits, `libDexHelper.so` path and hash, frida-dexdump command,
sleep/attach strategy, dump output directory, validation JSON, JADX validation
result, outer/inner SO paths if a shell SO was decrypted, and the first
restored business class or call chain.
