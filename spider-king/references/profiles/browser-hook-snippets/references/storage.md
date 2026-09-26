# Storage Hook Selection

本文件只说明来源边界。可执行 Cookie/storage Hook 只从 `../scripts/cookie_header.js` 和 `../scripts/storage.js` 生成。

## Cookie

- `document.cookie` Hook 只能证明 JS setter 写入，不能观察 HTTP `Set-Cookie`。
- 使用 `cookieNameIncludes` 过滤，只记录名称和值长度；默认不记录读取和完整值。
- descriptor 不可配置时不强行覆盖，改查 Network 响应头或上游调用点。
- 恢复时还原原 own descriptor；原先没有 own descriptor 时删除临时属性。

## localStorage 与 sessionStorage

- 使用 `keyIncludes` 过滤；默认只记录 write/remove，read 保持关闭。
- value 只输出长度，事件总量受 `maxEvents` 限制。
- `storage.foo = value` 不经过 `setItem`，此时改盯具体 writer 或请求边界，不用 Proxy 包住整个 Storage。

## 表单属性

只有 selector 和属性都明确时才生成单元素 descriptor Hook。保存 own descriptor 和当前值，摘要输出，事件加上限，restore 时恢复 descriptor。不要覆盖所有 `HTMLInputElement.prototype.value`，除非用户明确接受全页影响。

Cookie 名、storage key 和 selector 都未知时，本 profile 证据不足；先用调用链或 Network 取证缩小观察点。
