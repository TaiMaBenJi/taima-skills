---
name: minis-400-guard
description: Minis 会话 400 错误的预防、检测与自愈（两类：A=tool_calls 粘死 / B=上下文超限）。当用户或会话提到「400」「tool_calls 报错」「insufficient tool messages」「maximum context length」「上下文超限」「对话卡死/发消息没反应」「那个会话不回了」「压缩对话」「修复400」「400又出现了」，或需要巡检此类问题时触发。Use for any Minis session 400 or stuck-chat issue (tool_calls / context overflow), or when asked to prevent/detect/fix them.
---

# Minis 400 防护与自愈（minis-400-guard）v2

## 0. 两条流水线（先定类型，再动手）

| | 类型 A：tool_calls 粘死 | 类型 B：上下文超限 |
|---|---|---|
| 报文 | `assistant message with 'tool_calls' must be followed by tool messages` | `maximum context length is N tokens. However, you requested M` |
| 现象 | 会话彻底不回；重启 App 前反复失败 | 发送后 app 重试 `retry 1/3..3/3` 全失败；**对超限会话重启无效** |
| 根因 | 图片类工具结果插入 tool 序列中间（批内多图/不在末位）；失败字节缓存于进程内被重放 | 模型组 `contextLimitTokens` 失效（超大值/null）→ 自动压缩阈值不可达 → 历史涨过服务商硬顶；App 记账比服务商**少算 ≈13%** |
| 修法 | 重启 App（清缓存）+ 续跑注入 | **发一条新消息（续跑）** → App 重建有效上下文（实测 948K→444K）恢复正常；配置侧把组上限改 800000 |
| 验证 | check 显示 OK + 会话有新回合 | check RC=2；会话出现健康 assistant 回复 |

**一键处置**：
```sh
minis400heal check     # 两类全查（A 类 + B-STUCK/B-NOREPLY/B-RISK/CFG）
minis400heal fix       # 自动修（A=预约续跑+必要时重启链；B=预约续跑+配置修复）
```
退出码：`0`=有发现（或已修）/ `2`=全健康 / `1`=错误。**巡检先用 check，有发现再 fix。**

## 1. A 类机制（2026-09-19 破案，保留）
带图工具结果（`read_image`、`browser_use` screenshot、任何产出图片字节的工具）**不在批次末位**或**一批多图** → 图片消息被插进 tool 消息序列中间 → 400。
失败回合的图片字节缓存在 **App 进程内存**里，该会话之后每次请求都会重放 → **不重启 App 进程就永久卡死**。
恢复 = 清缓存（重启 App）+ 注入一条新消息唤醒（`minis400heal fix` 自动做）。
**预防铁律：任何图片类工具每批最多一个、且必须放最后；多图拆多个回合。**

## 2. B 类机制（2026-09-21 反编译实证，V1.13）

### 2.1 阈值模型（类 `m3.c` ContextPolicy，构造函数 `g4.H1.Q(limit)`）
| limit 档 | offloadThreshold | offloadTarget | compactThreshold | exhaustedOnly | manualCompactAllowed |
|---|---|---|---|---|---|
| <32K | 0 | 0 | 0 | true | false |
| 32–64K | limit-10K | limit-15K | 0 | true | true |
| 64–128K | limit-20K | limit-30K | limit-10K | false | true |
| ≥128K | limit-40K | limit-60K | **limit-20K** | false | true |

判定 `a(tracked, limit)` → **OK(0)** / **NEEDS_COMPACT(1)**（tracked ≥ compactThreshold）/ **EXHAUSTED(2)**（仅小窗口可达）。
> 对 ≥64K 窗口：**tracked ≥ limit-20K 即进入 NEEDS_COMPACT**。有效上限 = min(服务商窗口, 组 contextLimitTokens)，由 `V3.a6.Z()` 每次现取（配置改动无需重启，实测同进程内生效）。

