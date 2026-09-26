/**
 * @env-module EnvMonitor
 * @description 环境监控核心 - 完整的DOM/BOM操作监控、mock配置、调用链追踪
 * @status 高级可选模块。日常优先使用 core/ProxyMonitor.js。
 * @use-when 需要以下能力之一：
 *   - 完整日志系统（按 access/call/DOM/create 分类存储 + undefined 自动记录）
 *   - 多类型 Mock 存储（property/method/returnValue/conditional 分别管理）
 *   - 丰富的查询筛选 API（getUndefinedLogs/getCallLogs/getCreateLogs/getDOMLogs/getAllLogs）
 *   - 日志导出（exportLogs json）和 undefined 修复标记（markFixed）
 *   - 逐类清除日志（clearLogs category）
 * @not-for 只需要基础 watch/safefunction 的常规补环境流程 → 用 ProxyMonitor.js
 * @conflict 与 core/MonitorSystem.js 互斥（二者均注册 window.__EnvMonitor__），不要同时加载。与 core/ProxyMonitor.js 不建议混用（功能重叠）。
 * @alternatives core/ProxyMonitor.js（首选，所有模块的基础依赖）、core/MonitorSystem.js（侧重元素代理 + 属性监控 + mock 钩子）
 * @version 2.0.0
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    'use strict';

    const METADATA_MAX_DEPTH = 4;
    const METADATA_MAX_KEYS = 32;

    function sanitizeMetadata(value, depth = 0, seen = new WeakSet()) {
        if (value === undefined) return { type: 'undefined' };
        if (value === null) return { type: 'null' };

        const valueType = typeof value;
        if (valueType === 'string') return { type: 'string', length: value.length };
        if (valueType === 'number') return { type: 'number' };
        if (valueType === 'boolean') return { type: 'boolean' };
        if (valueType === 'bigint') return { type: 'bigint' };
        if (valueType === 'symbol') return { type: 'symbol' };
        if (valueType === 'function') return { type: 'function' };
        if (valueType !== 'object') return { type: 'unknown' };

        if (seen.has(value)) return { type: 'object', circular: true };
        seen.add(value);

        try {
            if (value instanceof Error) {
                const descriptor = Object.getOwnPropertyDescriptor(value, 'message');
                return {
                    type: 'error',
                    messageLength: descriptor && typeof descriptor.value === 'string'
                        ? descriptor.value.length
                        : null
                };
            }
        } catch (_) {}

        try {
            if (Array.isArray(value)) return { type: 'array', length: value.length };
            if (value instanceof ArrayBuffer) return { type: 'array-buffer', byteLength: value.byteLength };
            if (ArrayBuffer.isView(value)) return { type: 'array-buffer-view', byteLength: value.byteLength };
        } catch (_) {
            return { type: 'object', inspection: 'unavailable' };
        }

        if (depth >= METADATA_MAX_DEPTH) return { type: 'object', truncated: true };

        let descriptors;
        try {
            descriptors = Object.getOwnPropertyDescriptors(value);
        } catch (_) {
            return { type: 'object', inspection: 'unavailable' };
        }

        const keys = Object.keys(descriptors);
        const fields = Object.create(null);
        for (const key of keys.slice(0, METADATA_MAX_KEYS)) {
            const descriptor = descriptors[key];
            fields[key] = Object.prototype.hasOwnProperty.call(descriptor, 'value')
                ? sanitizeMetadata(descriptor.value, depth + 1, seen)
                : { type: 'accessor' };
        }

        return {
            type: 'object',
            keyCount: keys.length,
            fields,
            truncated: keys.length > METADATA_MAX_KEYS
        };
    }
    
    // ==================== 监控配置 ====================
    const MonitorConfig = {
        enabled: true,
        logLevel: 'all', // 'all', 'undefined', 'calls', 'none'
        maxLogSize: 10000,
        maxChainDepth: 50,
        trackPropertyAccess: true,
        trackMethodCalls: true,
        trackElementCreation: true,
        trackDOMOperations: true,
        autoRecordUndefined: true,
        // Mock 配置
        mockEnabled: true,
        // 详细日志开关
        verboseMode: false
    };
    
    // ==================== 日志存储 ====================
    const LogStore = {
        // 属性访问日志
        accessLogs: [],
        // 方法调用日志
        callLogs: [],
        // undefined 访问日志
        undefinedLogs: [],
        // 元素创建日志
        createLogs: [],
        // DOM 操作日志
        domLogs: [],
        // 调用链日志
        chainLogs: [],
        // 全部日志（按时间顺序）
        allLogs: []
    };
    
    // ==================== Mock 存储 ====================
    const MockStore = {
        // 属性 mock: { 'navigator.userAgent': 'Mozilla/5.0...' }
        properties: {},
        // 方法 mock: { 'document.createElement': function(tag) { ... } }
        methods: {},
        // 返回值 mock: { 'document.getElementById:myId': <element> }
        returnValues: {},
        // 条件 mock: { 'fetch': [{ condition: (url) => url.includes('api'), result: {...} }] }
        conditionalMocks: {}
    };
    
    // ==================== 调用链追踪 ====================
    const CallChain = {
        stack: [],
        maxDepth: MonitorConfig.maxChainDepth,
        
        push: function(call) {
            if (this.stack.length < this.maxDepth) {
                this.stack.push({
                    call: call,
                    timestamp: Date.now(),
                    depth: this.stack.length
                });
            }
        },
        
        pop: function() {
            return this.stack.pop();
        },
        
        current: function() {
            return this.stack[this.stack.length - 1];
        },
        
        getChain: function() {
            return this.stack.map(s => s.call).join(' -> ');
        },
        
        clear: function() {
            this.stack = [];
        }
    };
    
    // ==================== 唯一ID生成 ====================
    let __logId__ = 0;
    function generateLogId() {
        return 'log_' + (++__logId__) + '_' + Date.now();
    }
    
    // ==================== 核心监控对象 ====================
    const EnvMonitor = {
        config: MonitorConfig,
        logs: LogStore,
        mocks: MockStore,
        chain: CallChain,
        
        // ========== 基础日志方法 ==========
        log: function(category, action, data) {
            if (!this.config.enabled) return;
            if (this.config.logLevel === 'none') return;

            const safeData = this._sanitizeMetadata(data);
            
            const logEntry = {
                id: generateLogId(),
                timestamp: Date.now(),
                category: category,
                action: action,
                data: safeData,
                chain: CallChain.getChain()
            };
            
            LogStore.allLogs.push(logEntry);
            if (LogStore.allLogs.length > this.config.maxLogSize) {
                LogStore.allLogs.shift();
            }
            
            // 分类存储
            switch (category) {
                case 'Access':
                    LogStore.accessLogs.push(logEntry);
                    break;
                case 'Call':
                    LogStore.callLogs.push(logEntry);
                    break;
                case 'DOM':
                    LogStore.domLogs.push(logEntry);
                    break;
                case 'Create':
                    LogStore.createLogs.push(logEntry);
                    break;
            }
            
            if (this.config.verboseMode) {
                console.log(`[EnvMonitor][${category}]`, action, safeData);
            }
            
            return logEntry;
        },
        
        // ========== undefined 记录 ==========
        logUndefined: function(path, context) {
            if (!this.config.enabled) return;

            const safeContext = this._sanitizeMetadata(context || {});
            
            const entry = {
                id: generateLogId(),
                timestamp: Date.now(),
                path: path,
                context: safeContext,
                chain: CallChain.getChain(),
                fixed: false
            };
            
            // 检查是否已记录
            const exists = LogStore.undefinedLogs.find(log => log.path === path);
            if (!exists) {
                LogStore.undefinedLogs.push(entry);
                
                if (this.config.verboseMode) {
                    console.warn(`[EnvMonitor][Undefined] ${path}`, safeContext);
                }
            }
            
            return entry;
        },
        
        // ========== 方法调用记录 ==========
        logCall: function(path, args, result, context) {
            if (!this.config.enabled || !this.config.trackMethodCalls) return;
            if (this.config.logLevel === 'undefined') return;
            
            const entry = {
                id: generateLogId(),
                timestamp: Date.now(),
                path: path,
                args: this._serializeArgs(args),
                result: this._serializeValue(result),
                context: this._sanitizeMetadata(context || {}),
                chain: CallChain.getChain()
            };
            
            LogStore.callLogs.push(entry);
            
            if (this.config.verboseMode) {
                console.log(`[EnvMonitor][Call] ${path}`, { args: entry.args, result: entry.result });
            }
            
            return entry;
        },
        
        // ========== 元素创建记录 ==========
        logCreate: function(tagName, element, options) {
            if (!this.config.enabled || !this.config.trackElementCreation) return;
            
            const entry = {
                id: generateLogId(),
                timestamp: Date.now(),
                tagName: tagName,
                elementId: element?.__id__,
                options: this._sanitizeMetadata(options || {}),
                chain: CallChain.getChain(),
                attributes: {},
                properties: {}
            };
            
            LogStore.createLogs.push(entry);
            
            if (this.config.verboseMode) {
                console.log(`[EnvMonitor][Create] <${tagName}>`, { options: entry.options });
            }
            
            return entry;
        },
        
        // ========== 调用链管理 ==========
        pushChain: function(call) {
            CallChain.push(call);
        },
        
        popChain: function() {
            return CallChain.pop();
        },
        
        getChain: function() {
            return CallChain.getChain();
        },
        
        // ========== Mock 管理 ==========
        hasMock: function(path) {
            if (!this.config.mockEnabled) return false;
            return path in MockStore.properties || 
                   path in MockStore.methods || 
                   path in MockStore.returnValues ||
                   path in MockStore.conditionalMocks;
        },
        
        getMock: function(path) {
            if (!this.config.mockEnabled) return undefined;
            
            if (path in MockStore.properties) {
                return { type: 'property', value: MockStore.properties[path] };
            }
            if (path in MockStore.methods) {
                return { type: 'method', value: MockStore.methods[path] };
            }
            if (path in MockStore.returnValues) {
                return { type: 'returnValue', value: MockStore.returnValues[path] };
            }
            
            return undefined;
        },
        
        executeMock: function(path, args, context) {
            if (!this.config.mockEnabled) {
                return { mocked: false };
            }
            
            // 检查条件 mock
            if (path in MockStore.conditionalMocks) {
                const conditions = MockStore.conditionalMocks[path];
                for (const cond of conditions) {
                    try {
                        if (cond.condition.apply(context, args)) {
                            this.log('Mock', 'conditionalMock', { path, args, result: cond.result });
                            return { mocked: true, result: cond.result };
                        }
                    } catch (e) {
                        console.error('[EnvMonitor] Conditional mock error: details redacted');
                    }
                }
            }
            
            // 检查返回值 mock（带参数）
            if (args && args.length > 0) {
                const returnKey = `${path}:${args[0]}`;
                if (returnKey in MockStore.returnValues) {
                    const result = MockStore.returnValues[returnKey];
                    this.log('Mock', 'returnValueMock', { path, key: returnKey, result });
                    return { mocked: true, result };
                }
            }
            
            // 检查方法 mock
            if (path in MockStore.methods) {
                const mockFn = MockStore.methods[path];
                try {
                    const result = mockFn.apply(context, args);
                    this.log('Mock', 'methodMock', { path, args, result });
                    return { mocked: true, result };
                } catch (e) {
                    console.error('[EnvMonitor] Method mock error: details redacted');
                }
            }
            
            return { mocked: false };
        },
        
        // 设置 Mock
        setMock: function(type, path, value) {
            switch (type) {
                case 'property':
                    MockStore.properties[path] = value;
                    break;
                case 'method':
                    MockStore.methods[path] = value;
                    break;
                case 'returnValue':
                    MockStore.returnValues[path] = value;
                    break;
                case 'conditional':
                    if (!MockStore.conditionalMocks[path]) {
                        MockStore.conditionalMocks[path] = [];
                    }
                    MockStore.conditionalMocks[path].push(value);
                    break;
            }
            
            this.log('Mock', 'setMock', { type, path });
        },
        
        // 移除 Mock
        removeMock: function(type, path) {
            switch (type) {
                case 'property':
                    delete MockStore.properties[path];
                    break;
                case 'method':
                    delete MockStore.methods[path];
                    break;
                case 'returnValue':
                    delete MockStore.returnValues[path];
                    break;
                case 'conditional':
                    delete MockStore.conditionalMocks[path];
                    break;
                case 'all':
                    delete MockStore.properties[path];
                    delete MockStore.methods[path];
                    delete MockStore.returnValues[path];
                    delete MockStore.conditionalMocks[path];
                    break;
            }
        },
        
        // 清空所有 Mock
        clearAllMocks: function() {
            MockStore.properties = {};
            MockStore.methods = {};
            MockStore.returnValues = {};
            MockStore.conditionalMocks = {};
        },
        
        // ========== 日志查询 ==========
        getUndefinedLogs: function(options = {}) {
            let logs = LogStore.undefinedLogs;
            
            if (options.unfixedOnly) {
                logs = logs.filter(log => !log.fixed);
            }
            if (options.path) {
                logs = logs.filter(log => log.path.includes(options.path));
            }
            if (options.limit) {
                logs = logs.slice(-options.limit);
            }
            
            return logs;
        },
        
        getCallLogs: function(options = {}) {
            let logs = LogStore.callLogs;
            
            if (options.path) {
                logs = logs.filter(log => log.path.includes(options.path));
            }
            if (options.limit) {
                logs = logs.slice(-options.limit);
            }
            
            return logs;
        },
        
        getCreateLogs: function(options = {}) {
            let logs = LogStore.createLogs;
            
            if (options.tagName) {
                logs = logs.filter(log => 
                    log.tagName.toLowerCase() === options.tagName.toLowerCase()
                );
            }
            if (options.limit) {
                logs = logs.slice(-options.limit);
            }
            
            return logs;
        },
        
        getDOMLogs: function(options = {}) {
            let logs = LogStore.domLogs;
            
            if (options.action) {
                logs = logs.filter(log => log.action === options.action);
            }
            if (options.limit) {
                logs = logs.slice(-options.limit);
            }
            
            return logs;
        },
        
        getAllLogs: function(options = {}) {
            let logs = LogStore.allLogs;
            
            if (options.category) {
                logs = logs.filter(log => log.category === options.category);
            }
            if (options.since) {
                logs = logs.filter(log => log.timestamp >= options.since);
            }
            if (options.limit) {
                logs = logs.slice(-options.limit);
            }
            
            return logs;
        },
        
        // ========== 统计信息 ==========
        getStats: function() {
            return {
                totalAccess: LogStore.accessLogs.length,
                totalCalls: LogStore.callLogs.length,
                totalUndefined: LogStore.undefinedLogs.length,
                unfixedUndefined: LogStore.undefinedLogs.filter(l => !l.fixed).length,
                totalCreates: LogStore.createLogs.length,
                totalDOMLogs: LogStore.domLogs.length,
                totalLogs: LogStore.allLogs.length,
                mockCount: {
                    properties: Object.keys(MockStore.properties).length,
                    methods: Object.keys(MockStore.methods).length,
                    returnValues: Object.keys(MockStore.returnValues).length,
                    conditional: Object.keys(MockStore.conditionalMocks).length
                }
            };
        },
        
        // ========== 清空日志 ==========
        clearLogs: function(category) {
            if (category) {
                switch (category) {
                    case 'access':
                        LogStore.accessLogs = [];
                        break;
                    case 'calls':
                        LogStore.callLogs = [];
                        break;
                    case 'undefined':
                        LogStore.undefinedLogs = [];
                        break;
                    case 'create':
                        LogStore.createLogs = [];
                        break;
                    case 'dom':
                        LogStore.domLogs = [];
                        break;
                }
            } else {
                LogStore.accessLogs = [];
                LogStore.callLogs = [];
                LogStore.undefinedLogs = [];
                LogStore.createLogs = [];
                LogStore.domLogs = [];
                LogStore.chainLogs = [];
                LogStore.allLogs = [];
            }
        },
        
        // ========== 标记 undefined 为已修复 ==========
        markFixed: function(path) {
            const log = LogStore.undefinedLogs.find(l => l.path === path);
            if (log) {
                log.fixed = true;
                log.fixedAt = Date.now();
            }
        },
        
        // ========== 导出日志 ==========
        exportLogs: function(format = 'json') {
            const data = {
                exportedAt: Date.now(),
                stats: this.getStats(),
                config: MonitorConfig,
                logs: {
                    undefined: LogStore.undefinedLogs,
                    calls: LogStore.callLogs,
                    creates: LogStore.createLogs,
                    dom: LogStore.domLogs
                },
                mocks: {
                    properties: Object.keys(MockStore.properties),
                    methods: Object.keys(MockStore.methods),
                    returnValues: Object.keys(MockStore.returnValues)
                }
            };
            
            if (format === 'json') {
                return JSON.stringify(data, null, 2);
            }
            
            return data;
        },
        
        // ========== 辅助方法 ==========
        _serializeArgs: function(args) {
            if (!args) return [];
            return Array.from(args).map(arg => this._serializeValue(arg));
        },
        
        _serializeValue: function(value) {
            return this._sanitizeMetadata(value);
        },

        _sanitizeMetadata: function(value) {
            return sanitizeMetadata(value);
        },
        
        // ========== 配置方法 ==========
        setConfig: function(key, value) {
            if (key in MonitorConfig) {
                MonitorConfig[key] = value;
            }
        },
        
        getConfig: function() {
            return { ...MonitorConfig };
        }
    };
    
    // ==================== 全局暴露 ====================
    window.__EnvMonitor__ = EnvMonitor;
    window.__envMonitor__ = EnvMonitor; // 兼容
    
    // 简化的全局方法
    window.__logUndefined__ = function(path, context) {
        return EnvMonitor.logUndefined(path, context);
    };
    
    window.__logCall__ = function(path, args, result) {
        return EnvMonitor.logCall(path, args, result);
    };
    
    window.__setMock__ = function(type, path, value) {
        return EnvMonitor.setMock(type, path, value);
    };
    
    window.__getMock__ = function(path) {
        return EnvMonitor.getMock(path);
    };
    
})();
