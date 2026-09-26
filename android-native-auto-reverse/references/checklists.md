# Android Native Reverse Checklists

## New APK Triage

- Record APK path, SHA-256, package name, version, min/target SDK, ABI folders, signing status, and packer/protector clues.
- Run `apkid` when available and compare with `scan_apk_shell.py`; treat both as triage signals that need confirmation from APK structure or runtime loader behavior.
- Inspect manifest for entry activity, services, receivers, debuggable state, network security config, exported components, and custom Application.
- List native libraries by ABI and size. Prioritize unusually large, stripped, encrypted, or loader-like libraries.
- Search Java/Kotlin for `System.loadLibrary`, `System.load`, native declarations, `RegisterNatives` wrappers, class loader tricks, anti-debug APIs, TLS pinning, proxy/VPN checks, and request signing paths.
- Search native strings for `/proc`, `maps`, `frida`, `gum-js-loop`, `xposed`, `magisk`, `su`, `test-keys`, `ro.debuggable`, `ro.secure`, `qemu`, `TracerPid`, `ptrace`, `kill`, `tgkill`, and suspicious domains.
- Run `scripts/scan_apk_shell.py` when an APK is present. Review both built-in heuristic hits and `apkpackdata.json` rule hits. If visible Java is small or stub-like, pivot to unpacking and loader analysis instead of exhausting jadx output.

## Packer And Shell Triage

- Strong shell clues: `com.stub.StubApp`, `libjiagu.so`, `libshell*.so`, `libDexHelper.so`, `libDexHelper-x86.so`, `libdatajar.so`, `libdexjni.so`, `libSecShell.so`, `libdexprotector.so`, Bangcle, Ijiami, Qihoo/360, Tencent Legu, Alibaba, SecNeo, encrypted assets such as `resthird.data`, tiny `classes.dex`, or large loader libraries.
- Rule-database clues: `scan_apk_shell.py` reports `rule_hits` from `references/apkpackdata.json`; record the family name, match type, pattern, and matched APK path.
- Runtime-loader clues: custom `Application`, `attachBaseContext`, `DexClassLoader`, `PathClassLoader`, `InMemoryDexClassLoader`, `loadDex`, `openDexFile`, asset extraction, and late `dlopen`.
- Protection category: whole-dex shell, file-backed loading, memory-backed loading, function extraction, VMP/dex2c, string/resource encryption, or native/ELF packing. Let this category choose the next dump path.
- Treat `apktool` output that contains only shell code as a signal, not a dead end. Move to loader `.so`, runtime dex dump, RegisterNatives logs, and maps/dlopen evidence.
- Preserve original APK, unpacked stub tree, dumped dex, dumped `.so`, maps snapshot, and commands in one experiment folder.

## Native Library Static Checklist

- If more than one app library exists, generate `so_inventory.json` and
  `so_target_candidates.json` before deep manual analysis.
- Select the first IDA/Ghidra target by evidence: Java load sites, JNI hints,
  crypto/signing hints, anti-analysis hints, loader/memory hints, crash offsets,
  RegisterNatives logs, and app-specific names.
- ELF headers: class, endianness, machine, PIE, stripped state, section/program headers.
- Load-time code: `.init_array`, constructors, `JNI_OnLoad`, imported `dlopen`, `android_dlopen_ext`, `pthread_create`, and `prctl`.
- JNI surface: exports, dynamic registration arrays, native method strings, Java signatures, and offsets.
- ART/VMP surface: `OpenMemory`, `OpenDexFilesFromOat`, `DexFileVerifier`,
  `makeDexElements`, `libdexjni`, `JniLib`, type-specific native methods
  (`cV/cI/cL/...`), opcode handlers, and JNI side-effect calls.
- Syscall surface: inline `svc #0`, syscall numbers, wrappers around `openat`, `readlinkat`, `newfstatat`, `statx`, `ptrace`, `kill`, `tgkill`, `exit_group`, `mmap`, `mprotect`, and `memfd_create`.
- Integrity surface: `.text` hashing, CRC tables, page permission flips, self-read of `/proc/self/maps` or library path, linker/libc/libart address checks.
- Anti-instrumentation surface: thread names, port scans, Frida pipe/socket checks, memory map name checks, breakpoint/trap logic, timing checks, and suspicious signal handlers.

## Runtime Evidence Checklist

