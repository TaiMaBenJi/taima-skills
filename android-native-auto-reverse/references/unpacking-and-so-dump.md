# Unpacking And Loaded SO Dump Workflow

Use this reference when the APK is protected/packed, visible Java is only a shell, the real dex appears at runtime, or a native library is encrypted, self-decrypting, anonymous, memfd-backed, or different in memory from the file inside the APK.

## Decision Tree

1. If the goal is Java/business logic recovery, prioritize dex unpacking.
2. If the goal is native algorithm, anti-debug, anti-Frida, or crash root cause, prioritize loaded `.so` mapping and dump.
3. If the app exits before hooks are usable, collect logcat/tombstone/syscall evidence first, then choose an early-window dump point.
4. If the sample is shell-only, do not over-analyze stub code. Use it to find loader timing, payload names, native anchors, and dump windows.

## Static Packer Signals

- Stub Application: `com.stub.StubApp`, `StubApp`, `ShellApplication`, `ProxyApplication`, custom `attachBaseContext`.
- Known or common library names: `libjiagu.so`, `libshell.so`, `libshella.so`, `libDexHelper.so`, `libDexHelper-x86.so`, `libSecShell.so`, `libsecexe.so`, `libsecmain.so`, `libdexprotector.so`, `libprotectClass.so`, `libtup.so`, `libexec.so`.
- Bangcle/SecNeo enterprise clues: `libdatajar.so`, `libdexjni.so`,
  `assets/resthird.data`, `v1filter.jar`, `com.secneo.apkwrapper.*`,
  `com/fort/andjni/JniLib`, shell provider `com.secneo.apkwrapper.CP`, and
  native methods named like `attach`, `b`, `c`, `d`, `e`, `f`, or `cV/cI/cL`.
- Suspicious structure: tiny `classes.dex`, many encrypted assets, native loader much larger than business libs, extracted dex/bin blobs in assets, and native libraries without useful exports.
- Java signs: `DexClassLoader`, `PathClassLoader`, `InMemoryDexClassLoader`, `DexFile.loadDex`, asset extraction, reflection-heavy app bootstrap.
- Native signs: `JNI_OnLoad`, constructor-heavy loader, `mmap`/`mprotect`, custom ELF loader, linker namespace tricks, `memfd_create`, direct syscalls, and self-delete/unlink behavior.

## Protection Categories

Classify the protection before choosing a dump point:

- Whole-dex shell: the original dex is encrypted, compressed, or stored in a custom container. Visible Java is mostly shell code. Goal: dump the recovered dex after it is loaded.
- File-backed whole-dex loading: the shell writes decrypted dex to disk, then loads it with `DexClassLoader`, `PathClassLoader`, `DexFile.loadDex`, or equivalent APIs. Goal: capture the written file and validate it.
- Memory-backed whole-dex loading: the shell decrypts dex into memory and loads it through `InMemoryDexClassLoader`, `DexFile(ByteBuffer[])`, or ART native loaders. Goal: dump from `DexFile`/mCookie/DexFile pointers or memory buffers.
- Function extraction: class and method metadata remain, but selected method bodies are empty, nop-like, native-backed, or restored only during execution. Goal: collect method code after restoration or force method restoration through FART/youpk-style active calls.
- VMP/dex2c/native transformation: Java bytecode is translated or virtualized into native code. Goal: pivot to SO/JNI analysis, VM dispatcher analysis, RegisterNatives mapping, and runtime traces.
- Native/ELF packing: `.so` structure, sections, imports, or text/data are encrypted or loaded by a custom linker. Goal: dump mapped executable ranges and repair enough for IDA/Ghidra.
- Shell-SO wrapping: the file-backed loader library itself is a small outer ELF that decrypts a richer inner ELF before relocation or handoff. Goal: identify `.init_array`/constructor entry, reconstruct or dump the inner ELF, then analyze the inner artifact instead of the outer shell.

Common side protections include string/resource encryption, anti-debug, signature verification, root/emulator/proxy checks, and anti-Frida logic. Record them as environment constraints, but do not let them distract from the primary dump target.

