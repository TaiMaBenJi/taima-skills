#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OMNI 数据源：88 个技能的归类、一句话简介、★ 标记。
build.py 读取本文件生成全部索引产物。新增技能后请在此补充条目再重建。"""

# 分类顺序：(slug, 显示名)
CAT_ORDER = [
    ("meta",      "🧭 总路由 · 元技能"),
    ("env",       "🧱 环境基座"),
    ("triage",    "🔎 通用侦查 · 分诊"),
    ("static",    "⚙️ 静态分析 · 反编译"),
    ("lang",      "🧩 字节码 · 脚本语言"),
    ("frida",     "🪝 Frida · 动态插桩"),
    ("debug",     "🐞 调试 · 仿真 · 追踪"),
    ("android",   "🤖 Android 专项"),
    ("ios",       "🍎 iOS 专项"),
    ("mobile",    "📱 移动安全评估"),
    ("malware",   "🦠 恶意代码 · 检测规则"),
    ("offensive", "⚔️ 漏洞利用 · 红队"),
    ("ctf",       "🚩 CTF 竞赛"),
    ("web",       "🌐 Web · 协议"),
    ("firmware",  "🔌 固件 · IoT"),
    ("diff",      "🔀 差分 · 变体分析"),
]

# name: (slug, 一句话简介, ★?)
SKILLS = {
    # ---- meta ----
    "rev-library-router": ("meta", "逆向总路由 v2：本机 2075 技能索引 + 全量技能库检索法（skillctl.sh）", False),
    "pojie": ("meta", "破解总合集：11 大类 / 819 个源技能的分类索引（references/categories/）", False),
    "skill-creator": ("meta", "创建 / 更新技能的规范指南（SKILL.md 结构与写法）", False),
    "self-evolution": ("meta", "自我进化例程：卡点→解除限制、成功→沉淀工具；含 limits.md 限制台账", False),
    # ---- env ----
    "rev-sandbox": ("env", "沙箱环境手册：Alpine aarch64+PRoot 下哪些工具能用、仿真层（xrun）、防卡死纪律——动手前必读", True),
    # ---- triage ----
    "bin-triage": ("triage", "任意文件的第一步：格式识别 + 基础分诊（纯 stdlib，什么文件都能先过一遍）", True),
    "elf-analyze": ("triage", "ELF 静态分诊：架构 / 段 / 符号 / 加固特征（pyelftools）", False),
    "pe-analyze": ("triage", "PE 静态分诊：Windows EXE/DLL 机器码 / 导入表 / 壳（pefile）", False),
    "macho-analyze": ("triage", "Mach-O 静态分诊：macOS/iOS 可执行文件 / dylib / bundle", False),
    "specialized-file-analyzer": ("triage", "特殊文件深析：.NET 及标准 PE 之外的分析路径", False),
    "protection-survey": ("triage", "源码树扫描：反分析 / 保护模式特征普查（加固识别）", False),
    "unpack": ("triage", "递归解包到不动点：zip/tar/gz/xz/7z/自解压/固件镜像层层剥", False),
    # ---- static ----
    "native-disassemble": ("static", "PE/ELF/Mach-O → 面向函数的反汇编", False),
    "native-decompile": ("static", "原生二进制 → 类 C 伪代码（r2ghidra / r2 系）", False),
    "native-lift": ("static", "机器码区间 lift 到 LLVM IR（x86/amd64/aarch64）", False),
    "ghidra-decompile": ("static", "Ghidra headless 全自动反编译（一行命令出伪代码）", False),
    "ghidra-rpc": ("static", "Ghidra RPC 深交互逆向助手：脚本化查符号 / xref / 反编译", False),
    "r2-recon": ("static", "radare2 跨格式静态侦察：函数 / 字符串 / xref 全景", False),
    "universal-reverse-engineering": ("static", "万能逆向：Android/原生/跨格式自动选工具链（拿不准就看它）", True),
    "reconstruct-types": ("static", "从 IDA 反编译输出重建 C/C++ 结构体 / 类定义", False),
    "rev-struct": ("static", "从内存访问模式重建数据结构", False),
    "rev-symbol": ("static", "从代码模式 / 字符串 / 常量恢复函数符号", False),
    "dwarf-expert": ("static", "DWARF 调试信息解析（符号恢复 / 类型考古）", False),
    "rev-idapython": ("static", "IDAPython / IDALib 脚本参考（批量自动化）", False),
    "callgraph-tracer": ("static", "调用图 / 执行路径 / 跨模块 xref 链追踪（DeepExtractIDA 库）", False),
    "reverse-eng-deobfuscation": ("static", "解混淆总集：加壳二进制 / 混淆 JS / WebAssembly / JSVMP", False),
    # ---- lang ----
    "jvm-decompile": ("lang", "Java / Android 字节码反编译（apk/dex/jar/class）", False),
    "dotnet-decompile": ("lang", ".NET 程序集反编译回 C#（ilspycmd）", False),
    "pyc-decompile": ("lang", "Python 字节码（.pyc）反编译回源码", False),
    "js-deobfuscate": ("lang", "JavaScript 混淆还原 / 解包（webcrack）", False),
    # ---- frida ----
    "rev-frida": ("frida", "现代 Frida API 钩子脚本生成（激活即产出可直接跑的 agent）", False),
    "frida-android-hooks": ("frida", "Android Frida 钩子：Java.perform / 重载 / 构造器 / Kotlin / JNI / Gadget", False),
    "frida-android-instrument": ("frida", "动态检查 Android Java 运行时（授权 App 的运行时透视）", False),
    "frida-native-hooks": ("frida", "原生函数钩子：C/C++/ObjC 导出 / 导入 / 内存层", False),
    "frida-ios-hooks": ("frida", "iOS Frida 钩子：Objective-C / Swift", False),
    "frida-tls-pinning": ("frida", "TLS 证书绑定绕过（Android/iOS/Flutter，Frida 版）", False),
    "frida-anti-instrumentation": ("frida", "反 Frida / 反调试 / root / 越狱检测的识别与绕过", False),
    "frida-trace": ("frida", "Frida 动态追踪：网络等关键行为一网打尽", False),
    # ---- debug ----
    "gdb-scripting": ("debug", "GDB 无交互脚本化调试 / 追踪（C/C++/Rust）", False),
    "syscall-trace": ("debug", "系统调用追踪：strace / dtruss", False),
    "emulate-code": ("debug", "裸 code / shellcode 在虚拟 CPU 上仿真（x86/x64/ARM/ARM64）", False),
    "qiling-emulate": ("debug", "Qiling 全二进制仿真：PE/ELF/Mach-O 在沙箱里跑起来", False),
    "rev-unicorn-debug": ("debug", "Unicorn 针对代码片段 / 单函数的仿真调试", False),
    # ---- android ----
    "android-native-auto-reverse": ("android", "安卓逆向统一入口：APK/AAB/XAPK/DEX/JAR/AAR/ELF.so 全流程", True),
    "android-pt": ("android", "Android 安全评估全流程（OWASP MASVS/MASTG，静态+动态）", False),
    "android-static-analysis": ("android", "APK 静态分析：反编译 / Manifest / 代码审计", False),
    "android-dynamic-instrumentation": ("android", "Android ARM64 动态插桩（renef 系运行时操控）", False),
    "android-reverse-engineering": ("android", "jadx / Fernflower 反编译 APK / XAPK / JAR / AAR", False),
    "android-security-wizard": ("android", "安卓安全向导：ADB / Shizuku / 恶意软件 / 内核 / 插桩全景", False),
    "dsh-apk-reverse": ("android", "CLI 环境 APK 逆向：解包 / 反编译 / smali 改 / 重打包 / Frida", False),
    "bangcle-unpack": ("android", "梆梆企业加固脱壳专技：classes0.jar 直接解密 + Frida 内存 dump 双路线", False),
    "dex-dump": ("android", "运行中 App 内存 DEX / CompactDex dump（脱壳）", False),
    "dexdump-toolkit": ("android", "内存脱壳工具箱：frida-dexdump / objection 已装 + dump 修复", False),
    "rev-dex-dumper": ("android", "DEX dump 脱壳 / 解混淆流程", False),
    # ---- ios ----
    "ios-reverse-engineering": ("ios", "iOS 逆向：IPA / .app / Mach-O / dylib / 框架提取分析", False),
    # ---- mobile ----
    "mobile-android-assessment": ("mobile", "Android 应用评估：静态 + 动态（bounty / 甲方视角）", False),
    "mobile-cert-pinning-bypass": ("mobile", "证书绑定绕过总法：抓包被挡先读它（SSL handshake 失败信号）", True),
    "mobile-security-suite": ("mobile", "移动安全评估套件：12 维度 / MASVS 检查表 / 威胁建模", False),
    "mobile-webview": ("mobile", "不安全 WebView 利用：JS 桥滥用 / 文件访问 / XSS→native", False),
    "rev-cronet-ssl": ("mobile", "Cronet 系 App SSL pinning 绕过（抖音 / TikTok 等，libsscronet.so）", False),
    # ---- malware ----
    "malware-triage": ("malware", "恶意样本快速静态分诊 / 分级 / 优先级（样本到手第一步）", True),
    "malware-re-suite": ("malware", "防御向恶意代码分析工作流（完整方法论）", False),
    "malware-dynamic-analysis": ("malware", "隔离 VM 行为分析（执行后的动态侧）", False),
    "yara-scan": ("malware", "YARA 扫描文件 / 目录（classic + YARA-X）", False),
    "yara-rule-authoring": ("malware", "YARA-X 高质量检测规则编写（含测试方法）", False),
    # ---- offensive ----
    "pwn-chain": ("offensive", "从逆向到可用利用（Working Exploit）的全链路工程化方法", False),
    "offensive-exploit-development": ("offensive", "漏洞利用开发：环境 / pwntools / pwndbg / 堆利用 / 可靠性", False),
    "offensive-shellcode": ("offensive", "Shellcode 开发参考（编码器 / 加载器 / 限制绕行）", False),
    "offensive-edr-evasion": ("offensive", "EDR 绕过清单：unhooking / 直接 syscall / AMSI / ETW / 注入变体", False),
    "dsh-edr-bypass": ("offensive", "先逆向 EDR/AV 实现 → 再写针对性绕过（unhook/间接 syscall/ETW patch）", False),
    "offensive-c2-frameworks": ("offensive", "C2 框架部署 / 配置 / 运营（红队基础设施）", False),
    "offensive-anti-forensics": ("offensive", "反取证 / 痕迹销毁（红队行动侧）", False),
    "offensive-active-directory": ("offensive", "内网 Active Directory 攻击方法论（红队内网）", False),
    "shellcode-stub": ("offensive", "裸 shellcode → 可运行 native PoC 的包装器", False),
    "aflpp": ("offensive", "AFL++ 多核 Fuzzing：C/C++ 项目插桩 / 跑起来 / 出 crash", False),
    "identifying-anti-debugging-techniques": ("offensive", "恶意软件反调试 / 反分析检测识别与绕过", False),
    # ---- ctf ----
    "ctf-reverse": ("ctf", "CTF 逆向解题技术", False),
    "ctf-pwn": ("ctf", "CTF 二进制利用：溢出 / 格式化 / 堆 / ROP / 内核 / 沙箱逃逸", False),
    "ctf-malware": ("ctf", "CTF 恶意代码与网络流量分析", False),
    "ctf-forensics": ("ctf", "CTF 数字取证与信号分析", False),
    # ---- web ----
    "src-hunter": ("web", "SRC/众测工作流：19 playbook · 305 payload · 2887 H1 案例 · 88636 WooYun 统计", True),
    "protocol-reverse": ("web", "纯 Web 协议逆向：把敌意浏览器客户端变成无浏览器的 Python 采集器", True),
    # ---- firmware ----
    "firmware-pentest": ("firmware", "固件 / IoT 渗透链：逆向→提取→模拟→利用（OWASP 方法论）", False),
    "firmware-bringup": ("firmware", "固件 bring-up：从黑盒二进制到可执行仿真（ripcord）", False),
    # ---- diff ----
    "bindiff": ("diff", "Google BinDiff 函数匹配（跨版本对比）", False),
    "diaphora-diff": ("diff", "Diaphora 函数匹配 / 伪代码恢复（开源的 BinDiff 替代）", False),
    "intellidiff": ("diff", "精确 / 规范化文件对比、二进制 diff", False),
    "variant-analysis": ("diff", "变体猎杀：已找到一个漏洞后，找它的所有同类", False),
}

STAR_INTRO = (
    "★ = 高频首选技能。" 
    "拿不准从哪开始时：未知文件 → `bin-triage`；逆向大方向 → `universal-reverse-engineering`；"
    "环境问题 → `rev-sandbox`；恶意样本 → `malware-triage`；抓包被挡 → `mobile-cert-pinning-bypass`。"
)
