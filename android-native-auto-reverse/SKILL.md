---
name: android-native-auto-reverse
description: "Unified Android mobile reverse-engineering skill for authorized APK/AAB/XAPK/DEX/JAR/AAR/ELF .so work. Use for static analysis with JADX/apktool/resources, shell/packer recognition with APKiD and apkpackdata rules, Frida/objection runtime Hook, frida-dexdump/BlackDex/FART/youpk dex unpacking, Bangcle/libDexHelper anti-Frida, server-only versus agent-loaded detection triage, clone/pthread detection-thread tracing, Bionic pthread start-routine recovery, and exit_group bypass triage, ART DexFile/mCookie/ClassLoader unpacking strategy, loaded .so dump and repair, Burp Suite/r0capture/request traffic analysis, Frida-to-Python-to-Burp plaintext crypto bridge, OkHttp/Retrofit/WebView/mPaaS RpcInvoker/JsonSerializerV2/API/signature tracing, JADX and IDA/Ghidra Java-native correlation, SO/JNI/RegisterNatives analysis, native crypto/signing, anti-debug/anti-Frida/root/emulator/VPN/proxy checks, and concise evidence reports."
---

# Android Native Auto Reverse

This is the single Android reverse-engineering entrypoint. Use it instead of older split Android reverse skills. It covers the full workflow from APK triage to traffic/code/native correlation and report delivery.

Use only for authorized analysis. If a task implies bypassing protections, live tracing, TLS interception, patching, or dumping code and the authorization is unclear, stop and ask for scope confirmation before invasive runtime work.

## Operating Rules

- Prefer evidence over guesses: APK paths, decompiled output, strings, manifests, resources, `.so` metadata, logs, maps, Frida output, Burp/r0capture traffic, IDA/Ghidra exports, and request samples.
- Start static unless the user explicitly asks for runtime work or the question cannot be answered statically.
- Keep app-specific findings out of the skill. Reports, Hook scripts, dumps, JADX output, and sample-specific notes belong in the task workspace, never inside this skill directory.
- Separate shell code from real business code. If visible Java is stub-only or loader-heavy, pivot to unpacking before summarizing business logic.
- Treat runtime hooks and patches as experiments. Record command, device state, package/PID, ABI, timestamp, observed output, and conclusion.
- For request tasks, align three sources when possible: traffic evidence, Java/Kotlin construction path, and native/signing implementation.
- For native tasks, keep offsets disciplined: distinguish file offset, image offset, runtime address, load base, IDA/Ghidra address, and `so!offset`.

## Unified Workflow

1. Scope and inventory.
   - Identify package, version, ABI, launcher, target SDK, signing state, permissions, exported components, assets, native libraries, and user goal.
   - Run shell recognition first for APK/XAPK targets with `scripts/scan_apk_shell.py`; use APKiD when available and compare both.
   - Read `references/checklists.md` for new APK/.so analysis, crash/exit investigation, dump/fix work, or final reporting.

2. Static analysis with apktool and JADX.
   - Use apktool for manifest, resources, assets, smali, network security config, native files, and package structure.
   - Use JADX for Java/Kotlin call chains, request builders, crypto/signing wrappers, native method declarations, WebView bridges, and app logic.
   - If JADX is missing or incomplete, continue with apktool/smali/strings/native anchors and say what fallback was used.
   - Read `references/jadx-and-ida.md` before a Java/native correlation pass or when using JADX with IDA/Ghidra.
   - Run `scripts/jadx_triage.py` on JADX output to summarize native loading, shell clues, TLS/pinning, class loaders, and request/signature anchors.

