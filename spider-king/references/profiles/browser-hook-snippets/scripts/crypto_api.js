// Spider browser-hook profile: filtered WebCrypto/CryptoJS metadata with restore.
(function () {
  'use strict';

  const CONFIG = { subtleMethods: ['digest', 'sign', 'encrypt', 'decrypt'], includeRandom: true, logStack: false, maxEvents: 50 };
  const registry = window.__spiderHooks = window.__spiderHooks || {};
  if (registry.cryptoApi && registry.cryptoApi.restore) registry.cryptoApi.restore();
  const subtleProto = window.SubtleCrypto && SubtleCrypto.prototype;
  const cryptoProto = window.Crypto && Crypto.prototype;
  const cryptoJs = window.CryptoJS;
  const subtleOriginals = new Map();
  const cryptoJsOriginals = new Map();
  let originalGetRandomValues = null;
  let wrappedGetRandomValues = null;
  let events = 0;

  function observe(callback) {
    try { callback(); } catch (_) {}
  }

  function ownDataValue(value, name) {
    if ((typeof value !== 'object' && typeof value !== 'function') || value === null) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, name);
    return descriptor && Object.prototype.hasOwnProperty.call(descriptor, 'value') ? descriptor.value : undefined;
  }

  function safeAlgorithm(value) {
    let candidate = typeof value === 'string' ? value : ownDataValue(value, 'name');
    if (candidate === undefined) candidate = ownDataValue(ownDataValue(value, 'hash'), 'name');
    if (typeof candidate !== 'string' || candidate.length > 32) return 'other';
    const normalized = candidate.toUpperCase();
    const allowed = [
      'AES-CBC', 'AES-CTR', 'AES-GCM', 'AES-KW', 'ECDH', 'ECDSA', 'HKDF', 'HMAC',
      'PBKDF2', 'RSA-OAEP', 'RSA-PSS', 'RSASSA-PKCS1-V1_5', 'SHA-1', 'SHA-256',
      'SHA-384', 'SHA-512',
    ];
    return allowed.includes(normalized) ? normalized : 'other';
  }

  function sizeOf(value) {
    if (value == null) return 0;
    if (typeof value === 'string') return value.length;
    const sigBytes = ownDataValue(value, 'sigBytes');
    if (Number.isFinite(sigBytes)) return sigBytes;
    const ciphertext = ownDataValue(value, 'ciphertext');
    const ciphertextBytes = ownDataValue(ciphertext, 'sigBytes');
    if (Number.isFinite(ciphertextBytes)) return ciphertextBytes;
    if (typeof ArrayBuffer !== 'undefined') {
      if (value instanceof ArrayBuffer) return value.byteLength;
      if (ArrayBuffer.isView(value)) return value.byteLength;
    }
    return null;
  }

  function typeOf(value) {
    if (value === null) return 'null';
    if (typeof ArrayBuffer !== 'undefined') {
      if (value instanceof ArrayBuffer) return 'ArrayBuffer';
      if (ArrayBuffer.isView(value)) return 'ArrayBufferView';
    }
    return typeof value;
  }

  function emit(label, meta) {
    if (events >= CONFIG.maxEvents) return;
    events += 1;
    console.log(label, JSON.stringify(meta));
    if (CONFIG.logStack) console.trace(label + ' stack');
  }

  if (subtleProto) {
    for (const method of CONFIG.subtleMethods) {
      const original = subtleProto[method];
      if (typeof original !== 'function') continue;
      function wrapped() {
        const input = arguments[arguments.length - 1];
        observe(() => {
          const algorithm = safeAlgorithm(arguments[0]);
          emit('[spider-webcrypto]', { method, algorithm, inputType: typeOf(input), inputLength: sizeOf(input) });
        });
        const promise = original.apply(this, arguments);
        observe(() => {
          Promise.prototype.then.call(
            promise,
            (result) => observe(() => emit('[spider-webcrypto-result]', { method, outputType: typeOf(result), outputLength: sizeOf(result) })),
            () => {},
          );
        });
        return promise;
      }
      subtleOriginals.set(method, { original, wrapped });
      subtleProto[method] = wrapped;
    }
  }

  if (CONFIG.includeRandom && cryptoProto && typeof cryptoProto.getRandomValues === 'function') {
    originalGetRandomValues = cryptoProto.getRandomValues;
    wrappedGetRandomValues = function (array) {
      observe(() => emit('[spider-random]', { method: 'getRandomValues', arrayType: typeOf(array), length: sizeOf(array) }));
      return originalGetRandomValues.apply(this, arguments);
    };
    cryptoProto.getRandomValues = wrappedGetRandomValues;
  }

  if (cryptoJs) {
    for (const name of ['MD5', 'SHA1', 'SHA256', 'SHA512', 'HmacSHA256']) {
      const original = cryptoJs[name];
      if (typeof original !== 'function') continue;
      function wrapped() {
        observe(() => emit('[spider-cryptojs]', { method: name, inputType: typeOf(arguments[0]), inputLength: sizeOf(arguments[0]) }));
        const result = original.apply(this, arguments);
        observe(() => emit('[spider-cryptojs-result]', { method: name, outputType: typeOf(result), outputLength: sizeOf(result) }));
        return result;
      }
      cryptoJsOriginals.set(name, { owner: cryptoJs, method: name, original, wrapped });
      cryptoJs[name] = wrapped;
    }

    for (const family of ['AES', 'DES', 'TripleDES', 'RC4']) {
      const owner = cryptoJs[family];
      if (!owner || (typeof owner !== 'object' && typeof owner !== 'function')) continue;
      for (const operation of ['encrypt', 'decrypt']) {
        const original = owner[operation];
        if (typeof original !== 'function') continue;
        function wrapped() {
          observe(() => emit('[spider-cryptojs]', {
            method: family + '.' + operation,
            inputType: typeOf(arguments[0]),
            inputLength: sizeOf(arguments[0]),
          }));
          const result = original.apply(this, arguments);
          observe(() => emit('[spider-cryptojs-result]', {
            method: family + '.' + operation,
            outputType: typeOf(result),
            outputLength: sizeOf(result),
          }));
          return result;
        }
        const key = family + '.' + operation;
        cryptoJsOriginals.set(key, { owner, method: operation, original, wrapped });
        owner[operation] = wrapped;
      }
    }
  }

  registry.cryptoApi = {
    config: CONFIG,
    restore() {
      for (const [method, entry] of subtleOriginals) if (subtleProto[method] === entry.wrapped) subtleProto[method] = entry.original;
      if (originalGetRandomValues && cryptoProto.getRandomValues === wrappedGetRandomValues) cryptoProto.getRandomValues = originalGetRandomValues;
      for (const entry of cryptoJsOriginals.values()) {
        if (entry.owner[entry.method] === entry.wrapped) entry.owner[entry.method] = entry.original;
      }
      delete registry.cryptoApi;
    },
  };
  console.log('[spider-hook] cryptoApi installed; edit __spiderHooks.cryptoApi.config and call .restore() when done');
})();
