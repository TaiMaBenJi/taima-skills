---
name: device-diagnostics
description: 手机体检技能：排查卡顿/发热/耗电/存储/网络问题，读取电池、CPU、内存、日志与网络状态。当用户说"手机卡/发烫/耗电快/没网/帮我看看"时使用。
---

# 手机体检（Diagnostics）

## 一、快速体检（一次性采集）

```sh
su -c "uptime; free -h; df -h /data; dumpsys battery | head -12"
su -c "dumpsys thermalservice | head -20"            # 温度
su -c "top -n 1 -b -o %CPU | head -15"               # CPU 占用 Top
su -c "dumpsys meminfo | head -25"                    # 内存
```

## 二、排查卡顿（重点：谁在吃 CPU）

```sh
su -c "cat /proc/loadavg"                             # 负载对比核数
su -c "ps -A -o PID,%CPU,%MEM,ARGS | sort -k2 -rn | head -12"
```
- 负载 > 核数×2 → 找重负载进程；`ps` 里若见到 ffmpeg/编译类进程，多半是它们在跑。
- 单个进程失控可 `kill <PID>`（应用进程先问用户）。

## 三、排查发热/耗电

```sh
su -c "dumpsys thermalservice | grep -i temp | head -10"
su -c "dumpsys batterystats --charged | head -40"     # 耗电明细(重)
su -c "dumpsys deviceidle whitelist | grep <包名>"    # 是否白名单
```

## 四、排查网络

```sh
su -c "ping -c 3 223.5.5.5"        # ICMP(有的网络禁 ping，失败不代表断网)
su -c "curl -s -o /dev/null -w '%{http_code} %{time_total}s' https://www.baidu.com"
su -c "dumpsys wifi | grep -i 'mNetworkInfo\|SSID' | head -6"
su -c "getprop | grep -i dns"      # DNS 配置
```

## 五、看崩溃日志

```sh
su -c "logcat -d -b crash | tail -60"
su -c "logcat -d | grep -E 'FATAL|ANR' | tail -30"
```

## 输出规范

按「结论 → 证据（命令输出摘要）→ 建议动作」三段式汇报；发现异常进程/设置时给出可执行的处置命令。
