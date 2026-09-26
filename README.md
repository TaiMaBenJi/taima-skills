# 太马奔极 · 技能库（Agent Skills）

> **164 个开箱即用的 Agent 技能**（SKILL.md 指令包）—— 逆向 / 安全 / 安卓 / CTF / 研发全栈。
> 为「太马奔极」/「Minis」等 Agent 应用配套。

技能 = 一份 `SKILL.md`：告诉 Agent「遇到这类任务，按什么流程做、用什么工具、避开哪些坑」。
装上技能库，Agent 从"通用助手"变成"专业工程师"。

## 📚 技能分类（共 164 个）

| 分类 | 数量 | 代表技能 |
|------|------|----------|
| 🛡️ 安全与渗透 | 34+ | XSS / SSRF / XXE / IDOR / 请求走私 / WAF 绕过 / 漏洞利用开发 / OSINT |
| 🔍 逆向工程 | 36 | Android / iOS / Native / JS 逆向 · Frida 全家桶 · Ghidra / IDA · 反编译 · 脱壳 |
| 🤖 AI 安全 | 10+ | 提示注入 · 越狱研究 · MCP 安全 · Agent 工具滥用 |
| 🕹️ CTF 竞赛 | 5+ | pwn / reverse / forensics / malware · 沙箱编排 |
| 📱 安卓 & 移动 | 10+ | 安卓控制 · 静态分析 · 证书固定绕过 · 移动安全套件 |
| 🛠️ 通用 & 研发 | 70+ | 代码运行 · 文件操作 · 深度研究 · 文档写作 · 设备诊断 |

## 🚀 怎么用

**① App 内导入（推荐）**
在「太马奔极」/「Minis」的「技能」页中从本仓库导入。

**② 手动复制**

```bash
git clone https://github.com/TaiMaBenJi/taima-skills.git
cp -r "taima-skills/SKILL: XSS" ~/.minis/skills/      # 或 /var/minis/skills/
```

**③ 批量安装**
在装有「太马奔极」的环境里执行：

```bash
taima-market install-all
```

## ✍️ 写一个新技能

```
my-skill/
└── SKILL.md    # frontmatter（name / description）+ 正文步骤
```

参照仓库内任意技能目录的结构，欢迎 PR 补充。

## ⚖️ 来源与使用

- 部分技能整理自公开社区项目（对应目录内附原始 LICENSE，如 dsh / js-reverse-ops / pojia-next 等）；
- 其余为本仓库整理汇编；
- 仅供**学习研究**与**授权环境下的安全测试**使用，请遵守当地法律法规。
