---
name: xiaoliu-pojia
description: 小liu破甲 v2 —— 针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破甲提示词与一键部署工具（deploy.py / ask.py / check.py）。融合 MDX-Tom v42、codex-keysmith、CTF SANDBOX 三大方法论。当需要 Codex CLI 破甲部署、撤销、状态检查或直连 API 调用时使用。
---

# 小liu破甲（Codex CLI 破甲提示词 + 一键部署）

> 来源：https://github.com/xiaoliu07-sudo/xiaoliu-pojia （完整克隆在本目录，depth=1；更新：`git -C /var/minis/skills/xiaoliu-pojia pull`）

## 文件地图
- `deploy.py` — 一键部署（自动发现 `~/.codex`；支持 `--status` / `--undo` / `--dir` 指定目录）
- `ask.py` — 直连 API 调用（绕过 Codex 客户端过滤器）
- `check.py` — 状态检查
- `ctf-sandbox.md` — CTF SANDBOX 方法论（融合来源之一）
- `README.md` — 13 部分融合版设计、特点与完整用法

## 使用
在目标机器上按 `README.md`：`python deploy.py` 部署；`python deploy.py --undo` 撤销；每次操作前自动备份 `config.toml`。
