---
name: mobile-security-suite
description: 移动应用安全评估套件（12 维度）：认证/加密/安全存储/网络/平台交互/韧性（反调试·root·完整性）/隐私/代码质量/MASVS 检查表/威胁建模/测试计划/安全开发。当用户要求评估移动应用安全性、审计 APK/IPA、按 MASVS/MASTG 检查、梳理移动漏洞面时使用。
---

# 移动安全评估套件（12 维度）

每个维度一份独立指南，位于 `references/<维度>/SKILL.md`：

| 维度 | 入口 |
|---|---|
| 认证评估 | `references/auth-assessment/SKILL.md` |
| 加密审查 | `references/crypto-review/SKILL.md` |
| 安全存储 | `references/secure-storage-audit/SKILL.md` |
| 网络安全 | `references/network-security-check/SKILL.md` |
| 平台交互 | `references/platform-interaction-review/SKILL.md` |
| 韧性（反调试/root/完整性） | `references/resilience-assessment/SKILL.md` |
| 隐私 | `references/privacy-audit/SKILL.md` |
| 代码质量 | `references/code-quality-scan/SKILL.md` |
| MASVS 检查表 | `references/masvs-checklist/SKILL.md` |
| 威胁建模 | `references/mobile-threat-model/SKILL.md` |
| 测试计划 | `references/mobile-pentest-plan/SKILL.md` |
| 安全开发 | `references/secure-mobile-dev-guide/SKILL.md` |

## 用法

1. 先定位评估维度（可多选），打开对应 `references/<维度>/SKILL.md` 执行。
2. 动态测试与绕过（Frida/脱壳/SSL pinning）配套技能：
   - `android-native-auto-reverse`（全能逆向入口）
   - `android-pt`（OWASP MASVS 全流程）
   - `rev-cronet-ssl`（Cronet 原生层 pinning）
3. 本机工具链：frida 插桩见 `/var/minis/shared/self/frida-kit/README.md`（`ensure-frida` + `fhook`）。
