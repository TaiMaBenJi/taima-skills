#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OMNI v2 构建器：扫描 /var/minis/skills/ 全部技能（全量 2000+），生成：
   SKILL.md（总入口）、catalog.md、index.json、index.tsv、FULL-BUNDLE.md、browse.html
归类优先级：_data.SKILLS 手动精编 → skills-library/INDEX-RE.tsv 自动分类 → 关键词兜底。
用法：python3 build.py   （或 `omni rebuild`）
"""
import os, re, json, sys
from datetime import datetime

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = '/var/minis/skills'
LIB = '/var/minis/shared/skills-library'
sys.path.insert(0, HERE)
import _data

GEN_TIME = datetime.now().strftime('%Y-%m-%d %H:%M')

# 全量模式下扩展的分类（追加在 _data.CAT_ORDER 之后）
EXTRA_CATS = [
    ("forensics", "🧫 取证 · 事件响应"),
    ("fuzz",      "🎯 模糊测试"),
    ("kernel",    "🧠 内核 · 底层研究"),
    ("games",     "🎮 游戏逆向"),
]
CAT_ORDER = list(_data.CAT_ORDER) + EXTRA_CATS
CAT_LABEL = dict(CAT_ORDER)
CAT_LABEL['misc'] = '🆕 其他'

# INDEX-RE 分类 → omni 分类
CAT_MAP = {
    'malware': 'malware', 'exploit': 'offensive', 'disasm': 'static',
    'firmware': 'firmware', 'forensics': 'forensics', 'ctf': 'ctf',
    'unpack': 'triage', 'rev-core': 'static', 'mobile': 'mobile',
    'fuzz': 'fuzz', 'dynamic': 'debug', 'kernel': 'kernel', 'symbolic': 'debug',
}

# 关键词兜底（无索引条目时按名称/描述判类）
KW_RULES = [
    ('games',     ['game', 'unity', 'il2cpp', 'cocos', 'unreal', 'ps2', 'nintendo', 'switch', 'cheat', '游戏']),
    ('frida',     ['frida', 'instrumentation framework']),
    ('android',   ['android', 'apk', 'smali', 'jadx', '安卓']),
    ('ios',       ['ios ', 'ipa', 'mach-o', 'macho', 'iphone', 'apple platform']),
    ('malware',   ['malware', 'ransomware', 'trojan', 'stealer', 'rootkit', 'bootkit', '恶意']),
    ('offensive', ['exploit', 'pwn', 'shellcode', 'red team', 'adversary', 'payload', '漏洞']),
    ('firmware',  ['firmware', 'uefi', 'bios', 'iot', 'embedded', '固件', 'mcu', 'can bus', 'can-bus', 'scada', 'modbus']),
    ('forensics', ['forensic', 'incident response', '取证', 'memory dump', 'disk image']),
    ('fuzz',      ['fuzz', 'afl', '模糊']),
    ('kernel',    ['kernel', '内核', 'ebpf', 'rootkit']),
    ('debug',     ['debug', 'gdb', 'windbg', 'trace probe', 'syscall', '调试', '仿真', 'emulat']),
    ('ctf',       ['ctf', 'crackme']),
    ('lang',      ['bytecode', 'python bytecode', 'pyc', 'wasm', 'webassembly', 'jvm', 'dotnet', 'il2cpp', 'lua', '脚本']),
    ('web',       ['javascript', 'js ', 'browser', 'web ', 'protocol']),
    ('mobile',    ['mobile', 'cordova', 'react native']),
    ('triage',    ['triage', 'unpack', 'packer', 'upx', 'analyze binary', '分诊']),
    ('diff',      ['diff', 'variant']),
    ('static',    ['decompil', 'disassembl', 'ghidra', 'ida ', 'radare', 'rizin', 'binary', 'elf', '反编译', '反汇编', '逆向', 'reverse']),
]

# 名称强制覆盖（优先于 INDEX-RE 自动分类）
NAME_OVERRIDE = [
    ('games', ['cocos', 'ps2', 'nintendo', 'retro game', 'game re', 'game-re', 'gba', 'unity', 'il2cpp', 'dragonbones', 'spine']),
]

def load_auto_map():
    """name → omni slug，来源：INDEX-RE.tsv"""
    m = {}
    p = os.path.join(LIB, 'INDEX-RE.tsv')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8', errors='replace'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 7:
                continue
            name = parts[2].strip()
            cat = parts[1].strip()
            if not name:
                continue
            slug = CAT_MAP.get(cat)
            if slug and name not in m:
                m[name] = slug
    return m

def kw_fallback(name, desc):
    blob = (name + ' ' + (desc or '')).lower()
    for slug, kws in KW_RULES:
        for k in kws:
            if k in blob:
                return slug
    return 'misc'

def parse_frontmatter(text):
    fm = {}
    body = text
    if text.startswith('---'):
        m = re.search(r'\n---\s*\n', text[3:])
        if m:
            raw = text[3:3 + m.start()]
            body = text[3 + m.end():]
            cur = None
            for line in raw.splitlines():
                mm = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$', line)
                if mm:
                    cur = mm.group(1).strip()
                    fm[cur] = mm.group(2).strip()
                elif cur and line.strip():
                    fm[cur] = (fm[cur] + ' ' + line.strip()).strip()
    if not fm.get('description'):
        m = re.search(r'##\s*Description\s*\n+([^\n#].*(?:\n(?!\n|#)[^\n]*)*)', text)
        if m:
            fm['description'] = m.group(1).strip()
    return fm, body

def clean_desc(s):
    s = (s or '').strip()
    if s[:2] in ('>-', '|-') or s[:1] in ('>', '|'):
        s = s.lstrip('>|-').strip()
    s = s.strip('"').strip("'").strip()
    return ' '.join(s.split())

def human(n):
    if n >= 1024 * 1024:
        return f'{n/1048576:.1f} MB'
    if n >= 1024:
        return f'{n/1024:.1f} KB'
    return f'{n} B'

def preview_of(body, limit=1800):
    """取正文前部作为预览（截到段落边界）"""
    if len(body) <= limit:
        return body
    cut = body[:limit]
    pos = cut.rfind('\n\n')
    if pos > limit * 0.5:
        cut = cut[:pos]
    return cut + '\n\n…（完整内容见 SKILL.md）'

auto_map = load_auto_map()
items = []
warn = []
for d in sorted(os.listdir(ROOT)):
    if d == 'omni':
        continue
    p = os.path.join(ROOT, d)
    sp = os.path.join(p, 'SKILL.md')
    if not (os.path.isdir(p) and os.path.exists(sp)):
        continue
    try:
        raw = open(sp, encoding='utf-8', errors='replace').read()
    except OSError:
        continue
    fm, body = parse_frontmatter(raw)
    desc = clean_desc(fm.get('description', '')) or clean_desc(fm.get('name', ''))
    meta = _data.SKILLS.get(d)
    if meta:
        slug, oneliner, star = meta
    else:
        slug = auto_map.get(d) or kw_fallback(d, desc)
        low = d.lower()
        for ov_slug, kws in NAME_OVERRIDE:
            if any(k in low for k in kws):
                slug = ov_slug
                break
        oneliner = desc[:72] if desc else ''
        star = False
    if slug not in CAT_LABEL:
        slug = 'misc'
    subdirs = sorted(x for x in os.listdir(p)
                     if os.path.isdir(os.path.join(p, x)) and x != '.git')
    files = sorted(x for x in os.listdir(p)
                   if os.path.isfile(os.path.join(p, x)) and x != 'SKILL.md')
    items.append({
        'name': d,
        'dir': p,
        'category': slug,
        'catLabel': CAT_LABEL.get(slug, CAT_LABEL['misc']),
        'star': star,
        'oneliner': oneliner,
        'desc': desc,
        'bytes': os.path.getsize(sp),
        'body': body,
        'preview': preview_of(body),
        'subdirs': subdirs,
        'files': files,
    })

for name in _data.SKILLS:
    if name not in {i['name'] for i in items}:
        warn.append(f'- {name}（在 _data.py 有登记但磁盘上没有）')

# ---------- index.json ----------
json_items = [{k: v for k, v in it.items() if k not in ('body', 'preview')} for it in items]
cats = [{'slug': s, 'label': l, 'count': sum(1 for it in items if it['category'] == s)}
        for s, l in CAT_ORDER]
cats.append({'slug': 'misc', 'label': CAT_LABEL['misc'],
             'count': sum(1 for it in items if it['category'] == 'misc')})
index = {'generated': GEN_TIME, 'total': len(items), 'root': ROOT,
         'categories': [c for c in cats if c['count'] or c['slug'] != 'misc'],
         'skills': json_items}
open(os.path.join(HERE, 'index.json'), 'w', encoding='utf-8').write(
    json.dumps(index, ensure_ascii=False, indent=1))

# ---------- index.tsv ----------
with open(os.path.join(HERE, 'index.tsv'), 'w', encoding='utf-8') as f:
    for it in items:
        f.write(f"{it['name']}\t{it['category']}\t{it['bytes']}\t{it['dir']}\t{it['oneliner']}\n")

# ---------- SKILL.md ----------
def render_index():
    out = []
    order = [s for s, _ in CAT_ORDER] + ['misc']
    for slug in order:
        grp = [it for it in items if it['category'] == slug]
        if not grp:
            continue
        label = CAT_LABEL.get(slug, slug)
        out.append(f'### {label}（{len(grp)}）\n')
        for it in sorted(grp, key=lambda x: (not x['star'], x['name'].lower())):
            star = ' ★' if it['star'] else ''
            out.append(f"- `{it['name']}`{star} — {it['oneliner'][:90]}")
        out.append('')
    return '\n'.join(out)

stats = f"{len(items)} 技能 · 分类 {len([c for c in cats if c['count'] and c['slug'] != 'misc'])} · " \
        f"文本 {human(sum(it['bytes'] for it in items))} · 生成于 {GEN_TIME}"
tpl = open(os.path.join(HERE, 'TEMPLATE.md'), encoding='utf-8').read()
skill_md = tpl.replace('<!--@STATS@-->', stats) \
              .replace('<!--@INDEX@-->', render_index()) \
              .replace('<!--@GENTIME@-->', f'<!-- 本文件由 build.py 自动生成 / 更新时间 {GEN_TIME} -->')
open(os.path.join(HERE, 'SKILL.md'), 'w', encoding='utf-8').write(skill_md)

# ---------- catalog.md ----------
cat = [f'# OMNI 技能目录 · catalog', '', f'> {stats}', '',
       '本文件由 `build.py` 自动生成。全文合集见 `FULL-BUNDLE.md`，在线浏览见 `browse.html`。', '']
for slug, label in CAT_ORDER + [('misc', CAT_LABEL['misc'])]:
    grp = [it for it in items if it['category'] == slug]
    if not grp:
        continue
    cat.append(f'## {label}（{len(grp)}）\n')
    for it in sorted(grp, key=lambda x: (not x['star'], x['name'].lower())):
        star = ' ★' if it['star'] else ''
        cat.append(f"### `{it['name']}`{star}")
        cat.append(f"- **路径**：`{it['dir']}/SKILL.md`（{human(it['bytes'])}）")
        assets = []
        if it['subdirs']:
            assets.append('目录 ' + ' / '.join(it['subdirs'][:8]) + ('…' if len(it['subdirs']) > 8 else ''))
        if it['files']:
            assets.append('文件 ' + ' / '.join(it['files'][:8]) + ('…' if len(it['files']) > 8 else ''))
        if assets:
            cat.append('- **资源**：' + '；'.join(assets))
        if it['oneliner']:
            cat.append(f"- **一句话**：{it['oneliner']}")
        if it['desc'] and it['desc'] != it['oneliner']:
            cat.append(f"- **描述**：{it['desc']}")
        cat.append('')
open(os.path.join(HERE, 'catalog.md'), 'w', encoding='utf-8').write('\n'.join(cat))

# ---------- FULL-BUNDLE.md ----------
b = [f'# OMNI 全技能合集 — {len(items)} 个技能全文', '',
     f'> {stats} · 本文件把所有技能 SKILL.md 合并于一处，可直接搜索 / grep / 通读。', '']
b.append('## 目录\n')
for slug, label in CAT_ORDER + [('misc', CAT_LABEL['misc'])]:
    grp = [it for it in items if it['category'] == slug]
    if not grp:
        continue
    b.append(f'**{label}**（{len(grp)}）')
    for it in sorted(grp, key=lambda x: (not x['star'], x['name'].lower())):
        b.append(f"- `{it['name']}` — {it['oneliner'][:90]}")
    b.append('')
b.append('\n---\n')
for n, it in enumerate(items, 1):
    b.append(f'\n<a id="{it["name"]}"></a>\n')
    b.append(f'# {n}/{len(items)} · `{it["name"]}` — {it["catLabel"]}')
    b.append(f'> 路径 `{it["dir"]}/SKILL.md` · {human(it["bytes"])} · {it["oneliner"]}\n')
    b.append(it['body'].strip())
    b.append('\n---\n')
open(os.path.join(HERE, 'FULL-BUNDLE.md'), 'w', encoding='utf-8').write('\n'.join(b))

# ---------- browse.html（嵌 preview 而非全文，页面轻量） ----------
tpl_html = open(os.path.join(HERE, '_browse_template.html'), encoding='utf-8').read()
embed = [{'name': it['name'], 'cat': it['category'], 'catLabel': it['catLabel'],
          'star': it['star'], 'oneliner': it['oneliner'], 'desc': it['desc'],
          'bytes': it['bytes'], 'human': human(it['bytes']), 'path': it['dir'] + '/SKILL.md',
          'subdirs': it['subdirs'], 'files': it['files'], 'body': it['preview']}
         for it in items]
meta_js = json.dumps({'generated': GEN_TIME, 'total': len(items), 'root': ROOT},
                     ensure_ascii=False)
data_js = json.dumps(embed, ensure_ascii=False).replace('</', '<\\/')
html = tpl_html.replace('__OMNI_DATA__', data_js).replace('__OMNI_META__', meta_js)
open(os.path.join(HERE, 'browse.html'), 'w', encoding='utf-8').write(html)

# ---------- report ----------
print(f'OMNI v2 rebuilt at {GEN_TIME}')
print(f'   skills: {len(items)}  · categories: {len([c for c in cats if c["count"]])}')
print(f'   index.json {human(os.path.getsize(os.path.join(HERE, "index.json")))}  · '
      f'catalog.md {human(os.path.getsize(os.path.join(HERE, "catalog.md")))}  · '
      f'FULL-BUNDLE.md {human(os.path.getsize(os.path.join(HERE, "FULL-BUNDLE.md")))}  · '
      f'browse.html {human(os.path.getsize(os.path.join(HERE, "browse.html")))}')
for w in warn:
    print('WARN', w)
