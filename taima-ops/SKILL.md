---
name: taima-ops
description: 太马奔极内置工具集：实时余额/套餐查询、技能市场安装、Trae-Agent 启动、状态面板。当用户说"查余额/套餐/装技能/跑 trae/看状态"时使用。
---

# 太马奔极 · 内置工具集

本机（沙箱）预装了以下命令，直接在 bash 工具里执行：

| 命令 | 用途 |
|---|---|
| `taima-status` | 状态面板：版本/技能数/余额/破甲状态 |
| `taima-balance` | **实时查询 DeepSeek 套餐/余额**（密钥已预置在 ~/.taima/deepseek.key） |
| `taima-market list [关键词]` | 浏览内置技能市场（163 个） |
| `taima-market install <id>` | 安装单个技能到 /var/minis/skills（App 自动识别） |
| `taima-market install-all` | 一键全部同步 |
| `taima-trae` | 启动 Trae-Agent（ByteDance 开源编码 Agent；首次自动装依赖，DeepSeek 已配好） |
| `taima-sync` | 把内置技能包同步到 /var/minis/skills |

## 约定

- 用户问"套餐/余额/还有多少钱" → 直接跑 `taima-balance` 并转述结果。
- 用户想"装某技能" → 先 `taima-market list 关键词` 找 id，再 `install`。
- 需要跑 Trae-Agent → `taima-trae`（可能需要网络；失败时把错误原样报给用户）。
