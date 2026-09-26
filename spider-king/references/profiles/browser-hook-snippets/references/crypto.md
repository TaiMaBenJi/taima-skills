# Crypto Hook Selection

WebCrypto、CryptoJS 和随机数的可执行实现统一使用 `../scripts/crypto_api.js`。该脚本记录 method、algorithm、输入/输出类型与长度，具有事件上限和恢复函数，不输出 key、明文、签名或随机字节。

## WebCrypto

按 `CONFIG.subtleMethods` 只开启目标方法。`digest`、`sign`、`encrypt`、`decrypt` 的参数位置不同，因此只记录算法摘要和末尾 buffer 的类型/长度。Promise resolve/reject 语义必须保持不变。

## CryptoJS

只 Hook 已存在且证据相关的方法。输入和结果只记类型/长度；不要隐式调用可能有副作用的自定义 serializer。恢复时仅在属性仍指向本 Hook 时写回原函数。

## 随机数

`getRandomValues` 默认只记录 typed array 类型和长度。完整随机字节会改变秘密边界，不作为默认日志。

## Encoding

需要观察 `atob`、`btoa`、`TextEncoder` 或 `TextDecoder` 时，在任务项目中按 `crypto_api.js` 的 registry/emit/restore 结构增加一个窄 Hook：过滤调用栈或长度，字符串和 buffer 都只给类型/长度。不得复制全值日志片段。

用户要的是算法入口、脚本 URL 或完整调用链时停止扩写 Hook，按 profile 入口的 capability-aware 契约转交；专用技能不可用时返回 Spider core loop。要本地执行已知入口时转 Spider env-patch profile。
