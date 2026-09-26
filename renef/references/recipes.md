# Renef Recipes

Copy-paste-ready, derived from renef's shipped `scripts/examples/`. Adjust class names, signatures,
offsets, and library names to the target. Load with `renef -s com.pkg -l recipe.lua -w`.

---

## 1. SSL pinning bypass — Java (robust, multi-target)

`safe_hook` wraps each hook in `pcall` so a missing class doesn't abort the script.

```lua
__hook_type__ = "trampoline"
print(CYAN .. "=== SSL unpin ===" .. RESET)
local n = 0
local function safe_hook(cls, m, sig, cb, label)
  local ok = pcall(function() hook(cls, m, sig, cb) end)
  if ok then n = n + 1; print(GREEN .. "  [+] " .. label .. RESET)
  else print(YELLOW .. "  [-] " .. label .. " (not found)" .. RESET) end
end

-- Conscrypt TrustManagerImpl.checkServerTrusted (void → skip)
safe_hook("com/android/org/conscrypt/TrustManagerImpl", "checkServerTrusted",
  "([Ljava/security/cert/X509Certificate;Ljava/lang/String;)V",
  { onEnter = function(args) args.skip = true end }, "TrustManagerImpl.checkServerTrusted")

-- TrustManagerImpl.verifyChain returns a List → return the untrusted chain arg unchanged
local saved
safe_hook("com/android/org/conscrypt/TrustManagerImpl", "verifyChain",
  "([Ljava/security/cert/X509Certificate;[B[BLjava/lang/String;Z)Ljava/util/List;",
  { onEnter = function(args) saved = args[2] end,           -- first Java param = untrustedChain
    onLeave = function(retval) if saved then return saved end; return retval.raw end },
  "TrustManagerImpl.verifyChain")

-- OkHttp3 CertificatePinner.check (void → skip)
safe_hook("okhttp3/CertificatePinner", "check", "(Ljava/lang/String;Ljava/util/List;)V",
  { onEnter = function(args) args.skip = true end }, "okhttp3.CertificatePinner.check")

-- Hostname verifier returning boolean → force true
safe_hook("okhttp3/internal/tls/OkHostnameVerifier", "verify",
  "(Ljava/lang/String;Ljavax/net/ssl/SSLSession;)Z",
  { onLeave = function() return 1 end }, "OkHostnameVerifier.verify")

print(string.format("%d SSL hooks installed", n))
```

Replace the app's TrustManagers wholesale (use when per-method hooks aren't enough):
```lua
local EmptyTM = Java.registerClass({
  implements = { "javax/net/ssl/X509TrustManager" },
  methods = { checkClientTrusted=function() end, checkServerTrusted=function() end,
              getAcceptedIssuers=function() return nil end }
})
local arr = Java.array("javax/net/ssl/TrustManager", { EmptyTM })
hook("javax/net/ssl/SSLContext", "init",
  "(Ljavax/net/ssl/KeyManager;[Ljavax/net/ssl/TrustManager;Ljava/security/SecureRandom;)V",
  { onEnter = function(args) args[3] = arr.raw; print("[*] SSLContext TMs replaced") end })
```

> Android 16 changed some Conscrypt signatures; hook both variants and prefer `args.skip = true`
> on void methods to avoid ART stack-walk crashes when hooks nest. Hookshare has a 30+ target script.

---

## 2. SSL pinning bypass — Flutter (libflutter.so, load-time hook)

Flutter bundles BoringSSL; the verify fn isn't exported, so hook by offset and, if the lib isn't
loaded yet, wait for it via `do_dlopen` in the linker.

```lua
local SSL_VERIFY_OFFSET = 0x5dc730   -- ssl_crypto_x509_session_verify_cert_chain; VERSION-SPECIFIC
local installed = false
local function install()
  if installed or not Module.find("libflutter.so") then return installed end
  hook("libflutter.so", SSL_VERIFY_OFFSET, {
    onLeave = function(retval) return 1 end   -- 1 = verified
  })
  installed = true; print("[+] Flutter SSL bypass active"); return true
end

if not install() then
  local linker = Module.find("linker64") and "linker64" or "linker"
  local syms = Module.symbols(linker) or Module.exports(linker)
  for _, s in ipairs(syms or {}) do
    if s.name:find("do_dlopen") then
      hook(linker, s.offset, { onLeave = function() if not installed then install() end end })
      print("[+] Waiting for libflutter.so via " .. linker); break
    end
  end
end
```
Find the offset for your Flutter build: `Memory.search("session_verify", "libflutter.so")`, or
extract `lib/arm64-v8a/libflutter.so` and analyze statically.

---

