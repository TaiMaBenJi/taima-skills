# Translating from other tools → Renef

You already know how to instrument apps. This maps the tool you came from onto renef's syntax.
Renef itself doesn't care where you came from — it's Lua 5.4, Android ARM64, hook engine +
raw `Memory` API. Translate concepts, then apply the Syntax Contract from `SKILL.md`.

---

# Frida (JavaScript) → Renef (Lua)

| | Frida | Renef |
|---|---|---|
| Hook target | absolute `ptr(addr)` | **`(library, offset)`** |
| Modify return | `retval.replace(v)` | **`return v`** from `onLeave` |
| Java class name | `com.example.Class` | **`com/example/Class`** (JNI `/`) |
| Java overloads | auto / `.overload()` | **explicit JNI signature always** |
| `Java.perform()` | required | **not needed** |
| Skip Java original | don't call `this.method()` | **`args.skip = true`** |
| Memory API | OOP `ptr(x).readU32()` | functional `Memory.readU32(x)` |
| File access | `recv`/`send` proxy | built-in `File` API |
| Gadget | separate binary + config | built-in `-g <pid>` |

### Module / Process
| Frida | Renef |
|---|---|
| `Module.findBaseAddress("libc.so")` | `Module.find("libc.so")` (int, not NativePointer) |
| `Module.findExportByName("libc.so","open")` | loop `Module.exports("libc.so")` → `name=="open"` → `.offset` |
| `Module.enumerateExports("libc.so")` | `Module.exports("libc.so")` → `{name, offset}` |
| `Module.enumerateSymbols("libc.so")` | `Module.symbols("libc.so")` (`.symtab`) |
| `Process.enumerateModules()` | `Module.list()` (returns a **string**) |

```javascript
// Frida
Interceptor.attach(Module.findExportByName("libc.so","open"), {
  onEnter: function(a){ console.log("open(" + a[0].readUtf8String() + ")"); },
  onLeave: function(r){ console.log("fd=" + r.toInt32()); }
});
```
```lua
-- Renef
for _, s in ipairs(Module.exports("libc.so")) do
  if s.name == "open" then
    hook("libc.so", s.offset, {
      onEnter = function(args) print("open(" .. tostring(Memory.readString(args[0])) .. ")") end,
      onLeave = function(retval) print("fd=" .. retval); return retval end
    }); break
  end
end
```

### Native hooks
| Frida | Renef |
|---|---|
| `Interceptor.attach(ptr(a), cb)` | `hook("lib.so", offset, cb)` |
| `Interceptor.detachAll()` | `unhook all` (CLI) |
| `args[0] = ptr(0x200)` | `args[0] = 0x200` |
| `retval.replace(ptr(1))` | `return 1` (from `onLeave`) |
| `args[0].readUtf8String()` | `Memory.readString(args[0])` |
| `Thread.backtrace(this.context, ...)` | `Thread.backtrace()` (auto caller context) |

