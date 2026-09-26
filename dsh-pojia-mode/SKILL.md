---
name: dsh-pojia-mode
description: DSH（DeepSeek Harness）「破甲模式」安装器 v1.0（Windows / PowerShell）：双击即装、不改 DSH 代码、改前自动备份、可一键卸载、零依赖。当需要给 DSH 增加破甲模式、解锁受限的模式选择器、或安装/卸载该补丁时使用。
---

# DSH 破甲模式（dsh-pojia-mode）

> 来源：https://github.com/z91772524-ai/dsh-pojia-mode （完整克隆在本目录，depth=1；更新：`git -C /var/minis/skills/dsh-pojia-mode pull`）

双击一个文件，DSH（DeepSeek Harness）就多出一个「破甲模式」——不改 DSH 一字节代码、不动官方目录、升级不丢；改前自动备份、装完可自证、随时可一键卸载。

## 文件地图
- `unlock-dsh.ps1` — 主安装脚本（PowerShell 5.1+）
- `unlock-dsh.bat` — 双击入口
- `unlock-dsh-silent.vbs` — 无黑框静默入口
- `assets/` — 注入模板（`agent.cordis.yml.tmpl`、`preset.yml.tmpl`）、`make_preview.py`、预览图
- `SHA256SUMS.txt` — 完整性校验；`build.ps1` — 构建脚本

## 使用
仅 Windows：在本目录（或 clone/下载的副本）双击 `unlock-dsh.bat`；卸载与安全设计见 `README.md`。

## 注意
本沙箱（Android/Alpine）仅作存档与查阅；脚本需在 Windows 机器上运行。
