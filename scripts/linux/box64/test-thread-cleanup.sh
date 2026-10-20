#!/usr/bin/env bash
# Exercise the actual x86 thread-local destructor wrapper through a native ARM64 Box64.
set -euo pipefail
BOX64=$(realpath "${1:?path to freshly built Box64}")
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
x86_64-linux-gnu-gcc -O2 -pthread "$HERE/thread-cleanup-test.c" -o "$WORK/probe"
for mode in serial stress main; do
    timeout 30 env BOX64_NOBANNER=1 BOX64_LOG=0 BOX64_DYNACACHE=0 "$BOX64" "$WORK/probe" "$mode" | tee "$WORK/$mode.log"
    grep -q '^PASS:' "$WORK/$mode.log"
done
