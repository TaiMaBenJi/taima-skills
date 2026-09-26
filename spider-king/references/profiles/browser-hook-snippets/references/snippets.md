# Browser Hook Snippets

主题文档已经拆分，但不再内嵌第二套可执行片段。受测脚本在 `../scripts/`；主题文档只帮助选择最窄 Hook 点并约束新增脚本。

## 目录

1. `network.md`：XHR、fetch、WebSocket、postMessage、页面上下文注入。
2. `storage.md`：cookie、localStorage、sessionStorage、表单值。
3. `crypto.md`：atob/btoa、crypto.subtle、getRandomValues、TextEncoder/TextDecoder。
4. `dom.md`：createElement、appendChild、insertBefore、MutationObserver、canvas。
5. `runtime.md`：JSON、eval、Function、Blob、URL.createObjectURL、Worker。

## 选择建议

1. 盯请求和消息链路，先读 `network.md`。
2. 盯 token、cookie、缓存、输入框值，先读 `storage.md`。
3. 盯编码、摘要、签名、随机数，先读 `crypto.md`。
4. 盯动态节点、脚本插入、canvas 指纹，先读 `dom.md`。
5. 盯动态执行、worker、blob 资源，先读 `runtime.md`。

## 不建议默认收录的片段

1. 大范围去除 `debugger` 的脚本。
2. 替换所有 `console` 方法的脚本。
3. 全局清除所有 `setInterval`。
4. 粗暴重写 `RegExp`、`Date`、`Function.prototype.constructor`。

原因不是“不能用”，而是副作用通常大于定位收益，容易把页面行为改坏。
