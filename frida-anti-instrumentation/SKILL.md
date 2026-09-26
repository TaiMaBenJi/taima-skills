---
name: frida-anti-instrumentation
description: Analyze and bypass anti-Frida, anti-debugging, root or jailbreak checks, emulator checks, ptrace, port scans, module scans, and integrity checks.
---

# Frida Anti-Instrumentation

Use this skill when the app exits, hides behavior, blocks attach, or detects Frida/root/jailbreak/emulator/debugging.

## Diagnosis Order

1. Prove whether failure happens before or after Frida attaches.
2. Use spawn mode for early checks.
3. Log exits, process checks, file checks, property checks, and native anti-debug calls.
4. Identify the specific detection before bypassing it.
5. Keep only narrow hooks that change the detected condition.

## Android Boundaries

```js
Java.perform(() => {
  const Runtime = Java.use("java.lang.Runtime");
  Runtime.exec.overload("java.lang.String").implementation = function (cmd) {
    console.log("Runtime.exec", cmd);
    return this.exec(cmd);
  };
});
```

Common Java surfaces: `File.exists`, `SystemProperties.get`, `Build.*`, package manager queries, shell command execution, debugger checks, emulator properties.

## Native Boundaries

```js
for (const name of ["open", "access", "stat", "ptrace", "prctl", "connect"]) {
  try {
    const f = Module.getGlobalExportByName(name);
    Interceptor.attach(f, { onEnter() { console.log(name); } });
  } catch (_) {}
}
```

Common native surfaces: `/proc`, `maps`, `task`, `frida`, `gum-js-loop`, TCP port scans, `ptrace`, `prctl`, `syscall`, `dlopen`, checksum functions.

## iOS Boundaries

Look for file checks, URL scheme checks, `fork`, `ptrace`, `sysctl`, `csops`, dyld image scans, suspicious library names, and jailbreak path lists.

## Verification

- The app reaches the previously blocked screen or behavior.
- Logs show which detection hook fired.
- Removing the hook restores the failure.
- The final bypass does not mask unrelated errors or crash paths.

## References

- Frida JavaScript API: https://frida.re/docs/javascript-api/
- Frida CodeShare: https://codeshare.frida.re/
- OWASP MASTG Frida Android: https://mas.owasp.org/MASTG/tools/android/MASTG-TOOL-0001/
- OWASP MASTG Frida iOS: https://mas.owasp.org/MASTG/tools/ios/MASTG-TOOL-0039/
