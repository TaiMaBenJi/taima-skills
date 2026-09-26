# 从真实 check 输出生成预览图（不伪造内容）
import subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\DSH-Workspace\dsh-unlock-mode"
PS1  = os.path.join(ROOT, "unlock-dsh.ps1")
OUT  = os.path.join(ROOT, "assets", "preview.png")

# 1) 跑真实命令，抓输出
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, "check"],
    capture_output=True, cwd=ROOT,
)
raw = r.stdout.decode("utf-8", errors="replace")
lines = [l.rstrip() for l in raw.splitlines()]

# 只取有信息量的行：去掉空行、去掉 banner 装饰行
keep = []
for l in lines:
    s = l.strip()
    if not s:
        continue
    if set(s) <= set("= "):          # banner 分隔线
        continue
    keep.append(l)

# 截到 "自检通过" 那行为止，后面是 next-step 说明，图里不必要
cut = len(keep)
for i, l in enumerate(keep):
    if "自检通过" in l:
        cut = i + 1
        break
keep = keep[:cut]

# 脱敏：把本机用户名与绝对路径打码，避免把作者机器信息发到公开仓库
import re
HOME = os.path.expanduser("~")
USER = os.path.basename(HOME)
def scrub(s):
    s = s.replace(HOME, r"%USERPROFILE%")
    s = s.replace(HOME.replace("\\", "/"), r"%USERPROFILE%")
    s = re.sub(re.escape(USER), "<user>", s, flags=re.I)
    return s

keep = [scrub(l) for l in keep]

# 2) 字体
def load_font(size, bold=False):
    cands = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\consola.ttf",
    ]
    for c in cands:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()

F  = load_font(19)
FB = load_font(19, bold=True)
FT = load_font(24, bold=True)

# 3) 量尺寸
pad_x, pad_y = 34, 30
title_h = 66
lh = 31
W = 1080
H = title_h + pad_y * 2 + lh * len(keep) + 20

img = Image.new("RGB", (W, H), (13, 17, 23))          # GitHub dark
d = ImageDraw.Draw(img)

# 顶部标题栏
d.rectangle([0, 0, W, title_h], fill=(22, 27, 34))
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    cx = 26 + i * 26
    d.ellipse([cx - 8, title_h // 2 - 8, cx + 8, title_h // 2 + 8], fill=c)
d.text((128, title_h // 2 - 14), "unlock-dsh.bat  —  真实运行输出", font=FT, fill=(201, 209, 217))

y = title_h + pad_y
for l in keep:
    s = l.strip()
    if s.startswith("[OK]"):
        col = (63, 185, 80)
    elif s.startswith("[X]") or s.startswith("[!]"):
        col = (210, 153, 34) if s.startswith("[!]") else (248, 81, 73)
    elif s.startswith("==") or s.startswith("──"):
        col = (110, 118, 129)
    elif s.startswith("DSH_HOME") or s.startswith("preset"):
        col = (88, 166, 255)
    else:
        col = (201, 209, 217)
    d.text((pad_x, y), l, font=F, fill=col)
    y += lh

img.save(OUT, "PNG", optimize=True)
print("saved:", OUT, img.size)
print("lines:", len(keep))
