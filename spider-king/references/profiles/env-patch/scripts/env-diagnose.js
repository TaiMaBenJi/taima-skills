#!/usr/bin/env node
/**
 * JS compatibility-context diagnostic tool.
 * Node's vm API is not a security boundary. Run unknown target code in an
 * external disposable OS/container sandbox and acknowledge that risk here.
 *
 * 用法:
 *   node env-diagnose.js --external-sandbox-confirmed target.js
 *   node env-diagnose.js --external-sandbox-confirmed --env bom/navigator.js,bom/crypto.js target.js
 *
 * 输出: JSON 到 stdout
 *   {
 *     "success": true/false,
 *     "error": null | "错误信息",
 *     "undefinedPaths": ["window.crypto.getRandomValues", ...],
 *     "stats": { "get": N, "set": N, "call": N, "construct": N, "total": N },
 *     "consoleOutput": [["log", "msg"], ["error", "msg"], ...]
 *   }
 */

import vm from 'vm';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── 参数解析 ─────────────────────────────────────────────
const args = process.argv.slice(2);
let targetFile = null;
let envModules = [];
let timeout = 60000;
let quiet = false;
let externalSandboxConfirmed = false;

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if ((arg === '--env' || arg === '-e') && i + 1 < args.length) {
    // 支持逗号分隔和多次 --env
    envModules.push(...args[++i].split(',').map(s => s.trim()).filter(Boolean));
  } else if (arg === '--timeout' && i + 1 < args.length) {
    timeout = parseInt(args[++i], 10);
  } else if (arg === '--quiet' || arg === '-q') {
    quiet = true;
  } else if (arg === '--external-sandbox-confirmed') {
    externalSandboxConfirmed = true;
  } else if (arg === '--help' || arg === '-h') {
    console.log(`用法: node env-diagnose.js [选项] <目标脚本>

选项:
  --env, -e <模块列表>      加载的 env 模块（逗号分隔或多次指定）
                             内置路径相对于 profile/env/；工作区 custom patch 可用相对或绝对路径
  --timeout <毫秒>          执行超时（默认 60000）
  --quiet, -q              不输出日志到 stderr
  --external-sandbox-confirmed  确认当前进程已置于外部隔离环境；node:vm 本身不是安全边界
  --help, -h               显示帮助

示例:
  node env-diagnose.js --external-sandbox-confirmed target.js
  node env-diagnose.js --external-sandbox-confirmed --env bom/navigator.js,bom/crypto.js target.js`);
    process.exit(0);
  } else if (!targetFile) {
    targetFile = arg;
  }
}

if (!targetFile) {
  console.error('错误: 请提供目标脚本文件');
  process.exit(1);
}

if (!externalSandboxConfirmed) {
  console.log(JSON.stringify({
    success: false,
    error: 'Refusing execution: node:vm is a compatibility context, not a security boundary. Run unknown code in an external disposable sandbox, then pass --external-sandbox-confirmed.',
    undefinedPaths: [],
    stats: { get: 0, set: 0, call: 0, construct: 0, total: 0 },
    consoleOutput: [],
  }, null, 2));
  process.exit(2);
}

// ─── 定位框架目录 ─────────────────────────────────────────
function findSkillDir() {
  // profile 自包含，env 目录固定在 profile 根目录下
  const skillRoot = path.resolve(__dirname, '..');
  const envDir = path.join(skillRoot, 'env');
  if (!fs.existsSync(path.join(envDir, 'core', 'ProxyMonitor.js'))) {
    console.error(`错误: env 目录不完整，缺少 core/ProxyMonitor.js: ${envDir}`);
    process.exit(1);
  }
  return skillRoot;
}

const FRAMEWORK = findSkillDir();
const ENV_DIR = path.join(FRAMEWORK, 'env');

function log(msg) {
  if (!quiet) process.stderr.write(msg + '\n');
}

// ─── 创建兼容上下文 ───────────────────────────────────────
// Do not inject host functions or objects. A host closure such as an arrow
// around Buffer exposes its host Function constructor to target code.
const context = vm.createContext(Object.create(null), {
  name: 'spider-env-diagnose',
  codeGeneration: { strings: true, wasm: false },
});

