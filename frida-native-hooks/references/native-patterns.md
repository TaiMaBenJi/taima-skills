# Native Patterns

## Export Hook

```js
const mod = Process.getModuleByName("libtarget.so");
const fn = mod.getExportByName("target");
Interceptor.attach(fn, {
  onEnter(args) {
    console.log("arg0", args[0]);
  },
  onLeave(retval) {
    console.log("ret", retval);
  }
});
```

## Import Hook

```js
for (const imp of Process.getModuleByName("app").enumerateImports()) {
  if (imp.name === "strcmp") console.log(imp);
}
```

## Pattern Scan

```js
const m = Process.getModuleByName("libtarget.so");
Memory.scan(m.base, m.size, "13 37 ?? ??", {
  onMatch(address) { console.log("match", address); },
  onError(reason) { console.log("scan error", reason); },
  onComplete() { console.log("scan done"); }
});
```

## Backtrace

```js
console.log(Thread.backtrace(this.context, Backtracer.ACCURATE)
  .map(DebugSymbol.fromAddress)
  .join("\n"));
```

## Replacement

```js
const openPtr = Process.getModuleByName("libc.so").getExportByName("open");
const open = new NativeFunction(openPtr, "int", ["pointer", "int"]);
Interceptor.replace(openPtr, new NativeCallback((pathPtr, flags) => {
  const path = pathPtr.readUtf8String();
  console.log("open", path);
  return open(pathPtr, flags);
}, "int", ["pointer", "int"]));
```

## Performance

- Avoid expensive stringification in hot hooks.
- Sample or gate logs when functions fire frequently.
- Use `CModule` or `replaceFast()` only after a normal hook proves the target and overhead problem.
