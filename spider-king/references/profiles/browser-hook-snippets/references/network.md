# Network Hook Selection

本文件只做 Hook 点选择，不提供另一套可粘贴实现。XHR/fetch 请求必须从 `../scripts/xhr_fetch.js` 或 `../scripts/cookie_header.js` 生成，避免无过滤、无事件上限、无恢复函数的旧片段漂移回来。

## XHR 与 Fetch

- 请求 method、URL、body 长度和响应状态：使用 `xhr_fetch.js`。
- Cookie/Authorization/x-sign/token 与具体请求绑定：使用 `cookie_header.js`。
- 修改脚本顶部 `CONFIG.urlIncludes` 和 header filter 后再交付；默认不打印 header/body 值。
- XHR 二进制响应只记录 `response` 的类型/长度，不直接读取 `responseText`。

## WebSocket

仅盯明确 URL 或消息类型。新增项目脚本时必须同时保存并恢复 `WebSocket.prototype.send` 或 listener，给发送和接收各自的事件上限，并只输出 opcode、类型和长度。不得默认输出 frame 内容。

## jQuery Ajax

只有证据表明参数在 jQuery 包装层被改写时才 Hook `jQuery.ajax`。过滤 URL，摘要 `data`/headers，保留原 `this`、返回 jqXHR 和异常行为，并在 registry 中登记恢复函数。

## postMessage

必须过滤 `targetOrigin`、`event.origin` 或明确消息字段。transferable、ArrayBuffer 和对象 payload 只输出类型与长度；添加的 message listener 必须在 restore 中移除。

## 页面上下文

Console 处于 isolated world 时才把同一受控脚本注入 main world。注入不改变过滤、上限、摘要和 restore 契约。用户真正要 initiator 或完整调用链时停止扩写 Hook，按 profile 入口的 capability-aware 契约转交；专用技能不可用时返回 Spider core loop。
