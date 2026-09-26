/**
 * env_core.js - optional hand-written environment patch engine.
 *
 * This is adapted from the backup env-patch framework and kept as an
 * advanced branch. The profile's default path remains
 * scripts/env-diagnose.js + env/ modules.
 */

const __env__ = (() => {
  const errors = [];
  const undefinedGets = Object.create(null);
  const functionCalls = Object.create(null);
  const successfulGets = Object.create(null);
  const proxyCache = new WeakMap();

  const originalToString = Function.prototype.toString;
  const originalToStringDescriptor = Object.getOwnPropertyDescriptor(Function.prototype, 'toString');
  const nativeFunctions = new WeakSet();
  const originalGlobals = new Map();
  let nativeToStringInstalled = false;

  function nativeToString() {
    if (nativeFunctions.has(this)) {
      const name = this.name || '';
      return `function ${name}() { [native code] }`;
    }
    return originalToString.call(this);
  }

  Object.defineProperty(nativeToString, 'name', {
    value: 'toString',
    writable: false,
    enumerable: false,
    configurable: true,
  });
  nativeFunctions.add(nativeToString);

  function installNativeToString() {
    if (nativeToStringInstalled) return;
    Object.defineProperty(Function.prototype, 'toString', {
      value: nativeToString,
      writable: true,
      enumerable: false,
      configurable: true,
    });
    nativeToStringInstalled = true;
  }

  function setFuncNative(fn, name, len) {
    if (typeof fn !== 'function') return fn;
    if (typeof name === 'number') {
      len = name;
      name = undefined;
    }
    if (typeof name === 'string') {
      Object.defineProperty(fn, 'name', {
        value: name,
        writable: false,
        enumerable: false,
        configurable: true,
      });
    }
    if (typeof len === 'number') {
      Object.defineProperty(fn, 'length', {
        value: len,
        writable: false,
        enumerable: false,
        configurable: true,
      });
    }
    nativeFunctions.add(fn);
    return fn;
  }

  function setObjNative(obj, name) {
    if (!obj || (typeof obj !== 'object' && typeof obj !== 'function')) return obj;
    Object.defineProperty(obj, Symbol.toStringTag, {
      value: name,
      writable: false,
      enumerable: false,
      configurable: true,
    });
    return obj;
  }

  function getNativeProto(ctorName, attrs = {}, opts = {}) {
    const Ctor = setFuncNative(function () {
      throw new TypeError('Illegal constructor');
    }, ctorName, opts.length || 0);

    Object.defineProperty(Ctor, 'prototype', {
      writable: false,
      enumerable: false,
      configurable: false,
    });
    Object.defineProperty(Ctor.prototype, 'constructor', {
      value: Ctor,
      writable: false,
      enumerable: false,
      configurable: true,
    });

    const instance = Object.create(Ctor.prototype);
    setObjNative(instance, ctorName);

    for (const [key, val] of Object.entries(attrs)) {
      if (val && typeof val === 'object' && ('get' in val || 'set' in val || 'value' in val)) {
        Object.defineProperty(instance, key, val);
      } else {
        Object.defineProperty(instance, key, {
          value: val,
          writable: true,
          enumerable: true,
          configurable: true,
        });
      }
    }

    return [Ctor, instance];
  }

  function setProtoAccessor(ctor, propName, getter, setter, enumerable = true) {
    const desc = {
      get: getter,
      enumerable,
      configurable: true,
    };
    if (setter) desc.set = setter;
    Object.defineProperty(ctor.prototype, propName, desc);
  }

  function wrapFunc(obj, method, callback) {
    const original = obj[method];
    const wrapped = function (...args) {
      return callback.call(this, original && original.bind(this), ...args);
    };
    setFuncNative(wrapped, method, original ? original.length : 0);
    obj[method] = wrapped;
    return wrapped;
  }

  function summarize(value) {
    if (value === undefined) return 'undefined';
    if (value === null) return 'null';
    const type = typeof value;
    if (type === 'function') return '[Function]';
    if (type === 'string') return `[String length=${value.length}]`;
    if (type === 'number') return '[Number]';
    if (type === 'boolean') return '[Boolean]';
    if (type === 'bigint') return '[BigInt]';
    if (type === 'symbol') return '[Symbol]';
    if (Array.isArray(value)) return `Array(${value.length})`;
    return '[Object]';
  }

  function recordUndefined(path) {
    undefinedGets[path] = (undefinedGets[path] || 0) + 1;
  }

  function recordSuccess(path) {
    successfulGets[path] = (successfulGets[path] || 0) + 1;
  }

  function recordCall(path, args) {
    if (!functionCalls[path]) functionCalls[path] = { count: 0, args: [] };
    const entry = functionCalls[path];
    entry.count += 1;
    if (entry.args.length < 3) {
      const sample = args.map(summarize).join(', ');
      if (!entry.args.includes(sample)) entry.args.push(sample);
    }
  }

  function recordError(path, operation, err) {
    let message = summarize(err);
    if (err instanceof Error) {
      const descriptor = Object.getOwnPropertyDescriptor(err, 'message');
      const length = descriptor && typeof descriptor.value === 'string' ? descriptor.value.length : null;
      message = length === null ? '[Error details redacted]' : `[Error messageLength=${length}]`;
    }
    const key = `${path}|${operation}|${message}`;
    if (!errors.some((item) => `${item.path}|${item.operation}|${item.message}` === key)) {
      errors.push({ path, operation, message });
    }
  }

  const skipProps = new Set([
    'constructor', 'prototype', '__proto__', 'toJSON', 'hasOwnProperty',
    'isPrototypeOf', 'propertyIsEnumerable', 'valueOf', 'inspect', 'then',
    'asymmetricMatch', 'nodeType', '$$typeof', '@@__IMMUTABLE_ITERABLE__@@',
  ]);

  const noRecurseCtors = new Set([
    'ArrayBuffer', 'SharedArrayBuffer', 'DataView', 'Int8Array', 'Uint8Array',
    'Uint8ClampedArray', 'Int16Array', 'Uint16Array', 'Int32Array', 'Uint32Array',
    'Float32Array', 'Float64Array', 'BigInt64Array', 'BigUint64Array', 'Map',
    'Set', 'WeakMap', 'WeakSet', 'Date', 'RegExp', 'Promise', 'Error',
    'TypeError', 'RangeError', 'ReferenceError', 'SyntaxError',
  ]);

  function shouldProxy(obj) {
    if (obj === null || obj === undefined) return false;
    const type = typeof obj;
    if (type !== 'object' && type !== 'function') return false;
    try {
      const name = obj.constructor && obj.constructor.name;
      if (name && noRecurseCtors.has(name)) return false;
    } catch (_) {}
    return true;
  }

  function monitor(target, name, config = {}) {
    const {
      getLog, setLog, log,
      getKeys = [], setKeys = [], keys = [],
      getCb, setCb, cb,
      getParse = (key, value) => value,
      setParse = (key, value) => value,
      handles = {},
    } = config;

    return new Proxy(target, {
      get(obj, prop, receiver) {
        if (typeof prop === 'symbol') return Reflect.get(obj, prop, receiver);
        if (getLog || log) console.log(`[monitor] ${name}.${prop} GET`);
        if (getKeys.includes(prop) || keys.includes(prop)) debugger;
        (getCb || cb)?.(prop, name);
        return getParse(prop, Reflect.get(obj, prop, receiver), obj);
      },
      set(obj, prop, value, receiver) {
        if (typeof prop === 'symbol') return Reflect.set(obj, prop, value, receiver);
        if (setLog || log) console.log(`[monitor] ${name}.${prop} SET`, summarize(value));
        if (setKeys.includes(prop) || keys.includes(prop)) debugger;
        (setCb || cb)?.(prop, value, name);
        return Reflect.set(obj, prop, setParse(prop, value, obj), receiver);
      },
      ...handles,
    });
  }

  function createProxy(target, name, depth = 0) {
    if (depth > 8) return target;
    if (!shouldProxy(target)) return target;
    if (proxyCache.has(target)) return proxyCache.get(target);

    const proxy = new Proxy(target, {
      get(obj, prop, receiver) {
        if (typeof prop === 'symbol') return Reflect.get(obj, prop, receiver);
        if (skipProps.has(prop)) return Reflect.get(obj, prop, receiver);

        const chain = `${name}.${prop}`;
        let value;
        try {
          value = Reflect.get(obj, prop, receiver);
        } catch (err) {
          recordError(chain, 'get', err);
          return undefined;
        }

        if (value === undefined) recordUndefined(chain);
        else recordSuccess(chain);

        if (typeof value === 'function') {
          const needsBind = obj instanceof Map || obj instanceof Set || obj instanceof Date || obj instanceof RegExp || obj instanceof Promise || ArrayBuffer.isView(obj);
          const wrappedFn = function (...args) {
            recordCall(chain, args);
            try {
              const thisArg = this === proxy ? obj : this;
              const result = needsBind ? value.apply(obj, args) : value.apply(thisArg, args);
              return shouldProxy(result) ? createProxy(result, `${chain}()`, depth + 1) : result;
            } catch (err) {
              recordError(chain, 'call', err);
              throw err;
            }
          };
          setFuncNative(wrappedFn, prop);
          return wrappedFn;
        }

        return shouldProxy(value) ? createProxy(value, chain, depth + 1) : value;
      },
      set(obj, prop, value, receiver) {
        try {
          return Reflect.set(obj, prop, value, receiver);
        } catch (err) {
          recordError(`${name}.${String(prop)}`, 'set', err);
          return false;
        }
      },
      has: (obj, prop) => Reflect.has(obj, prop),
      deleteProperty: (obj, prop) => Reflect.deleteProperty(obj, prop),
      getOwnPropertyDescriptor: (obj, prop) => Reflect.getOwnPropertyDescriptor(obj, prop),
      defineProperty: (obj, prop, desc) => Reflect.defineProperty(obj, prop, desc),
      ownKeys: (obj) => Reflect.ownKeys(obj),
      getPrototypeOf: (obj) => Reflect.getPrototypeOf(obj),
      ...(typeof target === 'function' ? {
        apply(fn, thisArg, args) {
          recordCall(name, args);
          try {
            const result = Reflect.apply(fn, thisArg, args);
            return shouldProxy(result) ? createProxy(result, `${name}()`, depth + 1) : result;
          } catch (err) {
            recordError(name, 'call', err);
            throw err;
          }
        },
        construct(fn, args, newTarget) {
          recordCall(`new ${name}`, args);
          try {
            const result = Reflect.construct(fn, args, newTarget);
            return shouldProxy(result) ? createProxy(result, `new ${name}()`, depth + 1) : result;
          } catch (err) {
            recordError(`new ${name}`, 'construct', err);
            throw err;
          }
        },
      } : {}),
    });

    proxyCache.set(target, proxy);
    return proxy;
  }

  function init(config = {}) {
    if (globalThis.process?.env?.SPIDER_EXTERNAL_SANDBOX_CONFIRMED !== '1') {
      throw new Error(
        'env_core executes target code in the host Node realm. Run it in an external disposable sandbox and set SPIDER_EXTERNAL_SANDBOX_CONFIRMED=1 only inside that boundary.'
      );
    }
    installNativeToString();

    for (const key of ['process', 'Buffer', '__dirname', '__filename', 'setImmediate', 'clearImmediate']) {
      if (key in globalThis) {
        try {
          if (!originalGlobals.has(key)) {
            originalGlobals.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
          }
          Object.defineProperty(globalThis, key, {
            value: undefined,
            writable: false,
            enumerable: false,
            configurable: true,
          });
        } catch (_) {}
      }
    }

    const globals = {};
    if (config.window) {
      globals.window = config.window;
      globals.self = config.window;
      globals.top = config.window;
      globals.parent = config.window;
    }
    if (config.document) globals.document = config.document;
    if (config.navigator) globals.navigator = config.navigator;
    if (config.location) globals.location = config.location;

    for (const [key, value] of Object.entries(globals)) {
      if (!originalGlobals.has(key)) {
        originalGlobals.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
      }
      Object.defineProperty(globalThis, key, {
        value,
        writable: true,
        configurable: true,
        enumerable: true,
      });
    }
  }

  function report() {
    const lines = [];
    const errorCount = errors.length;
    const undefCount = Object.keys(undefinedGets).length;
    const callCount = Object.keys(functionCalls).length;
    const okCount = Object.keys(successfulGets).length;

    lines.push('');
    lines.push('========== ENV PATCH REPORT ==========');
    lines.push('');
    if (errorCount) {
      lines.push(`[ERRORS] (${errorCount}) - must fix:`);
      for (const item of errors) lines.push(`  ${item.path} [${item.operation}] -> ${item.message}`);
      lines.push('');
    }
    if (undefCount) {
      lines.push(`[UNDEFINED] (${undefCount}) - likely need patching:`);
      for (const [path, count] of Object.entries(undefinedGets).sort((a, b) => b[1] - a[1])) {
        lines.push(`  ${path}  (x${count})`);
      }
      lines.push('');
    }
    if (callCount) {
      lines.push(`[CALLS] (${callCount}) - function calls observed:`);
      for (const [path, info] of Object.entries(functionCalls).sort((a, b) => b[1].count - a[1].count)) {
        const args = info.args.length ? `  args: [${info.args.join('] [')}]` : '';
        lines.push(`  ${path}  (x${info.count})${args}`);
      }
      lines.push('');
    }
    lines.push(`Summary: ${errorCount} errors, ${undefCount} undefined, ${callCount} calls, ${okCount} ok (hidden)`);
    lines.push('=======================================');
    lines.push('');

    console.log(lines.join('\n'));
    return { errors, undefined: undefinedGets, calls: functionCalls };
  }

  function reset() {
    errors.length = 0;
    for (const key of Object.keys(undefinedGets)) delete undefinedGets[key];
    for (const key of Object.keys(functionCalls)) delete functionCalls[key];
    for (const key of Object.keys(successfulGets)) delete successfulGets[key];
  }

  function restore() {
    if (nativeToStringInstalled) {
      Object.defineProperty(Function.prototype, 'toString', originalToStringDescriptor);
      nativeToStringInstalled = false;
    }
    for (const [key, descriptor] of originalGlobals) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
    originalGlobals.clear();
  }

  return {
    setFuncNative,
    setObjNative,
    getNativeProto,
    setProtoAccessor,
    wrapFunc,
    monitor,
    createProxy,
    init,
    report,
    reset,
    restore,
    _reset: reset,
  };
})();

export const setFuncNative = __env__.setFuncNative;
export const setObjNative = __env__.setObjNative;
export const getNativeProto = __env__.getNativeProto;
export const setProtoAccessor = __env__.setProtoAccessor;
export const wrapFunc = __env__.wrapFunc;
export const monitor = __env__.monitor;
export const createProxy = __env__.createProxy;
export const init = __env__.init;
export const report = __env__.report;
export const reset = __env__.reset;
export const restore = __env__.restore;
export const _reset = __env__._reset;

export default __env__;
