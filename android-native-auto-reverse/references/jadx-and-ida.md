# JADX And IDA Tool Support

Use JADX and IDA as complementary evidence sources. JADX answers "who calls native code and why"; IDA answers "what the native code does at this offset." Keep their outputs connected by library name, Java signature, native method name, runtime base, and `so!offset`.

## Tool Discovery

Check only the tools needed for the current task.

```bash
command -v jadx || command -v jadx-gui
command -v ida64 || command -v idat64 || command -v ida
command -v apktool
```

If JADX is missing, do not stall static triage. Use `apktool`, manifest reading, smali grep, native library strings, and shell/loader signals. Record that JADX was unavailable and what fallback was used.

If IDA is unavailable, continue with `readelf`, `objdump`, `nm`, `strings`, Ghidra if available, or runtime offsets. Record that IDA export was not produced.

## JADX Workflow

1. Decompile the APK or dumped dex:

```bash
jadx --no-debug-info --show-bad-code --deobf target.apk -d jadx_out
```

2. Run the triage helper:

```bash
python3 scripts/jadx_triage.py jadx_out > jadx_triage.txt
```

3. Inspect high-value anchors:
   - `System.loadLibrary` and `System.load`
   - `native` method declarations
   - `DexClassLoader`, `PathClassLoader`, `InMemoryDexClassLoader`, `DexFile.loadDex`
   - `attachBaseContext`, custom `Application`, shell/stub classes
   - request signing, crypto, TLS pinning, proxy/VPN/root/debug checks
4. Build a Java-to-native map:
   - Java class and method
   - native declaration signature
   - loaded library name
   - caller chain from UI/request/initialization
   - likely native function or RegisterNatives runtime evidence
5. If JADX output is stub-only, switch to unpacking. Do not spend time summarizing shell code as business logic.

## JADX Output Rules

- Prefer exact file paths and line numbers in reports.
- Treat decompiler output as a guide, not ground truth. Verify confusing control flow in smali or runtime evidence.
- For packed apps, rerun JADX on dumped dex and clearly separate original APK JADX output from dumped-dex JADX output.
- If JADX cannot parse a dex, preserve raw dex and try minimal header/checksum repair only when needed to inspect classes.

## IDA Workflow

1. Open the original or dumped `.so` with the correct architecture and base.
2. If comparing runtime offsets, rebase or calculate using the runtime load base from `/proc/<pid>/maps`.
3. Wait for autoanalysis to finish before exporting.
4. Run `scripts/ida_export_native_summary.py` from IDA:

```bash
idat64 -A -S"scripts/ida_export_native_summary.py /tmp/libtarget_ida_summary.json" libtarget.so
```

5. Use the JSON to correlate:
   - exports/imports
   - suspicious strings
   - functions with names or xrefs matching JNI, debug, Frida, root, emulator, path, mmap/mprotect, exit/signal, crypto, or networking
   - offsets from logcat, tombstones, Frida, RegisterNatives, or syscall traces

## IDA MCP Workflow

If an IDA MCP bridge such as `ida-pro-mcp` is available in the current Codex
tool list, prefer it for interactive native analysis:

1. Open the target `.so` in IDA and wait for autoanalysis.
2. Confirm the IDA image base and whether it matches runtime `so!offset`
   convention. For Android PIE libraries, Stalker/Frida offsets usually map to
   IDA image offsets when the database base is zero.
3. Use MCP to navigate to offsets from runtime evidence:
   - Stalker summary callees,
   - Stalker call/ret caller and target offsets,
   - RegisterNatives function pointers,
   - crash/tombstone offsets,
   - direct syscall or anti-Frida scanner offsets.
4. Ask IDA MCP for function bounds, pseudocode, disassembly, xrefs, strings,
   and call graph around each offset.
5. Rename or comment functions only when the runtime evidence supports the
   label. Keep names evidence-based, for example `stalker_aes_round_candidate`
   instead of a final algorithm name too early.

When no IDA MCP bridge is available, use headless/export mode instead:

```bash
idat64 -A -S"scripts/ida_export_native_summary.py analysis/libtarget_ida_summary.json" libtarget.so
```

Then correlate the exported JSON with Stalker logs:

```text
Stalker lib.so!offset -> IDA function containing offset -> strings/constants/xrefs -> runtime args/retval
```

Record whether the analysis came from live MCP or exported JSON. Do not imply
interactive IDA control when only a static export was available.

## IDA Offset Discipline

- Always distinguish file offset, image offset, IDA address, runtime address, and `so!offset`.
- For PIE Android libraries, most runtime evidence should be reported as `library_base + offset`.
- When a log shows `pc = 0x...`, resolve it by maps range, then subtract module base.
- If a dumped `.so` was loaded at a nonzero base or has repaired headers, note the base used in IDA.
- Do not claim a function identity only from a nearby string; confirm xref, call path, or runtime hit.

## RegisterNatives Correlation

For dynamic registration, the strongest map is:

```text
Java class + method name + JNI signature -> native function pointer -> library base -> so!offset -> IDA function
```

Collect it from custom ROM logs, Frida RegisterNatives hooks, IDA xrefs to `RegisterNatives`, or static JNINativeMethod arrays. Store the map in the report before patching or bypass experiments.

## Report Fields

Include:

- JADX command and output path
- JADX triage summary path
- IDA database or analyzed `.so` path
- IDA export JSON path
- runtime maps excerpt for any offset correlation
- Java caller chain
- native function offset and confidence label
