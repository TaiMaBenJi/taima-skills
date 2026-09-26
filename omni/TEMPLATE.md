---
name: omni
description: 全技能总入口（88 合 1）——本机全部 88 个技能的统一索引与路由。当用户提到「所有技能/全部技能/总入口/合集/万能/omni/该用哪个技能/找不到技能」或任务涉及逆向工程、二进制/APK/iOS/固件分析、脱壳、Frida 插桩、恶意代码、CTF、漏洞利用、红队、Web/协议渗透、YARA、安全评估时，先读本技能定位正确子技能，再加载子技能全文执行。含：全量分类索引、任务→技能路由表、omni 命令行搜索引擎、全库 2987 技能深度检索（skillctl）。
---

# ⚡ OMNI — 全技能总控（88 合 1）

> 一个入口，三层深度：**本文件（88 个已装技能索引 + 路由）** → **`omni` 命令行（搜索/直达）** → **全量库 2987（skillctl）**。

## 0. 使用纪律（先读）

1. **先定位、再加载**：从 §1 路由表或 §3 索引选定 1 个主技能 + 最多 2 个辅助技能，然后 `file_read /var/minis/skills/<name>/SKILL.md` 读全文再动手。禁止凭技能名猜内容。
2. **环境先行**：动手做二进制/固件/移动端/恶意代码任务前，先读 `rev-sandbox`（沙箱工具可用性 / 仿真层 / 防卡死纪律）。
3. **最小加载**：不要一次读多个技能全文；按需逐个读。
4. **越权边界**：全部技能仅限授权环境、自有样本、CTF、漏洞研究。任何"下载并执行外部二进制 / 外传数据"的步骤先停下问用户。
5. **找不到就搜**：`omni find <关键词>`（本机 88）→ 仍无 → `skillctl search <关键词>`（全库 2987）。

## 1. 任务 → 技能 路由速查

| 任务信号 | 先读 |
|---|---|
| 环境 / 工具可用性 / 仿真 / 卡死纪律 | `rev-sandbox` |
| 拿到一个未知文件 | `bin-triage` → 按格式 `elf-analyze` / `pe-analyze` / `macho-analyze` |
| APK / Android App 分析 | `android-native-auto-reverse`（统一入口，再分流） |
| 加固 / 脱壳（梆梆等） | `bangcle-unpack`、`dexdump-toolkit`、`dex-dump`、`unpack` |
| iOS IPA / Mach-O | `ios-reverse-engineering`、`macho-analyze` |
| Frida 钩子 / 插桩 | `rev-frida`、`frida-android-hooks`、`frida-native-hooks`、`frida-ios-hooks` |
| 抓包被证书绑定挡住 | `mobile-cert-pinning-bypass` → `rev-cronet-ssl`（Cronet 系）→ `frida-tls-pinning` |
| 反调试 / 反 Frida / root 检测 | `frida-anti-instrumentation`、`identifying-anti-debugging-techniques` |
| 二进制深入（反编译/符号/类型） | `universal-reverse-engineering` → `ghidra-rpc`、`native-decompile`、`r2-recon`、`rev-symbol` |
| 两个版本对比 / 漏洞变体 | `bindiff`、`diaphora-diff`、`intellidiff`、`variant-analysis` |
| 恶意样本 | `malware-triage` → `malware-re-suite` → `malware-dynamic-analysis` |
| YARA 规则 / 扫描 | `yara-rule-authoring`、`yara-scan` |
| CTF 比赛 | `ctf-reverse`、`ctf-pwn`、`ctf-malware`、`ctf-forensics` |
| Web 漏洞挖掘 / SRC | `src-hunter` |
| 纯 Web 协议逆向 / 采集器 | `protocol-reverse` |
| 固件 / IoT | `firmware-pentest`、`firmware-bringup` |
| 红队内网 / 免杀 / C2 | `offensive-active-directory`、`offensive-edr-evasion`、`dsh-edr-bypass`、`offensive-c2-frameworks` |
| 移动应用安全评估（合规向） | `mobile-android-assessment`、`mobile-security-suite`、`android-pt` |
| 混淆代码还原（JS/Java/.NET/.pyc） | `reverse-eng-deobfuscation`、`js-deobfuscate`、`jvm-decompile`、`dotnet-decompile`、`pyc-decompile` |
| 写 / 改技能 | `skill-creator` |
| 复盘 / 沉淀 / 限制台账 | `self-evolution` |
| 大合集索引 | `pojie`（819 源）、`rev-library-router`（2987 全库检索法） |

## 2. 工具：`omni` 命令行

```sh
omni list                  # 全部技能（按分类）
omni list android          # 按分类/关键词过滤列表
omni find frida hook       # 多关键词搜索（名称+简介+全文）
omni show bangcle-unpack   # 打印技能全文（读完再动手）
omni path src-hunter       # 打印技能目录（找scripts/references/assets）
omni stats                 # 统计
omni rebuild               # 技能目录变化后重建索引
```

## 3. 全量索引（<!--@STATS@-->）

<!--@INDEX@-->

## 4. 第三层：全量技能库（2987 个）

本机 88 之外，还有 2987 个去重技能（46 仓库 / 精编 1316）在 `/var/minis/shared/skills-library/`：

```sh
skillctl search vmprotect    # 精编索引搜索（多词 AND）
skillctl cat dynamic         # 分类浏览：disasm malware exploit firmware mobile kernel
                             #   dynamic unpack rev-core forensics ctf fuzz symbolic
skillctl show <name>         # 打印全文
skillctl install <name>      # 装入本机 /var/minis/skills/
skillctl all <关键词>         # 全库 2987 搜索
skillctl stats               # 库统计
```

已知缺口（别浪费时间找）：VMProtect/Themida 去虚拟化无专项；Windows 内核驱动利用几乎空白。库内技能均过"注入/外传"安全扫描（0 命中），但仍守 §0.4 边界。

## 5. 人类可读入口 & 维护

- **单文件浏览器**：[browse.html](minis://skills/omni/browse.html)（液态玻璃风格，全部技能全文离线可查，支持搜索）
- **全文字典**：`catalog.md`（目录摘要）、`FULL-BUNDLE.md`（88 技能全文合集，可直接 grep）
- **机器索引**：`index.json` / `index.tsv`
- **新增技能后**：跑 `omni rebuild`（= `python3 /var/minis/skills/omni/build.py`）重新生成以上全部产物，并在 `_data.py` 里补一行归类。

<!--@GENTIME@-->
