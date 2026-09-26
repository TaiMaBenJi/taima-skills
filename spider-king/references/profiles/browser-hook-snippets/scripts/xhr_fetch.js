// Spider browser-hook profile: filtered XHR/fetch observation with restore.
(function () {
  'use strict';

  const CONFIG = {
    urlIncludes: ['/api/'],
    headerIncludes: ['sign', 'token', 'auth'],
    maxEvents: 50,
    logStack: false,
    observeResponse: false,
  };
  const registry = window.__spiderHooks = window.__spiderHooks || {};
  if (registry.xhrFetch && registry.xhrFetch.restore) registry.xhrFetch.restore();

  const original = {
    open: XMLHttpRequest.prototype.open,
    send: XMLHttpRequest.prototype.send,
    setRequestHeader: XMLHttpRequest.prototype.setRequestHeader,
    fetch: window.fetch,
  };
  const xhrState = new WeakMap();
  let events = 0;

  function includesAny(value, filters) {
    if (typeof value !== 'string') return filters.length === 0;
    const text = value.toLowerCase();
    return filters.length === 0 || filters.some((item) => text.includes(item.toLowerCase()));
  }

  function allowUrl(url) {
    return includesAny(url, CONFIG.urlIncludes);
  }

  function summarizeUrl(value) {
    if (typeof value !== 'string') return '';
    const text = value;
    try {
      if (typeof URL === 'function') {
        const base = typeof location !== 'undefined' ? location.href : 'https://spider.invalid/';
        const parsed = new URL(text, base);
        return parsed.origin === 'https://spider.invalid' ? parsed.pathname : parsed.origin + parsed.pathname;
      }
    } catch (_) {}
    return text.split(/[?#]/, 1)[0];
  }

  function sizeOf(value) {
    if (value == null) return 0;
    if (typeof value === 'string') return value.length;
    if (typeof ArrayBuffer !== 'undefined') {
      if (value instanceof ArrayBuffer) return value.byteLength;
      if (ArrayBuffer.isView(value)) return value.byteLength;
    }
    if (typeof Blob !== 'undefined' && value instanceof Blob) return value.size;
    return null;
  }

  function ownDataValue(object, name) {
    if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
    try {
      const descriptor = Object.getOwnPropertyDescriptor(object, name);
      return descriptor && Object.prototype.hasOwnProperty.call(descriptor, 'value') ? descriptor.value : undefined;
    } catch (_) {
      return undefined;
    }
  }

  function typeOf(value) {
    if (value === null) return 'null';
    if (typeof ArrayBuffer !== 'undefined') {
      if (value instanceof ArrayBuffer) return 'ArrayBuffer';
      if (ArrayBuffer.isView(value)) return 'ArrayBufferView';
    }
    if (typeof Blob !== 'undefined' && value instanceof Blob) return 'Blob';
    return typeof value;
  }

  function summarizeHeaders(headers) {
    const result = [];
    if (!headers) return result;
    try {
      if (typeof Headers !== 'undefined' && headers instanceof Headers) {
        headers.forEach((value, name) => {
          if (includesAny(name, CONFIG.headerIncludes)) result.push({ name, valueLength: typeof value === 'string' ? value.length : null });
        });
      } else if (Array.isArray(headers)) {
        for (const pair of headers) {
          if (!Array.isArray(pair) || typeof pair[0] !== 'string') continue;
          if (includesAny(pair[0], CONFIG.headerIncludes)) result.push({ name: pair[0], valueLength: typeof pair[1] === 'string' ? pair[1].length : null });
        }
      } else if (Object.getPrototypeOf(headers) === Object.prototype || Object.getPrototypeOf(headers) === null) {
        for (const name of Object.keys(headers)) {
          const value = ownDataValue(headers, name);
          if (includesAny(name, CONFIG.headerIncludes)) result.push({ name, valueLength: typeof value === 'string' ? value.length : null });
        }
      }
    } catch (_) {}
    return result;
  }

  function emit(label, meta) {
    if (events >= CONFIG.maxEvents) return;
    events += 1;
    console.log(label, JSON.stringify(meta));
    if (CONFIG.logStack) console.trace(label + ' stack');
  }

  function open(method, url) {
    const result = original.open.apply(this, arguments);
    xhrState.set(this, {
      method: typeof method === 'string' ? method : '?',
      url: typeof url === 'string' ? url : '',
      headers: [],
    });
    return result;
  }

  function setRequestHeader(name, value) {
    const result = original.setRequestHeader.apply(this, arguments);
    const state = xhrState.get(this);
    if (state && typeof name === 'string' && includesAny(name, CONFIG.headerIncludes)) {
      state.headers.push({ name, valueLength: typeof value === 'string' ? value.length : null });
    }
    return result;
  }

  function send(body) {
    const state = xhrState.get(this) || { method: '?', url: '', headers: [] };
    if (allowUrl(state.url)) {
      emit('[spider-xhr-send]', {
        target: 'xhr', event: 'send', method: state.method,
        url: summarizeUrl(state.url), headers: state.headers,
        bodyType: typeOf(body), bodyLength: sizeOf(body),
      });
      this.addEventListener('load', function () {
        let responseLength = 0;
        try {
          if (!this.responseType || this.responseType === 'text') responseLength = String(this.responseText || '').length;
          else responseLength = this.response && (this.response.byteLength || this.response.size || this.response.length) || 0;
        } catch (_) {}
        emit('[spider-xhr-response]', {
          target: 'xhr', event: 'response', method: state.method, url: summarizeUrl(state.url),
          status: this.status, responseType: this.responseType || 'text', responseLength,
        });
      }, { once: true });
    }
    return original.send.apply(this, arguments);
  }

  function fetchHook(input, init) {
    const promise = original.fetch.apply(this, arguments);
    const requestInput = typeof Request !== 'undefined' && input instanceof Request ? input : null;
    const url = typeof input === 'string' ? input : (requestInput ? requestInput.url : '');
    const initMethod = ownDataValue(init, 'method');
    const method = typeof initMethod === 'string' ? initMethod : (requestInput && typeof requestInput.method === 'string' ? requestInput.method : 'GET');
    const initHeaders = ownDataValue(init, 'headers');
    const initBody = ownDataValue(init, 'body');
    if (allowUrl(url)) {
      emit('[spider-fetch-send]', {
        target: 'fetch', event: 'send', method, url: summarizeUrl(url),
        headers: summarizeHeaders(initHeaders || (requestInput ? requestInput.headers : undefined)),
        bodyType: typeOf(initBody),
        bodyLength: sizeOf(initBody),
      });
    }
    if (CONFIG.observeResponse && promise && typeof promise.then === 'function') {
      promise.then(
        (response) => {
          if (allowUrl(url)) emit('[spider-fetch-response]', { target: 'fetch', event: 'response', method, url: summarizeUrl(url), status: response && response.status });
        },
        () => {},
      );
    }
    return promise;
  }

  XMLHttpRequest.prototype.open = open;
  XMLHttpRequest.prototype.setRequestHeader = setRequestHeader;
  XMLHttpRequest.prototype.send = send;
  window.fetch = fetchHook;

  registry.xhrFetch = {
    config: CONFIG,
    restore() {
      if (XMLHttpRequest.prototype.open === open) XMLHttpRequest.prototype.open = original.open;
      if (XMLHttpRequest.prototype.send === send) XMLHttpRequest.prototype.send = original.send;
      if (XMLHttpRequest.prototype.setRequestHeader === setRequestHeader) XMLHttpRequest.prototype.setRequestHeader = original.setRequestHeader;
      if (window.fetch === fetchHook) window.fetch = original.fetch;
      delete registry.xhrFetch;
    },
  };
  console.log('[spider-hook] xhrFetch installed; response observation is off by default because it changes Promise handled-state; edit config and call .restore() when done');
})();