3. Shell, unpacking, and dump decisions.
   - Treat these as strong shell clues: `com.stub.StubApp`, tiny or stub-only dex, encrypted assets, custom class loaders, late dex loads, `libjiagu.so`, `libshell*.so`, `libDexHelper.so`, `libSecShell.so`, `libsecexe.so`, `libsecmain.so`, `libdexprotector.so`, `libtup.so`, `libexec.so`.
   - Classify protection type when evidence allows: whole-dex shell, function extraction, VMP/dex2c, string/resource encryption, or native/ELF packing. The category decides whether to dump dex, force method execution, or dump/fix `.so`.
   - If packed, identify shell family, loader library, payload timing, class loader, and dump target before business analysis.
   - Read `references/unpacking-and-so-dump.md` for generic dex/.so dump and repair, ART `DexFile`/`mCookie`, `ClassLoader`, BlackDex/FART/youpk, whole-dex and function-extraction strategies.
   - Read `references/bangcle-dexhelper-frida-dexdump.md` for 梆梆/Bangcle/libDexHelper/frida-dexdump workflows, including Frida server-only versus agent-loaded crash triage, `/proc/self/maps` filtering, `pthread_create`/`clone` detection-thread tracing, Bionic pthread start-routine recovery, direct `svc exit_group`, and offset-based patch triage.
   - Validate dumped dex with `scripts/dex_dump_validator.py`; repair only copied raw dex with `scripts/dex_header_fix.py`.

4. Request, API, and traffic analysis.
   - Extract URLs, hosts, Retrofit annotations, OkHttp/Volley/custom builders, WebView loads, mPaaS RPC anchors, headers, params, body writers, signing methods, and native handoffs.
   - Run `scripts/request_endpoint_extractor.py` on JADX, apktool, dumped source trees, Burp exports, r0capture logs, or curated text logs.
   - Use Burp Suite when the app trusts the proxy CA or can be made to trust it in scope.
   - Use r0capture when pinning, native TLS, custom trust, or binary protocols hide plaintext from Burp.
   - Use Frida/objection for call-chain proof: request builders, interceptors, headers, body writers, crypto/signing methods, WebView loads, mPaaS `Serializer.packet`/`RpcInvoker`/`HttpCaller` boundaries, TLS checks, and JNI methods.
   - When Burp sees encrypted traffic but Frida can see plaintext at a crypto/request boundary, use the Frida-to-Python-to-Burp bridge pattern: Frida sends plaintext with a correlation ID, Python forwards it through Burp for editing, then posts the edited body back to Frida before encryption or after decryption.
   - Read `references/request-traffic-analysis.md` for capture setup, evidence standards, Hook strategy, and traffic-to-code correlation.

5. SO/JNI/native analysis.
   - Build a native inventory before deep manual work. Run `scripts/so_inventory.py`, then `scripts/native_target_ranker.py`.
   - Prioritize libraries by Java load sites, JNI exports, `JNI_OnLoad`, `RegisterNatives`, crypto/signing strings, loader behavior, anti-analysis strings, crash offsets, and runtime hits.
   - Track constructor/init_array -> loader -> JNI registration -> Java call site -> native implementation -> helper calls -> observable behavior.
   - For protected or self-decrypting libraries, use `scripts/elf_init_array_finder.py` and runtime maps/dlopen evidence before opening every function manually.
   - Read `references/so-analysis-workflow.md` for SO ranking, JNI mapping, anti-analysis categories, crypto targets, and native report shape.

6. Runtime evidence and experiments.
   - Use `adb logcat`, tombstones, `/proc/<pid>/maps`, Frida, objection, Burp, r0capture, linker hooks, RegisterNatives hooks, syscall tracing, or IDA/Ghidra exports based on the symptom.
   - For crash/exit: prioritize `exit`, `exit_group`, `kill`, `tgkill`, `SIGABRT`, `SIGSEGV`, `SIGTRAP`, PC/LR, thread name, and caller library offset.
   - For loader/self-modifying behavior: watch constructors, constructor leave, `mmap`, `mprotect`, `pkey_mprotect`, `memfd_create`, `android_dlopen_ext`, `dlopen`, class loaders, and maps transitions to RX/RWX.
   - For multi-SO protectors, build a staged load chain across main and child/service processes; keep heavy trace separate from final low-noise patch scripts.
   - For direct syscall exits, remember syscall-trace PCs can point after `svc`; inspect `pc - 4`, then patch only causal fatal `svc` or safe-dispatch edges.
   - Use `scripts/frida_watch_dex_loading.js` for dex and library load timing.
   - Use `scripts/frida_dump_so.js` as a starting template for authorized loaded-library dumps.
   - Use `scripts/collect_key_evidence.py` when logs are large or evidence is scattered.

