---
name: deepextract-agents
description: DeepExtractRuntime 的深提取多智能体集（8 个角色：code-lifter / logic-scanner / memory-corruption-scanner / re-analyst / security-auditor / taint-scanner / triage-coordinator / type-reconstructor）。用于跨二进制/字节码深度提取、污点分析与类型重建的编排。Use for orchestrating deep extraction pipelines over binaries and bytecode with specialized agent roles.
---

# DeepExtractRuntime Agents（深提取智能体集）

完整 agent 定义（含 `_shared/` 共享协议与 `registry.json`）位于 `agents/` 子目录。

- `agents/code-lifter.md`
- `agents/logic-scanner.md`
- `agents/memory-corruption-scanner.md`
- `agents/re-analyst.md`
- `agents/security-auditor.md`
- `agents/taint-scanner.md`
- `agents/triage-coordinator.md`
- `agents/type-reconstructor.md`

## 用法

从 `agents/triage-coordinator.md` 开始（分诊协调），再由协调器指派其余角色。
