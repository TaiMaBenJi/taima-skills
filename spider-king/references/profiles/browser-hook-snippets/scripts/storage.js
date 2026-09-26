// Spider browser-hook profile: filtered Storage writes/removals with restore.
(function () {
  'use strict';

  const CONFIG = { keyIncludes: ['token', 'auth', 'sign', 'session'], logReads: false, logStack: false, maxEvents: 50 };
  const registry = window.__spiderHooks = window.__spiderHooks || {};
  if (registry.storage && registry.storage.restore) registry.storage.restore();
  const proto = window.Storage && Storage.prototype;
  if (!proto) return;
  const original = { setItem: proto.setItem, getItem: proto.getItem, removeItem: proto.removeItem };
  let events = 0;

  function matches(key) {
    const text = String(key || '').toLowerCase();
    return CONFIG.keyIncludes.length === 0 || CONFIG.keyIncludes.some((item) => text.includes(item.toLowerCase()));
  }

  function storageName(storage) {
    try { if (storage === window.localStorage) return 'localStorage'; } catch (_) {}
    try { if (storage === window.sessionStorage) return 'sessionStorage'; } catch (_) {}
    return 'storage';
  }

  function emit(event, storage, key, value) {
    if (events >= CONFIG.maxEvents || !matches(key)) return;
    events += 1;
    console.log('[spider-storage]', JSON.stringify({ target: storageName(storage), event, key: String(key), valueLength: value == null ? 0 : String(value).length }));
    if (CONFIG.logStack && event !== 'get') console.trace('[spider-storage] stack');
  }

  function setItem(key, value) { emit('set', this, key, value); return original.setItem.apply(this, arguments); }
  function getItem(key) { const value = original.getItem.apply(this, arguments); if (CONFIG.logReads) emit('get', this, key, value); return value; }
  function removeItem(key) { emit('remove', this, key, null); return original.removeItem.apply(this, arguments); }

  proto.setItem = setItem;
  proto.getItem = getItem;
  proto.removeItem = removeItem;
  registry.storage = {
    config: CONFIG,
    restore() {
      if (proto.setItem === setItem) proto.setItem = original.setItem;
      if (proto.getItem === getItem) proto.getItem = original.getItem;
      if (proto.removeItem === removeItem) proto.removeItem = original.removeItem;
      delete registry.storage;
    },
  };
  console.log('[spider-hook] storage installed; edit __spiderHooks.storage.config and call .restore() when done');
})();