7. Deepen with IDA/Ghidra.
   - Rebase with runtime base addresses when correlating Frida/log offsets.
   - Start from ranked SO targets, RegisterNatives offsets, crash offsets, high-value strings, and Java native declarations.
   - Confirm function boundaries before trusting pseudocode in obfuscated or OLLVM-heavy code.
   - Run `scripts/ida_export_native_summary.py` inside IDA when a JSON evidence export is useful.
   - Use Ghidra similarly when IDA is unavailable; record which tool produced each finding.

8. Report.
   - Produce a chain of evidence, not a list of guesses.
   - Include artifact paths, commands, offsets, logs, runtime observations, unresolved questions, and the next concrete experiment.
   - Keep sample-specific Hook scripts, dump outputs, reports, JADX trees, and traffic exports in the workspace output directory, not in the skill.

## Resource Routing

- `references/checklists.md`: start of APK/.so analysis, crash/exit, dump/fix, report QA.
- `references/unpacking-and-so-dump.md`: packed APK, dex dump, ART DexFile/mCookie/ClassLoader strategy, BlackDex/FART/youpk/frida-dexdump, loaded `.so` dump/fix.
- `references/bangcle-dexhelper-frida-dexdump.md`: 梆梆/Bangcle/libDexHelper/libSecShell/libsecexe/libsecmain cases.
- `references/request-traffic-analysis.md`: 请求分析, 接口分析, 抓包, Burp Suite, r0capture, objection, Frida Hook, TLS, signing params.
- `references/jadx-and-ida.md`: JADX/IDA/Ghidra usage, Java-native bridge mapping, offset discipline.
- `references/so-analysis-workflow.md`: SO/JNI/native crypto/anti-analysis workflow and target ranking.
- `references/apkpackdata.json`: shell rule database used by `scripts/scan_apk_shell.py`; do not edit for one sample unless the user explicitly asks to update shell rules.

## Bundled Scripts

- `scripts/scan_apk_shell.py`: APK shell/packer clues using built-in heuristics and `apkpackdata.json`.
- `scripts/jadx_triage.py`: JADX output triage for native loading, class loaders, TLS/pinning, request/sign anchors.
- `scripts/request_endpoint_extractor.py`: URLs, hosts, API anchors, headers, signing/crypto anchors from source or traffic logs.
- `scripts/so_inventory.py`: ELF identity and native hint inventory.
- `scripts/native_target_ranker.py`: rank high-value `.so` targets.
- `scripts/dex_dump_validator.py`: rank and validate dex dump outputs.
- `scripts/dex_header_fix.py`: minimal copied-dex header repair.
- `scripts/elf_init_array_finder.py`: protected `.so` init-array target discovery.
- `scripts/bangcle_dexhelper_inner_decrypt.py`: parameterized Bangcle/libDexHelper outer-shell to inner-ELF reconstruction helper for RC4-like-header plus XOR-body samples.
- `scripts/frida_watch_dex_loading.js`: log dex/class-loader/library loading.
- `scripts/frida_art_openmemory_watch.js`: hook ART OpenMemory/OpenDexFilesFromOat/DexFileVerifier candidates and heuristically dump in-memory dex buffers.
- `scripts/frida_stalker_ollvm_trace.js`: Frida Stalker template for OLLVM/control-flow-flattened native algorithm recovery with call summaries, call/ret traces, argument dumps, and IDA offset correlation.
- `scripts/stalker_log_summarizer.py`: parse Stalker logs into JSON offset evidence for IDA/Ghidra/MCP correlation.
- `scripts/frida_dump_so.js`: template for authorized loaded `.so` dumps.
- `scripts/frida_bangcle_dexhelper_antifrida.js`: template for authorized Bangcle/libDexHelper anti-Frida triage and offset-based patch experiments.
- `scripts/frida_thread_create_tracer.js`: template for authorized pthread/clone thread-start tracing and module-offset RET patch experiments.
- `scripts/frida_mpaas_rpc_probe.js`: observe-only mPaaS RPC probe for `JsonSerializerV2`/`SignJsonSerializer`/`PBSerializer` packet boundaries, `RpcInvoker`, and `HttpCaller` request/response correlation.
- `scripts/frida_crypto_bridge_template.js`: generic Frida helper template for routing plaintext request/response hook points through the Python/Burp bridge.
- `scripts/frida_burp_crypto_bridge.py`: generic Python controller that loads a Frida script, forwards hook messages through Burp, and posts edited bodies back to Frida.
- `scripts/ida_export_native_summary.py`: IDA JSON export of functions/imports/exports/strings/xrefs.
- `scripts/collect_key_evidence.py`: extract useful evidence from large logs.

