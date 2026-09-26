/**
 * @env-module console
 * @description Console API模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // 日志存储（用于调试）
    const logs = [];
    const MAX_LOGS = 1000;

    function formatArgs(args) {
        return args.map(arg => {
            if (arg === null) return 'null';
            if (arg === undefined) return 'undefined';
            if (typeof arg === 'string') return `[String length=${arg.length}]`;
            if (typeof arg === 'number') return '[Number]';
            if (typeof arg === 'boolean') return '[Boolean]';
            if (typeof arg === 'bigint') return '[BigInt]';
            if (typeof arg === 'function') return '[Function]';
            if (typeof arg === 'symbol') return '[Symbol]';
            if (Array.isArray(arg)) return `[Array length=${arg.length}]`;
            return '[Object]';
        }).join(' ');
    }

    function addLog(level, args) {
        const entry = {
            level,
            message: formatArgs(args),
            timestamp: Date.now()
        };
        logs.push(entry);
        if (logs.length > MAX_LOGS) {
            logs.shift();
        }
    }

    const console = {
        // 基础日志方法
        log: function(...args) {
            addLog('log', args);
        },

        info: function(...args) {
            addLog('info', args);
        },

        warn: function(...args) {
            addLog('warn', args);
        },

        error: function(...args) {
            addLog('error', args);
        },

        debug: function(...args) {
            addLog('debug', args);
        },

        // 断言
        assert: function(condition, ...args) {
            if (!condition) {
                addLog('error', ['Assertion failed:', ...args]);
            }
        },

        // 清除
        clear: function() {
            logs.length = 0;
        },

        // 计数
        _counters: {},
        count: function(label = 'default') {
            if (!this._counters[label]) {
                this._counters[label] = 0;
            }
            this._counters[label]++;
            addLog('log', [`${label}: ${this._counters[label]}`]);
        },

        countReset: function(label = 'default') {
            this._counters[label] = 0;
        },

        // 目录
        dir: function(obj, options) {
            addLog('log', [obj]);
        },

        dirxml: function(obj) {
            addLog('log', [obj]);
        },

        // 分组
        _groupDepth: 0,
        group: function(...args) {
            addLog('log', args);
            this._groupDepth++;
        },

        groupCollapsed: function(...args) {
            addLog('log', args);
            this._groupDepth++;
        },

        groupEnd: function() {
            if (this._groupDepth > 0) {
                this._groupDepth--;
            }
        },

        // 表格
        table: function(data, columns) {
            addLog('log', ['[Table]', data]);
        },

        // 计时
        _timers: {},
        time: function(label = 'default') {
            this._timers[label] = Date.now();
        },

        timeEnd: function(label = 'default') {
            if (this._timers[label]) {
                const duration = Date.now() - this._timers[label];
                addLog('log', [`${label}: ${duration}ms`]);
                delete this._timers[label];
            }
        },

        timeLog: function(label = 'default', ...args) {
            if (this._timers[label]) {
                const duration = Date.now() - this._timers[label];
                addLog('log', [`${label}: ${duration}ms`, ...args]);
            }
        },

        timeStamp: function(label) {
            addLog('log', [`[TimeStamp] ${label || ''}`]);
        },

        // 跟踪
        trace: function(...args) {
            const stack = new Error().stack || '';
            addLog('log', ['Trace:', ...args, '\n', stack]);
        },

        // 性能分析（浏览器开发工具功能，这里只是占位）
        profile: function(label) {},
        profileEnd: function(label) {},

        // 获取日志（调试用）
        __getLogs__: function() {
            return [...logs];
        },

        // 清除日志
        __clearLogs__: function() {
            logs.length = 0;
        }
    };

    // 挂载到window
    window.console = console;
})();
