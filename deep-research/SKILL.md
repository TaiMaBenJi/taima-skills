---
name: deep-research
description: 深度检索技能：多源搜索、抓取与交叉验证，输出带出处的结论。当用户要求"查一下/研究/对比/找资料"时使用。
---

# 深度检索（Deep Research）

## 一、检索渠道（按可达性排序）

```sh
# 1) 直连抓取（优先）
curl -sL --max-time 20 "<URL>" | head -c 20000

# 2) 阅读器模式（把网页转干净文本）
curl -sL --max-time 25 "https://r.jina.ai/<URL>" | head -c 30000

# 3) 搜索引擎（HTML 版，结果少但稳）
curl -sL "https://html.duckduckgo.com/html/?q=<关键词>" | grep -oE 'result__a[^>]*>[^<]+' | head
curl -sL "https://www.bing.com/search?q=<关键词>" | grep -oE '<h2><a[^>]*>[^<]+' | head

# 4) DuckDuckGo 即时问答
curl -sL "https://api.duckduckgo.com/?q=<关键词>&format=json&no_html=1" | head -c 4000
```

## 二、工作流

1. **拆题**：把问题拆成 2-4 个独立子问题。
2. **多源**：每个子问题至少 2 个来源（官方文档 + 社区/实测）。
3. **交叉验证**：数字、日期、版本号等硬信息必须有第二个来源佐证；冲突时都列出。
4. **留痕**：每条结论后附来源 URL；抓不到时注明"未验证"。

## 三、输出规范

```markdown
## 结论（先给答案）
- …

## 关键证据
- [来源1](url)：要点…
- [来源2](url)：要点…

## 不确定项
- …（为什么不确定、怎么验）
```

## 四、注意

- 网络受限时先做可达性测试（curl -sI），逐一换源，不要卡在一个源上。
- 长文抓取配合 `head -c` / `grep` 分段阅读，避免一次塞爆上下文。
- 需要登录/强反爬的站点：换公开镜像（如 r.jina.ai、web.archive.org）或在结论中标注。