## Useful Commands

Use local equivalents when tool names differ.

```bash
aapt dump badging target.apk
apktool d -f target.apk -o apktool_out
jadx --no-debug-info --show-bad-code target.apk -d jadx_out
apkid target.apk
python3 android-native-auto-reverse/scripts/scan_apk_shell.py target.apk --json
python3 android-native-auto-reverse/scripts/jadx_triage.py jadx_out
python3 android-native-auto-reverse/scripts/request_endpoint_extractor.py jadx_out apktool_out --out analysis/static_endpoints.json
python3 android-native-auto-reverse/scripts/so_inventory.py apktool_out --out analysis/so_inventory.json
python3 android-native-auto-reverse/scripts/native_target_ranker.py --so-inventory analysis/so_inventory.json --out-dir analysis/native_rank
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_watch_dex_loading.js --no-pause
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_art_openmemory_watch.js --no-pause
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_stalker_ollvm_trace.js --no-pause
python3 android-native-auto-reverse/scripts/stalker_log_summarizer.py analysis/frida_stalker.log --out analysis/stalker_summary.json
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_bangcle_dexhelper_antifrida.js --no-pause
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_thread_create_tracer.js --no-pause
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_mpaas_rpc_probe.js --no-pause
python3 android-native-auto-reverse/scripts/frida_burp_crypto_bridge.py --spawn com.example.app --script analysis/hooks/request_crypto_bridge.js --burp-port 8080
frida-dexdump -U -f com.example.app -o dumps/com.example.app --sleep 8
frida-dexdump -U -n com.example.app -o dumps/com.example.app -d --sleep 5
objection -g com.example.app explore
adb shell settings put global http_proxy 192.168.1.10:8080
adb shell settings put global http_proxy :0
python3 r0capture.py -U -f com.example.app -v -p analysis/capture.pcap
python3 android-native-auto-reverse/scripts/dex_dump_validator.py dumps/com.example.app --out analysis/dex_dump_validation.json
python3 android-native-auto-reverse/scripts/elf_init_array_finder.py libtarget.so --out analysis/libtarget_init_array.json
python3 android-native-auto-reverse/scripts/bangcle_dexhelper_inner_decrypt.py libDexHelper.so -o analysis/libDexHelper_inner.so --payload-offset 0x... --key-material-offset 0x... --header-key-len 0x10 --xor-key 0x...
adb shell pidof com.example.app
adb logcat -c
adb logcat -v threadtime
adb shell cat /proc/$(adb shell pidof com.example.app | tr -d '\r')/maps
readelf -hW libtarget.so
readelf -SW libtarget.so
readelf -sW libtarget.so
objdump -T libtarget.so
strings -a -t x libtarget.so
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_dump_so.js --no-pause
idat64 -A -S"android-native-auto-reverse/scripts/ida_export_native_summary.py /tmp/libtarget_ida_summary.json" libtarget.so
```

## Report Shape

```markdown
## Scope
- Target:
- Goal:
- Tool/device state:

## Evidence
- Static:
- Runtime:
- Traffic:
- Native:
- Dump/fix:

## Chain
| Stage | Evidence | Function/offset/path | Confidence |

## Findings
1. ...

## Experiments
| Experiment | Before | Change | After | Conclusion |

## Next Steps
1. ...
```
