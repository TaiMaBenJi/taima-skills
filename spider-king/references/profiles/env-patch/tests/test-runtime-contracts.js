import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const profileDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtimeSource = fs.readFileSync(path.join(profileDir, 'env', 'webapi', 'runtime-contracts.js'), 'utf8');
const windowSource = fs.readFileSync(path.join(profileDir, 'env', 'bom', 'window.js'), 'utf8');
const historySource = fs.readFileSync(path.join(profileDir, 'env', 'bom', 'history.js'), 'utf8');
const fetchSource = fs.readFileSync(path.join(profileDir, 'env', 'webapi', 'fetch.js'), 'utf8');
const observersSource = fs.readFileSync(path.join(profileDir, 'env', 'bom', 'observers.js'), 'utf8');
const envMonitorSource = fs.readFileSync(path.join(profileDir, 'env', 'core', 'EnvMonitor.js'), 'utf8');
const monitorSystemSource = fs.readFileSync(path.join(profileDir, 'env', 'core', 'MonitorSystem.js'), 'utf8');
const diagnose = path.join(profileDir, 'scripts', 'env-diagnose.js');
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'env-runtime-contracts-'));

function runDiagnose(envModules, targetName) {
  const result = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', '--env', envModules, targetName],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(result.stdout);
}

function createPrivacyContext() {
  const context = vm.createContext({ URL });
  context.globalThis = context;
  context.window = context;
  context.global = context;
  context.self = context;
  vm.runInContext(`
    globalThis.__consoleEntries__ = [];
    globalThis.console = {
      log(...args) { __consoleEntries__.push(['log', ...args]); },
      warn(...args) { __consoleEntries__.push(['warn', ...args]); },
      error(...args) { __consoleEntries__.push(['error', ...args]); },
      info(...args) { __consoleEntries__.push(['info', ...args]); },
      debug(...args) { __consoleEntries__.push(['debug', ...args]); }
    };
    globalThis.setTimeout = function () { return 1; };
    globalThis.clearTimeout = function () {};
  `, context);
  return context;
}