- Device: Android version, ABI, root state, SELinux state, Frida/server version, target UID, package version, and whether a custom ROM/system capability is in use.
- Process: spawn or attach, PID changes, zygote/app process split, loaded maps, target library base address, and thread names.
- Logs: logcat around startup, tombstone if crash, dmesg/kernel trace if available, Frida console output, and any syscall/eBPF/KPM logs.
- Loader events: `dlopen`, `android_dlopen_ext`, constructors, `JNI_OnLoad`, and `RegisterNatives` hits with base + offset.
- Multi-process events: package main process, named service processes,
  provider/push/risk-control processes, parent/child PID changes, and which
  agent or patch set each process received.
- Path checks: file/path, property, command, `/proc`, `maps`, `fd`, mount, package manager, and system setting probes.
- Frida split test: record server-only behavior, non-default-port behavior,
  and agent-loaded behavior separately. A default-port crash is not the same
  evidence as an agent maps/thread detection.
- Thread detection: if `pthread_create` tracing changes behavior, fall back to
  `clone` and recover the Bionic pthread start routine from the thread-control
  structure when applicable. Record `module!offset`, parent PID, and whether
  the thread was observed, replaced, or patched.
- Root/environment checks: record root state, Magisk/KernelSU/Zygisk/LSPosed
  package visibility, `su` path probes, property reads, mount reads, and command
  execution probes. Keep root-bypass and Frida-bypass experiments separate until
  evidence shows a shared routine.
- Exit/crash checks: signal, sender PID/TID, PC/LR, `so!offset`, thread, last path/memory syscall, and whether exit happens before Java code runs.
- Memory execution: anonymous RX/RWX mappings, memfd names, VMA names, permission transitions, self-decrypted ranges, and dump windows.

## Request And Traffic Checklist

- Static request map: URLs, hosts, Retrofit annotations, OkHttp/Volley/HttpURLConnection/WebView anchors, headers, params, signing methods, and native handoff points.
- Burp state: proxy host/port, CA install location, Android version, target trust model, QUIC/HTTP3 risk, capture window, and exported HTTP items.
- r0capture state: script path/version, spawn or attach mode, package/PID, capture command, hook errors, and plaintext request/response snippets.
- Frida/objection hooks: request builders, interceptors, headers, body writers, crypto/signing methods, WebView loads, TLS pinning classes, and JNI methods.
- Correlation: endpoint -> static file/line -> runtime capture -> params/headers -> signing source -> native offset or Java method -> confidence label.
- Redaction: tokens, cookies, passwords, account IDs, device IDs, and personal data should be masked in reports unless explicitly needed for authorized debugging.

## Crash Or Exit Investigation

1. Clear logs and reproduce once without hooks.
2. Capture logcat, tombstone, and process lifetime.
3. If the app exits before usable Java/Frida hooks, collect syscall or kernel-level evidence where available.
4. Resolve PC/LR and caller offsets against `/proc/<pid>/maps` and library load bias.
5. Identify whether the trigger is a signal, direct `exit_group`, watcher thread, constructor failure, JNI exception, or deliberate crash instruction.
6. If syscall evidence reports a PC, verify whether the real `svc` is at
   `pc - 4`; record the syscall number and the branch/state that selected it.
7. Check whether the crash-adjacent address is a function entry, dispatcher
   block, fatal helper, or mixed initialization/check routine. Do not patch a
   flattened dispatcher to `ret` until this is known.
8. Only then design a narrow hook or patch.

## Dump/Fix Checklist

- Confirm target library base, size, path, and whether it is file-backed, anonymous, or memfd-backed.
- Choose stable dump for long-lived mappings, early-window dump for constructor/JNI/dlopen windows.
- Preserve original file, dumped file, maps snapshot, dump command, and load address.
- Validate ELF loadability, segment alignment, dynamic table, relocations where possible, and IDA/Ghidra base.
- If symbols/sections are missing, recover enough function boundaries and strings to answer the task before over-fixing.

## Dex Unpacking Checklist