### 2.2 发送管线（`V3.a6.B1`）
- tier=OK → 直发；
- tier=NEEDS_COMPACT 且 `autoCompactOnThreshold`=true → 日志 `[Context] pre-send near capacity — auto-compacting (pref on)` → 发送前压缩 → 压缩成功继续发；**压缩失败 → `pre-send compaction failed — sending anyway` → 仍会 400**；
- 中循环另有 `[AutoCompact] mid-loop compact #n`（每回合最多 3 次，仍超 → 停回合）。
- 压缩偏好文件：`shared_prefs/minis_auto_compact_prefs.xml`（`autoCompactOnThreshold`）。

### 2.3 手动通道（用户可操作）
- 会话 ⋮ 菜单 →「**压缩对话历史为摘要**」；
- 接近上限时发送会弹窗：「对话上下文即将占满。发送前可先压缩历史以释放空间。启用自动压缩后，之后将自动完成此操作。」→ 按钮「**压缩并发送**」/「**压缩并启用自动压缩**」；
- 进度文案：「正在压缩… %1$d 秒 · 分段摘要中（%2$d/%3$d）」；
- 兜底提示（EXHAUSTED 档 或压缩失败）：`Start a new chat or /compact to continue reliably.`（提示语提及 `/compact`）。

### 2.4 超限会话的复活（2026-09-21 实战，53ac6199）
时间线：19:20 首次 400（tracked 948K / 实际请求 1.07M > 硬顶 1.048M）→ 用户 20:52/20:56/21:40 三条消息全部无处理 → 21:39 修配置（组上限 2147483647→**800000**）→ 22:24 发一条续跑消息（minis-scheduled follow-up）→ **22:25 成功回复，tracked 重建为 443,838** → 之后连续工作 0 错误，`check` RC=2。
**结论：对 B 类卡死会话，"注入一条新消息"就是修复动作**（触发发送管线重建有效上下文）；不需要重启、不需要手动压缩。仅当注入后仍无响应，才引导用户手动压缩。
（有效上下文重建在 `V3.a6.Y()`，含摘要锚点 walkBack ≤100 条/目标 3 个用户回合、孤儿工具修复、大输出丢弃；无摘要时走全量+剪枝。细节未完全还原，但效果已两次实证。）

## 3. 工具箱与数据通道（canonical，勿重复造轮子）
| 工具 | 作用 |
|---|---|
| `minis400heal`（v4 主入口） | check/fix 两类 400；`--since-hours N` / `--no-restart` |
| `shared/self/bin/minis400kit/scan_ctx.py` | B 类扫描器（B-STUCK / B-NOREPLY / B-RISK / CFG） |
| `shared/self/bin/minis400kit/prefs_sync.sh` | 同步 `provider_config.xml` + 自动压缩偏好 → `/tmp/`（B 类判定用） |
| `shared/self/bin/minis400kit/db_sync.sh` | 同步 `minis.db` → `/tmp/minis.db`（= `m4kit db`） |
| `shared/self/bin/restart_chain.sh` | A 类自动重启链（+N 秒执行，PID 校验+全日志 `/data/local/tmp/minis_restart_probe.log`） |
| `shared/self/bin/minis-conf-probe.py` | 配置体检：解析 provider_config.xml 的 config JSON，只打印安全字段（**绝不打印密钥**），对 `contextLimitTokens ≥ 1e6 / == Integer.MAX_VALUE` 告警。⚠️ 自写解析时别用裸 `token\|key` 过滤字段名——会把 `contextLimitTokens` 吞掉，给出 `WARN=0` 的**假安心** |
| `shared/self/bin/minis-dexstr.py` | classes.dex 字符串 + xref 探针（androguard，免 JDK）：`python3 minis-dexstr.py /tmp/apkx/classes.dex autoCompact 压缩`（大 dex 后台跑） |
| `m4kit` | 取证箱（scan/verify/ctx/last/sess…） |