const guestBootstrap = String.raw`
(function () {
  'use strict';
  const output = [];
  const proxyPattern = /^方法: (get|set|has|ownKeys|getOwnPropertyDescriptor|defineProperty|deleteProperty|getPrototypeOf|setPrototypeOf|apply|construct)\s+\|/;
  function safeValue(value) {
    if (value === null || value === undefined || typeof value === 'number' || typeof value === 'boolean') return value;
    if (typeof value === 'string') return '[String length=' + value.length + ']';
    if (typeof value === 'bigint') return '[BigInt]';
    if (typeof value === 'symbol') return '[Symbol]';
    if (typeof value === 'function') return '[Function]';
    try { if (Array.isArray(value)) return '[Array]'; } catch (_) {}
    return '[Object]';
  }
  function record(level, args) {
    const first = args.length && typeof args[0] === 'string' ? args[0] : '';
    if (globalThis.__suppressProxyLogs__ && (proxyPattern.test(first) || first.startsWith('[ProxyMonitor]'))) return;
    output.push([level].concat(Array.prototype.map.call(args, safeValue)));
  }
  const guestConsole = Object.create(null);
  for (const level of ['log', 'error', 'warn', 'info', 'debug', 'trace', 'dir', 'table']) {
    guestConsole[level] = function () { record(level, arguments); };
  }
  for (const level of ['group', 'groupCollapsed', 'groupEnd', 'time', 'timeEnd', 'timeLog', 'count', 'countReset', 'assert', 'clear']) {
    guestConsole[level] = function () {};
  }

  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
  function atobCompat(input) {
    const text = String(input).replace(/[\t\n\f\r ]/g, '');
    if (text.length % 4 === 1 || /[^A-Za-z0-9+/=]/.test(text)) throw new TypeError('Invalid character');
    let outputText = '';
    let buffer = 0;
    let bits = 0;
    for (const char of text.replace(/=+$/, '')) {
      buffer = (buffer << 6) | alphabet.indexOf(char);
      bits += 6;
      if (bits >= 8) {
        bits -= 8;
        outputText += String.fromCharCode((buffer >> bits) & 255);
      }
    }
    return outputText;
  }
  function btoaCompat(input) {
    const text = String(input);
    let outputText = '';
    for (let index = 0; index < text.length; index += 3) {
      const a = text.charCodeAt(index);
      const b = text.charCodeAt(index + 1);
      const c = text.charCodeAt(index + 2);
      if (a > 255 || b > 255 || c > 255) throw new TypeError('Invalid character');
      const triple = (a << 16) | ((Number.isNaN(b) ? 0 : b) << 8) | (Number.isNaN(c) ? 0 : c);
      outputText += alphabet[(triple >> 18) & 63] + alphabet[(triple >> 12) & 63];
      outputText += Number.isNaN(b) ? '=' : alphabet[(triple >> 6) & 63];
      outputText += Number.isNaN(c) ? '=' : alphabet[triple & 63];
    }
    return outputText;
  }
  class XMLHttpRequestCompat {
    constructor() { this.bdmsInvokeList = []; }
    open() {}
    send() {}
    setRequestHeader() {}
    getResponseHeader() { return null; }
    getAllResponseHeaders() { return ''; }
    addEventListener() {}
    removeEventListener() {}
  }

  Object.assign(globalThis, {
    console: guestConsole,
    setTimeout: function () { return 0; },
    setInterval: function () { return 0; },
    clearTimeout: function () {},
    clearInterval: function () {},
    atob: atobCompat,
    btoa: btoaCompat,
    XMLHttpRequest: XMLHttpRequestCompat,
    __output__: output,
    __suppressProxyLogs__: false,
  });
  globalThis.window = globalThis;
  globalThis.global = globalThis;
  globalThis.self = globalThis;
})();
`;
vm.runInContext(guestBootstrap, context, { timeout });

// ─── 加载 ProxyMonitor ────────────────────────────────────
const proxyMonitorPath = path.join(ENV_DIR, 'core', 'ProxyMonitor.js');
if (!fs.existsSync(proxyMonitorPath)) {
  console.error(`错误: ProxyMonitor.js 不存在: ${proxyMonitorPath}`);
  process.exit(1);
}

log('[diagnose] 加载 ProxyMonitor...');
vm.runInContext(fs.readFileSync(proxyMonitorPath, 'utf-8'), context, { timeout });

