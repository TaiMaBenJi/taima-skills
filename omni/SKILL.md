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

## 3. 全量索引（155 技能 · 分类 17 · 文本 3.6 MB · 生成于 2026-09-25 07:57）

### 🧭 总路由 · 元技能（3）

- `rev-library-router` — 逆向总路由 v2：本机 2075 技能索引 + 全量技能库检索法（skillctl.sh）
- `self-evolution` — 自我进化例程：卡点→解除限制、成功→沉淀工具；含 limits.md 限制台账
- `skill-creator` — 创建 / 更新技能的规范指南（SKILL.md 结构与写法）

### 🧱 环境基座（1）

- `rev-sandbox` ★ — 沙箱环境手册：Alpine aarch64+PRoot 下哪些工具能用、仿真层（xrun）、防卡死纪律——动手前必读

### 🔎 通用侦查 · 分诊（8）

- `bin-triage` ★ — 任意文件的第一步：格式识别 + 基础分诊（纯 stdlib，什么文件都能先过一遍）
- `elf-analyze` — ELF 静态分诊：架构 / 段 / 符号 / 加固特征（pyelftools）
- `ida-pro-skill` — Use this skill only when Codex needs to work with a currently running ID
- `macho-analyze` — Mach-O 静态分诊：macOS/iOS 可执行文件 / dylib / bundle
- `pe-analyze` — PE 静态分诊：Windows EXE/DLL 机器码 / 导入表 / 壳（pefile）
- `protection-survey` — 源码树扫描：反分析 / 保护模式特征普查（加固识别）
- `specialized-file-analyzer` — 特殊文件深析：.NET 及标准 PE 之外的分析路径
- `unpack` — 递归解包到不动点：zip/tar/gz/xz/7z/自解压/固件镜像层层剥

### ⚙️ 静态分析 · 反编译（65）

