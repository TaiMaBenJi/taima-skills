# iOS Patterns

## Enumerate Objective-C Classes

```js
if (ObjC.available) {
  Object.keys(ObjC.classes)
    .filter(name => name.includes("Session") || name.includes("Trust"))
    .forEach(name => console.log(name));
}
```

## Hook Method

```js
const method = ObjC.classes.Target["- isEnabled"];
Interceptor.attach(method.implementation, {
  onLeave(retval) {
    console.log("isEnabled ->", retval);
  }
});
```

## SecTrust Recon

```js
const sec = Process.getModuleByName("Security");
const evaluate = sec.findExportByName("SecTrustEvaluateWithError");
if (evaluate) {
  Interceptor.attach(evaluate, {
    onEnter(args) { console.log("SecTrustEvaluateWithError", args[0]); },
    onLeave(retval) { console.log("trust ret", retval); }
  });
}
```

## Swift Symbols

```js
for (const m of Process.enumerateModules()) {
  for (const s of m.enumerateSymbols()) {
    if (s.name.includes("TargetName")) console.log(m.name, s.name, s.address);
  }
}
```

## Rootless Checks

- Verify host tools, device Frida package, and jailbreak/bootstrap compatibility.
- Prefer official Frida packages for the device setup.
- If attach fails but process listing works, test a minimal script before loading a large agent.
