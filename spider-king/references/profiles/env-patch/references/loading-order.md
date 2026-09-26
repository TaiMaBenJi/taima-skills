# 环境模块加载顺序

## Contents

- [标准加载顺序](#标准加载顺序)
- [分类内部顺序](#分类内部顺序)
- [最小加载集](#最小加载集)
- [实战踩坑经验](#实战踩坑经验)
- [按 undefinedPaths 前缀选择模块的算法](#按-undefinedpaths-前缀选择模块的算法)

## 标准加载顺序

```
core/ProxyMonitor.js          ← env-diagnose.js 始终自动加载
core/ProxyEnv.js              ← 仅未指定 --env 时自动加载
────────────────────────────── ↑ 自动 / ↓ 手动指定
bom/navigator.js
bom/location.js
bom/screen.js
bom/storage.js
bom/window.js
bom/history.js                 ← 按需，依赖 location.js
bom/crypto.js
bom/performance.js
bom/console.js                ← 可选
bom/observers.js              ← 可选
dom/event.js
dom/document.js
dom/elements.js               ← 必须在 document.js 之后
webapi/fetch.js               ← 按需
webapi/xhr.js                 ← 按需
webapi/blob.js                ← 按需
webapi/url.js                 ← 按需
webapi/network.js             ← 按需，需在 xhr/fetch 之后
webapi/runtime-contracts.js   ← 按需，建议在 event/window 之后
encoding/atob.js              ← env-diagnose.js 已内置
encoding/textencoder.js       ← 按需
timer/timeout.js              ← env-diagnose.js 已有 stub
ai-generated/*                ← 最后加载
```

## 分类内部顺序

### BOM 内部顺序
```
navigator → location → screen → storage → window → history → crypto → performance
```
- `navigator.js` 最先：大多数指纹检测首先读 navigator
- `location.js` 其次：history.js 依赖它更新 URL
- `history.js` 在 window.js 之后：需要 `window.location._parseUrl()`，且内部栈依赖 window
- `window.js` 在 navigator/location/screen 之后：它补充窗口级属性，不覆盖已有的
- `crypto.js` 和 `performance.js` 可以放在 BOM 最后

### DOM 内部顺序
```
event → document → elements
```
- `event.js` 定义事件类，`document.js` 可能用到
- `elements.js` **强依赖** `document.js` 提供的 `Element` 基类，必须在之后

### WebAPI 内部顺序
```
fetch → xhr → blob → url → network
```
- `network.js` 增强 XMLHttpRequest 和 fetch，必须最后

## 最小加载集

根据目标脚本需求，只加载实际需要的模块。常见最小集：

### 简单指纹脚本
```
bom/navigator.js, bom/location.js, bom/screen.js
```

### JSVMP 类签名（如 a_bogus）
```
bom/navigator.js, bom/location.js, bom/screen.js, bom/storage.js,
bom/window.js, bom/crypto.js, bom/performance.js,
dom/event.js, dom/document.js, dom/elements.js,
webapi/xhr.js, webapi/url.js, encoding/textencoder.js
```

### 完整浏览器环境
加载所有模块（少见，一般不需要）。

## 实战踩坑经验

### a_bogus119.js 教训

1. **crypto.js 和 performance.js 是 JSVMP 签名的关键依赖**
   - 缺少这两个模块，a_bogus 签名计算结果为 `undefined`
   - JSVMP 用 `crypto.getRandomValues` 生成随机数，用 `performance.now()`/`performance.timeOrigin` 做时间戳
   - 症状：XHR 流程走通，URL 上有 `a_bogus=undefined`

2. **环境必须在目标脚本之前加载**
   - `bdms.init()` 在脚本加载时立即执行，读取 navigator/document 等
   - 如果环境在脚本之后注入，bdms 初始化时拿到的全是 undefined

3. **标准 XHR 流程不可省略**
   - a_bogus 的 `get_ab()` 用 `bdmsInvokeList` 跳过 `xhr.open()`
   - JSVMP 的 wrapped open 负责存储 URL，跳过导致拿不到 URL
   - 解决：用 `xhr.open(method, url) → xhr.send()` 标准流程

4. **真实环境参数很重要**
   - 框架模块提供的是默认值（Chrome 120 + macOS 等）
   - 对于校验严格的网站，需要用同一个可用页面上下文或用户样本采集真实浏览器参数覆盖默认值，不要混用多个来源

## 按 undefinedPaths 前缀选择模块的算法

```
1. 收集所有 undefinedPaths
2. 提取前缀集合（第一个 . 之前的部分）
3. 前缀 → 模块映射（见 env-modules.md）
4. 按标准顺序手动排列要加载的模块
5. 手动补充依赖（如 elements.js 需要 document.js，document.js 前建议加载 event.js）
6. 重新执行诊断
```

注意：`env-diagnose.js` 会按 `--env` 参数给出的顺序逐个加载模块，不会自动排序或补依赖。把这段算法当作人工选择 `--env` 列表的规则。
