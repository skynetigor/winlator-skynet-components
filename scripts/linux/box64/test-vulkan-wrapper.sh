#!/usr/bin/env bash
# Exercise Box64's actual Vulkan proc-address wrappers without a GPU. The native mock driver exposes a function
# Box64 cannot wrap, reproducing the vkCmdDispatchTileQCOM lookup that crashed during game startup.
set -euo pipefail
BOX64=$(realpath "${1:?path to the freshly built Box64}")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/native"

cat > "$WORK/driver.c" <<'C'
#include <string.h>
static void unwrapped(void) {}
void *vkGetInstanceProcAddr(void *instance, const char *name);
void *vkGetDeviceProcAddr(void *device, const char *name);
void *vkGetInstanceProcAddr(void *instance, const char *name) {
    (void)instance;
    if (!strcmp(name, "vkGetInstanceProcAddr")) return vkGetInstanceProcAddr;
    if (!strcmp(name, "vkGetDeviceProcAddr")) return vkGetDeviceProcAddr;
    if (!strcmp(name, "vkCmdDispatchTileQCOM") || !strcmp(name, "vkSkyNetUnwrappedProbe")) return unwrapped;
    return 0;
}
void *vkGetDeviceProcAddr(void *device, const char *name) {
    return vkGetInstanceProcAddr(device, name);
}
C

cat > "$WORK/guest.c" <<'C'
#include <dlfcn.h>
#include <stdio.h>
typedef void *(*get_proc)(void *, const char *);
int main(void) {
    void *library = dlopen("libvulkan.so.1", RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    const char *names[] = {"vkGetInstanceProcAddr", "vkGetDeviceProcAddr"};
    for (int i = 0; i < 2; ++i) {
        get_proc get = (get_proc)dlsym(library, names[i]);
        if (!get || !get(0, names[i])) return 2;
        if (get(0, "vkCmdDispatchTileQCOM")) return 3;
        if (get(0, "vkSkyNetUnwrappedProbe")) return 4;
        if (get(0, "vkCreateInstance")) return 5;
        printf("PASS %s: known function resolves; unsupported and absent functions return NULL\n", names[i]);
    }
    dlclose(library);
    return 0;
}
C

gcc -shared -fPIC -Wl,-soname,libvulkan.so.1 -o "$WORK/native/libvulkan.so.1" "$WORK/driver.c"
x86_64-linux-gnu-gcc -o "$WORK/guest" "$WORK/guest.c" -ldl
LD_LIBRARY_PATH="$WORK/native${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" BOX64_NOBANNER=1 "$BOX64" "$WORK/guest"
