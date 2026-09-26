# 本地修改记录（相对上游 DT-wanf/SCI-Skills）

> 修改日期：2026-09-22
> 目的：用户要求 —— 把技能从「口令触发」改为「**意图自动触发**」：
> 用户不需要喊“宝宝巴士/山海”，只要任务/意图属于科研论文方向就自动激活；无关任务不激活。

## 改动 1 — SKILL.md frontmatter `description`（第 3 行）

- 原：`... Use when users say “宝宝巴士” or “山海”, or need topic selection, ...`
- 现：`... AUTO-TRIGGER by user intent, no keyword needed — use this skill whenever the user's task, topic, or intent is research or paper related.`
- 新增：中文触发词列表（论文/科研/文献/开题/综述/投稿/审稿/返修/润色/翻译/实验/数据/统计/图表/汇报/答辩/SCI/SSCI/期刊）、英文触发场景列表、“无关任务不激活”约束。
- 昵称触发（宝宝巴士/山海）保留为**可选的显式调用**。

## 改动 2 — SKILL.md `## Identity` 段

- 新增独立段落：

  > **Activation is intent-based and automatic — never require a keyword.**
  > （+ 触发条件枚举 + 不激活条件 + 昵称仍为显式调用）

- 原欢迎词与 `Do not repeat the full welcome in every turn.` 保持不变。

## 未改动

- `manifest.yaml`（内部路由，与激活无关）
- `agents/openai.yaml`（已含 `allow_implicit_invocation: true`，方向一致，可不动）
- 欢迎词字面量、模板、工作流（35 阶段）、校验脚本

## 上游升级注意

重新拉取上游后，需按上面两处重放修改；`scripts/validate_skill.py` 不检查这两处文本，改后自检仍应 `VALIDATION PASSED`。
