#!/usr/bin/env python3
"""把 SCI-skill 改为「意图自动触发」版本（幂等，可重复运行）。

背景：上游 DT-wanf/SCI-Skills 默认要求口令触发（“宝宝巴士”/“山海”）。
本地改为：用户只要在做科研/论文相关的事，就自动激活，无需口令。
详见 LOCAL-CHANGES.md。上游更新覆盖本文件后，运行本脚本即可重放。

用法: python3 local_apply_auto_trigger.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
skill = ROOT / "SKILL.md"
text = skill.read_text(encoding="utf-8")

NEW_DESC = (
    "description: A beginner-friendly, stage-gated research and SCI paper collaboration skill called SCI保姆. "
    "AUTO-TRIGGER by user intent, no keyword needed — use this skill whenever the user's task, topic, or intent is research or paper related. "
    "Chinese cues 论文, 科研, 文献, 开题, 综述, 投稿, 审稿, 返修, 润色, 翻译, 实验, 数据, 统计, 图表, 汇报, 答辩, SCI, SSCI, 期刊. "
    "English cues topic selection, paper planning, literature search or deep reading, experiments, data sufficiency, collection or acquisition, "
    "data cleaning and analysis, statistics, manuscript or thesis writing, academic polishing or translation, scientific-figure planning, "
    "Python/R result plots, algorithm or workflow diagrams, reference-figure adaptation, academic presentations or PPT, pre-submission review, "
    "Data Availability, journal submission, or reviewer responses; also activate when the user shares a draft, dataset, figure, result, or reviewer letter. "
    "Do not activate for unrelated tasks. Nicknames \"宝宝巴士\" and 山海 still work as explicit invocations. "
    "Acquire web data only when none exists or audited data is critically insufficient; prefer downloads, APIs, licensed data, or authorized exports and crawl only as a documented last resort. "
    "Never render an experimental result figure without real data or verified result files, Python/R source, and verified execution; "
    "propose explanatory or enhancement figures at a manuscript location and obtain user approval before rendering."
)

ANCHOR = ("Use **SCI保姆** as the product name and **宝宝巴士** as the primary nickname. "
          "Treat **山海** as an equally valid legacy invocation name.\n")

ACTIVATION = (
    "\n**Activation is intent-based and automatic — never require a keyword.** Activate this skill whenever the user's task, "
    "topic, or intent is research- or paper-related, in any wording and any language, including but not limited to: topic selection, "
    "paper planning, literature search or deep reading, experiments, data sufficiency, data collection or acquisition, "
    "data cleaning and analysis, statistics, manuscript or thesis writing, academic polishing or translation, scientific figures or plots, "
    "algorithm or workflow diagrams, reference-figure adaptation, academic presentations or PPT, pre-submission review, Data Availability, "
    "journal submission, or reviewer responses; mentions of 论文 / 科研 / 文献 / 投稿 / 审稿 / 润色 / 实验 / 数据 / SCI / SSCI / 期刊; "
    "or the user sharing a draft, dataset, figure, result, or reviewer letter. Do not activate for unrelated tasks. "
    "The nicknames **宝宝巴士** and **山海** remain valid explicit invocations.\n"
)

changed = []

# --- 改动 1：frontmatter description ---
front = text.split("---", 2)[1] if text.startswith("---\n") else ""
if "AUTO-TRIGGER" not in front:
    if not re.search(r"^description: .*$", text, flags=re.M):
        sys.exit("ERROR: description 行未找到，请检查 SKILL.md 结构")
    text = re.sub(r"^description: .*$", NEW_DESC, text, count=1, flags=re.M)
    changed.append("description")
else:
    print("description 已是 AUTO-TRIGGER 版本，跳过")

# --- 改动 2：Identity 段自动激活规则 ---
if "Activation is intent-based and automatic" not in text:
    if ANCHOR not in text:
        sys.exit("ERROR: Identity 锚点未找到，请检查 SKILL.md 结构")
    text = text.replace(ANCHOR, ANCHOR + ACTIVATION, 1)
    changed.append("Identity 自动激活段")
else:
    print("Identity 段已含自动激活规则，跳过")

if changed:
    skill.write_text(text, encoding="utf-8")
    print("已重放本地修改:", ", ".join(changed))
else:
    print("无需修改（已是自动触发版本）")

# 自检：跑官方校验
import subprocess
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py")],
                   capture_output=True, text=True)
print("--- validate_skill.py ---")
print(r.stdout.strip() or r.stderr.strip())
sys.exit(r.returncode)
