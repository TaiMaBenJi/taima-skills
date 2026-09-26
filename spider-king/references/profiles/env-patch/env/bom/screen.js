/**
 * @env-module screen
 * @description 浏览器screen对象模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    const screen = {
        // 屏幕尺寸
        width: 1920,
        height: 1080,
        availWidth: 1920,
        availHeight: 1040,
        availLeft: 0,
        availTop: 0,

        // 颜色深度
        colorDepth: 24,
        pixelDepth: 24,

        // 方向
        orientation: {
            angle: 0,
            type: 'landscape-primary',
            onchange: null,
            lock: function(orientation) {
                return Promise.resolve();
            },
            unlock: function() {}
        },

        // 是否为扩展显示器
        isExtended: false
    };

    // 挂载到window
    window.screen = screen;
})();
