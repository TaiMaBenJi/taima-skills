/**
 * @env-module ProxyEnv  
 * @description 使用 Proxy 创建基础浏览器环境
 */

(() => {
    'use strict';
    
    // 隐藏 Node.js 特有的全局变量（不能删除，只能覆盖）
    if (typeof global !== 'undefined') {
        try { globalThis.global = undefined; } catch(e) {}
    }
    if (typeof __dirname !== 'undefined') {
        try { globalThis.__dirname = undefined; } catch(e) {}
    }
    if (typeof __filename !== 'undefined') {
        try { globalThis.__filename = undefined; } catch(e) {}
    }
    
    // ==================== 创建基础环境对象 ====================
    
    // document 对象
    if (typeof document === 'undefined') {
        Object.defineProperty(window, 'document', {
            value: watch({
                URL: '',
                domain: '',
                referrer: '',
                title: '',
                cookie: '',
                readyState: 'complete'
            }, 'document'),
            enumerable: true,
            configurable: false
        });
    }
    
    // navigator 对象
    if (typeof navigator === 'undefined') {
        Object.defineProperty(window, 'navigator', {
            value: watch({
                userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                platform: 'Win32',
                language: 'zh-CN',
                languages: ['zh-CN', 'zh', 'en'],
                hardwareConcurrency: 8,
                deviceMemory: 8,
                maxTouchPoints: 0,
                webdriver: false,
                cookieEnabled: true,
                doNotTrack: null
            }, 'navigator'),
            enumerable: true,
            configurable: true
        });
    }
    
    // location 对象
    if (typeof location === 'undefined') {
        Object.defineProperty(window, 'location', {
            value: watch({
                href: 'http://localhost/',
                protocol: 'http:',
                host: 'localhost',
                hostname: 'localhost',
                port: '',
                pathname: '/',
                search: '',
                hash: '',
                origin: 'http://localhost'
            }, 'location'),
            enumerable: true,
            configurable: false
        });
    }
    
    // history 对象
    if (typeof history === 'undefined') {
        Object.defineProperty(window, 'history', {
            value: watch({
                length: 1,
                state: null
            }, 'history'),
            enumerable: true,
            configurable: true
        });
    }
    
    // screen 对象
    if (typeof screen === 'undefined') {
        Object.defineProperty(window, 'screen', {
            value: watch({
                width: 1920,
                height: 1080,
                availWidth: 1920,
                availHeight: 1040,
                colorDepth: 24,
                pixelDepth: 24
            }, 'screen'),
            enumerable: true,
            configurable: true
        });
    }
    
    // localStorage 对象
    if (typeof localStorage === 'undefined') {
        Object.defineProperty(window, 'localStorage', {
            value: watch({}, 'localStorage'),
            enumerable: true,
            configurable: true
        });
    }
    
    // sessionStorage 对象
    if (typeof sessionStorage === 'undefined') {
        Object.defineProperty(window, 'sessionStorage', {
            value: watch({}, 'sessionStorage'),
            enumerable: true,
            configurable: true
        });
    }
    
    console.log('[ProxyEnv] 基础环境对象已创建并代理');
})();
