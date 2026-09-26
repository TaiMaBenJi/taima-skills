# Renef CLI Reference

The `renef` binary is the **host client** (REPL). It talks to `renef_server` on the device.

## Launch options

```
renef [options]
  -s, --spawn <package>   Spawn app by package, inject, then interactive/script
  -a, --attach <pid>      Attach to running process (adb shell pidof <pkg>)
  -g, --gadget <pid>      Connect to embedded gadget agent (non-root, patched APK)
  -d, --device <id>       Pick ADB device (adb devices) when multiple connected
  -l, --load <script>     Load+exec a Lua script right after connect (repeatable via REPL)
  -w, --watch             Auto-watch hook output after loading (Ctrl+C to exit)
  -v, --verbose           Show agent logcat debug output (troubleshoot injection/hooks)
      --local             Connect via UDS directly (on-device: Termux/adb shell; SELinux-safe)
      --hook <type>       trampoline (default) | pltgot
  -p, --pause             Spawn gate: freeze process after inject until script loads
  -m, --mode <mode>       Interface mode: v/view (TUI) | CLI (default)
  -h, --help

> Verified caveats: `-p/--pause` returns `(no response)` and swallows load-time prints (use `-w` to
> see runtime output), and on some builds doesn't install hooks at all — verify by behavior. When
> spawn/attach prints `(no response)` or `Failed to start process`, the server session is usually
> stale: restart `renef_server` + `am force-stop` the app + re-`adb forward`. Attach (`-a`) often
> fails on hardened apps — prefer `-s`. See `references/debugging.md`.
```

Examples:
```bash
renef -s com.example.app                       # spawn, interactive
renef -s com.example.app -l hook.lua -w        # spawn, load, watch
renef -a 12345 --hook pltgot -l script.lua     # attach, PLT/GOT engine
renef -d emulator-5554 -s com.example.app      # specific device
renef -g 12345 -l script.lua                   # gadget (no root)
renef -s com.example.app -l bypass.lua --pause # beat startup checks
renef -s com.example.app -v                    # verbose injection debug
```

## REPL commands

### Process
- `spawn <pkg> [--hook=pltgot] [--pause]` → `OK <pid>`
- `attach <pid> [--hook=pltgot]` → `OK`
- `resume` — resume a `--pause`'d process (only needed when paused without a script)

**Spawn gate (`--pause`)** freezes the target with `SIGSTOP` right after injection; loading a
script (`-l` or `l`) writes it to the kernel socket buffer and resumes with `SIGCONT`, so hooks
install (µs) before the main thread reaches `onCreate` (ms). No ptrace/proc-trace/SELinux audit —
undetectable by anti-tamper. Use it for root/integrity/debugger checks that run at startup.

### Apps
- `la` / `la~filter` — list installed packages, `~` filters (`la~google`)

### Scripts
- `exec <lua>` — run Lua in target. Bare input with no known command prefix is auto-`exec`'d.
- `l <file> [file2 ...] [-w|--watch]` — load one or more script files (executed in order).

### Memory
- `ms <hexpattern>` — scan all readable `.so` regions (hex only at CLI; e.g. `ms C0035FD6`).
  For strings/wildcards use Lua: `exec Memory.dump(Memory.search("native"))`.
- `msi <hexpattern>` — interactive TUI: `[d]ump [p]atch [w]atch [c]opy [q]uit`.
- `md <addr> <size> [-d]` — dump bytes; `-d` disassembles as ARM64.

### Hooks
- `hooks` — list active hooks with ids
- `unhook <id|all>` — remove hook(s)
- `hookgen <lib> <offset|symbol>` or `hookgen <symbol>` — print a Lua hook template (scaffold)

### Monitoring / tracing
- `watch [address]` — stream hook output in real time (`q` to exit). Needed because hook output
  is async.
- `renef-strace <syscalls> | -c <category> | -a [-f <lib>] | --list | --active | --stop` —
  built-in syscall tracer (PLT/GOT). In-shell needs no `-p`.

