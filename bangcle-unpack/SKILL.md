---
name: bangcle-unpack
description: 企业加固（梆梆 Bangcle / libDexHelper 系）脱壳专技。含两条脱壳路线：直接解密 classes0.jar（C++ 解密器源码）与 Frida hook 内存 dump；附完整逆向调试记录。当目标 APK 被加固（APKiD 报 bangcle/nqshield/娜迦等）、类抽取/填充式加固、Frida 遭反调试干扰时使用。
---

# 梆梆企业加固脱壳（crack_dexhelper 材料包）

材料来源：开源项目 `ylcangel/crack_dexhelper`（498★，梆梆企业加固详细逆向分析）。

## 材料清单

| 文件 | 用途 |
|---|---|
| `src/decrypt_classes0.jar/decrypt.cpp` + `.h` | **路线 A**：直接解密 classes0.jar 的 C++ 解密器源码 |
| `src/frida_dump/dumdex_open_mem.js` + `main.py` | **路线 B**：Frida hook 内存 dump 方案 |
| `src/decstring/decstr.c` | 字符串解密工具 |
| `docs/调试整个过程.txt` | 完整调试过程记录（第一手） |
| `docs/加固分析总结.pdf` | 加固机制分析与总结 |
| `README-source.md` | 原项目 README |

## 作业流程

1. **识别**：APKiD 判定加固类型；确认 `libDexHelper.so`、壳入口 Application、类抽取特征。
2. **路线 A（静态解密）**：定位 classes0.jar 的加密环节 → 编译 `decrypt.cpp` → 解密出真实 dex。
3. **路线 B（动态 dump）**：`ensure-frida` → `fhook` 注入 `dumdex_open_mem.js`（hook open 系列拦截 dex 落地）→ dump → 修复 header。
4. **修复与验证**：`android-native-auto-reverse` 技能内 `scripts/dex_header_fix.py`、`dex_dump_validator.py`。
5. **反 Frida 对抗**：`android-native-auto-reverse/references/bangcle-dexhelper-frida-dexdump.md` 与 `scripts/frida_bangcle_dexhelper_antifrida.js`（本机 frida-kit 环境下同样适用）。

## 环境

Frida 链路（本机已建成）：`ensure-frida` 拉起设备侧服务，`fhook <目标> <脚本>` 注入。
手册：`/var/minis/shared/self/frida-kit/README.md`。
通用脱壳工具（frida-dexdump 等）：见技能 `dexdump-toolkit`。
