/**
 * @env-module URL/URLSearchParams
 * @description URL和URLSearchParams模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // URLSearchParams
    function URLSearchParams(init) {
        this._params = [];
        
        if (init) {
            if (typeof init === 'string') {
                this._parseString(init);
            } else if (init instanceof URLSearchParams) {
                init.forEach((value, key) => {
                    this.append(key, value);
                });
            } else if (Array.isArray(init)) {
                init.forEach(([key, value]) => {
                    this.append(key, value);
                });
            } else if (typeof init === 'object') {
                Object.entries(init).forEach(([key, value]) => {
                    this.append(key, value);
                });
            }
        }
    }

    URLSearchParams.prototype = {
        _parseString: function(str) {
            str = str.replace(/^\?/, '');
            if (!str) return;
            
            str.split('&').forEach(pair => {
                const [key, value = ''] = pair.split('=').map(decodeURIComponent);
                this.append(key, value);
            });
        },

        append: function(name, value) {
            this._params.push([String(name), String(value)]);
        },

        delete: function(name) {
            this._params = this._params.filter(([key]) => key !== name);
        },

        get: function(name) {
            const param = this._params.find(([key]) => key === name);
            return param ? param[1] : null;
        },

        getAll: function(name) {
            return this._params.filter(([key]) => key === name).map(([, value]) => value);
        },

        has: function(name) {
            return this._params.some(([key]) => key === name);
        },

        set: function(name, value) {
            let found = false;
            this._params = this._params.reduce((acc, [key, val]) => {
                if (key === name) {
                    if (!found) {
                        acc.push([key, String(value)]);
                        found = true;
                    }
                } else {
                    acc.push([key, val]);
                }
                return acc;
            }, []);
            if (!found) {
                this.append(name, value);
            }
        },

        sort: function() {
            this._params.sort((a, b) => a[0].localeCompare(b[0]));
        },

        toString: function() {
            return this._params
                .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
                .join('&');
        },

        forEach: function(callback, thisArg) {
            this._params.forEach(([key, value]) => {
                callback.call(thisArg, value, key, this);
            });
        },

        entries: function() {
            return this._params[Symbol.iterator]();
        },

        keys: function() {
            return this._params.map(([key]) => key)[Symbol.iterator]();
        },

        values: function() {
            return this._params.map(([, value]) => value)[Symbol.iterator]();
        },

        [Symbol.iterator]: function() {
            return this.entries();
        },

        get size() {
            return this._params.length;
        }
    };

    // URL
    function URL(url, base) {
        let fullUrl = url;
        
        if (base) {
            // 处理相对URL
            if (!url.match(/^[a-z]+:/i)) {
                const baseUrl = typeof base === 'string' ? base : base.href;
                if (url.startsWith('//')) {
                    const protocol = baseUrl.match(/^([a-z]+:)/i)?.[1] || 'https:';
                    fullUrl = protocol + url;
                } else if (url.startsWith('/')) {
                    const origin = baseUrl.match(/^([a-z]+:\/\/[^\/]+)/i)?.[1] || '';
                    fullUrl = origin + url;
                } else {
                    const basePath = baseUrl.replace(/\/[^\/]*$/, '/');
                    fullUrl = basePath + url;
                }
            }
        }

        // 解析URL
        const match = fullUrl.match(/^([a-z]+:)\/\/(?:([^:@]+)(?::([^@]+))?@)?([^:\/\?#]+)(?::(\d+))?(\/[^\?#]*)?(\?[^#]*)?(#.*)?$/i);
        
        if (!match) {
            throw new TypeError(`Invalid URL: ${fullUrl}`);
        }

        this._protocol = match[1];
        this._username = match[2] || '';
        this._password = match[3] || '';
        this._hostname = match[4];
        this._port = match[5] || '';
        this._pathname = match[6] || '/';
        this._search = match[7] || '';
        this._hash = match[8] || '';
        this._searchParams = new URLSearchParams(this._search);
    }

    Object.defineProperties(URL.prototype, {
        href: {
            get: function() {
                let auth = '';
                if (this._username) {
                    auth = this._password 
                        ? `${this._username}:${this._password}@` 
                        : `${this._username}@`;
                }
                const port = this._port ? `:${this._port}` : '';
                return `${this._protocol}//${auth}${this._hostname}${port}${this._pathname}${this._search}${this._hash}`;
            },
            set: function(value) {
                const url = new URL(value);
                this._protocol = url._protocol;
                this._username = url._username;
                this._password = url._password;
                this._hostname = url._hostname;
                this._port = url._port;
                this._pathname = url._pathname;
                this._search = url._search;
                this._hash = url._hash;
                this._searchParams = new URLSearchParams(this._search);
            }
        },
        protocol: {
            get: function() { return this._protocol; },
            set: function(value) { this._protocol = value.endsWith(':') ? value : value + ':'; }
        },
        username: {
            get: function() { return this._username; },
            set: function(value) { this._username = value; }
        },
        password: {
            get: function() { return this._password; },
            set: function(value) { this._password = value; }
        },
        hostname: {
            get: function() { return this._hostname; },
            set: function(value) { this._hostname = value; }
        },
        port: {
            get: function() { return this._port; },
            set: function(value) { this._port = value; }
        },
        host: {
            get: function() { return this._port ? `${this._hostname}:${this._port}` : this._hostname; },
            set: function(value) {
                const parts = value.split(':');
                this._hostname = parts[0];
                this._port = parts[1] || '';
            }
        },
        pathname: {
            get: function() { return this._pathname; },
            set: function(value) { this._pathname = value.startsWith('/') ? value : '/' + value; }
        },
        search: {
            get: function() { return this._search; },
            set: function(value) {
                this._search = value.startsWith('?') ? value : (value ? '?' + value : '');
                this._searchParams = new URLSearchParams(this._search);
            }
        },
        hash: {
            get: function() { return this._hash; },
            set: function(value) { this._hash = value.startsWith('#') ? value : (value ? '#' + value : ''); }
        },
        origin: {
            get: function() {
                const port = this._port ? `:${this._port}` : '';
                return `${this._protocol}//${this._hostname}${port}`;
            }
        },
        searchParams: {
            get: function() { return this._searchParams; }
        }
    });

    URL.prototype.toString = function() {
        return this.href;
    };

    URL.prototype.toJSON = function() {
        return this.href;
    };

    // 静态方法
    URL.createObjectURL = function(object) {
        return `blob:${window.location?.origin || 'https://example.com'}/${Math.random().toString(36).slice(2)}`;
    };

    URL.revokeObjectURL = function(url) {
        // 清理blob URL
    };

    URL.canParse = function(url, base) {
        try {
            new URL(url, base);
            return true;
        } catch {
            return false;
        }
    };

    // 挂载到window
    window.URL = URL;
    window.URLSearchParams = URLSearchParams;
    window.webkitURL = URL; // Chrome兼容
})();
