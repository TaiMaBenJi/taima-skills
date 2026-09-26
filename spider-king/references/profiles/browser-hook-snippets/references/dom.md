# DOM Hook Selection

DOM/Canvas 没有通用的“全开”安全脚本。先确定一个 tag、selector、method 或 canvas operation，再在任务项目中按 `../scripts/xhr_fetch.js` 的 lifecycle 结构生成专用脚本。

## Element Creation And Insertion

- `createElement` 只过滤 `script`、`iframe` 或用户指定 tag。
- `appendChild`/`insertBefore` 只记录 tag、src 是否存在和父节点类型，不打印完整 node/HTML。
- 保存原函数，保持 receiver、参数、返回值和异常，restore 时条件式写回。

## MutationObserver

优先用 observer 而不是改写原型。限制 root、subtree 范围、tag/selector 和事件数；日志只给节点类型和受控属性。restore 必须 `disconnect()` 并删除 registry 项。

## Canvas

只观察已确认的 `getContext`、`fillText` 或 `toDataURL` 边界。文本只给长度，data URL 只给 MIME/长度，WebGL 参数只给明确 pname。Canvas Hook 可显著改变指纹路径，命中异常时立即恢复并转引擎级 trace。

## Delivery Contract

新 DOM 脚本必须具备 `CONFIG` filter、`maxEvents`、摘要函数、`window.__spiderHooks.<name>.restore()` 和一次可信触发验证。缺少 selector/tag 时先补证据，不生成全局原型 Hook。
