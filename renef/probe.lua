-- probe.lua — renef capability probe. RUN THIS FIRST on any new target/build.
-- It measures the actual API surface and behavior of *your* renef instead of
-- trusting docs (builds differ). Load it and read the report:
--
--   renef -s <package> -l probe.lua          (plain spawn; this script hooks nothing hot)
--
-- Everything is wrapped so one failure never aborts the rest (renef otherwise
-- reports a bare "ERROR: Lua execution failed" and stops). Report any surprises
-- back to the skill (see CONTRIBUTING).

local function line() print(string.rep("-", 56)) end
local function ok(b) return b and "yes" or "NO" end

print("================ renef probe ================")

-- 1) API surface: what actually exists on THIS build -------------------------
local function keys(t, name)
  if type(t) ~= "table" then print(string.format("%-10s = %s", name, type(t))); return end
  local ks = {}
  for k, v in pairs(t) do ks[#ks + 1] = k .. "(" .. type(v) .. ")" end
  table.sort(ks)
  print(name .. " {" .. #ks .. "}: " .. table.concat(ks, ", "))
end
line(); print("[1] API surface")
keys(Java, "Java"); keys(Jni, "Jni"); keys(JNI, "JNI")
keys(Memory, "Memory"); keys(Module, "Module")
keys(Thread, "Thread"); keys(File, "File"); keys(OS, "OS"); keys(Syscall, "Syscall")
print("globals: hook=" .. type(hook) .. " print=" .. type(print) ..
      " GREEN=" .. type(GREEN) .. " RESET=" .. type(RESET))
print("Memory.writeString exists? " .. ok(type(Memory) == "table" and type(Memory.writeString) == "function")
      .. "   (expected: NO — use Memory.write(a, s..'\\0'))")

-- 2) Error recovery: prove pcall surfaces the real message --------------------
line(); print("[2] error recovery (pcall recovers what renef hides)")
local _, err = pcall(function() this_is_missing_xyz(1) end)
print("pcall(runtime err) -> " .. tostring(err))
local f, lerr = load("local x = =")
print("load(syntax err)  -> " .. tostring(lerr) .. "  (f=" .. tostring(f) .. ")")

-- 3) Modules ------------------------------------------------------------------
line(); print("[3] modules")
print("libc.so base = " .. tostring(Module.find("libc.so")))
local n = 0
for _ in tostring(Module.list()):gmatch("[^\n]+") do n = n + 1 end
print("loaded module count = " .. n)

-- 4) Reflection bridge: call an instance method on a RAW pointer --------------
-- (safe — hooks nothing)
line(); print("[4] reflection bridge (call method on a raw object pointer)")
local refl_ok, refl = pcall(function()
  local sb = Java.use("java/lang/StringBuilder"):new("()V")
  sb:call("append", "(Ljava/lang/String;)Ljava/lang/StringBuilder;", "PROBE")
  local raw = sb.raw                       -- an integer (like a hook arg)
  local clazz = Java.use("java/lang/Class")
    :call("forName", "(Ljava/lang/String;)Ljava/lang/Class;", "java.lang.StringBuilder")
  local m = clazz:call("getMethod",
    "(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;", "toString",
    Java.array("java/lang/Class", {}))
  return m:call("invoke", "(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;",
    raw, Java.array("java/lang/Object", {}))   -- pass RAW int as the Object target
end)
print("invoke on raw pointer -> ok=" .. ok(refl_ok) .. " result=" .. tostring(refl) ..
      "   (expected: PROBE -> you CAN call methods on raw arg pointers via reflection)")

-- 5) Notes --------------------------------------------------------------------
line(); print("[5] notes")
print("- The 'hooks' CLI command lists only NATIVE trampolines; Java hooks never appear there.")
print("- Verify a hook fires by print()-ing in a callback + 'watch' while you exercise the app.")
print("- Don't hook hot fns (open/read/write/system/popen/do_dlopen) while the app runs (race/crash).")

-- 6) Static vs instance arg layout (LAST — installing a hook can race) --------
-- Uses a rarely-called static method so hooking it won't collide with app
-- startup. If this section aborts the script, that itself confirms the
-- hot-hook race; everything above already printed.
line(); print("[6] arg layout: hook static Integer.toOctalString(I), then call it")
local s1, s2 = "?", "?"
local hooked = pcall(function()
  hook("java/lang/Integer", "toOctalString", "(I)Ljava/lang/String;",
    { onEnter = function(args) s1 = tostring(args[1]); s2 = tostring(args[2]) end })
end)
print("hook installed? " .. ok(hooked))
pcall(function() Java.use("java/lang/Integer"):call("toOctalString", "(I)Ljava/lang/String;", 4242) end)
print("STATIC first param: args[1]=" .. s1 .. "  args[2]=" .. s2 ..
      "   (expected args[1]=4242 -> static first param = args[1]; instance methods shift by 1)")
print("================ probe done =================")
