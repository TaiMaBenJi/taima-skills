---
name: code-runner
description: 本机代码运行技能：在手机环境里跑 Node/Bash 脚本、写小程序、做数据/文本处理。当任务需要"写个脚本/跑段代码/处理数据"时使用。
---

# 本机跑码（Code Runner）

## 一、可用运行时（先探测）

```sh
which node bash busybox rg 2>/dev/null; node -v; bash --version | head -1
```
- **node**：可用（payload 自带 v24）。
- **bash 5.3**：可用（payload/bin）。
- python：通常无 → 用 node 替代（文本/JSON/批量处理 Node 都够）。

## 二、标准姿势

1. 脚本写到 `workspace/`（持久、可回看）：
   ```sh
   # 用 write_file 工具写 workspace/task.mjs，然后：
   node workspace/task.mjs
   ```
2. 长任务：`nohup node workspace/task.mjs > workspace/task.log 2>&1 &`，稍后读日志。
3. 需要 root 的脚本：`su -c "node /完整路径/task.mjs"`（注意路径要绝对路径）。

## 三、Node 常用片段

```js
// 读目录
import { readdirSync } from 'node:fs';
console.log(readdirSync('/sdcard/Download').slice(0, 50));

// 读 JSON/CSV 简单处理
import { readFileSync } from 'node:fs';
const rows = readFileSync('data.csv', 'utf8').trim().split('\n').slice(1).map(l => l.split(','));

// 发 HTTP（无 curl 时）
const r = await fetch('https://api.example.com/x'); console.log(await r.text());
```

## 四、纪律

- 先跑最小验证（`node -e "console.log(1)"`），再上复杂脚本。
- 脚本报错把 stderr 原文带回来，不要吞错。
- 输出大结果时 `slice/head` 截断，重要结果写入文件给用户路径。
