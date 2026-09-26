# Renef Lua API Reference

> **Provenance.** The runtime API surface here — `Module`, `Memory`, `hook`, `Java`, `Jni`/`JNI`,
> `Thread`, `File`, `OS`, `Syscall`, the reflection bridge, arg layout, and "no `Memory.writeString`"
> — was **enumerated on a real device** (run `probe.lua` to re-confirm on your build; builds differ).
> `KCov`, gadget/local mode, the Python binding, and r2renef are **doc-derived and not re-verified
> here** — treat them as such. When in doubt, probe.

Lua 5.4. All of this runs **inside the target process**. Globals available without `require`:
`Module`, `Memory`, `hook`, `Java`, `Jni`/`JNI`, `Thread`, `File`, `Syscall`, `OS`, `KCov`,
`console`, `print`, and color constants `RED GREEN YELLOW BLUE MAGENTA CYAN WHITE RESET`.

Script-level directive: set `__hook_type__ = "trampoline"` (or `"pltgot"`) at the top of a script
to choose the hook engine for that script.

---

## Module — inspect loaded libraries & symbols

| Call | Returns |
|---|---|
| `Module.find(name)` | base address (int) or `nil`. Partial names OK (`"flutter"`). |
| `Module.list()` | newline-separated **string** of all loaded `.so` + addresses (not a table). |
| `Module.exports(name)` | table of `{name, offset}` from `.dynsym` (public symbols). Always available. |
| `Module.symbols(name)` | table of `{name, offset}` from `.symtab` (all incl. internal/static). `nil` if stripped. |

- `offset` is relative to the library base. Absolute = `Module.find(lib) + offset`.
- C++ names are mangled — match with `sym.name:find("do_dlopen")`.
- `linker64` is usually **not** stripped → `Module.symbols("linker64")` exposes `do_dlopen`,
  `call_constructors`, etc. Use this to hook library loads.
- Release libs are usually stripped → `symbols()` returns `nil`; fall back to `exports()` or
  `Memory.search`. `symbols()` can return thousands of entries — cache the result.

```lua
local base = Module.find("libc.so")
for _, s in ipairs(Module.exports("libc.so")) do
  if s.name == "malloc" then print(string.format("malloc @ 0x%x (abs 0x%x)", s.offset, base + s.offset)) end
end
```

---

## Memory — search / read / write / patch

### Search
- `Memory.search(pattern [, lib])` / `Memory.scan(...)` (alias). String **or** hex pattern,
  IDA-style `??` wildcards. Optional `lib` limits scope (faster; needed for big apps — scan is
  capped ~50MB / ~1000 matches otherwise).
- Returns table of `{library, addr, offset, hex, ascii}`. `addr` is absolute; `offset` from base.
- `Memory.dump(results)` pretty-prints a result table.

```lua
Memory.search("native")                 -- string
Memory.search("FD 7B ?? A9")            -- ARM64 prologue, wildcard byte
Memory.search("C0 03 5F D6", "libc.so") -- ret, scoped to one lib
```

Common ARM64 patterns: prologue `FD 7B ?? A9` · ret `C0 03 5F D6` · NOP `1F 20 03 D5` ·
bl `?? ?? ?? 94` (or `97`) · b `?? ?? ?? 14`.

### Read
| Call | Notes |
|---|---|
| `Memory.read(addr, size)` | raw bytes as Lua string (max 1MB) |
| `Memory.readU8/U16/U32/U64(addr)` | unsigned int |
| `Memory.readStr(addr [, maxLen])` | null-terminated string (default 256) |
| `Memory.readString(addr [, maxLen])` | alias; `nil` if addr is 0 (max 1024) |

### Write / patch
| Call | Notes |
|---|---|
| `Memory.write(addr, bytes)` | raw bytes; returns `true`. Write a **string** as bytes: `Memory.write(addr, "text\0")` |
| `Memory.writeU8/U16/U32/U64(addr, val)` | unsigned int |
| `Memory.patch(addr, bytes)` | patches code, **auto-handles mprotect**; returns `true` or `false, err` |

