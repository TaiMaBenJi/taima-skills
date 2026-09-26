# Renef Gotchas, Discrepancies & Troubleshooting

## Mistakes agents make most

1. **Treating it like Frida JS.** It's Lua 5.4. `local`, `..`, `nil`, `function()...end`,
   `string.format`, `ipairs`, `#t`, `0x`-hex ints. No `var/let/const`, no arrow fns, no template
   strings, no `===`.
2. **Hardcoding an absolute address as the hook target.** `hook()` takes `(library, offset)`. The
   offset is relative to the lib base; renef resolves the live base. Compute absolutes only for
   `Memory.*` (`Module.find(lib) + offset`).
3. **Wrong Java arg index.** Java: `args[0]`=ArtMethod* (ignore), `args[1]`=`this` (instance) or
   first param (static), `args[2..]`=params. Native: `args[0]`=first arg. Mixing these up reads
   garbage. For a `static` method the first real parameter is `args[1]`, NOT `args[2]`.
4. **Using `args` inside `onLeave`.** `args` is only in `onEnter`. To carry state, close over a
   `local` declared just before the `hook(...)` call (see recipes). The official docs' root-bypass
   `args.block` snippet is buggy for this reason — don't copy it.
5. **Expecting `retval.replace()`.** In renef you `return` the new value from `onLeave`. Returning
   nothing keeps the original. For native pass-through, `return retval`.
6. **Dotted Java class names.** Must be `/`-separated JNI form: `com/example/Foo`.
7. **Omitting the JNI signature.** Java hooks always need the exact `(params)ret` signature — no
   automatic overload resolution. Get it from the decompiled method (e.g. jadx).
8. **Forgetting to watch.** Hook/syscall output is async. Use `-w` or the `watch` command, or you
   see nothing even though hooks fire.
9. **Reaching for Frida globals.** No `Interceptor`, no `Java.perform`, no `Process.enumerate*`,
   no `Memory.scanSync`, no `ptr()`/NativePointer. Use `Module`, `Memory`, `hook`, `Java`, `Jni`,
   `Thread`, `File`, `Syscall`, `OS`.

> **Most "it errors silently / I can't tell where it failed" problems are covered in
> `references/debugging.md`** — renef reports all errors as a bare `ERROR: Lua execution failed`
> and aborts the rest of the script. Read that file first when something doesn't work.

## Documentation vs runtime discrepancies (verified on-device)

- **`Memory.writeString` does NOT exist** (`type(Memory.writeString) == nil`). Older example
  scripts (e.g. `root_bypass.lua`) call it — those calls fail at runtime. Use
  `Memory.write(addr, str .. "\0")` to write a string into a buffer.
- **`Jni.newStringUTF(s)` and `JNI.string(s)` BOTH exist** (verified — both functions; `Jni`/`JNI`
  both tables). `Memory.readStr` and `Memory.readString` both exist. Prefer `Jni.newStringUTF`.
- **Static vs instance arg index — verified:** for a **static** Java method the first parameter is
  `args[1]`; for an **instance** method it's `args[2]` (`args[1]` is `this`). Confirmed by hooking
  static `String.valueOf(I)` and calling `valueOf(4242)` → `args[1]==4242`, `args[2]==0`.
  Common static targets people get wrong: `SystemProperties.get`, `System.getProperty`,
  `String.valueOf`. Spoof their result in `onLeave`; don't mutate the input key in `onEnter`.
- **`hooks` command counts only native trampolines** — Java hooks never appear (can show
  `Active hooks: 0` with Java hooks live). Verify Java hooks by behavior, not by `hooks`.
- **`Process.modules()`** — appears in a debug branch of `root_bypass.lua`, but `Process.*` is **not**
  a real renef global (Frida-ism). Use `Module.list()` (string) / `Module.exports()`.

## Install-time race & hot hooks (verified — causes silent abort / agent crash)

Hooking a frequently-called function **while the app is running** (plain spawn) makes that hook fire
on another thread *during* install → the script aborts (`ERROR: Lua execution failed`, **not**
catchable by `pcall`) or the agent crashes (`Agent disconnected`). Verified on a real app: libc
`open` crashed immediately; `access`/`stat`/`fopen` aborted after a few installs; `do_dlopen`
crashed the agent during the startup library storm; 10+ *cold* hooks installed fine. Avoid hooking
`open`/`read`/`write`/`system`/`popen`/`do_dlopen` (and startup-hot `stat`/`access`/`fopen`); put
important bypasses first and risky hooks last. Full detail: `references/debugging.md`.

