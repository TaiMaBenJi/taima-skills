/**
 * @env-module history
 * @description 浏览器history对象模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    function safeUrlShape(value) {
        if (typeof value !== 'string') return `[${typeof value}]`;
        try {
            const parsed = new URL(value, window.location?.href || 'https://example.invalid/');
            return parsed.origin + parsed.pathname;
        } catch (_) {
            return value.split(/[?#]/, 1)[0];
        }
    }
    const historyStack = [{ state: null, title: '', url: window.location?.href || 'https://example.com/' }];
    let currentIndex = 0;

    const history = {
        get length() {
            return historyStack.length;
        },

        get state() {
            return historyStack[currentIndex]?.state || null;
        },

        get scrollRestoration() {
            return 'auto';
        },
        set scrollRestoration(value) {
            // 允许设置但不实际生效
        },

        back: function() {
            if (currentIndex > 0) {
                currentIndex--;
                console.log('[history.back]', safeUrlShape(historyStack[currentIndex].url));
                this._dispatchPopState();
            }
        },

        forward: function() {
            if (currentIndex < historyStack.length - 1) {
                currentIndex++;
                console.log('[history.forward]', safeUrlShape(historyStack[currentIndex].url));
                this._dispatchPopState();
            }
        },

        go: function(delta) {
            delta = parseInt(delta) || 0;
            const newIndex = currentIndex + delta;
            
            if (newIndex >= 0 && newIndex < historyStack.length) {
                currentIndex = newIndex;
                console.log('[history.go]', { delta, url: safeUrlShape(historyStack[currentIndex].url) });
                this._dispatchPopState();
            }
        },

        pushState: function(state, title, url) {
            // 移除当前位置之后的所有历史记录
            historyStack.splice(currentIndex + 1);
            
            // 添加新记录
            const newUrl = this._resolveUrl(url);
            historyStack.push({ state, title, url: newUrl });
            currentIndex = historyStack.length - 1;
            
            console.log('[history.pushState]', {
                stateType: state === null ? 'null' : typeof state,
                titleLength: typeof title === 'string' ? title.length : null,
                url: safeUrlShape(newUrl)
            });
            
            // 更新location
            if (window.location && url) {
                window.location._parseUrl(newUrl);
            }
        },

        replaceState: function(state, title, url) {
            const newUrl = url ? this._resolveUrl(url) : historyStack[currentIndex].url;
            historyStack[currentIndex] = { state, title, url: newUrl };
            
            console.log('[history.replaceState]', {
                stateType: state === null ? 'null' : typeof state,
                titleLength: typeof title === 'string' ? title.length : null,
                url: safeUrlShape(newUrl)
            });
            
            // 更新location
            if (window.location && url) {
                window.location._parseUrl(newUrl);
            }
        },

        // 内部方法
        _resolveUrl: function(url) {
            if (!url) return historyStack[currentIndex]?.url || '';
            
            // 处理相对URL
            if (url.startsWith('http://') || url.startsWith('https://')) {
                return url;
            }
            
            const origin = window.location?.origin || 'https://example.com';
            if (url.startsWith('/')) {
                return origin + url;
            }
            
            const pathname = window.location?.pathname || '/';
            const basePath = pathname.replace(/\/[^\/]*$/, '/');
            return origin + basePath + url;
        },

        _dispatchPopState: function() {
            // 触发popstate事件
            if (typeof window !== 'undefined' && window.dispatchEvent) {
                const event = {
                    type: 'popstate',
                    state: this.state,
                    bubbles: true,
                    cancelable: false
                };
                window.dispatchEvent(event);
            }
        }
    };

    // 挂载到window
    window.history = history;
})();