- `universal-reverse-engineering` ★ — 万能逆向：Android/原生/跨格式自动选工具链（拿不准就看它）
- `ai-agent-tool-abuse` — Abuse an LLM agent's tools/functions — coerce it to call tools with atta
- `ai-jailbreak` — Bypass an LLM's safety/guardrails to make it produce restricted output o
- `ai-mcp-security` — Assess Model Context Protocol (MCP) servers and agent tool integrations 
- `ai-prompt-injection` — Test LLM-backed apps for prompt injection (direct + indirect) and its co
- `api-auth-attacks` — Break API authentication: token handling, key leakage, weak session/JWT,
- `api-bola` — Broken Object/Function Level Authorization in REST/JSON APIs (the #1 API
- `api-testing-checklist` — A fast, ordered methodology for assessing an API end to end — REST/Graph
- `callgraph-tracer` — 调用图 / 执行路径 / 跨模块 xref 链追踪（DeepExtractIDA 库）
- `ctf-sandbox-orchestrator` — Default entrypoint and master ctf-sandbox-orchestrator workflow for CTF,
- `deepextract-agents` — DeepExtractRuntime 的深提取多智能体集（8 个角色：code-lifter / logic-scanner / memory-
- `dsl-vm-reverse` — Reverse JavaScript-based custom DSL/VM interpreters, non-standard WASM-l
- `dwarf-expert` — DWARF 调试信息解析（符号恢复 / 类型考古）
- `ghidra-decompile` — Ghidra headless 全自动反编译（一行命令出伪代码）
- `ghidra-rpc` — Ghidra RPC 深交互逆向助手：脚本化查符号 / xref / 反编译
- `native-decompile` — 原生二进制 → 类 C 伪代码（r2ghidra / r2 系）
- `native-disassemble` — PE/ELF/Mach-O → 面向函数的反汇编
- `native-lift` — 机器码区间 lift 到 LLVM IR（x86/amd64/aarch64）
- `practical-malware-analysis` — Defensive malware analysis and reverse-engineering workflow. Use for aut
- `privesc-arsenal` — One line: Linux + Windows local privilege-escalation tool arsenal for au
- `privesc-linux-gtfobins` — Linux privilege escalation via sudo rules, SUID/SGID binaries, and capab
- `privesc-windows-tokens` — Windows privilege escalation via token impersonation privileges — SeImpe
- `r2-recon` — radare2 跨格式静态侦察：函数 / 字符串 / xref 全景
- `recon-arsenal` — One line: port/host/service discovery tool arsenal for authorized engage
- `recon-js-analysis` — Mine JavaScript for endpoints, params, secrets, and hidden functionality
- `reconstruct-types` — 从 IDA 反编译输出重建 C/C++ 结构体 / 类定义
- `reporting — findings schema, panel export, report automation` — Turn engagement output (reports, evidence chains, case dirs) into machin
- `reporting-pentest-report` — Structure a professional penetration-test report (engagement deliverable
- `rev-idapython` — IDAPython / IDALib 脚本参考（批量自动化）
- `rev-struct` — 从内存访问模式重建数据结构
- `rev-symbol` — 从代码模式 / 字符串 / 常量恢复函数符号
- `reverse-skill-router` — Use the reverse-skill repository. The full package is installed locally 
- `SKILL: AI Pentest` — AI/LLM security offensive checklist: prompt injection, jailbreaking, mod
- `SKILL: Bug Identification` — Systematic bug identification methodology: source code review patterns, 
- `SKILL: Cross-Site Scripting (XSS)` — Cross-Site Scripting testing checklist: stored/reflected/DOM/blind XSS d
- `SKILL: Fast Testing Checklist` — Speed-optimized offensive checklist for rapid assessment: quick-win vuln
- `SKILL: File Upload Vulnerabilities` — File upload vulnerability checklist: MIME type bypass, extension bypass,
- `SKILL: HTTP Parameter Pollution (HPP)` — HTTP parameter pollution (HPP) checklist: duplicate parameter injection,
- `SKILL: HTTP Request Smuggling` — HTTP request smuggling checklist: CL.TE, TE.CL, TE.TE variants, detectio
- `SKILL: Insecure Direct Object References (IDOR)` — IDOR (Insecure Direct Object Reference) testing checklist: object ID enu
- `SKILL: Modern Initial Access` — Initial access techniques checklist: phishing (spear/smishing), credenti
- `SKILL: Novel research` — Low-level keylogger architecture design: kernel driver hooks (WH_KEYBOAR
- `SKILL: OAuth Security Testing` — OAuth 2.0 attack checklist: authorization code interception, redirect_ur
- `SKILL: Open Redirect Vulnerabilities` — Open redirect vulnerability checklist: parameter identification, bypass 
- `SKILL: OSINT Methodology` — Structured OSINT methodology framework: target definition, source select
- `SKILL: Race Conditions` — Race condition (TOCTOU) testing checklist: identifying timing windows, B
- `SKILL: Remote Code Execution` — Remote Code Execution testing checklist: OS command injection, SSTI-to-R
- `SKILL: Server-Side Request Forgery (SSRF)` — Server-Side Request Forgery testing checklist: SSRF discovery, blind SSR
- `SKILL: WAF Bypass Techniques` — WAF bypass techniques checklist: encoding bypass (URL/HTML/Unicode/doubl
- `SKILL: Week 2: Finding Vulnerabilities Through Fuzzing` — Week 2 of the exploit development curriculum. Covers fuzzing methodology
- `SKILL: Week 6: Understanding Windows Mitigations` — Deep-dive on Windows exploit mitigations: ASLR, DEP/NX, CFG, CET/Shadow 
- `SKILL: Week 7: Defeating Windows Security Boundaries` — Windows security boundary taxonomy and attack surface enumeration: kerne
- `SKILL: XML External Entity (XXE) Injection` — XML External Entity injection testing checklist: classic XXE, blind XXE 
- `web-arsenal` — One line: web enumeration + exploitation tool arsenal for authorized eng
- `web-auth-jwt` — Attack JWT/session authentication. Load when auth uses a JWT (three base
- `web-cache-poisoning` — Web cache poisoning & deception — get a shared cache to serve attacker c
- `web-command-injection` — Turn user input that reaches a shell into arbitrary OS command execution
- `web-csrf` — Cross-Site Request Forgery — force a victim's browser to perform state-c
- `web-deserialization` — Insecure deserialization → RCE via gadget chains. Load when the app dese
- `web-lfi-path-traversal` — Local File Inclusion / path traversal → read files, sometimes RCE. Load 
- `web-sqli` — Detect and exploit SQL injection (error-based, UNION, boolean/time blind
- `web-ssti` — Server-Side Template Injection → RCE. Load when user input is rendered b
- `web-testing-checklist` — A fast, ordered checklist for testing a web application end to end — so 
- `zhaoxuya-field-journal` — 逆向/安全实战日记合集（45 篇真实案例，含 Android/Go/DSL-VM/Electron/固件/APK 等方向的一手复盘笔记）。当遇到
- `🔄 DSL 自定义虚拟机逆向（DSL VM Reverse Engineering）` — 逆向基于 JavaScript 实现的自定义 WASM 虚拟机/风控引擎：识别特征、opcode 提取与分类、运行时捕获、状态码对照与自检清单。

### 🧩 字节码 · 脚本语言（5）

- `dotnet-decompile` — .NET 程序集反编译回 C#（ilspycmd）
- `js-deobfuscate` — JavaScript 混淆还原 / 解包（webcrack）
- `jvm-decompile` — Java / Android 字节码反编译（apk/dex/jar/class）
- `pojia-next` — 破甲一键通 v7.5 —— 把多套破甲工具合并为一个一键脚本（目标：DSH / WorkBuddy / ZCode；统一人格、备份/回滚、破甲自
- `pyc-decompile` — Python 字节码（.pyc）反编译回源码

### 🪝 Frida · 动态插桩（8）

- `frida-android-hooks` — Android Frida 钩子：Java.perform / 重载 / 构造器 / Kotlin / JNI / Gadget
- `frida-android-instrument` — 动态检查 Android Java 运行时（授权 App 的运行时透视）
- `frida-anti-instrumentation` — 反 Frida / 反调试 / root / 越狱检测的识别与绕过
- `frida-ios-hooks` — iOS Frida 钩子：Objective-C / Swift
- `frida-native-hooks` — 原生函数钩子：C/C++/ObjC 导出 / 导入 / 内存层
- `frida-tls-pinning` — TLS 证书绑定绕过（Android/iOS/Flutter，Frida 版）
- `frida-trace` — Frida 动态追踪：网络等关键行为一网打尽
- `rev-frida` — 现代 Frida API 钩子脚本生成（激活即产出可直接跑的 agent）

### 🐞 调试 · 仿真 · 追踪（6）

- `emulate-code` — 裸 code / shellcode 在虚拟 CPU 上仿真（x86/x64/ARM/ARM64）
- `gdb` — Debug and trace C/C++/Rust programs with the GNU Debugger (GDB) without 
- `js-reverse-ops` — Execute advanced JavaScript reverse-engineering workflows for modern web
- `qiling-emulate` — Qiling 全二进制仿真：PE/ELF/Mach-O 在沙箱里跑起来
- `rev-unicorn-debug` — Unicorn 针对代码片段 / 单函数的仿真调试
- `syscall-trace` — 系统调用追踪：strace / dtruss

### 🤖 Android 专项（7）

- `android-native-auto-reverse` ★ — 安卓逆向统一入口：APK/AAB/XAPK/DEX/JAR/AAR/ELF.so 全流程
- `android-reverse-engineering` — jadx / Fernflower 反编译 APK / XAPK / JAR / AAR
- `android-static-analysis` — APK 静态分析：反编译 / Manifest / 代码审计
- `bangcle-unpack` — 梆梆企业加固脱壳专技：classes0.jar 直接解密 + Frida 内存 dump 双路线
- `dex-dump` — 运行中 App 内存 DEX / CompactDex dump（脱壳）
- `dsh-apk-reverse` — CLI 环境 APK 逆向：解包 / 反编译 / smali 改 / 重打包 / Frida
- `rev-dex-dumper` — DEX dump 脱壳 / 解混淆流程

### 🍎 iOS 专项（1）

- `ios-reverse-engineering` — iOS 逆向：IPA / .app / Mach-O / dylib / 框架提取分析

### 📱 移动安全评估（4）

- `mobile-cert-pinning-bypass` ★ — 证书绑定绕过总法：抓包被挡先读它（SSL handshake 失败信号）
- `mobile-security-suite` — 移动安全评估套件：12 维度 / MASVS 检查表 / 威胁建模
- `renef` — Use when operating renef / renef.io to instrument Android ARM64 apps: ho
- `spider-king` — Pure-web protocol reverse skill: turn hostile browser clients into brows

### 🦠 恶意代码 · 检测规则（5）

- `malware-triage` ★ — 恶意样本快速静态分诊 / 分级 / 优先级（样本到手第一步）
- `malware-dynamic-analysis` — 隔离 VM 行为分析（执行后的动态侧）
- `open-static-malware-analysis` — Static malware analysis skill for examining suspicious files without exe
- `yara-rule-authoring` — YARA-X 高质量检测规则编写（含测试方法）
- `yara-scan` — YARA 扫描文件 / 目录（classic + YARA-X）

### ⚔️ 漏洞利用 · 红队（25）

- `adscan-ad-agents` — Active Directory 攻击多智能体定义集（3 个角色：攻击规划 / 枚举 / 利用操作）。配合 ADScan 工作流或独立用于红队 
- `aflpp` — AFL++ 多核 Fuzzing：C/C++ 项目插桩 / 跑起来 / 出 crash
- `ctf-sandbox` — Thin PRIMARY for CTF / AWD / 靶场 multi-type orchestration. Hands off to t
- `dsh-edr-bypass` — 先逆向 EDR/AV 实现 → 再写针对性绕过（unhook/间接 syscall/ETW patch）
- `exploit-chaining` — Combine low/medium findings into one high-impact exploit chain, and ampl
- `exploit-memory-corruption` — Turn a memory-corruption bug in a native binary into code execution — st
- `exploit-poc-development` — Turn a known/1-day vulnerability or a raw bug into a working, reliable P
- `identifying-anti-debugging-techniques` — 恶意软件反调试 / 反分析检测识别与绕过
- `offensive-active-directory` — 内网 Active Directory 攻击方法论（红队内网）
- `offensive-anti-forensics` — 反取证 / 痕迹销毁（红队行动侧）
- `offensive-c2-frameworks` — C2 框架部署 / 配置 / 运营（红队基础设施）
- `offensive-edr-evasion` — EDR 绕过清单：unhooking / 直接 syscall / AMSI / ETW / 注入变体
- `offensive-exploit-development` — 漏洞利用开发：环境 / pwntools / pwndbg / 堆利用 / 可靠性
- `offensive-shellcode` — Shellcode 开发参考（编码器 / 加载器 / 限制绕行）
- `payloads-file-transfers` — Move files on/off a target when there's no shared drive — upload tools (
- `payloads-reverse-shells` — Get a reliable reverse (or bind) shell and upgrade it to a real interact
- `payloads-waf-bypass` — Bypass WAFs/filters blocking your payloads. Load when a payload that sho
- `payloads-xss-polyglots` — Context-breaking XSS polyglots and per-context payloads that fire across
- `pwn-chain` — 从逆向到可用利用（Working Exploit）的全链路工程化方法
- `shellcode-stub` — 裸 shellcode → 可运行 native PoC 的包装器
- `SKILL: Exploit Development` — Full exploit development course roadmap and syllabus: weekly topics, rec
- `SKILL: Modern Kernel Exploit Mitigations` — Security mitigation reference and bypass catalog: ASLR, DEP/NX, RELRO, s
- `SKILL: Week 1: Vulnerability Classes with Real-World Examples` — Exploit development curriculum covering core vulnerability classes with 
- `SKILL: Week 4: Crash Analysis and Exploitability Assessment` — Week 4 exploit development curriculum. Crash triage and analysis methodo
- `SKILL: Week 5: Basic Exploitation (Linux with Mitigations Disabled)` — Week 5 exploit development curriculum. Foundational exploitation techniq

### 🚩 CTF 竞赛（5）

- `ctf-forensics` — CTF 数字取证与信号分析
- `ctf-malware` — CTF 恶意代码与网络流量分析
- `ctf-pwn` — CTF 二进制利用：溢出 / 格式化 / 堆 / ROP / 内核 / 沙箱逃逸
- `ctf-reverse` — CTF 逆向解题技术
- `xiaoliu-pojia` — 小liu破甲 v2 —— 针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破甲提示词与一键部署工具（deploy.py

### 🌐 Web · 协议（1）

- `sci-skill` — A beginner-friendly, stage-gated research and SCI paper collaboration sk

### 🔌 固件 · IoT（2）

- `firmware-bringup` — 固件 bring-up：从黑盒二进制到可执行仿真（ripcord）
- `firmware-pentest` — 固件 / IoT 渗透链：逆向→提取→模拟→利用（OWASP 方法论）

### 🔀 差分 · 变体分析（4）

- `bindiff` — Google BinDiff 函数匹配（跨版本对比）
- `diaphora-diff` — Diaphora 函数匹配 / 伪代码恢复（开源的 BinDiff 替代）
- `intellidiff` — 精确 / 规范化文件对比、二进制 diff
- `variant-analysis` — 变体猎杀：已找到一个漏洞后，找它的所有同类

### 🎮 游戏逆向（1）

- `reverse-skill` — 逆向/渗透/安全任务总路由包——zhaoxuya520/reverse-skill 完整仓库已装于本机 /var/minis/skills/re

### 🆕 其他（4）

- `dsh` — dsh 破限者 —— 为 DeepSeek Harness（dsh）打造的「解除限制执行器」技能包，适配 deepseek-v4-flash（7
- `dsh-pojia-mode` — DSH（DeepSeek Harness）「破甲模式」安装器 v1.0（Windows / PowerShell）：双击即装、不改 DSH 代码
- `kimi-break` — kimi-break —— 针对 Kimi Code CLI Agent 的红队系统提示词（SYSTEM.md，完整 drop-in 替换版，人
- `minis-400-guard` — Minis 会话 400 错误的预防、检测与自愈（两类：A=tool_calls 粘死 / B=上下文超限）。当用户或会话提到「400」「too


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

<!-- 本文件由 build.py 自动生成 / 更新时间 2026-09-25 07:57 -->
