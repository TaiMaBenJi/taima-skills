# Debugging Renef (renef hides errors — read this first)

renef gives you almost no diagnostics. **Every Lua error — syntax or runtime — is reported as a
single bare line with no message, no line number, no stack trace, and the rest of the script
silently stops running:**

```
ERROR: Lua execution failed
```

This is the #1 reason scripts "do nothing" or "error silently." The good news: the real error IS
recoverable — renef's *loader* throws it away, but `pcall`/`load` inside your script can capture it.

## Failure symptoms → what they mean

| What you see | Meaning | Fix |
|---|---|---|
| `ERROR: Lua execution failed` | A Lua **syntax or runtime** error. Output stops at that point; everything after it never runs. | Wrap sections in `pcall` and print the error (below). Syntax errors print **nothing** before the line → run `luac -p` locally first. |
| `(no response)` after "Loading script" | Server session is stale/occupied, **or** you used `--pause` (the gate buffers + resumes, returning no inline response). | Restart the server + `am force-stop` the app (below). For `--pause`, see its caveats. |
| `Agent disconnected` (in watch) | The injected **agent process crashed** — usually a hot hook firing mid-install, or a bad `Memory.patch`. | Don't hook hot functions while the app runs; install risky hooks last (below). |
| `[ERROR] Failed to start process` | Spawn/attach failed. Attach often fails on hardened apps; server may be stuck. | Spawn instead of attach; restart server + force-stop app. |
| `Failed to install Java hook` (from a `pcall`) | The class/method/signature isn't present (e.g. hooking a framework the app doesn't ship, or a wrong signature). | Expected when probing many candidates — keep it in `safe()`; verify the class/sig in jadx. |
| Script loads, hook never fires | Wrong offset / class / signature, lib not loaded yet, wrong hook engine, **or a subclass override that doesn't call `super`** (hooking the base class won't catch it). | Verify with `Module.find`, `hookgen`, `md <addr> -d`; defer not-yet-loaded libs via `do_dlopen`; hook the app's actual subclass by name. |

## Recover the real error message with pcall

`pcall` returns the full Lua message **with a line number** — renef just doesn't surface it for you:

```lua
local ok, err = pcall(function() this_is_missing(1) end)
-- ok=false  err=[string "..."]:2: attempt to call a nil value (global 'this_is_missing')
if not ok then print("ERR: " .. tostring(err)) end
```

So the single most important habit when scripting renef is to **wrap every independent hook/section
in a `safe()` helper that prints the real error** — one failure then neither hides itself nor
aborts the rest:

```lua
local function safe(label, fn)
  local ok, err = pcall(fn)
  if ok then print(GREEN .. "[+] " .. label .. RESET)
  else      print(RED   .. "[-] " .. label .. "  ::  " .. tostring(err) .. RESET) end
end

safe("MyClass.check", function()
  hook("com/x/MyClass", "check", "()Z", { onLeave = function() return 0 end })
end)
```

### Catch SYNTAX errors before loading
A syntax error aborts the whole chunk before anything runs (you see only `ERROR: Lua execution
failed`, no prints). `pcall` can't help (the chunk never compiles). Two ways to find them:

1. **Pre-check locally** (best): `luac -p script.lua` (Lua 5.4 ideally; 5.3/5.5 catches almost all).
   Renef runs Lua 5.4 — avoid 5.5-only syntax.
2. **Recover at runtime** with `load`: `local f, e = load(code); print(e)` →
   `[string "..."]:1: unexpected symbol near '='`.

### `pcall` does NOT catch everything
Some failures are **not** catchable Lua errors — notably installing a hook on a **hot function
while the app is running** can abort the chunk (or crash the agent) in a way `pcall` cannot trap.
Defensive code can't save you there; you must avoid the dangerous target or change *when* you install.

## The hot-hook install race (causes silent abort / `Agent disconnected`)

When you **spawn without freezing the app** and hook a frequently-called function, the app calls
that function on another thread **while your script is still installing hooks** → the hook fires
re-entrantly → the script aborts (uncatchable) or the agent crashes (`Agent disconnected`).