### Utility
- `help` · `q` (quit) · `clear` · `color [prompt=CYAN|response=GREEN|...]`

## Connection modes in depth

### Root mode (standard)
Server injects at runtime via memfd+shellcode. Can spawn or attach any app. All APIs.
```bash
adb shell /data/local/tmp/renef_server   # start server (or use magisk-renef to auto-start)
renef -s com.example.app
```
ADB forwards `tcp:1907` ↔ `localabstract:com.android.internal.os.RuntimeInit` (done automatically).

### Gadget mode (`-g`, no root)
Embed `libagent.so` in the APK (apktool: add to `lib/arm64-v8a/`, add a `System.loadLibrary`
loader via smali/LSPatch), rebuild, **re-sign** (breaks signature-based checks/Play Integrity),
install. Then `make gadget-forward` (or `adb forward tcp:6666 tcp:6666`) and `renef -g <pid>`.
Limits: attach-only (no spawn), one agent per patched APK. All Lua APIs/hooks still work.

### Local mode (`--local`, on-device)
Client + server both on device; UDS transport (no ADB/TCP), works under SELinux enforcing, near-
zero latency. Build: `make deploy-local` (pushes `renef`, `renef_server`, `libagent.so` to
`/data/local/tmp/`). Run on device: `su`; `/data/local/tmp/renef_server &`;
`/data/local/tmp/renef --local -s com.pkg -l /data/local/tmp/hook.lua -w`. **Paths are
device-side.** Combine with `-g` for rootless on-device.

## Hook engines
| Engine | How | Use |
|---|---|---|
| `trampoline` (default) | inline patch at function entry (Capstone) | any address, general purpose |
| `pltgot` | patches PLT/GOT entries | faster, **imported functions only**; great with `caller=` filtering & syscall tracing |

## Build / deploy (host = macOS/Linux, x86_64 or ARM64)
Needs Android NDK r25/r26+, CMake 3.16+, ADB, rooted ARM64 device.
```bash
make setup        # Lua 5.4 + Capstone for Android
make              # client + server + payload (== make all)
make deploy       # push renef_server + .r (payload) to /data/local/tmp
make install      # deploy + port forward
make client       # host client only        make client-android  # on-device client
make renef-strace # standalone tracer        make deploy-local    # on-device bundle
BUILD_MODE=debug make      # debug build      NDK=/path make       # override NDK
```
Client-only builds (no NDK) for Linux/WSL/macOS: `mkdir build && cd build && cmake .. && make`.
Env: `NDK`, `BUILD_MODE`, `ANDROID_SERIAL`, `RENEF_PAYLOAD_PATH` (default `/data/local/tmp/.r`).

## Companion tooling
- **magisk-renef** — Magisk/KernelSU/APatch module; auto-starts `renef_server` on boot (no manual
  ADB). Install ZIP, reboot. Log: `/data/local/tmp/renef_server.log`.
- **r2renef** — Radare2 IO plugin: `r2 renef://spawn/com.pkg` or `renef://attach/<pid>`. r2
  commands (`pd`, `px`, `pdf`, `/x`, `w`) on live memory; renef commands via `:` prefix
  (`:exec`, `:l`, `:watch`, `:ms`, `:md`).
- **Python binding** (`librenef.so`): `from renef import Renef; s = r.spawn("com.pkg")`;
  `s.eval(lua)`, `s.load_script(path)`, `s.hook(lib, off, on_enter=..., on_leave=...)`,
  `s.hook_java(cls, m, sig, ...)`, `s.Module.find/exports/symbols`, `s.Memory.read_u32/...`,
  `s.watch_start(cb)`, context-manager support. Build: `make renef_shared`.
- **Hookshare** (hook.renef.io) — community hook scripts (e.g. universal SSL unpin, 30+ targets).
- **`ai` command** — renef's in-CLI LLM script generator; `ai <prompt> [@file]`. Provider via
  `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` (else Ollama). System prompt = `RENEF_AI_PROMPT.md`.
