/**
 * @env-module Blob/File/FormData
 * @description Blob、File、FormData模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // Blob
    function Blob(blobParts, options) {
        this._parts = blobParts || [];
        this._type = options?.type || '';
        
        // 计算大小
        let size = 0;
        this._parts.forEach(part => {
            if (typeof part === 'string') {
                size += part.length;
            } else if (part instanceof ArrayBuffer) {
                size += part.byteLength;
            } else if (part instanceof Blob) {
                size += part.size;
            } else if (ArrayBuffer.isView(part)) {
                size += part.byteLength;
            }
        });
        this._size = size;
    }

    Object.defineProperties(Blob.prototype, {
        size: {
            get: function() { return this._size; }
        },
        type: {
            get: function() { return this._type; }
        }
    });

    Blob.prototype.slice = function(start, end, contentType) {
        start = start || 0;
        end = end || this._size;
        return new Blob(this._parts.slice(start, end), { type: contentType || this._type });
    };

    Blob.prototype.text = function() {
        return Promise.resolve(this._parts.map(part => {
            if (typeof part === 'string') return part;
            return '';
        }).join(''));
    };

    Blob.prototype.arrayBuffer = function() {
        return Promise.resolve(new ArrayBuffer(this._size));
    };

    Blob.prototype.stream = function() {
        return {
            getReader: function() {
                let done = false;
                return {
                    read: function() {
                        if (done) {
                            return Promise.resolve({ done: true, value: undefined });
                        }
                        done = true;
                        return Promise.resolve({ done: false, value: new Uint8Array(0) });
                    },
                    cancel: function() { return Promise.resolve(); }
                };
            }
        };
    };

    // File
    function File(fileBits, fileName, options) {
        Blob.call(this, fileBits, options);
        this._name = fileName;
        this._lastModified = options?.lastModified || Date.now();
        this._webkitRelativePath = '';
    }

    File.prototype = Object.create(Blob.prototype);
    File.prototype.constructor = File;

    Object.defineProperties(File.prototype, {
        name: {
            get: function() { return this._name; }
        },
        lastModified: {
            get: function() { return this._lastModified; }
        },
        lastModifiedDate: {
            get: function() { return new Date(this._lastModified); }
        },
        webkitRelativePath: {
            get: function() { return this._webkitRelativePath; }
        }
    });

    // FileReader
    function FileReader() {
        this.readyState = 0;
        this.result = null;
        this.error = null;
        
        this.onload = null;
        this.onerror = null;
        this.onabort = null;
        this.onloadstart = null;
        this.onloadend = null;
        this.onprogress = null;
        
        this._listeners = {};
    }

    FileReader.EMPTY = 0;
    FileReader.LOADING = 1;
    FileReader.DONE = 2;

    FileReader.prototype = {
        readAsArrayBuffer: function(blob) {
            this._read(blob, 'arrayBuffer');
        },
        readAsBinaryString: function(blob) {
            this._read(blob, 'binaryString');
        },
        readAsDataURL: function(blob) {
            this._read(blob, 'dataURL');
        },
        readAsText: function(blob, encoding) {
            this._read(blob, 'text', encoding);
        },
        abort: function() {
            this.readyState = FileReader.DONE;
            this.result = null;
            this._dispatchEvent('abort');
            this._dispatchEvent('loadend');
        },
        
        _read: function(blob, type, encoding) {
            const self = this;
            this.readyState = FileReader.LOADING;
            this._dispatchEvent('loadstart');
            
            setTimeout(function() {
                self.readyState = FileReader.DONE;
                
                switch (type) {
                    case 'arrayBuffer':
                        self.result = new ArrayBuffer(blob.size);
                        break;
                    case 'binaryString':
                        self.result = '';
                        break;
                    case 'dataURL':
                        self.result = `data:${blob.type || 'application/octet-stream'};base64,`;
                        break;
                    case 'text':
                        self.result = '';
                        break;
                }
                
                self._dispatchEvent('progress', { loaded: blob.size, total: blob.size });
                self._dispatchEvent('load');
                self._dispatchEvent('loadend');
            }, 10);
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
        
        _dispatchEvent: function(type, props) {
            const event = {
                type: type,
                target: this,
                loaded: props?.loaded || 0,
                total: props?.total || 0
            };
            
            if (this['on' + type]) {
                this['on' + type].call(this, event);
            }
            
            (this._listeners[type] || []).forEach(listener => {
                listener.call(this, event);
            });
        }
    };

    // FormData
    function FormData(form) {
        this._entries = [];
        
        if (form && form.elements) {
            // 从表单元素提取数据
            Array.from(form.elements).forEach(element => {
                if (element.name && !element.disabled) {
                    if (element.type === 'file') {
                        // 文件处理
                        if (element.files) {
                            Array.from(element.files).forEach(file => {
                                this.append(element.name, file);
                            });
                        }
                    } else if (element.type === 'checkbox' || element.type === 'radio') {
                        if (element.checked) {
                            this.append(element.name, element.value);
                        }
                    } else if (element.type !== 'submit' && element.type !== 'button') {
                        this.append(element.name, element.value);
                    }
                }
            });
        }
    }

    FormData.prototype = {
        append: function(name, value, filename) {
            if (value instanceof Blob && filename) {
                value = new File([value], filename, { type: value.type });
            }
            this._entries.push([String(name), value]);
        },
        
        delete: function(name) {
            this._entries = this._entries.filter(([key]) => key !== name);
        },
        
        get: function(name) {
            const entry = this._entries.find(([key]) => key === name);
            return entry ? entry[1] : null;
        },
        
        getAll: function(name) {
            return this._entries.filter(([key]) => key === name).map(([, value]) => value);
        },
        
        has: function(name) {
            return this._entries.some(([key]) => key === name);
        },
        
        set: function(name, value, filename) {
            this.delete(name);
            this.append(name, value, filename);
        },
        
        forEach: function(callback, thisArg) {
            this._entries.forEach(([key, value]) => {
                callback.call(thisArg, value, key, this);
            });
        },
        
        entries: function() {
            return this._entries[Symbol.iterator]();
        },
        
        keys: function() {
            return this._entries.map(([key]) => key)[Symbol.iterator]();
        },
        
        values: function() {
            return this._entries.map(([, value]) => value)[Symbol.iterator]();
        },
        
        [Symbol.iterator]: function() {
            return this.entries();
        }
    };

    // 挂载到window
    window.Blob = Blob;
    window.File = File;
    window.FileReader = FileReader;
    window.FormData = FormData;
})();
