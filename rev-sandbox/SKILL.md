---
name: rev-sandbox
description: Minis 沙箱逆向环境手册。动手做二进制/固件/移动端/恶意代码分析前先读这个：本沙箱是 Alpine aarch64 + PRoot，哪些工具能用、哪些要跨架构仿真、哪些坑必须绕（TMPDIR、JDK21 JIT 被禁、PRoot 高并发 make 会挂）。含 x86/x64/ARM32/RISC-V 仿真层用法（xrun/xstrace/xpython）、原生 Ghidra headless、r2/llvm/capstone/keystone/pwntools/unicorn 全链路命令模板。
---

# Minis 沙箱逆向环境手册

## 0. 反卡死纪律（最高优先级，先读这条）

**绝不等待。卡住就换方案，不重试同一条命令。**

- 不用 `delay`、不用 `sleep` 轮询、不做"等一会儿再看"。
- 长跑命令必须 `timeout N` 包住；重活 `nohup ... > log 2>&1 &` 丢后台。
- ⚠️ **`timeout` 默认发 SIGTERM，而挂住的进程会忽略它 → 进程存活 → 整个 PRoot 被拖死**（这就是本沙箱三次卡死的真正原因）。必须用 **`timeout -s KILL`**，重活再加 `setsid` 脱离进程组，事后 `pkill -9` 清残留。
- ⚠️ **第三种卡死＝自家重活叠加**（2026-09-22 实测，此前误判为"PRoot 实例损坏，需重启沙箱"）：全树 `grep -ril /var/minis/shared`（含视频二进制，单人烧 48 分钟 CPU）＋ 4 路 `curl -r` 分段下载 ＋ 900K 限速大文件上传 ＋ 8 路分段上传实验 → load 14–16，PRoot 内 `echo` 都要几十秒才回，**file 工具/浏览器仍正常**。
  - **判据**：`prunner status` → `RUNAWAY`/`HEAVY_IO`/`UPLOAD` 计数（有 RUNAWAY 或 ≥2 重活 = 假死前置条件，exit 3）。
  - **处置**：停掉重活即自愈（实测约 5–10 分钟恢复），**不需要重启沙箱**；`prunner kill-runaway`（干跑）/ `--kill`（只杀 PRoot 后代，绝不碰宿主进程）。
  - **预防**：大文件串行 1–2 路；找文件用 `find -name` 或限定目录，绝不 `grep -r` 扫 `/var/minis/shared`。
- **看结果用 `file_read` 读日志**，不要 shell 轮询。
- 命令无响应 = 该方案作废 → 立刻换**完全不同的路径**（换工具/换数据源/换实现层/用文件工具绕过 shell）。
- 本沙箱里长跑进程可能**拖死整个 PRoot**（shell 全线无响应）：此时直接用文件工具继续推进，不要试图用 shell 抢救。
- ⚠️ **`/var/minis/workspace` 是会话级临时目录**（每条新会话重新开始，旧内容不可见）。**任何要复用的工具/脚本/文档必须写 `/var/minis/shared/`（能力资产统一放 `/var/minis/shared/self/`）**，workspace 只放当次构建产物。指向 workspace 的 `ln -s` 和文档路径会在换会话后集体悬空（2026-09-16 实际发生过一次）。

## 0a. 格机守卫 brickguard（做任何解密/解包前先过一遍；2026-09-23 修订：目标=sh/apk 等可执行产物）

- **解密 / 解包 / 反序列化产出的可执行类产物（.sh/.bat/.ps1 脚本、.apk、二进制、含上述内容的压缩包）→ 先 `brickguard scan --auto <产物>`**；未知来源脚本执行前先 `brickguard scan`。
- **技能（skills/）、普通源码、文档不是目标**：危险字样只提示、**永不自动隔离**；`/var/minis/skills/**` 连 .sh 也不自动隔离。
- **命中 critical（格机级）→ 立即停止整条任务链**，向用户醒目警告、隔离文件；**绝不执行被扫内容里的任何命令**。high → 暂停、证据交用户裁决；medium → 提醒、不动作。
- 工具：`/var/minis/shared/brickguard/`，命令 `brickguard`（scan/check/run/quarantine/restore/purge/selftest）。