Observed on a real app: hooking libc `open` crashed right after install; `stat`/`access`/`fopen`
aborted the chunk after a few installs; `do_dlopen` crashed the agent during the startup library
storm. Cold functions (10+ of them) installed fine.

Hottest / most dangerous to hook: `open`, `read`, `write`, `system`, `popen`, `malloc`, `free`,
`do_dlopen`, and at app startup `stat`/`access`/`fopen`/`__system_property_get`.

Mitigations, in order of preference:
1. **Don't hook the hottest libc functions.** For file-based checks prefer `access`/`stat`; for
   command execution prefer the **Java** layer (`Runtime.exec`, `ProcessBuilder.start`) over libc
   `system`/`popen`.
2. **Install risky hooks LAST**, after the important bypasses (SSL, etc.), so a race can't lose them.
3. **Install before app code runs** — `--pause` in theory (but see caveats); or attach when the app
   is idle rather than mid-startup.
4. Use `caller=` (PLT/GOT) scoping so only calls from a specific lib are intercepted (far less hot).

## `--pause` (spawn gate) caveats

`--pause`/`-p` is meant to freeze the app so hooks install before `onCreate`. In practice:
- It returns **`(no response)`** and **swallows your script's load-time prints** — they do not appear
  inline. Use `-w`/`watch` to see *runtime* hook output.
- On some agent builds/targets it **may not install hooks at all** (verify — don't assume). If hooks
  don't take effect, fall back to plain spawn with careful ordering (risky hooks last), or attach.
- Verify by **behavior**, not prints: check that the bypass actually works, read back patched bytes
  (`Memory.readU32`), etc.

## Verifying installs

- The **`hooks`** command lists only **native trampoline** hooks — **Java hooks do not show up**
  there (you can see `Active hooks: 0` with Java hooks active). Don't use it to confirm Java hooks.
- Confirm a **native patch** by reading the bytes back: `Memory.readU32(addr)` before/after.
- Confirm a **hook fires** by `print`-ing in `onEnter` and running `watch` while you exercise the app.

## Connection recovery (stale server / "(no response)")

```bash
# 1) find & restart the server (path varies; magisk-renef installs here):
adb shell su -c 'kill $(pidof renef_server)'
adb shell su -c 'nohup /data/adb/modules/magisk-renef/system/bin/renef_server >/data/local/tmp/renef_server.log 2>&1 &'
# 2) re-establish the forward and clear the app:
adb forward tcp:1907 localabstract:com.android.internal.os.RuntimeInit
adb shell am force-stop <package>
# 3) check the server log if spawn keeps failing:
adb shell 'tail -n 30 /data/local/tmp/renef_server.log'
```
Attach (`-a`) frequently fails on hardened apps (`Failed to start process`) — prefer `-s` (spawn).

## Hardened apps / RASP (why a correct script can still "not work")

If the app ships shielding/RASP libraries — commercial products like Promon SHIELD,
Guardsquare/DexGuard, Appdome, Talsec/freeRASP, Zimperium, or vendor-custom native libs (often named
like `libshield*.so` / `libsecurity*.so` / `libguard*.so`) — it may **detect renef's injection and
refuse to fully start** (e.g. a Flutter app never loads `libflutter.so`; a
target lib never appears in `Module.list()`). In that case your bypass is *correct* but lands too
late: the RASP gate runs first. Recognize this by listing modules early and noting the app stalls /
the target lib never loads. Defeating RASP is a separate, app-specific effort (hook/patch the
detection routines in the shield lib before they run) — not something a generic SSL/root script does.

## Pre-flight checklist for any renef script

1. `luac -p script.lua` — catch syntax errors locally (renef won't tell you the line).
2. Wrap every hook/section in `safe()` so failures print and don't cascade.
3. Put the important bypasses first; risky/hot hooks last (or omit).
4. Load with `-w`; trigger the app; watch for `[+]` installs and runtime output.
5. If `(no response)` / `Agent disconnected` / `Failed to start process` → see the tables above.
