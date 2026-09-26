/**
 * @env-module network
 * @description 增强版网络请求模拟 - 带完整监控和灵活mock支持
 * @version 2.0.0
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    'use strict';
    
    // ==================== 获取监控系统 ====================
    const Monitor = window.__EnvMonitor__ || {
        log: function() {},
        logCall: function() {},
        logCreate: function() {},
        hasMock: function() { return false; },
        executeMock: function() { return { mocked: false }; },
        pushChain: function() {},
        popChain: function() {},
        setMock: function() {},
        config: { enabled: false }
    };
    
    // ==================== 网络请求存储 ====================
    const NetworkStore = {
        requests: [],
        maxSize: 100,
        
        add: function(request) {
            this.requests.push(request);
            if (this.requests.length > this.maxSize) {
                this.requests.shift();
            }
        },
        
        getAll: function() {
            return this.requests.slice();
        },
        
        getByUrl: function(urlPattern) {
            return this.requests.filter(r => r.url.includes(urlPattern));
        },
        
        clear: function() {
            this.requests = [];
        }
    };
    
    window.__NetworkStore__ = NetworkStore;
    
    // ==================== Mock 响应配置 ====================
    const NetworkMock = {
        rules: [],
        
        // 添加 mock 规则
        add: function(rule) {
            // rule: { pattern: string|RegExp, response: { status, body, headers, delay } }
            this.rules.push(rule);
        },
        
        // 移除 mock 规则
        remove: function(pattern) {
            this.rules = this.rules.filter(r => r.pattern !== pattern);
        },
        
        // 清空所有规则
        clear: function() {
            this.rules = [];
        },
        
        // 查找匹配的 mock 规则
        find: function(url, method) {
            for (const rule of this.rules) {
                let match = false;
                if (typeof rule.pattern === 'string') {
                    match = url.includes(rule.pattern);
                } else if (rule.pattern instanceof RegExp) {
                    match = rule.pattern.test(url);
                } else if (typeof rule.pattern === 'function') {
                    match = rule.pattern(url, method);
                }
                
                if (match) {
                    if (rule.method && rule.method !== method) continue;
                    return rule;
                }
            }
            return null;
        }
    };
    
    window.__NetworkMock__ = NetworkMock;
    
    // ==================== 增强版 XMLHttpRequest ====================
    const OriginalXHR = window.XMLHttpRequest;
    
    function EnhancedXMLHttpRequest() {
        this.readyState = 0;
        this.response = null;
        this.responseText = '';
        this.responseType = '';
        this.responseURL = '';
        this.responseXML = null;
        this.status = 0;
        this.statusText = '';
        this.timeout = 0;
        this.withCredentials = false;
        this.upload = new XMLHttpRequestUpload();
        
        this._id = 'xhr_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this._method = '';
        this._url = '';
        this._async = true;
        this._user = null;
        this._password = null;
        this._headers = {};
        this._responseHeaders = {};
        this._aborted = false;
        this._body = null;
        this._startTime = 0;
        
        // 事件处理器
        this.onreadystatechange = null;
        this.onload = null;
        this.onerror = null;
        this.onabort = null;
        this.ontimeout = null;
        this.onloadstart = null;
        this.onloadend = null;
        this.onprogress = null;
        
        this._listeners = {};
        
        Monitor.logCreate('XMLHttpRequest', { id: this._id });
    }
    
    // 静态常量
    EnhancedXMLHttpRequest.UNSENT = 0;
    EnhancedXMLHttpRequest.OPENED = 1;
    EnhancedXMLHttpRequest.HEADERS_RECEIVED = 2;
    EnhancedXMLHttpRequest.LOADING = 3;
    EnhancedXMLHttpRequest.DONE = 4;
    
    EnhancedXMLHttpRequest.prototype = {
        UNSENT: 0,
        OPENED: 1,
        HEADERS_RECEIVED: 2,
        LOADING: 3,
        DONE: 4,
        
        open: function(method, url, async, user, password) {
            Monitor.pushChain('XMLHttpRequest.open');
            Monitor.logCall('XMLHttpRequest.open', [method, url, async], null, { id: this._id });
            
            // 检查 mock
            const mock = Monitor.executeMock('XMLHttpRequest.open', [method, url, async], this);
            if (mock.mocked) {
                Monitor.popChain();
                return mock.result;
            }
            
            this._method = method.toUpperCase();
            this._url = url;
            this._async = async !== false;
            this._user = user;
            this._password = password;
            this.readyState = EnhancedXMLHttpRequest.OPENED;
            this._dispatchReadyStateChange();
            
            Monitor.popChain();
        },
        
        setRequestHeader: function(name, value) {
            Monitor.logCall('XMLHttpRequest.setRequestHeader', [name, value], null, { id: this._id });
            this._headers[name.toLowerCase()] = value;
        },
        
        getResponseHeader: function(name) {
            const value = this._responseHeaders[name.toLowerCase()] || null;
            Monitor.logCall('XMLHttpRequest.getResponseHeader', [name], value, { id: this._id });
            return value;
        },
        
        getAllResponseHeaders: function() {
            const headers = Object.entries(this._responseHeaders)
                .map(([name, value]) => `${name}: ${value}`)
                .join('\r\n');
            Monitor.logCall('XMLHttpRequest.getAllResponseHeaders', [], headers, { id: this._id });
            return headers;
        },
        
        overrideMimeType: function(mime) {
            Monitor.logCall('XMLHttpRequest.overrideMimeType', [mime], null, { id: this._id });
            this._mimeType = mime;
        },
        
        send: function(body) {
            Monitor.pushChain('XMLHttpRequest.send');
            Monitor.logCall('XMLHttpRequest.send', [body], null, { id: this._id });
            
            if (this._aborted) {
                Monitor.popChain();
                return;
            }
            
            this._body = body;
            this._startTime = Date.now();
            
            // 记录请求
            const requestInfo = {
                id: this._id,
                type: 'xhr',
                method: this._method,
                url: this._url,
                headers: { ...this._headers },
                body: body,
                startTime: this._startTime,
                status: null,
                response: null,
                endTime: null,
                duration: null
            };
            NetworkStore.add(requestInfo);
            
            this._dispatchEvent('loadstart');
            
            // 检查 mock
            const mock = Monitor.executeMock('XMLHttpRequest.send', [body, this._url, this._method], this);
            if (mock.mocked) {
                this._handleMockResponse(mock.result, requestInfo);
                Monitor.popChain();
                return;
            }
            
            // 检查网络 mock 规则
            const networkMock = NetworkMock.find(this._url, this._method);
            if (networkMock) {
                this._handleNetworkMock(networkMock, requestInfo);
                Monitor.popChain();
                return;
            }
            
            // 默认模拟响应
            this._simulateResponse(requestInfo);
            Monitor.popChain();
        },
        
        _handleMockResponse: function(mockResult, requestInfo) {
            const self = this;
            const delay = mockResult.delay || 10;
            
            setTimeout(function() {
                if (self._aborted) return;
                
                self._setResponse(mockResult, requestInfo);
            }, delay);
        },
        
        _handleNetworkMock: function(mockRule, requestInfo) {
            const self = this;
            const delay = mockRule.response?.delay || mockRule.delay || 10;
            
            setTimeout(function() {
                if (self._aborted) return;
                
                const response = mockRule.response || {};
                self._setResponse({
                    status: response.status || 200,
                    statusText: response.statusText || 'OK',
                    headers: response.headers || { 'content-type': 'application/json' },
                    body: response.body || { mocked: true }
                }, requestInfo);
            }, delay);
        },
        
        _simulateResponse: function(requestInfo) {
            const self = this;
            
            // 模拟网络延迟
            setTimeout(function() {
                if (self._aborted) return;
                
                self.readyState = EnhancedXMLHttpRequest.HEADERS_RECEIVED;
                self._responseHeaders = {
                    'content-type': 'application/json',
                    'x-simulated': 'true'
                };
                self._dispatchReadyStateChange();
                
                setTimeout(function() {
                    if (self._aborted) return;
                    
                    self.readyState = EnhancedXMLHttpRequest.LOADING;
                    self._dispatchReadyStateChange();
                    self._dispatchEvent('progress', { loaded: 50, total: 100 });
                    
                    setTimeout(function() {
                        if (self._aborted) return;
                        
                        self._setResponse({
                            status: 200,
                            statusText: 'OK',
                            body: {
                                success: true,
                                message: 'Simulated XHR response',
                                url: self._url,
                                method: self._method,
                                timestamp: Date.now()
                            }
                        }, requestInfo);
                    }, 10);
                }, 10);
            }, 10);
        },
        
        _setResponse: function(data, requestInfo) {
            this.readyState = EnhancedXMLHttpRequest.DONE;
            this.status = data.status || 200;
            this.statusText = data.statusText || 'OK';
            
            if (data.headers) {
                Object.entries(data.headers).forEach(([name, value]) => {
                    this._responseHeaders[name.toLowerCase()] = value;
                });
            }
            
            const body = data.body;
            if (typeof body === 'object') {
                this.responseText = JSON.stringify(body);
            } else if (body !== undefined) {
                this.responseText = String(body);
            } else {
                this.responseText = '';
            }
            
            this.response = this.responseType === '' || this.responseType === 'text' 
                ? this.responseText 
                : (this.responseType === 'json' ? body : this.responseText);
            this.responseURL = this._url;
            
            // 更新请求记录
            if (requestInfo) {
                requestInfo.status = this.status;
                requestInfo.response = this.response;
                requestInfo.endTime = Date.now();
                requestInfo.duration = requestInfo.endTime - requestInfo.startTime;
            }
            
            this._dispatchReadyStateChange();
            this._dispatchEvent('progress', { loaded: 100, total: 100 });
            this._dispatchEvent('load');
            this._dispatchEvent('loadend');
        },
        
        abort: function() {
            Monitor.logCall('XMLHttpRequest.abort', [], null, { id: this._id });
            this._aborted = true;
            this.readyState = EnhancedXMLHttpRequest.UNSENT;
            this._dispatchEvent('abort');
            this._dispatchEvent('loadend');
        },
        
        addEventListener: function(type, listener, options) {
            if (!this._listeners[type]) {
                this._listeners[type] = [];
            }
            this._listeners[type].push(listener);
        },
        
        removeEventListener: function(type, listener) {
            if (this._listeners[type]) {
                this._listeners[type] = this._listeners[type].filter(l => l !== listener);
            }
        },
        
        dispatchEvent: function(event) {
            this._dispatchEvent(event.type, event);
        },
        
        _dispatchEvent: function(type, props) {
            const event = {
                type: type,
                target: this,
                currentTarget: this,
                loaded: props?.loaded || 0,
                total: props?.total || 0,
                lengthComputable: (props?.total || 0) > 0
            };
            
            // 调用 on* 处理器
            const handler = this['on' + type];
            if (typeof handler === 'function') {
                try {
                    handler.call(this, event);
                } catch (e) {
                    console.error('[XMLHttpRequest] Event handler error: details redacted');
                }
            }
            
            // 调用 addEventListener 添加的监听器
            const listeners = this._listeners[type] || [];
            listeners.forEach(listener => {
                try {
                    listener.call(this, event);
                } catch (e) {
                    console.error('[XMLHttpRequest] Event listener error: details redacted');
                }
            });
        },
        
        _dispatchReadyStateChange: function() {
            this._dispatchEvent('readystatechange');
        }
    };
    
    // XMLHttpRequestUpload
    function XMLHttpRequestUpload() {
        this.onloadstart = null;
        this.onprogress = null;
        this.onabort = null;
        this.onerror = null;
        this.onload = null;
        this.ontimeout = null;
        this.onloadend = null;
        this._listeners = {};
    }
    
    XMLHttpRequestUpload.prototype = {
        addEventListener: function(type, listener) {
            if (!this._listeners[type]) this._listeners[type] = [];
            this._listeners[type].push(listener);
        },
        removeEventListener: function(type, listener) {
            if (this._listeners[type]) {
                this._listeners[type] = this._listeners[type].filter(l => l !== listener);
            }
        }
    };
    
    window.XMLHttpRequest = EnhancedXMLHttpRequest;
    window.XMLHttpRequestUpload = XMLHttpRequestUpload;
    
    // ==================== 增强版 fetch ====================
    const OriginalFetch = window.fetch;
    
    window.fetch = function(input, init) {
        Monitor.pushChain('fetch');
        
        const url = typeof input === 'string' ? input : (input.url || String(input));
        const method = init?.method?.toUpperCase() || (input.method?.toUpperCase()) || 'GET';
        
        Monitor.logCall('fetch', [url, init], 'Promise', {});
        
        // 记录请求
        const requestInfo = {
            id: 'fetch_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
            type: 'fetch',
            method: method,
            url: url,
            headers: init?.headers || {},
            body: init?.body,
            startTime: Date.now(),
            status: null,
            response: null,
            endTime: null,
            duration: null
        };
        NetworkStore.add(requestInfo);
        
        // 检查 mock
        const mock = Monitor.executeMock('fetch', [url, init], window);
        if (mock.mocked) {
            Monitor.popChain();
            return createMockResponse(mock.result, requestInfo);
        }
        
        // 检查网络 mock 规则
        const networkMock = NetworkMock.find(url, method);
        if (networkMock) {
            Monitor.popChain();
            return createNetworkMockResponse(networkMock, requestInfo);
        }
        
        // 默认模拟响应
        Monitor.popChain();
        return createSimulatedResponse(url, method, requestInfo);
    };
    
    function createMockResponse(mockResult, requestInfo) {
        return new Promise((resolve, reject) => {
            const delay = mockResult.delay || 10;
            
            setTimeout(() => {
                const status = mockResult.status || 200;
                const body = mockResult.body || {};
                const headers = mockResult.headers || {};
                
                requestInfo.status = status;
                requestInfo.response = body;
                requestInfo.endTime = Date.now();
                requestInfo.duration = requestInfo.endTime - requestInfo.startTime;
                
                if (mockResult.error) {
                    reject(new TypeError(mockResult.error));
                    return;
                }
                
                resolve(new Response(
                    JSON.stringify(body),
                    {
                        status: status,
                        statusText: mockResult.statusText || 'OK',
                        headers: headers
                    }
                ));
            }, delay);
        });
    }
    
    function createNetworkMockResponse(mockRule, requestInfo) {
        return new Promise((resolve, reject) => {
            const delay = mockRule.response?.delay || mockRule.delay || 10;
            const response = mockRule.response || {};
            
            setTimeout(() => {
                const status = response.status || 200;
                const body = response.body || { mocked: true };
                
                requestInfo.status = status;
                requestInfo.response = body;
                requestInfo.endTime = Date.now();
                requestInfo.duration = requestInfo.endTime - requestInfo.startTime;
                
                if (response.error) {
                    reject(new TypeError(response.error));
                    return;
                }
                
                resolve(new Response(
                    typeof body === 'string' ? body : JSON.stringify(body),
                    {
                        status: status,
                        statusText: response.statusText || 'OK',
                        headers: response.headers || { 'content-type': 'application/json' }
                    }
                ));
            }, delay);
        });
    }
    
    function createSimulatedResponse(url, method, requestInfo) {
        return new Promise((resolve) => {
            setTimeout(() => {
                const body = {
                    success: true,
                    message: 'Simulated fetch response',
                    url: url,
                    method: method,
                    timestamp: Date.now()
                };
                
                requestInfo.status = 200;
                requestInfo.response = body;
                requestInfo.endTime = Date.now();
                requestInfo.duration = requestInfo.endTime - requestInfo.startTime;
                
                resolve(new Response(
                    JSON.stringify(body),
                    {
                        status: 200,
                        statusText: 'OK',
                        headers: {
                            'content-type': 'application/json',
                            'x-simulated': 'true'
                        }
                    }
                ));
            }, 20);
        });
    }
    
    // ==================== Headers 增强 ====================
    if (!window.Headers) {
        function Headers(init) {
            this._headers = {};
            
            if (init) {
                if (init instanceof Headers) {
                    init.forEach((value, key) => this.append(key, value));
                } else if (Array.isArray(init)) {
                    init.forEach(([key, value]) => this.append(key, value));
                } else if (typeof init === 'object') {
                    Object.entries(init).forEach(([key, value]) => this.append(key, value));
                }
            }
        }
        
        Headers.prototype = {
            append: function(name, value) {
                name = name.toLowerCase();
                if (!this._headers[name]) this._headers[name] = [];
                this._headers[name].push(String(value));
            },
            delete: function(name) { delete this._headers[name.toLowerCase()]; },
            get: function(name) {
                const values = this._headers[name.toLowerCase()];
                return values ? values.join(', ') : null;
            },
            has: function(name) { return name.toLowerCase() in this._headers; },
            set: function(name, value) { this._headers[name.toLowerCase()] = [String(value)]; },
            forEach: function(callback, thisArg) {
                Object.entries(this._headers).forEach(([name, values]) => {
                    values.forEach(value => callback.call(thisArg, value, name, this));
                });
            },
            entries: function() {
                const entries = [];
                this.forEach((value, key) => entries.push([key, value]));
                return entries[Symbol.iterator]();
            },
            keys: function() { return Object.keys(this._headers)[Symbol.iterator](); },
            values: function() {
                const values = [];
                this.forEach(value => values.push(value));
                return values[Symbol.iterator]();
            },
            [Symbol.iterator]: function() { return this.entries(); }
        };
        
        window.Headers = Headers;
    }
    
    // ==================== Response 增强 ====================
    if (!window.Response) {
        function Response(body, init) {
            init = init || {};
            
            this._body = body;
            this._bodyUsed = false;
            this.status = init.status !== undefined ? init.status : 200;
            this.statusText = init.statusText || '';
            this.ok = this.status >= 200 && this.status < 300;
            this.headers = new Headers(init.headers);
            this.type = 'basic';
            this.url = init.url || '';
            this.redirected = false;
        }
        
        Response.prototype = {
            get bodyUsed() { return this._bodyUsed; },
            
            clone: function() {
                if (this._bodyUsed) {
                    throw new TypeError('Already read');
                }
                return new Response(this._body, {
                    status: this.status,
                    statusText: this.statusText,
                    headers: this.headers
                });
            },
            
            arrayBuffer: function() {
                this._bodyUsed = true;
                if (typeof this._body === 'string') {
                    const encoder = new TextEncoder();
                    return Promise.resolve(encoder.encode(this._body).buffer);
                }
                return Promise.resolve(new ArrayBuffer(0));
            },
            
            blob: function() {
                this._bodyUsed = true;
                return Promise.resolve(new Blob([this._body || '']));
            },
            
            formData: function() {
                this._bodyUsed = true;
                return Promise.resolve(new FormData());
            },
            
            json: function() {
                this._bodyUsed = true;
                try {
                    const parsed = typeof this._body === 'string' ? JSON.parse(this._body) : this._body;
                    return Promise.resolve(parsed);
                } catch (e) {
                    return Promise.reject(new SyntaxError('Invalid JSON'));
                }
            },
            
            text: function() {
                this._bodyUsed = true;
                return Promise.resolve(String(this._body || ''));
            }
        };
        
        Response.error = function() {
            const response = new Response(null, { status: 0, statusText: '' });
            response.type = 'error';
            return response;
        };
        
        Response.redirect = function(url, status) {
            status = status || 302;
            return new Response(null, {
                status: status,
                headers: { Location: url }
            });
        };
        
        Response.json = function(data, init) {
            init = init || {};
            const headers = new Headers(init.headers);
            if (!headers.has('content-type')) {
                headers.set('content-type', 'application/json');
            }
            return new Response(JSON.stringify(data), {
                ...init,
                headers: headers
            });
        };
        
        window.Response = Response;
    }
    
    // ==================== Request 增强 ====================
    if (!window.Request) {
        function Request(input, init) {
            init = init || {};
            
            if (input instanceof Request) {
                this.url = input.url;
                this.method = input.method;
                this.headers = new Headers(input.headers);
                this.body = input.body;
                this.mode = input.mode;
                this.credentials = input.credentials;
                this.cache = input.cache;
                this.redirect = input.redirect;
                this.referrer = input.referrer;
                this.referrerPolicy = input.referrerPolicy;
                this.integrity = input.integrity;
            } else {
                this.url = String(input);
            }
            
            if (init.method) this.method = init.method.toUpperCase();
            else if (!this.method) this.method = 'GET';
            
            if (init.headers) this.headers = new Headers(init.headers);
            else if (!this.headers) this.headers = new Headers();
            
            if (init.body !== undefined) this.body = init.body;
            
            this.mode = init.mode || this.mode || 'cors';
            this.credentials = init.credentials || this.credentials || 'same-origin';
            this.cache = init.cache || this.cache || 'default';
            this.redirect = init.redirect || this.redirect || 'follow';
            this.referrer = init.referrer !== undefined ? init.referrer : (this.referrer || 'about:client');
            this.referrerPolicy = init.referrerPolicy || this.referrerPolicy || '';
            this.integrity = init.integrity || this.integrity || '';
            this.signal = init.signal || null;
            
            this._bodyUsed = false;
        }
        
        Request.prototype = {
            get bodyUsed() { return this._bodyUsed; },
            
            clone: function() {
                if (this._bodyUsed) {
                    throw new TypeError('Already read');
                }
                return new Request(this);
            },
            
            arrayBuffer: function() {
                this._bodyUsed = true;
                return Promise.resolve(new ArrayBuffer(0));
            },
            
            blob: function() {
                this._bodyUsed = true;
                return Promise.resolve(new Blob([]));
            },
            
            formData: function() {
                this._bodyUsed = true;
                return Promise.resolve(new FormData());
            },
            
            json: function() {
                this._bodyUsed = true;
                return Promise.resolve({});
            },
            
            text: function() {
                this._bodyUsed = true;
                return Promise.resolve('');
            }
        };
        
        window.Request = Request;
    }
    
    // ==================== AbortController ====================
    if (!window.AbortController) {
        function AbortController() {
            this.signal = new AbortSignal();
        }
        
        AbortController.prototype = {
            abort: function(reason) {
                this.signal._aborted = true;
                this.signal._reason = reason;
                this.signal.dispatchEvent(new Event('abort'));
            }
        };
        
        function AbortSignal() {
            this._aborted = false;
            this._reason = undefined;
            this._listeners = {};
        }
        
        AbortSignal.prototype = {
            get aborted() { return this._aborted; },
            get reason() { return this._reason; },
            
            throwIfAborted: function() {
                if (this._aborted) {
                    throw this._reason || new DOMException('The operation was aborted.', 'AbortError');
                }
            },
            
            addEventListener: function(type, listener) {
                if (!this._listeners[type]) this._listeners[type] = [];
                this._listeners[type].push(listener);
            },
            
            removeEventListener: function(type, listener) {
                if (this._listeners[type]) {
                    this._listeners[type] = this._listeners[type].filter(l => l !== listener);
                }
            },
            
            dispatchEvent: function(event) {
                const listeners = this._listeners[event.type] || [];
                listeners.forEach(l => l.call(this, event));
            }
        };
        
        AbortSignal.abort = function(reason) {
            const controller = new AbortController();
            controller.abort(reason);
            return controller.signal;
        };
        
        AbortSignal.timeout = function(milliseconds) {
            const controller = new AbortController();
            setTimeout(() => {
                controller.abort(new DOMException('The operation timed out.', 'TimeoutError'));
            }, milliseconds);
            return controller.signal;
        };
        
        AbortSignal.any = function(signals) {
            const controller = new AbortController();
            signals.forEach(signal => {
                if (signal.aborted) {
                    controller.abort(signal.reason);
                } else {
                    signal.addEventListener('abort', () => {
                        controller.abort(signal.reason);
                    });
                }
            });
            return controller.signal;
        };
        
        window.AbortController = AbortController;
        window.AbortSignal = AbortSignal;
    }
    
    console.log('[network.js] 增强版网络请求模拟加载完成');
    
})();
