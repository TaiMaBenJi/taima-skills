# Methodology — solving a NEW bypass/hook with renef

This is the durable core of the skill. Recipes age (offsets, class names, signatures rot); this
investigation loop does not. Use it to derive okhttp / flutter / root / debugger / WebView / custom
checks **yourself**, on targets that aren't in any recipe.

## Operating principles

- **Attempt and measure — don't pre-refuse.** Feasibility is decided on the device, not from
  theory. Probe, try the smallest thing, read the result. "I can't" should come from an observed
  failure, not a guess.
- **Decompose to the smallest sufficient goal.** You rarely need to defeat a whole protection
  system — only the one method/offset/path that achieves your objective. An app can have heavy
  shielding (RASP) and you can still hook one WebView/SSL/check path without touching the rest.
  Find the minimal surface.
- **Combine tools.** renef rarely works alone: pair it with a decompiler (jadx for Java class/method
  /signature; Ghidra/IDA/r2 for native offsets) and a proxy (Burp/mitmproxy) to *observe* results.
  Reach for another tool to *add* capability, not as an admission of defeat.
- **Report status honestly in three states** so the human can steer:
  *not attempted* → *installed but unverified* → *verified working*. "The hook installs" is not
  "the bypass works" — say which one you've reached.

## Human ↔ AI division of labor

renef work is a loop between a human and an AI; it goes fastest when each does what it's best at.

| AI does (mechanical, fast, tireless) | Human does (judgment, world-access) |
|---|---|
| Enumerate API (`probe.lua`), read decompiled source, find class/method/signature & offsets | Decide the objective and what "success" means |
| Write/iterate Lua, parse opaque errors, try signature/offset variants | Drive the device & app UI (navigate to the screen, trigger the flow) |
| Install minimal hooks, verify arg layout, build the reflection/patch | Run the proxy, observe traffic, judge whether the bypass truly worked |
| Track honest status, propose next experiment | Authorize the target and the testing |

## The loop

**0. Preconditions.** Confirm you actually have what the task needs before promising results:
device access (adb), root (or gadget mode for non-root), ARM64, `renef_server` running, a decompiler
for target discovery, and a proxy if you need to *see* an SSL bypass. Missing one → say scripts are
best-effort/unverified.

**1. Ground-truth the build — run `probe.lua` first.** Don't trust notes (renef builds differ).
The probe reports the real API surface, error behavior, arg layout, and the reflection bridge.

**2. Classify the layer and framework.** Java/Kotlin logic → Java hook. Native `.so`/crypto/packer
→ native hook by `(lib, offset)`. For SSL specifically, identify the stack: OkHttp / Conscrypt
(`TrustManagerImpl`) / Cronet / **Flutter (native BoringSSL in libflutter.so)** / **WebView
(`onReceivedSslError`)`** — each has a different target. The decompiled app + loaded `Module.list()`
tell you which.

**3. Locate the exact target.**
- Java: jadx → exact class (`/`-form), method, and **signature**. Note whether it's `static` (first
  param = `args[1]`) or instance (`args[2]`), and whether a subclass overrides it (and calls `super`).
- Native: `Module.exports/symbols` for symbol offsets; `Memory.search("FD 7B ?? A9", "lib.so")` etc.
  for unexported code; `md <addr> -d` to confirm. Offsets are build-specific — re-derive per app.
- Not-yet-loaded lib (Flutter, plugins): it won't be in `Module.find` at spawn — defer via a
  `do_dlopen` hook and install on load.

**4. Probe the mechanism in isolation before committing.** If you're unsure renef can do the thing
(call a method on an arg object? modify this return type? patch this page?), prove it on a throwaway
first — with `pcall` so you see the real error. Example: the reflection bridge for calling a method
on a raw pointer was confirmed this way before being used in a WebView bypass.

**5. Install the smallest hook that proves the call fires.** A single `print` in `onEnter`, loaded
with `-w`, exercised from the app. Confirm it fires *before* adding logic. Remember: `hooks` counts
only native trampolines, so verify Java hooks by behavior.

**6. Add the bypass logic — pick the right primitive.**
- Boolean/int check → `onLeave` returns `0`/`1`.
- Void method that throws on failure (e.g. `checkServerTrusted`) → `onEnter` `args.skip = true`.
- Need to call a method on `this`/an arg object → **reflection bridge** (`Method.invoke` with the
  raw pointer as target).
- Native code path → `Memory.patch` (e.g. `MOV X0,#1; RET`).
- Replace an interface implementation → `Java.registerClass` + `Java.array`.

**7. When it resists, narrow or change layer — then check `debugging.md`.** Late-loaded lib? defer
via dlopen. Agent crash / silent abort? hot-hook race — move risky hooks last or avoid them. App
won't start / a target lib never loads? recognize RASP/shielding and re-scope to the minimal goal,
or attack the detection itself (separate, app-specific effort). Opaque `ERROR: Lua execution failed`?
wrap sections in `safe()`/`pcall` to surface the real line.

## Self-improvement

Every time you discover something the docs/skill didn't have — a missing API, a working
class/signature, a build-specific quirk, a new primitive — **write it down** (a findings note, or a
contribution to the skill). The skill is only as good as what's been verified and recorded; this
loop is how it grows. See `CONTRIBUTING.md`.