## Rule-Based Shell Recognition

Run the built-in scanner before deep manual analysis:

```bash
python3 scripts/scan_apk_shell.py target.apk
python3 scripts/scan_apk_shell.py target.apk --json > shell_scan.json
```

The scanner loads `references/apkpackdata.json` by default. The rule database contains 52 shell/protector families and matches:

- `sopath`: exact APK archive paths such as `assets/libjiagu.so` or `lib/armeabi/libxxx.so`
- `soname`: native library basenames regardless of ABI directory
- `other`: non-so payload files such as encrypted dex blobs, appkey files, jar/dat/bin assets
- `soregex`: regex patterns for variant library names

Use `--rules <json>` to test a newer rule database without editing the skill. Treat rule hits as strong triage evidence, not final proof. Confirm with manifest/Application, dex size, loader behavior, JADX output, native strings, maps, `dlopen`, or dump results.

Recommended confidence labels:

- `rule-hit`: file name/path/regex matches a known shell rule.
- `rule-hit-plus-loader`: rule hit plus loader APIs or shell Application.
- `packed-confirmed`: runtime evidence shows real dex/native payload loading or dump succeeds.
- `not-packed-evident`: no rule hit and normal Java/native business code is visible.

## Dex Unpacking Flow

1. Record original APK hash, package name, version, ABI, shell clues, and visible Application.
2. Run normal decompile first enough to prove whether visible code is shell-only.
3. Identify load mechanism and dump timing:
   - after `attachBaseContext`
   - after shell `Application.onCreate`
   - after native loader `JNI_OnLoad`
   - after first Activity starts
   - after feature/plugin extraction
   - when `DexClassLoader`, `PathClassLoader`, `InMemoryDexClassLoader`, `DexFile.loadDex`, `openDexFile`, `openInMemoryDexFilesNative`, or `OpenDexFilesFromOat` is hit
4. Prefer existing trusted dumpers in the environment when available. Common choices are custom ROM dump output, Frida-based class-loader/dex dumping, objection/r0capture-style helpers, or local project dump scripts.
5. Pull dumped dex files, hash them, and sort by size/class count/package names.
6. Validate with jadx:
   - target package classes exist
   - business entry points exist
   - request/signature/native bridge code exists
   - stub-only classes are no longer the majority
7. If dumped dex has checksum/header issues, repair only enough to load in jadx or extract strings/classes. Preserve the raw dump.
8. Reconnect Java call chains to native methods and loaded libraries.

## ART DexFile And mCookie Dump Points

When a shell uses memory-backed dex or hides file-backed artifacts, use ART loader internals to choose Hook/dump points. The exact symbol names vary by Android version, but the evidence chain is stable:

1. `InMemoryDexClassLoader(ByteBuffer[])` calls `BaseDexClassLoader`.
2. `BaseDexClassLoader` builds a `DexPathList`.
3. `DexPathList.initByteBufferDexPath()` creates a `DexFile` from the byte buffers.
4. `DexFile(ByteBuffer[])` stores `mCookie` and `mInternalCookie`.
5. Native `openInMemoryDexFilesNative()` copies direct or array-backed byte buffers into ART memory.
6. `OpenDexFilesFromOat` / `OpenDexFilesFromOat_Impl` / `DexFileLoader::OpenOne` / `DexFileLoader::OpenCommon` create `StandardDexFile` or `CompactDexFile`.
7. `DexFile::DexFile` owns the useful `begin` pointer, `size`, header, ids, class defs, and container metadata.

Why `mCookie` matters:

- On ART, `mCookie` commonly references a native array or structure that includes `DexFile*` pointers and sometimes an oat pointer.
- Each `DexFile*` exposes the dex base and size through ART internals.
- BlackDex-style dumpers use this Java-to-native bridge to dump loaded dex even when no decrypted dex file exists on disk.

Practical evidence to collect:

- Class loader type and parent chain.
- `DexPathList.pathList.dexElements`.
- `DexPathList$Element.dexFile`.
- `DexFile.mCookie` and fallback `mInternalCookie`.
- class name list from the `DexFile`.
- memory base/size from native `DexFile` or mapped buffers.
- dumped dex SHA-256, size, class count, and JADX validation.