- Identify when the real dex appears: after `attachBaseContext`, after shell `Application.onCreate`, after login screen, after plugin extraction, or after native loader initialization.
- Capture class loader type, parent chain, `DexPathList.dexElements`, `DexFile.mCookie` or `mInternalCookie`, dex path or memory-backed source, dumped file name, size, SHA-256, and class count.
- For memory-backed dex, watch `InMemoryDexClassLoader`, `DexFile(ByteBuffer[])`, `openInMemoryDexFilesNative`, `OpenDexFilesFromOat`, `DexFileLoader::OpenCommon`, or `DexFile::DexFile`.
- For shells that hook ART, watch `DexFileVerifier::Verify`,
  `ClassLinker::OpenDexFilesFromOat`, and `DexFile::OpenMemory`; placeholder
  `.cache/classes*.dex` files with only dex magic are evidence of memory-backed
  loading, not successful file extraction.
- For VMP/libdexjni, recover `RegisterNatives`, identify the native bridge
  method, record `vmpId`/codeItem pointers, and build an opcode-handler map
  from JNI side effects.
- For function extraction, distinguish delayed whole-dex dump from active restoration/FART/youpk-style method-code capture.
- Validate dump with jadx, package/class names, strings, native declarations, and business entry points.
- If multiple dex files are produced, rank them by class count, target package names, request/signing code, and native bridge references.
- Do not claim unpacking succeeded until dumped dex contains non-stub app logic, or extracted methods have restored non-empty code items, and the result can be tied back to the target package/version.

## Loaded .so Dump/Fix Checklist

- Snapshot `/proc/<pid>/maps` and identify all mappings for the target library, including split RX/RW segments and anonymous/memfd executable ranges.
- Dump from mapped memory with base and size from maps, not from guessed file size.
- For self-decrypting libraries, hook or monitor `dlopen`, `android_dlopen_ext`, constructors, constructor leave, `JNI_OnLoad`, `mprotect`, and first export/native-method call.
- For linker-unlinked or anonymous libraries, use executable range, build-id/string anchors, memfd name, VMA name, or RegisterNatives offset to choose the dump range.
- After dump, check ELF magic, program headers, `readelf -l`, strings, imported names, and whether IDA/Ghidra can load at the runtime base.
- If the dump lacks section headers, continue with program headers and load segments; section restoration is optional unless it blocks the task.

## Runtime Patch Stability Checklist

- Prefer exact byte/offset patches over broad high-frequency libc hooks once the
  detection path is known.
- Patch at the right load stage: constructor leave, after anonymous RX creation,
  before detection threads, or before the next protection library loads.
- Keep heavy trace and stable bypass separate. Heavy trace can use broad hooks;
  the stable script should be narrow and low-noise.
- For multi-process apps, define main and child/light patch scripts separately.
  Child processes should receive only the early loader patches they need.
- Verify with a timed run long enough to cover delayed checks, usually 120-180
  seconds for startup/native-protection work.
- Status logs should be per library or stage, for example
  `libname-patch-status patched=6/6 ok=true`.
- Passing the splash screen is not enough: check no repeated PID churn, no
  uninstrumented child crash, no ANR, no fatal Java exception, and no native
  tombstone at the old offset.

## OLLVM And Control-Flow Checklist

- Confirm function boundaries before deobfuscation.
- Identify dispatcher block, state variable, indirect branch, bogus branches, and real exit blocks.
- Avoid trusting pseudocode until branch targets and side effects are checked in disassembly.
- Re-export or reanalyze after deobfuscation and compare with runtime offsets.

## Evidence Confidence Labels

- `static-candidate`: plausible from code or strings only.
- `runtime-hit`: observed with log/hook/syscall/tombstone evidence.
- `causal`: before/after experiment shows it affects the symptom.
- `bypass-verified`: a narrow change makes the target pass a defined success condition.
- `disproven`: tested and did not affect the symptom.

## Structured SO Outputs

- `so_inventory.json`: native libraries, ABI, size, SHA-256, ELF identity, hint counts, and notable strings.
- `so_target_candidates.json`: ranked libraries with score reasons and high-value strings.
- `selected_so_target.json`: current top target plus a reminder to verify against Java/runtime evidence.
- `jni_map.json`: Java class and method to native function or offset, preferably confirmed by RegisterNatives logs.
- `so_static_triage.json`: readelf/objdump/nm/IDA/Ghidra summaries for the chosen target.
- `so_analysis_report.md`: final evidence chain and next experiments.

## Safety Boundaries

- Do not perform live bypass, patching, TLS capture, or device manipulation without clear authorization.
- Do not provide data exfiltration, persistence, malware deployment, or third-party account access workflows.
- When reporting bypass concepts, keep them tied to authorized testing and reproducible evidence.