## 3. SSL pinning bypass — native OpenSSL/BoringSSL (`libssl.so`)

```lua
for _, e in ipairs(Module.exports("libssl.so") or {}) do
  if e.name == "SSL_CTX_set_verify" then
    hook("libssl.so", e.offset, { onEnter = function(args) args[1] = 0 end }) -- SSL_VERIFY_NONE
    print(GREEN .. "[+] SSL_CTX_set_verify neutralized" .. RESET); break
  end
end
```

---

## 3b. WebView SSL pinning bypass (and: calling a method on a raw arg pointer)

WebView pinning is bypassed by making `WebViewClient.onReceivedSslError(view, handler, error)` call
`handler.proceed()`. But `handler` arrives as a **raw pointer** (`args[3]`), and renef has **no
`Java.cast`/`Java.wrap` and no generic `Jni` method-call** — so you can't call `proceed()` on it
directly. The bridge is **`java.lang.reflect.Method.invoke`**: renef marshals a raw integer pointer
as the Object target (verified), so reflection can invoke any instance method on a hook-arg object.

```lua
-- reflection bridge: SslErrorHandler.proceed()
local proceedM, emptyObjs
do
  local clazz = Java.use("java/lang/Class")
    :call("forName", "(Ljava/lang/String;)Ljava/lang/Class;", "android.webkit.SslErrorHandler")
  proceedM = clazz:call("getMethod",
    "(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;", "proceed",
    Java.array("java/lang/Class", {}))           -- empty Class[] = no-arg method
  emptyObjs = Java.array("java/lang/Object", {})
end

hook("android/webkit/WebViewClient", "onReceivedSslError",
  "(Landroid/webkit/WebView;Landroid/webkit/SslErrorHandler;Landroid/net/http/SslError;)V", {
  onEnter = function(args)        -- instance: args[2]=view args[3]=handler args[4]=error
    -- pass the RAW handler pointer (args[3]) as the Object target:
    proceedM:call("invoke", "(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;", args[3], emptyObjs)
    args.skip = true              -- don't run the default cancel / app pinning logic
  end
})
```

Notes:
- Hooking the **base** `android/webkit/WebViewClient` catches a subclass override only if that
  override calls `super.onReceivedSslError(...)`. If it fully overrides without `super`, hook the
  app's **actual subclass** by name (find it in jadx, e.g. `com/app/MyWebViewClient`).
- The reflection pattern generalizes: to call **any** instance method on a raw hook-arg pointer,
  `forName` the class → `getMethod(name, paramClasses[])` → `method:invoke(rawPtr, args[])`.
  This is how you port Frida's `this.method(...)` / `arg.method(...)` calls (renef can't do them directly).

## 4. Root detection bypass (native libc layer)

Closure-local pattern: capture in `onEnter`, decide in `onLeave`.

```lua
__hook_type__ = "trampoline"
local ROOT = { "/su", "magisk", "supersu", "/system/xbin/su", "/system/bin/su", "/data/adb/magisk" }
local function is_root(p) if not p then return false end
  for _, x in ipairs(ROOT) do if p:find(x, 1, true) then return true end end; return false end

local exp = Module.exports("libc.so")
local function hook_named(name, blockval)            -- blockval: what onLeave returns when blocked
  for _, e in ipairs(exp) do if e.name == name then
    local blocked = false
    hook("libc.so", e.offset, {
      onEnter = function(args)
        local ok, p = pcall(function() return Memory.readString(args[0]) end)
        blocked = ok and is_root(p)
        if blocked then print(RED .. "[blocked] " .. name .. ": " .. p .. RESET) end
      end,
      onLeave = function(retval) if blocked then return blockval end; return retval end
    })
    print(GREEN .. "[+] hooked " .. name .. RESET); break
  end end
end

hook_named("open",   -1)   -- ENOENT
hook_named("access", -1)
hook_named("stat",   -1)
hook_named("fopen",   0)   -- NULL
hook_named("system", 127)  -- "command not found" for su-ish commands (refine match in onEnter)

-- Spoof dangerous system properties
for _, e in ipairs(exp) do if e.name == "__system_property_get" then
  hook("libc.so", e.offset, { onEnter = function(args)
    local ok, prop = pcall(function() return Memory.readString(args[0]) end)
    if ok and prop == "ro.debuggable" then Memory.writeString(args[1], "0")
    elseif ok and prop == "ro.build.tags" then Memory.writeString(args[1], "release-keys")
    elseif ok and prop == "ro.build.type" then Memory.writeString(args[1], "user") end
  end }); break
end end
```
For Java-layer checks, hook the app's own method directly:
```lua
hook("com/example/security/RootCheck", "isDeviceRooted", "()Z", { onLeave = function() return 0 end })
```
Tip: for checks that run at startup, launch with `--pause` so these install first.