Good Hook targets by level:

- Java level: `InMemoryDexClassLoader`, `BaseDexClassLoader`, `DexClassLoader`, `PathClassLoader`, `DexFile.loadDex`, `DexFile` constructors, and `DexPathList`.
- ART/native level: `openInMemoryDexFilesNative`, `OpenDexFilesFromOat`, `DexFileLoader::OpenCommon`, `DexFile::DexFile`, `ClassLinker` dex cache traversal, and `ArtMethod::GetDexFile`.
- Runtime observation: class loader creation, byte buffer sizes, class counts, and first app package class resolution.

When a shell hooks ART itself, also inspect `DexFileVerifier::Verify` or
`DexFileVerifier::verify`, `ClassLinker::OpenDexFilesFromOat`, and
`DexFile::OpenMemory`. Some enterprise shells create placeholder dex files with
only magic bytes, route selected files through a fake `OpenDexFilesFromOat`, and
feed the real dex bytes to `OpenMemory`.

Use the ART watcher when these symbols are suspected:

```bash
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_art_openmemory_watch.js --no-pause
adb pull /data/local/tmp ./art_openmemory_dumps
python3 android-native-auto-reverse/scripts/dex_dump_validator.py art_openmemory_dumps --out analysis/openmemory_dex_validation.json
```

Treat dumped DEX files as candidates. Validate package names, class counts, and
business anchors before claiming success.

For Android 8+ memory loading, `InMemoryDexClassLoader` is a high-value signal. For older or file-backed loading, `DexClassLoader`/`PathClassLoader` and written dex paths may be enough.

## ClassLoader Recovery Strategy

Do not assume `LoadedApk.mClassLoader` points to the real app dex in protected apps. Common layouts:

- Normal app: `BootClassLoader -> PathClassLoader`, and `LoadedApk.mClassLoader` points to the app `PathClassLoader`.
- Protected app with inserted loader: `BootClassLoader -> DexClassLoader -> PathClassLoader`, while the visible path loader may still represent shell code.
- Protected app with replacement loader: `BootClassLoader -> PathClassLoader -> DexClassLoader`, and `LoadedApk.mClassLoader` may be replaced after shell startup.

Procedure:

1. Get one app class loader from `ActivityThread.currentActivityThread() -> mBoundApplication -> info -> mApplication -> getClassLoader()`.
2. Walk parent class loaders until `BootClassLoader`.
3. For each non-boot loader, inspect `BaseDexClassLoader.pathList.dexElements`.
4. For each element, extract `dexFile`, `mCookie` or `mInternalCookie`, and class names.
5. Prefer class loaders that contain target package/business classes over shell-only packages.
6. If class names are present but methods are empty or nop-like, classify as function extraction and use method restoration strategy.

## Whole-Dex Versus Function-Extraction Strategy

Whole-dex protection:

- Dump after the dex is decrypted and loaded.
- `mCookie`, `DexFile*`, class loader, `OpenCommon`, and `ArtMethod::GetDexFile()` are all viable dump paths.
- A valid whole-dex dump should contain class defs and business strings/classes even if checksums or headers require small repair.

Function extraction:

- Case A: method bodies are restored during execution and remain restored. Use delayed dump after exercising flows.
- Case B: method bodies are restored during execution and extracted again afterward. Delayed whole-dex dump is insufficient; capture method code during the execution window.
- Case C: method bodies require forced restoration. Use FART/youpk-style active invocation to enumerate classes/methods and trigger restoration, then dump `CodeItem` data.

FART/youpk concepts to recognize:

- FART whole-dex dumping commonly pivots from interpreter `Execute` or `ArtMethod` to `artmethod->GetDexFile()`, then dumps `dex_file->Begin()` and `dex_file->Size()`.
- For function extraction, FART-style logic can enumerate class names from `DexFile`, load classes, walk constructors/methods, and call a native `dumpMethodCode` bridge.
- Active invocation may intentionally pass sentinel/null arguments into modified ART code to trigger dump paths rather than execute business behavior normally.
- youpk-style approaches can enumerate `ClassLinker::DexCacheData`, filter system dex paths, and collect `data.dex_file` pointers.

