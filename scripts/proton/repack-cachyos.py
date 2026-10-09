#!/usr/bin/env python3
"""Repack a proton-cachyos release tarball into a Winlator Proton .wcp (tar.xz).

  repack-cachyos.py <proton-cachyos-*.tar.xz> <version-name> <output.wcp> [--llvm-strip PATH]

The Steam-style tarball (proton script, protonfixes, SLR files) becomes the layout Winlator expects
(see the Proton 11.0-2 package): bin/, lib/wine/{x86_64-unix,x86_64-windows,i386-windows}, share/wine,
prefixPack.txz (the default prefix under .wine/) and profile.json. Optional components that Winlator
supplies itself (DXVK, VKD3D, nvapi, Mono, Gecko, ...) are left out. ELF and PE files are stripped when
llvm-strip is available.
"""
import json, os, shutil, subprocess, sys, tarfile, tempfile

DESC = ('Experimental repack of proton-cachyos {rel} ({arch}). Stock CachyOS Wine, not built for Android; '
        'repacked for Winlator, untested.')


def strip(tool, root):
    if not tool:
        return
    for dirpath, _, names in os.walk(root):
        for n in names:
            p = os.path.join(dirpath, n)
            if os.path.islink(p):
                continue
            if n.endswith(('.dll', '.exe', '.drv', '.sys', '.ocx', '.cpl', '.acm', '.ax', '.tlb', '.mui')) or n.endswith('.so') or '.so.' in n or n in ('wine', 'wineserver', 'wine-preloader', 'wine64', 'wine64-preloader', 'msidb'):
                subprocess.run([tool, '--strip-unneeded' if '.so' in n or '.' not in n else '--strip-debug', p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    tool = None
    if '--llvm-strip' in sys.argv:
        tool = sys.argv[sys.argv.index('--llvm-strip') + 1]
        args = [a for a in args if a != tool]
    src, version, out = args[:3]
    rel = version.replace('exp-cachyos-', '')
    arch = 'arm64' if version.endswith('arm64') else ('x86_64_v3' if version.endswith('x86_64_v3') else 'x86_64')
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.check_call(['tar', '-xJf', src, '-C', tmp])
        root = os.path.join(tmp, os.listdir(tmp)[0], 'files')
        stage = os.path.join(tmp, 'stage')
        os.makedirs(os.path.join(stage, 'lib', 'wine'))
        os.makedirs(os.path.join(stage, 'share', 'wine'))
        shutil.copytree(os.path.join(root, 'bin'), os.path.join(stage, 'bin'), symlinks=True)
        unix = 'aarch64-unix' if arch == 'arm64' else 'x86_64-unix'
        for d in (unix, 'x86_64-windows', 'i386-windows', 'aarch64-windows'):
            p = os.path.join(root, 'lib', 'wine', d)
            if os.path.isdir(p):
                shutil.copytree(p, os.path.join(stage, 'lib', 'wine', d), symlinks=True)
        pre = os.path.join(stage, 'lib', 'wine', unix, 'wine-preloader')
        if os.path.exists(pre) and not os.path.exists(os.path.join(stage, 'bin', 'wine-preloader')):
            shutil.copy2(pre, os.path.join(stage, 'bin', 'wine-preloader'))
        for n in ('wine.inf', 'nls', 'fonts', 'winmd'):
            p = os.path.join(root, 'share', 'wine', n)
            q = os.path.join(stage, 'share', 'wine', n)
            if os.path.isdir(p):
                shutil.copytree(p, q, symlinks=True)
            elif os.path.exists(p):
                shutil.copy2(p, q)
        strip(tool, stage)

        pfx = os.path.join(root, 'share', 'default_pfx')
        with tarfile.open(os.path.join(stage, 'prefixPack.txz'), 'w:xz') as t:
            t.add(pfx, '.wine')
        profile = {'type': 'Proton', 'versionName': version.replace('exp-', 'exp-', 1), 'versionCode': 1,
                   'description': DESC.format(rel=rel, arch=arch), 'files': [],
                   'wine': {'binPath': 'bin', 'libPath': 'lib', 'prefixPack': 'prefixPack.txz'}}
        with open(os.path.join(stage, 'profile.json'), 'w') as f:
            json.dump(profile, f, indent=2)
        with tarfile.open(out, 'w:xz', preset=6) as t:
            t.add(os.path.join(stage, 'profile.json'), 'profile.json')
            for top in ('bin', 'lib', 'share', 'prefixPack.txz'):
                t.add(os.path.join(stage, top), top)
    print(out, os.path.getsize(out))


main()
