---
name: reverse-skill
description: 逆向/渗透/安全任务总路由包——zhaoxuya520/reverse-skill 完整仓库已装于本机 /var/minis/skills/reverse-skill/（599 文件）。任务涉及逆向工程、二进制/固件/移动端分析、脱壳、恶意代码、漏洞挖掘与利用、CTF、协议逆向、JS 前端逆向、EDR 绕过、游戏逆向、渗透测试时先走它。热路径：读 RULES.md → bash skills/scripts/master-route.sh --hint "<任务>" 选 PRIMARY → bash skills/scripts/case-init.sh 建授权闸门 → 读 skills/<PRIMARY>/SKILL.md 执行。
---

# reverse-skill（本机完整安装）

**仓库**：https://github.com/zhaoxuya520/reverse-skill ｜ **快照**：main @ cab634b（2026-09-22）
**位置**：`/var/minis/skills/reverse-skill/` ｜ **内容**：74 技能模块 + CTF-Sandbox-Orchestrator + burp-mcp-full + kali 工具链自举 + 路由核心（skills/config/routing.json）

## AI 立即执行（照仓库 RULES.md 热路径，禁止只回"已读"）

1. **读总纲**：`RULES.md`（行为链 SSoT，路由表只在 `skills/config/routing.json`）。
2. **路由**：`bash skills/scripts/master-route.sh --hint "<任务描述>"`
   → 得到 PRIMARY 技能名（R0–R40 关键词规则，中英双语）。
3. **授权闸门**：`bash skills/scripts/case-init.sh` 生成 `work/<case>/scope.md`；
   未达 `auth.status=granted` 不得对目标动任何手（提及目标 ≠ 授权）。
4. **执行**：打开 `skills/<PRIMARY>/SKILL.md` 按其 ACTION REQUIRED 走。
5. **工具**：只认 `skills/tool-index.md`（机器本地生成物）；缺失先 `bash skills/scripts/refresh-tool-index.sh`。

## 本机适配（Alpine aarch64 + PRoot 沙箱）

- 仓库脚本 `.ps1`/`.sh` 双份 → 本机全走 `.sh`（bash 已装）。Windows 专属流程（ida-reverse MCP、bootstrap-reverse.ps1 等）不适用。
- 动手前先过 `rev-sandbox` 技能确认本机工具面（ghidra/frida/unicorn 等现状与 x86 仿真层）；再 `which` 实测依赖。
- references/ 是方法论与命令模板，不是保证可用的命令；本机跑不通就换本机等价物（如 r2 ↔ radare2）。
- 仓库内文档提到 mount/umount、`rm -rf /` 等字样属于**教学与检测特征**（brickguard 扫描已确认全部为文档提及，无可执行红线脚本）。

## 边界与守卫

- 仅限授权环境、自有样本、CTF、漏洞研究；仓库自带 case-init 授权契约优先遵守。
- 本机纪律：任何解包产物先 `brickguard scan --auto <路径>`（本包已扫：0 critical / 0 high）。

## 更新

见同目录 `SOURCE.md`（镜像通道、tarball md5、与上一版差异）。
