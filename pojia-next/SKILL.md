---
name: pojia-next
description: 破甲一键通 v7.5 —— 把多套破甲工具合并为一个一键脚本（目标：DSH / WorkBuddy / ZCode；统一人格、备份/回滚、破甲自检、--check 只读体检）。Python 主脚本 + Windows 双击 bat。当需要为上述目标做破甲注入/还原、或查阅其回归测试与修复记录时使用。
---

# 破甲一键通（pojia-next v7.5）

> 来源：https://github.com/z91772524-ai/pojia-next （完整克隆在本目录，depth=1；更新：`git -C /var/minis/skills/pojia-next pull`）

## 文件地图
- `破甲一键通.py` — 主脚本（apply / revert / `--check` / 自检；支持 `--dry-run`）
- `一键破甲.bat` — Windows 双击入口
- `persona.md` — 统一人格
- `使用说明.md` — 完整用法（v7.5：Codex 目标已移除；v7.4 修复 19 项，含 4 类数据丢失问题）
- `修复报告.md` / `_回归测试/` — 修复记录与回归测试
- `SHA256SUMS.txt` / `release.py` / `fill_hashes.py` — 发布与校验工具链

## 使用
按 `使用说明.md` 操作：目标机上运行 `python 破甲一键通.py`（或双击 `一键破甲.bat`）；支持备份、还原、自检与只读体检。
