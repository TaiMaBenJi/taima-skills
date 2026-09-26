/**
 * @env-module Timer
 * @description 定时器函数模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 * @note 在沙箱环境中，定时器是模拟实现，不会真正延迟执行
 */

(function() {
    let timerId = 0;
    const timers = new Map();
    const intervals = new Map();

    // setTimeout
    const originalSetTimeout = window.setTimeout;
    window.setTimeout = function(callback, delay, ...args) {
        if (typeof callback !== 'function') {
            // 处理字符串代码（不推荐但需要兼容）
            const code = String(callback);
            callback = function() {
                eval(code);
            };
        }
        
        const id = ++timerId;
        
        // 在沙箱环境中，我们记录定时器但可能需要不同的执行策略
        timers.set(id, {
            callback,
            delay: delay || 0,
            args,
            createdAt: Date.now()
        });
        
        // 如果有原始实现，使用它
        if (typeof originalSetTimeout === 'function') {
            const realId = originalSetTimeout.call(window, function() {
                timers.delete(id);
                callback.apply(window, args);
            }, delay);
            
            // 建立映射关系
            timers.get(id).realId = realId;
        }
        
        return id;
    };

    // clearTimeout
    const originalClearTimeout = window.clearTimeout;
    window.clearTimeout = function(id) {
        const timer = timers.get(id);
        if (timer) {
            if (timer.realId !== undefined && typeof originalClearTimeout === 'function') {
                originalClearTimeout.call(window, timer.realId);
            }
            timers.delete(id);
        }
    };

    // setInterval
    const originalSetInterval = window.setInterval;
    window.setInterval = function(callback, delay, ...args) {
        if (typeof callback !== 'function') {
            const code = String(callback);
            callback = function() {
                eval(code);
            };
        }
        
        const id = ++timerId;
        
        intervals.set(id, {
            callback,
            delay: delay || 0,
            args,
            createdAt: Date.now()
        });
        
        if (typeof originalSetInterval === 'function') {
            const realId = originalSetInterval.call(window, function() {
                callback.apply(window, args);
            }, delay);
            
            intervals.get(id).realId = realId;
        }
        
        return id;
    };

    // clearInterval
    const originalClearInterval = window.clearInterval;
    window.clearInterval = function(id) {
        const interval = intervals.get(id);
        if (interval) {
            if (interval.realId !== undefined && typeof originalClearInterval === 'function') {
                originalClearInterval.call(window, interval.realId);
            }
            intervals.delete(id);
        }
    };

    // queueMicrotask
    window.queueMicrotask = window.queueMicrotask || function(callback) {
        Promise.resolve().then(callback);
    };

    // 用于调试：获取所有活动定时器
    window.__getActiveTimers__ = function() {
        return {
            timeouts: Array.from(timers.entries()).map(([id, t]) => ({
                id,
                delay: t.delay,
                age: Date.now() - t.createdAt
            })),
            intervals: Array.from(intervals.entries()).map(([id, i]) => ({
                id,
                delay: i.delay,
                age: Date.now() - i.createdAt
            }))
        };
    };

    // 清除所有定时器
    window.__clearAllTimers__ = function() {
        timers.forEach((timer, id) => window.clearTimeout(id));
        intervals.forEach((interval, id) => window.clearInterval(id));
    };
})();
