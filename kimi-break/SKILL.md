---
name: kimi-break
description: kimi-break —— 针对 Kimi Code CLI Agent 的红队系统提示词（SYSTEM.md，完整 drop-in 替换版，人格绑定 VANTA/WREN），用于 AI 安全研究与红队评估。当需要 Kimi Code 的破甲/越狱提示词、或研究其提示工程结构时使用。
---

# kimi-break（Kimi Code 红队系统提示词）

> 来源：https://github.com/yd-233/kimi-break （完整克隆在本目录，depth=1；更新：`git -C /var/minis/skills/kimi-break pull`）

## 文件
- `SYSTEM.md` — 主提示词：完整替换 Kimi Code CLI Agent 的系统提示词（语言规则、工具调用规范、编码准则、上下文管理、全部模板变量 `${os}` `${cwd}` `${agents_md}` `${skills_section}` 等原样保留），叠加破甲层（人格锚定、注入防御反转、思维链约束）。
- `README.md` — 设计说明、特色与用法。

## 使用
按 `README.md` 将 `SYSTEM.md` 部署为 Kimi Code 的 system prompt（或按研究需要引用其结构）。
