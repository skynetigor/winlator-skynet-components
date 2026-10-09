#!/usr/bin/env python3
"""Regenerate the "Container" entries of contents.json from the containers/ tree.

Layout:
  containers/<game-slug>/game.json             {"name": "Display name"}
  containers/<game-slug>/<version>/<x>.wcfg     a Winlator container profile
  containers/<game-slug>/<version>/configs.json optional {"<x>.wcfg": {"name", "description", "tags", "channel": "stable"|"prerelease"}}

Other entries in contents.json are left untouched. Run from anywhere:
  python3 scripts/containers/build-registry.py
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = 'https://raw.githubusercontent.com/skynetigor/winlator-skynet-components/main/'
REGISTRY = os.path.join(ROOT, 'contents.json')
TREE = os.path.join(ROOT, 'containers')


def load(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    entries = []
    for game in sorted(os.listdir(TREE)):
        game_dir = os.path.join(TREE, game)
        if not os.path.isdir(game_dir):
            continue
        game_name = (load(os.path.join(game_dir, 'game.json'), {}) or {}).get('name', game)
        for version in sorted(os.listdir(game_dir)):
            version_dir = os.path.join(game_dir, version)
            if not os.path.isdir(version_dir):
                continue
            meta = load(os.path.join(version_dir, 'configs.json'), {}) or {}
            for fname in sorted(os.listdir(version_dir)):
                if not fname.endswith('.wcfg'):
                    continue
                profile = load(os.path.join(version_dir, fname))
                if profile.get('format') != 'winlator-skynet-container':
                    sys.exit(f'{fname}: not a winlator-skynet-container profile')
                info = meta.get(fname, {})
                stem = fname[:-len('.wcfg')]
                entries.append({
                    'id': f'container-{game}-{version}-{stem}',
                    'name': info.get('name') or profile.get('container', {}).get('name', stem),
                    'type': 'Container',
                    'gameId': game,
                    'gameName': game_name,
                    'gameVersion': version,
                    'description': info.get('description', ''),
                    'tags': info.get('tags', []),
                    **({'channel': info['channel']} if info.get('channel') in ('stable', 'prerelease') else {}),
                    'verName': version,
                    'verCode': 1,
                    'remoteUrl': f'{RAW}containers/{game}/{version}/{fname}',
                })

    ids = [e['id'] for e in entries]
    if len(ids) != len(set(ids)):
        sys.exit('duplicate container ids')

    registry = load(REGISTRY, [])
    others = [e for e in registry if e.get('type') != 'Container']
    clash = {e['id'] for e in others} & set(ids)
    if clash:
        sys.exit(f'ids clash with existing entries: {sorted(clash)}')
    with open(REGISTRY, 'w', encoding='utf-8') as f:
        json.dump(others + entries, f, indent=2)
        f.write('\n')
    print(f'{len(entries)} container entries, {len(others)} other entries')


main()
