/**
 * @env-module storage
 * @description localStorage和sessionStorage模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // 创建Storage实现
    function createStorage() {
        const data = {};
        
        return {
            get length() {
                return Object.keys(data).length;
            },

            key: function(index) {
                const keys = Object.keys(data);
                return keys[index] || null;
            },

            getItem: function(key) {
                return data.hasOwnProperty(key) ? data[key] : null;
            },

            setItem: function(key, value) {
                data[String(key)] = String(value);
            },

            removeItem: function(key) {
                delete data[key];
            },

            clear: function() {
                Object.keys(data).forEach(key => delete data[key]);
            }
        };
    }

    // 创建localStorage和sessionStorage
    window.localStorage = createStorage();
    window.sessionStorage = createStorage();

    // Storage事件构造函数
    window.StorageEvent = function StorageEvent(type, options) {
        this.type = type;
        this.key = options?.key || null;
        this.oldValue = options?.oldValue || null;
        this.newValue = options?.newValue || null;
        this.url = options?.url || '';
        this.storageArea = options?.storageArea || null;
        this.bubbles = false;
        this.cancelable = false;
    };
})();