**设备↔沙箱文件通道（shizuku 实为 root）**：
```sh
# 设备 → 沙箱（从 /data/app、/data/data 等任意处）：
android-shizuku-cli exec 'cp -f <src> /data/data/com.openminis.app/files/minis-global/shared/xfer/<name>; chmod 666 /data/data/com.openminis.app/files/minis-global/shared/xfer/<name>'
# 沙箱侧读： /var/minis/shared/xfer/<name>
```
对应关系：沙箱 `/var/minis/shared` ＝ 设备 `files/minis-global/shared`（同一份，双向即时可见）。root 拷贝的文件默认 600，**必须 chmod 666** 沙箱才能读。常用源：`/data/data/com.openminis.app/{databases/minis.db*,shared_prefs/*.xml,files/logs/*}`、`/data/app/*/base.apk`。

**关键 DB 查询**（`/tmp/minis.db`）：
```sql
-- B 类卡死判据：有 context 400 且其后无健康 assistant
SELECT session_id, max(sort_order) FROM messages
 WHERE error_info LIKE '%context length%' GROUP BY session_id;
-- 各会话当前 tracked：token_usage 里的 latestContextTokens（按 sort_order 最新一条）
```
复压取证模板：`apkx`（Minis dex 反编译源料）在 /tmp（易失）；还原法：拉 APK → `unzip classes.dex` → `jadx --single-class 'V3.a6'`（压缩引擎）、`'m3.c'`（ContextPolicy）、`'m3.b'`（枚举）、`'g4.H1'`（阈值工厂）。
`androguard` 可用（字符串 xref 定位超快）：`AnalyzeDex('/tmp/apkx/classes.dex')[2].get_strings()` + `get_xref_from()`。

## 4. 巡检部署（已生效）
- **3 班/日**：09:37 / 13:37 / 21:37「400自愈巡检」（new session，跑 check→fix→汇报）。
- 用户随时可说「查 400 / 修复 400」→ 手动跑 `minis400heal check`。
- 每次处理完 B 类，确认 `scan_ctx.py` 该会话不再报 B-STUCK（健康回复出现即自动消警）。

## 5. 已知坑（血泪合集）
- `minis-config set`：**永远后台化发射**（`setsid nohup sh -c '... >log 2>&1' &`）；弹确认单需用户点，30s 超时后进程仍可能不返回且**阻塞后续 shell**。命令超时 ≠ 未执行，查 audit / 副作用验证。
- `minis-scheduled run --id`：**会挂起（需 timeout），但实际已生效**（2026-09-21 实测）。create/delete 正常；`list` 极慢，避免。
- `minis-sessions-cli`（本版）：只有 `list/search/messages` —— **没有 send/retry/open**（给会话发消息用 minis-scheduled follow-up）。
- 分析 DB 前先 `m4kit db`；对照 prefs 用 `prefs_sync.sh`。
- 更新 App 版本后 dex 会变（apkx 为 V1.13 快照，重建方法见 §3）。
- A 类重启链会 force-stop App（**会打断所有会话的本轮**）→ 只在 A 类且缓存判据 YES 时武装，并提前告知用户「App 将闪断重启」。

## 6. 验证食谱
```sh
minis400heal check                       # 期望：相关会话从卡死列表消失 / RC=2
# 看会话是否恢复（示例：目标会话出现晚于 400 时刻的健康 assistant 行）
python3 - <<'EOF'
import sqlite3
db=sqlite3.connect('file:/tmp/minis.db?mode=ro',uri=True)
print(db.execute("""SELECT sort_order,role,datetime(created_at/1000,'unixepoch','+8 hours'),
  substr(coalesce(error_info,''),1,60) FROM messages WHERE session_id LIKE '53ac6199%'
  ORDER BY sort_order DESC LIMIT 6""").fetchall())
EOF
```
A 类另可看重启链日志 `CHAIN DONE` + PID 校验行。

## 7. 历史
- 2026-09-19：A 类破案（全库 26/26 交叉验证）+ 纪律固化 + 自愈体系 v1。
- 2026-09-21：B 类破案（ContextPolicy 反编译）+ 实战复活案例 + 检测修复 v2/v4 + 三班巡检。