## 0b. 环境本质（先读这段，能省半小时）

- **平台**：Alpine Linux aarch64（musl）跑在 Android 上的 **PRoot** 里。不是真 Linux，系统调用被 PRoot 转发。
- **`TMPDIR` 坏掉了**：默认指向 `/data/user/0/.../cache`（不存在）。**所有编译/pip 前先 `export TMPDIR=/tmp`**，否则 make 报奇怪的 "Function not implemented"、pip 报权限错误。
- **PRoot 的 `wait()` 有缺陷**：`make -j4` 以上容易整段报 `wait: Function not implemented` 并失败，甚至把整个沙箱卡死。**源码编译用 `-j1` 或 `-j2`**。
- **JDK 21 跑不起来**：`Failed to mark memory page as executable`（PRoot/Android 禁止 JIT 申请可执行页）。**只有 JDK 17 可用**。任何要求 JDK 21 的软件（Ghidra 11.1+）都不能用原生 JRE。
- **没有 ICMP**：`ping` 会挂死，测连通性用 `curl -o /dev/null -w "%{http_code}"`。
- **写文件优先用 file_write 工具**，BusyBox ash 的 heredoc 容易炸；`**` 递归 glob、brace expansion、bash 数组都不支持。

## 0c. 文件操作陷阱（2026-09 实测，代价 5.5 万坏条目，必读）

- **绝对禁用 `cp -al` / `cp -l` / `ln`（任何硬链接操作）**：PRoot 的 link2symlink 会把源与目标文件都转换成 `.l2s.<名>0001` 实体 + 原名条目（`ls`/`stat` 报 EPERM、`rm` 删不掉、`find` 遍历报错）。一次 `cp -al` 大目录 = 数万坏条目灾难。
- **永不删除既有的 `.l2s.*`（2026-09-25 自伤实证）**：`.l2s.*` **不是垃圾**，而是 PRoot 模拟 hardlink/rename 的实现细节。
  很多情况下**原名条目只是符号链接，`.l2s.X` 才是数据本体** —— 删 `.l2s.*` 会当场毁掉对应文件
  （实测：删 `.git/objects/pack/.l2s.tmp_pack_*` 后，`pack-*.pack/.idx/.rev` 立刻 EPERM，`git log` → `bad object HEAD`）。
  **判据**：`readlink <文件>` 若指向同目录 `.l2s.*`，那个 `.l2s.*` 就是数据本体。只清**悬空**的（`-xtype l`），且先取证。
  事故恢复法：重新 `git clone` 到 `/tmp` → 损坏仓库里 `git fetch /tmp/<clone> <branch>` → `git reset --hard FETCH_HEAD`（工作树本地新增文件会显示为 `??`，属正常）。
- **复制目录用**：`cp -r`（小目录）或 `tar -C src -cf - . | tar -C dst -xf -`（大目录，零 link 调用，最稳）。
- **不要 `git clone` 大仓库**（PRoot 下可能损坏：`git fsck` 报 invalid sha1、文件转 .l2s）。用 GitHub tarball：`curl -L https://github.com/<o>/<r>/archive/refs/heads/main.tar.gz` + `tar xzf`（解压不含 link 调用）。必须 clone 时：clone 后立刻 `git fsck --connectivity-only` + 抽查文件可读性。
- **删不掉的坏目录这两招**：① `mv 整目录` 到别处（rename 系统调用，绕过逐文件 stat/EPERM）；② 从 **Android 侧** `android-shizuku-cli exec 'rm -rf <真实路径>'`（绕过 PRoot 模拟层，真 FS 层删除）。
- **批量操作后验证**：`find <dir> -print >/dev/null 2>/tmp/err.txt; wc -l < /tmp/err.txt` 应为 0。

