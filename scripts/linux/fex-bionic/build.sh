#!/bin/sh
# Builds FEX (the x86-64 emulator) as an Android (bionic) program: FEX, FEXServer and FEXOfflineCompiler.
#
#   ANDROID_NDK_HOME=/path/to/ndk-r29 ./build.sh [output folder]        (default: ./out)
#
# Needs git, cmake, ninja, python3 and an NDK (r29 was used). Clones FEX-2610 (FEX_TAG overrides), applies patches/*.patch in
# name order, builds Release without jemalloc (and without LTO unless FEX_LTO=ON) and writes stripped binaries. Set KEEP_SYMBOLS=1 to build with -g and also leave
# the symbolized binaries (*.debug, about 50 MB each) beside them, for profiling and for symbolizing crash addresses.
#
# The GPU thunks (Vulkan host side) are not built here; the app packages a matching libvulkan-host.so separately.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HERE/out}
NDK=${ANDROID_NDK_HOME:-/opt/homebrew/share/android-commandlinetools/ndk/29.0.14206865}
TAG=${FEX_TAG:-FEX-2610}
WORK=${WORK:-$(mktemp -d)}

git clone --branch "$TAG" --depth 1 https://github.com/FEX-Emu/FEX.git "$WORK/src"
# Three submodules hold test binaries (large, and a clone that fails half way stops the build); the build does not use them.
for module in fex-posixtest-bins fex-gvisor-tests-bins fex-gcc-target-tests-bins; do
  git -C "$WORK/src" config "submodule.External/$module.update" none
done
git -C "$WORK/src" submodule update --init --depth 1 --jobs 4 --recursive
for patch in "$HERE"/patches/*.patch; do
  git -C "$WORK/src" apply "$patch"
done

cmake -S "$WORK/src" -B "$WORK/build" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTS=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_THUNKS=OFF \
  -DENABLE_JEMALLOC=OFF -DENABLE_JEMALLOC_GLIBC_ALLOC=OFF -DENABLE_LTO=${FEX_LTO:-OFF} \
  -DENABLE_OFFLINE_TELEMETRY=OFF -DHAS_CLANG_PRESERVE_ALL=OFF -DENABLE_CCACHE=OFF \
  -DTUNE_ARCH=armv8.4-a -DTUNE_CPU=generic ${KEEP_SYMBOLS:+-DCMAKE_C_FLAGS=-g -DCMAKE_CXX_FLAGS=-g}
# FEX links with --strip-all; drop it when symbols are wanted
[ -n "$KEEP_SYMBOLS" ] && sed -i.bak 's/-Xlinker --strip-all//g' "$WORK/build/build.ninja"
cmake --build "$WORK/build" --target Bin/FEX Bin/FEXServer Bin/FEXOfflineCompiler

STRIP=$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/llvm-strip)
mkdir -p "$OUT"
for name in FEX FEXServer FEXOfflineCompiler; do
  "$STRIP" -o "$OUT/$name" "$WORK/build/Bin/$name"
  [ -n "$KEEP_SYMBOLS" ] && cp "$WORK/build/Bin/$name" "$OUT/$name.debug"
done
ls -l "$OUT"
