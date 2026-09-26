---
name: android-control
description: 手机操控技能：读取屏幕内容(uiautomator dump)、点击/滑动/按键、启动与管理系统应用、修改系统设置。当任务涉及"帮我操作手机/打开某应用/点某处/改设置"时使用。
---

# 手机操控（Android + root）

可用工具：`android_screenshot` `android_tap` `android_swipe` `android_key` `android_app` `android_root`（插件），以及 `bash`（可用 `su -c` 提权）。

## 一、先"看"再"动"（必须）

1. 读当前界面结构（比截图更适合你阅读）：
   ```sh
   su -c "uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml"
   ```
   输出是节点树，找到目标控件的 `text` / `content-desc` / `bounds`（如 `[360,2100][720,2250]`）。
2. 由 bounds 计算中心点：x=(左+右)/2，y=(上+下)/2。
3. 用 `android_tap` 点击；界面变化后（约 1-2 秒）再次 dump 确认结果。
4. 需要视觉信息时 `android_screenshot` 截屏存档（路径回报给用户）。

## 二、常用操作速查

- 返回：`android_key BACK`；回桌面：`android_key HOME`；最近任务：`android_key APP_SWITCH`
- 启动应用：`android_app launch <包名>`（如 com.tencent.mm）
- 停止/清数据：`android_app stop|clear <包名>`
- 输入文字：`android_root` 执行 `input text '内容'`（中文建议先切到英文输入或使用剪贴板：`input keyevent 279` 粘贴）
- 滑动列表：`android_swipe x1 y1 x2 y2 300`（上滑=x相同，y從大到小）

## 三、系统设置（root 直改，免点按）

```sh
su -c "settings put system screen_brightness 128"        # 亮度
su -c "settings put system volume_music 8"                # 音量(0-15)
su -c "cmd wifi status"                                    # WiFi 状态
su -c "svc wifi enable|disable"                            # WiFi 开关
su -c "cmd connectivity airplane-mode enable|disable"      # 飞行模式
su -c "am start -a android.intent.action.VIEW -d <URL>"    # 打开链接
```

## 四、应用管理

```sh
su -c "pm list packages -3"                     # 第三方应用
su -c "dumpsys package <包名> | head -40"        # 版本/权限
su -c "pm disable-user --user 0 <包名>"          # 停用（可逆）
su -c "pm enable <包名>"                         # 恢复
```
卸载前必须向用户确认；系统关键包不要动。

## 五、纪律

- 每一步"操作→验证"，不要连续盲点。
- 涉及支付、删除、退出账号等敏感界面：先停下让用户确认。
- 坐标会因分辨率不同而变：先 `wm size` 拿分辨率，比例换算参考。
