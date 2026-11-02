# FEX for Android (bionic)

FEX-2610 built as an Android program (no glibc runtime, no PRoot) so a Linux x86-64 game can run straight from the app.
`build.sh` clones FEX, applies `patches/` in name order and builds `FEX`, `FEXServer` and `FEXOfflineCompiler` for arm64.

    ANDROID_NDK_HOME=/path/to/ndk-r29 ./build.sh [out]        # KEEP_SYMBOLS=1 also writes *.debug (unstripped) copies

## Patches

| # | What |
|---|---|
| 0001 | Accept Android/bionic in the build (POSIX shm via `FEX_SHM_DIR`, `memfd_create`, `getdents64`, `valloc`, libc++ differences, `<elf.h>` types) |
| 0002 | Clang 23 removed `FileManager::clearStatCache` in the thunk generator |
| 0003 | Separate the guest environment from the host process environment |
| 0004 | Report `set_robust_list` as unsupported (Android) |
| 0005 | Use Android's `accept4` |
| 0006 | Preserve the native loader environment |
| 0007 | Report protection keys as unavailable |
| 0008 | Open the real Android `/proc` directory |
| 0009 | Route Vulkan debug-callback proc addresses (thunk correctness) |
| 0010 | Code cache: skip guest libs that have no backing file (the VDSO thunk mapping); without this FEX crashes at startup with `FEX_ENABLECODECACHINGWIP=1` |
| 0011 | Code cache: make relocation offsets buffer-relative when generating a cache (see below) |

## Code cache status (`FEX_ENABLECODECACHINGWIP=1`, experimental)

FEX's persistent code cache is marked work-in-progress upstream. Findings on Android (FEX-2610, SM-F976B):

* Recording works: each run writes code maps to `<cache>/fex-emu/codemap/`. On the next launch FEXServer merges them and runs
  `FEXOfflineCompiler generate <codemap>` (it must sit beside `FEXServer`) to write `<cache>/fex-emu/cache/*`.
* **Bug fixed by 0011:** the JIT records relocation offsets relative to the temporary buffer of each compile unit, but
  `CodeCache::SaveData` and the loader treat them as offsets into the whole shared code buffer. Only the first compile units'
  relocations landed in valid places; the others kept the generating process's `ExitFunctionLinker` address (found as 208 raw
  copies in one cache file), so loading a cache jumped to an unmapped address. With 0011 caches load and the game runs.
* `FEX_ENABLECODECACHEVALIDATION=1` still crashes in `GenerateIR` while ELF files are being mapped (not investigated further).
* Measured benefit is small once the game's Lua JIT is off (BeamNG West Coast, single car: 72/66/61 FPS average with cache vs
  71/55/57 without, 1% lows 41/31/29 vs 31/24/21; with 3 AI cars: 50-53 vs 47-54, lows unchanged at about 8-9). Caches are
  about 300 MB for BeamNG. The app does not enable or ship the cache yet.
* Upstream (`FEX-Emu/FEX` main, checked 2026-11-02) has the same relocation recording and no later cache commits.

## Provenance

The tag, flags and patch order match the earlier `SkyNetEmuTools/tools/linux-fex-bionic/build.sh`, plus patches 0010/0011 and the
offline compiler target. The SkyNetEmu app packages the stripped `FEX` and `FEXServer` from this script
(`app/src/main/assets/linux-fex-bionic/`); `FEXOfflineCompiler` is built but not shipped. A rebuild is not byte-identical to an
earlier build (the toolchain embeds paths), so compare behavior, not hashes.
