#!/usr/bin/env python3
"""Check registry/: every id used by a game exists in containers/index.json, every .wcfg parses and is a profile of the platform its
index entry says (windows, the default, or linux), every game has programs to recognise it by (windows.executables or
linux.executables), every soc family used by a config or a game is in socs.json, and the desktops of ../linux.json are well formed. Run from anywhere: python3 registry/validate.py"""
import json, os, sys
R = os.path.dirname(os.path.abspath(__file__))
load = lambda p: json.load(open(os.path.join(R, p), encoding='utf-8'))
errors = []
RELATIVE = lambda p: isinstance(p, str) and p and not p.startswith('/') and '..' not in p and '\\' not in p
socs = {s['family'] for s in load('socs.json')['socs']}
configs = {}
for c in load('containers/index.json')['containers']:
    if c['id'] in configs: errors.append(f"duplicate config {c['id']}")
    configs[c['id']] = c
    platform = c.get('platform', 'windows')
    if platform not in ('windows', 'linux'): errors.append(f"{c['id']}: platform must be windows or linux")
    for s in c.get('socs', []):
        if s not in socs: errors.append(f"{c['id']}: unknown soc {s}")
    try:
        p = load(c['file'])
        if p.get('format') != 'winlator-skynet-container': errors.append(f"{c['file']}: not a container profile")
        kind = 'linux' if p['container'].get('type') == 'linux' else 'windows'
        if kind != platform: errors.append(f"{c['file']}: a {kind} profile listed as {platform}")
    except Exception as e:
        errors.append(f"{c['file']}: {e}")
for g in load('games.json')['games']:
    game = load(g['config'])
    if game['id'] != g['id']: errors.append(f"{g['config']}: id mismatch")
    programs = {k: game.get(k, {}).get('executables', []) for k in ('windows', 'linux')}
    if not programs['windows'] and not programs['linux']: errors.append(f"{g['id']}: no windows.executables or linux.executables")
    for k, exes in programs.items():
        for e in exes:
            if not RELATIVE(e): errors.append(f"{g['id']}: {k}.executables: {e!r} must be a relative path")
    defaults = [v for v in game['versions'] if v.get('default')]
    if len(defaults) != 1: errors.append(f"{g['id']}: needs exactly one default version")
    for v in game['versions']:
        ids = v.get('containers', [])
        # A version may list no configs at all (a Linux game without one yet); one that lists some names the preferred.
        if ids and v.get('preferredContainer') not in ids: errors.append(f"{g['id']} {v['id']}: preferredContainer not in containers")
        for i in ids + list(v.get('preferredBySoc', {}).values()):
            if i not in configs: errors.append(f"{g['id']} {v['id']}: unknown config {i}")
        for s in v.get('preferredBySoc', {}):
            if s not in socs: errors.append(f"{g['id']} {v['id']}: unknown soc {s}")
# linux.json (next to registry/): the desktops the app can install into a Linux runtime.
try:
    desktops = json.load(open(os.path.join(R, '..', 'linux.json'), encoding='utf-8')).get('desktops', [])
except Exception as e:
    desktops = []; errors.append(f"linux.json: {e}")
import re
seen = set()
for d in desktops:
    i = d.get('id', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', i) or i in seen: errors.append(f"linux.json desktops: bad or duplicate id {i!r}")
    seen.add(i)
    if not str(d.get('url', '')).startswith('https://'): errors.append(f"linux.json desktops {i}: url must be https")
    if not re.fullmatch(r'[0-9a-fA-F]{64}', str(d.get('sha256', ''))): errors.append(f"linux.json desktops {i}: sha256 must be 64 hex characters")
    if not isinstance(d.get('size'), int) or d['size'] <= 0: errors.append(f"linux.json desktops {i}: size must be a positive integer")
print('\n'.join(errors) or 'ok'); sys.exit(1 if errors else 0)
