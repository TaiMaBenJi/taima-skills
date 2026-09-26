# Known Limitations

当 Proxy、`Object.defineProperty` 拦截、定向监控和真实值对照都正常，但签名仍然是降级版本时，参考本文。

## VMP opcode 级检测

典型现象：

1. 诊断报告无明显 `ERRORS` / `UNDEFINED`。
2. 外部 hook 看不到可疑访问。
3. 签名前缀、长度或版本仍与浏览器不一致。

可能根因：VMP 字节码解释器在 opcode 层面完成环境检测，不经过可 hook 的外部 JS API。例如 Error.stack 相关探测可能完全在解释器内部完成。

## 已知风险

1. 删除 `Buffer`、伪装 `process`、删除 `Error.prepareStackTrace` 可能都不是唯一检测点。
2. 设置 `Symbol.toStringTag` 只能修复外形，不能修复内部执行语义差异。
3. `vm.createContext` 可能带来 cross-realm 差异。
4. 强行修改内部标志可能只得到短签名或结构错误的降级结果。

## 可选方向

1. 对比浏览器和 Node.js 的 VMP opcode 执行序列，找第一分叉点。
2. 固定 fixture，尝试从环境补丁转向算法提纯。
3. 明确告知用户当前 Node 补环境路径的天花板，评估是否转真实浏览器执行路径。
4. 若服务端接受降级签名，也要标注风险：服务端能区分版本，后续可能封禁。

不要把“能返回 HTTP 200”直接当作补环境完全成功；还要看签名格式、版本、稳定性和业务响应。
