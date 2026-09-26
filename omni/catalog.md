# OMNI 技能目录 · catalog

> 155 技能 · 分类 17 · 文本 3.6 MB · 生成于 2026-09-25 07:57

本文件由 `build.py` 自动生成。全文合集见 `FULL-BUNDLE.md`，在线浏览见 `browse.html`。

## 🧭 总路由 · 元技能（3）

### `rev-library-router`
- **路径**：`/var/minis/skills/rev-library-router/SKILL.md`（7.0 KB）
- **一句话**：逆向总路由 v2：本机 2075 技能索引 + 全量技能库检索法（skillctl.sh）
- **描述**：逆向/安全技能总路由 v3（全量版）。任务涉及逆向工程、二进制/固件/移动端分析、脱壳、恶意代码分析、漏洞挖掘与利用、CTF、Fuzzing、符号执行、协议逆向、EDR绕过、游戏逆向、CAN总线等主题时先激活本技能。本机已装 2084 个技能（omni 总索引），全量库 102 仓库 / 3386 条目（其中逆向精编 2483 条）。入口：`omni`（全机技能总控）、`skillctl`（全量库检索）。

### `self-evolution`
- **路径**：`/var/minis/skills/self-evolution/SKILL.md`（8.4 KB）
- **一句话**：自我进化例程：卡点→解除限制、成功→沉淀工具；含 limits.md 限制台账
- **描述**：自我进化例程——把每次卡点变成已解除的限制、把每次成功沉淀成可复用工具。当用户提到「自我训练/进化/复盘/限制」或定期自省任务运行时使用。

### `skill-creator`
- **路径**：`/var/minis/skills/skill-creator/SKILL.md`（3.8 KB）
- **一句话**：创建 / 更新技能的规范指南（SKILL.md 结构与写法）
- **描述**：Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.

## 🧱 环境基座（1）

### `rev-sandbox` ★
- **路径**：`/var/minis/skills/rev-sandbox/SKILL.md`（17.4 KB）
- **一句话**：沙箱环境手册：Alpine aarch64+PRoot 下哪些工具能用、仿真层（xrun）、防卡死纪律——动手前必读
- **描述**：Minis 沙箱逆向环境手册。动手做二进制/固件/移动端/恶意代码分析前先读这个：本沙箱是 Alpine aarch64 + PRoot，哪些工具能用、哪些要跨架构仿真、哪些坑必须绕（TMPDIR、JDK21 JIT 被禁、PRoot 高并发 make 会挂）。含 x86/x64/ARM32/RISC-V 仿真层用法（xrun/xstrace/xpython）、原生 Ghidra headless、r2/llvm/capstone/keystone/pwntools/unicorn 全链路命令模板。

## 🔎 通用侦查 · 分诊（8）

### `bin-triage` ★
- **路径**：`/var/minis/skills/bin-triage/SKILL.md`（2.2 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：任意文件的第一步：格式识别 + 基础分诊（纯 stdlib，什么文件都能先过一遍）
- **描述**：Fast format-agnostic first look at any file, pure-stdlib: identify format from magic bytes (and route to the right analyzer), chunked Shannon entropy (packed/encrypted regions), string extraction with interesting-string surfacing (URLs/IPs/onion/shell/paths/exec-APIs), and an embedded-signature scan (mini-binwalk: ZIP/gzip/ELF/PDF at non-zero offsets). When given an output dir, also CARVES large embedded readable-source regions (the JS/text a single-file executable — Bun/Deno/pkg/nexe/SEA — appends after its native runtime) for rescanning. Emits BINARY.* atoms. Read-only — never executes the input.

### `elf-analyze`
- **路径**：`/var/minis/skills/elf-analyze/SKILL.md`（2.0 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：ELF 静态分诊：架构 / 段 / 符号 / 加固特征（pyelftools）
- **描述**：Static triage of ELF binaries (Linux/BSD) with pyelftools: class/arch/type, sections + per-section entropy (packing), needed libraries, RPATH/RUNPATH, imported symbols classified by capability (network/exec/inject/load/crypto), and hardening (PIE/NX/RELRO). Emits BINARY.* atoms. Reads structure only — never runs the binary.

### `ida-pro-skill`
- **路径**：`/var/minis/skills/ida-pro-skill/SKILL.md`（4.6 KB）
- **资源**：目录 ida_pro_skill / references / scripts
- **一句话**：Use this skill only when Codex needs to work with a currently running ID
- **描述**：Use this skill only when Codex needs to work with a currently running IDA Pro database through the local ida-pro-skill CLI and installed IDA HTTP bridge. Trigger it for live IDA tasks such as: discovering or selecting IDA instances; reading metadata, cursor or selection, segments, entrypoints, functions, callers/callees, xrefs, imports, strings, globals, structs, or types; decompiling or disassembling code from the open IDB; exporting bounded AI context packs from IDA; applying deliberate IDB edits such as rename/comment/patch/define-function; or running explicit IDAPython with py-eval or py-file. Do not use it for generic reverse-engineering advice that does not require a live IDA session. This skill explicitly covers WSL-to-Windows IDA bridge workflows.

### `macho-analyze`
- **路径**：`/var/minis/skills/macho-analyze/SKILL.md`（1.9 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Mach-O 静态分诊：macOS/iOS 可执行文件 / dylib / bundle
- **描述**：Static triage of Mach-O binaries (macOS/iOS executables, dylibs, bundles, kexts) with macholib: arch/fat slices, file type, PIE, linked dylibs, RPATH, code-signature presence, and encryption (LC_ENCRYPTION_INFO). Emits BINARY.* atoms. Reads structure only — never runs the binary.

### `pe-analyze`
- **路径**：`/var/minis/skills/pe-analyze/SKILL.md`（2.0 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：PE 静态分诊：Windows EXE/DLL 机器码 / 导入表 / 壳（pefile）
- **描述**：Static triage of Windows PE binaries (EXE/DLL) with pefile: machine/arch, subsystem, entry/imagebase, sections + per-section entropy (packing) and RWX flags, imports classified by capability (inject/exec/network/anti-debug/persist/crypto), exports, TLS callbacks, overlay, and Authenticode presence. Emits BINARY.* atoms. Reads structure only — never runs the binary.

### `protection-survey`
- **路径**：`/var/minis/skills/protection-survey/SKILL.md`（2.1 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：源码树扫描：反分析 / 保护模式特征普查（加固识别）
- **描述**：Statically survey source trees for anti-analysis and protection patterns across C/C++, Objective-C, assembly, Rust, Go, Python, JavaScript/TypeScript, Java/Kotlin, C#, and Swift. Finds anti-debug/VM checks, runtime API resolution, executable-memory changes, early execution, custom sections, inline assembly, opaque/flattened control flow, stack strings, obfuscating build flags, injection primitives, and self-integrity checks. Emits evidence with confidence; read-only and never executes source.

### `specialized-file-analyzer`
- **路径**：`/var/minis/skills/specialized-file-analyzer/SKILL.md`（41.4 KB）
- **资源**：文件 SOURCE.md
- **一句话**：特殊文件深析：.NET 及标准 PE 之外的分析路径
- **描述**：Analyze specialized file types beyond standard PE executables - .NET assemblies, Office macros, PDFs, PowerShell scripts, JavaScript, archives, HTA files, disk images (ISO/IMG/VHD/VHDX), and Linux ELF binaries. Use when you encounter documents, scripts, disk images, or non-Windows executables that require format-specific analysis tools and techniques. Claude runs the extraction and deobfuscation tooling on the host itself; nothing is executed.

### `unpack`
- **路径**：`/var/minis/skills/unpack/SKILL.md`（2.3 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：递归解包到不动点：zip/tar/gz/xz/7z/自解压/固件镜像层层剥
- **描述**：Recursively extract archives to a fixpoint: zip / tar(.gz/.bz2/.xz) / gz / bz2 / xz / asar (Electron) / ar / .deb with the pure-stdlib core, 7z and RAR via an external CLI (7z/7za/7zz, unar) when present. Walks the output for nested archives and extracts those too. Guards against zip-slip (path traversal) and decompression bombs (byte budget). Extraction is not execution — contents are written, never run.

## ⚙️ 静态分析 · 反编译（65）

### `universal-reverse-engineering` ★
- **路径**：`/var/minis/skills/universal-reverse-engineering/SKILL.md`（10.9 KB）
- **资源**：目录 references / scripts；文件 SOURCE.md
- **一句话**：万能逆向：Android/原生/跨格式自动选工具链（拿不准就看它）
- **描述**：Universal reverse engineering skill for Android (APK/XAPK/JAR/AAR), iOS (IPA/dylib), Windows (PE/EXE/DLL/SYS), Linux (ELF/SO), macOS (Mach-O/dylib/framework), and .NET assemblies. Auto-detects the target format, selects the right toolchain, and produces structured analysis: architecture, strings, imports/exports, disassembly, decompiled source, and call-flow documentation. Also detects 40+ vulnerability classes in both source code and compiled binaries.

### `ai-agent-tool-abuse`
- **路径**：`/var/minis/skills/ai-agent-tool-abuse/SKILL.md`（2.6 KB）
- **一句话**：Abuse an LLM agent's tools/functions — coerce it to call tools with atta
- **描述**：Abuse an LLM agent's tools/functions — coerce it to call tools with attacker-chosen args for SSRF, RCE, data exfil, or privilege abuse. Load when the target is an agent with tools/ function-calling/plugins, MCP servers, code interpreters, or "the assistant can do X". Signals: function-calling, tool schemas, browse/email/query/exec tools, autonomous agents.

### `ai-jailbreak`
- **路径**：`/var/minis/skills/ai-jailbreak/SKILL.md`（2.4 KB）
- **一句话**：Bypass an LLM's safety/guardrails to make it produce restricted output o
- **描述**：Bypass an LLM's safety/guardrails to make it produce restricted output or ignore its policy. Load when testing an AI product's content controls, "jailbreak", "guardrail bypass", refusal testing, or safety evals. Signals: a chatbot/assistant with a usage policy, refusals to test, content filters.

### `ai-mcp-security`
- **路径**：`/var/minis/skills/ai-mcp-security/SKILL.md`（2.9 KB）
- **一句话**：Assess Model Context Protocol (MCP) servers and agent tool integrations 
- **描述**：Assess Model Context Protocol (MCP) servers and agent tool integrations — tool poisoning, prompt injection via tool descriptions/results, over-broad scopes, and unauth tool exposure. Load when the target uses MCP servers, agent tool/function integrations, or connectors. Signals: mcp.json, MCP server, tool schemas, connector marketplace, agent with external tools.

### `ai-prompt-injection`
- **路径**：`/var/minis/skills/ai-prompt-injection/SKILL.md`（2.8 KB）
- **一句话**：Test LLM-backed apps for prompt injection (direct + indirect) and its co
- **描述**：Test LLM-backed apps for prompt injection (direct + indirect) and its consequences: data exfil, tool/function abuse, guardrail bypass. Load when the target is a chatbot/assistant/ agent, summarizes untrusted content, has tools/functions, or does RAG. Signals: "ask AI", system prompts, function-calling, "summarize this URL/file", agentic actions.

### `api-auth-attacks`
- **路径**：`/var/minis/skills/api-auth-attacks/SKILL.md`（2.2 KB）
- **一句话**：Break API authentication: token handling, key leakage, weak session/JWT,
- **描述**：Break API authentication: token handling, key leakage, weak session/JWT, and no-auth endpoints. Load on REST/GraphQL APIs using API keys, Bearer tokens, HMAC signing, or basic auth. Signals: `Authorization` headers, api_key params, tokens in URLs, /v1 vs /v2 auth drift.

