# Android Patterns

## Overloads

```js
Java.perform(() => {
  const C = Java.use("com.example.Target");
  for (const o of C.method.overloads) {
    console.log(o.returnType.name, o.argumentTypes.map(t => t.name).join(", "));
  }
});
```

## Constructor

```js
Java.perform(() => {
  const C = Java.use("com.example.Target");
  C.$init.overload("java.lang.String").implementation = function (s) {
    console.log("new Target", s);
    return this.$init(s);
  };
});
```

## Class Loader Probe

```js
Java.perform(() => {
  Java.enumerateClassLoaders({
    onMatch(loader) {
      try {
        const factory = Java.ClassFactory.get(loader);
        factory.use("com.example.Target");
        console.log("found loader", loader);
      } catch (_) {}
    },
    onComplete() {}
  });
});
```

## JNI Bridge

```js
Java.perform(() => {
  const Runtime = Java.use("java.lang.Runtime");
  Runtime.loadLibrary0.implementation = function (loader, lib) {
    console.log("loadLibrary0", lib);
    return this.loadLibrary0(loader, lib);
  };
});
```

After the library is loaded, switch to `frida-native-hooks` and resolve exports/symbols.

## OkHttp Recon

Hook request builders and interceptors to identify request construction before bypassing trust logic. Log URL, method, headers, and call stack when allowed by scope.
