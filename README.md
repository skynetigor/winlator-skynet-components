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
| `type` | Component type (`DXVK`, `Box64`, `FEXCore`, `RendererDriver` for Adrenotools Turnip zips, `Container` for game configs, ...). |
| `verName` | Version string the app uses internally. For ARM64EC builds it must contain `arm64ec`, the app filters on that. |
| `verCode` | Integer version, bump it when you republish the same `id`. |
| `remoteUrl` | Direct download URL of the `.wcp`. |
| `channel` | Optional: `stable` or `prerelease`; the app shows it as a badge. No badge when absent. |

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

## Game containers

Ready-made container configs, shown in the app under **+ > For a game** (pick a game, then a game version, then a config).

```
containers/
  <game-slug>/
    game.json                  {"name": "Display name"}
    <game-version>/
      <config>.wcfg            a Winlator container profile (exported from the app)
      configs.json             optional, {"<config>.wcfg": {"name", "description", "tags"}}
```

`contents.json` lists each config as a flat `Container` entry:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier, like every other entry. |
| `name` | Config display name. Free text. |
| `gameId`, `gameName` | Game slug (the directory) and display name. |
| `gameVersion` | Game version (the directory). Newest is listed first in the app. |
| `description`, `tags` | Shown under the config name. Optional. |
| `channel` | Optional badge: `stable` or `prerelease`. Also valid on component and driver entries. No badge when absent. |
| `remoteUrl` | Direct link to the `.wcfg`. |

Don't edit those entries by hand. Add or change files under `containers/` and run:

```sh
python3 scripts/containers/build-registry.py
```

It rewrites only the `Container` entries of `contents.json`. A config's components (Proton, DXVK, drivers...) are downloaded by the app when the container is created.

## Game profiles (games.json)

Per-game launch settings for Steam games, read by the app to pick the right executable, arguments and tweaks for the installed game version.

```
games.json                     index: {"schema": 1, "games": [{"id", "name", "steamAppId", "config"}]}
games/<id>.json                one file per game; "config" is always "games/<id>.json"
```

A game file has `steam` (`appId`, `installDir`), `defaults` and `versions`. A version has `id`, `label`, `status` (`works`, `untested` or `broken`), optional `testedOn`, `notes`, `default` and `match`, plus any `defaults` key it wants to override.

**Matching.** The app picks the first version, in the order of the file, that any one of its `match` detectors recognises in the game's folder; a Steam build id is only known for games Steam installed, so the file detectors are what recognise a game that is not from Steam. A version the user chose by hand always wins.

| Detector | Meaning |
| --- | --- |
| `steamBuildId` | `{from, until}` integers, `from` inclusive, `until` exclusive, either may be missing. Ranges of one game must not overlap. |
| `versionFile` | Reads `head` or `tail` bytes (1..65536, exactly one) of `path` and applies `regex` (exactly one capture group); the result must be within `from` (inclusive) and `until` (exclusive), dotted versions compared as numbers. |
| `files` | `path` plus `size` and/or `sha256`. `sha256` is only for small files and needs a `size` <= 16777216. |

A version without `match` is only chosen explicitly or as the game's `default: true` entry (at most one per game), which is also used when detection finds nothing.

**Inheritance.** `defaults` is deep-merged with the chosen version. `env` and `extras` merge per key and a JSON `null` removes a key. `executable`, `args`, `resolution` (`native` or `WIDTHxHEIGHT`) and `noSteam` (`{"default": bool, "arg": "..."}`) are replaced as a whole.

**Extras allowlist.** `extras` may only use the keys in `ALLOWED_EXTRAS` at the top of `scripts/games/validate.py` (`--print-extras` lists them); values are strings.

A debug build of the app reads the branch named like the app branch, release builds read `main`. A copy of these files is bundled in the app (`assets/registry`) for offline use.

Check changes before committing:

```sh
python3 -I scripts/games/validate.py [--bundle <app>/app/src/main/assets/registry]
python3 -I scripts/games/validate.py --self-test
```

### Steam container (linux.json)

The top-level `steam` block of `linux.json` defines the automatically created Steam container: `runtime` (id from the external runtime catalog), `emulator` (a Box64 id from `emulators`), `emulatorPreset` (`STABILITY`, `COMPATIBILITY`, `INTERMEDIATE` or `PERFORMANCE`), `driver` (an id from `drivers`), `glDriver` (`zink` or `software`) and `vulkanPresent` (`native` or `sw`).