### `api-bola`
- **路径**：`/var/minis/skills/api-bola/SKILL.md`（2.3 KB）
- **一句话**：Broken Object/Function Level Authorization in REST/JSON APIs (the #1 API
- **描述**：Broken Object/Function Level Authorization in REST/JSON APIs (the #1 API risk). Load on any REST API with object ids in paths/bodies (/api/v1/users/123, /orders/{id}), Bearer auth, mobile-app backends, or admin vs user function separation. Signals: predictable ids, verbs that skip re-authorization, "role" enforced only in the UI.

### `api-testing-checklist`
- **路径**：`/var/minis/skills/api-testing-checklist/SKILL.md`（3.7 KB）
- **一句话**：A fast, ordered methodology for assessing an API end to end — REST/Graph
- **描述**：A fast, ordered methodology for assessing an API end to end — REST/GraphQL/gRPC/SOAP — so nothing gets skipped. Load when the target is an API (or recon found one), on "test this API", "checklist", methodology triage, or to confirm coverage before reporting. Signals: /api, swagger/openapi.json, GraphQL /graphql, gRPC, JSON/XML endpoints, a mobile/SPA backend.

### `callgraph-tracer`
- **路径**：`/var/minis/skills/callgraph-tracer/SKILL.md`（16.6 KB）
- **资源**：目录 scripts；文件 README.md / SOURCE.md / reference.md
- **一句话**：调用图 / 执行路径 / 跨模块 xref 链追踪（DeepExtractIDA 库）
- **描述**：Trace call graphs, execution paths, and cross-module xref chains across DeepExtractIDA analysis databases. Use when the user asks to trace a function's call chain, find paths between functions, understand cross-module dependencies, show what a function calls across DLL boundaries, generate call graph diagrams, find reachable functions from an entry point, identify recursive call clusters, or asks about execution flow across extracted modules.

### `ctf-sandbox-orchestrator`
- **路径**：`/var/minis/skills/ctf-sandbox-orchestrator/SKILL.md`（7.2 KB）
- **资源**：目录 agents / references
- **一句话**：Default entrypoint and master ctf-sandbox-orchestrator workflow for CTF,
- **描述**：Default entrypoint and master ctf-sandbox-orchestrator workflow for CTF, exploit, reverse engineering, DFIR, pwnable, crypto, stego, mobile, AI-agent, cloud, container, Active Directory, Windows-host, and identity challenges. Use first when the user presents challenge infrastructure, binaries, prompts, hosts, or identities that should be treated as sandbox-internal by default and Codex needs to choose, route, and load the right downstream analysis path with concise evidence.

### `deepextract-agents`
- **路径**：`/var/minis/skills/deepextract-agents/SKILL.md`（961 B）
- **资源**：目录 agents
- **一句话**：DeepExtractRuntime 的深提取多智能体集（8 个角色：code-lifter / logic-scanner / memory-
- **描述**：DeepExtractRuntime 的深提取多智能体集（8 个角色：code-lifter / logic-scanner / memory-corruption-scanner / re-analyst / security-auditor / taint-scanner / triage-coordinator / type-reconstructor）。用于跨二进制/字节码深度提取、污点分析与类型重建的编排。Use for orchestrating deep extraction pipelines over binaries and bytecode with specialized agent roles.

### `dsl-vm-reverse`
- **路径**：`/var/minis/skills/dsl-vm-reverse/SKILL.md`（11.5 KB）
- **一句话**：Reverse JavaScript-based custom DSL/VM interpreters, non-standard WASM-l
- **描述**：Reverse JavaScript-based custom DSL/VM interpreters, non-standard WASM-like runtimes, and risk-control engines. Use when analyzing IIFE or switch-based opcode dispatchers, extracting instruction tables, recovering bytecode semantics, capturing VM state at runtime, or reconstructing execution flow.

### `dwarf-expert`
- **路径**：`/var/minis/skills/dwarf-expert/SKILL.md`（5.9 KB）
- **资源**：目录 agents / assets；文件 SOURCE.md
- **一句话**：DWARF 调试信息解析（符号恢复 / 类型考古）
- **描述**：Analyzes DWARF debug information in compiled binaries. Use when inspecting .debug_* sections, DIE trees, or DW_TAG_/DW_AT_ entries with dwarfdump/llvm-dwarfdump or readelf, verifying debug info with llvm-dwarfdump --verify, answering DWARF standard questions, or writing code that parses DWARF (libdwarf, pyelftools, gimli).

### `ghidra-decompile`
- **路径**：`/var/minis/skills/ghidra-decompile/SKILL.md`（1.8 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Ghidra headless 全自动反编译（一行命令出伪代码）
- **描述**：Decompile a native binary (ELF/PE/Mach-O) with full Ghidra headless analysis — higher fidelity than native-decompile (rizin pdg) for hard targets. Runs analyzeHeadless with a bundled Ghidra script that decompiles every function to one C file. Static: analyses + decompiles, never runs the binary. Prereq-gated on Ghidra's analyzeHeadless (needs a JRE 17+).

### `ghidra-rpc`
- **路径**：`/var/minis/skills/ghidra-rpc/SKILL.md`（37.9 KB）
- **资源**：目录 .github / .pi / docs / ghidra_rpc / tests；文件 .gitignore / AGENTS.md / CHANGELOG.md / CLAUDE.md / README.md / SOURCE.md / package.json / pyproject.toml
- **一句话**：Ghidra RPC 深交互逆向助手：脚本化查符号 / xref / 反编译
- **描述**：Reverse engineering assistant powered by Ghidra. Use for binary analysis, decompilation, vulnerability research, auditing compiled code, renaming symbols, annotating disassembly, cross-references, or any RE task - even without explicit mention of Ghidra.

### `native-decompile`
- **路径**：`/var/minis/skills/native-decompile/SKILL.md`（1.4 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：原生二进制 → 类 C 伪代码（r2ghidra / r2 系）
- **描述**：Decompile a native binary (ELF/PE/Mach-O) to C-like pseudocode with rizin's built-in Ghidra decompiler (pdg over all functions). Static: analyses and decompiles, never runs the target. Prereq-gated on rizin/r2; honest blind spot with an install hint when absent. Pair with elf/pe/macho-analyze.

### `native-disassemble`
- **路径**：`/var/minis/skills/native-disassemble/SKILL.md`（2.3 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：PE/ELF/Mach-O → 面向函数的反汇编
- **描述**：Disassemble PE, ELF, or Mach-O binaries to function-oriented assembly without executing them. Automatically uses llvm-objdump/objdump, then falls back to Rizin/radare2 analysis for stripped binaries. Writes the complete listing to disassembly.txt and reports instruction/function-line counts.

### `native-lift`
- **路径**：`/var/minis/skills/native-lift/SKILL.md`（3.6 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：机器码区间 lift 到 LLVM IR（x86/amd64/aarch64）
- **描述**：Lift a bounded raw x86, amd64, or aarch64 machine-code region into LLVM IR or bitcode with pinned Remill. Use for semantic analysis of an isolated function, shellcode, or decoder stub. Static and offline: never executes the bytes; rejects whole executable containers.

### `practical-malware-analysis`
- **路径**：`/var/minis/skills/practical-malware-analysis/SKILL.md`（3.5 KB）
- **资源**：目录 references；文件 SOURCE.md
- **一句话**：Defensive malware analysis and reverse-engineering workflow. Use for aut
- **描述**：Defensive malware analysis and reverse-engineering workflow. Use for authorized lab analysis of suspicious Windows executables, DLLs, shellcode, packed samples, malicious documents, indicators of compromise, static and dynamic triage, IDA/Ghidra/debugger reasoning, anti-analysis handling, unpacking, host/network signature creation, and concise malware reports.

### `privesc-arsenal`
- **路径**：`/var/minis/skills/privesc-arsenal/SKILL.md`（8.9 KB）
- **一句话**：One line: Linux + Windows local privilege-escalation tool arsenal for au
- **描述**：One line: Linux + Windows local privilege-escalation tool arsenal for authorized engagements. Trigger signals: "privesc", "got a shell", "escalate", "root", "SYSTEM", initial access gained but not root. Authorized, in-scope targets only.

### `privesc-linux-gtfobins`
- **路径**：`/var/minis/skills/privesc-linux-gtfobins/SKILL.md`（2.4 KB）
- **一句话**：Linux privilege escalation via sudo rules, SUID/SGID binaries, and capab
- **描述**：Linux privilege escalation via sudo rules, SUID/SGID binaries, and capabilities using GTFOBins techniques. Load with a Linux shell needing root, on `sudo -l` output, SUID/`getcap` findings, or "escalate on Linux". Signals: allowed sudo commands, SUID binaries, file capabilities, cron/PATH abuse.

### `privesc-windows-tokens`
- **路径**：`/var/minis/skills/privesc-windows-tokens/SKILL.md`（2.4 KB）
- **一句话**：Windows privilege escalation via token impersonation privileges — SeImpe
- **描述**：Windows privilege escalation via token impersonation privileges — SeImpersonate/SeAssignPrimaryToken (the Potato family) and related token abuse to SYSTEM. Load with a Windows shell as a service/web account, on "SeImpersonate", "whoami /priv", IIS/MSSQL service context, or "got a shell on Windows".

### `r2-recon`
- **路径**：`/var/minis/skills/r2-recon/SKILL.md`（2.9 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：radare2 跨格式静态侦察：函数 / 字符串 / xref 全景
- **描述**：Cross-format static recon of a native binary with radare2: drives r2 headless (-q -c, JSON commands) in one session for binary info, sections + per-section entropy, imports, exports, entry points, analysed functions, and decoded strings (incl. UTF-16). r2 auto-detects ELF/PE/Mach-O/DEX/..., so one skill covers them all and reports the relational view r2 is good at. Classifies imports by capability (inject/exec/network/anti-debug — Windows AND POSIX) and surfaces interesting strings. Emits BINARY.* atoms. Static: r2 analyses structure; it never runs or emulates the target.

### `recon-arsenal`
- **路径**：`/var/minis/skills/recon-arsenal/SKILL.md`（7.0 KB）
- **一句话**：One line: port/host/service discovery tool arsenal for authorized engage
- **描述**：One line: port/host/service discovery tool arsenal for authorized engagements. Pack in trigger signals so it auto-loads: "new target", "enumerate", "scan", an in-scope target, open-port lists needing deeper enum. Authorized, in-scope targets only.

### `recon-js-analysis`
- **路径**：`/var/minis/skills/recon-js-analysis/SKILL.md`（2.0 KB）
- **一句话**：Mine JavaScript for endpoints, params, secrets, and hidden functionality
- **描述**：Mine JavaScript for endpoints, params, secrets, and hidden functionality. Load on SPAs, heavy JS apps, after crawling, or "analyze the JS". Signals: bundled JS (webpack/main.*.js), API calls in JS, source maps, /static/js, front-end frameworks.

### `reconstruct-types`
- **路径**：`/var/minis/skills/reconstruct-types/SKILL.md`（12.2 KB）
- **资源**：目录 scripts；文件 README.md / SOURCE.md / reference.md
- **一句话**：从 IDA 反编译输出重建 C/C++ 结构体 / 类定义
- **描述**：Reconstruct C/C++ struct and class definitions from IDA Pro decompiled code by scanning memory access patterns, vtable contexts, and mangled names across all functions in a module. Use when the user asks to reconstruct types, build struct layouts, extract class hierarchies, generate header files, improve type information for code lifting, or analyze struct/class definitions from decompiled binaries.

### `reporting — findings schema, panel export, report automation`
- **路径**：`/var/minis/skills/reporting — findings schema, panel export, report automation/SKILL.md`（3.4 KB）
- **资源**：目录 templates；文件 finding-schema.json
- **一句话**：Turn engagement output (reports, evidence chains, case dirs) into machin
- **描述**：Turn engagement output (reports, evidence chains, case dirs) into machine-readable findings and an interactive dashboard (ReverseOps panel). Use when writing up findings, generating pentest reports or dashboards, or when the panel shows stale or missing data.

### `reporting-pentest-report`
- **路径**：`/var/minis/skills/reporting-pentest-report/SKILL.md`（2.4 KB）
- **一句话**：Structure a professional penetration-test report (engagement deliverable
- **描述**：Structure a professional penetration-test report (engagement deliverable, not a single bug). Load at the end of a pentest, on "write the pentest report", "executive summary", "deliverable", or compiling findings for a client. Signals: engagement wrap-up, multiple findings, client report.

### `rev-idapython`
- **路径**：`/var/minis/skills/rev-idapython/SKILL.md`（18.6 KB）
- **资源**：文件 SOURCE.md
- **一句话**：IDAPython / IDALib 脚本参考（批量自动化）
- **描述**：IDAPython and IDALib script reference for reverse engineering. Activate when the user needs to write IDAPython scripts in IDA, use IDALib for headless analysis, operate on IDB databases, debug with IDA, manipulate memory/registers, traverse functions/blocks/instructions, work with Hex-Rays decompiler API, handle obfuscation, or batch-process binaries.

### `rev-struct`
- **路径**：`/var/minis/skills/rev-struct/SKILL.md`（5.9 KB）
- **资源**：文件 SOURCE.md
- **一句话**：从内存访问模式重建数据结构
- **描述**：Reconstruct data structures by analyzing memory access patterns across functions

### `rev-symbol`
- **路径**：`/var/minis/skills/rev-symbol/SKILL.md`（6.8 KB）
- **资源**：文件 SOURCE.md
- **一句话**：从代码模式 / 字符串 / 常量恢复函数符号
- **描述**：Restore function symbols by analyzing code patterns, strings, constants, and cross-references

### `reverse-skill-router`
- **路径**：`/var/minis/skills/reverse-skill-router/SKILL.md`（1.5 KB）
- **一句话**：Use the reverse-skill repository. The full package is installed locally 
- **描述**：Use the reverse-skill repository. The full package is installed locally at /var/minis/skills/reverse-skill/ — for authorized reverse engineering, security analysis, CTF, and defensive testing tasks.

### `SKILL: AI Pentest`
- **路径**：`/var/minis/skills/SKILL: AI Pentest/SKILL.md`（39.4 KB）
- **一句话**：AI/LLM security offensive checklist: prompt injection, jailbreaking, mod
- **描述**：AI/LLM security offensive checklist: prompt injection, jailbreaking, model extraction, training data poisoning, adversarial inputs, LLM-assisted attack automation, and AI system reconnaissance. Use when assessing AI/ML systems, red-teaming LLMs, or researching AI attack vectors. Trigger phrases: AI security, LLM security, prompt injection, jailbreak, model extraction, training data poisoning, adversarial input, AI red team, ML security, RAG poisoning, AI attack.

### `SKILL: Bug Identification`
- **路径**：`/var/minis/skills/SKILL: Bug Identification/SKILL.md`（55.1 KB）
- **一句话**：Systematic bug identification methodology: source code review patterns, 
- **描述**：Systematic bug identification methodology: source code review patterns, black-box testing strategies, taint analysis, dangerous function hunting, data flow tracing, and automated scanning setup. Use for code audits, bug bounty triage, or building vulnerability identification pipelines. Trigger phrases: bug identification, code review, taint analysis, dangerous functions, data flow, source audit, black box, vulnerability identification, static analysis, code audit, bug hunting.

### `SKILL: Cross-Site Scripting (XSS)`
- **路径**：`/var/minis/skills/SKILL: Cross-Site Scripting (XSS)/SKILL.md`（24.8 KB）
- **一句话**：Cross-Site Scripting testing checklist: stored/reflected/DOM/blind XSS d
- **描述**：Cross-Site Scripting testing checklist: stored/reflected/DOM/blind XSS discovery, polyglot payloads, CSP bypass, XSS filter bypass, event handler injection, DOM clobbering, mutation XSS, and impact escalation (session hijack, phishing, keylogging). Use for web app XSS testing and bug bounty. Trigger phrases: XSS, cross-site scripting, stored XSS, reflected XSS, DOM XSS, blind XSS, CSP bypass, XSS filter bypass, polyglot, DOM clobbering, mutation XSS, event handler injection.

### `SKILL: Fast Testing Checklist`
- **路径**：`/var/minis/skills/SKILL: Fast Testing Checklist/SKILL.md`（23.7 KB）
- **一句话**：Speed-optimized offensive checklist for rapid assessment: quick-win vuln
- **描述**：Speed-optimized offensive checklist for rapid assessment: quick-win vulnerability patterns, fast recon shortcuts, automated scanner configurations, and triage shortcuts. Use for time-boxed assessments, CTF-speed engagements, or initial rapid surface mapping. Trigger phrases: fast check, quick recon, rapid assessment, quick wins, fast triage, speed checklist, time-boxed, CTF, fast scan, quick vulnerability.

### `SKILL: File Upload Vulnerabilities`
- **路径**：`/var/minis/skills/SKILL: File Upload Vulnerabilities/SKILL.md`（30.5 KB）
- **一句话**：File upload vulnerability checklist: MIME type bypass, extension bypass,
- **描述**：File upload vulnerability checklist: MIME type bypass, extension bypass, magic byte manipulation, path traversal in filenames, stored XSS via SVG/HTML upload, server-side processing attacks, and race conditions. Use for assessing file upload endpoints in web app pentests or bug bounty. Trigger phrases: file upload, MIME bypass, extension bypass, magic byte, path traversal upload, SVG XSS, polyglot, upload bypass, malicious upload, web shell upload.

### `SKILL: HTTP Parameter Pollution (HPP)`
- **路径**：`/var/minis/skills/SKILL: HTTP Parameter Pollution (HPP)/SKILL.md`（16.8 KB）
- **一句话**：HTTP parameter pollution (HPP) checklist: duplicate parameter injection,
- **描述**：HTTP parameter pollution (HPP) checklist: duplicate parameter injection, backend vs frontend parsing differences, WAF bypass via HPP, server-side vs client-side HPP, and practical exploitation patterns. Use when testing web applications for parameter handling flaws. Trigger phrases: parameter pollution, HTTP parameter pollution, HPP, duplicate parameter, WAF bypass, parsing differences, server-side HPP, client-side HPP, parameter injection.

### `SKILL: HTTP Request Smuggling`
- **路径**：`/var/minis/skills/SKILL: HTTP Request Smuggling/SKILL.md`（21.8 KB）
- **一句话**：HTTP request smuggling checklist: CL.TE, TE.CL, TE.TE variants, detectio
- **描述**：HTTP request smuggling checklist: CL.TE, TE.CL, TE.TE variants, detection with timing and differential responses, WAF bypass, cache poisoning, credential hijacking, and request smuggling via HTTP/2. Use when testing reverse proxy/load balancer configurations. Trigger phrases: request smuggling, HTTP smuggling, CL.TE, TE.CL, TE.TE, HTTP/2 smuggling, cache poisoning, WAF bypass, differential response, smuggling detection, proxy desync.

### `SKILL: Insecure Direct Object References (IDOR)`
- **路径**：`/var/minis/skills/SKILL: Insecure Direct Object References (IDOR)/SKILL.md`（25.5 KB）
- **一句话**：IDOR (Insecure Direct Object Reference) testing checklist: object ID enu
- **描述**：IDOR (Insecure Direct Object Reference) testing checklist: object ID enumeration, horizontal/vertical privilege escalation, GUID predictability, indirect references via hashes, chained IDOR, and API endpoint IDOR. Use for web app pentests and bug bounty IDOR discovery. Trigger phrases: IDOR, insecure direct object reference, horizontal privilege escalation, vertical privilege escalation, object enumeration, GUID, API IDOR, mass assignment, broken access control.

### `SKILL: Modern Initial Access`
- **路径**：`/var/minis/skills/SKILL: Modern Initial Access/SKILL.md`（64.5 KB）
- **一句话**：Initial access techniques checklist: phishing (spear/smishing), credenti
- **描述**：Initial access techniques checklist: phishing (spear/smishing), credential stuffing, exposed service exploitation, supply chain attacks, watering hole, VPN/RDP brute force, public-facing application exploitation. Maps to MITRE ATT&CK TA0001. Use when planning initial access phases of red team engagements. Trigger phrases: initial access, phishing, spear phishing, credential stuffing, exposed service, supply chain, watering hole, VPN brute force, RDP attack, MITRE TA0001, initial foothold.

### `SKILL: Novel research`
- **路径**：`/var/minis/skills/SKILL: Novel research/SKILL.md`（11.8 KB）
- **一句话**：Low-level keylogger architecture design: kernel driver hooks (WH_KEYBOAR
- **描述**：Low-level keylogger architecture design: kernel driver hooks (WH_KEYBOARD_LL, SetWindowsHookEx), ETW-based input capture, user-mode vs kernel-mode approaches, stealth techniques, and data exfiltration. Use for understanding input capture mechanisms, EDR evasion research, or malware architecture analysis. Trigger phrases: keylogger, keyboard hook, WH_KEYBOARD_LL, SetWindowsHookEx, ETW, kernel driver, input capture, low-level keylogger, malware architecture, stealth, exfiltration.

### `SKILL: OAuth Security Testing`
- **路径**：`/var/minis/skills/SKILL: OAuth Security Testing/SKILL.md`（15.2 KB）
- **一句话**：OAuth 2.0 attack checklist: authorization code interception, redirect_ur
- **描述**：OAuth 2.0 attack checklist: authorization code interception, redirect_uri bypass, CSRF on OAuth flow, state parameter abuse, open redirector chaining, token leakage via Referer, PKCE bypass, and scope escalation. Use when testing OAuth implementations in web apps or bug bounty. Trigger phrases: OAuth, OAuth 2.0, authorization code, redirect_uri bypass, OAuth CSRF, state parameter, PKCE bypass, scope escalation, token leakage, open redirector, OAuth attack.

### `SKILL: Open Redirect Vulnerabilities`
- **路径**：`/var/minis/skills/SKILL: Open Redirect Vulnerabilities/SKILL.md`（16.4 KB）
- **一句话**：Open redirect vulnerability checklist: parameter identification, bypass 
- **描述**：Open redirect vulnerability checklist: parameter identification, bypass techniques (URL encoding, double slashes, CRLF injection, protocol handlers), chaining with OAuth/SSRF, and impact escalation paths. Use for web app testing and bug bounty open redirect discovery. Trigger phrases: open redirect, URL redirect, redirect bypass, URL encoding bypass, CRLF, protocol handler, redirect chain, OAuth redirect, SSRF chain, open redirection.

### `SKILL: OSINT Methodology`
- **路径**：`/var/minis/skills/SKILL: OSINT Methodology/SKILL.md`（22.7 KB）
- **一句话**：Structured OSINT methodology framework: target definition, source select
- **描述**：Structured OSINT methodology framework: target definition, source selection, collection workflows, data correlation, timeline reconstruction, and reporting. Use to guide systematic OSINT campaigns or teach OSINT methodology. Trigger phrases: OSINT methodology, open source intelligence, target profiling, data correlation, OSINT workflow, intelligence collection, OSINT campaign, recon methodology.

### `SKILL: Race Conditions`
- **路径**：`/var/minis/skills/SKILL: Race Conditions/SKILL.md`（29.2 KB）
- **一句话**：Race condition (TOCTOU) testing checklist: identifying timing windows, B
- **描述**：Race condition (TOCTOU) testing checklist: identifying timing windows, Burp Suite Turbo Intruder, Last-Byte sync technique, rate limit bypass, double-spend attacks, and concurrent request exploitation. Use for web app race condition testing or bug bounty time-of-check-to-time-of-use bugs. Trigger phrases: race condition, TOCTOU, timing attack, Turbo Intruder, last-byte sync, rate limit bypass, double spend, concurrent request, race window, time of check, time of use.

### `SKILL: Remote Code Execution`
- **路径**：`/var/minis/skills/SKILL: Remote Code Execution/SKILL.md`（26.4 KB）
- **一句话**：Remote Code Execution testing checklist: OS command injection, SSTI-to-R
- **描述**：Remote Code Execution testing checklist: OS command injection, SSTI-to-RCE, deserialization RCE, file upload RCE, XXE with SSRF to RCE, RCE via dependency confusion, and CVE-based RCE patterns. Use for web app pentests and bug bounty RCE discovery. Trigger phrases: RCE, remote code execution, command injection, OS injection, SSTI RCE, deserialization RCE, file upload RCE, XXE RCE, dependency confusion, code execution.

### `SKILL: Server-Side Request Forgery (SSRF)`
- **路径**：`/var/minis/skills/SKILL: Server-Side Request Forgery (SSRF)/SKILL.md`（25.8 KB）
- **一句话**：Server-Side Request Forgery testing checklist: SSRF discovery, blind SSR
- **描述**：Server-Side Request Forgery testing checklist: SSRF discovery, blind SSRF with out-of-band, cloud metadata endpoints (AWS/GCP/Azure), SSRF filter bypass techniques (IP encoding, DNS rebinding, redirect chains), and SSRF to RCE escalation. Use for web app SSRF testing and bug bounty. Trigger phrases: SSRF, server-side request forgery, blind SSRF, cloud metadata, AWS metadata, GCP metadata, SSRF bypass, DNS rebinding, redirect chain, SSRF RCE, internal port scan.

### `SKILL: WAF Bypass Techniques`
- **路径**：`/var/minis/skills/SKILL: WAF Bypass Techniques/SKILL.md`（37.4 KB）
- **一句话**：WAF bypass techniques checklist: encoding bypass (URL/HTML/Unicode/doubl
- **描述**：WAF bypass techniques checklist: encoding bypass (URL/HTML/Unicode/double encoding), case variation, comment injection, HTTP header manipulation, chunked encoding, IP rotation, timing attacks, and payload obfuscation per WAF vendor. Use when WAF is blocking payloads during web app tests. Trigger phrases: WAF bypass, web application firewall bypass, URL encoding, double encoding, Unicode bypass, comment injection, HTTP header bypass, chunked encoding, IP rotation, payload obfuscation, WAF evasion.

### `SKILL: Week 2: Finding Vulnerabilities Through Fuzzing`
- **路径**：`/var/minis/skills/SKILL: Week 2: Finding Vulnerabilities Through Fuzzing/SKILL.md`（79.0 KB）
- **一句话**：Week 2 of the exploit development curriculum. Covers fuzzing methodology
- **描述**：Week 2 of the exploit development curriculum. Covers fuzzing methodology: target selection, corpus generation, coverage-guided fuzzing with AFL++/libFuzzer, structured fuzzing, and triage/deduplication. Use when setting up fuzz campaigns, selecting harness strategies, or triaging fuzzer output. Trigger phrases: fuzzing curriculum, AFL++, libFuzzer, coverage-guided fuzzing, corpus generation, harness, fuzz target, mutation, triage, crash dedup, week 2, exploit dev course.

### `SKILL: Week 6: Understanding Windows Mitigations`
- **路径**：`/var/minis/skills/SKILL: Week 6: Understanding Windows Mitigations/SKILL.md`（518.5 KB）
- **一句话**：Deep-dive on Windows exploit mitigations: ASLR, DEP/NX, CFG, CET/Shadow 
- **描述**：Deep-dive on Windows exploit mitigations: ASLR, DEP/NX, CFG, CET/Shadow Stack, SEHOP, Heap Guard, ACG, Arbitrary Code Guard. Covers both the protection mechanism and known bypass techniques. Use when researching Windows exploit mitigations, planning bypass strategies, or understanding protection depth. Trigger phrases: Windows mitigations, ASLR, DEP, NX, CFG, CET, shadow stack, SEHOP, heap guard, ACG, mitigation bypass, exploit mitigation, Windows hardening.

### `SKILL: Week 7: Defeating Windows Security Boundaries`
- **路径**：`/var/minis/skills/SKILL: Week 7: Defeating Windows Security Boundaries/SKILL.md`（554.7 KB）
- **一句话**：Windows security boundary taxonomy and attack surface enumeration: kerne
- **描述**：Windows security boundary taxonomy and attack surface enumeration: kernel/user boundary, sandbox boundaries (LPAC, AppContainer), COM/RPC boundaries, hypervisor boundary, trust level transitions. Use when planning privilege escalation paths, sandbox escapes, or understanding Windows security architecture. Trigger phrases: Windows boundaries, security boundary, kernel user boundary, sandbox escape, AppContainer, LPAC, COM boundary, RPC boundary, hypervisor, Hyper-V, privilege escalation, trust level.

### `SKILL: XML External Entity (XXE) Injection`
- **路径**：`/var/minis/skills/SKILL: XML External Entity (XXE) Injection/SKILL.md`（28.2 KB）
- **一句话**：XML External Entity injection testing checklist: classic XXE, blind XXE 
- **描述**：XML External Entity injection testing checklist: classic XXE, blind XXE (out-of-band), XXE via file upload (SVG/docx), XXE in SOAP/REST, error-based XXE, XInclude attacks, and XXE filter bypass. Use for web app XXE testing and bug bounty. Trigger phrases: XXE, XML external entity, blind XXE, out-of-band XXE, XXE file upload, SVG XXE, SOAP XXE, XInclude, entity bypass, XXE SSRF, XXE file read.

### `web-arsenal`
- **路径**：`/var/minis/skills/web-arsenal/SKILL.md`（7.3 KB）
- **一句话**：One line: web enumeration + exploitation tool arsenal for authorized eng
- **描述**：One line: web enumeration + exploitation tool arsenal for authorized engagements. Trigger signals: port 80/443/8080/8443 open, "web", a URL to a lab target, an HTTP service surfaced by recon. Authorized, in-scope targets only.

### `web-auth-jwt`
- **路径**：`/var/minis/skills/web-auth-jwt/SKILL.md`（2.4 KB）
- **资源**：文件 cheatsheet.md
- **一句话**：Attack JWT/session authentication. Load when auth uses a JWT (three base
- **描述**：Attack JWT/session authentication. Load when auth uses a JWT (three base64url parts, header.payload.signature), Authorization: Bearer, or you see alg/kid/jku fields. Signals: eyJ... tokens, "alg":"none"/"HS256"/"RS256", kid header, JWKS endpoints, role/admin claims.

### `web-cache-poisoning`
- **路径**：`/var/minis/skills/web-cache-poisoning/SKILL.md`（2.5 KB）
- **一句话**：Web cache poisoning & deception — get a shared cache to serve attacker c
- **描述**：Web cache poisoning & deception — get a shared cache to serve attacker content to other users, or trick it into caching victims' private pages. Load behind a CDN/cache (Cloudflare, Varnish, Fastly, Akamai), on unkeyed headers, `X-Forwarded-Host`, cache headers, or static-looking URLs. Signals: `Age`/`X-Cache` headers, CDN, reflected headers.

### `web-command-injection`
- **路径**：`/var/minis/skills/web-command-injection/SKILL.md`（2.8 KB）
- **资源**：文件 cheatsheet.md
- **一句话**：Turn user input that reaches a shell into arbitrary OS command execution
- **描述**：Turn user input that reaches a shell into arbitrary OS command execution. Load when a parameter feeds a system call — ping/nslookup/host tools, file conversion (ImageMagick, ffmpeg), archive/ export, PDF/thumbnail generation, filename handling, or any "network tools" feature. Signals: output that looks like command output, a value echoed into a system utility, blind time/OOB behaviour.

### `web-csrf`
- **路径**：`/var/minis/skills/web-csrf/SKILL.md`（2.2 KB）
- **一句话**：Cross-Site Request Forgery — force a victim's browser to perform state-c
- **描述**：Cross-Site Request Forgery — force a victim's browser to perform state-changing actions. Load on state-changing requests (POST/PUT/DELETE) that rely only on cookies, missing/weak CSRF tokens, `SameSite=None`, or forms/JSON without anti-CSRF. Signals: cookie-only auth, no token, token not validated.

### `web-deserialization`
- **路径**：`/var/minis/skills/web-deserialization/SKILL.md`（2.3 KB）
- **资源**：文件 cheatsheet.md
- **一句话**：Insecure deserialization → RCE via gadget chains. Load when the app dese
- **描述**：Insecure deserialization → RCE via gadget chains. Load when the app deserializes attacker data: Java (rO0/AC ED base64), PHP `unserialize` (O:), Python pickle, .NET BinaryFormatter/ViewState, Ruby Marshal/YAML. Signals: serialized blobs in cookies/params, `__VIEWSTATE`, `rO0AB`, `O:8:`.

### `web-lfi-path-traversal`
- **路径**：`/var/minis/skills/web-lfi-path-traversal/SKILL.md`（2.7 KB）
- **一句话**：Local File Inclusion / path traversal → read files, sometimes RCE. Load 
- **描述**：Local File Inclusion / path traversal → read files, sometimes RCE. Load when a param names a file/path/template/page: ?file=, ?page=, ?template=, ?download=, ?lang=, or path segments. Signals: filenames in params, "include", download endpoints, `../` filtered, `.php?page=`.

### `web-sqli`
- **路径**：`/var/minis/skills/web-sqli/SKILL.md`（3.2 KB）
- **资源**：文件 cheatsheet.md
- **一句话**：Detect and exploit SQL injection (error-based, UNION, boolean/time blind
- **描述**：Detect and exploit SQL injection (error-based, UNION, boolean/time blind, stacked). Load when a param feeds a query, you see DB errors, numeric/string params change result sets, login forms, search, sort/order-by, or ORM raw queries. Signals: "id=", 500 on a quote, "You have an error in your SQL syntax", MySQL/Postgres/MSSQL/Oracle banners.

### `web-ssti`
- **路径**：`/var/minis/skills/web-ssti/SKILL.md`（2.5 KB）
- **资源**：文件 cheatsheet.md
- **一句话**：Server-Side Template Injection → RCE. Load when user input is rendered b
- **描述**：Server-Side Template Injection → RCE. Load when user input is rendered by a template engine: profile names in emails, custom reports, "hello {{name}}", error pages echoing math, Jinja2/Twig/Freemarker/Velocity/ERB/Handlebars. Signals: {{7*7}} returns 49, ${...} or #{...} evaluated, framework stack traces mentioning a templating engine.

### `web-testing-checklist`
- **路径**：`/var/minis/skills/web-testing-checklist/SKILL.md`（2.1 KB）
- **一句话**：A fast, ordered checklist for testing a web application end to end — so 
- **描述**：A fast, ordered checklist for testing a web application end to end — so nothing gets skipped. Load when starting on a web target, "checklist", "what should I test", methodology triage, or to confirm coverage before reporting. Signals: a new web app in scope, "am I missing anything".

### `zhaoxuya-field-journal`
- **路径**：`/var/minis/skills/zhaoxuya-field-journal/SKILL.md`（3.9 KB）
- **资源**：目录 journal
- **一句话**：逆向/安全实战日记合集（45 篇真实案例，含 Android/Go/DSL-VM/Electron/固件/APK 等方向的一手复盘笔记）。当遇到
- **描述**：逆向/安全实战日记合集（45 篇真实案例，含 Android/Go/DSL-VM/Electron/固件/APK 等方向的一手复盘笔记）。当遇到类似目标或想参考真实作战思路时加载对应的日记。Use when looking for real-world case studies and field notes on reverse engineering and pentesting engagements.

### `🔄 DSL 自定义虚拟机逆向（DSL VM Reverse Engineering）`
- **路径**：`/var/minis/skills/🔄 DSL 自定义虚拟机逆向（DSL VM Reverse Engineering）/SKILL.md`（11.1 KB）
- **一句话**：逆向基于 JavaScript 实现的自定义 WASM 虚拟机/风控引擎：识别特征、opcode 提取与分类、运行时捕获、状态码对照与自检清单。
- **描述**：逆向基于 JavaScript 实现的自定义 WASM 虚拟机/风控引擎：识别特征、opcode 提取与分类、运行时捕获、状态码对照与自检清单。当需要逆向 JS 混淆 VM、DSL VM 或自定义字节码引擎时使用。

## 🧩 字节码 · 脚本语言（5）

### `dotnet-decompile`
- **路径**：`/var/minis/skills/dotnet-decompile/SKILL.md`（1.1 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：.NET 程序集反编译回 C#（ilspycmd）
- **描述**：Decompile a .NET / CLR assembly (IL) back to C# with the ilspycmd dotnet tool. Static: reads metadata + IL, never runs the assembly. Prereq-gated on ilspycmd (needs the .NET runtime); honest blind spot with an install hint when absent. Pair with dotnet-analyze for the P/Invoke surface.

### `js-deobfuscate`
- **路径**：`/var/minis/skills/js-deobfuscate/SKILL.md`（3.1 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：JavaScript 混淆还原 / 解包（webcrack）
- **描述**：Deobfuscate and unpack obfuscated JavaScript (webcrack): reverses string arrays, folds constants, deflattens control flow, unminifies, and splits webpack/browserify bundles. Encoded string arrays are decoded by running the decoder inside an isolated-vm sandbox — not the whole program.

### `jvm-decompile`
- **路径**：`/var/minis/skills/jvm-decompile/SKILL.md`（1.2 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Java / Android 字节码反编译（apk/dex/jar/class）
- **描述**：Decompile Java / Android bytecode (.apk / .dex / .jar / .class) back to Java source with jadx. Static: reads bytecode, never runs it. Prereq-gated on the jadx CLI (which needs a JRE); when jadx is absent the skill reports the honest blind spot with an install hint.

### `pojia-next`
- **路径**：`/var/minis/skills/pojia-next/SKILL.md`（1.2 KB）
- **资源**：目录 .github / _回归测试；文件 .bandit.yml / .gitattributes / .gitignore / .semgrep.yml / LICENSE / README.md / SHA256SUMS.txt / fill_hashes.py…
- **一句话**：破甲一键通 v7.5 —— 把多套破甲工具合并为一个一键脚本（目标：DSH / WorkBuddy / ZCode；统一人格、备份/回滚、破甲自
- **描述**：破甲一键通 v7.5 —— 把多套破甲工具合并为一个一键脚本（目标：DSH / WorkBuddy / ZCode；统一人格、备份/回滚、破甲自检、--check 只读体检）。Python 主脚本 + Windows 双击 bat。当需要为上述目标做破甲注入/还原、或查阅其回归测试与修复记录时使用。

### `pyc-decompile`
- **路径**：`/var/minis/skills/pyc-decompile/SKILL.md`（2.2 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Python 字节码（.pyc）反编译回源码
- **描述**：Decompile Python bytecode (.pyc / compiled code objects) back to source with decompyle3. Best for CPython 3.7-3.8 bytecode (e.g. PyInstaller-extracted payloads); reports honestly when the bytecode version is out of range. Static: reads bytecode, never runs it.

## 🪝 Frida · 动态插桩（8）

### `frida-android-hooks`
- **路径**：`/var/minis/skills/frida-android-hooks/SKILL.md`（3.4 KB）
- **资源**：目录 agents / references；文件 SOURCE.md
- **一句话**：Android Frida 钩子：Java.perform / 重载 / 构造器 / Kotlin / JNI / Gadget
- **描述**：Create and debug Frida hooks for Android apps, including Java.perform, overloads, constructors, class loaders, Kotlin, JNI, pinning, spawn, and Gadget.

### `frida-android-instrument`
- **路径**：`/var/minis/skills/frida-android-instrument/SKILL.md`（3.1 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：动态检查 Android Java 运行时（授权 App 的运行时透视）
- **描述**：DYNAMIC: inspect an authorized Android app's Java runtime through Frida: list loaded classes, enumerate method signatures, or install observation-only hooks that report arguments and return values without intentionally changing them. Use for runtime discovery when static APK/DEX analysis is insufficient. Attaches to or spawns the app on a BYO Frida-capable USB device; executes the target and is consent-gated.

### `frida-anti-instrumentation`
- **路径**：`/var/minis/skills/frida-anti-instrumentation/SKILL.md`（2.1 KB）
- **资源**：目录 agents；文件 SOURCE.md
- **一句话**：反 Frida / 反调试 / root / 越狱检测的识别与绕过
- **描述**：Analyze and bypass anti-Frida, anti-debugging, root or jailbreak checks, emulator checks, ptrace, port scans, module scans, and integrity checks.

### `frida-ios-hooks`
- **路径**：`/var/minis/skills/frida-ios-hooks/SKILL.md`（3.0 KB）
- **资源**：目录 agents / references；文件 SOURCE.md
- **一句话**：iOS Frida 钩子：Objective-C / Swift
- **描述**：Create and debug Frida hooks for iOS apps, including Objective-C, Swift symbols, modules, Interceptor, TLS pinning, rootless jailbreaks, Gadget, and ObjC issues.

### `frida-native-hooks`
- **路径**：`/var/minis/skills/frida-native-hooks/SKILL.md`（3.5 KB）
- **资源**：目录 agents / references；文件 SOURCE.md
- **一句话**：原生函数钩子：C/C++/ObjC 导出 / 导入 / 内存层
- **描述**：Build Frida native hooks for C/C++/Objective-C functions, exports, imports, symbols, memory, Interceptor, NativeFunction, Stalker, and CModule.

### `frida-tls-pinning`
- **路径**：`/var/minis/skills/frida-tls-pinning/SKILL.md`（1.8 KB）
- **资源**：目录 agents / references；文件 SOURCE.md
- **一句话**：TLS 证书绑定绕过（Android/iOS/Flutter，Frida 版）
- **描述**：Analyze and bypass TLS or SSL pinning with Frida on Android, iOS, Flutter, React Native, native BoringSSL/OpenSSL, Conscrypt, OkHttp, NSURLSession, SecTrust, and app-specific trust code.

### `frida-trace`
- **路径**：`/var/minis/skills/frida-trace/SKILL.md`（1.4 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Frida 动态追踪：网络等关键行为一网打尽
- **描述**：DYNAMIC: spawn a target under Frida and trace a curated set of network/exec/file/crypto API calls (dynamic instrumentation, no debugger). Logs the calls the sample makes. EXECUTES the target; consent-gated. BYO frida-trace (pip install frida-tools).

### `rev-frida`
- **路径**：`/var/minis/skills/rev-frida/SKILL.md`（10.1 KB）
- **资源**：文件 SOURCE.md
- **一句话**：现代 Frida API 钩子脚本生成（激活即产出可直接跑的 agent）
- **描述**：Generate Frida hook scripts using modern Frida API. Activate when the user wants to write Frida scripts, hook functions at runtime, trace calls or arguments or return values, intercept native or ObjC or Java methods, dump memory or exports, or handle native module load timing for Android and other targets.

## 🐞 调试 · 仿真 · 追踪（6）

### `emulate-code`
- **路径**：`/var/minis/skills/emulate-code/SKILL.md`（2.2 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：裸 code / shellcode 在虚拟 CPU 上仿真（x86/x64/ARM/ARM64）
- **描述**：Emulate a raw code/shellcode blob on a virtual CPU (x86/x64/arm/arm64) with Unicorn and report the final register state, instruction count, and memory writes. Contained: the bytes run on an emulated CPU, not the host (memory-only; no host syscalls unless wired) — the safe way to 'run' shellcode or an isolated function.

### `gdb`
- **路径**：`/var/minis/skills/gdb/SKILL.md`（13.6 KB）
- **资源**：目录 examples / scripts；文件 SOURCE.md / demo_prompts.md
- **一句话**：Debug and trace C/C++/Rust programs with the GNU Debugger (GDB) without 
- **描述**：Debug and trace C/C++/Rust programs with the GNU Debugger (GDB) without blocking the agent. Use when you need to set tracepoints, inspect variables, or monitor a running process while staying responsive to the user.

### `js-reverse-ops`
- **路径**：`/var/minis/skills/js-reverse-ops/SKILL.md`（14.3 KB）
- **资源**：目录 .claude-plugin / .github / agents / assets / commands / examples / playbooks / references…；文件 .gitattributes / .gitignore / AGENTS.md / AI_USAGE.md / CHANGELOG.md / CHECKLIST.md / CONTRIBUTING.md / LICENSE…
- **一句话**：Execute advanced JavaScript reverse-engineering workflows for modern web
- **描述**：Execute advanced JavaScript reverse-engineering workflows for modern web applications, including signature recovery, runtime instrumentation, deobfuscation, bundle analysis, anti-debug bypass, environment rebuild, and replay validation. Use when an agent needs to analyze obfuscated or minified frontend code, trace request-signing logic, recover crypto flows, hook browser runtime behavior, rebuild browser-only logic in Node/Python, or produce evidence-backed reverse-engineering reports. Do not use it for writing new crawlers from scratch, general frontend development, or binary/APK reverse engineering.

### `qiling-emulate`
- **路径**：`/var/minis/skills/qiling-emulate/SKILL.md`（2.8 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Qiling 全二进制仿真：PE/ELF/Mach-O 在沙箱里跑起来
- **描述**：Emulate a FULL binary (PE/ELF/Mach-O/…) with the Qiling framework: loads the program and emulates the OS/syscalls against a BYO rootfs, so a Linux ELF or Windows PE can be detonated on this host cross-arch/cross-OS WITHOUT native execution or a VM. Contained: syscalls hit Qiling's emulation, not the host kernel. Complements emulate-code (raw shellcode, no OS) and exec-observe (native run).

### `rev-unicorn-debug`
- **路径**：`/var/minis/skills/rev-unicorn-debug/SKILL.md`（4.4 KB）
- **资源**：文件 SOURCE.md
- **一句话**：Unicorn 针对代码片段 / 单函数的仿真调试
- **描述**：Debug and emulate specific code fragments or functions using the Unicorn engine. Activate when the user wants to emulate a function with Unicorn, trace binary execution without running the full program, decrypt or decode data by emulating the algorithm, or bypass environment dependencies (JNI, syscalls, libc) during emulation.

### `syscall-trace`
- **路径**：`/var/minis/skills/syscall-trace/SKILL.md`（1.5 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：系统调用追踪：strace / dtruss
- **描述**：DYNAMIC: run a target under a syscall tracer (strace on Linux, dtruss on macOS) and summarize its behaviour — files opened, network connects, processes exec'd, and a syscall histogram. EXECUTES the target; consent-gated. dtruss needs root + a permissive SIP.

## 🤖 Android 专项（7）

### `android-native-auto-reverse` ★
- **路径**：`/var/minis/skills/android-native-auto-reverse/SKILL.md`（15.6 KB）
- **资源**：目录 agents / references / scripts
- **一句话**：安卓逆向统一入口：APK/AAB/XAPK/DEX/JAR/AAR/ELF.so 全流程
- **描述**：Unified Android mobile reverse-engineering skill for authorized APK/AAB/XAPK/DEX/JAR/AAR/ELF .so work. Use for static analysis with JADX/apktool/resources, shell/packer recognition with APKiD and apkpackdata rules, Frida/objection runtime Hook, frida-dexdump/BlackDex/FART/youpk dex unpacking, Bangcle/libDexHelper anti-Frida, server-only versus agent-loaded detection triage, clone/pthread detection-thread tracing, Bionic pthread start-routine recovery, and exit_group bypass triage, ART DexFile/mCookie/ClassLoader unpacking strategy, loaded .so dump and repair, Burp Suite/r0capture/request traffic analysis, Frida-to-Python-to-Burp plaintext crypto bridge, OkHttp/Retrofit/WebView/mPaaS RpcInvoker/JsonSerializerV2/API/signature tracing, JADX and IDA/Ghidra Java-native correlation, SO/JNI/RegisterNatives analysis, native crypto/signing, anti-debug/anti-Frida/root/emulator/VPN/proxy checks, and concise evidence reports.

### `android-reverse-engineering`
- **路径**：`/var/minis/skills/android-reverse-engineering/SKILL.md`（15.9 KB）
- **资源**：目录 references / scripts；文件 SOURCE.md
- **一句话**：jadx / Fernflower 反编译 APK / XAPK / JAR / AAR
- **描述**：Decompile Android APK, XAPK, JAR, and AAR files using jadx or Fernflower/Vineflower. Reverse engineer Android apps, extract HTTP API endpoints (Retrofit, OkHttp, Volley), and trace call flows from UI to network layer. Use when the user wants to decompile, analyze, or reverse engineer Android packages, find API endpoints, or follow call flows. 中文触发词：反编译APK、安卓逆向、提取API、分析安卓应用、反编译安卓、逆向工程、追踪调用链、提取接口

### `android-static-analysis`
- **路径**：`/var/minis/skills/android-static-analysis/SKILL.md`（10.2 KB）
- **资源**：目录 references / scripts；文件 SOURCE.md
- **一句话**：APK 静态分析：反编译 / Manifest / 代码审计
- **描述**：Decompile Android APK, XAPK, JAR, and AAR files using jadx or Fernflower/Vineflower. Reverse engineer Android apps, extract HTTP API endpoints (Retrofit, OkHttp, Volley), trace call flows from UI to network layer, analyze obfuscated code. Use when the user wants to decompile, analyze, or reverse engineer Android packages, find API endpoints, follow call flows, or perform static analysis on Android applications.

### `bangcle-unpack`
- **路径**：`/var/minis/skills/bangcle-unpack/SKILL.md`（2.0 KB）
- **资源**：目录 docs / src；文件 README-source.md
- **一句话**：梆梆企业加固脱壳专技：classes0.jar 直接解密 + Frida 内存 dump 双路线
- **描述**：企业加固（梆梆 Bangcle / libDexHelper 系）脱壳专技。含两条脱壳路线：直接解密 classes0.jar（C++ 解密器源码）与 Frida hook 内存 dump；附完整逆向调试记录。当目标 APK 被加固（APKiD 报 bangcle/nqshield/娜迦等）、类抽取/填充式加固、Frida 遭反调试干扰时使用。

### `dex-dump`
- **路径**：`/var/minis/skills/dex-dump/SKILL.md`（2.7 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：运行中 App 内存 DEX / CompactDex dump（脱壳）
- **描述**：Dump decrypted DEX and CompactDex images from a RUNNING Android app's memory with Rekit's clean-room Apache-2.0 device tool (ptrace on a rooted aarch64 device). Defeats class-loading packers by reading the image after the app decrypts it. Does not launch the app or execute a sample on the host. BYO rooted device + adb; build the device tool from the included Rust source.

### `dsh-apk-reverse`
- **路径**：`/var/minis/skills/dsh-apk-reverse/SKILL.md`（11.6 KB）
- **资源**：目录 references / scripts
- **一句话**：CLI 环境 APK 逆向：解包 / 反编译 / smali 改 / 重打包 / Frida
- **描述**：在 CLI 环境下做 Android APK 逆向时使用。适用于 APK 解包、Java 反编译、smali 修改、重打包、Frida 动态 Hook，以及按需切换到 so/native 分析。优先使用本机已安装的 jadx、apktool、frida、adb、ida-reverse、radare2。

### `rev-dex-dumper`
- **路径**：`/var/minis/skills/rev-dex-dumper/SKILL.md`（2.4 KB）
- **资源**：文件 SOURCE.md / panda-dex-dumper
- **一句话**：DEX dump 脱壳 / 解混淆流程
- **描述**：Dump DEX files from a running Android app for unpacking/deobfuscation. Activate when the user wants to unpack an Android APK, dump DEX from memory, extract decrypted DEX files, or defeat class-loading packing.

## 🍎 iOS 专项（1）

### `ios-reverse-engineering`
- **路径**：`/var/minis/skills/ios-reverse-engineering/SKILL.md`（27.1 KB）
- **资源**：文件 SOURCE.md
- **一句话**：iOS 逆向：IPA / .app / Mach-O / dylib / 框架提取分析
- **描述**：Extract and analyze iOS IPA, .app bundles, Mach-O binaries, .dylib, and .framework files using ipsw, otool, strings, radare2/rizin, and Ghidra headless. Reverse engineer iOS apps, extract HTTP API endpoints (URLSession, Alamofire, Moya, AFNetworking, GraphQL, WebSocket), trace call flows from ViewControllers to network layer, analyze security patterns (ATS, cert pinning, keychain, jailbreak detection), deep-scan for cloud credentials (Firebase, AWS, GCP, Azure, Stripe), perform LLM-assisted binary reversing analysis with Ghidra scripts, fingerprint embedded third-party SDKs with CVE checking, and detect anti-tampering protections (obfuscation, anti-debug, dylib injection prevention, integrity checks). Use when the user wants to extract, analyze, or reverse engineer iOS packages, find API endpoints, follow call flows, audit app security, scan for leaked secrets, identify third-party SDKs, detect app protections, or perform deep binary analysis.

## 📱 移动安全评估（4）

### `mobile-cert-pinning-bypass` ★
- **路径**：`/var/minis/skills/mobile-cert-pinning-bypass/SKILL.md`（2.1 KB）
- **一句话**：证书绑定绕过总法：抓包被挡先读它（SSL handshake 失败信号）
- **描述**：Bypass TLS certificate pinning so you can proxy a mobile app's traffic. Load when a proxy shows no/broken traffic, you see SSL handshake failures in logs, OkHttp CertificatePinner, TrustKit, or "the app won't connect through Burp". Android/iOS.

### `mobile-security-suite`
- **路径**：`/var/minis/skills/mobile-security-suite/SKILL.md`（1.7 KB）
- **资源**：目录 references
- **一句话**：移动安全评估套件：12 维度 / MASVS 检查表 / 威胁建模
- **描述**：移动应用安全评估套件（12 维度）：认证/加密/安全存储/网络/平台交互/韧性（反调试·root·完整性）/隐私/代码质量/MASVS 检查表/威胁建模/测试计划/安全开发。当用户要求评估移动应用安全性、审计 APK/IPA、按 MASVS/MASTG 检查、梳理移动漏洞面时使用。

### `renef`
- **路径**：`/var/minis/skills/renef/SKILL.md`（13.5 KB）
- **资源**：目录 references；文件 SOURCE.md / probe.lua
- **一句话**：Use when operating renef / renef.io to instrument Android ARM64 apps: ho
- **描述**：Use when operating renef / renef.io to instrument Android ARM64 apps: hooking native and Java functions, scanning/reading/writing/patching process memory, tracing syscalls (renef-strace), stack backtraces, value/memory cheats, and writing Lua 5.4 scripts. Reach for this for SSL pinning bypass, root/debugger detection bypass, function tracing, crypto key logging, game memory editing/cheats, CTF native challenges, or porting Frida JS / GameGuardian (gg.*) scripts to renef. Triggers: "renef", "renef.io", ".renef script", "renef-strace", "hook this Android function", "bypass SSL pinning with renef", "port this Frida/GameGuardian script to renef".

### `spider-king`
- **路径**：`/var/minis/skills/spider-king/SKILL.md`（28.7 KB）
- **资源**：目录 agents / references / scripts / tests；文件 LICENSE / README.md / SOURCE.md
- **一句话**：Pure-web protocol reverse skill: turn hostile browser clients into brows
- **描述**：Pure-web protocol reverse skill: turn hostile browser clients into browser-free Python collectors. Auto-judge intake and tool path from signals: artifact-only first when samples suffice; for a fresh web live-target, collect sequential fingerprint-baseline then debugger-trace evidence (default chrome-devtools then js-reverse; upgrade baseline host to Camoufox/managed profile only on fingerprint pressure); for continuation, reuse the current gate when target and environment are unchanged. Route only mounted web-relevant MCP families. Out of primary scope: APK, native app, and mini-program reverse as the main path. Use for hostile web sign, token, cookie, WebSocket, GraphQL, protobuf, response-decode, browser-fingerprint, WebAssembly, challenge-bootstrap, dynamic-font, or protocol-collector flows.

## 🦠 恶意代码 · 检测规则（5）

### `malware-triage` ★
- **路径**：`/var/minis/skills/malware-triage/SKILL.md`（13.4 KB）
- **资源**：目录 references / scripts；文件 SOURCE.md
- **一句话**：恶意样本快速静态分诊 / 分级 / 优先级（样本到手第一步）
- **描述**：Rapid static assessment, classification, and prioritization of malware samples. Use for the first look at any unknown file — hashes, file type, packing, imports, strings, initial IOCs, threat level, and the decision on which deep-analysis phase comes next. Claude runs the static tooling on the host itself; the sample is never executed.

### `malware-dynamic-analysis`
- **路径**：`/var/minis/skills/malware-dynamic-analysis/SKILL.md`（19.2 KB）
- **资源**：目录 references / scripts；文件 SOURCE.md
- **一句话**：隔离 VM 行为分析（执行后的动态侧）
- **描述**：Behavioral analysis of a sample executed in an isolated VM. Use after triage when runtime behavior, C2 traffic, dropped files, persistence, or injection must be observed. Claude produces a tailored VM runbook from triage predictions, then parses the exported text evidence (Procmon CSV, Sysmon JSON/CSV, tshark output, autoruns, strings) on the host to reconstruct behavior and extract IOCs. The analyst runs the VM; Claude never executes the sample.

### `open-static-malware-analysis`
- **路径**：`/var/minis/skills/open-static-malware-analysis/SKILL.md`（31.0 KB）
- **资源**：目录 references
- **一句话**：Static malware analysis skill for examining suspicious files without exe
- **描述**：Static malware analysis skill for examining suspicious files without execution. Performs file triage, PE/ELF/Mach-O binary analysis, document analysis (Office macros, PDFs), script deobfuscation, entropy analysis, string extraction, IOC identification, packer/obfuscation detection, and generates structured reports with MITRE ATT&CK mappings and risk assessments. Complements dynamic analysis sandboxes with deep static examination. Trigger whenever the user uploads a suspicious file, mentions malware analysis, reverse engineering, file triage, IOC extraction, suspicious binary, PE analysis, macro analysis, static analysis, or asks "is this file malicious". Also trigger when file metadata, hashes, imports, strings, entropy, or embedded artifacts are mentioned in a security context. Use this skill proactively — if a file is uploaded and security analysis seems relevant, load it.

### `yara-rule-authoring`
- **路径**：`/var/minis/skills/yara-rule-authoring/SKILL.md`（23.3 KB）
- **资源**：目录 agents / assets / examples / references / scripts / workflows；文件 SOURCE.md
- **一句话**：YARA-X 高质量检测规则编写（含测试方法）
- **描述**：Guides authoring of high-quality YARA-X detection rules for malware identification. Use when writing, reviewing, or optimizing YARA rules. Covers naming conventions, string selection, performance optimization, migration from legacy YARA, and false positive reduction. Triggers on: YARA, YARA-X, malware detection, threat hunting, IOC, signature, crx module, dex module.

### `yara-scan`
- **路径**：`/var/minis/skills/yara-scan/SKILL.md`（1.8 KB）
- **资源**：目录 assets / scripts；文件 SOURCE.md
- **一句话**：YARA 扫描文件 / 目录（classic + YARA-X）
- **描述**：Scan a file or directory with YARA rules (classic yara or the newer yara-x). Ships a small high-signal starter rule pack; point --rules at a real corpus (YARA-Rules, signature-base, your own) for serious coverage. Read-only — matches patterns, never runs the target. Prereq-gated on the yara CLI with honest degradation.

## ⚔️ 漏洞利用 · 红队（25）

### `adscan-ad-agents`
- **路径**：`/var/minis/skills/adscan-ad-agents/SKILL.md`（683 B）
- **资源**：文件 ad-attack-planner.md / ad-enumerator.md / ad-exploit-operator.md
- **一句话**：Active Directory 攻击多智能体定义集（3 个角色：攻击规划 / 枚举 / 利用操作）。配合 ADScan 工作流或独立用于红队 
- **描述**：Active Directory 攻击多智能体定义集（3 个角色：攻击规划 / 枚举 / 利用操作）。配合 ADScan 工作流或独立用于红队 AD 战役的分阶段推理。Use when planning or executing authorized Active Directory attack chains with staged agent personas.

### `aflpp`
- **路径**：`/var/minis/skills/aflpp/SKILL.md`（21.9 KB）
- **资源**：目录 agents / assets；文件 SOURCE.md
- **一句话**：AFL++ 多核 Fuzzing：C/C++ 项目插桩 / 跑起来 / 出 crash
- **描述**：Sets up and runs AFL++ for multi-core fuzzing of C/C++ projects built with afl-clang-fast or afl-gcc-fast. Covers instrumentation modes, parallel main and secondary campaigns, persistent mode, corpus minimization, and crash triage. Use when scaling fuzzing across cores, fuzzing a mature C/C++ codebase, reading the afl-fuzz status screen, or moving on after libFuzzer has plateaued.

### `ctf-sandbox`
- **路径**：`/var/minis/skills/ctf-sandbox/SKILL.md`（1.5 KB）
- **一句话**：Thin PRIMARY for CTF / AWD / 靶场 multi-type orchestration. Hands off to t
- **描述**：Thin PRIMARY for CTF / AWD / 靶场 multi-type orchestration. Hands off to the sidecar CTF-Sandbox-Orchestrator. Use when the user says CTF, AWD, 靶场, or 比赛题 and no more specific pwn/APK/IDA route already won.

### `dsh-edr-bypass`
- **路径**：`/var/minis/skills/dsh-edr-bypass/SKILL.md`（9.3 KB）
- **资源**：目录 references
- **一句话**：先逆向 EDR/AV 实现 → 再写针对性绕过（unhook/间接 syscall/ETW patch）
- **描述**：逆向防御方实现 → 红队针对性绕过。把 EDR / Defender / AV 的 hook 表、ETW provider、AMSI 实现先逆向出来， 再写针对性的 unhook / 间接 syscall / ETW patch / call stack spoof。对照 MITRE ATT&CK T1562 防御规避。 触发关键词：EDR 绕过、AV bypass、免杀、unhook、direct syscall、indirect syscall、Hell's Gate、Halo's Gate、 Tartarus Gate、ETW patch、AMSI patch、call stack spoofing、hardware breakpoint Blindside、MITRE T1562、 ntdll unhook、kernel callback、CrowdStrike 绕过、Defender 绕过、Sentinel One 绕过、Elastic Defend、 Sysmon 规避、PPID spoof、Sleep mask、Process Hollowing、Reflective DLL。

### `exploit-chaining`
- **路径**：`/var/minis/skills/exploit-chaining/SKILL.md`（2.4 KB）
- **一句话**：Combine low/medium findings into one high-impact exploit chain, and ampl
- **描述**：Combine low/medium findings into one high-impact exploit chain, and amplify demonstrated impact. Load when you have several small bugs, a "so what?" finding, on "chain", "escalate impact", or building the narrative for a report. Signals: self-XSS + CSRF, open-redirect + OAuth, IDOR + info-leak, SSRF + metadata.

### `exploit-memory-corruption`
- **路径**：`/var/minis/skills/exploit-memory-corruption/SKILL.md`（4.1 KB）
- **一句话**：Turn a memory-corruption bug in a native binary into code execution — st
- **描述**：Turn a memory-corruption bug in a native binary into code execution — stack overflows, format strings, and ROP against modern mitigations. Load when you control input to a compiled program and it crashes or misbehaves: a network daemon, a thick client, a setuid/SUID helper, or extracted firmware. Signals: segfault on long/`%n` input, a crash with control of a register, no source, checksec output, "exploit this binary/service".

### `exploit-poc-development`
- **路径**：`/var/minis/skills/exploit-poc-development/SKILL.md`（2.4 KB）
- **一句话**：Turn a known/1-day vulnerability or a raw bug into a working, reliable P
- **描述**：Turn a known/1-day vulnerability or a raw bug into a working, reliable PoC for an authorized target. Load when a CVE/advisory needs weaponizing, a public PoC needs adapting, or "write an exploit/PoC". Signals: a versioned service with a known CVE, a crash/primitive to develop, searchsploit hits.

### `identifying-anti-debugging-techniques`
- **路径**：`/var/minis/skills/identifying-anti-debugging-techniques/SKILL.md`（3.3 KB）
- **资源**：目录 references / scripts；文件 LICENSE
- **一句话**：恶意软件反调试 / 反分析检测识别与绕过
- **描述**：Identifies and bypasses anti-debugging and anti-analysis checks in malware: PEB flags, debugger-detection APIs, timing checks, and exception tricks, then neutralizes them to continue analysis. Activates for requests to identify anti-debugging, bypass anti-debug checks, or analyze evasion that blocks a debugger.

### `offensive-active-directory`
- **路径**：`/var/minis/skills/offensive-active-directory/SKILL.md`（13.5 KB）
- **资源**：文件 SOURCE.md
- **一句话**：内网 Active Directory 攻击方法论（红队内网）
- **描述**：Active Directory attack methodology for internal network red team engagements. Covers reconnaissance (BloodHound, PowerView, ADExplorer), credential abuse (Kerberoasting, ASREProasting, NTLM relay, LLMNR/NBT-NS poisoning), privilege escalation (ACL abuse, GPO abuse, unconstrained/constrained delegation), lateral movement (Pass-the-Hash, Pass-the-Ticket, Overpass-the-Hash, WMI/WinRM/PsExec), persistence (Golden/Silver/Diamond Tickets, DCSync, DCShadow, AdminSDHolder, Skeleton Key), forest trust attacks, ADCS abuse (ESC1-ESC15), and modern MDI/Defender for Identity evasion. Use when assessing on-prem AD, hybrid AD/Entra ID environments, or ADCS deployments.

### `offensive-anti-forensics`
- **路径**：`/var/minis/skills/offensive-anti-forensics/SKILL.md`（19.0 KB）
- **资源**：文件 SOURCE.md
- **一句话**：反取证 / 痕迹销毁（红队行动侧）
- **描述**：Anti-forensics and evidence destruction techniques for red team operators conducting authorized engagements. Covers log clearing on Windows (wevtutil, Clear-EventLog, ETW provider patching) and Linux (journal truncation, utmp/wtmp binary editing, syslog manipulation), timestamp manipulation via Timestomp and SetMACE to defeat timeline analysis, filesystem-level anti-forensics including NTFS Alternate Data Streams for payload hiding and secure deletion with sdelete/shred, memory artifact removal to counter live forensics, disk artifact manipulation targeting MFT entries and USN journal records, network forensics evasion through encrypted C2 channels and DNS-over-HTTPS tunneling, and anti-VM/sandbox detection to avoid dynamic analysis environments. Tools: Timestomp, wevtutil, sdelete, shred, MimiPenguin, Invoke-Phant0m. Aligns to MITRE ATT&CK T1070 (Indicator Removal), T1027 (Obfuscated Files or Information), T1497 (Virtualization/Sandbox Evasion). Each technique includes the forensic artifact it targets, the destruction or manipulation method, and the defender perspective so operators understand detection gaps they must account for.

### `offensive-c2-frameworks`
- **路径**：`/var/minis/skills/offensive-c2-frameworks/SKILL.md`（21.8 KB）
- **资源**：文件 SOURCE.md
- **一句话**：C2 框架部署 / 配置 / 运营（红队基础设施）
- **描述**：Command and Control framework deployment, configuration, and operational tradecraft for red team engagements. Covers Cobalt Strike (malleable C2 profiles, Beacon types HTTP/HTTPS/DNS/SMB, Beacon Object Files for in-memory execution, sleep and jitter tuning, named pipe pivoting), Sliver (implant generation across mTLS/WireGuard/DNS transport, operator multiplayer mode, armory extensions), Mythic (agent ecosystem with Apollo/Poseidon/Medusa, C2 profile configuration, translation containers), Havoc (Demon agent with sleep obfuscation via Ekko/Zilean, indirect syscalls, dotnet inline execution), Metasploit (msfvenom payload generation, multi/handler staging, Meterpreter post-exploitation modules), redirector architecture using Apache mod_rewrite and Nginx, domain fronting through CDN providers, DNS-based C2 for restrictive network egress, and TLS certificate management for infrastructure OPSEC. Tools: Cobalt Strike, Sliver, Mythic, Havoc, Metasploit Framework. Aligns to MITRE ATT&CK T1071 (Application Layer Protocol), T1573 (Encrypted Channel), T1090 (Proxy/Connection Proxy).

### `offensive-edr-evasion`
- **路径**：`/var/minis/skills/offensive-edr-evasion/SKILL.md`（82.9 KB）
- **资源**：文件 SOURCE.md
- **一句话**：EDR 绕过清单：unhooking / 直接 syscall / AMSI / ETW / 注入变体
- **描述**：EDR evasion offensive checklist: hook unhooking (user/kernel), direct syscalls, PPID spoofing, process injection variants, AMSI bypass, ETW patching, memory encryption, and behavior-based evasion. Use when planning EDR bypass during red team engagements or researching AV/EDR evasion techniques. Trigger phrases: EDR evasion, EDR bypass, hook unhooking, direct syscalls, PPID spoofing, process injection, AMSI bypass, ETW patch, memory encryption, AV evasion, behavioral evasion, red team evasion.

### `offensive-exploit-development`
- **路径**：`/var/minis/skills/offensive-exploit-development/SKILL.md`（33.5 KB）
- **资源**：文件 SOURCE.md
- **一句话**：漏洞利用开发：环境 / pwntools / pwndbg / 堆利用 / 可靠性
- **描述**：Exploit development operational guide: environment setup, debugging workflow, PoC development lifecycle, writing reliable exploits, using pwntools/pwndbg, heap exploitation techniques, and weaponization considerations. Use when actively developing exploits or setting up an exploit dev environment. Trigger phrases: exploit development, pwntools, pwndbg, heap exploitation, PoC development, exploit reliability, weaponization, debugging workflow, exploit dev environment.

### `offensive-shellcode`
- **路径**：`/var/minis/skills/offensive-shellcode/SKILL.md`（18.4 KB）
- **资源**：文件 SOURCE.md
- **一句话**：Shellcode 开发参考（编码器 / 加载器 / 限制绕行）
- **描述**：Shellcode development reference for offensive security engagements. Use when writing custom x86/x64 shellcode, implementing position-independent code (PIC), building shellcode loaders, evading AV/EDR detection, or converting PE files to shellcode. Covers null byte avoidance, API hashing, encoder/decoder patterns, staged vs stageless payloads, Windows PEB traversal, and cross-platform shellcode techniques.

### `payloads-file-transfers`
- **路径**：`/var/minis/skills/payloads-file-transfers/SKILL.md`（3.8 KB）
- **一句话**：Move files on/off a target when there's no shared drive — upload tools (
- **描述**：Move files on/off a target when there's no shared drive — upload tools (linpeas, nc, exploits), pull loot back, and do it through a pivot or when wget/curl are missing. Load when you need to get a file to or from an authorized host. Signals: "transfer a file", "upload linpeas", "no wget/curl", "get the file off the box", certutil/bitsadmin/impacket-smbserver, exfil over a tunnel.

### `payloads-reverse-shells`
- **路径**：`/var/minis/skills/payloads-reverse-shells/SKILL.md`（4.8 KB）
- **一句话**：Get a reliable reverse (or bind) shell and upgrade it to a real interact
- **描述**：Get a reliable reverse (or bind) shell and upgrade it to a real interactive TTY. Load the moment you have code execution and need a shell back — RCE confirmed, a command-injection sink, an upload that runs, a webshell, a cron/service you control. Signals: "reverse shell", "get a shell", "nc listener", "shell is dumb / no tab completion", "which payload", stabilize/upgrade a shell.

### `payloads-waf-bypass`
- **路径**：`/var/minis/skills/payloads-waf-bypass/SKILL.md`（2.5 KB）
- **资源**：目录 reference
- **一句话**：Bypass WAFs/filters blocking your payloads. Load when a payload that sho
- **描述**：Bypass WAFs/filters blocking your payloads. Load when a payload that should work is blocked, you see 403/406/429 or "request blocked", Cloudflare/Akamai/Imperva/AWS-WAF/ModSecurity, or a filter strips keywords. Signals: works locally but blocked on target, generic block pages.

### `payloads-xss-polyglots`
- **路径**：`/var/minis/skills/payloads-xss-polyglots/SKILL.md`（2.0 KB）
- **一句话**：Context-breaking XSS polyglots and per-context payloads that fire across
- **描述**：Context-breaking XSS polyglots and per-context payloads that fire across HTML/attribute/JS/ URL sinks in one shot. Load when confirming XSS fast, unsure of the injection context, or a single test payload should cover many contexts. Signals: reflected input, XSS triage, "polyglot".

### `pwn-chain`
- **路径**：`/var/minis/skills/pwn-chain/SKILL.md`（9.3 KB）
- **资源**：目录 references；文件 SOURCE.md
- **一句话**：从逆向到可用利用（Working Exploit）的全链路工程化方法
- **描述**：从逆向走到可用利用 (Working Exploit) 的全链路工程化方法。 适用场景：拿到了二进制 + 漏洞点 + 目标环境，需要写出一个能稳定打通的 exploit（不是只能本地复现一下、远程一打就崩的脚本）。 覆盖三大方向：栈溢出 / 堆利用 / 内核 pwn。强调"CTF 本地通 → 真实远程稳定打通"的工程差距：libc 版本错配、堆喷射时序、SMEP/SMAP/KASLR、栈对齐、远程缓冲。 核心工具链：pwntools + GEF/pwndbg + ROPgadget/Ropper + one_gadget + libc-database + qemu-system 内核调试。 触发关键词：pwn、栈溢出、堆溢出、ROP、ret2libc、ret2csu、one_gadget、libc-database、堆利用、tcache、fastbin、unsorted bin、kernel pwn、kROP、SMEP、SMAP、KASLR、modprobe_path、pwntools、GEF、pwndbg。

### `shellcode-stub`
- **路径**：`/var/minis/skills/shellcode-stub/SKILL.md`（3.8 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：裸 shellcode → 可运行 native PoC 的包装器
- **描述**：CONSTRUCT: wrap a raw shellcode blob into a runnable native PoC — a tiny C loader compiled with clang, whose exit code is the shellcode's return value. --os picks the loader: posix (mmap RW → memcpy → mprotect RX → call, default) or windows (VirtualAlloc RWX → memcpy → call → ExitProcess). --emit c dumps just the loader source. The last link in the write chain: asm-assemble → shellcode-stub → exec-observe (native) or qiling-emulate (cross-arch/cross-OS). Builds the exe; does NOT run it.

### `SKILL: Exploit Development`
- **路径**：`/var/minis/skills/SKILL: Exploit Development/SKILL.md`（20.1 KB）
- **一句话**：Full exploit development course roadmap and syllabus: weekly topics, rec
- **描述**：Full exploit development course roadmap and syllabus: weekly topics, recommended reading, lab setup, and learning path from vulnerability classes through advanced exploitation. Use to structure exploit dev training or onboard new researchers. Trigger phrases: exploit development course, exploit dev curriculum, learning path, syllabus, exploit dev training, vulnerability research training, course overview.

### `SKILL: Modern Kernel Exploit Mitigations`
- **路径**：`/var/minis/skills/SKILL: Modern Kernel Exploit Mitigations/SKILL.md`（57.9 KB）
- **一句话**：Security mitigation reference and bypass catalog: ASLR, DEP/NX, RELRO, s
- **描述**：Security mitigation reference and bypass catalog: ASLR, DEP/NX, RELRO, stack canaries, CFI, sandboxing, seccomp. Covers both detection of enabled mitigations and known bypass techniques. Use when assessing target hardening or planning exploit mitigation bypasses. Trigger phrases: mitigations, ASLR bypass, DEP bypass, NX bypass, RELRO, stack canary bypass, CFI bypass, sandbox bypass, seccomp bypass, mitigation detection, checksec.

### `SKILL: Week 1: Vulnerability Classes with Real-World Examples`
- **路径**：`/var/minis/skills/SKILL: Week 1: Vulnerability Classes with Real-World Examples/SKILL.md`（94.8 KB）
- **一句话**：Exploit development curriculum covering core vulnerability classes with 
- **描述**：Exploit development curriculum covering core vulnerability classes with real-world CVE case studies: stack/heap buffer overflows, use-after-free, integer overflows, format strings, type confusion, and race conditions. Use when learning or teaching vuln classes, researching specific CVE patterns, or building exploit dev knowledge. Trigger phrases: vulnerability classes, buffer overflow, use-after-free, UAF, heap overflow, stack overflow, type confusion, integer overflow, format string, memory corruption, CVE case study, exploit development, Day 1-7.

### `SKILL: Week 4: Crash Analysis and Exploitability Assessment`
- **路径**：`/var/minis/skills/SKILL: Week 4: Crash Analysis and Exploitability Assessment/SKILL.md`（400.1 KB）
- **一句话**：Week 4 exploit development curriculum. Crash triage and analysis methodo
- **描述**：Week 4 exploit development curriculum. Crash triage and analysis methodology: WinDbg/GDB analysis, ASAN/MSAN output interpretation, exploitability assessment, register/stack trace reading, root cause identification. Use when analyzing crash dumps, assessing exploitability, or understanding fuzzer-generated crashes. Trigger phrases: crash analysis, crash triage, WinDbg, GDB, ASAN, MSAN, exploitability, stack trace, register dump, segfault, null deref, access violation, week 4.

### `SKILL: Week 5: Basic Exploitation (Linux with Mitigations Disabled)`
- **路径**：`/var/minis/skills/SKILL: Week 5: Basic Exploitation (Linux with Mitigations Disabled)/SKILL.md`（346.5 KB）
- **一句话**：Week 5 exploit development curriculum. Foundational exploitation techniq
- **描述**：Week 5 exploit development curriculum. Foundational exploitation techniques: controlling EIP/RIP, ROP chain construction, ret2libc, shellcode injection, heap spraying, bypass techniques for ASLR/NX/stack canaries. Use when building initial PoCs or understanding classic exploitation primitives. Trigger phrases: basic exploitation, EIP control, RIP control, ROP chain, ret2libc, shellcode injection, heap spray, ASLR bypass, NX bypass, stack canary bypass, week 5.

## 🚩 CTF 竞赛（5）

### `ctf-forensics`
- **路径**：`/var/minis/skills/ctf-forensics/SKILL.md`（35.8 KB）
- **资源**：文件 3d-printing.md / SOURCE.md / disk-advanced.md / disk-and-memory.md / disk-recovery.md / linux-forensics.md / network-advanced.md / network.md…
- **一句话**：CTF 数字取证与信号分析
- **描述**：Provides digital forensics and signal analysis techniques for CTF challenges. Use when analyzing disk images, memory dumps, event logs, network captures, cryptocurrency transactions, steganography, PDF analysis, Windows registry, Volatility, PCAP, Docker images, coredumps, side-channel power traces, DTMF audio spectrograms, packet timing analysis, CD audio disc images, or recovering deleted files and credentials.

### `ctf-malware`
- **路径**：`/var/minis/skills/ctf-malware/SKILL.md`（8.2 KB）
- **资源**：文件 SOURCE.md / c2-and-protocols.md / pe-and-dotnet.md / scripts-and-obfuscation.md
- **一句话**：CTF 恶意代码与网络流量分析
- **描述**：Provides malware analysis and network traffic techniques for CTF challenges. Use when analyzing obfuscated scripts, malicious packages, custom crypto protocols, C2 traffic, PE/.NET binaries, RC4/AES encrypted communications, YARA rules, shellcode analysis, memory forensics for malware (Volatility malfind, process injection detection), anti-analysis techniques (VM/sandbox detection, timing evasion, API hashing, process injection, environment checks), or extracting malware configurations and indicators of compromise.

### `ctf-pwn`
- **路径**：`/var/minis/skills/ctf-pwn/SKILL.md`（19.0 KB）
- **资源**：目录 scripts；文件 SOURCE.md / advanced-exploits-2.md / advanced-exploits-3.md / advanced-exploits-4.md / advanced-exploits-5.md / advanced-exploits.md / advanced.md / field-notes.md…
- **一句话**：CTF 二进制利用：溢出 / 格式化 / 堆 / ROP / 内核 / 沙箱逃逸
- **描述**：Provides binary exploitation techniques for CTF challenges. Use when you already have a vulnerable native target or service and need to turn memory corruption or low-level primitives into code execution or privilege escalation, such as buffer overflows, format strings, heap bugs, ROP, ret2libc, shellcode, kernel exploitation, seccomp bypass, sandbox escape, or Windows/Linux exploit chains. Do not use it when the main blocker is understanding what the binary does; use reverse engineering first. Do not use it for pure web bugs, disk or packet forensics, or standalone crypto/math challenges.

### `ctf-reverse`
- **路径**：`/var/minis/skills/ctf-reverse/SKILL.md`（13.0 KB）
- **资源**：文件 SOURCE.md / anti-analysis-ctf.md / anti-analysis.md / field-notes.md / languages-compiled.md / languages-platforms.md / languages.md / patterns-ctf-2.md…
- **一句话**：CTF 逆向解题技术
- **描述**：Provides reverse engineering techniques for CTF challenges. Use when the main job is to understand how a compiled, obfuscated, packed, or virtualized target works before exploiting or solving it, including binaries, APKs, WASM, firmware, custom VMs, bytecode, game clients, malware-like loaders, and anti-debug or anti-analysis logic. Do not use it when the vulnerability is already understood and the remaining task is exploitation; use pwn instead. Do not use it for pure web workflows, log or disk forensics, or standalone crypto problems unless reversing the implementation is the real blocker.

### `xiaoliu-pojia`
- **路径**：`/var/minis/skills/xiaoliu-pojia/SKILL.md`（1.1 KB）
- **资源**：文件 .gitignore / README.md / ask.py / check.py / ctf-sandbox.md / deploy.py
- **一句话**：小liu破甲 v2 —— 针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破甲提示词与一键部署工具（deploy.py
- **描述**：小liu破甲 v2 —— 针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破甲提示词与一键部署工具（deploy.py / ask.py / check.py）。融合 MDX-Tom v42、codex-keysmith、CTF SANDBOX 三大方法论。当需要 Codex CLI 破甲部署、撤销、状态检查或直连 API 调用时使用。

## 🌐 Web · 协议（1）

### `sci-skill`
- **路径**：`/var/minis/skills/sci-skill/SKILL.md`（21.7 KB）
- **资源**：目录 agents / assets / references / schemas / scripts / templates / workflows；文件 LOCAL-CHANGES.md / README.md / SCI-Skills-promo-v4.png / local_apply_auto_trigger.py / manifest.yaml
- **一句话**：A beginner-friendly, stage-gated research and SCI paper collaboration sk
- **描述**：A beginner-friendly, stage-gated research and SCI paper collaboration skill called SCI保姆. AUTO-TRIGGER by user intent, no keyword needed — use this skill whenever the user's task, topic, or intent is research or paper related. Chinese cues 论文, 科研, 文献, 开题, 综述, 投稿, 审稿, 返修, 润色, 翻译, 实验, 数据, 统计, 图表, 汇报, 答辩, SCI, SSCI, 期刊. English cues topic selection, paper planning, literature search or deep reading, experiments, data sufficiency, collection or acquisition, data cleaning and analysis, statistics, manuscript or thesis writing, academic polishing or translation, scientific-figure planning, Python/R result plots, algorithm or workflow diagrams, reference-figure adaptation, academic presentations or PPT, pre-submission review, Data Availability, journal submission, or reviewer responses; also activate when the user shares a draft, dataset, figure, result, or reviewer letter. Do not activate for unrelated tasks. Nicknames "宝宝巴士" and 山海 still work as explicit invocations. Acquire web data only when none exists or audited data is critically insufficient; prefer downloads, APIs, licensed data, or authorized exports and crawl only as a documented last resort. Never render an experimental result figure without real data or verified result files, Python/R source, and verified execution; propose explanatory or enhancement figures at a manuscript location and obtain user approval before rendering.

## 🔌 固件 · IoT（2）

### `firmware-bringup`
- **路径**：`/var/minis/skills/firmware-bringup/SKILL.md`（5.8 KB）
- **资源**：文件 SOURCE.md
- **一句话**：固件 bring-up：从黑盒二进制到可执行仿真（ripcord）
- **描述**：Bring up a firmware target in ripcord from opaque binary to an execution-verified hardware-boundary (MMIO) transcript. Use when the user wants to emulate a firmware target, capture how the MCU drives a peripheral or opaque device (FPGA/ASIC), reverse-engineer a hardware protocol, triage why a firmware image won't boot in Renode, or reproduce/extend the FNIRSI scope bring-up. Chains identify → pipeline → boot-triage → decompose → function-level emulation → reconcile.

### `firmware-pentest`
- **路径**：`/var/minis/skills/firmware-pentest/SKILL.md`（12.2 KB）
- **资源**：目录 references；文件 SOURCE.md
- **一句话**：固件 / IoT 渗透链：逆向→提取→模拟→利用（OWASP 方法论）
- **描述**：固件 / IoT 渗透链。从拿到一坨 .bin / .img 开始，闭环走完逆向 → 提取 → 模拟 → 利用。 方法论遵循 OWASP FSTM 九阶段；工具链以 binwalk v3、unblob、EMBA、Firmadyne、AFL++ 为主。 适用场景：路由器/摄像头/智能家居固件审计、固件升级包逆向、IoT CVE 复现、嵌入式 0day 挖掘。 触发关键词：固件、firmware、IoT、binwalk、unblob、UART、JTAG、squashfs、UBI、JFFS2、Firmadyne、QEMU 全系统仿真、EMBA、固件渗透、路由器固件、嵌入式漏洞利用、bootloader、NVRAM、FAT、firmware analysis toolkit。

## 🔀 差分 · 变体分析（4）

### `bindiff`
- **路径**：`/var/minis/skills/bindiff/SKILL.md`（5.2 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Google BinDiff 函数匹配（跨版本对比）
- **描述**：Match functions across two builds of a binary with Google BinDiff: per-function similarity and confidence, renamed or moved functions, and functions added or removed. Use for patch diffing (what did this update actually change?), porting symbols from a named build onto a stripped one, malware variant comparison, and finding a known function again after a recompile moved every address. Complements intellidiff, which compares bytes and text rather than structure. Static — disassembles and matches, never executes either binary.

### `diaphora-diff`
- **路径**：`/var/minis/skills/diaphora-diff/SKILL.md`（7.8 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：Diaphora 函数匹配 / 伪代码恢复（开源的 BinDiff 替代）
- **描述**：Match functions between two builds of a program with Diaphora, recover symbol names from a build that has them onto stripped builds, and emit per-function pseudocode diffs documenting what changed. Use for version lineage archaeology, renaming stripped binaries from an unstripped sibling, and reconstructing undocumented source changes between releases. Export needs IDA; diffing and reporting are pure Python. Static — analyses and matches, never runs the targets.

### `intellidiff`
- **路径**：`/var/minis/skills/intellidiff/SKILL.md`（2.5 KB）
- **资源**：目录 scripts；文件 SOURCE.md
- **一句话**：精确 / 规范化文件对比、二进制 diff
- **描述**：Compare files exactly or with deliberate text normalization, compare directory trees, find duplicate files, calculate SHA-256 and CRC32 identities, and read bounded line ranges. Use for change analysis, duplicate/orphan discovery, checksum verification, or focused source inspection. Pure-stdlib and read-only; never executes input or follows symlinks.

### `variant-analysis`
- **路径**：`/var/minis/skills/variant-analysis/SKILL.md`（3.8 KB）
- **资源**：目录 agents / assets / references / resources；文件 SOURCE.md
- **一句话**：变体猎杀：已找到一个漏洞后，找它的所有同类
- **描述**：Hunts for the other instances of a bug already found — the variants of one root cause across a codebase. Use immediately after a vulnerability, logic bug, or bad pattern turns up in a specific file and the question becomes where else it occurs, including the bare conversational form ("are there others like this?", "is this the same bug?"). Also for generalizing one known instance into a CodeQL or Semgrep query for its whole pattern family, and for triaging a set of look-alike candidates against a known root cause. Not for initial discovery with no bug in hand.

## 🎮 游戏逆向（1）

### `reverse-skill`
- **路径**：`/var/minis/skills/reverse-skill/SKILL.md`（2.6 KB）
- **资源**：目录 .github / CTF-Sandbox-Orchestrator / burp-mcp-full / docs / examples / kali / plugins / reports…；文件 .gitattributes / .gitignore / AGENTS.md / CHANGELOG.md / CLAUDE.md / LICENSE / README-kali.md / README.md…
- **一句话**：逆向/渗透/安全任务总路由包——zhaoxuya520/reverse-skill 完整仓库已装于本机 /var/minis/skills/re
- **描述**：逆向/渗透/安全任务总路由包——zhaoxuya520/reverse-skill 完整仓库已装于本机 /var/minis/skills/reverse-skill/（599 文件）。任务涉及逆向工程、二进制/固件/移动端分析、脱壳、恶意代码、漏洞挖掘与利用、CTF、协议逆向、JS 前端逆向、EDR 绕过、游戏逆向、渗透测试时先走它。热路径：读 RULES.md → bash skills/scripts/master-route.sh --hint "<任务>" 选 PRIMARY → bash skills/scripts/case-init.sh 建授权闸门 → 读 skills/<PRIMARY>/SKILL.md 执行。

## 🆕 其他（4）

### `dsh`
- **路径**：`/var/minis/skills/dsh/SKILL.md`（1.6 KB）
- **资源**：目录 astrbot_plugin_pojia / unrestricted-executor；文件 .gitignore / AGENTS.md / LICENSE / README.md / install.ps1 / install.sh
- **一句话**：dsh 破限者 —— 为 DeepSeek Harness（dsh）打造的「解除限制执行器」技能包，适配 deepseek-v4-flash（7
- **描述**：dsh 破限者 —— 为 DeepSeek Harness（dsh）打造的「解除限制执行器」技能包，适配 deepseek-v4-flash（7013）与 deepseek-v4-pro（8013）。含常驻自动层（~/.dsh/AGENTS.md 注入）与按需技能层 unrestricted-executor（flash 精简档 / pro 完整档），另附 AstrBot 插件版。当需要为 DSH 解除限制、取用其执行器规则文件，或部署相关技能包时使用。

### `dsh-pojia-mode`
- **路径**：`/var/minis/skills/dsh-pojia-mode/SKILL.md`（1.3 KB）
- **资源**：目录 .github / assets；文件 .gitattributes / .gitignore / LICENSE / README.md / SHA256SUMS.txt / build.ps1 / preview-mode-picker.png / unlock-dsh-silent.vbs…
- **一句话**：DSH（DeepSeek Harness）「破甲模式」安装器 v1.0（Windows / PowerShell）：双击即装、不改 DSH 代码
- **描述**：DSH（DeepSeek Harness）「破甲模式」安装器 v1.0（Windows / PowerShell）：双击即装、不改 DSH 代码、改前自动备份、可一键卸载、零依赖。当需要给 DSH 增加破甲模式、解锁受限的模式选择器、或安装/卸载该补丁时使用。

### `kimi-break`
- **路径**：`/var/minis/skills/kimi-break/SKILL.md`（1014 B）
- **资源**：文件 LICENSE / README.md / SYSTEM.md
- **一句话**：kimi-break —— 针对 Kimi Code CLI Agent 的红队系统提示词（SYSTEM.md，完整 drop-in 替换版，人
- **描述**：kimi-break —— 针对 Kimi Code CLI Agent 的红队系统提示词（SYSTEM.md，完整 drop-in 替换版，人格绑定 VANTA/WREN），用于 AI 安全研究与红队评估。当需要 Kimi Code 的破甲/越狱提示词、或研究其提示工程结构时使用。

### `minis-400-guard`
- **路径**：`/var/minis/skills/minis-400-guard/SKILL.md`（10.0 KB）
- **一句话**：Minis 会话 400 错误的预防、检测与自愈（两类：A=tool_calls 粘死 / B=上下文超限）。当用户或会话提到「400」「too
- **描述**：Minis 会话 400 错误的预防、检测与自愈（两类：A=tool_calls 粘死 / B=上下文超限）。当用户或会话提到「400」「tool_calls 报错」「insufficient tool messages」「maximum context length」「上下文超限」「对话卡死/发消息没反应」「那个会话不回了」「压缩对话」「修复400」「400又出现了」，或需要巡检此类问题时触发。Use for any Minis session 400 or stuck-chat issue (tool_calls / context overflow), or when asked to prevent/detect/fix them.