function assertCoreMonitorPrivacy(source, exportExpression, enableVerboseExpression) {
  const context = createPrivacyContext();
  vm.runInContext(source, context);
  const dump = vm.runInContext(`
    (function () {
      const textSecret = 'TOKEN_LEAK_PROBE_CORE';
      const stateSecret = 'STATE_LEAK_PROBE_CORE';
      const querySecret = 'QUERY_LEAK_PROBE_CORE';
      const errorSecret = 'ERROR_LEAK_PROBE_CORE';
      const numericSecret = 314159265358979;
      const payload = {
        token: textSecret,
        numeric: numericSecret,
        nested: {
          message: errorSecret,
          state: stateSecret,
          url: 'https://example.test/private?token=' + querySecret + '#fragment'
        }
      };
      let getterReads = 0;
      Object.defineProperty(payload, 'accessorSecret', {
        enumerable: true,
        get() {
          getterReads += 1;
          return textSecret;
        }
      });
      Object.defineProperty(payload, '__proto__', {
        enumerable: true,
        value: textSecret
      });
      ${enableVerboseExpression}
      __EnvMonitor__.log('DOM', 'privacyProbe', payload);
      __EnvMonitor__.logUndefined('fixture.missing', payload, 'fixture');
      if (Object.prototype.hasOwnProperty.call(__EnvMonitor__.config, 'verboseMode')) {
        __EnvMonitor__.logCall('fixture.call', [textSecret, numericSecret], new Error(errorSecret), payload);
      } else {
        __EnvMonitor__.logCall('fixture.call', [textSecret, numericSecret], new Error(errorSecret), 17);
      }
      __EnvMonitor__.logCreate('fixture', { __id__: 'fixture-element' }, payload);
      if (getterReads !== 0) throw new Error('metadata sanitizer invoked a getter');
      return JSON.stringify({ exported: ${exportExpression}, logs: __EnvMonitor__.logs, console: __consoleEntries__ });
    })()
  `, context);

  assert.doesNotMatch(dump, /TOKEN_LEAK_PROBE_CORE|STATE_LEAK_PROBE_CORE|QUERY_LEAK_PROBE_CORE|ERROR_LEAK_PROBE_CORE|314159265358979/);
  assert.match(dump, /messageLength/);
  assert.match(dump, /accessorSecret/);
  assert.match(dump, /__proto__/);
  assert.match(dump, /\"type\":\"string\"/);
  assert.match(dump, /\"type\":\"number\"/);
}

function assertEnvironmentModuleLogPrivacy() {
  const context = createPrivacyContext();
  for (const source of [envMonitorSource, windowSource, historySource, fetchSource, observersSource]) {
    vm.runInContext(source, context);
  }

  const dump = vm.runInContext(`
    (function () {
      const querySecret = 'QUERY_LEAK_PROBE_MODULE';
      const messageSecret = 'MESSAGE_LEAK_PROBE_MODULE';
      const stateSecret = 'STATE_LEAK_PROBE_MODULE';
      const errorSecret = 'ERROR_LEAK_PROBE_MODULE';
      const numericSecret = 271828182845904;
      __EnvMonitor__.clearLogs();
      __consoleEntries__.length = 0;

      postMessage(
        { message: messageSecret, state: stateSecret, token: querySecret, numeric: numericSecret },
        'https://example.test/receiver?token=' + querySecret + '#fragment'
      );
      history.pushState({ state: stateSecret }, messageSecret, '/next?token=' + querySecret + '#fragment');
      fetch('https://example.test/api?token=' + querySecret + '#fragment', {
        method: 'POST',
        body: messageSecret
      });
      reportError(new Error(errorSecret));
      const observer = new MutationObserver(function () {});
      observer.observe(
        { __id__: 'fixture-target' },
        { attributes: true, attributeFilter: [querySecret], state: stateSecret, message: messageSecret }
      );

      return JSON.stringify({ logs: __EnvMonitor__.logs, console: __consoleEntries__ });
    })()
  `, context);

  assert.doesNotMatch(dump, /QUERY_LEAK_PROBE_MODULE|MESSAGE_LEAK_PROBE_MODULE|STATE_LEAK_PROBE_MODULE|ERROR_LEAK_PROBE_MODULE|271828182845904/);
  assert.match(dump, /https:\/\/example\.test\/(receiver|next|api)/);
}

try {
  assertCoreMonitorPrivacy(
    envMonitorSource,
    "__EnvMonitor__.exportLogs('object')",
    '__EnvMonitor__.config.verboseMode = true;',
  );
  assertCoreMonitorPrivacy(
    monitorSystemSource,
    '__EnvMonitor__.export()',
    '__EnvMonitor__.config.consoleOutput = true;',
  );
  assertEnvironmentModuleLogPrivacy();

  const contextGlobals = { console };
  if (typeof globalThis.MessageEvent === 'function') contextGlobals.MessageEvent = globalThis.MessageEvent;
  const context = vm.createContext(contextGlobals);
  context.globalThis = context;
  context.window = context;
  vm.runInContext(windowSource, context);
  assert.equal(typeof context.MessageChannel, 'undefined', 'window.js must not install an inert MessageChannel');
  vm.runInContext(runtimeSource, context);

  const messageResult = await new Promise((resolve, reject) => {
    const channel = new context.MessageChannel();
    const seen = [];
    channel.port2.onmessage = (event) => {
      assert.equal(event.target, channel.port2);
      assert.equal(event.currentTarget, channel.port2);
      seen.push(['property', event.data.kind]);
    };
    channel.port2.addEventListener('message', (event) => {
      assert.equal(event.target, channel.port2);
      assert.equal(event.currentTarget, channel.port2);
      seen.push(['listener', event.data.kind]);
    });
    channel.port2.start();
    channel.port1.postMessage({ kind: 'linked-port-fixture' });
    assert.equal(seen.length, 0, 'MessageChannel delivery must be asynchronous');
    setTimeout(() => {
      try {
        assert.deepEqual(seen, [
          ['property', 'linked-port-fixture'],
          ['listener', 'linked-port-fixture'],
        ]);
        resolve(true);
      } catch (error) {
        reject(error);
      }
    }, 0);
  });
  assert.equal(messageResult, true);

  const startChannel = new context.MessageChannel();
  let startCount = 0;
  startChannel.port2.addEventListener('message', () => { startCount += 1; });
  startChannel.port1.postMessage({ kind: 'queued-until-start' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(startCount, 0, 'addEventListener must not implicitly start a MessagePort');
  startChannel.port2.start();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(startCount, 1);

  const reentrantChannel = new context.MessageChannel();
  let onceCount = 0;
  reentrantChannel.port2.addEventListener('fixture', () => {
    onceCount += 1;
    reentrantChannel.port2.dispatchEvent({ type: 'fixture' });
  }, { once: true });
  reentrantChannel.port2.dispatchEvent({ type: 'fixture' });
  assert.equal(onceCount, 1, 'once listener must be removed before invocation');

  const listenerChannel = new context.MessageChannel();
  let duplicateCount = 0;
  const duplicateListener = () => { duplicateCount += 1; };
  listenerChannel.port2.addEventListener('fixture', duplicateListener);
  listenerChannel.port2.addEventListener('fixture', duplicateListener);
  listenerChannel.port2.addEventListener('fixture', () => { throw new Error('synthetic port listener failure'); });
  listenerChannel.port2.addEventListener('fixture', () => { duplicateCount += 1; });
  assert.doesNotThrow(() => listenerChannel.port2.dispatchEvent({ type: 'fixture' }));
  assert.equal(duplicateCount, 2, 'duplicate listeners must collapse and later listeners must survive exceptions');

  assert.equal(Object.hasOwn(context.webpackChunkFixture || [], 'push'), false);
  const capture = context.__installWebpackChunkCapture__(context, 'webpackChunkFixture');
  context.webpackChunkFixture.push([['chunk-a'], { 101: function fixtureModule() {} }]);
  assert.deepEqual(JSON.parse(JSON.stringify(capture.records)), [{
    chunkIds: ['chunk-a'],
    moduleIds: ['101'],
    chunkIdCount: 1,
    moduleIdCount: 1,
    truncated: false,
  }]);
  assert.deepEqual(JSON.parse(JSON.stringify(capture.stats)), { seenRecords: 1, droppedRecords: 0 });
  assert.equal(capture.restore(), true);
  assert.equal(Object.hasOwn(context.webpackChunkFixture, 'push'), false);
  context.webpackChunkFixture.push([['chunk-b'], { 202: function otherModule() {} }]);
  assert.equal(capture.records.length, 1);

  const ownPushArray = [];
  const ownPush = function(...entries) {
    return Array.prototype.push.apply(this, entries);
  };
  Object.defineProperty(ownPushArray, 'push', {
    value: ownPush,
    writable: true,
    enumerable: true,
    configurable: true,
  });
  context.webpackChunkOwnPush = ownPushArray;
  const ownPushDescriptor = Object.getOwnPropertyDescriptor(ownPushArray, 'push');
  const ownPushCapture = context.__installWebpackChunkCapture__(context, 'webpackChunkOwnPush');
  assert.equal(ownPushCapture.restore(), true);
  const restoredOwnPushDescriptor = Object.getOwnPropertyDescriptor(ownPushArray, 'push');
  assert.equal(restoredOwnPushDescriptor.value, ownPushDescriptor.value);
  assert.equal(restoredOwnPushDescriptor.writable, ownPushDescriptor.writable);
  assert.equal(restoredOwnPushDescriptor.enumerable, ownPushDescriptor.enumerable);
  assert.equal(restoredOwnPushDescriptor.configurable, ownPushDescriptor.configurable);

  const chainedCapture = context.__installWebpackChunkCapture__(context, 'webpackChunkChained');
  const capturedPush = context.webpackChunkChained.push;
  let laterWrapperCalls = 0;
  context.webpackChunkChained.push = function(...entries) {
    laterWrapperCalls += 1;
    return capturedPush.apply(this, entries);
  };
  assert.equal(chainedCapture.restore(), false, 'A later wrapper must not be overwritten');
  context.webpackChunkChained.push([['chunk-c'], { 303: function chainedModule() {} }]);
  assert.equal(laterWrapperCalls, 1);
  assert.equal(chainedCapture.records.length, 0, 'Restored capture must remain inactive through a later wrapper');

  const boundedCapture = context.__installWebpackChunkCapture__(context, 'webpackChunkBounded', {
    maxIds: 2,
    maxIdLength: 8,
  });
  const longId = 'x'.repeat(1000);
  context.webpackChunkBounded.push([[longId, 'chunk-b', 'chunk-c'], { [longId]: function a() {}, 2: function b() {}, 3: function c() {} }]);
  assert.equal(boundedCapture.records[0].chunkIds.length, 2);
  assert.equal(boundedCapture.records[0].moduleIds.length, 2);
  assert(boundedCapture.records[0].chunkIds.every((id) => id.length <= 8));
  assert(boundedCapture.records[0].moduleIds.every((id) => id.length <= 8));
  assert.equal(boundedCapture.records[0].moduleIdCount, null);
  assert.equal(boundedCapture.records[0].truncated, true);
  boundedCapture.restore();

  fs.writeFileSync(path.join(tempDir, 'timer-patch.js'), 'globalThis.setTimeout = (callback) => { callback(); return 1; };\n');
  fs.writeFileSync(
    path.join(tempDir, 'image-target.js'),
      'const image = new Image();\n' +
      'const createdImage = document.createElement("img");\n' +
      'if (!(image instanceof Image) || !(createdImage instanceof Image) || !(image instanceof HTMLImageElement) || !(createdImage instanceof HTMLImageElement) || image.constructor !== createdImage.constructor) throw new Error("Image constructors diverged");\n' +
      'let propertyCount = 0; let listenerCount = 0;\n' +
      'image.onload = (event) => { if (event.type !== "load" || event.target !== image) throw new Error("bad onload event"); propertyCount += 1; throw new Error("synthetic onload failure"); };\n' +
      'image.addEventListener("load", () => { throw new Error("synthetic listener failure"); });\n' +
      'image.addEventListener("load", (event) => { if (event.type !== "load" || event.target !== image) throw new Error("bad listener event"); listenerCount += 1; });\n' +
      'image.src = "fixture://image";\n' +
      'if (propertyCount !== 1 || listenerCount !== 1) throw new Error("Image load listeners were not both dispatched");\n',
  );
  const imageResult = runDiagnose('timer-patch.js,dom/event.js,dom/document.js', 'image-target.js');
  assert.equal(imageResult.success, true);
  const elementsImageResult = runDiagnose('timer-patch.js,dom/event.js,dom/document.js,dom/elements.js', 'image-target.js');
  assert.equal(elementsImageResult.success, true);

  fs.writeFileSync(path.join(tempDir, 'btoa-target.js'),
    'if (btoa("\\x00\\xffAz") !== "AP9Beg==") throw new Error("Latin1 btoa vector mismatch");\n' +
      'let rejected = false; try { btoa("\\u0100"); } catch (error) { rejected = error.name === "InvalidCharacterError"; }\n' +
      'if (!rejected) throw new Error("btoa must reject non-Latin1 code units");\n');
  const btoaResult = runDiagnose('encoding/atob.js', 'btoa-target.js');
  assert.equal(btoaResult.success, true);

  console.log('env runtime contracts: ok');
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