## 1. 跨架构仿真层（本沙箱最有价值的能力）

aarch64 宿主能跑别的架构的 Linux 用户态程序，**每个架构配一个独立 rootfs**：

| 架构 | 命令 | rootfs | 便捷包装 |
|---|---|---|---|
| x86_64 | `qemu-x86_64` | `/opt/x86` | `xrun` `xstrace` `xpython` `xpip` |
| i386 | `qemu-i386` | 需另建 | — |
| armhf (ARM32) | `qemu-arm` | `/opt/arm`（不完整） | `rrun` |
| riscv64 / mips | `qemu-riscv64` `qemu-mips` | 需另建 | — |

```sh
xrun /path/to/x86_64_binary args     # 直接跑 x86_64 程序
xstrace /path/to/sample              # qemu 用户态系统调用追踪（= 免 strace 的动态分析）
xpython -c "print('x86_64 python')"  # x86_64 Python 3.12（可 xpip 装 manylinux 轮子）
```

建新架构 rootfs 的模板：
```sh
apk --arch x86_64 --root /opt/x86 --initdb --keys-dir /etc/apk/keys \
  -X https://repo.huaweicloud.com/alpine/v3.21/main \
  -X https://repo.huaweicloud.com/alpine/v3.21/community \
  -U --allow-untrusted add busybox coreutils python3 binutils
```
（busybox 的安装后触发脚本会报 signal 7，**无害**，文件已就位。）

**用途**：跑只有 x86_64 版的工具、跑 x86_64 样本观察行为、用 `-strace` 抓系统调用、用 manylinux 轮子绕开 aarch64-musl 的轮子缺失。

## 2. 静态分析

| 工具 | 能力 |
|---|---|
| `file` / `readelf` / `nm` | 格式识别与 ELF 头节表（宿主 binutils，支持所有架构的**解析**） |
| `objdump` | **混合分派器**：aarch64 走 GNU，其他架构自动转 `llvm-objdump`（能反汇编 x86/x64/ARM/MIPS/RISC-V 等全部目标） |
| `llvm-objdump` / `llvm-readobj` / `llvm-mc` | LLVM 19 全架构工具集 |
| `r2` / `rabin2` | radare2 5.9.8，全架构分析：`r2 -q -e bin.cache=true -c 'iI;aa;afl' target` |
| `pdc` | r2 内置伪反编译：`r2 -q -c 's main; pdc' target` |
| **Ghost/分析脚本** | `ghidra_headless`（见第 4 节）、`r2pipe`（Python） |
| `capstone` / `keystone` | Python 反汇编/汇编（2.x/0.9.2） |
| `pwntools` 4.15 | `asm` `disasm` `ELF` `ROP` `shellcraft`。x86_64 目标靠 `/usr/local/bin/x86_64-{objdump,as,objcopy,strip,...}` shim → qemu 调 `/opt/x86` 里的**真 GNU binutils**（用 llvm/clang 做 shim 不行，参数约定不符） |
| `ropper` / `ROPgadget` | gadget 搜索 |
| `lief` / `pyelftools` / `pefile` / `macho` | 各格式解析库 |
| `dwarf-expert` 技能 | DWARF 类型/行号恢复 |

**注意**：`objdump -i` 显示宿主 binutils 只支持 aarch64 —— 这是为什么做了分派器。直接调 `/usr/bin/objdump` 分析 x86 会失败。

## 3. 动态分析 / 仿真