---

## 5. Crypto key logger

```lua
for _, e in ipairs(Module.exports("libcrypto.so") or {}) do
  if e.name == "AES_set_encrypt_key" then
    hook("libcrypto.so", e.offset, { onEnter = function(args)
      local bits = args[1]; local key = Memory.read(args[0], bits // 8)
      local hex = ""; for i = 1, #key do hex = hex .. string.format("%02x", key:byte(i)) end
      print(RED .. string.format("[AES] %d-bit key: %s", bits, hex) .. RESET)
    end }); break
  end
end
```

---

## 6. Function tracer (with backtrace)

```lua
local lib = "libapp.so"
if not Module.find(lib) then print(RED .. lib .. " not loaded" .. RESET); return end
local count = 0
for i, e in ipairs(Module.exports(lib)) do
  if i > 15 then break end                 -- cap; high-frequency fns add overhead
  hook(lib, e.offset, {
    onEnter = function(args)
      print(CYAN .. string.format("[%s] (0x%x, 0x%x, 0x%x)", e.name, args[0], args[1], args[2]) .. RESET)
      -- print(Thread.backtrace())          -- uncomment to see callers
    end,
    onLeave = function(retval) print(string.format("  └─> 0x%x", retval)); return retval end
  })
  count = count + 1
end
print(GREEN .. count .. " trace hooks" .. RESET)
```

---

## 7. Watch library loads (dlopen)

```lua
local linker = Module.find("linker64") and "linker64" or "linker"
for _, s in ipairs(Module.symbols(linker) or {}) do
  if s.name:find("do_dlopen") then
    hook(linker, s.offset, { onEnter = function(args)
      local p = Memory.readString(args[0]); if p then print("[dlopen] " .. p) end
    end }); break
  end
end
```

---

## 8. Memory scan / patch / cheat

```lua
-- Find an int32 value (little-endian) in memory
local v = 12345
local pat = string.char(v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff)
local hits = Memory.scan(pat)
for i, r in ipairs(hits) do
  print(string.format("[%d] %s + 0x%x (abs 0x%x)", i, r.library, r.offset, r.addr))
end

-- Overwrite the first hit, then "freeze" it (re-write on an interval if you keep the script alive)
if #hits > 0 then Memory.writeU32(hits[1].addr, 999999) end

-- NOP out a branch / patch a function to always-return-1 (ARM64: mov w0,#1 ; ret)
-- mov w0, #1 = 0x52800020 ; ret = 0xD65F03C0
Memory.patch(target_addr, "\x20\x00\x80\x52\xc0\x03\x5f\xd6")
```
CLI equivalents: `ms <hex>`, `msi <hex>` (interactive), `md <addr> <size> -d` (disasm).

---

## 9. Syscall auditing (renef-strace via Lua)

```lua
-- Flag access to sensitive paths
local SENS = { "/proc/", "/sys/", "su", "magisk", "frida", "/data/local/tmp/" }
Syscall.trace("openat", "access", "stat", "readlink", {
  onCall = function(info)
    for _, p in ipairs(SENS) do
      if info.formatted:find(p) then print(RED .. "[SEC] " .. info.formatted .. RESET); return end
    end
  end
})
-- Network capture:  Syscall.trace({ category = "network" })
-- Stop later:       Syscall.stop()
```
Run, then `watch` (output is async). CLI one-shot: `renef-strace -c file` / `renef-strace openat,read,write`.

---

## 10. Java runtime automation (no hook needed)

```lua
local app = Java.use("android/app/ActivityThread")
  :call("currentApplication", "()Landroid/app/Application;")
print("package = " .. app:call("getPackageName", "()Ljava/lang/String;"))

local Build = Java.use("android/os/Build")          -- read static fields via getters/reflection as needed
local sb = Java.use("java/lang/StringBuilder"):new("()V")
sb:call("append", "(Ljava/lang/String;)Ljava/lang/StringBuilder;", "hi")
print(sb:call("toString", "()Ljava/lang/String;"))
```

---

## 11. CTF — hook first export, force a return value

```lua
local lib = "liba0x9.so"
if not Module.find(lib) then print("[!] lib not loaded — trigger it in-app, then reload"); return end
local exports = Module.exports(lib)
local f = exports[1]
print("hooking " .. f.name)
hook(lib, f.offset, {
  onEnter = function() print("[called] " .. f.name) end,
  onLeave = function(retval) print("orig=" .. tostring(retval)); return 1337 end
})
```
Lazy-loaded libs: trigger the relevant app feature first, then reload the script.
