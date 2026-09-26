---
name: file-ops
description: 文件批处理技能：批量重命名/归类/查找/去重/打包/替换文本，工作目录在 app workspace 或 /sdcard。当用户说"整理文件/批量改名/找文件/压缩"时使用。
---

# 文件批处理（File Ops）

工作目录：引擎 workspace（`files/data/workspace`）或用户指定路径（/sdcard 需存储权限）。

## 一、先侦察再动手

```sh
ls -la <目录> | head -30
find <目录> -type f -name '*.jpg' | head -20
find <目录> -type f -printf '%s %p\n' | sort -rn | head    # 最大的文件
```
批量操作前先 `echo` 预览命令结果（干跑一遍），确认无误再执行。

## 二、常用批处理模板

```sh
# 批量重命名（前缀+序号）
i=1; for f in *.jpg; do mv "$f" "photo_$(printf '%03d' $i).jpg"; i=$((i+1)); done

# 按扩展名归类到子目录
for e in jpg png mp4 pdf; do mkdir -p "$e"; find . -maxdepth 1 -iname "*.$e" -exec mv {} "$e/" \;; done

# 按日期整理（mtime → YYYY-MM 目录）
for f in *; do [ -f "$f" ] || continue; d=$(date -r "$f" +%Y-%m 2>/dev/null || date -d @"$(stat -c %Y "$f")" +%Y-%m); mkdir -p "$d"; mv "$f" "$d/"; done

# 批量查找+替换（先备份）
cp file.txt file.txt.bak && sed -i 's/旧文本/新文本/g' file.txt

# 去重（按 MD5）
find . -type f -exec md5sum {} + | sort | awk 'seen[$1]++ {print $2}' | head

# 打包/解包
tar czf backup-$(date +%Y%m%d).tar.gz <目录>
tar xzf backup.tar.gz
```

## 三、安全纪律

- 删除类操作：先列出将被删的清单给用户确认；`rm -rf` 前必须双确认。
- 覆盖类操作：先 `.bak` 备份。
- 大量小文件操作注意耐心：用 nohup 后台+日志，别阻塞对话。

## 四、交付

对用户输出：改动清单（多少文件、目标目录）、抽查示例、回滚方法。
