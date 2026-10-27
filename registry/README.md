# Registry

What the SkyNetEmu app reads to recognise a game and set it up. The app downloads these files from the `main` branch and keeps each for a few hours (the index and the processor map for 6, the rest for 24), so a change here reaches installed apps on its own. A copy is bundled in every app build (`app/src/main/assets/registry/`) for when there is no network; update it from this folder when you make a release.

```
games.json                 index: [{id, name, steamAppId?, config: "games/<id>.json"}]
games/<id>.json            one game: its exes, defaults and versions
containers/index.json      the container configs
containers/<config>.wcfg   a config: a container profile exported by the app (format winlator-skynet-container v1)
socs.json                  processor models (what Android reports) to families
validate.py                checks all of the above: python3 registry/validate.py
```

## A game (`games/<id>.json`)

```json
{"schema":1,"id":"beamng-drive","name":"BeamNG.drive","steam":{"appId":284160},
 "windows":{"executables":["BeamNG.drive.exe","Bin64/BeamNG.drive.x64.exe"]},
 "defaults":{"args":[],"extras":{}},
 "versions":[
  {"id":"0.34","label":"0.34.x","status":"works",
   "match":{"versionFile":{"path":"integrity.json","tail":256,"regex":"\"version\":\\s*\"([0-9.]+)\"","from":"0.34","until":"0.35"}},
   "containers":["proton11-x64-box64-turnip-stable","cachyos-x64-box64-dd-turnip"],
   "preferredContainer":"proton11-x64-box64-turnip-stable",
   "preferredBySoc":{"snapdragon-8-gen-3":"..."}}]}
```

- `windows.executables`: the exe the user picks is this game when its path ends with one of these (any case). The rest of the path is the game's folder.
- `linux.executables`: the same for a Linux program or script the user picks (`BinLinux/BeamNG.drive.x64`). A game may have `windows`, `linux` or both; the picked file's kind (Wine program, ELF program, shell script) says which list is used. A game file from before this key that names one executable under `defaults.executable` and has no `windows.executables` is taken as a Linux game.
- `windows.defaults` and `linux.defaults`: settings (`args`, `env`, `resolution`, `extras`) for that platform only, laid over the game's `defaults`; a version can say the same under its own `windows` or `linux` object. The order is: `defaults`, the platform's `defaults`, the version's settings, the version's platform settings.
- `match`: how a version is recognised from the folder: `versionFile`, `files` (size or sha256) or `steamBuildId`. Exactly one version has `"default": true`; it is used when none matches.
- `containers`: the configs that work for this version. `preferredContainer`: the one a new shortcut gets. `preferredBySoc`: per processor family, wins over `preferredContainer`.
- `args` and `extras` (allowed keys only, see `GameProfile.ALLOWED_EXTRAS` in the app) are written into the new shortcut.
- `status`: `works`, `untested` or `broken`.

### BeamNG.drive display defaults

All listed BeamNG.drive versions (0.20, 0.28, 0.31, 0.34, 0.39 and 0.40), on Linux and Windows including ARM64,
inherit a **955x560** resolution, **scale game window to fit the screen** (`fullscreenStretched: "2"`),
and **FSR upscaling** (`graphicsFilterMode: "3"`) from the shared game defaults (profile revision 10).
The 0.40 Linux profile no longer overrides the resolution with `native`.
Explicit shortcut display settings still take precedence; this catalog update does not overwrite user overrides.
FSR requires the app's Vulkan renderer; this update does not change renderer or driver selection.

## A config (`containers/index.json`)

`id`, `name`, `file` (`containers/<name>.wcfg`), `description`, `socs` (families it was made for, empty for any), `channel` (`stable` or `prerelease`), `tags`, `testedOn`. `platform`: `windows` (the default) or `linux`; a Linux config's `.wcfg` is the profile of a Linux container (type `linux`), a Windows one's a Wine container, and `validate.py` checks they agree. A game on Linux gets only Linux configs offered, a Windows exe only Windows ones. A config belongs to no game; several games can list it. Two shortcuts with the same config and the same Wine share one container.

## How the app chooses a config

1. `preferredBySoc` for the device's processor family.
2. `preferredContainer`, if its `socs` is empty or includes the family.
3. The first listed config made for the family.
4. `preferredContainer` anyway, marked "not tested on your processor".

## Adding a device

Add its model (`Build.SOC_MODEL`, for example `SM8850`) and family to `socs.json`; no app update is needed.

## Android renderer drivers (`renderer-drivers.json`)

Automatic renderer selection uses exact Adreno model mappings and Android API ranges in this catalog, separately from game/SoC profiles and Linux game drivers. Native Vulkan output requires an entry with `dmaBufImport: true`. Increment `revision` when changing mappings so a newer bundled catalog does not override the update.

Adreno 810 (including Android API 36) maps to **Turnip Gen8 V30**, alongside Adreno 830. [Upstream](https://github.com/StevenMXZ/Adreno-Tools-Drivers/releases/tag/gen_8_v30) lists experimental support for both models. The package checksum, Android driver layout, and binary support markers were checked; Steam rendering and DMA-BUF import on an Adreno 810 device remain untested. `testedGpus` stays empty until device validation.

This is a remote catalog update, not an APK update. Refresh the app's registry while online and retry with the shortcut's Renderer driver set to Auto.

## The Linux desktop (`../linux.json`, `desktops`)

The XFCE desktop a Linux container opens when it is started without a program is not in the runtime. It is a tarball of the files the runtime lacks, listed here:

```json
"desktops": [{"id":"xfce-4.20.4","name":"XFCE","version":"4.20.4","channel":"prerelease",
              "url":"https://github.com/.../releases/download/linux-desktop-xfce-4.20.4/xfce-4.20.4.tar.zst",
              "sha256":"...","size":5601493}]
```

The app downloads the first entry, checks it, and adds its files to every installed Linux runtime (never replacing one). The tarball is made by `tools/xfce-bundle/build.sh` of the SkyNetEmu repository from pinned Arch Linux ARM packages; the script prints this entry. Publish the file as a release of this repository and add the entry; `validate.py` checks its shape.
