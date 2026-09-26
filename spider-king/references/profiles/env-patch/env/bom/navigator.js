/**
 * @env-module navigator
 * @description 浏览器navigator对象模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    const navigator = {};

    // 基础属性
    navigator.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    navigator.appCodeName = 'Mozilla';
    navigator.appName = 'Netscape';
    navigator.appVersion = '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    navigator.platform = 'Win32';
    navigator.product = 'Gecko';
    navigator.productSub = '20030107';
    navigator.vendor = 'Google Inc.';
    navigator.vendorSub = '';
    navigator.buildID = undefined;

    // 语言相关
    navigator.language = 'zh-CN';
    navigator.languages = ['zh-CN', 'zh', 'en'];

    // 在线状态
    navigator.onLine = true;

    // Cookie
    navigator.cookieEnabled = true;

    // Do Not Track
    navigator.doNotTrack = null;

    // 硬件相关
    navigator.hardwareConcurrency = 8;
    navigator.maxTouchPoints = 0;
    navigator.deviceMemory = 8;

    // 反爬虫检测关键属性
    navigator.webdriver = false;

    // plugins
    const pluginArray = [];
    pluginArray.length = 0;
    pluginArray.item = function(index) { return null; };
    pluginArray.namedItem = function(name) { return null; };
    pluginArray.refresh = function() {};
    navigator.plugins = pluginArray;

    // mimeTypes
    const mimeTypeArray = [];
    mimeTypeArray.length = 0;
    mimeTypeArray.item = function(index) { return null; };
    mimeTypeArray.namedItem = function(name) { return null; };
    navigator.mimeTypes = mimeTypeArray;

    // connection
    navigator.connection = {
        downlink: 10,
        effectiveType: '4g',
        onchange: null,
        rtt: 50,
        saveData: false,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    // geolocation
    navigator.geolocation = {
        getCurrentPosition: function(success, error, options) {
            if (error) {
                error({
                    code: 1,
                    message: 'User denied Geolocation'
                });
            }
        },
        watchPosition: function(success, error, options) {
            return 0;
        },
        clearWatch: function(id) {}
    };

    // permissions
    navigator.permissions = {
        query: function(descriptor) {
            return Promise.resolve({
                name: descriptor.name,
                state: 'prompt',
                onchange: null,
                addEventListener: function() {},
                removeEventListener: function() {},
                dispatchEvent: function() { return true; }
            });
        }
    };

    // mediaDevices
    navigator.mediaDevices = {
        enumerateDevices: function() {
            return Promise.resolve([]);
        },
        getUserMedia: function(constraints) {
            return Promise.reject(new Error('NotAllowedError'));
        },
        getDisplayMedia: function(constraints) {
            return Promise.reject(new Error('NotAllowedError'));
        },
        getSupportedConstraints: function() {
            return {
                aspectRatio: true,
                deviceId: true,
                echoCancellation: true,
                facingMode: true,
                frameRate: true,
                height: true,
                width: true,
                volume: true
            };
        },
        ondevicechange: null,
        addEventListener: function() {},
        removeEventListener: function() {}
    };

    // serviceWorker
    navigator.serviceWorker = {
        controller: null,
        ready: Promise.resolve(),
        oncontrollerchange: null,
        onmessage: null,
        register: function(scriptURL, options) {
            return Promise.resolve({
                scope: '/',
                installing: null,
                waiting: null,
                active: null
            });
        },
        getRegistration: function(clientURL) {
            return Promise.resolve(undefined);
        },
        getRegistrations: function() {
            return Promise.resolve([]);
        },
        addEventListener: function() {},
        removeEventListener: function() {}
    };

    // 方法实现
    navigator.javaEnabled = function() {
        return false;
    };

    navigator.vibrate = function(pattern) {
        return true;
    };

    navigator.sendBeacon = function(url, data) {
        console.log('[sendBeacon]', typeof url === 'string' ? url.split(/[?#]/, 1)[0] : `[${typeof url}]`);
        return true;
    };

    navigator.registerProtocolHandler = function(scheme, url, title) {};

    navigator.unregisterProtocolHandler = function(scheme, url) {};

    // getBattery
    navigator.getBattery = function() {
        return Promise.resolve({
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 1,
            onchargingchange: null,
            onchargingtimechange: null,
            ondischargingtimechange: null,
            onlevelchange: null,
            addEventListener: function() {},
            removeEventListener: function() {}
        });
    };

    // clipboard
    navigator.clipboard = {
        read: function() {
            return Promise.reject(new Error('NotAllowedError'));
        },
        readText: function() {
            return Promise.reject(new Error('NotAllowedError'));
        },
        write: function(data) {
            return Promise.reject(new Error('NotAllowedError'));
        },
        writeText: function(text) {
            return Promise.reject(new Error('NotAllowedError'));
        }
    };

    // credentials
    navigator.credentials = {
        create: function(options) {
            return Promise.resolve(null);
        },
        get: function(options) {
            return Promise.resolve(null);
        },
        preventSilentAccess: function() {
            return Promise.resolve();
        },
        store: function(credential) {
            return Promise.resolve(credential);
        }
    };

    // storage
    navigator.storage = {
        estimate: function() {
            return Promise.resolve({
                quota: 1073741824,
                usage: 0
            });
        },
        persist: function() {
            return Promise.resolve(false);
        },
        persisted: function() {
            return Promise.resolve(false);
        }
    };

    // userAgentData (新API)
    navigator.userAgentData = {
        brands: [
            { brand: 'Not_A Brand', version: '8' },
            { brand: 'Chromium', version: '120' },
            { brand: 'Google Chrome', version: '120' }
        ],
        mobile: false,
        platform: 'Windows',
        getHighEntropyValues: function(hints) {
            return Promise.resolve({
                architecture: 'x86',
                bitness: '64',
                brands: this.brands,
                fullVersionList: [
                    { brand: 'Not_A Brand', version: '8.0.0.0' },
                    { brand: 'Chromium', version: '120.0.0.0' },
                    { brand: 'Google Chrome', version: '120.0.0.0' }
                ],
                mobile: false,
                model: '',
                platform: 'Windows',
                platformVersion: '10.0.0',
                uaFullVersion: '120.0.0.0'
            });
        },
        toJSON: function() {
            return {
                brands: this.brands,
                mobile: this.mobile,
                platform: this.platform
            };
        }
    };

    // 挂载到window
    window.navigator = navigator;
})();
