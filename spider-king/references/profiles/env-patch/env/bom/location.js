/**
 * @env-module location
 * @description 浏览器location对象模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    const location = {
        _href: 'https://example.com/',
        _protocol: 'https:',
        _host: 'example.com',
        _hostname: 'example.com',
        _port: '',
        _pathname: '/',
        _search: '',
        _hash: '',
        _origin: 'https://example.com',

        get href() {
            return this._href;
        },
        set href(value) {
            this._parseUrl(value);
        },

        get protocol() {
            return this._protocol;
        },
        set protocol(value) {
            this._protocol = value;
            this._updateHref();
        },

        get host() {
            return this._host;
        },
        set host(value) {
            this._host = value;
            const parts = value.split(':');
            this._hostname = parts[0];
            this._port = parts[1] || '';
            this._updateHref();
        },

        get hostname() {
            return this._hostname;
        },
        set hostname(value) {
            this._hostname = value;
            this._host = this._port ? `${value}:${this._port}` : value;
            this._updateHref();
        },

        get port() {
            return this._port;
        },
        set port(value) {
            this._port = value;
            this._host = value ? `${this._hostname}:${value}` : this._hostname;
            this._updateHref();
        },

        get pathname() {
            return this._pathname;
        },
        set pathname(value) {
            this._pathname = value.startsWith('/') ? value : '/' + value;
            this._updateHref();
        },

        get search() {
            return this._search;
        },
        set search(value) {
            this._search = value.startsWith('?') ? value : (value ? '?' + value : '');
            this._updateHref();
        },

        get hash() {
            return this._hash;
        },
        set hash(value) {
            this._hash = value.startsWith('#') ? value : (value ? '#' + value : '');
            this._updateHref();
        },

        get origin() {
            return this._origin;
        },

        // 方法
        assign: function(url) {
            console.log('[location.assign]', typeof url === 'string' ? url.split(/[?#]/, 1)[0] : `[${typeof url}]`);
            this._parseUrl(url);
        },

        replace: function(url) {
            console.log('[location.replace]', typeof url === 'string' ? url.split(/[?#]/, 1)[0] : `[${typeof url}]`);
            this._parseUrl(url);
        },

        reload: function(forceReload) {
            console.log('[location.reload]', forceReload);
        },

        toString: function() {
            return this._href;
        },

        valueOf: function() {
            return this._href;
        },

        // 内部方法
        _parseUrl: function(url) {
            try {
                // 处理相对URL
                let fullUrl = url;
                if (!url.includes('://')) {
                    if (url.startsWith('//')) {
                        fullUrl = this._protocol + url;
                    } else if (url.startsWith('/')) {
                        fullUrl = this._origin + url;
                    } else {
                        fullUrl = this._origin + this._pathname.replace(/\/[^\/]*$/, '/') + url;
                    }
                }

                // 简单解析
                const match = fullUrl.match(/^(https?:)\/\/([^\/\?#]+)(\/[^\?#]*)?(\?[^#]*)?(#.*)?$/);
                if (match) {
                    this._protocol = match[1];
                    this._host = match[2];
                    const hostParts = match[2].split(':');
                    this._hostname = hostParts[0];
                    this._port = hostParts[1] || '';
                    this._pathname = match[3] || '/';
                    this._search = match[4] || '';
                    this._hash = match[5] || '';
                    this._origin = `${this._protocol}//${this._host}`;
                    this._href = fullUrl;
                }
            } catch (e) {
                console.error('[location._parseUrl error] details redacted');
            }
        },

        _updateHref: function() {
            this._origin = `${this._protocol}//${this._host}`;
            this._href = `${this._origin}${this._pathname}${this._search}${this._hash}`;
        }
    };

    // 挂载到window
    window.location = location;
})();