Record whether the approach is:

- passive dump: wait until shell loads dex, then dump.
- delayed dump: exercise features, then dump after restoration.
- active restoration: enumerate and invoke methods to force code restoration.
- method-code capture: dump individual `CodeItem` bytes with method index, offset, and length for later repair.

Validation for extracted-method recovery:

- compare method bodies before/after exercise or active invocation.
- record method index, code item offset, code item length, and owning dex size.
- verify restored methods decompile or at least disassemble into non-empty instructions.
- do not claim full recovery if only class names are restored while method bodies remain empty.

## Bangcle libDexHelper Flow

For 梆梆/Bangcle samples, especially enterprise-style `libDexHelper.so`
protectors:

1. Confirm static signs with `scan_apk_shell.py`, native library names, stub
   Java, and encrypted assets.
2. Treat `libDexHelper.so` as the loader/decryption target. Check
   `.init_array`, `JNI_OnLoad`, `RegisterNatives`, `mmap`, `mprotect`,
   `dlopen`, and dex/class-loader references.
   Use `elf_init_array_finder.py` to locate the first constructor/init-array
   candidates before deep IDA work.
3. If the goal is Java recovery, start with frida-dexdump:

```bash
frida-dexdump -U -f com.example.app -o dumps/com.example.app --sleep 8
frida-dexdump -U -n com.example.app -o dumps/com.example.app -d --sleep 5
```

4. If timing is unclear, log loader events:

```bash
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_watch_dex_loading.js --no-pause
```

5. Validate all dumped dex files before claiming success:

```bash
python3 android-native-auto-reverse/scripts/dex_dump_validator.py dumps/com.example.app --out analysis/dex_dump_validation.json
jadx --no-debug-info --show-bad-code dumps/com.example.app/classes.dex -d dumped_jadx
```

6. If dumped dex still has extracted/empty methods, pivot to native analysis of
   `libDexHelper.so` and map restored Java methods to native offsets.
7. If `libDexHelper.so` itself is an outer shell, identify the init-array entry,
   label decrypt/transform/relocation calls, reconstruct or dump the inner SO,
   then compare outer and inner function counts in IDA/Ghidra.
   For RC4-like-header plus XOR-body samples, use
   `scripts/bangcle_dexhelper_inner_decrypt.py` with sample-derived offsets and
   keys, then validate the output with ELF magic, `readelf`, function count, and
   JNI/string richness.

### SecNeo/Bangcle Enterprise Variant

For enterprise variants with `com.secneo.apkwrapper` and ART hook behavior, use
this additional flow:

1. Manifest/Java entry:
   - inspect `Application.attachBaseContext`,
   - identify shell classes such as `AW`, `H`, or `CP`,
   - record the real application name and `appComponentFactory` if the shell
     later replaces them.
2. Loader library:
   - copy `libDexHelper.so` / `libDexHelper-x86.so` and any `libdatajar.so`,
   - locate init/init-array code that maps/copies encrypted segments,
   - watch `mprotect` transitions; the end of code/data permission restoration
     is a good SO dump window.
3. JNI bridge:
   - log or statically recover `RegisterNatives`,
   - map shell methods such as `attach`, `b`, `c`, `d`, `e`, `f` to native
     offsets,
   - treat native method `f`/`makeDexElements` style paths as high-value DEX
     load points.
4. DEX decrypt/load:
   - look for reflection into `java/lang/Class`, `DexCache`, and `dexFile`,
   - find injected data inside the shell dex or `libdatajar.so`,
   - identify auxiliary resources such as `assets/resthird.data` being released
     as `v1filter.jar`,
   - hook or break on `OpenMemory` to dump the real DEX bytes.
5. ART hook evidence:
   - `DexFileVerifier::Verify` forced success indicates verifier bypass,
   - fake `OpenDexFilesFromOat` may branch between auxiliary jar file loading
     and in-memory `classes.dex` loading,
   - placeholder `.cache/classes*.dex` files containing only magic bytes are
     not the real payload.

