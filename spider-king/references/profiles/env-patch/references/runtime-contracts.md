# Narrow Runtime Contracts

Use `env/webapi/runtime-contracts.js` only after a fixed fixture proves that the target depends on `MessageChannel` scheduling or an explicitly named webpack chunk array. It is an opt-in compatibility module, not a generic browser emulator.

## MessageChannel

The module installs linked `MessagePort` objects with asynchronous peer delivery:

- `port1.postMessage(value)` queues one `message` event on `port2`, and vice versa.
- `onmessage` and `addEventListener('message', ...)` receive the same event.
- `addEventListener` queues incoming messages until `start()`; assigning `onmessage` starts delivery as browsers do. `close`, `removeEventListener`, and reentrancy-safe `{ once: true }` are supported.
- Closing either receiving port suppresses later delivery.

The implementation intentionally does not emulate structured clone, transferable ownership, `messageerror`, agent isolation, or browser task-source ordering. If any of those change the decisive output, move to a more faithful local host and preserve the fixed counterexample.

## Image Load Dispatch

The `dom/document.js` and `dom/elements.js` image implementations schedule one `load` event after `src` changes. The `onload` property and `addEventListener('load', ...)` listeners receive the same event object. The scheduler must be supplied by the selected runtime; the default diagnostic timer is deliberately inert.

Use synthetic URLs in fixtures. Do not turn Image into a network client or embed target URLs in this profile.

## Webpack Chunk Capture

The module exposes:

```javascript
const capture = __installWebpackChunkCapture__(globalThis, 'webpackChunkKnownName');
// Load the already captured local bundle or chunk here.
console.log(capture.records);
capture.restore();
```

The chunk name must come from current bundle evidence. The capture records bounded chunk IDs and module IDs only; `maxIds` bounds enumeration and `maxIdLength` bounds each retained ID. A clipped module scan reports `moduleIdCount: null`; `truncated` and `stats.droppedRecords` expose clipping. It does not stringify module bodies, scan global arrays, execute registered modules, or retain request data. `restore()` restores the original own-property descriptor when the capture wrapper is still installed. If another wrapper was installed later, `restore()` leaves that wrapper in place and permanently disables capture through the older wrapper.

## Latin1 btoa Oracle

Before replacing a host `btoa`, prove that it fails a browser-compatible Latin1 vector:

```text
input code units: 00 ff 41 7a
btoa("\x00\xffAz"): AP9Beg==
```

Code units above `0xff` must be rejected. Do not silently UTF-8 encode them. A host override is justified only when the fixed positive vector or a fixed rejection vector disagrees.

Run both profile test files after changing any contract:

```text
npm test
```
