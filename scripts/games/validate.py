#!/usr/bin/env python3
"""Validates games.json, games/*.json and the steam block of linux.json.

Usage: python3 -I scripts/games/validate.py [--root DIR] [--bundle APP_ASSETS_REGISTRY_DIR]
       python3 -I scripts/games/validate.py --self-test | --print-extras
"""
import argparse, json, os, re, shutil, sys, tempfile

# The only keys a game version may set under "extras" (values are strings). Keep in sync with the app.
ALLOWED_EXTRAS = (
    "graphicsFilterMode", "graphicsSharpness", "graphicsPostFXMode", "graphicsColorMode",
    "fullscreenStretched", "simTouchScreen", "lsfgMultiplier", "lsfgFlowScale", "steamMinimal",
)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RES_RE = re.compile(r"^\d{3,5}x\d{3,5}$")
VER_RE = re.compile(r"^\d+(\.\d+)*$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
STATUSES = ("works", "untested", "broken")
PRESETS = ("STABILITY", "COMPATIBILITY", "INTERMEDIATE", "PERFORMANCE")
INF = float("inf")


def isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def vkey(s):
    return tuple(int(x) for x in s.split("."))


def vcmp(a, b):
    """Dotted-version comparison; missing trailing parts count as 0."""
    a, b = list(vkey(a)), list(vkey(b))
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return (a > b) - (a < b)


class Report:
    def __init__(self):
        self.errors = []

    def err(self, path, msg):
        self.errors.append("%s: %s" % (path, msg))


def load(rep, path, shown):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        rep.err(shown, "file is missing")
    except (ValueError, OSError) as e:
        rep.err(shown, "cannot parse: %s" % e)
    return None


def check_range(rep, p, where, rng, kind):
    """kind: 'int' or 'ver'. Returns (lo, hi) with inf for missing, or None."""
    if not isinstance(rng, dict):
        rep.err(p, "%s must be an object" % where)
        return None
    extra = set(rng) - {"from", "until"}
    if extra:
        rep.err(p, "%s has unknown keys %s" % (where, sorted(extra)))
    vals = {}
    for k in ("from", "until"):
        if k not in rng:
            continue
        v = rng[k]
        if kind == "int":
            if not isint(v) or v < 0:
                rep.err(p, "%s.%s must be a non-negative integer" % (where, k))
                return None
        elif not isinstance(v, str) or not VER_RE.match(v):
            rep.err(p, "%s.%s must be a dotted version string" % (where, k))
            return None
        vals[k] = v
    if "from" in vals and "until" in vals:
        lt = vals["from"] < vals["until"] if kind == "int" else vcmp(vals["from"], vals["until"]) < 0
        if not lt:
            rep.err(p, "%s: from must be less than until" % where)
            return None
    return vals.get("from", 0 if kind == "int" else None), vals.get("until", INF if kind == "int" else None)


def check_files(rep, p, where, files):
    if not isinstance(files, list) or not files:
        rep.err(p, "%s must be a non-empty list" % where)
        return
    for i, f in enumerate(files):
        w = "%s[%d]" % (where, i)
        if not isinstance(f, dict):
            rep.err(p, "%s must be an object" % w)
            continue
        extra = set(f) - {"path", "size", "sha256"}
        if extra:
            rep.err(p, "%s has unknown keys %s" % (w, sorted(extra)))
        check_relpath(rep, p, w + ".path", f.get("path"))
        has_size, has_sha = "size" in f, "sha256" in f
        if not has_size and not has_sha:
            rep.err(p, "%s needs size and/or sha256" % w)
        if has_size and (not isint(f["size"]) or f["size"] < 0):
            rep.err(p, "%s.size must be a non-negative integer" % w)
        if has_sha:
            if not isinstance(f["sha256"], str) or not SHA_RE.match(f["sha256"]):
                rep.err(p, "%s.sha256 must be 64 hex chars" % w)
            if not has_size or not isint(f.get("size")) or f["size"] > 16777216:
                rep.err(p, "%s: sha256 requires an integer size <= 16777216" % w)


def check_relpath(rep, p, where, v):
    if not isinstance(v, str) or not v:
        rep.err(p, "%s must be a non-empty string" % where)
    elif v.startswith("/") or v.startswith("\\") or re.match(r"^[A-Za-z]:", v) or ".." in re.split(r"[\\/]", v):
        rep.err(p, "%s must be relative without '..' or a leading '/'" % where)


def check_version_file(rep, p, where, vf):
    if not isinstance(vf, dict):
        rep.err(p, "%s must be an object" % where)
        return
    extra = set(vf) - {"path", "head", "tail", "regex", "from", "until"}
    if extra:
        rep.err(p, "%s has unknown keys %s" % (where, sorted(extra)))
    check_relpath(rep, p, where + ".path", vf.get("path"))
    if ("head" in vf) == ("tail" in vf):
        rep.err(p, "%s needs exactly one of head/tail" % where)
    for k in ("head", "tail"):
        if k in vf and (not isint(vf[k]) or not 1 <= vf[k] <= 65536):
            rep.err(p, "%s.%s must be an integer 1..65536" % (where, k))
    rx = vf.get("regex")
    if not isinstance(rx, str):
        rep.err(p, "%s.regex must be a string" % where)
    else:
        try:
            if re.compile(rx).groups != 1:
                rep.err(p, "%s.regex must have exactly one capture group" % where)
        except re.error as e:
            rep.err(p, "%s.regex does not compile: %s" % (where, e))
    check_range(rep, p, where, {k: v for k, v in vf.items() if k in ("from", "until")}, "ver")


def check_defaults(rep, p, d, where="defaults", partial=False):
    if not isinstance(d, dict):
        rep.err(p, "%s must be an object" % where)
        return
    extra = set(d) - {"executable", "noSteam", "args", "env", "resolution", "extras"}
    if extra:
        rep.err(p, "%s has unknown keys %s" % (where, sorted(extra)))
    if "executable" in d:
        check_relpath(rep, p, where + ".executable", d["executable"])
    elif not partial:
        rep.err(p, "%s.executable is required" % where)
    if "resolution" in d and not (isinstance(d["resolution"], str) and (d["resolution"] == "native" or RES_RE.match(d["resolution"]))):
        rep.err(p, "%s.resolution must be 'native' or WIDTHxHEIGHT" % where)
    if "noSteam" in d:
        n = d["noSteam"]
        if not (isinstance(n, dict) and set(n) == {"default", "arg"} and isinstance(n["default"], bool)
                and isinstance(n["arg"], str) and n["arg"]):
            rep.err(p, "%s.noSteam must be {default: bool, arg: non-empty string}" % where)
    if "args" in d and not (isinstance(d["args"], list) and all(isinstance(a, str) for a in d["args"])):
        rep.err(p, "%s.args must be a list of strings" % where)
    if "env" in d:
        e = d["env"]
        if not isinstance(e, dict) or not all(isinstance(k, str) and (isinstance(v, str) or (partial and v is None)) for k, v in e.items()):
            rep.err(p, "%s.env must be an object of string -> string" % where)
    if "extras" in d:
        x = d["extras"]
        if not isinstance(x, dict):
            rep.err(p, "%s.extras must be an object" % where)
        else:
            for k, v in x.items():
                if k not in ALLOWED_EXTRAS:
                    rep.err(p, "%s.extras key '%s' is not allowed" % (where, k))
                if not (isinstance(v, str) or (partial and v is None)):
                    rep.err(p, "%s.extras.%s must be a string" % (where, k))


def check_game(rep, p, g, entry):
    if not isinstance(g, dict):
        rep.err(p, "must be an object")
        return
    if g.get("schema") != 1:
        rep.err(p, "schema must be 1")
    if g.get("id") != entry.get("id"):
        rep.err(p, "id '%s' does not match the index id '%s'" % (g.get("id"), entry.get("id")))
    if not isinstance(g.get("name"), str) or not g.get("name"):
        rep.err(p, "name must be a non-empty string")
    st = g.get("steam")
    if not isinstance(st, dict):
        rep.err(p, "steam must be an object")
    else:
        if not isint(st.get("appId")):
            rep.err(p, "steam.appId must be an integer")
        elif st["appId"] != entry.get("steamAppId"):
            rep.err(p, "steam.appId %s does not match the index steamAppId %s" % (st["appId"], entry.get("steamAppId")))
        check_relpath(rep, p, "steam.installDir", st.get("installDir"))
    check_defaults(rep, p, g.get("defaults"))
    vs = g.get("versions")
    if not isinstance(vs, list) or not vs:
        rep.err(p, "versions must be a non-empty list")
        return
    ids, defaults, ranges = set(), 0, []
    for i, v in enumerate(vs):
        w = "versions[%d]" % i
        if not isinstance(v, dict):
            rep.err(p, "%s must be an object" % w)
            continue
        vid = v.get("id")
        if not isinstance(vid, str) or not ID_RE.match(vid):
            rep.err(p, "%s.id is invalid" % w)
        elif vid in ids:
            rep.err(p, "duplicate version id '%s'" % vid)
        ids.add(vid)
        if not isinstance(v.get("label"), str) or not v.get("label"):
            rep.err(p, "%s.label must be a non-empty string" % w)
        if v.get("status") not in STATUSES:
            rep.err(p, "%s.status must be one of %s" % (w, "/".join(STATUSES)))
        for k in ("testedOn", "notes"):
            if k in v and not isinstance(v[k], str):
                rep.err(p, "%s.%s must be a string" % (w, k))
        if "default" in v:
            if not isinstance(v["default"], bool):
                rep.err(p, "%s.default must be a boolean" % w)
            elif v["default"]:
                defaults += 1
        override = {k: x for k, x in v.items() if k in ("executable", "noSteam", "args", "env", "resolution", "extras")}
        check_defaults(rep, p, override, w, partial=True)
        known = {"id", "label", "status", "default", "testedOn", "notes", "match",
                 "executable", "noSteam", "args", "env", "resolution", "extras"}
        if set(v) - known:
            rep.err(p, "%s has unknown keys %s" % (w, sorted(set(v) - known)))
        if "match" in v:
            m = v["match"]
            if not isinstance(m, dict):
                rep.err(p, "%s.match must be an object" % w)
                continue
            if set(m) - {"steamBuildId", "versionFile", "files"}:
                rep.err(p, "%s.match has unknown keys %s" % (w, sorted(set(m) - {"steamBuildId", "versionFile", "files"})))
            if "steamBuildId" in m:
                r = check_range(rep, p, w + ".match.steamBuildId", m["steamBuildId"], "int")
                if r:
                    ranges.append((r, vid))
            if "versionFile" in m:
                check_version_file(rep, p, w + ".match.versionFile", m["versionFile"])
            if "files" in m:
                check_files(rep, p, w + ".match.files", m["files"])
    if defaults > 1:
        rep.err(p, "more than one version has default: true")
    for a in range(len(ranges)):
        for b in range(a + 1, len(ranges)):
            (l1, h1), i1 = ranges[a]
            (l2, h2), i2 = ranges[b]
            if l1 < h2 and l2 < h1:
                rep.err(p, "steamBuildId ranges of versions '%s' and '%s' overlap" % (i1, i2))


def check_linux(rep, p, d):
    if not isinstance(d, dict):
        rep.err(p, "must be an object")
        return
    s = d.get("steam")
    if not isinstance(s, dict):
        rep.err(p, "the steam block is missing")
        return
    want = {"runtime", "emulator", "emulatorPreset", "driver", "glDriver", "vulkanPresent"}
    if set(s) != want:
        rep.err(p, "steam keys must be exactly %s" % sorted(want))
    rt = s.get("runtime")
    if not isinstance(rt, str) or not ID_RE.match(rt):
        rep.err(p, "steam.runtime must match the id pattern")
    em = [e for e in d.get("emulators", []) if isinstance(e, dict) and e.get("id") == s.get("emulator")]
    if not em or em[0].get("emulator") != "box64":
        rep.err(p, "steam.emulator must be an emulators[].id with emulator 'box64'")
    if not any(isinstance(x, dict) and x.get("id") == s.get("driver") for x in d.get("drivers", [])):
        rep.err(p, "steam.driver must be a drivers[].id")
    if s.get("emulatorPreset") not in PRESETS:
        rep.err(p, "steam.emulatorPreset must be one of %s" % "/".join(PRESETS))
    if s.get("glDriver") not in ("zink", "software"):
        rep.err(p, "steam.glDriver must be zink or software")
    if s.get("vulkanPresent") not in ("native", "sw"):
        rep.err(p, "steam.vulkanPresent must be native or sw")


def check_bundle(rep, root, bundle):
    names = ["games.json", "linux.json"]
    gdir = os.path.join(root, "games")
    if os.path.isdir(gdir):
        names += ["games/" + n for n in sorted(os.listdir(gdir)) if n.endswith(".json")]
    bgames = os.path.join(bundle, "games")
    if os.path.isdir(bgames):
        for n in sorted(os.listdir(bgames)):
            if n.endswith(".json") and "games/" + n not in names:
                names.append("games/" + n)
    for n in names:
        a, b = os.path.join(root, n), os.path.join(bundle, n)
        shown = os.path.join(bundle, n)
        if not os.path.isfile(a):
            rep.err(shown, "bundled file has no counterpart in the registry")
        elif not os.path.isfile(b):
            rep.err(shown, "bundled copy is missing")
        else:
            with open(a, "rb") as fa, open(b, "rb") as fb:
                if fa.read() != fb.read():
                    rep.err(shown, "differs from %s" % a)


def validate(root, bundle=None):
    rep = Report()
    idx = load(rep, os.path.join(root, "games.json"), "games.json")
    if isinstance(idx, dict):
        if idx.get("schema") != 1:
            rep.err("games.json", "schema must be 1")
        games = idx.get("games")
        if not isinstance(games, list):
            rep.err("games.json", "games must be a list")
            games = []
        ids, apps = set(), set()
        for i, e in enumerate(games):
            if not isinstance(e, dict):
                rep.err("games.json", "games[%d] must be an object" % i)
                continue
            gid = e.get("id")
            if not isinstance(gid, str) or not ID_RE.match(gid):
                rep.err("games.json", "games[%d].id is invalid" % i)
                continue
            if gid in ids:
                rep.err("games.json", "duplicate id '%s'" % gid)
            ids.add(gid)
            if not isinstance(e.get("name"), str) or not e["name"]:
                rep.err("games.json", "%s: name must be a non-empty string" % gid)
            a = e.get("steamAppId")
            if not isint(a):
                rep.err("games.json", "%s: steamAppId must be an integer" % gid)
            elif a in apps:
                rep.err("games.json", "duplicate steamAppId %d" % a)
            apps.add(a)
            want = "games/%s.json" % gid
            if e.get("config") != want:
                rep.err("games.json", "%s: config must be '%s'" % (gid, want))
            shown = want
            g = load(rep, os.path.join(root, want), shown)
            if g is not None:
                check_game(rep, shown, g, e)
        gdir = os.path.join(root, "games")
        if os.path.isdir(gdir):
            for n in sorted(os.listdir(gdir)):
                if n.endswith(".json") and n[:-5] not in ids:
                    rep.err("games/" + n, "not listed in games.json")
    elif idx is not None:
        rep.err("games.json", "must be an object")
    lx = load(rep, os.path.join(root, "linux.json"), "linux.json")
    if lx is not None:
        check_linux(rep, "linux.json", lx)
    if bundle:
        check_bundle(rep, root, bundle)
    return rep.errors


def self_test(root):
    tmp = tempfile.mkdtemp(prefix="games-validate-")
    try:
        def fresh(name):
            d = os.path.join(tmp, name)
            os.makedirs(os.path.join(d, "games"))
            for n in ["games.json", "linux.json"] + ["games/" + f for f in os.listdir(os.path.join(root, "games")) if f.endswith(".json")]:
                shutil.copyfile(os.path.join(root, n), os.path.join(d, n))
            return d

        def rw(d, name, fn):
            p = os.path.join(d, name)
            with open(p, encoding="utf-8") as f:
                j = json.load(f)
            fn(j)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(j, f)

        beam = "games/beamng-drive.json"
        cases = []

        def case(label, name, fn, expect):
            cases.append((label, name, fn, expect))

        case("config path", "games.json", lambda j: j["games"][0].update(config="games/other.json"), "config must be")
        case("duplicate appId", "games.json", lambda j: j["games"][1].update(steamAppId=284160), "duplicate steamAppId")
        case("bad id", "games.json", lambda j: j["games"][0].update(id="-x"), "id is invalid")
        case("appId mismatch", beam, lambda j: j["steam"].update(appId=1), "does not match the index steamAppId")
        case("parent path", beam, lambda j: j["defaults"].update(executable="../x"), "relative without")
        case("absolute path", beam, lambda j: j["defaults"].update(executable="/x"), "relative without")
        case("resolution", beam, lambda j: j["defaults"].update(resolution="big"), "resolution")
        case("noSteam", beam, lambda j: j["defaults"].update(noSteam={"default": True, "arg": ""}), "noSteam")
        case("env value", beam, lambda j: j["defaults"].update(env={"A": 1}), "env")
        case("extras key", beam, lambda j: j["defaults"].update(extras={"nope": "1"}), "not allowed")
        case("bad status", beam, lambda j: j["versions"][0].update(status="fine"), "status")
        case("duplicate version id", beam, lambda j: j["versions"][1].update(id="0.39"), "duplicate version id")
        case("two defaults", beam, lambda j: j["versions"][1].update(default=True), "more than one")
        case("build range order", beam, lambda j: j["versions"][0]["match"]["steamBuildId"].update(until=5), "from must be less")
        case("version range order", beam, lambda j: j["versions"][0]["match"]["versionFile"].update({"from": "0.10", "until": "0.9"}), "from must be less")
        case("range overlap", beam, lambda j: j["versions"][1]["match"].update(steamBuildId={"from": 100}), "overlap")
        case("regex groups", beam, lambda j: j["versions"][0]["match"]["versionFile"].update(regex="a"), "capture group")
        case("head and tail", beam, lambda j: j["versions"][0]["match"]["versionFile"].update(head=10), "head/tail")
        case("sha256 without size", beam, lambda j: j["versions"][0]["match"]["files"].append({"path": "a", "sha256": "0" * 64}), "sha256 requires")
        case("steam block", "linux.json", lambda j: j.pop("steam"), "steam block is missing")
        case("steam emulator", "linux.json", lambda j: j["steam"].update(emulator="fex-2610"), "steam.emulator")
        case("steam driver", "linux.json", lambda j: j["steam"].update(driver="nope"), "steam.driver")
        case("steam preset", "linux.json", lambda j: j["steam"].update(emulatorPreset="FAST"), "emulatorPreset")
        ok = True
        for label, name, fn, expect in cases:
            d = fresh("c")
            rw(d, name, fn)
            errs = validate(d)
            if not any(expect in e for e in errs):
                print("self-test: defect not detected: %s (expected '%s')" % (label, expect))
                ok = False
            shutil.rmtree(d)
        d = fresh("b")
        os.makedirs(os.path.join(tmp, "bundle", "games"))
        b = os.path.join(tmp, "bundle")
        shutil.copyfile(os.path.join(d, "games.json"), os.path.join(b, "games.json"))
        with open(os.path.join(b, "linux.json"), "w") as f:
            f.write("{}")
        errs = validate(d, b)
        for want in ("linux.json: differs", "beamng-drive.json: bundled copy is missing"):
            if not any(want in e.replace(b + os.sep, "").replace("games" + os.sep, "") or want in e for e in errs):
                print("self-test: bundle drift not detected: %s" % want)
                ok = False
        if validate(root):
            print("self-test: the real registry is not clean")
            ok = False
        print("self-test: %s (%d defects)" % ("ok" if ok else "FAILED", len(cases) + 2))
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    ap.add_argument("--bundle", help="app assets/registry directory that must mirror the registry")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--print-extras", action="store_true")
    a = ap.parse_args()
    if a.print_extras:
        print("\n".join(ALLOWED_EXTRAS))
        return 0
    root = os.path.normpath(a.root)
    if a.self_test:
        return 0 if self_test(root) else 1
    errs = validate(root, a.bundle)
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