Report whether the dump came from file-backed dex, `OpenMemory`, mCookie, or
an external dumper. These paths have different confidence and repair needs.

## VMP/libdexjni Triage

Some variants include `libdexjni.so` and move selected Java methods, often
Activity lifecycle code, into a native VMP-like interpreter. This is not solved
by whole-dex dumping alone.

Triage signs:

- Java methods call `com.fort.andjni.JniLib` native entries such as `cV`, `cI`,
  `cL`, `cS`, `cB`, or `cJ`.
- `RegisterNatives` registers many type-specific native bridge methods.
- Native code contains handler tables, opcode decode loops, JNI calls such as
  `FindClass`, `GetMethodID`, `Call*Method`, or `CallNonvirtual*Method`.
- Opcode bytes are encrypted or transformed, often with a per-method or
  per-offset key table.

Analysis route:

1. Recover `RegisterNatives` mapping for `JniLib`.
2. Identify VMP entry variants by return type and signature.
3. Trace from a Java call into the native VMP entry, recording the `vmpId` or
   method index and the structure that contains the code item pointer.
4. Log handler dispatch and JNI calls. Infer bytecode semantics from side
   effects: `FindClass`/`GetMethodID`/`CallNonvirtualVoidMethodA` can reveal
   `invoke-super`, field setters can reveal `iput-object`, and string lookups
   can reveal `const-string`.
5. Build an opcode-to-smali mapping table per app version. Do not assume the
   table is stable across versions unless two samples prove it.

Record recovered instructions as partial reconstruction unless all handlers,
operands, and key derivation are mapped.

## Loaded SO Dump Flow

1. Identify target process and library name or runtime anchor.
2. Capture maps:

```bash
adb shell pidof com.example.app
adb shell cat /proc/<pid>/maps > maps.txt
```

3. Locate mappings:
   - file-backed `/data/app/.../lib/arm64/libtarget.so`
   - extracted shell paths under app data
   - deleted mappings
   - `[anon:...]`
   - `memfd:name`
4. Choose dump timing:
   - stable: library stays mapped after app settles
   - early-window: dump on `dlopen`, `android_dlopen_ext`, constructor, `JNI_OnLoad`, or first registered native call
   - decrypt-window: dump after `mprotect` changes a range to executable or after the first call into decrypted code
5. Dump the exact mapped range. For Frida, start from `scripts/frida_dump_so.js` and change `TARGET_LIB`, output path, and trigger timing.
6. Validate:

```bash
file dumped.so
readelf -hW dumped.so
readelf -lW dumped.so
strings -a -t x dumped.so | head
```

7. Load into IDA/Ghidra using the runtime base when comparing offsets. If dumped offset `0x1234` came from `base + 0x1234`, keep that base in the report.
8. If ELF headers are damaged, recover by segments. Do not require section headers unless decompiler loading is blocked.

## Early-Window Targets

- `android_dlopen_ext`: best for knowing library path and load base.
- `call_constructor` or linker constructor traces: useful when crash happens before `JNI_OnLoad`.
- `JNI_OnLoad`: good point after loader setup and before Java calls.
- `RegisterNatives`: high-value point for mapping Java method signatures to native offsets.
- `mprotect` or `pkey_mprotect`: useful for self-decrypting code when RW becomes RX.
- `memfd_create`: useful when code is loaded from anonymous in-memory ELF.

## Fixup Principles

- Keep raw and fixed outputs separate.
- Record every fixup step.
- Prefer minimal fixup: enough for IDA/Ghidra/jadx to load and for offsets to match runtime evidence.
- For ELF dumps, program headers and mapped segments matter more than section headers.
- For dex dumps, class readability and package matching matter more than perfect original APK reconstruction.

## Report Requirements

Include:

- original APK/SO path and SHA-256
- shell/packer clues
- rule hit family, matched file, and confidence label
- dump timing and command
- PID, package, ABI, Android version
- maps excerpt with base/end/perms/path
- raw dump path and fixed dump path
- validation results
- how dumped code changes the previous static conclusion
