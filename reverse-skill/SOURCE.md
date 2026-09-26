# SOURCE — reverse-skill

- **仓库**: https://github.com/zhaoxuya520/reverse-skill
- **快照**: main @ `cab634bd855f`（2026-09-22，"fix: scope pwntools version probe environment"）｜ tarball md5 `6747c86c7675833ddf48a9ae6f2d11c9`
- **获取通道**: ghfast.top 镜像（github.com / codeload 直连被墙；ghproxy.net、gh-proxy.com 大文件会中途 RST；raw.githubusercontent.com 抖动可用）
- **安装**: 2026-09-23 → `/var/minis/skills/reverse-skill/`（仓库 599 文件 + 本目录 SKILL.md 入口）
- **brickguard 全量扫描**: 0 critical / 2 high —— 仅 `skills/pentest-tools/src-hunter/references/payloader/raw/{tools,web}.json`（payload 参考语料，纯数据不执行，与 9-13 库内快照逐字节相同）→ 用户裁决：直接装
- **冒烟实测**: `master-route.sh --hint "安卓APK 脱壳与 Frida hook"` → apk-reverse ✓ ｜ `"固件提取与 QEMU 仿真"` → firmware-pentest ✓
- **更新**: 网络直连可用时 `git pull`；否则重下 tarball 覆盖（保留本文件）
