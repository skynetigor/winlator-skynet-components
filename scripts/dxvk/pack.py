#!/usr/bin/env python3
"""Pack DXVK DLLs into Winlator .wcp files (tar.xz with profile.json).

  pack.py <version> <upstream-tar.gz> <arm64ec-build-dir> <output-dir>

Writes dxvk-<version>.wcp (x86_64) and dxvk-<version>-arm64ec.wcp.
<arm64ec-build-dir> is the <output-dir> given to build-arm64ec.sh.
"""
import json, os, shutil, subprocess, sys, tarfile, tempfile

DLLS = ['d3d10core', 'd3d11', 'd3d8', 'd3d9', 'dxgi']


def profile(ver, desc):
    files = [{'source': f'{d}/{n}.dll', 'target': f'${{{d}}}/{n}.dll'}
             for d in ('system32', 'syswow64') for n in DLLS]
    return {'type': 'DXVK', 'versionName': ver, 'versionCode': 1, 'description': desc, 'files': files}


def pack(stage, out, prof):
    with open(f'{stage}/profile.json', 'w') as f:
        json.dump(prof, f, indent=2)
    with tarfile.open(out, 'w:xz') as t:
        t.add(f'{stage}/profile.json', 'profile.json')
        for d in ('system32', 'syswow64'):
            for n in DLLS:
                t.add(f'{stage}/{d}/{n}.dll', f'{d}/{n}.dll')


def main():
    v, tgz, ec_dir, out = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.check_call(['tar', '-xzf', tgz, '-C', tmp])
        up = f'{tmp}/dxvk-{v}'
        for kind in ('x86_64', 'arm64ec'):
            st = f'{tmp}/stage-{kind}'
            os.makedirs(f'{st}/system32'); os.makedirs(f'{st}/syswow64')
            for n in DLLS:
                shutil.copy(f'{up}/x32/{n}.dll', f'{st}/syswow64/{n}.dll')
                src = f'{up}/x64' if kind == 'x86_64' else f'{ec_dir}/{v}/system32'
                shutil.copy(f'{src}/{n}.dll', f'{st}/system32/{n}.dll')
            if kind == 'x86_64':
                pack(st, f'{out}/dxvk-{v}.wcp', profile(v, f'Official DXVK {v} (x86 and x86_64)'))
            else:
                pack(st, f'{out}/dxvk-{v}-arm64ec.wcp',
                     profile(f'{v}-arm64ec', f'Official DXVK {v} built for ARM64EC (x86 in syswow64)'))


main()
