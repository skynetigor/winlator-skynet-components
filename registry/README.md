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
- `match`: how a version is recognised from the folder: `versionFile`, `files` (size or sha256) or `steamBuildId`. Exactly one version has `"default": true`; it is used when none matches.
- `containers`: the configs that work for this version. `preferredContainer`: the one a new shortcut gets. `preferredBySoc`: per processor family, wins over `preferredContainer`.
- `args` and `extras` (allowed keys only, see `GameProfile.ALLOWED_EXTRAS` in the app) are written into the new shortcut.
- `status`: `works`, `untested` or `broken`.

## A config (`containers/index.json`)

`id`, `name`, `file` (`containers/<name>.wcfg`), `description`, `socs` (families it was made for, empty for any), `channel` (`stable` or `prerelease`), `tags`, `testedOn`. A config belongs to no game; several games can list it. Two shortcuts with the same config and the same Wine share one container.

## How the app chooses a config

1. `preferredBySoc` for the device's processor family.
2. `preferredContainer`, if its `socs` is empty or includes the family.
3. The first listed config made for the family.
4. `preferredContainer` anyway, marked "not tested on your processor".

## Adding a device

Add its model (`Build.SOC_MODEL`, for example `SM8850`) and family to `socs.json`; no app update is needed.