| 工具 | 能力 | 限制 |
|---|---|---|
| `gdb` 15.2 | 原生 aarch64 调试 | **不支持交叉架构**（`set architecture i386:x86-64` 报错） |
| `strace` / `ltrace` | aarch64 目标系统调用/库调用追踪 | 对别架构目标无效 |
| `qemu-*-strace` | **跨架构系统调用追踪**（x86_64 样本可用） | 见第 1 节 |
| `qemu -d in_asm,exec,cpu` | 指令级执行追踪 | 输出量大 |
| `qemu -g <port>` | GDB stub（需 guest 侧 gdb，见下） | — |
| `valgrind` | aarch64 内存检查 | 慢 |
| `unicorn` 2.1 | 指令级仿真（Python），x86/arm/aarch64 | 无系统调用 |
| `qiling` 1.4.6 | 全系统仿真框架（带 syscall 模拟，基于 unicorn） | 需要 rootfs |
| `qemu-system-*` | 全系统仿真（aarch64/arm/x86_64），固件用 | — |
| `afl-fuzz` | 模糊测试（aarch64 目标） | 插桩需重编译 |
| `mitmproxy` / `tshark` / `tcpdump` / `tcpflow` / `nmap` / `socat` | 网络侧 | — |

**跨架构调试的正确姿势**（d 目标为 x86_64）：
```sh
# 1) 在 x86_64 rootfs 里装 gdb
apk --arch x86_64 --root /opt/x86 ... add gdb
# 2) 宿主 side: qemu-x86_64 -g 1234 -L /opt/x86 ./sample
# 3) guest side gdb 连过去：
xrun /opt/x86/usr/bin/gdb ./sample -ex 'target remote :1234'
```

## 4. 反编译（Ghidra 11.0.3 + 自编原生 aarch64 解编译器）

Ghidra 官方只发 **x86_64 的原生解编译器**，aarch64 上跑不了；但**源码在发行包里**，已把它编成原生 aarch64 二进制。

- 版本：**Ghidra 11.0.3**（最后一个要求 JDK 17 的版本，`application.java.min=17`；11.1+ 强制 JDK 21，本沙箱跑不了）
- 位置：`/opt/ghidra1103/ghidra_11.0.3_PUBLIC`
- 原生解编译器：`Ghidra/Features/Decompiler/os/linux_arm_64/{decompile,sleigh}`（自行编译，另有 `linux_aarch64`/`linux_arm64` 等别名目录，因为 Ghidra 的架构目录名不确定）
- **必须先卸掉 `openjdk21`**（`apk del openjdk21`）：它坏在本沙箱跑不起来，却会把 `java` 抢走，导致 Ghidra 的 LaunchSupport 崩在 "Failed to mark memory page as executable"，最终报 "Unable to prompt user for JDK path"
- **关键：解编译器需要 `SLEIGHHOME=<Ghidra 根目录>`**。`consolemain.cc` 里 `FileManage::discoverGhidraRoot(argv[0])` 在无参数启动（Ghidra 就是无参数用管道启动它）时推导不出根目录，会回退到 `SLEIGHHOME`，否则直接 `exit(1)`→ Ghidra 侧表现为 `IOException: Unable to create decompiler`。

- **DWARF 版本限制**：Ghidra 11.0.3 只认 DWARF ≤ 4，而 clang 默认产 DWARF5（实测报 `Only DWARF version 2, 3, or 4 information is currently supported (detected 5)`）。自编样本加 `-gdwarf-4` 可消除该告警。

**现状**：headless 的 导入/分析 已验证可用（`IMPORTING`/`ANALYZING`/反编译前流程全通）；解编译器进程能被 Ghidra 启动（用包装脚本抓到调用），但带 `SLEIGHHOME` 的解编译调用在测试中超时未返回，**反编译输出尚未验证成功**。高频场景先退回 r2 的 `pdc`：

```sh
export TMPDIR=/tmp
G=/opt/ghidra1103/ghidra_11.0.3_PUBLIC
export SLEIGHHOME=$G
# 导入+分析（已验证 OK）
$G/support/analyzeHeadless /tmp/ghproj Proj -import <样本> -noanalysis
# 反编译（待验证，脚本已就绪）
$G/support/analyzeHeadless /tmp/ghproj Proj -import <样本> \
  -postScript DecompHeadless.java -scriptPath /var/minis/shared/self/ghidra-scripts
```
> ⚠️ `DecompHeadless.java` 本身尚未重建（旧副本在会话级 workspace 中丢失）；此处路径是它的持久化归宿。Ghidra 反编译链路仍是**待验证**项（见 limits.md 待办）。

