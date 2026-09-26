/**
 * @env-module performance
 * @description Performance API模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    const startTime = Date.now();
    const entries = [];
    const marks = {};
    const measures = {};

    const performance = {
        // 基础属性
        get timeOrigin() {
            return startTime;
        },

        // 高精度时间
        now: function() {
            return Date.now() - startTime;
        },

        // Performance Timing (已废弃但仍广泛使用)
        timing: {
            navigationStart: startTime,
            unloadEventStart: 0,
            unloadEventEnd: 0,
            redirectStart: 0,
            redirectEnd: 0,
            fetchStart: startTime,
            domainLookupStart: startTime,
            domainLookupEnd: startTime,
            connectStart: startTime,
            connectEnd: startTime,
            secureConnectionStart: startTime,
            requestStart: startTime,
            responseStart: startTime + 10,
            responseEnd: startTime + 50,
            domLoading: startTime + 60,
            domInteractive: startTime + 100,
            domContentLoadedEventStart: startTime + 150,
            domContentLoadedEventEnd: startTime + 160,
            domComplete: startTime + 200,
            loadEventStart: startTime + 210,
            loadEventEnd: startTime + 220
        },

        // Navigation Timing
        navigation: {
            type: 0, // TYPE_NAVIGATE
            redirectCount: 0
        },

        // Memory (Chrome特有)
        memory: {
            jsHeapSizeLimit: 2172649472,
            totalJSHeapSize: 10000000,
            usedJSHeapSize: 8000000
        },

        // 标记
        mark: function(name, options) {
            const entry = {
                name: name,
                entryType: 'mark',
                startTime: this.now(),
                duration: 0,
                detail: options?.detail || null
            };
            marks[name] = entry;
            entries.push(entry);
            return entry;
        },

        // 清除标记
        clearMarks: function(name) {
            if (name) {
                delete marks[name];
                const idx = entries.findIndex(e => e.entryType === 'mark' && e.name === name);
                if (idx > -1) entries.splice(idx, 1);
            } else {
                Object.keys(marks).forEach(key => delete marks[key]);
                for (let i = entries.length - 1; i >= 0; i--) {
                    if (entries[i].entryType === 'mark') {
                        entries.splice(i, 1);
                    }
                }
            }
        },

        // 测量
        measure: function(name, startMarkOrOptions, endMark) {
            let startTime = 0;
            let endTime = this.now();
            let detail = null;

            if (typeof startMarkOrOptions === 'object') {
                // 新API格式
                if (startMarkOrOptions.start !== undefined) {
                    if (typeof startMarkOrOptions.start === 'string') {
                        startTime = marks[startMarkOrOptions.start]?.startTime || 0;
                    } else {
                        startTime = startMarkOrOptions.start;
                    }
                }
                if (startMarkOrOptions.end !== undefined) {
                    if (typeof startMarkOrOptions.end === 'string') {
                        endTime = marks[startMarkOrOptions.end]?.startTime || this.now();
                    } else {
                        endTime = startMarkOrOptions.end;
                    }
                }
                if (startMarkOrOptions.duration !== undefined) {
                    endTime = startTime + startMarkOrOptions.duration;
                }
                detail = startMarkOrOptions.detail || null;
            } else {
                // 旧API格式
                if (startMarkOrOptions) {
                    startTime = marks[startMarkOrOptions]?.startTime || 0;
                }
                if (endMark) {
                    endTime = marks[endMark]?.startTime || this.now();
                }
            }

            const entry = {
                name: name,
                entryType: 'measure',
                startTime: startTime,
                duration: endTime - startTime,
                detail: detail
            };
            measures[name] = entry;
            entries.push(entry);
            return entry;
        },

        // 清除测量
        clearMeasures: function(name) {
            if (name) {
                delete measures[name];
                const idx = entries.findIndex(e => e.entryType === 'measure' && e.name === name);
                if (idx > -1) entries.splice(idx, 1);
            } else {
                Object.keys(measures).forEach(key => delete measures[key]);
                for (let i = entries.length - 1; i >= 0; i--) {
                    if (entries[i].entryType === 'measure') {
                        entries.splice(i, 1);
                    }
                }
            }
        },

        // 获取条目
        getEntries: function() {
            return [...entries];
        },

        getEntriesByType: function(type) {
            return entries.filter(e => e.entryType === type);
        },

        getEntriesByName: function(name, type) {
            return entries.filter(e => e.name === name && (!type || e.entryType === type));
        },

        // 清除资源计时
        clearResourceTimings: function() {
            for (let i = entries.length - 1; i >= 0; i--) {
                if (entries[i].entryType === 'resource') {
                    entries.splice(i, 1);
                }
            }
        },

        // 设置资源计时缓冲区大小
        setResourceTimingBufferSize: function(maxSize) {
            // 模拟实现
        },

        // JSON序列化
        toJSON: function() {
            return {
                timeOrigin: this.timeOrigin,
                timing: this.timing,
                navigation: this.navigation
            };
        },

        // 事件目标方法
        addEventListener: function(type, listener) {
            // 模拟实现
        },

        removeEventListener: function(type, listener) {
            // 模拟实现
        },

        dispatchEvent: function(event) {
            return true;
        }
    };

    // PerformanceObserver
    function PerformanceObserver(callback) {
        this.callback = callback;
        this.entryTypes = [];
    }

    PerformanceObserver.prototype = {
        observe: function(options) {
            if (options.entryTypes) {
                this.entryTypes = options.entryTypes;
            }
            if (options.type) {
                this.entryTypes = [options.type];
            }
        },
        disconnect: function() {
            this.entryTypes = [];
        },
        takeRecords: function() {
            return [];
        }
    };

    PerformanceObserver.supportedEntryTypes = [
        'element',
        'event',
        'first-input',
        'largest-contentful-paint',
        'layout-shift',
        'longtask',
        'mark',
        'measure',
        'navigation',
        'paint',
        'resource'
    ];

    // 挂载到window
    window.performance = performance;
    window.PerformanceObserver = PerformanceObserver;
})();
