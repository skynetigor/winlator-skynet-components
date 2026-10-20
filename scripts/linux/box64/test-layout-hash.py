#!/usr/bin/env python3
"""Verify the patched Box64 cache hash rejects machine code built for an older emulator layout."""
import importlib.util
from pathlib import Path
import re
import sys
import tempfile

spec = importlib.util.spec_from_file_location("dynacache_hashes", Path(sys.argv[1]) / "tools/gen_dynacache_hashes.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

with tempfile.TemporaryDirectory(prefix="box64-layout-hash-") as work:
    root = Path(work)
    for relative in ("src/dynarec/common.c", "src/dynarec/arm64/backend.c", "src/dynarec/la64/backend.c",
                     "src/dynarec/rv64/backend.c", "src/dynarec/ppc64le/backend.c",
                     "src/emu/x64emu_private.h", "src/include/box64context.h"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("/* fixture */\n")
    before = generator.render_header(root)
    for relative in ("src/emu/x64emu_private.h", "src/include/box64context.h"):
        with (root / relative).open("a") as out:
            out.write("/* changed layout */\n")
        after = generator.render_header(root)
        common = lambda text: re.search(r"#define DYNAREC_VERSION (\S+)", text).group(1)
        assert common(before) != common(after), f"Layout change not hashed: {relative}"
        assert re.findall(r"#define ARCH_VERSION (\S+)", before) == re.findall(r"#define ARCH_VERSION (\S+)", after)
        before = after
print("PASS: both emulator layout headers invalidate the translated-code cache")
