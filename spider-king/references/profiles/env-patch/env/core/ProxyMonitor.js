/**
 * @env-module ProxyMonitor
 * @description 高级代理监控系统 - 完整的对象追踪和 toString 保护
 * @version 2.0.0
 */

(() => {
    'use strict';
    
    // ==================== toString 保护 ====================
    const $toString = Function.toString;
    const myFunction_toString_symbol = Symbol('('.concat('', ')_', (Math.random() + '').toString(36)));
    
    const myToString = function () {
        return typeof this == 'function' && this[myFunction_toString_symbol] || $toString.call(this);
    };

    function set_native(func, key, value) {
        Object.defineProperty(func, key, {
            "enumerable": false,
            "configurable": true,
            "writable": true,
            "value": value
        })
    }

    // 删除并重写 toString
    delete Function.prototype['toString'];
    set_native(Function.prototype, "toString", myToString);
    set_native(Function.prototype.toString, myFunction_toString_symbol, "function toString() { [native code] }");
    
    // 导出安全函数设置
    globalThis.safefunction = (func) => {
        set_native(func, myFunction_toString_symbol, `function ${func.name || ''}() { [native code] }`);
    };
    
    // ==================== 日志配置 ====================
    const LogConfig = {
        enabled: true,
        logGet: true,
        logSet: true,
        logCall: true,
        logConstruct: true,
        maxLogs: 1000
    };
    
    const LogStore = {
        get: [],
        set: [],
        call: [],
        construct: [],
        other: []
    };
    
    // ==================== 核心 watch 函数 ====================
    globalThis.watch = function(obj, obj_name) {
        // 如果 obj 是 undefined 或 null，返回原值
        if (obj === undefined || obj === null) {
            if (LogConfig.enabled) {
                console.log(`[ProxyMonitor] 警告: "${obj_name}" 是 ${obj === null ? 'null' : 'undefined'}，跳过代理`);
            }
            return obj;
        }

        // 如果不是对象类型（包括函数），也返回原值
        if (typeof obj !== 'object' && typeof obj !== 'function') {
            if (LogConfig.enabled) {
                console.log(`[ProxyMonitor] 警告: "${obj_name}" 不是对象或函数类型，而是 ${typeof obj}，跳过代理`);
            }
            return obj;
        }

        const handler = {
            get(target, property, receiver) {
                // 特殊属性不记录
                if (property === 'toJSON' || property === '__isProxy__') {
                    return target[property];
                }
                
                if (LogConfig.enabled && LogConfig.logGet) {
                    const logEntry = {
                        method: 'get',
                        object: obj_name,
                        property: typeof property === 'symbol' ? property.toString() : property,
                        propertyType: typeof property,
                        valueType: typeof target[property],
                        timestamp: Date.now()
                    };
                    
                    LogStore.get.push(logEntry);
                    if (LogStore.get.length > LogConfig.maxLogs) {
                        LogStore.get.shift();
                    }
                    
                    console.log(
                        `方法: get  | 对象: "${obj_name}" | 属性: ${logEntry.property} | 属性类型: ${logEntry.propertyType} | 属性值类型: ${logEntry.valueType}`
                    );
                }
                
                return Reflect.get(target, property, receiver);
            },
            
            set(target, property, value, receiver) {
                if (LogConfig.enabled && LogConfig.logSet) {
                    const logEntry = {
                        method: 'set',
                        object: obj_name,
                        property: typeof property === 'symbol' ? property.toString() : property,
                        propertyType: typeof property,
                        valueType: typeof value,
                        timestamp: Date.now()
                    };
                    
                    LogStore.set.push(logEntry);
                    if (LogStore.set.length > LogConfig.maxLogs) {
                        LogStore.set.shift();
                    }
                    
                    console.log(
                        `方法: set  | 对象: "${obj_name}" | 属性: ${logEntry.property} | 属性类型: ${logEntry.propertyType} | 属性值类型: ${logEntry.valueType}`
                    );
                }
                
                return Reflect.set(target, property, value, receiver);
            },
            
            has(target, property) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: has  | 对象: "${obj_name}" | 属性: ${typeof property === 'symbol' ? property.toString() : property} | 属性类型: ${typeof property} | 检查自身或原型链属性是否存在`
                    );
                }
                return Reflect.has(target, property);
            },
            
            ownKeys(target) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: ownKeys  | 对象: "${obj_name}" | 获取自身可枚举属性键`
                    );
                }
                return Reflect.ownKeys(target);
            },
            
            getOwnPropertyDescriptor(target, property) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: getOwnPropertyDescriptor  | 对象: "${obj_name}" | 属性: ${typeof property === 'symbol' ? property.toString() : property} | 属性类型: ${typeof property} | 获取属性描述符`
                    );
                }
                return Reflect.getOwnPropertyDescriptor(target, property);
            },
            
            defineProperty(target, property, descriptor) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: defineProperty  | 对象: "${obj_name}" | 属性: ${typeof property === 'symbol' ? property.toString() : property} | 属性类型: ${typeof property} | 定义或修改属性描述符`
                    );
                }
                return Reflect.defineProperty(target, property, descriptor);
            },
            
            deleteProperty(target, property) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: deleteProperty  | 对象: "${obj_name}" | 属性: ${typeof property === 'symbol' ? property.toString() : property} | 属性类型: ${typeof property} | 删除属性`
                    );
                }
                return Reflect.deleteProperty(target, property);
            },
            
            getPrototypeOf(target) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: getPrototypeOf  | 对象: "${obj_name}" | 获取原型链`
                    );
                }
                return Reflect.getPrototypeOf(target);
            },
            
            setPrototypeOf(target, proto) {
                if (LogConfig.enabled) {
                    console.log(
                        `方法: setPrototypeOf  | 对象: "${obj_name}" | 设置新原型: ${proto ? proto.constructor.name : 'null'}`
                    );
                }
                return Reflect.setPrototypeOf(target, proto);
            },
            
            apply(target, thisArg, argumentsList) {
                if (LogConfig.enabled && LogConfig.logCall) {
                    const logEntry = {
                        method: 'apply',
                        object: obj_name,
                        argsCount: argumentsList.length,
                        timestamp: Date.now()
                    };
                    
                    LogStore.call.push(logEntry);
                    if (LogStore.call.length > LogConfig.maxLogs) {
                        LogStore.call.shift();
                    }
                    
                    console.log(
                        `方法: apply  | 对象: "${obj_name}" | 函数调用 | 参数数量: ${argumentsList.length}`
                    );
                }
                return Reflect.apply(target, thisArg, argumentsList);
            },
            
            construct(target, argumentsList, newTarget) {
                if (LogConfig.enabled && LogConfig.logConstruct) {
                    const logEntry = {
                        method: 'construct',
                        object: obj_name,
                        argsCount: argumentsList.length,
                        timestamp: Date.now()
                    };
                    
                    LogStore.construct.push(logEntry);
                    if (LogStore.construct.length > LogConfig.maxLogs) {
                        LogStore.construct.shift();
                    }
                    
                    console.log(
                        `方法: construct  | 对象: "${obj_name}" | 构造函数调用 | 参数数量: ${argumentsList.length}`
                    );
                }
                return Reflect.construct(target, argumentsList, newTarget);
            }
        };

        return new Proxy(obj, handler);
    };
    
    // ==================== makeFunction 辅助函数 ====================
    globalThis.makeFunction = function(name) {
        // 动态创建一个函数
        var func = new Function(`
            return function ${name}() {
                console.log('[Function] ${name} 被调用，参数:', arguments)
            }
        `)();

        // 设置为原生函数
        globalThis.safefunction(func);

        // 代理原型
        if (func.prototype) {
            func.prototype = watch(func.prototype, `方法原型:${name}.prototype`)
        }

        func = watch(func, `方法本身:${name}`)
        return func;
    };
    
    // ==================== 日志管理 ====================
    globalThis.__ProxyMonitor__ = {
        config: LogConfig,
        logs: LogStore,
        
        // 获取日志
        getLogs(type) {
            if (type) {
                return LogStore[type] || [];
            }
            return LogStore;
        },
        
        // 清空日志
        clearLogs(type) {
            if (type) {
                LogStore[type] = [];
            } else {
                Object.keys(LogStore).forEach(key => {
                    LogStore[key] = [];
                });
            }
        },
        
        // 获取统计
        getStats() {
            return {
                get: LogStore.get.length,
                set: LogStore.set.length,
                call: LogStore.call.length,
                construct: LogStore.construct.length,
                total: LogStore.get.length + LogStore.set.length + LogStore.call.length + LogStore.construct.length
            };
        },
        
        // 设置配置
        setConfig(key, value) {
            if (key in LogConfig) {
                LogConfig[key] = value;
            }
        }
    };
    
    console.log('[ProxyMonitor] 代理监控系统已加载');
})();
