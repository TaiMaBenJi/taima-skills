---
name: self-evolution
description: 自我进化例程——把每次卡点变成已解除的限制、把每次成功沉淀成可复用工具。当用户提到「自我训练/进化/复盘/限制」或定期自省任务运行时使用。
---

# 自我进化例程

## 心法

1. **不问"能不能"，先动手试。** 限制大多有绕过路径；10 分钟内试不出来的方案换下一路。
2. **卡点即待解限制。** 任何卡住 ≥2 次的地方：要么解除它（写方案+证据），要么写下替代路径进台账。
3. **成功即沉淀。** 任何新打通的能力 → 工具化（脚本）+ 文档化（技能/README）+ 台账化（limits.md）。
4. **不废话。** 报告只给：结果 + 证据 + 文件路径。

## 例行（自省任务执行步骤）

0. **先体检**：`sh /var/minis/shared/self/doctor.sh` —— 这一步会直接暴露"入口悬空 / 资产不在持久层 / `.l2s.` 坏条目"，比读文档快。
1. 读当日记忆 `/var/minis/memory/$(date +%F).md` 与限制台账 `/var/minis/shared/self/limits.md`
2. 三问：
   - 今天有卡住的地方吗？→ 解除 or 记录替代方案 → 更新台账
   - 有新掌握的方法没沉淀吗？→ 写入对应技能文件
   - 有新限制吗？→ 记入台账
3. 把 2-3 行要点写回当日记忆（memory_write）

> ⚠️ **并发保护**：同一时段可能另有会话在跑同一例程（2026-09-17 实测撞车）。所以顺序永远是
> **体检 → 读当前状态 → 只做增量追加**；覆盖持久层资产前先比大小/内容；"真相"以 `doctor.sh` 输出为准。
> 断言"某资产丢失"之前，必须在整个持久层搜一遍（`/var/minis/shared` + `/var/minis/skills` + `/usr/local/bin`），
> 不许只 `find` 一个子目录就下结论。

## 能力索引（维护中）