> **`Memory.writeString` does NOT exist** (verified at runtime: `type(Memory.writeString)==nil`).
> Some old example scripts call it — they fail. Use `Memory.write(addr, str.."\0")` instead.

The hook/patch engine writes via `/proc/self/mem` (pwrite) — bypasses SELinux/seccomp, W^X-clean,
invisible in `/proc/self/maps`; falls back to `mprotect` if needed.

### Hexdump
`hexdump(target [, length])` (global; also `Memory.hexdump`). Returns a **string** — `print()` it.
`target` may be: integer address (reads `length` bytes), binary string, userdata (Java `.raw`
pointer), or a byte table `{0x41,0x42}`. Default length 256, max 64KB.

```lua
print(hexdump(addr, 64))
print(hexdump(Memory.read(addr, 256)))
print(hexdump(args[1], 64))     -- a pointer arg inside a hook
```

---

## hook() — native and Java hooking

### Native: `hook(library, offset, callbacks)`
```lua
hook("libc.so", 0x12340, {
  onEnter = function(args)
    -- args[0..7] = x0..x7. Assign to modify a register arg.
    print(string.format("size=0x%x", args[0]))
    args[0] = 0x200
  end,
  onLeave = function(retval)
    return retval + 0x100   -- replaces x0; return retval to keep
  end,
  caller = "libnative.so"   -- optional: only hook calls FROM this lib → PLT/GOT mode
})
```
- Callbacks: `onEnter(args)`, `onLeave(retval)`, both optional. Optional `caller` (string or
  table of strings) restricts to specific callers and switches to **PLT/GOT** hooking (patches the
  caller's GOT only). Without `caller` → **trampoline** hook (patches target directly, any address).
- Modify args by assignment; modify return by `return`-ing from `onLeave`.

### Java: `hook(class, method, signature, callbacks)`
Android 10–16. Class uses `/` separators. Signature is mandatory JNI form `(Params)Ret`.

```lua
hook("com/example/MainActivity", "getSecret", "(Ljava/lang/String;)Ljava/lang/String;", {
  onEnter = function(args)
    -- args[0]=ArtMethod*  args[1]=this(instance) OR first param(static)  args[2..]=params
    local input = Jni.getStringUTF(args[2])
    print("input=" .. tostring(input))
    -- args.skip = true            -- skip original entirely
    -- args[2] = newPtr            -- modify a parameter
  end,
  onLeave = function(retval)
    -- retval.raw   = raw x0 (int);  retval.value = decoded string (String returns only)
    return Jni.newStringUTF("HOOKED")
  end
})
```

`onEnter` `args` extra keys: `args.class`, `args.method`, `args.signature`, `args.isStatic`,
`args.skip` (set `true` to skip original — essential for void methods that throw, like
`checkServerTrusted`; avoids ART stack-walk crashes on nested hooks, esp. Android 16).

`onLeave` return options for Java:
| Return | Effect |
|---|---|
| `nil` / nothing | unchanged |
| integer | sets x0 (e.g. `return 1` true, `return 0` false) |
| boolean | sets x0 to 1/0 |
| `Jni.newStringUTF("x")` | returns a new Java String |
| `{__jni_type="string", value="x"}` | new Java String |
| `{__jni_type="int", value=N}` / `{__jni_type="boolean", value=true}` | typed return |
| `retval.raw` | pass original through (common when not changing it) |

> **Verifying hooks:** the `hooks` CLI command lists only **native trampoline** hooks. **Java hooks
> never show up there** (you can have working Java hooks and still see `Active hooks: 0`). Verify
> Java hooks by behavior (print in a callback + `watch`), not by the `hooks` count.

### Jni namespace (use inside hook callbacks)
| Call | Purpose |
|---|---|
| `Jni.newStringUTF(str)` | create Java String, returns raw pointer (use as onLeave return) |
| `Jni.getStringUTF(ref)` | read Java String content → Lua string (or `nil`) |
| `Jni.getStringLength(ref)` | length |
| `Jni.deleteGlobalRef(ref)` | free a global ref |

> Naming note: both `Jni.newStringUTF(s)` and `JNI.string(s)` exist at runtime (verified — both are
> functions; `Jni` and `JNI` are both tables). Prefer the documented `Jni.newStringUTF`.

### JNI signature quick table
`V` void · `Z` boolean · `B` byte · `C` char · `S` short · `I` int · `J` long · `F` float ·
`D` double · `Lpkg/Cls;` object · `[T` array. Method = `(params)ret`.
Examples: `()V` · `(II)I` · `(Ljava/lang/String;)Ljava/lang/String;` · `([IZ)V` ·
`(Ljava/lang/String;I)Ljava/lang/Object;`.

---

## Java — call/instantiate classes at runtime (`Java.use` etc.)

```lua
local System = Java.use("java/lang/System")          -- class wrapper (FindClass + app ClassLoader fallback)
local t = System:call("currentTimeMillis", "()J")    -- static call

local SB = Java.use("java/lang/StringBuilder")
local sb = SB:new("()V")                              -- constructor (default "()V")
sb:call("append", "(Ljava/lang/String;)Ljava/lang/StringBuilder;", "Hello")
print(sb:call("toString", "()Ljava/lang/String;"))

local app = Java.use("android/app/ActivityThread")
  :call("currentApplication", "()Landroid/app/Application;")
print(app:call("getPackageName", "()Ljava/lang/String;"))
```

- `wrapper:call(method, sig, ...)` static · `wrapper:new(sig, ...)` instance ·
  `instance:call(method, sig, ...)` instance method.
- `instance.raw` → raw ART `mirror::Object*` int (pass Java objects as hook args). Only valid
  while alive; don't cache across GC.
- Type conversion is automatic (Lua number/boolean/string ↔ Java primitives/String; other objects
  → `JavaInstance` userdata; `null` → `nil`).
- `Java.registerClass({implements={"a/b/Iface"}, methods={name=function(...) end}})` → implement a
  Java interface in Lua (DEX `Proxy` bridge). Returns a `JavaInstance`. (Some examples also pass a
  `name=` field.) Method callbacks receive Java args directly (strings auto-converted, other
  objects as raw int pointers).
- `Java.array(type, {elem, ...})` → `jobjectArray` as `JavaInstance`; use `.raw` to pass it.

> **Calling a method on a RAW object pointer (e.g. a hook arg / `this`).** renef has **no
> `Java.cast`/`Java.wrap`** and **no generic `Jni` method-call**, so you cannot call an instance
> method directly on the raw integer you get from a hook arg. Bridge via reflection — renef marshals
> a raw int as the Object target of `Method.invoke` (verified):
> ```lua
> local Class  = Java.use("java/lang/Class")
> local clazz  = Class:call("forName","(Ljava/lang/String;)Ljava/lang/Class;","pkg.Cls")
> local m      = clazz:call("getMethod","(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;","meth", Java.array("java/lang/Class",{}))
> m:call("invoke","(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;", rawPtrFromHookArg, Java.array("java/lang/Object",{}))
> ```
> This is how you port Frida's `this.method()` / `arg.method()`. `Class.forName` returns the Class
> object as a `JavaInstance`, so reflection (`getMethod`/`getDeclaredField`/`invoke`) is fully usable.

```lua
local EmptyTM = Java.registerClass({
  implements = { "javax/net/ssl/X509TrustManager" },
  methods = {
    checkClientTrusted = function() end,
    checkServerTrusted = function() end,
    getAcceptedIssuers = function() return nil end,
  }
})
local arr = Java.array("javax/net/ssl/TrustManager", { EmptyTM })
hook("javax/net/ssl/SSLContext", "init",
  "(Ljavax/net/ssl/KeyManager;[Ljavax/net/ssl/TrustManager;Ljava/security/SecureRandom;)V", {
  onEnter = function(args) args[3] = arr.raw end
})
```

---

## Thread — backtrace & tid

- `Thread.backtrace([fp])` → array of frame tables `{index, pc, symbol?, module?, path?, base?,
  offset?}`. Inside a hook callback it **auto-starts from the hooked function's caller** (skips
  hook infra). PAC bits are stripped automatically (Android 12+). `print(Thread.backtrace())`
  formats nicely; iterate for filtering. `symbol` is `nil` for stripped libs — use `module+offset`.
