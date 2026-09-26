/*
 * Generic Frida hook helper for routing plaintext crypto/request data through
 * scripts/frida_burp_crypto_bridge.py.
 *
 * Copy this file into the task workspace and place bridgeEdit(...) at the
 * authorized hook point: before encryption/signing for requests, and after
 * decryption/parsing for responses. Keep target-specific hooks outside the
 * reusable skill.
 */

'use strict';

const Bridge = (function () {
  const CFG = {
    enabled: true,
    timeoutMs: 120000,
    maxLog: 1200,
  };
  let JavaString = null;
  let AtomicInteger = null;
  let counter = null;

  function init() {
    Java.perform(function () {
      JavaString = Java.use('java.lang.String');
      AtomicInteger = Java.use('java.util.concurrent.atomic.AtomicInteger');
      counter = AtomicInteger.$new(0);
    });
  }

  function nextId(prefix) {
    try {
      return prefix + '-' + counter.incrementAndGet();
    } catch (_) {
      return prefix + '-' + Date.now() + '-' + Math.floor(Math.random() * 100000);
    }
  }

  function bytesToText(bytes) {
    if (bytes === null || bytes === undefined) return '';
    try {
      return JavaString.$new(bytes, 'UTF-8').toString();
    } catch (_) {
      try {
        return JavaString.$new(bytes).toString();
      } catch (_) {
        return '<non-utf8-bytes len=' + bytes.length + '>';
      }
    }
  }

  function textToBytes(text) {
    return JavaString.$new(String(text)).getBytes('UTF-8');
  }

  function compact(text) {
    const value = String(text === null || text === undefined ? '' : text);
    if (value.length <= CFG.maxLog) return value;
    return value.slice(0, CFG.maxLog) + '...<truncated len=' + value.length + '>';
  }

  function bridgeEdit(kind, body, meta) {
    const itemId = (meta && meta.id) || nextId(kind === 'response' ? 'resp' : 'req');
    const original = String(body === null || body === undefined ? '' : body);
    console.log('[crypto-bridge] ' + kind + ' id=' + itemId + ' body=' + compact(original));
    send({ kind: kind, id: itemId, body: original, meta: meta || {} });
    if (!CFG.enabled) return original;

    let edited = null;
    let matched = false;
    recv(function (message) {
      if (!message || message.id !== itemId) return;
      if (message.kind === 'edit-' + kind || message.type === 'edit-' + kind) {
        edited = message.body !== undefined ? message.body : message.payload;
        matched = true;
      }
    }).wait(CFG.timeoutMs);
    if (!matched) {
      console.log('[crypto-bridge] no edit returned for id=' + itemId + ', keeping original');
      return original;
    }
    console.log('[crypto-bridge] edited ' + kind + ' id=' + itemId + ' len=' + String(edited).length);
    return String(edited);
  }

  function bridgeEditBytes(kind, bytes, meta) {
    return textToBytes(bridgeEdit(kind, bytesToText(bytes), meta));
  }

  init();
  return {
    bytesToText: bytesToText,
    textToBytes: textToBytes,
    bridgeEdit: bridgeEdit,
    bridgeEditBytes: bridgeEditBytes,
  };
})();

/*
 * Example shape for a target-specific request hook:
 *
 * Java.perform(function () {
 *   const Target = Java.use('com.example.crypto.RequestEncryptor');
 *   Target.encrypt.overload('java.lang.String').implementation = function (plain) {
 *     const editedPlain = Bridge.bridgeEdit('request', plain, {
 *       className: 'com.example.crypto.RequestEncryptor',
 *       methodName: 'encrypt',
 *     });
 *     return this.encrypt(editedPlain);
 *   };
 * });
 */