```sh
export TMPDIR=/tmp JAVA_HOME=/usr/lib/jvm/java-17-openjdk
GH=/opt/ghidra1103/ghidra_11.0.3_PUBLIC
$GH/support/analyzeHeadless /tmp/ghproj Proj \
  -import /path/to/target \
  -postScript DecompHeadless.java \
  -scriptPath /var/minis/shared/self/ghidra-scripts \
  -deleteProject
```
`DecompHeadless.java` **待重建**（旧副本随会话丢失），持久归宿 `/var/minis/shared/self/ghidra-scripts/`，功能是打印前两个函数的伪 C。

**自己重编解编译器的方法**（版本升级时用）：
```sh
export TMPDIR=/tmp
D=$GH/Ghidra/Features/Decompiler/src/decompile/cpp
cd $D && mkdir -p sla_opt sla_dbg com_opt com_dbg
make -j2 ARCH=x86_64 ARCH_TYPE= decomp_opt sleigh_opt   # ARCH_TYPE= 关键：默认会退化成 -m32
mkdir -p $GH/Ghidra/Features/Decompiler/os/linux_arm_64
cp decomp_opt .../os/linux_arm_64/decompile; cp sleigh_opt .../os/linux_arm_64/sleigh
```
需要 `bison flex linux-headers`（已装）。

## 5. 移动端 / 字节码

| 目标 | 工具 |
|---|---|
| Android APK | `jadx` 1.5.6、`apktool` 3.0.3、`dex2jar`、`androguard`、`apkid`（壳识别，依赖 yara）、apktool 内建 smali/baksmali |
| Java/JAR | `cfr` 0.152、`vineflower` 1.12、`jadx`、`jvm-decompile` 技能 |
| .NET | ⚠️ `dotnet` 8 SDK 装了但 **CoreCLR 起不来**（`GC heap initialization failed`，与 JDK21 同类的内存映射限制）→ 改用 **`dnfile`**（PE/.NET 元数据解析）+ **`dncil`**（CIL 反汇编），都是纯 Python 可用 |
| Python 字节码 | `uncompyle6`、`xdis`、`pyc-decompile` 技能 |
| JS | `js-deobfuscate` 技能 + node.js |
| Frida | **不可用**（无 aarch64-musl 构建）；改用 `objection`? 不行。用 renef 技能里的外部方案 |

## 6. 恶意代码分析

- `yara` 4.5.2 + `yara-python`（规则扫描）
- `volatility3`（内存取证）
- `oletools`（Office 宏）、`pefile`/`dnfile`/`lief`（PE 解析）
- `qiling` + `unicorn`（shellcode 仿真）、`qemu-*-strace`（行为追踪）
- `sleuthkit`（`fls`/`icat`/`mmls`/`fsstat`）、`testdisk`（磁盘镜像/固件提取）
- `exiftool`/`exiv2`（元数据）
- `capa`/`FLOSS`：**当前装不上**（新版需要 Rust 构建，crates.io 被 403；见第 8 节）

## 7. 构建工具链

`gcc` `g++` `clang`/`llvm` 19 `cmake` `make` `nasm` `yasm` `bison` `flex` `linux-headers` `rustc`/`cargo` `go` `nodejs` `perl` `ruby` `git` `binutils-dev` `capstone-dev` `yara-dev` `radare2-dev`

**交叉编译 x86_64 测试样本**（用 x86_64 rootfs 里的 gcc，跑在 qemu 下）：
```sh
apk --arch x86_64 --root /opt/x86 ... add build-base
xrun /opt/x86/usr/bin/gcc -static -o /tmp/t.bin /tmp/t.c
```

## 8. 已知缺口与规避

