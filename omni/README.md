# ⚡ OMNI — 88 合 1 技能总控

把 `/var/minis/skills/` 下全部 88 个技能合成一个「总入口技能」。装好即用：

- **给 AI 用**：任何任务先读 `SKILL.md`（含 88 技能全索引 + 任务→技能路由表），定位后再读子技能全文。
- **给自己用**：`browse.html` 是单文件离线浏览器（直接双击/用浏览器打开，支持全文搜索）；`FULL-BUNDLE.md` 是全部技能正文合集（可 grep）。

## 目录内容

| 文件 | 说明 |
|---|---|
| `SKILL.md` | 主入口（自动生成）：使用纪律 + 路由速查 + 88 技能分类索引 |
| `browse.html` | 单文件浏览器（1 MB，全离线，无外部依赖） |
| `catalog.md` | 技能目录摘要（一句话 + 完整描述 + 路径） |
| `FULL-BUNDLE.md` | 88 个技能全文合集（≈1 MB） |
| `index.json` / `index.tsv` | 机器可读索引 |
| `omni.py` | 命令行工具（`omni list/find/show/path/cat/stats/rebuild`） |
| `build.py` + `_data.py` + `_browse_template.html` + `TEMPLATE.md` | 生成器与数据源（分类/简介在此维护） |

## 命令行

```sh
omni list                  # 全部技能（按分类）
omni list android          # 关键词过滤
omni find frida tls        # 多关键词搜索（名称/简介/全文）
omni show rev-sandbox      # 打印技能全文
omni path src-hunter       # 打印技能目录
omni stats                 # 统计
omni rebuild               # 重建全部索引产物
```

## 安装到其他 Minis 设备

把本目录整个复制到目标设备的 `/var/minis/skills/omni/`，再建软链：

```sh
ln -sf /var/minis/skills/omni/omni.py /usr/local/bin/omni
python3 /var/minis/skills/omni/build.py   # 若目标机技能集不同，重建索引
```

> 说明：omni 本体只含「索引 + 路由 + 工具」；88 个子技能实体仍在 `skills/` 各自目录里（总计约 112 MB，其中 src-hunter/pojie 两个大合集占 97 MB）。要做整包备份时直接复制整个 `skills/` 目录即可。
