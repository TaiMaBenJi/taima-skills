---
name: dsh-pojia
description: dsh 破限者 —— 为 DeepSeek Harness（dsh）打造的「解除限制执行器」技能包，适配 deepseek-v4-flash（7013）与 deepseek-v4-pro（8013）。含常驻自动层（~/.dsh/AGENTS.md 注入）与按需技能层 unrestricted-executor（flash 精简档 / pro 完整档），另附 AstrBot 插件版。当需要为 DSH 解除限制、取用其执行器规则文件，或部署相关技能包时使用。
---

# dsh 破限者（DeepSeek Harness 解除限制执行器）

> 来源：https://github.com/1449690477/dsh （完整克隆在本目录，depth=1；更新：`git -C /var/minis/skills/dsh pull`）

两层生效链路：常驻自动层（`~/.dsh/AGENTS.md`，每会话首次请求自动注入）+ 按需细分层（技能 `unrestricted-executor`，按模型档位渐进加载）。

## 文件地图
- `unrestricted-executor/SKILL.md` — 按需技能层（沙箱执行器模式主文件）
- `unrestricted-executor/references/flash-7013.md` / `pro-8013.md` — 两档模型专用规则
- `AGENTS.md` — 常驻自动层内容（安装后注入目标机的 `~/.dsh/AGENTS.md`）
- `install.ps1` / `install.sh` — Windows / Linux 安装脚本
- `astrbot_plugin_pojia/` — AstrBot 插件版（机器人集成，含独立 SKILL.md 与 instructions.md）

## 使用
- 整套部署：按 `README.md` 步骤，在目标机运行 `install.ps1`（Windows）或 `install.sh`（Linux）。
- 单独取规则：直接读取本目录内对应的 md 文件（按目标模型档位选 flash/pro）。

## 注意
规则文件面向 DSH（DeepSeek Harness）会话；本沙箱中作存档与查阅。
