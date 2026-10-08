# Winlator skyNET components

Catalog of extra components for Winlator skyNET. The app reads `contents.json` and installs each `remoteUrl` as a `.wcp` (tar.xz).

Set **Downloadable contents URL** to:

https://raw.githubusercontent.com/skynetigor/winlator-skynet-components/main/contents.json

The binaries are **not** stored in git. Each one is a GitHub Release asset, with the source, toolchain, checksums and install notes in the release description. Tags are named `<component>-<version>`.

## contents.json format

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier. Never changes once published, even if the name, version or URL do. |
| `name` | Display name. Free text, can be changed at any time. |
| `type` | Component type (`DXVK`, `Box64`, `FEXCore`, `RendererDriver` for Adrenotools Turnip zips, ...). |
| `verName` | Version string the app uses internally. For ARM64EC builds it must contain `arm64ec`, the app filters on that. |
| `verCode` | Integer version, bump it when you republish the same `id`. |
| `remoteUrl` | Direct download URL of the `.wcp`. |

## DXVK 3

Official [DXVK](https://github.com/doitsujin/dxvk) 3.x releases. Every release has two packages:

- `dxvk-<version>.wcp` (x86_64): the upstream x64 DLLs in `system32` and x86 DLLs in `syswow64`.
- `dxvk-<version>-arm64ec.wcp`: DLLs built from the upstream tag with llvm-mingw (`arm64ec-w64-mingw32`) in `system32`, and the upstream x86 DLLs in `syswow64`.

| Version | Release |
| --- | --- |
| 3.1.1 | [dxvk-3.1.1](https://github.com/skynetigor/winlator-skynet-components/releases/tag/dxvk-3.1.1) |
| 3.1 | [dxvk-3.1](https://github.com/skynetigor/winlator-skynet-components/releases/tag/dxvk-3.1) |
| 3.0.2 | [dxvk-3.0.2](https://github.com/skynetigor/winlator-skynet-components/releases/tag/dxvk-3.0.2) |
| 3.0.1 | [dxvk-3.0.1](https://github.com/skynetigor/winlator-skynet-components/releases/tag/dxvk-3.0.1) |
| 3.0 | [dxvk-3.0](https://github.com/skynetigor/winlator-skynet-components/releases/tag/dxvk-3.0) |

### Rebuilding

`scripts/dxvk/` has the build recipe used for the arm64ec DLLs and the packer:

```sh
# needs llvm-mingw, meson, ninja, glslang on PATH, and a clone of doitsujin/dxvk
scripts/dxvk/build-arm64ec.sh 3.1.1 ~/src/dxvk out
scripts/dxvk/pack.py 3.1.1 dxvk-3.1.1.tar.gz out dist
```

`dxvk-3.1.1.tar.gz` is the asset from the upstream release.
