/**
 * @env-module elements
 * @description HTML元素类型库 - 完整的HTML元素模拟（带监控）
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
        popChain: function() {}
    };
    
    // ==================== 获取基础类 ====================
    const Element = window.Element;
    const Node = window.Node;
    
    if (!Element) {
        console.error('[elements.js] Element class not found, please load document.js first');
        return;
    }
    
    // ==================== 辅助函数 ====================
    function createProxiedElement(element, elementType) {
        const proxy = new Proxy(element, {
            get: function(target, prop) {
                if (typeof prop === 'symbol') return target[prop];
                
                // 检查 mock
                const mockPath = `${elementType}.${prop}`;
                if (Monitor.hasMock(mockPath)) {
                    const mock = Monitor.getMock(mockPath);
                    if (mock) {
                        Monitor.log('Element', 'mockAccess', { type: elementType, prop });
                        return mock.value;
                    }
                }
                
                const value = target[prop];
                
                // 记录 undefined 访问
                if (value === undefined && !(prop in target)) {
                    Monitor.logUndefined(`${elementType}.${prop}`, {
                        tagName: target.tagName,
                        elementId: target.__id__
                    });
                }
                
                // 包装方法调用
                if (typeof value === 'function') {
                    return function(...args) {
                        Monitor.pushChain(`${elementType}.${prop}`);
                        
                        // 检查方法 mock
                        const mockResult = Monitor.executeMock(`${elementType}.${prop}`, args, target);
                        if (mockResult.mocked) {
                            Monitor.popChain();
                            return mockResult.result;
                        }
                        
                        const result = value.apply(target, args);
                        Monitor.logCall(`${elementType}.${prop}`, args, result, {
                            tagName: target.tagName,
                            elementId: target.__id__
                        });
                        Monitor.popChain();
                        return result;
                    };
                }
                
                return value;
            },
            set: function(target, prop, value) {
                Monitor.log('Element', 'setProperty', {
                    type: elementType,
                    prop: prop,
                    value: Monitor._serializeValue ? Monitor._serializeValue(value) : value,
                    tagName: target.tagName,
                    elementId: target.__id__
                });
                target[prop] = value;
                return true;
            }
        });
        
        return proxy;
    }
    
    // ==================== HTMLElement 基类 ====================
    function HTMLElement(tagName) {
        Element.call(this, tagName || 'div');
        this.hidden = false;
        this.title = '';
        this.lang = '';
        this.dir = '';
        this.tabIndex = -1;
        this.accessKey = '';
        this.accessKeyLabel = '';
        this.draggable = false;
        this.spellcheck = true;
        this.autocapitalize = '';
        this.contentEditable = 'inherit';
        this.isContentEditable = false;
        this.inputMode = '';
        this.enterKeyHint = '';
        this.nonce = '';
        this.autofocus = false;
        this.inert = false;
        
        // 事件处理器
        this.onclick = null;
        this.ondblclick = null;
        this.onmousedown = null;
        this.onmouseup = null;
        this.onmouseover = null;
        this.onmouseout = null;
        this.onmousemove = null;
        this.onmouseenter = null;
        this.onmouseleave = null;
        this.onkeydown = null;
        this.onkeyup = null;
        this.onkeypress = null;
        this.onfocus = null;
        this.onblur = null;
        this.onchange = null;
        this.oninput = null;
        this.onsubmit = null;
        this.onreset = null;
        this.onscroll = null;
        this.onload = null;
        this.onerror = null;
        this.oncontextmenu = null;
        this.ondrag = null;
        this.ondragstart = null;
        this.ondragend = null;
        this.ondragover = null;
        this.ondragenter = null;
        this.ondragleave = null;
        this.ondrop = null;
        this.ontouchstart = null;
        this.ontouchend = null;
        this.ontouchmove = null;
        this.ontouchcancel = null;
        this.onpointerdown = null;
        this.onpointerup = null;
        this.onpointermove = null;
        this.onpointerenter = null;
        this.onpointerleave = null;
        this.onpointercancel = null;
        this.onanimationstart = null;
        this.onanimationend = null;
        this.onanimationiteration = null;
        this.ontransitionend = null;
    }
    
    HTMLElement.prototype = Object.create(Element.prototype);
    HTMLElement.prototype.constructor = HTMLElement;
    
    // HTMLElement 方法
    HTMLElement.prototype.click = function() {
        Monitor.logCall('HTMLElement.click', [], null, { elementId: this.__id__ });
        if (this.onclick) this.onclick(new Event('click'));
    };
    
    HTMLElement.prototype.focus = function() {
        Monitor.logCall('HTMLElement.focus', [], null, { elementId: this.__id__ });
        if (this.onfocus) this.onfocus(new Event('focus'));
    };
    
    HTMLElement.prototype.blur = function() {
        Monitor.logCall('HTMLElement.blur', [], null, { elementId: this.__id__ });
        if (this.onblur) this.onblur(new Event('blur'));
    };
    
    HTMLElement.prototype.attachInternals = function() {
        Monitor.logCall('HTMLElement.attachInternals', [], null, { elementId: this.__id__ });
        return {
            form: null,
            labels: [],
            validationMessage: '',
            validity: { valid: true },
            willValidate: false,
            setFormValue: function() {},
            setValidity: function() {},
            checkValidity: function() { return true; },
            reportValidity: function() { return true; }
        };
    };
    
    window.HTMLElement = HTMLElement;
    
    // ==================== HTMLDivElement ====================
    function HTMLDivElement() {
        HTMLElement.call(this, 'div');
        this.align = '';
    }
    HTMLDivElement.prototype = Object.create(HTMLElement.prototype);
    HTMLDivElement.prototype.constructor = HTMLDivElement;
    window.HTMLDivElement = HTMLDivElement;
    
    // ==================== HTMLSpanElement ====================
    function HTMLSpanElement() {
        HTMLElement.call(this, 'span');
    }
    HTMLSpanElement.prototype = Object.create(HTMLElement.prototype);
    HTMLSpanElement.prototype.constructor = HTMLSpanElement;
    window.HTMLSpanElement = HTMLSpanElement;
    
    // ==================== HTMLParagraphElement ====================
    function HTMLParagraphElement() {
        HTMLElement.call(this, 'p');
        this.align = '';
    }
    HTMLParagraphElement.prototype = Object.create(HTMLElement.prototype);
    HTMLParagraphElement.prototype.constructor = HTMLParagraphElement;
    window.HTMLParagraphElement = HTMLParagraphElement;
    
    // ==================== HTMLHeadingElement (h1-h6) ====================
    function HTMLHeadingElement(level) {
        HTMLElement.call(this, 'h' + (level || 1));
        this.align = '';
    }
    HTMLHeadingElement.prototype = Object.create(HTMLElement.prototype);
    HTMLHeadingElement.prototype.constructor = HTMLHeadingElement;
    window.HTMLHeadingElement = HTMLHeadingElement;
    
    // ==================== HTMLAnchorElement ====================
    function HTMLAnchorElement() {
        HTMLElement.call(this, 'a');
        this.href = '';
        this.target = '';
        this.download = '';
        this.rel = '';
        this.relList = new DOMTokenList(this, 'rel');
        this.hreflang = '';
        this.type = '';
        this.text = '';
        this.referrerPolicy = '';
        this.ping = '';
        this.origin = '';
        this.protocol = '';
        this.username = '';
        this.password = '';
        this.host = '';
        this.hostname = '';
        this.port = '';
        this.pathname = '';
        this.search = '';
        this.hash = '';
    }
    HTMLAnchorElement.prototype = Object.create(HTMLElement.prototype);
    HTMLAnchorElement.prototype.constructor = HTMLAnchorElement;
    HTMLAnchorElement.prototype.toString = function() { return this.href; };
    window.HTMLAnchorElement = HTMLAnchorElement;
    
    // ==================== HTMLImageElement ====================
    function HTMLImageElement() {
        HTMLElement.call(this, 'img');
        this._src = '';
        this.srcset = '';
        this.sizes = '';
        this.alt = '';
        this.crossOrigin = null;
        this.useMap = '';
        this.isMap = false;
        this.width = 0;
        this.height = 0;
        this.naturalWidth = 0;
        this.naturalHeight = 0;
        this.complete = true;
        this.currentSrc = '';
        this.referrerPolicy = '';
        this.decoding = 'auto';
        this.loading = 'auto';
        this.fetchPriority = 'auto';
        this.x = 0;
        this.y = 0;

        const self = this;
        Object.defineProperty(this, 'src', {
            configurable: true,
            enumerable: true,
            get: function() { return self._src || ''; },
            set: function(value) {
                self._src = String(value);
                self.currentSrc = self._src;
                setTimeout(() => {
                    self.complete = true;
                    self.naturalWidth = self.naturalWidth || 100;
                    self.naturalHeight = self.naturalHeight || 100;
                    const loadEvent = typeof Event === 'function' ? new Event('load') : { type: 'load' };
                    loadEvent.target = self;
                    loadEvent.currentTarget = self;
                    try {
                        if (self.onload) self.onload.call(self, loadEvent);
                    } catch (_) {}
                    try {
                        if (typeof self.dispatchEvent === 'function') self.dispatchEvent(loadEvent);
                    } catch (_) {}
                }, 0);
            }
        });
    }
    HTMLImageElement.prototype = Object.create(HTMLElement.prototype);
    HTMLImageElement.prototype.constructor = HTMLImageElement;
    HTMLImageElement.prototype.decode = function() { 
        Monitor.logCall('HTMLImageElement.decode', [], 'Promise', { elementId: this.__id__ });
        return Promise.resolve(); 
    };
    window.HTMLImageElement = HTMLImageElement;
    function Image(width, height) {
        const img = new HTMLImageElement();
        if (width !== undefined) img.width = width;
        if (height !== undefined) img.height = height;
        Monitor.logCreate('img', img, { width, height });
        return img;
    }
    Image.prototype = HTMLImageElement.prototype;
    window.Image = Image;
    
    // ==================== HTMLInputElement ====================
    function HTMLInputElement() {
        HTMLElement.call(this, 'input');
        this.accept = '';
        this.alt = '';
        this.autocomplete = '';
        this.checked = false;
        this.defaultChecked = false;
        this.defaultValue = '';
        this.dirName = '';
        this.disabled = false;
        this.files = null;
        this.form = null;
        this.formAction = '';
        this.formEnctype = '';
        this.formMethod = '';
        this.formNoValidate = false;
        this.formTarget = '';
        this.height = 0;
        this.indeterminate = false;
        this.labels = [];
        this.list = null;
        this.max = '';
        this.maxLength = -1;
        this.min = '';
        this.minLength = -1;
        this.multiple = false;
        this.name = '';
        this.pattern = '';
        this.placeholder = '';
        this.readOnly = false;
        this.required = false;
        this.selectionDirection = null;
        this.selectionEnd = null;
        this.selectionStart = null;
        this.size = 20;
        this.src = '';
        this.step = '';
        this.type = 'text';
        this.validationMessage = '';
        this.validity = {
            badInput: false,
            customError: false,
            patternMismatch: false,
            rangeOverflow: false,
            rangeUnderflow: false,
            stepMismatch: false,
            tooLong: false,
            tooShort: false,
            typeMismatch: false,
            valid: true,
            valueMissing: false
        };
        this.value = '';
        this.valueAsDate = null;
        this.valueAsNumber = NaN;
        this.width = 0;
        this.willValidate = true;
    }
    HTMLInputElement.prototype = Object.create(HTMLElement.prototype);
    HTMLInputElement.prototype.constructor = HTMLInputElement;
    HTMLInputElement.prototype.checkValidity = function() { return true; };
    HTMLInputElement.prototype.reportValidity = function() { return true; };
    HTMLInputElement.prototype.select = function() {
        Monitor.logCall('HTMLInputElement.select', [], null, { elementId: this.__id__ });
    };
    HTMLInputElement.prototype.setCustomValidity = function(message) {
        this.validationMessage = message;
        this.validity.customError = !!message;
        this.validity.valid = !message;
    };
    HTMLInputElement.prototype.setRangeText = function(replacement, start, end, selectMode) {
        Monitor.logCall('HTMLInputElement.setRangeText', [replacement, start, end, selectMode], null);
    };
    HTMLInputElement.prototype.setSelectionRange = function(start, end, direction) {
        this.selectionStart = start;
        this.selectionEnd = end;
        this.selectionDirection = direction || 'none';
    };
    HTMLInputElement.prototype.stepDown = function(n) { };
    HTMLInputElement.prototype.stepUp = function(n) { };
    HTMLInputElement.prototype.showPicker = function() { };
    window.HTMLInputElement = HTMLInputElement;
    
    // ==================== HTMLButtonElement ====================
    function HTMLButtonElement() {
        HTMLElement.call(this, 'button');
        this.disabled = false;
        this.form = null;
        this.formAction = '';
        this.formEnctype = '';
        this.formMethod = '';
        this.formNoValidate = false;
        this.formTarget = '';
        this.labels = [];
        this.name = '';
        this.type = 'submit';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.value = '';
        this.willValidate = true;
    }
    HTMLButtonElement.prototype = Object.create(HTMLElement.prototype);
    HTMLButtonElement.prototype.constructor = HTMLButtonElement;
    HTMLButtonElement.prototype.checkValidity = function() { return true; };
    HTMLButtonElement.prototype.reportValidity = function() { return true; };
    HTMLButtonElement.prototype.setCustomValidity = function(message) { };
    window.HTMLButtonElement = HTMLButtonElement;
    
    // ==================== HTMLSelectElement ====================
    function HTMLSelectElement() {
        HTMLElement.call(this, 'select');
        this.autocomplete = '';
        this.disabled = false;
        this.form = null;
        this.labels = [];
        this.length = 0;
        this.multiple = false;
        this.name = '';
        this.options = [];
        this.required = false;
        this.selectedIndex = -1;
        this.selectedOptions = [];
        this.size = 0;
        this.type = 'select-one';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.value = '';
        this.willValidate = true;
    }
    HTMLSelectElement.prototype = Object.create(HTMLElement.prototype);
    HTMLSelectElement.prototype.constructor = HTMLSelectElement;
    HTMLSelectElement.prototype.add = function(option, before) {
        this.options.push(option);
        this.length = this.options.length;
    };
    HTMLSelectElement.prototype.remove = function(index) {
        this.options.splice(index, 1);
        this.length = this.options.length;
    };
    HTMLSelectElement.prototype.item = function(index) { return this.options[index] || null; };
    HTMLSelectElement.prototype.namedItem = function(name) { 
        return this.options.find(o => o.name === name || o.id === name) || null; 
    };
    HTMLSelectElement.prototype.checkValidity = function() { return true; };
    HTMLSelectElement.prototype.reportValidity = function() { return true; };
    HTMLSelectElement.prototype.setCustomValidity = function(message) { };
    window.HTMLSelectElement = HTMLSelectElement;
    
    // ==================== HTMLOptionElement ====================
    function HTMLOptionElement() {
        HTMLElement.call(this, 'option');
        this.defaultSelected = false;
        this.disabled = false;
        this.form = null;
        this.index = 0;
        this.label = '';
        this.selected = false;
        this.text = '';
        this.value = '';
    }
    HTMLOptionElement.prototype = Object.create(HTMLElement.prototype);
    HTMLOptionElement.prototype.constructor = HTMLOptionElement;
    window.HTMLOptionElement = HTMLOptionElement;
    window.Option = function(text, value, defaultSelected, selected) {
        const option = new HTMLOptionElement();
        if (text !== undefined) option.text = text;
        if (value !== undefined) option.value = value;
        if (defaultSelected !== undefined) option.defaultSelected = defaultSelected;
        if (selected !== undefined) option.selected = selected;
        return option;
    };
    
    // ==================== HTMLTextAreaElement ====================
    function HTMLTextAreaElement() {
        HTMLElement.call(this, 'textarea');
        this.autocomplete = '';
        this.cols = 20;
        this.defaultValue = '';
        this.dirName = '';
        this.disabled = false;
        this.form = null;
        this.labels = [];
        this.maxLength = -1;
        this.minLength = -1;
        this.name = '';
        this.placeholder = '';
        this.readOnly = false;
        this.required = false;
        this.rows = 2;
        this.selectionDirection = 'none';
        this.selectionEnd = 0;
        this.selectionStart = 0;
        this.textLength = 0;
        this.type = 'textarea';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.value = '';
        this.willValidate = true;
        this.wrap = 'soft';
    }
    HTMLTextAreaElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTextAreaElement.prototype.constructor = HTMLTextAreaElement;
    HTMLTextAreaElement.prototype.checkValidity = function() { return true; };
    HTMLTextAreaElement.prototype.reportValidity = function() { return true; };
    HTMLTextAreaElement.prototype.select = function() { };
    HTMLTextAreaElement.prototype.setCustomValidity = function(message) { };
    HTMLTextAreaElement.prototype.setRangeText = function() { };
    HTMLTextAreaElement.prototype.setSelectionRange = function(start, end, direction) {
        this.selectionStart = start;
        this.selectionEnd = end;
        this.selectionDirection = direction || 'none';
    };
    window.HTMLTextAreaElement = HTMLTextAreaElement;
    
    // ==================== HTMLFormElement ====================
    function HTMLFormElement() {
        HTMLElement.call(this, 'form');
        this.acceptCharset = '';
        this.action = '';
        this.autocomplete = 'on';
        this.elements = [];
        this.encoding = '';
        this.enctype = 'application/x-www-form-urlencoded';
        this.length = 0;
        this.method = 'get';
        this.name = '';
        this.noValidate = false;
        this.target = '';
    }
    HTMLFormElement.prototype = Object.create(HTMLElement.prototype);
    HTMLFormElement.prototype.constructor = HTMLFormElement;
    HTMLFormElement.prototype.checkValidity = function() { return true; };
    HTMLFormElement.prototype.reportValidity = function() { return true; };
    HTMLFormElement.prototype.reset = function() {
        Monitor.logCall('HTMLFormElement.reset', [], null, { elementId: this.__id__ });
        if (this.onreset) this.onreset(new Event('reset'));
    };
    HTMLFormElement.prototype.submit = function() {
        Monitor.logCall('HTMLFormElement.submit', [], null, { elementId: this.__id__ });
        if (this.onsubmit) this.onsubmit(new Event('submit'));
    };
    HTMLFormElement.prototype.requestSubmit = function(submitter) {
        Monitor.logCall('HTMLFormElement.requestSubmit', [submitter], null);
        if (this.onsubmit) this.onsubmit(new Event('submit'));
    };
    window.HTMLFormElement = HTMLFormElement;
    
    // ==================== HTMLLabelElement ====================
    function HTMLLabelElement() {
        HTMLElement.call(this, 'label');
        this.control = null;
        this.form = null;
        this.htmlFor = '';
    }
    HTMLLabelElement.prototype = Object.create(HTMLElement.prototype);
    HTMLLabelElement.prototype.constructor = HTMLLabelElement;
    window.HTMLLabelElement = HTMLLabelElement;
    
    // ==================== HTMLScriptElement ====================
    function HTMLScriptElement() {
        HTMLElement.call(this, 'script');
        this.async = false;
        this.blocking = '';
        this.charset = '';
        this.crossOrigin = null;
        this.defer = false;
        this.event = '';
        this.fetchPriority = 'auto';
        this.htmlFor = '';
        this.integrity = '';
        this.noModule = false;
        this.referrerPolicy = '';
        this.src = '';
        this.text = '';
        this.type = '';
    }
    HTMLScriptElement.prototype = Object.create(HTMLElement.prototype);
    HTMLScriptElement.prototype.constructor = HTMLScriptElement;
    HTMLScriptElement.supports = function(type) {
        return type === 'classic' || type === 'module' || type === 'importmap';
    };
    window.HTMLScriptElement = HTMLScriptElement;
    
    // ==================== HTMLStyleElement ====================
    function HTMLStyleElement() {
        HTMLElement.call(this, 'style');
        this.disabled = false;
        this.media = '';
        this.type = 'text/css';
        this.sheet = null;
    }
    HTMLStyleElement.prototype = Object.create(HTMLElement.prototype);
    HTMLStyleElement.prototype.constructor = HTMLStyleElement;
    window.HTMLStyleElement = HTMLStyleElement;
    
    // ==================== HTMLLinkElement ====================
    function HTMLLinkElement() {
        HTMLElement.call(this, 'link');
        this.as = '';
        this.blocking = '';
        this.crossOrigin = null;
        this.disabled = false;
        this.fetchPriority = 'auto';
        this.href = '';
        this.hreflang = '';
        this.imageSizes = '';
        this.imageSrcset = '';
        this.integrity = '';
        this.media = '';
        this.referrerPolicy = '';
        this.rel = '';
        this.relList = new DOMTokenList(this, 'rel');
        this.sheet = null;
        this.sizes = '';
        this.type = '';
    }
    HTMLLinkElement.prototype = Object.create(HTMLElement.prototype);
    HTMLLinkElement.prototype.constructor = HTMLLinkElement;
    window.HTMLLinkElement = HTMLLinkElement;
    
    // ==================== HTMLMetaElement ====================
    function HTMLMetaElement() {
        HTMLElement.call(this, 'meta');
        this.content = '';
        this.httpEquiv = '';
        this.media = '';
        this.name = '';
        this.scheme = '';
    }
    HTMLMetaElement.prototype = Object.create(HTMLElement.prototype);
    HTMLMetaElement.prototype.constructor = HTMLMetaElement;
    window.HTMLMetaElement = HTMLMetaElement;
    
    // ==================== HTMLTitleElement ====================
    function HTMLTitleElement() {
        HTMLElement.call(this, 'title');
        this.text = '';
    }
    HTMLTitleElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTitleElement.prototype.constructor = HTMLTitleElement;
    window.HTMLTitleElement = HTMLTitleElement;
    
    // ==================== HTMLBaseElement ====================
    function HTMLBaseElement() {
        HTMLElement.call(this, 'base');
        this.href = '';
        this.target = '';
    }
    HTMLBaseElement.prototype = Object.create(HTMLElement.prototype);
    HTMLBaseElement.prototype.constructor = HTMLBaseElement;
    window.HTMLBaseElement = HTMLBaseElement;
    
    // ==================== HTMLCanvasElement ====================
    function HTMLCanvasElement() {
        HTMLElement.call(this, 'canvas');
        this.width = 300;
        this.height = 150;
        this._context2d = null;
        this._contextWebGL = null;
    }
    HTMLCanvasElement.prototype = Object.create(HTMLElement.prototype);
    HTMLCanvasElement.prototype.constructor = HTMLCanvasElement;
    
    HTMLCanvasElement.prototype.getContext = function(contextId, options) {
        Monitor.logCall('HTMLCanvasElement.getContext', [contextId, options], '[Context]', {
            elementId: this.__id__
        });
        
        // 检查 mock
        const mock = Monitor.executeMock('HTMLCanvasElement.getContext', [contextId, options], this);
        if (mock.mocked) return mock.result;
        
        if (contextId === '2d') {
            if (!this._context2d) {
                this._context2d = new CanvasRenderingContext2D(this);
            }
            return this._context2d;
        }
        if (contextId === 'webgl' || contextId === 'experimental-webgl') {
            if (!this._contextWebGL) {
                this._contextWebGL = new WebGLRenderingContext(this);
            }
            return this._contextWebGL;
        }
        if (contextId === 'webgl2') {
            return new WebGL2RenderingContext(this);
        }
        return null;
    };
    
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        Monitor.logCall('HTMLCanvasElement.toDataURL', [type, quality], 'data:image/png;base64,...');
        const mock = Monitor.executeMock('HTMLCanvasElement.toDataURL', [type, quality], this);
        if (mock.mocked) return mock.result;
        return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
    };
    
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
        Monitor.logCall('HTMLCanvasElement.toBlob', [callback, type, quality], null);
        const mock = Monitor.executeMock('HTMLCanvasElement.toBlob', [callback, type, quality], this);
        if (mock.mocked) {
            if (callback) callback(mock.result);
            return;
        }
        if (callback) {
            callback(new Blob([''], { type: type || 'image/png' }));
        }
    };
    
    HTMLCanvasElement.prototype.captureStream = function(frameRate) {
        Monitor.logCall('HTMLCanvasElement.captureStream', [frameRate], '[MediaStream]');
        return {};
    };
    
    HTMLCanvasElement.prototype.transferControlToOffscreen = function() {
        Monitor.logCall('HTMLCanvasElement.transferControlToOffscreen', [], '[OffscreenCanvas]');
        return {};
    };
    
    window.HTMLCanvasElement = HTMLCanvasElement;
    
    // ==================== CanvasRenderingContext2D ====================
    function CanvasRenderingContext2D(canvas) {
        this.canvas = canvas;
        
        // 状态
        this.fillStyle = '#000000';
        this.strokeStyle = '#000000';
        this.lineWidth = 1;
        this.lineCap = 'butt';
        this.lineJoin = 'miter';
        this.miterLimit = 10;
        this.lineDashOffset = 0;
        this.font = '10px sans-serif';
        this.textAlign = 'start';
        this.textBaseline = 'alphabetic';
        this.direction = 'ltr';
        this.globalAlpha = 1;
        this.globalCompositeOperation = 'source-over';
        this.imageSmoothingEnabled = true;
        this.imageSmoothingQuality = 'low';
        this.shadowBlur = 0;
        this.shadowColor = 'rgba(0, 0, 0, 0)';
        this.shadowOffsetX = 0;
        this.shadowOffsetY = 0;
        this.filter = 'none';
        
        // 状态栈
        this._stateStack = [];
    }
    
    // Canvas 2D 方法
    const context2dMethods = [
        'arc', 'arcTo', 'beginPath', 'bezierCurveTo', 'clearRect', 'clip',
        'closePath', 'createConicGradient', 'createImageData', 'createLinearGradient',
        'createPattern', 'createRadialGradient', 'drawFocusIfNeeded', 'drawImage',
        'ellipse', 'fill', 'fillRect', 'fillText', 'getContextAttributes',
        'getImageData', 'getLineDash', 'getTransform', 'isContextLost', 'isPointInPath',
        'isPointInStroke', 'lineTo', 'measureText', 'moveTo', 'putImageData',
        'quadraticCurveTo', 'rect', 'reset', 'resetTransform', 'restore',
        'rotate', 'roundRect', 'save', 'scale', 'scrollPathIntoView', 'setLineDash',
        'setTransform', 'stroke', 'strokeRect', 'strokeText', 'transform', 'translate'
    ];
    
    context2dMethods.forEach(method => {
        CanvasRenderingContext2D.prototype[method] = function(...args) {
            Monitor.logCall(`CanvasRenderingContext2D.${method}`, args, null, {
                canvasId: this.canvas?.__id__
            });
            
            const mock = Monitor.executeMock(`CanvasRenderingContext2D.${method}`, args, this);
            if (mock.mocked) return mock.result;
            
            // 特殊处理某些方法
            if (method === 'measureText') {
                return {
                    width: args[0]?.length * 8 || 0,
                    actualBoundingBoxAscent: 10,
                    actualBoundingBoxDescent: 2,
                    actualBoundingBoxLeft: 0,
                    actualBoundingBoxRight: args[0]?.length * 8 || 0,
                    fontBoundingBoxAscent: 12,
                    fontBoundingBoxDescent: 3,
                    emHeightAscent: 10,
                    emHeightDescent: 2,
                    hangingBaseline: 10,
                    alphabeticBaseline: 0,
                    ideographicBaseline: -2
                };
            }
            if (method === 'getImageData') {
                const width = args[2] || 1;
                const height = args[3] || 1;
                return {
                    data: new Uint8ClampedArray(width * height * 4),
                    width: width,
                    height: height,
                    colorSpace: 'srgb'
                };
            }
            if (method === 'createImageData') {
                const width = typeof args[0] === 'number' ? args[0] : args[0]?.width || 1;
                const height = typeof args[1] === 'number' ? args[1] : args[0]?.height || 1;
                return {
                    data: new Uint8ClampedArray(width * height * 4),
                    width: width,
                    height: height,
                    colorSpace: 'srgb'
                };
            }
            if (method === 'createLinearGradient' || method === 'createRadialGradient' || method === 'createConicGradient') {
                return {
                    addColorStop: function() {}
                };
            }
            if (method === 'createPattern') {
                return {};
            }
            if (method === 'save') {
                this._stateStack.push({});
                return;
            }
            if (method === 'restore') {
                this._stateStack.pop();
                return;
            }
            if (method === 'getLineDash') {
                return [];
            }
            if (method === 'getTransform') {
                return new DOMMatrix();
            }
            if (method === 'isPointInPath' || method === 'isPointInStroke') {
                return false;
            }
            if (method === 'getContextAttributes') {
                return {
                    alpha: true,
                    colorSpace: 'srgb',
                    desynchronized: false,
                    willReadFrequently: false
                };
            }
            if (method === 'isContextLost') {
                return false;
            }
            
            return undefined;
        };
    });
    
    window.CanvasRenderingContext2D = CanvasRenderingContext2D;
    
    // ==================== WebGLRenderingContext ====================
    function WebGLRenderingContext(canvas) {
        this.canvas = canvas;
        this.drawingBufferWidth = canvas.width;
        this.drawingBufferHeight = canvas.height;
        this.drawingBufferColorSpace = 'srgb';
        
        // WebGL 常量
        this.DEPTH_BUFFER_BIT = 0x00000100;
        this.STENCIL_BUFFER_BIT = 0x00000400;
        this.COLOR_BUFFER_BIT = 0x00004000;
        this.POINTS = 0x0000;
        this.LINES = 0x0001;
        this.LINE_LOOP = 0x0002;
        this.LINE_STRIP = 0x0003;
        this.TRIANGLES = 0x0004;
        this.TRIANGLE_STRIP = 0x0005;
        this.TRIANGLE_FAN = 0x0006;
        // ... 更多常量
    }
    
    // WebGL 方法
    const webglMethods = [
        'activeTexture', 'attachShader', 'bindAttribLocation', 'bindBuffer',
        'bindFramebuffer', 'bindRenderbuffer', 'bindTexture', 'blendColor',
        'blendEquation', 'blendEquationSeparate', 'blendFunc', 'blendFuncSeparate',
        'bufferData', 'bufferSubData', 'checkFramebufferStatus', 'clear',
        'clearColor', 'clearDepth', 'clearStencil', 'colorMask', 'compileShader',
        'compressedTexImage2D', 'compressedTexSubImage2D', 'copyTexImage2D',
        'copyTexSubImage2D', 'createBuffer', 'createFramebuffer', 'createProgram',
        'createRenderbuffer', 'createShader', 'createTexture', 'cullFace',
        'deleteBuffer', 'deleteFramebuffer', 'deleteProgram', 'deleteRenderbuffer',
        'deleteShader', 'deleteTexture', 'depthFunc', 'depthMask', 'depthRange',
        'detachShader', 'disable', 'disableVertexAttribArray', 'drawArrays',
        'drawElements', 'enable', 'enableVertexAttribArray', 'finish', 'flush',
        'framebufferRenderbuffer', 'framebufferTexture2D', 'frontFace',
        'generateMipmap', 'getActiveAttrib', 'getActiveUniform', 'getAttachedShaders',
        'getAttribLocation', 'getBufferParameter', 'getContextAttributes', 'getError',
        'getExtension', 'getFramebufferAttachmentParameter', 'getParameter',
        'getProgramInfoLog', 'getProgramParameter', 'getRenderbufferParameter',
        'getShaderInfoLog', 'getShaderParameter', 'getShaderPrecisionFormat',
        'getShaderSource', 'getSupportedExtensions', 'getTexParameter',
        'getUniform', 'getUniformLocation', 'getVertexAttrib', 'getVertexAttribOffset',
        'hint', 'isBuffer', 'isContextLost', 'isEnabled', 'isFramebuffer',
        'isProgram', 'isRenderbuffer', 'isShader', 'isTexture', 'lineWidth',
        'linkProgram', 'pixelStorei', 'polygonOffset', 'readPixels',
        'renderbufferStorage', 'sampleCoverage', 'scissor', 'shaderSource',
        'stencilFunc', 'stencilFuncSeparate', 'stencilMask', 'stencilMaskSeparate',
        'stencilOp', 'stencilOpSeparate', 'texImage2D', 'texParameterf',
        'texParameteri', 'texSubImage2D', 'uniform1f', 'uniform1fv', 'uniform1i',
        'uniform1iv', 'uniform2f', 'uniform2fv', 'uniform2i', 'uniform2iv',
        'uniform3f', 'uniform3fv', 'uniform3i', 'uniform3iv', 'uniform4f',
        'uniform4fv', 'uniform4i', 'uniform4iv', 'uniformMatrix2fv',
        'uniformMatrix3fv', 'uniformMatrix4fv', 'useProgram', 'validateProgram',
        'vertexAttrib1f', 'vertexAttrib1fv', 'vertexAttrib2f', 'vertexAttrib2fv',
        'vertexAttrib3f', 'vertexAttrib3fv', 'vertexAttrib4f', 'vertexAttrib4fv',
        'vertexAttribPointer', 'viewport'
    ];
    
    webglMethods.forEach(method => {
        WebGLRenderingContext.prototype[method] = function(...args) {
            Monitor.logCall(`WebGLRenderingContext.${method}`, args, null, {
                canvasId: this.canvas?.__id__
            });
            
            const mock = Monitor.executeMock(`WebGLRenderingContext.${method}`, args, this);
            if (mock.mocked) return mock.result;
            
            // 特殊处理
            if (method === 'createShader') return { __type__: 'WebGLShader' };
            if (method === 'createProgram') return { __type__: 'WebGLProgram' };
            if (method === 'createBuffer') return { __type__: 'WebGLBuffer' };
            if (method === 'createTexture') return { __type__: 'WebGLTexture' };
            if (method === 'createFramebuffer') return { __type__: 'WebGLFramebuffer' };
            if (method === 'createRenderbuffer') return { __type__: 'WebGLRenderbuffer' };
            if (method === 'getUniformLocation') return { __type__: 'WebGLUniformLocation' };
            if (method === 'getAttribLocation') return 0;
            if (method === 'getParameter') return null;
            if (method === 'getError') return 0;
            if (method === 'getSupportedExtensions') return [];
            if (method === 'getExtension') return null;
            if (method === 'getShaderParameter') return true;
            if (method === 'getProgramParameter') return true;
            if (method === 'getShaderInfoLog') return '';
            if (method === 'getProgramInfoLog') return '';
            if (method === 'isContextLost') return false;
            if (method === 'getContextAttributes') {
                return {
                    alpha: true,
                    antialias: true,
                    depth: true,
                    desynchronized: false,
                    failIfMajorPerformanceCaveat: false,
                    powerPreference: 'default',
                    premultipliedAlpha: true,
                    preserveDrawingBuffer: false,
                    stencil: false,
                    xrCompatible: false
                };
            }
            
            return undefined;
        };
    });
    
    window.WebGLRenderingContext = WebGLRenderingContext;
    
    // ==================== WebGL2RenderingContext ====================
    function WebGL2RenderingContext(canvas) {
        WebGLRenderingContext.call(this, canvas);
    }
    WebGL2RenderingContext.prototype = Object.create(WebGLRenderingContext.prototype);
    WebGL2RenderingContext.prototype.constructor = WebGL2RenderingContext;
    window.WebGL2RenderingContext = WebGL2RenderingContext;
    
    // ==================== HTMLVideoElement ====================
    function HTMLVideoElement() {
        HTMLElement.call(this, 'video');
        // 媒体属性
        this.autoplay = false;
        this.buffered = { length: 0, start: function() { return 0; }, end: function() { return 0; } };
        this.controls = false;
        this.crossOrigin = null;
        this.currentSrc = '';
        this.currentTime = 0;
        this.defaultMuted = false;
        this.defaultPlaybackRate = 1;
        this.disableRemotePlayback = false;
        this.duration = NaN;
        this.ended = false;
        this.error = null;
        this.loop = false;
        this.mediaKeys = null;
        this.muted = false;
        this.networkState = 0;
        this.paused = true;
        this.playbackRate = 1;
        this.played = { length: 0, start: function() { return 0; }, end: function() { return 0; } };
        this.preload = 'auto';
        this.preservesPitch = true;
        this.readyState = 0;
        this.remote = {};
        this.seekable = { length: 0, start: function() { return 0; }, end: function() { return 0; } };
        this.seeking = false;
        this.sinkId = '';
        this.src = '';
        this.srcObject = null;
        this.textTracks = [];
        this.volume = 1;
        // 视频特有属性
        this.height = 0;
        this.poster = '';
        this.videoHeight = 0;
        this.videoWidth = 0;
        this.width = 0;
        this.playsInline = false;
        this.disablePictureInPicture = false;
    }
    HTMLVideoElement.prototype = Object.create(HTMLElement.prototype);
    HTMLVideoElement.prototype.constructor = HTMLVideoElement;
    
    // 媒体方法
    HTMLVideoElement.prototype.play = function() {
        Monitor.logCall('HTMLVideoElement.play', [], 'Promise');
        this.paused = false;
        return Promise.resolve();
    };
    HTMLVideoElement.prototype.pause = function() {
        Monitor.logCall('HTMLVideoElement.pause', [], null);
        this.paused = true;
    };
    HTMLVideoElement.prototype.load = function() {
        Monitor.logCall('HTMLVideoElement.load', [], null);
    };
    HTMLVideoElement.prototype.canPlayType = function(type) {
        Monitor.logCall('HTMLVideoElement.canPlayType', [type], 'maybe');
        return 'maybe';
    };
    HTMLVideoElement.prototype.addTextTrack = function(kind, label, language) {
        Monitor.logCall('HTMLVideoElement.addTextTrack', [kind, label, language], null);
        return {};
    };
    HTMLVideoElement.prototype.captureStream = function() {
        Monitor.logCall('HTMLVideoElement.captureStream', [], '[MediaStream]');
        return {};
    };
    HTMLVideoElement.prototype.getVideoPlaybackQuality = function() {
        Monitor.logCall('HTMLVideoElement.getVideoPlaybackQuality', [], '[Object]');
        return {
            creationTime: performance.now(),
            droppedVideoFrames: 0,
            totalVideoFrames: 0,
            corruptedVideoFrames: 0
        };
    };
    HTMLVideoElement.prototype.requestPictureInPicture = function() {
        Monitor.logCall('HTMLVideoElement.requestPictureInPicture', [], 'Promise');
        return Promise.resolve({});
    };
    HTMLVideoElement.prototype.setSinkId = function(sinkId) {
        Monitor.logCall('HTMLVideoElement.setSinkId', [sinkId], 'Promise');
        return Promise.resolve();
    };
    HTMLVideoElement.prototype.setMediaKeys = function(mediaKeys) {
        Monitor.logCall('HTMLVideoElement.setMediaKeys', [mediaKeys], 'Promise');
        return Promise.resolve();
    };
    window.HTMLVideoElement = HTMLVideoElement;
    
    // ==================== HTMLAudioElement ====================
    function HTMLAudioElement() {
        HTMLElement.call(this, 'audio');
        // 继承媒体属性（简化版）
        this.autoplay = false;
        this.controls = false;
        this.currentSrc = '';
        this.currentTime = 0;
        this.duration = NaN;
        this.ended = false;
        this.loop = false;
        this.muted = false;
        this.paused = true;
        this.playbackRate = 1;
        this.preload = 'auto';
        this.src = '';
        this.volume = 1;
    }
    HTMLAudioElement.prototype = Object.create(HTMLElement.prototype);
    HTMLAudioElement.prototype.constructor = HTMLAudioElement;
    HTMLAudioElement.prototype.play = function() { 
        this.paused = false;
        return Promise.resolve(); 
    };
    HTMLAudioElement.prototype.pause = function() { this.paused = true; };
    HTMLAudioElement.prototype.load = function() {};
    HTMLAudioElement.prototype.canPlayType = function(type) { return 'maybe'; };
    window.HTMLAudioElement = HTMLAudioElement;
    window.Audio = function(src) {
        const audio = new HTMLAudioElement();
        if (src) audio.src = src;
        return audio;
    };
    
    // ==================== HTMLIFrameElement ====================
    function HTMLIFrameElement() {
        HTMLElement.call(this, 'iframe');
        this.allow = '';
        this.allowFullscreen = false;
        this.contentDocument = null;
        this.contentWindow = null;
        this.csp = '';
        this.featurePolicy = {};
        this.height = '';
        this.loading = 'eager';
        this.name = '';
        this.referrerPolicy = '';
        this.sandbox = new DOMTokenList(this, 'sandbox');
        this.src = '';
        this.srcdoc = '';
        this.width = '';
    }
    HTMLIFrameElement.prototype = Object.create(HTMLElement.prototype);
    HTMLIFrameElement.prototype.constructor = HTMLIFrameElement;
    HTMLIFrameElement.prototype.getSVGDocument = function() { return null; };
    window.HTMLIFrameElement = HTMLIFrameElement;
    
    // ==================== HTMLTableElement ====================
    function HTMLTableElement() {
        HTMLElement.call(this, 'table');
        this.caption = null;
        this.tHead = null;
        this.tFoot = null;
        this.tBodies = [];
        this.rows = [];
        this.align = '';
        this.bgColor = '';
        this.border = '';
        this.cellPadding = '';
        this.cellSpacing = '';
        this.frame = '';
        this.rules = '';
        this.summary = '';
        this.width = '';
    }
    HTMLTableElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTableElement.prototype.constructor = HTMLTableElement;
    HTMLTableElement.prototype.createCaption = function() { return new HTMLElement('caption'); };
    HTMLTableElement.prototype.deleteCaption = function() { this.caption = null; };
    HTMLTableElement.prototype.createTHead = function() { return new HTMLElement('thead'); };
    HTMLTableElement.prototype.deleteTHead = function() { this.tHead = null; };
    HTMLTableElement.prototype.createTFoot = function() { return new HTMLElement('tfoot'); };
    HTMLTableElement.prototype.deleteTFoot = function() { this.tFoot = null; };
    HTMLTableElement.prototype.createTBody = function() { return new HTMLElement('tbody'); };
    HTMLTableElement.prototype.insertRow = function(index) { return new HTMLTableRowElement(); };
    HTMLTableElement.prototype.deleteRow = function(index) { };
    window.HTMLTableElement = HTMLTableElement;
    
    // ==================== HTMLTableRowElement ====================
    function HTMLTableRowElement() {
        HTMLElement.call(this, 'tr');
        this.cells = [];
        this.rowIndex = -1;
        this.sectionRowIndex = -1;
        this.align = '';
        this.bgColor = '';
        this.ch = '';
        this.chOff = '';
        this.vAlign = '';
    }
    HTMLTableRowElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTableRowElement.prototype.constructor = HTMLTableRowElement;
    HTMLTableRowElement.prototype.insertCell = function(index) { return new HTMLTableCellElement(); };
    HTMLTableRowElement.prototype.deleteCell = function(index) { };
    window.HTMLTableRowElement = HTMLTableRowElement;
    
    // ==================== HTMLTableCellElement ====================
    function HTMLTableCellElement() {
        HTMLElement.call(this, 'td');
        this.cellIndex = -1;
        this.colSpan = 1;
        this.headers = '';
        this.rowSpan = 1;
        this.scope = '';
        this.abbr = '';
        this.align = '';
        this.axis = '';
        this.bgColor = '';
        this.ch = '';
        this.chOff = '';
        this.height = '';
        this.noWrap = false;
        this.vAlign = '';
        this.width = '';
    }
    HTMLTableCellElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTableCellElement.prototype.constructor = HTMLTableCellElement;
    window.HTMLTableCellElement = HTMLTableCellElement;
    
    // ==================== HTMLUListElement / HTMLOListElement / HTMLLIElement ====================
    function HTMLUListElement() {
        HTMLElement.call(this, 'ul');
        this.compact = false;
        this.type = '';
    }
    HTMLUListElement.prototype = Object.create(HTMLElement.prototype);
    HTMLUListElement.prototype.constructor = HTMLUListElement;
    window.HTMLUListElement = HTMLUListElement;
    
    function HTMLOListElement() {
        HTMLElement.call(this, 'ol');
        this.compact = false;
        this.reversed = false;
        this.start = 1;
        this.type = '';
    }
    HTMLOListElement.prototype = Object.create(HTMLElement.prototype);
    HTMLOListElement.prototype.constructor = HTMLOListElement;
    window.HTMLOListElement = HTMLOListElement;
    
    function HTMLLIElement() {
        HTMLElement.call(this, 'li');
        this.type = '';
        this.value = 0;
    }
    HTMLLIElement.prototype = Object.create(HTMLElement.prototype);
    HTMLLIElement.prototype.constructor = HTMLLIElement;
    window.HTMLLIElement = HTMLLIElement;
    
    // ==================== HTMLPreElement ====================
    function HTMLPreElement() {
        HTMLElement.call(this, 'pre');
        this.width = 0;
    }
    HTMLPreElement.prototype = Object.create(HTMLElement.prototype);
    HTMLPreElement.prototype.constructor = HTMLPreElement;
    window.HTMLPreElement = HTMLPreElement;
    
    // ==================== HTMLBRElement ====================
    function HTMLBRElement() {
        HTMLElement.call(this, 'br');
        this.clear = '';
    }
    HTMLBRElement.prototype = Object.create(HTMLElement.prototype);
    HTMLBRElement.prototype.constructor = HTMLBRElement;
    window.HTMLBRElement = HTMLBRElement;
    
    // ==================== HTMLHRElement ====================
    function HTMLHRElement() {
        HTMLElement.call(this, 'hr');
        this.align = '';
        this.color = '';
        this.noShade = false;
        this.size = '';
        this.width = '';
    }
    HTMLHRElement.prototype = Object.create(HTMLElement.prototype);
    HTMLHRElement.prototype.constructor = HTMLHRElement;
    window.HTMLHRElement = HTMLHRElement;
    
    // ==================== HTMLProgressElement ====================
    function HTMLProgressElement() {
        HTMLElement.call(this, 'progress');
        this.labels = [];
        this.max = 1;
        this.position = -1;
        this.value = 0;
    }
    HTMLProgressElement.prototype = Object.create(HTMLElement.prototype);
    HTMLProgressElement.prototype.constructor = HTMLProgressElement;
    window.HTMLProgressElement = HTMLProgressElement;
    
    // ==================== HTMLMeterElement ====================
    function HTMLMeterElement() {
        HTMLElement.call(this, 'meter');
        this.high = 0;
        this.labels = [];
        this.low = 0;
        this.max = 1;
        this.min = 0;
        this.optimum = 0;
        this.value = 0;
    }
    HTMLMeterElement.prototype = Object.create(HTMLElement.prototype);
    HTMLMeterElement.prototype.constructor = HTMLMeterElement;
    window.HTMLMeterElement = HTMLMeterElement;
    
    // ==================== HTMLDetailsElement ====================
    function HTMLDetailsElement() {
        HTMLElement.call(this, 'details');
        this.open = false;
    }
    HTMLDetailsElement.prototype = Object.create(HTMLElement.prototype);
    HTMLDetailsElement.prototype.constructor = HTMLDetailsElement;
    window.HTMLDetailsElement = HTMLDetailsElement;
    
    // ==================== HTMLDialogElement ====================
    function HTMLDialogElement() {
        HTMLElement.call(this, 'dialog');
        this.open = false;
        this.returnValue = '';
    }
    HTMLDialogElement.prototype = Object.create(HTMLElement.prototype);
    HTMLDialogElement.prototype.constructor = HTMLDialogElement;
    HTMLDialogElement.prototype.show = function() { 
        Monitor.logCall('HTMLDialogElement.show', [], null);
        this.open = true; 
    };
    HTMLDialogElement.prototype.showModal = function() { 
        Monitor.logCall('HTMLDialogElement.showModal', [], null);
        this.open = true; 
    };
    HTMLDialogElement.prototype.close = function(returnValue) { 
        Monitor.logCall('HTMLDialogElement.close', [returnValue], null);
        if (returnValue !== undefined) this.returnValue = returnValue;
        this.open = false; 
    };
    window.HTMLDialogElement = HTMLDialogElement;
    
    // ==================== HTMLTemplateElement ====================
    function HTMLTemplateElement() {
        HTMLElement.call(this, 'template');
        this.content = document.createDocumentFragment();
    }
    HTMLTemplateElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTemplateElement.prototype.constructor = HTMLTemplateElement;
    window.HTMLTemplateElement = HTMLTemplateElement;
    
    // ==================== HTMLSlotElement ====================
    function HTMLSlotElement() {
        HTMLElement.call(this, 'slot');
        this.name = '';
    }
    HTMLSlotElement.prototype = Object.create(HTMLElement.prototype);
    HTMLSlotElement.prototype.constructor = HTMLSlotElement;
    HTMLSlotElement.prototype.assignedNodes = function(options) { return []; };
    HTMLSlotElement.prototype.assignedElements = function(options) { return []; };
    HTMLSlotElement.prototype.assign = function(...nodes) { };
    window.HTMLSlotElement = HTMLSlotElement;
    
    // ==================== HTMLDataElement ====================
    function HTMLDataElement() {
        HTMLElement.call(this, 'data');
        this.value = '';
    }
    HTMLDataElement.prototype = Object.create(HTMLElement.prototype);
    HTMLDataElement.prototype.constructor = HTMLDataElement;
    window.HTMLDataElement = HTMLDataElement;
    
    // ==================== HTMLTimeElement ====================
    function HTMLTimeElement() {
        HTMLElement.call(this, 'time');
        this.dateTime = '';
    }
    HTMLTimeElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTimeElement.prototype.constructor = HTMLTimeElement;
    window.HTMLTimeElement = HTMLTimeElement;
    
    // ==================== HTMLOutputElement ====================
    function HTMLOutputElement() {
        HTMLElement.call(this, 'output');
        this.defaultValue = '';
        this.form = null;
        this.htmlFor = new DOMTokenList(this, 'for');
        this.labels = [];
        this.name = '';
        this.type = 'output';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.value = '';
        this.willValidate = false;
    }
    HTMLOutputElement.prototype = Object.create(HTMLElement.prototype);
    HTMLOutputElement.prototype.constructor = HTMLOutputElement;
    HTMLOutputElement.prototype.checkValidity = function() { return true; };
    HTMLOutputElement.prototype.reportValidity = function() { return true; };
    HTMLOutputElement.prototype.setCustomValidity = function() { };
    window.HTMLOutputElement = HTMLOutputElement;
    
    // ==================== HTMLFieldSetElement ====================
    function HTMLFieldSetElement() {
        HTMLElement.call(this, 'fieldset');
        this.disabled = false;
        this.elements = [];
        this.form = null;
        this.name = '';
        this.type = 'fieldset';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.willValidate = false;
    }
    HTMLFieldSetElement.prototype = Object.create(HTMLElement.prototype);
    HTMLFieldSetElement.prototype.constructor = HTMLFieldSetElement;
    HTMLFieldSetElement.prototype.checkValidity = function() { return true; };
    HTMLFieldSetElement.prototype.reportValidity = function() { return true; };
    HTMLFieldSetElement.prototype.setCustomValidity = function() { };
    window.HTMLFieldSetElement = HTMLFieldSetElement;
    
    // ==================== HTMLLegendElement ====================
    function HTMLLegendElement() {
        HTMLElement.call(this, 'legend');
        this.align = '';
        this.form = null;
    }
    HTMLLegendElement.prototype = Object.create(HTMLElement.prototype);
    HTMLLegendElement.prototype.constructor = HTMLLegendElement;
    window.HTMLLegendElement = HTMLLegendElement;
    
    // ==================== HTMLDataListElement ====================
    function HTMLDataListElement() {
        HTMLElement.call(this, 'datalist');
        this.options = [];
    }
    HTMLDataListElement.prototype = Object.create(HTMLElement.prototype);
    HTMLDataListElement.prototype.constructor = HTMLDataListElement;
    window.HTMLDataListElement = HTMLDataListElement;
    
    // ==================== HTMLOptGroupElement ====================
    function HTMLOptGroupElement() {
        HTMLElement.call(this, 'optgroup');
        this.disabled = false;
        this.label = '';
    }
    HTMLOptGroupElement.prototype = Object.create(HTMLElement.prototype);
    HTMLOptGroupElement.prototype.constructor = HTMLOptGroupElement;
    window.HTMLOptGroupElement = HTMLOptGroupElement;
    
    // ==================== HTMLObjectElement ====================
    function HTMLObjectElement() {
        HTMLElement.call(this, 'object');
        this.align = '';
        this.archive = '';
        this.border = '';
        this.code = '';
        this.codeBase = '';
        this.codeType = '';
        this.contentDocument = null;
        this.contentWindow = null;
        this.data = '';
        this.declare = false;
        this.form = null;
        this.height = '';
        this.hspace = 0;
        this.name = '';
        this.standby = '';
        this.type = '';
        this.useMap = '';
        this.validationMessage = '';
        this.validity = { valid: true };
        this.vspace = 0;
        this.width = '';
        this.willValidate = false;
    }
    HTMLObjectElement.prototype = Object.create(HTMLElement.prototype);
    HTMLObjectElement.prototype.constructor = HTMLObjectElement;
    HTMLObjectElement.prototype.checkValidity = function() { return true; };
    HTMLObjectElement.prototype.reportValidity = function() { return true; };
    HTMLObjectElement.prototype.setCustomValidity = function() { };
    HTMLObjectElement.prototype.getSVGDocument = function() { return null; };
    window.HTMLObjectElement = HTMLObjectElement;
    
    // ==================== HTMLEmbedElement ====================
    function HTMLEmbedElement() {
        HTMLElement.call(this, 'embed');
        this.align = '';
        this.height = '';
        this.name = '';
        this.src = '';
        this.type = '';
        this.width = '';
    }
    HTMLEmbedElement.prototype = Object.create(HTMLElement.prototype);
    HTMLEmbedElement.prototype.constructor = HTMLEmbedElement;
    HTMLEmbedElement.prototype.getSVGDocument = function() { return null; };
    window.HTMLEmbedElement = HTMLEmbedElement;
    
    // ==================== HTMLSourceElement ====================
    function HTMLSourceElement() {
        HTMLElement.call(this, 'source');
        this.height = 0;
        this.media = '';
        this.sizes = '';
        this.src = '';
        this.srcset = '';
        this.type = '';
        this.width = 0;
    }
    HTMLSourceElement.prototype = Object.create(HTMLElement.prototype);
    HTMLSourceElement.prototype.constructor = HTMLSourceElement;
    window.HTMLSourceElement = HTMLSourceElement;
    
    // ==================== HTMLTrackElement ====================
    function HTMLTrackElement() {
        HTMLElement.call(this, 'track');
        this.default = false;
        this.kind = 'subtitles';
        this.label = '';
        this.readyState = 0;
        this.src = '';
        this.srclang = '';
        this.track = null;
        
        // 常量
        this.NONE = 0;
        this.LOADING = 1;
        this.LOADED = 2;
        this.ERROR = 3;
    }
    HTMLTrackElement.prototype = Object.create(HTMLElement.prototype);
    HTMLTrackElement.prototype.constructor = HTMLTrackElement;
    HTMLTrackElement.NONE = 0;
    HTMLTrackElement.LOADING = 1;
    HTMLTrackElement.LOADED = 2;
    HTMLTrackElement.ERROR = 3;
    window.HTMLTrackElement = HTMLTrackElement;
    
    // ==================== HTMLPictureElement ====================
    function HTMLPictureElement() {
        HTMLElement.call(this, 'picture');
    }
    HTMLPictureElement.prototype = Object.create(HTMLElement.prototype);
    HTMLPictureElement.prototype.constructor = HTMLPictureElement;
    window.HTMLPictureElement = HTMLPictureElement;
    
    // ==================== HTMLMapElement ====================
    function HTMLMapElement() {
        HTMLElement.call(this, 'map');
        this.areas = [];
        this.name = '';
    }
    HTMLMapElement.prototype = Object.create(HTMLElement.prototype);
    HTMLMapElement.prototype.constructor = HTMLMapElement;
    window.HTMLMapElement = HTMLMapElement;
    
    // ==================== HTMLAreaElement ====================
    function HTMLAreaElement() {
        HTMLElement.call(this, 'area');
        this.alt = '';
        this.coords = '';
        this.download = '';
        this.hash = '';
        this.host = '';
        this.hostname = '';
        this.href = '';
        this.noHref = false;
        this.origin = '';
        this.password = '';
        this.pathname = '';
        this.ping = '';
        this.port = '';
        this.protocol = '';
        this.referrerPolicy = '';
        this.rel = '';
        this.relList = new DOMTokenList(this, 'rel');
        this.search = '';
        this.shape = '';
        this.target = '';
        this.username = '';
    }
    HTMLAreaElement.prototype = Object.create(HTMLElement.prototype);
    HTMLAreaElement.prototype.constructor = HTMLAreaElement;
    HTMLAreaElement.prototype.toString = function() { return this.href; };
    window.HTMLAreaElement = HTMLAreaElement;
    
    // ==================== SVGElement ====================
    function SVGElement(tagName) {
        Element.call(this, tagName || 'svg', 'http://www.w3.org/2000/svg');
    }
    SVGElement.prototype = Object.create(Element.prototype);
    SVGElement.prototype.constructor = SVGElement;
    window.SVGElement = SVGElement;
    
    // ==================== SVGSVGElement ====================
    function SVGSVGElement() {
        SVGElement.call(this, 'svg');
        this.currentScale = 1;
        this.currentTranslate = { x: 0, y: 0 };
        this.height = { baseVal: { value: 150 }, animVal: { value: 150 } };
        this.width = { baseVal: { value: 300 }, animVal: { value: 300 } };
        this.x = { baseVal: { value: 0 }, animVal: { value: 0 } };
        this.y = { baseVal: { value: 0 }, animVal: { value: 0 } };
        this.viewBox = { baseVal: { x: 0, y: 0, width: 300, height: 150 } };
    }
    SVGSVGElement.prototype = Object.create(SVGElement.prototype);
    SVGSVGElement.prototype.constructor = SVGSVGElement;
    SVGSVGElement.prototype.createSVGPoint = function() { return { x: 0, y: 0 }; };
    SVGSVGElement.prototype.createSVGRect = function() { return { x: 0, y: 0, width: 0, height: 0 }; };
    SVGSVGElement.prototype.createSVGMatrix = function() { return new DOMMatrix(); };
    SVGSVGElement.prototype.createSVGTransform = function() { return {}; };
    SVGSVGElement.prototype.createSVGLength = function() { return { value: 0 }; };
    SVGSVGElement.prototype.createSVGAngle = function() { return { value: 0 }; };
    SVGSVGElement.prototype.createSVGNumber = function() { return { value: 0 }; };
    SVGSVGElement.prototype.getElementById = function(id) { return null; };
    SVGSVGElement.prototype.getIntersectionList = function() { return []; };
    SVGSVGElement.prototype.getEnclosureList = function() { return []; };
    SVGSVGElement.prototype.checkIntersection = function() { return false; };
    SVGSVGElement.prototype.checkEnclosure = function() { return false; };
    SVGSVGElement.prototype.deselectAll = function() { };
    SVGSVGElement.prototype.suspendRedraw = function() { return 0; };
    SVGSVGElement.prototype.unsuspendRedraw = function() { };
    SVGSVGElement.prototype.unsuspendRedrawAll = function() { };
    SVGSVGElement.prototype.forceRedraw = function() { };
    SVGSVGElement.prototype.pauseAnimations = function() { };
    SVGSVGElement.prototype.unpauseAnimations = function() { };
    SVGSVGElement.prototype.animationsPaused = function() { return false; };
    SVGSVGElement.prototype.getCurrentTime = function() { return 0; };
    SVGSVGElement.prototype.setCurrentTime = function() { };
    window.SVGSVGElement = SVGSVGElement;
    
    // ==================== 元素构造函数映射表 ====================
    const elementConstructors = {
        // 基础元素
        'div': HTMLDivElement,
        'span': HTMLSpanElement,
        'p': HTMLParagraphElement,
        'a': HTMLAnchorElement,
        'img': HTMLImageElement,
        'br': HTMLBRElement,
        'hr': HTMLHRElement,
        'pre': HTMLPreElement,
        
        // 标题
        'h1': function() { return new HTMLHeadingElement(1); },
        'h2': function() { return new HTMLHeadingElement(2); },
        'h3': function() { return new HTMLHeadingElement(3); },
        'h4': function() { return new HTMLHeadingElement(4); },
        'h5': function() { return new HTMLHeadingElement(5); },
        'h6': function() { return new HTMLHeadingElement(6); },
        
        // 表单元素
        'form': HTMLFormElement,
        'input': HTMLInputElement,
        'button': HTMLButtonElement,
        'select': HTMLSelectElement,
        'option': HTMLOptionElement,
        'optgroup': HTMLOptGroupElement,
        'textarea': HTMLTextAreaElement,
        'label': HTMLLabelElement,
        'fieldset': HTMLFieldSetElement,
        'legend': HTMLLegendElement,
        'datalist': HTMLDataListElement,
        'output': HTMLOutputElement,
        'progress': HTMLProgressElement,
        'meter': HTMLMeterElement,
        
        // 表格元素
        'table': HTMLTableElement,
        'tr': HTMLTableRowElement,
        'td': HTMLTableCellElement,
        'th': HTMLTableCellElement,
        
        // 列表元素
        'ul': HTMLUListElement,
        'ol': HTMLOListElement,
        'li': HTMLLIElement,
        
        // 媒体元素
        'video': HTMLVideoElement,
        'audio': HTMLAudioElement,
        'source': HTMLSourceElement,
        'track': HTMLTrackElement,
        'picture': HTMLPictureElement,
        'canvas': HTMLCanvasElement,
        
        // 嵌入元素
        'iframe': HTMLIFrameElement,
        'embed': HTMLEmbedElement,
        'object': HTMLObjectElement,
        
        // 文档元素
        'script': HTMLScriptElement,
        'style': HTMLStyleElement,
        'link': HTMLLinkElement,
        'meta': HTMLMetaElement,
        'title': HTMLTitleElement,
        'base': HTMLBaseElement,
        
        // 交互元素
        'details': HTMLDetailsElement,
        'dialog': HTMLDialogElement,
        
        // 其他
        'template': HTMLTemplateElement,
        'slot': HTMLSlotElement,
        'data': HTMLDataElement,
        'time': HTMLTimeElement,
        'map': HTMLMapElement,
        'area': HTMLAreaElement,
        
        // SVG
        'svg': SVGSVGElement
    };
    
    // Keep document.createElement wired to constructors installed by this module.
    if (window.__elementConstructors__ && typeof window.__elementConstructors__ === 'object') {
        Object.assign(window.__elementConstructors__, elementConstructors);
    } else {
        window.__elementConstructors__ = elementConstructors;
    }
    
    // ==================== DOMTokenList (如果不存在) ====================
    if (!window.DOMTokenList) {
        function DOMTokenList(element, attrName) {
            this._element = element;
            this._attrName = attrName;
            this._tokens = [];
        }
        DOMTokenList.prototype = {
            add: function(...tokens) { tokens.forEach(t => { if (!this._tokens.includes(t)) this._tokens.push(t); }); },
            remove: function(...tokens) { tokens.forEach(t => { const i = this._tokens.indexOf(t); if (i > -1) this._tokens.splice(i, 1); }); },
            contains: function(token) { return this._tokens.includes(token); },
            toggle: function(token, force) {
                if (force !== undefined) {
                    if (force) this.add(token); else this.remove(token);
                    return force;
                }
                if (this.contains(token)) { this.remove(token); return false; }
                this.add(token); return true;
            },
            replace: function(oldToken, newToken) {
                const i = this._tokens.indexOf(oldToken);
                if (i > -1) { this._tokens[i] = newToken; return true; }
                return false;
            },
            item: function(index) { return this._tokens[index] || null; },
            get length() { return this._tokens.length; },
            get value() { return this._tokens.join(' '); },
            toString: function() { return this._tokens.join(' '); }
        };
        window.DOMTokenList = DOMTokenList;
    }
    
    // ==================== DOMMatrix (如果不存在) ====================
    if (!window.DOMMatrix) {
        function DOMMatrix(init) {
            this.a = 1; this.b = 0; this.c = 0; this.d = 1; this.e = 0; this.f = 0;
            this.m11 = 1; this.m12 = 0; this.m13 = 0; this.m14 = 0;
            this.m21 = 0; this.m22 = 1; this.m23 = 0; this.m24 = 0;
            this.m31 = 0; this.m32 = 0; this.m33 = 1; this.m34 = 0;
            this.m41 = 0; this.m42 = 0; this.m43 = 0; this.m44 = 1;
            this.is2D = true;
            this.isIdentity = true;
        }
        DOMMatrix.prototype = {
            multiply: function() { return new DOMMatrix(); },
            translate: function() { return new DOMMatrix(); },
            scale: function() { return new DOMMatrix(); },
            rotate: function() { return new DOMMatrix(); },
            inverse: function() { return new DOMMatrix(); },
            transformPoint: function(point) { return { x: point?.x || 0, y: point?.y || 0, z: 0, w: 1 }; },
            toString: function() { return `matrix(${this.a}, ${this.b}, ${this.c}, ${this.d}, ${this.e}, ${this.f})`; }
        };
        window.DOMMatrix = DOMMatrix;
        window.DOMMatrixReadOnly = DOMMatrix;
    }
    
    console.log('[elements.js] HTML元素类型库加载完成，共注册', Object.keys(elementConstructors).length, '种元素类型');
    
})();