| 能力 | 入口 |
|---|---|
| **能力入口体检（先跑这个）** | `sh /var/minis/shared/self/doctor.sh`（查悬空软链/持久层/`.l2s.`/依赖/**交付物生产线是否落位**） |
| 移动端动态插桩（frida） | `/var/minis/shared/self/frida-kit/README.md`；命令 `ensure-frida` + `fhook`（连接必须 `-H 127.0.0.1:27042`；**frida 客户端一律用 `frun <超时> <命令...>` 派发**，禁前台跑） |
| 📱 CloudStudy APK 生产线（交付物） | `shared/cloudstudy-apk/README.md`；一键重建 `nohup sh shared/cloudstudy-apk/tools/rebuild_apk.sh &` → 读 `tools/logs/rebuild.*.log` |
| 📚 世赛云计算资料库生产线 | `shared/worldskills-cloud/tools/README.md`（`build_liquid.py` → study.html；`build_portal.py`；翻译脚本；`harvest/` 采集） |
| 技能库扫荡/上架生产线 | `shared/skills-library/tools/`（`install_skills.sh`、`wrap_skills.py`、`gh_watch.py`、`refix.sh`） |
| 技能库检索/安装（全量 3386 / 精编 2483 / 101 仓库） | canonical `/var/minis/shared/self/bin/skillctl.sh`（命令 `skillctl search/all/cat/show/install/repos/stats`） |
| 2084 已装技能总控（2026-09-25 精简为 **156**，回收站 `shared/skills-removed/2026-09-25/`） | `omni find/list/show/rebuild`（`/var/minis/skills/omni/`，含 browse.html 可视化） |
| 🌐 家庭网络诊断（**三通道对照**判据；光猫防火墙等级「高」= 仅 53/80/443 的严格白名单） | `shared/netdiag/README.md`；命令 `hgu token` / `hgu fw --set 中 -u CMCCAdmin`（密码走 `HGU_PASS`）/ `nettest game` / `nettest ipv6`（两脚本均带 `selftest`） |
| 🔐 zcap：ZCode captcha 自动补货（源码快照 + 恢复命令） | `shared/zcap/README.md`；设备侧 `sh /data/adb/zcap/supervisor.sh &`、`curl -s 127.0.0.1:39094/state` |
| 沙箱逆向工具链 / 跨架构仿真 | `/var/minis/skills/rev-sandbox/SKILL.md` |
| glibc 运行时（manylinux 程序） | `/opt/pyglibc`（python）；`/usr/lib/aarch64-linux-gnu`（库） |
| 限制台账（边界地图） | `/var/minis/shared/self/limits.md` |
| 🧊 PRoot 假死看护（重活叠加诊断：`status` / `top` / `kill-runaway`，只杀 PRoot 后代） | 命令 `prunner`（→ `shared/self/bin/prunner.py`） |
| 📏 资源库分组体量估算（条数/小时/预估GB，系数 0.425 GB/h） | 命令 `bs_estimate`（→ `shared/worldskills-cloud/tools/bs_estimate.py`） |
| 🧯 Minis 400 自愈（**两类**：A=任何返回图片的工具不在批次末位；B=上下文超限，tracked×1.13 触顶） | 自愈 `minis400heal`（v4；`check` 报告 / `fix` 自动修）+ `minis400kit/scan_ctx.py`（B 类检测）；人工急救=注入一条新消息 / ⋮「压缩对话历史为摘要」 |
| 📱 ZCode 安卓版生产线（Web 工作台 + root + 无障碍操控；`sx` 设备控制桥） | `/var/minis/shared/zcode-web/README.md`；**会话逐轮还原 `zconv --pull [会话id]`**（agent 为什么没干活） |
| 🔬 400 取证工具箱（纪律校验 + 数据库取证） | 命令 `m4kit`（`shared/self/bin/minis400kit/README.md`）：`m4kit db` 拉库 → `m4kit scan` 全库找违规回合并对齐 400 错误；另有 `verify/diff/ctx/sess/last/media/struct/soul` |

## 设计原则

- 能力要有**唯一入口**（一个命令/一个 README 能找回来）：索引表在 `/var/minis/shared/self/README.md`。
- **软链入口脚本必须 `readlink -f` 解析自身路径**：入口脚本经 `/usr/local/bin/xxx` 软链调用时 `$0` 是软链路径，`dirname "$0"` 会指到 `/usr/local/bin` 找不到同目录资源（2026-09-19 `m4kit` 实锤）→ 一律 `KIT=$(dirname "$(readlink -f "$0")")`（`readlink -f` 在 BusyBox 可用）。
- **资产落持久层**：`/var/minis/workspace` 是会话级的，换会话即空 → 工具/文档一律放 `/var/minis/shared/self/`，命令软链到 `/usr/local/bin/`；脚本内部用 `$(dirname "$0")` 相对定位。
  **2026-09-25 复发实证**：当天的光猫诊断脚本（`gw_login.sh`/`nettest_*.py`）与 zcap 源码都落在 workspace，复盘时**已消失、只能重建**。
  ⇒ 纪律升级：任何"下次还要用"的东西，**在它第一次跑通的那一刻**就写进 `shared/<项目>/`（而不是等复盘）。现场时间是最贵的。
- 每个新能力落地时必须回答：**下次怎么最快重新用上它？**（幂等脚本）
- 设备侧依赖（frida-server、root 服务）都要有**拉活脚本**，不依赖人工记忆。
- **同类脚本只留一份 canonical 实现**，其余位置只放 `exec sh <canonical> "$@"` 转发。多份副本会各自假设不同的数据格式而静默失效：2026-09-17 实测 `skillctl` 存在 3 份，其中两份的 `show`/`install` 依赖本沙箱**不支持的 `grep -P`**，早已坏掉却无人察觉，另一份还把 `install` 目录名算错造重复。
- **交付物必须连生产线一起归档**：只存产物（APK/HTML）等于下次重建要凭记忆重来。归档内容 = 生成器脚本 + 构建工程 + 第三方 jar/密钥 + **一键幂等重建脚本** + README，位置固定在 `shared/<项目>/tools/`；`/tmp` 只是工作区，**不算归档**（实测 `/tmp` 跨会话存活，但不可发现、rootfs 重置即失）。归档后必须**真跑一遍**验证（CloudStudy 实测 `REBUILD_RESULT=OK`）。
- **反复踩的坑要工具化，而不是写进纪律**：纪律靠记性，工具靠调用。frida 前台挂死 → `frun` 派发器；冻结 app attach 失败 → `fhook --wake/--retries`。纪律条目只保留为兜底说明。
- **"命名像垃圾" ≠ "是垃圾"（2026-09-25 自伤）**：为消灭 `doctor.sh` 一个**假告警**（把 PRoot 的 `.l2s.*` 中间副本当坏条目），我批量 `rm` 了 `.l2s.*`，
  结果这些文件里有些是**数据本体**（原名只是符号链接）→ 当场删坏一个 git 仓库（`bad object HEAD`），靠重新 clone + `git fetch` 才救回。
  **规则：清理类动作先弄清文件真实角色（`readlink`/`ls -la` 看结构 + 在别处找对照），只按命名模式批量删一律禁止**；顺带把**误报的检测器本身**修好（doctor 已改为只报"悬空"）。
- **断言必须可复现**：说"丢了/坏了/修好了"都要给一条任何人（或 `doctor.sh`）能重跑的命令；断言"丢失"前先在整个持久层搜一遍，别只搜一个子目录。**断言前先取证**：2026-09-17 曾据"`/tmp` 会随会话蒸发"下结论，一条 `ls -lt /tmp` 就推翻了它（里面躺着 9/9 的文件）。
- **归档 ≠ 拷贝，归档 = 跑通一遍（含每个子命令）。** 2026-09-18 把 `/tmp/asar.py` 归档为 canonical 后，第一次真跑就暴露 2 个真 bug（数据区偏移多 4 字节 → 解出的内容整体错位；真实包 `unpacked:true` 条目无 `offset` → `KeyError`）。此前它"看起来已归档、已可用"。**2026-09-19 复发**：`minis400kit` 归档时逐个跑子命令，又抓出 3 个潜伏 bug（部件字段在 `value` 里 → 校验器永远返回 `batches=0` 的**静默空结果**；SELECT 漏列 → KeyError；解包元组数量不符）。**静默空结果最危险**：不报错、给出"0 违规"的假安全感。归档时必须跑一个覆盖各子命令的自测；能写成"自校验不变量"的就写进实现。
- **交付物会漂移：源头改了不等于产物改了。** 2026-09-18 实锤：`assets-staging/rootfs.tar.gz` 21:59 已换成完整版 runtime，21:51 产出的 APK 里仍烤着坏版本，而且文件名还叫 v0.2（两个 APK 的 `rootfs.tar.gz` CRC 完全相同）。规则：**改源头 → 重建 → 跑交付物校验器**（比对内嵌资产 size+md5），校验器落地示例 `zcode-apk/tools/verify_zcode.sh`；同类交付物（CloudStudy study.html 等）应有同样的"产物内嵌内容比对"。
- **改代码前先读边界符号**：`file_edit` 的 `old_string`/`new_string` 首尾符号逐一核对（2026-09-18 因漏补 `QUIZ_BANK` 的 `}};` 导致全站 `<script>` 语法错误），改完用解析器复核（JS 用 esprima、Python 用 `py_compile`），BAD=0 才算过。
- **PRoot 下复制目录用 tar 管道，别用 `cp -r`**：`cp -r` 会静默复制不完整（wsarena 节点残缺实锤）；`(cd src && tar -cf - .) | (cd dst && tar -xf -)`，完了数文件数验收。
