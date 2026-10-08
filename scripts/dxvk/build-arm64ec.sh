#!/bin/bash
# Build the ARM64EC DXVK DLLs for one upstream tag.
#
#   scripts/dxvk/build-arm64ec.sh <version> <dxvk-checkout> <output-dir>
#
# Needs on PATH: llvm-mingw (arm64ec-w64-mingw32-* tools), meson, ninja, glslang.
# <dxvk-checkout> is a clone of https://github.com/doitsujin/dxvk.
# Output: <output-dir>/<version>/system32/{d3d8,d3d9,d3d10core,d3d11,dxgi}.dll
set -euo pipefail
V=$1; SRC=$(cd "$2" && pwd); OUT=$3
HERE=$(cd "$(dirname "$0")" && pwd)

git -C "$SRC" checkout -q -f "v$V"
git -C "$SRC" submodule update -q --init --recursive
rm -rf "$SRC/build-ec"
# The include flags work around old DXVK sources (3.0) that relied on libstdc++ pulling these in.
( cd "$SRC" && meson setup --cross-file "$HERE/arm64ec.cross.txt" --buildtype release --strip \
    -Dcpp_args="['-include','new','-include','memory','-include','algorithm']" build-ec \
  && ninja -C build-ec )

mkdir -p "$OUT/$V/system32"
for pair in d3d8:d3d8 d3d9:d3d9 d3d10:d3d10core d3d11:d3d11 dxgi:dxgi; do
  cp "$SRC/build-ec/src/${pair%%:*}/${pair##*:}.dll" "$OUT/$V/system32/"
done