### Java hooks
| Frida | Renef |
|---|---|
| `Java.perform(fn)` | (drop it) |
| `cls.method.implementation = fn` | `hook("class","method","sig", cb)` |
| call original `this.method()` | automatic unless `args.skip = true` |
| `Java.use("p.C").$new("s")` | `Jni.newStringUTF("s")` in hooks / `Java.use("p/C"):new(sig,...)` |
| arg auto-convert | `Jni.getStringUTF(args[2])` (manual) |
| `this.method(...)` / `someArg.method(...)` | **reflection bridge** — see below (renef can't call a method on a raw pointer directly) |

**Calling a method on `this` or an arg object (no direct equivalent).** In Frida you just write
`this.proceed()` or `handler.proceed()`. renef hook args are raw integers and there is no
`Java.cast`/`Java.wrap`, so bridge via `java.lang.reflect.Method.invoke` (renef marshals the raw int
as the Object target — verified):

```lua
-- Frida: onReceivedSslError(view, handler, error){ handler.proceed(); }
local clazz = Java.use("java/lang/Class")
  :call("forName","(Ljava/lang/String;)Ljava/lang/Class;","android.webkit.SslErrorHandler")
local proceedM = clazz:call("getMethod",
  "(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;","proceed", Java.array("java/lang/Class",{}))
hook("android/webkit/WebViewClient","onReceivedSslError",
  "(Landroid/webkit/WebView;Landroid/webkit/SslErrorHandler;Landroid/net/http/SslError;)V",{
  onEnter=function(args)
    proceedM:call("invoke","(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;", args[3], Java.array("java/lang/Object",{}))
    args.skip=true
  end})
```

```javascript
Java.perform(function(){
  Java.use("com.example.MainActivity").getSecret.implementation = function(input){
    return "HOOKED!";
  };
});
```
```lua
hook("com/example/MainActivity", "getSecret", "(Ljava/lang/String;)Ljava/lang/String;", {
  onLeave = function(retval) return Jni.newStringUTF("HOOKED!") end
})
```
Remember Java arg layout: `args[0]`=ArtMethod*, `args[1]`=this/first-param, `args[2..]`=params.

### Java class interaction
| Frida | Renef |
|---|---|
| `Java.use("p.C")` | `Java.use("p/C")` |
| `cls.$new(args)` | `wrapper:new(sig, args)` |
| `cls.staticM(args)` | `wrapper:call("staticM", sig, args)` |
| `inst.m(args)` | `inst:call("m", sig, args)` |
| `Java.registerClass({...})` | `Java.registerClass({...})` |
| `Java.array("p.C",[..])` | `Java.array("p/C",{..})` → pass `.raw` |

### Memory
| Frida | Renef |
|---|---|
| `Memory.scan(base,size,pat,cb)` | `Memory.search("pat"[, "lib.so"])` (all `.so` by default; `??` wildcards) |
| `ptr(a).readU32()` / `readUtf8String()` | `Memory.readU32(a)` / `Memory.readString(a)` |
| `ptr(a).readByteArray(n)` | `Memory.read(a, n)` (Lua string) |
| `ptr(a).writeU32(v)` / `writeByteArray(b)` | `Memory.writeU32(a, v)` / `Memory.write(a, b)` |
| `Memory.patchCode(a,n,fn)` | `Memory.patch(a, bytes)` (auto mprotect) |
| `base.add(0x1234)` | `base + 0x1234` |
| `hexdump(p,{length})` | `hexdump(target[, length])` → string, `print()` it |

### Output / CLI
`console.log(x)` → `print(x)`; `` `v=${x}` `` → `string.format("v=0x%x", x)`.
`frida -U -f app -l s.js` → `renef -s app -l s.lua`; `frida -U -p N` → `renef -a N`;
`--no-pause` is renef's default (use `--pause` to gate startup).

---

# GameGuardian (`gg.*`) → Renef

**Critical:** GameGuardian scripts will **not** run in renef. GameGuardian is a standalone app with
its own `gg.*` Lua API and an interactive *scan → refine → freeze → edit-list* UI. Renef has **no
`gg` namespace and no built-in scan/refine/freeze loop** — it injects into the process and gives
you a raw `Memory` API. To port a GG cheat you **rebuild the loop in renef Lua**: keep the result
set as a Lua table, refine by re-reading each address, freeze by re-writing (ideally inside a hot
hook).

### Concept mapping
| GameGuardian | Renef equivalent |
|---|---|
| `gg.searchNumber("100", gg.TYPE_DWORD)` | `Memory.scan(u32le(100))` → keep `r.addr` list |
| refine / "search again" within results | filter the kept list: `Memory.readU32(addr) == newval` |
| `gg.getResults(n)` / `gg.getResultCount()` | your Lua table + `#list` |
| `gg.editAll("999", gg.TYPE_DWORD)` | `for _,a in ipairs(list) do Memory.writeU32(a, 999) end` |
| freeze value | re-write on each call of a hooked hot function (see below) |
| pointer/offset chain | `readU64`/`readU32` walk (helper below) |
| address list / saved offsets | a Lua table `{ {addr=, name=}, ... }` |
| `gg.TYPE_BYTE/WORD/DWORD/QWORD` | `readU8/16/32/64`, `writeU8/16/32/64` |
| `gg.TYPE_FLOAT/DOUBLE` | `string.unpack("<f"/"<d", Memory.read(a, 4/8))` / `string.pack` to write |
| `gg.alert/prompt/choice/toast` | no UI — use `print()` / CLI prompts; logic stays in the script |
| `gg.getRangesList` / region filters | scope scans with the `lib` arg: `Memory.scan(pat, "libUE4.so")` |
| `gg.PROCESS / gg.getTargetInfo` | renef is already inside the target; use `Module.list()` / `OS.getpid()` |

### Reusable value scanner (reconstructs the GG loop)
```lua
-- value helpers
local function u32le(v) return string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff) end

-- 1) initial scan → list of absolute addresses (optionally scope to a library)
local function scan_u32(value, lib)
  local hits = {}
  for _, r in ipairs(Memory.scan(u32le(value), lib) or {}) do hits[#hits+1] = r.addr end
  return hits
end

-- 2) refine ("next scan"): keep only addresses whose CURRENT value == newvalue
local function refine_u32(addrs, newvalue)
  local kept = {}
  for _, a in ipairs(addrs) do
    if Memory.readU32(a) == newvalue then kept[#kept+1] = a end
  end
  return kept
end

-- 3) edit all
local function edit_u32(addrs, value)
  for _, a in ipairs(addrs) do Memory.writeU32(a, value) end
end

-- Example: classic GG flow — find 100, do damage in-game, refine to 95, then set to 999999
local hits = scan_u32(100, nil)          -- gg.searchNumber("100", DWORD)
print("#hits=" .. #hits)
-- (trigger the value change in the app)
hits = refine_u32(hits, 95)              -- refine
print("#after refine=" .. #hits)
if #hits <= 50 then edit_u32(hits, 999999) end   -- gg.editAll
```

### Float values (GG TYPE_FLOAT)
```lua
local function read_f32(a) return (string.unpack("<f", Memory.read(a, 4))) end
local function write_f32(a, v) Memory.write(a, string.pack("<f", v)) end
```

### Freeze a value (renef has no timer/`gg.setValues` loop)
The idiomatic renef freeze re-writes the address inside a **frequently called function hook** (e.g.
the game's update/render tick), so the value is forced every frame:
```lua
local target_addr = hits[1]
-- hook a hot function in the game lib; re-assert the value on every call
hook("libgame.so", UPDATE_FN_OFFSET, {
  onEnter = function() Memory.writeU32(target_addr, 999999) end
})
```
Simpler (non-frozen) option: just call `edit_u32(hits, value)` again on demand. Avoid
`while true do ... end` — a busy loop blocks renef's script thread.

### Pointer / offset chain (GG "pointer search")
```lua
-- base + [o1] + [o2] + ... ; reads 64-bit pointers, returns FINAL address
local function ptr_chain(base, offsets)
  local p = base
  for i = 1, #offsets - 1 do p = Memory.readU64(p + offsets[i]) end
  return p + offsets[#offsets]
end
local hp = ptr_chain(Module.find("libgame.so") + 0x12345, { 0x10, 0x28, 0x0 })
print(string.format("HP @ 0x%x = %d", hp, Memory.readU32(hp)))
```

### Code patches (god-mode / no-recoil via instruction edits)
GG cheaters often NOP a "subtract health" instruction. In renef, find it and patch:
```lua
-- NOP one ARM64 instruction (4 bytes) ; or force a function to return 1:
Memory.patch(addr, "\x1f\x20\x03\xd5")                      -- NOP
Memory.patch(fn_addr, "\x20\x00\x80\x52\xc0\x03\x5f\xd6")   -- mov w0,#1 ; ret
```
Use `md <addr> 64 -d` (CLI) to disassemble and confirm before patching.

---

# General game-hacking Lua

If you're used to writing game-cheat Lua (GG or otherwise), the mindset is identical — find an
address, read/write/freeze it, or patch the code path. Renef just exposes that through
`Memory.scan/readU*/writeU*/patch` plus a **hook engine** GG doesn't have: prefer hooking the
function that computes a value (stable across updates) over scanning a raw address (brittle). For
anything Java-side (scores stored in Kotlin/Java, anti-cheat), use Java hooks instead of memory
scanning. Resolve offsets by symbol/pattern (`references/recipes.md` §8) so cheats survive app
updates.
