#!/usr/bin/env python3
"""Check registry/: every id used by a game exists in containers/index.json, every .wcfg parses and is a Windows profile, every soc
family used by a config or a game is in socs.json. Run from anywhere: python3 registry/validate.py"""
import json, os, sys
R = os.path.dirname(os.path.abspath(__file__))
load = lambda p: json.load(open(os.path.join(R, p), encoding='utf-8'))
errors = []
socs = {s['family'] for s in load('socs.json')['socs']}
configs = {}
for c in load('containers/index.json')['containers']:
    if c['id'] in configs: errors.append(f"duplicate config {c['id']}")
    configs[c['id']] = c
    for s in c.get('socs', []):
        if s not in socs: errors.append(f"{c['id']}: unknown soc {s}")
    try:
        p = load(c['file'])
        if p.get('format') != 'winlator-skynet-container': errors.append(f"{c['file']}: not a container profile")
        if p['container'].get('type') == 'linux': errors.append(f"{c['file']}: Linux profile in the Windows registry")
    except Exception as e:
        errors.append(f"{c['file']}: {e}")
for g in load('games.json')['games']:
    game = load(g['config'])
    if game['id'] != g['id']: errors.append(f"{g['config']}: id mismatch")
    if not game.get('windows', {}).get('executables'): errors.append(f"{g['id']}: no windows.executables")
    defaults = [v for v in game['versions'] if v.get('default')]
    if len(defaults) != 1: errors.append(f"{g['id']}: needs exactly one default version")
    for v in game['versions']:
        ids = v.get('containers', [])
        if v.get('preferredContainer') not in ids: errors.append(f"{g['id']} {v['id']}: preferredContainer not in containers")
        for i in ids + list(v.get('preferredBySoc', {}).values()):
            if i not in configs: errors.append(f"{g['id']} {v['id']}: unknown config {i}")
        for s in v.get('preferredBySoc', {}):
            if s not in socs: errors.append(f"{g['id']} {v['id']}: unknown soc {s}")
print('\n'.join(errors) or 'ok'); sys.exit(1 if errors else 0)