| 缺口 | 原因 | 规避 |
|---|---|---|
| Ghidra 11.1+ / 任何需要 JDK21 的 Java 软件 | PRoot 禁 JIT exec 页 | 用 Ghidra 11.0.3 |
| `frida` | 无 aarch64-musl 构建 | x86_64 rootfs + `xpip install frida`（仅限分析 x86_64 目标，且受 qemu 限制） |
| `capa` `FLOSS` | 新版需 Rust 构建，crates.io 403 | 见 install_capa.log；或改用 yara + 手工规则 |
| `binwalk` `foremost` `scalpel` | Alpine 无包 | 用 `sleuthkit` + 自写 carve 脚本，或 `xpip install binwalk`（需 x86_64 rootfs 的支撑工具） |
| `ghidra` 的 `-j1` 编译慢 | PRoot wait 缺陷 | 接受慢；或 `-j2` |
| 内核级工具（eBPF/drgn/ftrace） | 容器限制 | 不适用，改静态分析 |
| `strace` 跟踪 x86_64 目标 | 原生 strace 只认本架构 | 用 `qemu-x86_64 -strace` |

## 9. 标准工作流模板

```sh
export TMPDIR=/tmp
T=/path/to/sample

# ① 分诊
file $T; rabin2 -I $T; rabin2 -zz $T | head -20
python3 -c "import math;d=open('$T','rb').read();print('熵', sum(-p*math.log2(p) for p in [d.count(bytes([b]))/len(d) for b in range(256)] if p))"

# ② 保护探测
rabin2 -I $T | grep -E 'canary|nx|pic|relocs|stripped'

# ③ 静态（全架构反汇编）
llvm-objdump -d --no-show-raw-insn $T | head -40
r2 -q -e bin.cache=true -c 'aa; afl~main; s main; pdc' $T

# ④ 反编译（Ghidra headless，见第 4 节）

# ⑤ 动态
xstrace $T 2>&1 | head -50            # x86_64 目标
strace -f ./$T 2>&1 | head -50        # aarch64 目标

# ⑥ 仿真关键函数
python3 -c "
from unicorn import *
from unicorn.x86_const import *
mu=Uc(UC_ARCH_X86, UC_MODE_64); mu.mem_map(0x1000,0x10000)
mu.mem_write(0x1000, open('$T','rb').read()[0x1000:0x2000])
mu.emu_start(0x1000,0x1010)
print(hex(mu.reg_read(UC_X86_REG_RAX)))"

# ⑦ 出规则
yara myrule.yar $T
```

## 10. 纪律

1. **先 `which` 再动手**——技能文档里写的工具可能在这个沙箱没有。
2. **架构先判**：`file` 出来不是 aarch64 就要走仿真层，别指望原生 strace/gdb。
3. **`export TMPDIR=/tmp`** 是每次编译前的肌肉记忆。
4. 所有分析仅限**授权环境、自有样本、CTF、漏洞研究**。

## 11. 星匣沙盒系统（2026-09-18 新增）—— 跑跨架构完整负载的正确方式

**盒子（chroot 真隔离）**：`sbox box create <n> --arch x86_64|i386` → `sbox box exec <n> -- <命令>`。
盒内 **qemu 子进程 exec 链完整可用**（自研 execve 桥：execve/execv/execvp/execl* 全覆盖，python subprocess 深链实测通过）。
- 详细原理/限制/维护: `/var/minis/shared/self/starbox/README.md`
- 通用运行器: `runex <任意架构ELF或脚本>`（自动分派 qemu+rootfs）
- OCI 镜像: `sbox image pull alpine:3.21` / `sbox box create <n> --from-image <ref>`（走 daocloud 镜像站）
- 演示盒: `alpine`(原生aarch64) / `t32`(i386) / `t64`(x86_64)；体检 `sbox doctor`，自检 `sbox selftest`
- 注意：盒内无 /dev,/proc（PRoot 限制）；跨架构盒内避免依赖 shebang 脚本直跑
