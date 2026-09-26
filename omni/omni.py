#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""omni — 88 合 1 技能总控 CLI。
用法:
  omni list [过滤词]        列出技能（按分类，或按过滤词）
  omni find <词...>         多关键词搜索（名称/简介/描述/全文），全部命中才算
  omni show <技能名>        打印技能全文
  omni path <技能名>        打印技能目录（找 scripts/references/assets）
  omni cat                  分类统计
  omni stats                总统计
  omni rebuild              重建全部索引产物
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.realpath(__file__))
INDEX = os.path.join(HERE, 'index.json')
ROOT = '/var/minis/skills'

def load():
    if not os.path.exists(INDEX):
        subprocess.run([sys.executable, os.path.join(HERE, 'build.py')], check=True)
    return json.load(open(INDEX, encoding='utf-8'))

def body_of(name):
    p = os.path.join(ROOT, name, 'SKILL.md')
    try:
        return open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''

def cmd_list(args):
    idx = load()
    f = (args[0].lower() if args else '')
    for c in idx['categories']:
        grp = [s for s in idx['skills'] if s['category'] == c['slug']
               and (not f or f in s['name'].lower() or f in s['catLabel'].lower()
                    or f in s['oneliner'].lower())]
        if not grp:
            continue
        print(f"\n■ {c['label']}（{len(grp)}）")
        for s in sorted(grp, key=lambda x: x['name']):
            star = '★' if s['star'] else ' '
            print(f"  {star} {s['name']:<38} {s['oneliner']}")
    print()

def cmd_find(args):
    kws = [a.lower() for a in args if not a.startswith('-')]
    if not kws:
        print('用法: omni find <关键词...>'); return
    idx = load()
    res = []
    for s in idx['skills']:
        b = body_of(s['name'])
        blob = (s['name'] + ' ' + s['oneliner'] + ' ' + s['desc'] + ' ' + b).lower()
        if not all(k in blob for k in kws):
            continue
        score = 0
        for k in kws:
            if k in s['name'].lower(): score += 12
            if k in s['oneliner'].lower(): score += 6
            if k in s['desc'].lower(): score += 3
            n = blob.count(k)
            score += min(n, 10)
        # 命中的正文字段行（展示用）
        hit = ''
        for line in b.splitlines():
            low = line.lower()
            if all(k in low for k in kws) and line.strip() and not line.startswith('---'):
                hit = line.strip()[:90]; break
        res.append((score, s, hit))
    res.sort(key=lambda x: -x[0])
    if not res:
        print('本机 88 个技能无命中。试试全量库:  skillctl search ' + ' '.join(kws))
        print('或放宽关键词（更少/更短的词）。')
        return
    print(f"命中 {len(res)} 个（按相关度）:\n")
    for score, s, hit in res[:25]:
        star = '★' if s['star'] else ' '
        print(f"{star} {s['name']}  [{s['catLabel'].split(' ',1)[-1]}]")
        print(f"    {s['oneliner']}")
        if hit:
            print(f"    > {hit}")
    if len(res) > 25:
        print(f'\n... 还有 {len(res)-25} 个，缩小关键词或加词。')
    print('\n查看全文:  omni show <名字>      目录:  omni path <名字>')

def exact(idx, name):
    for s in idx['skills']:
        if s['name'] == name:
            return s
    # 宽松匹配
    cands = [s for s in idx['skills'] if name.lower() in s['name'].lower()]
    if len(cands) == 1:
        return cands[0]
    if cands:
        print('多处匹配: ' + ', '.join(c['name'] for c in cands[:12]))
    return None

def cmd_show(args):
    if not args: print('用法: omni show <技能名>'); return
    idx = load(); s = exact(idx, args[0])
    if not s: print('未找到。用 omni find <词> 搜一下。'); return
    print(f"# {s['name']}  [{s['catLabel']}]  {s['dir']}/SKILL.md\n")
    print(body_of(s['name']))

def cmd_path(args):
    if not args: print('用法: omni path <技能名>'); return
    idx = load(); s = exact(idx, args[0])
    if not s: print('未找到。'); return
    print(s['dir'])

def cmd_cat(args):
    idx = load()
    for c in idx['categories']:
        print(f"  {c['label']:<28} {c['count']:>3}")

def cmd_stats(args):
    idx = load()
    tot = sum(s['bytes'] for s in idx['skills'])
    print(f"技能总数 : {idx['total']}   分类: {len(idx['categories'])}")
    print(f"文本总量 : {tot/1024:.0f} KB")
    print(f"根目录   : {idx['root']}")
    print(f"生成时间 : {idx['generated']}")
    print(f"产物     : index.json / index.tsv / catalog.md / FULL-BUNDLE.md / browse.html")
    print(f"全量库   : skillctl stats   （101 仓库 / 3000+ 深度技能条目）")

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    c, rest = a[0], a[1:]
    if c == 'rebuild':
        subprocess.run([sys.executable, os.path.join(HERE, 'build.py')])
        return
    fn = {'list': cmd_list, 'find': cmd_find, 'show': cmd_show, 'path': cmd_path,
          'cat': cmd_cat, 'stats': cmd_stats}.get(c)
    if fn:
        fn(rest)
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