## `--pause` and connection issues (verified)

- `--pause`/`-p` returns `(no response)` and **swallows load-time prints**; on some builds/targets
  it **doesn't install hooks at all**. Don't rely on it blindly — verify by behavior.
- `(no response)` / `[ERROR] Failed to start process` is usually a **stale server session**.
  Restart `renef_server` + `am force-stop` the app + re-`adb forward` (commands in `debugging.md`).
- **Attach (`-a`) often fails on hardened apps** — prefer spawn (`-s`).
- **RASP/shielded apps** — commercial app-shielding (Promon SHIELD, Guardsquare/DexGuard, Appdome,
  Talsec/freeRASP, Zimperium) or vendor-custom native libs (often named like `libshield*.so`,
  `libsecurity*.so`, `libguard*.so`) — may detect renef and prevent the app from fully starting;
  a Flutter target may never load `libflutter.so`. Your script can be correct yet land too late.
  See `references/debugging.md` → RASP.
- **Color constants** (`RED`, `GREEN`, …, `RESET`) are predefined globals when a script runs via
  `l`/`exec`. Some example scripts also redefine them locally with raw escapes
  (`local RED = "\27[31m"`) — harmless, and a safe fallback if a global is ever missing.
- **`__hook_type__ = "trampoline"|"pltgot"`** — a script-level global that selects the engine for
  that script (overrides nothing else). Set it at the very top.

## When things don't work

### Injection fails / "Failed to find libc base"
- Device must be **rooted ARM64**. Only ARM64 is supported.
- SELinux: try `adb shell su -c setenforce 0` (or use `--local`/UDS which is SELinux-safe).
- `adb root` if available; confirm the process exists (`adb shell pidof com.pkg`).
- Re-run with `-v` to see agent logcat.

### Server won't start / can't connect
```bash
adb shell killall renef_server; adb shell /data/local/tmp/renef_server &
adb forward --remove tcp:1907
adb forward tcp:1907 localabstract:com.android.internal.os.RuntimeInit
adb forward --list
```
Or install **magisk-renef** so the server auto-starts on boot.

### Hook not triggering
1. Verify the offset really maps to the function (`hookgen`, or disasm with `md <addr> 64 -d`).
2. Confirm the library is loaded: `Module.find("libapp.so")` — many libs load lazily; trigger the
   feature first, or hook `do_dlopen` and install on load.
3. Try the other engine: `--hook=pltgot` (imported fns) vs `trampoline` (any address).
4. For Java, double-check the class/method/signature exactly (case, `/`, `;`).
5. Make sure you're actually watching (`-w`).

### Memory read crashes
Wrap in `pcall` and null-check addresses:
```lua
local ok, data = pcall(function() return Memory.read(addr, 16) end)
if not ok then print("read failed: " .. tostring(data)) end
```

### Startup-time checks fire before hooks
Use the **spawn gate**: `renef -s com.pkg -l bypass.lua --pause`. Hooks install during the freeze,
before `onCreate`. Without a script, `--pause` then `resume` manually.

## Performance notes
- Trampoline hook ≈ 10–50 ns/call; PLT/GOT ≈ 5–10 ns/call; Lua callback adds more. Keep callbacks
  tiny on hot functions (and avoid `print` storms — they dominate cost).
- `Memory.search` scans all readable `.so` (capped ~50MB / ~1000 matches). Scope with a `lib`
  argument and a specific pattern for big apps.
- `Module.symbols()` can return thousands of entries — cache it; prefer `exports()` when the
  symbol is public.

## Reverse-engineering offsets (when no symbol exists)
- Pull the lib: `unzip -j app.apk lib/arm64-v8a/libfoo.so`, analyze in Ghidra/IDA/radare2/Binary
  Ninja → note the file offset (== runtime offset from base for the `.text` mapping in most cases).
- Or pattern-scan at runtime: `Memory.search("FD 7B ?? A9", "libfoo.so")` for prologues, then
  `md <addr> 64 -d` to confirm.
- **r2renef** lets you do live r2 analysis on the running process and hook from the r2 prompt.
- Hardcoded offsets are version-specific — prefer resolving by exported/symtab symbol or by a
  stable byte pattern, and guard with `if not base then return end`.
