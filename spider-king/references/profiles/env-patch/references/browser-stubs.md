# Browser Stub Snippets

按诊断报告中出现的 `undefinedPaths`、`ERRORS` 或 `env_core.js` 报告按需取用。不要一次性把本文件所有存根都塞进项目。

以下代码假设：

```javascript
import env from './env_core.js';
```

## Contents

- [document 基础](#document-基础)
- [createElement 最小实现](#createelement-最小实现)
- [navigator 基础](#navigator-基础)
- [location 基础](#location-基础)
- [storage](#storage)
- [Canvas + WebGL 起点](#canvas-webgl-起点)

## document 基础

```javascript
const [Document, fakeDocument] = env.getNativeProto('HTMLDocument', {});

let COOKIE = '';
const PAGE_URL = 'https://example.com/';
const DOMAIN = 'example.com';

Object.defineProperties(fakeDocument, {
  cookie: { get() { return COOKIE; }, set(v) { COOKIE = v; }, enumerable: true, configurable: true },
  domain: { get() { return DOMAIN; }, enumerable: true, configurable: true },
  URL: { get() { return PAGE_URL; }, enumerable: true, configurable: true },
  referrer: { get() { return ''; }, enumerable: true, configurable: true },
  title: { get() { return ''; }, set() {}, enumerable: true, configurable: true },
  characterSet: { get() { return 'UTF-8'; }, enumerable: true, configurable: true },
  readyState: { get() { return 'complete'; }, enumerable: true, configurable: true },
  hidden: { get() { return false; }, enumerable: true, configurable: true },
  visibilityState: { get() { return 'visible'; }, enumerable: true, configurable: true },
});

const fakeHead = { appendChild(c) { return c; }, removeChild(c) { return c; }, insertBefore(c) { return c; } };
const fakeBody = { appendChild(c) { return c; }, removeChild(c) { return c; }, insertBefore(c) { return c; } };
env.setObjNative(fakeHead, 'HTMLHeadElement');
env.setObjNative(fakeBody, 'HTMLBodyElement');

fakeDocument.head = fakeHead;
fakeDocument.body = fakeBody;
fakeDocument.documentElement = { style: {}, appendChild(c) { return c; } };

fakeDocument.getElementById = env.setFuncNative(function getElementById() { return null; }, 'getElementById', 1);
fakeDocument.getElementsByTagName = env.setFuncNative(function getElementsByTagName(tag) {
  tag = String(tag || '').toLowerCase();
  if (tag === 'head') return [fakeDocument.head];
  if (tag === 'body') return [fakeDocument.body];
  return [];
}, 'getElementsByTagName', 1);
fakeDocument.querySelector = env.setFuncNative(function querySelector() { return null; }, 'querySelector', 1);
fakeDocument.querySelectorAll = env.setFuncNative(function querySelectorAll() { return []; }, 'querySelectorAll', 1);
fakeDocument.createTextNode = env.setFuncNative(function createTextNode(text) { return { textContent: text }; }, 'createTextNode', 1);
fakeDocument.createEvent = env.setFuncNative(function createEvent(type) {
  return { type, initEvent() {}, preventDefault() {}, stopPropagation() {} };
}, 'createEvent', 1);
fakeDocument.addEventListener = env.setFuncNative(function addEventListener() {}, 'addEventListener', 2);
fakeDocument.removeEventListener = env.setFuncNative(function removeEventListener() {}, 'removeEventListener', 2);
```

## createElement 最小实现

```javascript
fakeDocument.createElement = env.setFuncNative(function createElement(tag) {
  tag = String(tag || '').toLowerCase();
  if (tag === 'canvas') return createCanvasElement();
  return {
    tagName: tag.toUpperCase(),
    style: {},
    childNodes: [],
    setAttribute() {},
    getAttribute() { return null; },
    appendChild(c) { return c; },
    removeChild(c) { return c; },
    addEventListener() {},
    offsetWidth: 100,
    offsetHeight: 20,
    innerHTML: '',
    innerText: '',
    textContent: '',
  };
}, 'createElement', 1);
```

## navigator 基础

```javascript
const [Navigator, fakeNavigator] = env.getNativeProto('Navigator', {});

Object.defineProperties(fakeNavigator, {
  userAgent: { get() { return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'; }, enumerable: true },
  platform: { get() { return 'Win32'; }, enumerable: true },
  language: { get() { return 'zh-CN'; }, enumerable: true },
  languages: { get() { return ['zh-CN', 'zh']; }, enumerable: true },
  cookieEnabled: { get() { return true; }, enumerable: true },
  appName: { get() { return 'Netscape'; }, enumerable: true },
  vendor: { get() { return 'Google Inc.'; }, enumerable: true },
  onLine: { get() { return true; }, enumerable: true },
  hardwareConcurrency: { get() { return 8; }, enumerable: true },
  webdriver: { get() { return false; }, enumerable: true },
  maxTouchPoints: { get() { return 0; }, enumerable: true },
  deviceMemory: { get() { return 8; }, enumerable: true },
  productSub: { get() { return '20030107'; }, enumerable: true },
});
```

## location 基础

```javascript
const fakeLocation = {};
env.setObjNative(fakeLocation, 'Location');

const PAGE_URL = 'https://example.com/';
const url = new URL(PAGE_URL);
Object.defineProperties(fakeLocation, {
  href: { get() { return PAGE_URL; }, set() {}, enumerable: true },
  protocol: { get() { return url.protocol; }, enumerable: true },
  host: { get() { return url.host; }, enumerable: true },
  hostname: { get() { return url.hostname; }, enumerable: true },
  port: { get() { return url.port; }, enumerable: true },
  pathname: { get() { return url.pathname; }, enumerable: true },
  search: { get() { return url.search; }, enumerable: true },
  hash: { get() { return ''; }, enumerable: true },
  origin: { get() { return url.origin; }, enumerable: true },
});
fakeLocation.assign = env.setFuncNative(function assign() {}, 'assign', 1);
fakeLocation.replace = env.setFuncNative(function replace() {}, 'replace', 1);
fakeLocation.reload = env.setFuncNative(function reload() {}, 'reload', 0);
fakeLocation.toString = env.setFuncNative(function toString() { return PAGE_URL; }, 'toString', 0);
```

## storage

```javascript
function createStorage(name) {
  const data = Object.create(null);
  const storage = {};
  env.setObjNative(storage, 'Storage');
  storage.getItem = env.setFuncNative(function getItem(key) {
    console.log(`[storage] ${name}.getItem(${JSON.stringify(key)})`);
    return data[key] !== undefined ? data[key] : null;
  }, 'getItem', 1);
  storage.setItem = env.setFuncNative(function setItem(key, value) {
    console.log(`[storage] ${name}.setItem(${JSON.stringify(key)}, ${JSON.stringify(value)})`);
    data[key] = String(value);
  }, 'setItem', 2);
  storage.removeItem = env.setFuncNative(function removeItem(key) { delete data[key]; }, 'removeItem', 1);
  storage.clear = env.setFuncNative(function clear() {
    for (const key of Object.keys(data)) delete data[key];
  }, 'clear', 0);
  storage.key = env.setFuncNative(function key(index) { return Object.keys(data)[index] || null; }, 'key', 1);
  Object.defineProperty(storage, 'length', { get() { return Object.keys(data).length; }, enumerable: true });
  return storage;
}

const localStorage = createStorage('localStorage');
const sessionStorage = createStorage('sessionStorage');
```

## Canvas + WebGL 起点

```javascript
function createCanvasElement() {
  const el = {
    tagName: 'CANVAS',
    width: 150,
    height: 150,
    style: {},
    childNodes: [],
    setAttribute() {},
    getAttribute() { return null; },
    addEventListener() {},
  };

  const ctx2d = {};
  env.setObjNative(ctx2d, 'CanvasRenderingContext2D');
  for (const name of ['fillRect', 'strokeRect', 'clearRect', 'fillText', 'strokeText', 'beginPath', 'closePath', 'moveTo', 'lineTo', 'arc', 'fill', 'stroke', 'save', 'restore']) {
    ctx2d[name] = env.setFuncNative(function () {}, name);
  }
  ctx2d.measureText = env.setFuncNative(function measureText(text) { return { width: String(text).length * 8 }; }, 'measureText', 1);

  const gl = {};
  env.setObjNative(gl, 'WebGLRenderingContext');
  gl.getParameter = env.setFuncNative(function getParameter(param) {
    const values = {
      37445: 'Google Inc.',
      37446: 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)',
    };
    return values[param] || 0;
  }, 'getParameter', 1);

  el.getContext = env.setFuncNative(function getContext(type) {
    type = String(type || '').toLowerCase();
    if (type === '2d') return ctx2d;
    if (type.includes('webgl')) return gl;
    return null;
  }, 'getContext', 1);
  el.toDataURL = env.setFuncNative(function toDataURL() {
    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
  }, 'toDataURL', 0);

  return el;
}
```
