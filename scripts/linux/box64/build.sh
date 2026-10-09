#!/usr/bin/env bash
# Builds Box64 for the Winlator skyNET Linux runtime: a glibc aarch64 build (NOT the Android/bionic one that Wine
# containers use), packaged as a tar.zst the app installs under files/linux-emulators/<id>/.
#
#   build.sh <box64 tag> <output dir>
#
# Needs an aarch64 Linux machine (GitHub runner ubuntu-24.04-arm) with: git cmake make gcc python3 zstd binutils
# and, for the smoke test, gcc-x86-64-linux-gnu.
set -euo pipefail

TAG=${1:?box64 tag, e.g. v0.4.4}
OUT=${2:?output dir}
WORK=$(mktemp -d)
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

VERSION=${TAG#v}
NAME=box64-${VERSION}-linux-aarch64

# A full clone: shallow clones choke on tags.
git clone https://github.com/ptitSeb/box64.git "$WORK/src"
git -C "$WORK/src" checkout "$TAG"
COMMIT=$(git -C "$WORK/src" rev-parse HEAD)

# Our patches (scripts/linux/box64/patches/*.patch), applied in name order.
PATCHES=()
for patch in "$(cd "$(dirname "$0")" && pwd)"/patches/*.patch; do
  [ -e "$patch" ] || continue
  git -C "$WORK/src" apply "$patch"
  PATCHES+=("$(basename "$patch")")
done
PATCH_JSON=$(printf '"%s",' "${PATCHES[@]}" | sed 's/,$//')

# Generic arm64 (no -march tuning for one CPU), dynarec on, the x86_64 libs Box64 does not wrap bundled in.
# ANDROID / TERMUX / WINLATOR_GLIBC stay off: this is a plain glibc build.
cmake -S "$WORK/src" -B "$WORK/build" \
  -DARM_DYNAREC=ON \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DBUNDLE_X86_LIBS=ON \
  -DNO_CONF_INSTALL=ON
cmake --build "$WORK/build" -j"$(nproc)"
make -C "$WORK/build" install DESTDIR="$WORK/stage"

# Re-root the install into the package layout: bin/box64 and lib/box64-x86_64-linux-gnu/.
PKG=$WORK/pkg/$NAME
mkdir -p "$PKG/bin" "$PKG/lib"
install -m755 "$(find "$WORK/stage" -type f -name box64 | head -1)" "$PKG/bin/box64"
LIBS=$(find "$WORK/stage" -type d -name box64-x86_64-linux-gnu | head -1)
if [ -n "$LIBS" ]; then cp -a "$LIBS" "$PKG/lib/box64-x86_64-linux-gnu"; fi
cp "$WORK/src/LICENSE" "$PKG/LICENSE"

# The highest glibc symbol version the binary needs: the runtime's glibc must be at least that new.
MIN_GLIBC=$(objdump -T "$PKG/bin/box64" | grep -o 'GLIBC_[0-9.]*' | sort -V | tail -1 | sed 's/GLIBC_//')
cat > "$PKG/meta.json" <<JSON
{
  "schemaVersion": 1,
  "kind": "linux-emulator",
  "emulator": "box64",
  "name": "Box64",
  "version": "$VERSION",
  "arch": "aarch64",
  "libc": "glibc",
  "minGlibc": "$MIN_GLIBC",
  "upstream": {"repo": "https://github.com/ptitSeb/box64", "tag": "$TAG", "commit": "$COMMIT"},
  "patches": [${PATCH_JSON}],
  "build": {
    "cmake": "-DARM_DYNAREC=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUNDLE_X86_LIBS=ON -DNO_CONF_INSTALL=ON",
    "gcc": "$(gcc -dumpfullversion)",
    "cmakeVersion": "$(cmake --version | head -1 | awk '{print $3}')",
    "host": "$(. /etc/os-release && echo "$PRETTY_NAME")"
  }
}
JSON

# Smoke test: the freshly built binary must run an x86_64 program, static and dynamic.
cat > "$WORK/hello.c" <<'C'
#include <stdio.h>
int main(void) { puts("hello from x86_64 through box64"); return 0; }
C
if command -v x86_64-linux-gnu-gcc >/dev/null; then
  x86_64-linux-gnu-gcc -static -o "$WORK/hello_static" "$WORK/hello.c"
  x86_64-linux-gnu-gcc -o "$WORK/hello_dynamic" "$WORK/hello.c"
  BOX64_NOBANNER=1 BOX64_LD_LIBRARY_PATH="$PKG/lib/box64-x86_64-linux-gnu" "$PKG/bin/box64" "$WORK/hello_static" | tee "$WORK/smoke.txt"
  BOX64_NOBANNER=1 BOX64_LD_LIBRARY_PATH="$PKG/lib/box64-x86_64-linux-gnu" "$PKG/bin/box64" "$WORK/hello_dynamic" | tee -a "$WORK/smoke.txt"
  test "$(grep -c 'hello from x86_64' "$WORK/smoke.txt")" = 2
else
  echo "x86_64 cross compiler missing: smoke test skipped" >&2
fi

# Package. tar keeps the directory entries the app's extractor relies on.
tar -C "$WORK/pkg" -cf - "$NAME" | zstd -19 -T0 -o "$OUT/$NAME.tar.zst"
( cd "$OUT" && sha256sum "$NAME.tar.zst" > "$NAME.tar.zst.sha256" )
cp "$PKG/meta.json" "$OUT/$NAME.meta.json"
ls -l "$OUT"
cat "$OUT/$NAME.tar.zst.sha256"
