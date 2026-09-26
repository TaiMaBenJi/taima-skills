# Runtime Hook Selection

动态代码、Blob、Worker 和 timer Hook 破坏面较大。本文件只规定选择和交付约束；生成新脚本时复用 `../scripts/xhr_fetch.js` 的 filter/cap/registry/restore 结构，不使用无生命周期的历史片段。

## JSON

只有明确字段、URL 或调用栈特征时才观察 `JSON.parse/stringify`。字符串和对象只输出类型/长度；全站 JSON Hook 必须有很低的事件上限并尽快恢复。

## eval And Function

优先使用 debugger/source instrumentation。确需 Hook 时只摘要 source 长度和 hash，保持 direct/indirect eval 语义风险声明；构造器替换可被检测，命中异常立即恢复。

## Blob And Object URL

记录 Blob part 类型、总字节数和 MIME，不打印完整脚本/二进制。`URL.createObjectURL` 只关联 Blob metadata。构造器 prototype、static 属性、`new` 语义和 restore 都必须验证。

## Worker

过滤明确 script URL。constructor、`postMessage` 和 message listener 分别限流，payload 只摘要类型/长度，restore 时还原构造器并移除 listener。Worker 在 Hook 安装前创建时，改从创建调用栈取证。

## Timers

只观察 source 命中特定 token 的 callback，不取消、不改 delay、不清空所有 timer。记录 delay、callback 类型和一次 stack；restore 后原 timer API 必须保持引用一致。

未知动态入口或需要完整函数位置时，按 profile 入口的 capability-aware 契约转交；专用技能不可用时返回 Spider core loop。本 profile 不通过扩大 Runtime Hook 来代替调用链取证。
