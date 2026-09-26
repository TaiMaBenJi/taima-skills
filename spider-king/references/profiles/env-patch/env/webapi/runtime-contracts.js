/*
 * Opt-in runtime contracts for narrow browser semantics.
 *
 * This module does not discover chunk names, execute module bodies, clone
 * arbitrary values, or capture payloads. Load it only after the target has
 * been reduced to a known MessageChannel or webpack chunk boundary.
 */
(function installRuntimeContracts(global) {
    'use strict';

    const root = global.window || global;
    const schedule = typeof global.queueMicrotask === 'function'
        ? global.queueMicrotask.bind(global)
        : (callback) => Promise.resolve().then(callback);

    function bindEventTarget(event, target) {
        if (event.target === target && event.currentTarget === target) return event;
        try {
            Object.defineProperties(event, {
                target: { value: target, configurable: true },
                currentTarget: { value: target, configurable: true },
            });
            return event;
        } catch (_) {
            return {
                type: event.type,
                data: event.data,
                ports: event.ports || [],
                target,
                currentTarget: target,
                defaultPrevented: Boolean(event.defaultPrevented),
            };
        }
    }

    function makeMessageEvent(type, data, target) {
        let event;
        if (typeof root.MessageEvent === 'function') {
            try {
                event = new root.MessageEvent(type, { data, ports: [] });
            } catch (_) {
                event = null;
            }
        }
        if (!event) event = { type, data, ports: [] };
        return bindEventTarget(event, target);
    }

    function MessagePort() {
        this._onmessage = null;
        this.onmessageerror = null;
        this._peer = null;
        this._closed = false;
        this._started = false;
        this._listeners = [];
        this._pendingMessages = [];
        Object.defineProperty(this, 'onmessage', {
            configurable: true,
            enumerable: true,
            get: () => this._onmessage,
            set: (listener) => {
                this._onmessage = typeof listener === 'function' ? listener : null;
                if (this._onmessage) this.start();
            },
        });
    }

    MessagePort.prototype.start = function() {
        if (this._closed || this._started) return;
        this._started = true;
        const pending = this._pendingMessages.splice(0);
        for (const event of pending) {
            schedule(() => {
                if (!this._closed && this._started) this.dispatchEvent(event);
            });
        }
    };

    MessagePort.prototype.close = function() {
        this._closed = true;
        this._listeners.length = 0;
        this._pendingMessages.length = 0;
        this.onmessage = null;
        this.onmessageerror = null;
    };

    MessagePort.prototype.addEventListener = function(type, listener, options) {
        if (typeof listener !== 'function' && !(listener && typeof listener.handleEvent === 'function')) return;
        const once = Boolean(options && typeof options === 'object' && options.once);
        const capture = Boolean(options === true || (options && options.capture));
        if (this._listeners.some((entry) => entry.type === type && entry.listener === listener && entry.capture === capture)) return;
        this._listeners.push({ type, listener, once, capture });
    };

    MessagePort.prototype.removeEventListener = function(type, listener, options) {
        const capture = Boolean(options === true || (options && options.capture));
        this._listeners = this._listeners.filter((entry) => (
            entry.type !== type || entry.listener !== listener || entry.capture !== capture
        ));
    };

    MessagePort.prototype.dispatchEvent = function(event) {
        if (!event || typeof event.type !== 'string') throw new TypeError('MessagePort event must have a type');
        event = bindEventTarget(event, this);
        if (event.type === 'message' && typeof this.onmessage === 'function') {
            try { this.onmessage.call(this, event); } catch (_) {}
        }
        const pending = this._listeners.slice();
        for (const entry of pending) {
            if (entry.type !== event.type) continue;
            if (entry.once) this.removeEventListener(entry.type, entry.listener, entry.capture);
            try {
                if (typeof entry.listener === 'function') entry.listener.call(this, event);
                else entry.listener.handleEvent(event);
            } catch (_) {}
        }
        return !event.defaultPrevented;
    };

    MessagePort.prototype.postMessage = function(data) {
        if (this._closed) return;
        const peer = this._peer;
        if (!peer || peer._closed) return;
        schedule(() => {
            if (peer._closed) return;
            const event = makeMessageEvent('message', data, peer);
            if (!peer._started) {
                if (peer._pendingMessages.length < 128) peer._pendingMessages.push(event);
                return;
            }
            peer.dispatchEvent(event);
        });
    };

    function MessageChannel() {
        this.port1 = new MessagePort();
        this.port2 = new MessagePort();
        this.port1._peer = this.port2;
        this.port2._peer = this.port1;
    }

    root.MessagePort = MessagePort;
    root.MessageChannel = MessageChannel;

    function installWebpackChunkCapture(target, name, options) {
        const host = target || root;
        if (!host || typeof name !== 'string' || name.length === 0) {
            throw new TypeError('webpack chunk name is required');
        }
        const chunkArray = host[name] || (host[name] = []);
        if (!Array.isArray(chunkArray)) throw new TypeError('webpack chunk target is not an array');

        const config = options || {};
        const maxRecords = Number.isInteger(config.maxRecords) && config.maxRecords > 0 ? config.maxRecords : 128;
        const maxIds = Number.isInteger(config.maxIds) && config.maxIds > 0 ? config.maxIds : 256;
        const maxIdLength = Number.isInteger(config.maxIdLength) && config.maxIdLength > 0 ? config.maxIdLength : 128;
        const records = [];
        const stats = { seenRecords: 0, droppedRecords: 0 };
        const originalPushDescriptor = Object.getOwnPropertyDescriptor(chunkArray, 'push');
        const originalPush = chunkArray.push;
        if (typeof originalPush !== 'function') throw new TypeError('webpack chunk push is not callable');
        let active = true;

        function boundedId(value) {
            let text;
            try { text = String(value); } catch (_) { return { value: '[unavailable]', truncated: true }; }
            if (text.length <= maxIdLength) return { value: text, truncated: false };
            return { value: text.slice(0, maxIdLength), truncated: true };
        }

        function collectChunkIds(value) {
            if (!Array.isArray(value)) return { ids: [], count: 0, truncated: false };
            const ids = [];
            let truncated = value.length > maxIds;
            const limit = Math.min(value.length, maxIds);
            for (let index = 0; index < limit; index += 1) {
                const bounded = boundedId(value[index]);
                ids.push(bounded.value);
                truncated = truncated || bounded.truncated;
            }
            return { ids, count: value.length, truncated };
        }

        function collectModuleIds(value) {
            const ids = [];
            let observed = 0;
            let truncated = false;
            try {
                for (const key in value) {
                    if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
                    observed += 1;
                    if (observed > maxIds) {
                        truncated = true;
                        break;
                    }
                    const bounded = boundedId(key);
                    ids.push(bounded.value);
                    truncated = truncated || bounded.truncated;
                }
            } catch (_) {
                truncated = true;
            }
            return { ids, count: truncated && observed > maxIds ? null : observed, truncated };
        }

        function record(entry) {
            if (!Array.isArray(entry) || entry.length < 2 || !entry[1] || typeof entry[1] !== 'object') return;
            stats.seenRecords += 1;
            if (records.length >= maxRecords) {
                stats.droppedRecords += 1;
                return;
            }
            const chunkIds = collectChunkIds(entry[0]);
            const moduleIds = collectModuleIds(entry[1]);
            records.push({
                chunkIds: chunkIds.ids,
                moduleIds: moduleIds.ids,
                chunkIdCount: chunkIds.count,
                moduleIdCount: moduleIds.count,
                truncated: chunkIds.truncated || moduleIds.truncated,
            });
        }

        for (const entry of chunkArray) record(entry);
        const wrappedPush = function(...entries) {
            const result = originalPush.apply(this, entries);
            if (active) {
                try { entries.forEach(record); } catch (_) {}
            }
            return result;
        };
        const originalPushIsDataProperty = originalPushDescriptor &&
            Object.prototype.hasOwnProperty.call(originalPushDescriptor, 'value');
        if (originalPushDescriptor && !originalPushIsDataProperty && !originalPushDescriptor.configurable) {
            throw new TypeError('webpack chunk push accessor is not patchable');
        }
        if (originalPushDescriptor && originalPushIsDataProperty &&
            !originalPushDescriptor.configurable && !originalPushDescriptor.writable) {
            throw new TypeError('webpack chunk push is not patchable');
        }
        const wrappedPushDescriptor = originalPushIsDataProperty
            ? { ...originalPushDescriptor, value: wrappedPush }
            : {
                value: wrappedPush,
                writable: true,
                enumerable: originalPushDescriptor ? originalPushDescriptor.enumerable : false,
                configurable: true,
            };
        Object.defineProperty(chunkArray, 'push', wrappedPushDescriptor);

        return {
            array: chunkArray,
            records,
            stats,
            restore: function() {
                active = false;
                const currentDescriptor = Object.getOwnPropertyDescriptor(chunkArray, 'push');
                if (!currentDescriptor || currentDescriptor.value !== wrappedPush) return false;
                if (originalPushDescriptor) Object.defineProperty(chunkArray, 'push', originalPushDescriptor);
                else delete chunkArray.push;
                return true;
            },
        };
    }

    root.__installWebpackChunkCapture__ = installWebpackChunkCapture;
    root.__runtimeContracts__ = { MessageChannel, MessagePort, installWebpackChunkCapture };
})(typeof globalThis === 'object' ? globalThis : this);