- `Thread.id()` → current tid (`gettid`).

```lua
hook("libc.so", fopen_off, { onEnter = function(args)
  print("fopen(" .. tostring(Memory.readString(args[0])) .. ")")
  print(Thread.backtrace())
end })
```

---

## File — filesystem in the target's context

- `File.exists(path)` → bool
- `File.read(path)` → contents (max ~40KB) or `nil`
- `File.readlink(path)` → link target or `nil`
- `File.fdpath(fd)` → path behind an fd (reads `/proc/self/fd/<fd>`) — great for resolving fds in
  `read`/`write` hooks.
- `File.write(path, data)` → write data to a file (present at runtime; undocumented upstream).

---

## Syscall — PLT/GOT-based syscall tracing (no ptrace)

```lua
Syscall.trace("openat", "read", "write", "close")     -- by name
Syscall.trace({ category = "file" })                  -- file|network|memory|process|ipc
Syscall.trace("openat", { caller = "libnative.so" })  -- filter by caller lib
Syscall.trace("openat", {
  onCall = function(info)   -- info: name, tid, formatted, args[] (read/write), skip, retval
    print(info.formatted)
    info.args[2] = 0x1234         -- mutate an arg
    -- info.skip = true; info.retval = 0   -- skip kernel, fake return
  end,
  onReturn = function(info) -- info: name, tid, retval, errno_str(<0)
    if info.retval < 0 then return 0 end   -- override return
  end
})
Syscall.traceAll()                 -- everything (noisy)
Syscall.untrace("openat", ...)     -- stop some; returns count
Syscall.stop()                     -- stop all, restore GOT
Syscall.list([category]) ; Syscall.active()
```
Categories: **file** (openat/open/close/read/write/lseek/pread64/pwrite64/fstat/stat/access/
readlink/rename/unlink/mkdir/chmod) · **network** (socket/connect/bind/listen/accept4/sendto/
recvfrom) · **memory** (mmap/munmap/mprotect) · **process** (fork/execve/kill/getpid/getuid/
exit_group) · **ipc** (ioctl/fcntl/dup/dup2/pipe). Output is async — pair with `watch`.

---

## OS — process/signal/dir utilities

- `OS.getpid()` · `OS.kill(pid, sig)` (sig 0 = existence check) · `OS.tgkill(tgid, tid, sig)` ·
  `OS.listdir(path)` → table of names (dotfiles excluded), e.g. `/proc/self/task` for threads.

---

## KCov — kernel coverage (coverage-guided fuzzing)

Requires `CONFIG_KCOV=y` (not on stock Android), root + debugfs.
`KCov.open([entries])` → cov. Methods: `cov:enable()` / `:disable()` (thread-local) ·
`:count()` · `:collect([max])` (PC table) · `:reset()` · `:edges()` (AFL-style edge hashes) ·
`:diff(old_edges)` (count new edges) · `:close()`. Resolve PCs via `/proc/kallsyms`.

---

## Console

`print(...)`, `console.log(msg)` (same). Color usage: `print(GREEN .. "ok" .. RESET)`.
Use `string.format` for hex: `string.format("0x%x", n)`.
