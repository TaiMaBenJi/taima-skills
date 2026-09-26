---
name: adscan-ad-agents
description: Active Directory 攻击多智能体定义集（3 个角色：攻击规划 / 枚举 / 利用操作）。配合 ADScan 工作流或独立用于红队 AD 战役的分阶段推理。Use when planning or executing authorized Active Directory attack chains with staged agent personas.
---

# ADScan AD Agents（多智能体角色定义）

将 AD 攻击分解为 3 个协作角色，各角色文件见本目录：

- `ad-attack-planner.md`
- `ad-enumerator.md`
- `ad-exploit-operator.md`

## 用法

先读 `ad-attack-planner.md` 做战役规划 → `ad-enumerator.md` 枚举 → `ad-exploit-operator.md` 执行利用。
仅限授权环境使用。