// 仅在没有指定 env 模块时加载 ProxyEnv（提供 watch() 包裹的基本对象）
// 当指定了 env 模块时，ProxyEnv 的 configurable:false 属性会阻止完整模块覆盖
const proxyEnvPath = path.join(ENV_DIR, 'core', 'ProxyEnv.js');
if (envModules.length === 0 && fs.existsSync(proxyEnvPath)) {
  log('[diagnose] 加载 ProxyEnv（无 env 模块指定，使用基础代理环境）...');
  vm.runInContext(fs.readFileSync(proxyEnvPath, 'utf-8'), context, { timeout });
}

// ─── 加载用户指定的 env 模块 ──────────────────────────────
const envModuleErrors = [];
for (const mod of envModules) {
  // 优先解析工作区相对 custom patch，再解析 profile 内置 env 模块。
  let modPath;
  if (path.isAbsolute(mod)) {
    modPath = mod;
  } else if (fs.existsSync(path.resolve(process.cwd(), mod))) {
    modPath = path.resolve(process.cwd(), mod);
  } else if (mod.startsWith('env/')) {
    modPath = path.join(FRAMEWORK, mod);
  } else {
    modPath = path.join(ENV_DIR, mod);
  }

  if (!fs.existsSync(modPath)) {
    log(`[diagnose] 警告: 模块不存在，跳过: ${modPath}`);
    envModuleErrors.push('env module not found');
    continue;
  }

  log(`[diagnose] 加载 env 模块: ${mod}`);
  try {
    vm.runInContext(fs.readFileSync(modPath, 'utf-8'), context, { timeout });
  } catch (e) {
    log('[diagnose] env module failed; exception details redacted');
    envModuleErrors.push('env module failed; exception details redacted');
  }
}

// ─── 清空 ProxyMonitor 日志（env 加载期间的日志不算） ──────
try {
  vm.runInContext('__ProxyMonitor__.clearLogs()', context);
} catch (_) {}

// 清空 env 加载日志，并在 guest realm 内抑制 ProxyMonitor 自身噪声。
vm.runInContext('__output__.length = 0; __suppressProxyLogs__ = true;', context);

// ─── 执行目标脚本 ─────────────────────────────────────────
const targetPath = path.resolve(targetFile);
if (!fs.existsSync(targetPath)) {
  console.error(`错误: 目标脚本不存在: ${targetPath}`);
  process.exit(1);
}

log(`[diagnose] 执行目标脚本: ${targetFile}`);
const code = fs.readFileSync(targetPath, 'utf-8');

let success = envModuleErrors.length === 0;
let errorMsg = envModuleErrors.length > 0 ? envModuleErrors.join('\n') : null;

try {
  vm.runInContext(code, context, {
    timeout,
    filename: path.basename(targetFile),
    displayErrors: true,
  });
} catch (e) {
  success = false;
  errorMsg = [errorMsg, 'target execution failed; exception details redacted'].filter(Boolean).join('\n');
}

// ─── 收集诊断结果 ─────────────────────────────────────────
let stats = { get: 0, set: 0, call: 0, construct: 0, total: 0 };
let undefinedPaths = [];

try {
  stats = JSON.parse(vm.runInContext('JSON.stringify(__ProxyMonitor__.getStats())', context));
} catch (_) {}

// 从 getLogs('get') 中提取 valueType === 'undefined' 的条目
try {
  const getLogs = JSON.parse(vm.runInContext('JSON.stringify(__ProxyMonitor__.getLogs("get"))', context));
  if (Array.isArray(getLogs)) {
    const seen = new Set();
    for (const entry of getLogs) {
      if (entry.valueType === 'undefined' && entry.propertyType === 'string') {
        const fullPath = `${entry.object}.${entry.property}`;
        if (!seen.has(fullPath)) {
          seen.add(fullPath);
          undefinedPaths.push(fullPath);
        }
      }
    }
  }
} catch (_) {}

let safeConsoleOutput = [];
try {
  safeConsoleOutput = JSON.parse(vm.runInContext('JSON.stringify(__output__)', context));
} catch (_) {}

// ─── 输出 JSON ────────────────────────────────────────────
const result = {
  success,
  error: errorMsg,
  undefinedPaths,
  stats,
  consoleOutput: safeConsoleOutput,
};

console.log(JSON.stringify(result, null, 2));
process.exit(success ? 0 : 1);
