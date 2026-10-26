"""Seeded fuzz tests over what the scripts read from a Mac: Info.plist files of apps, launch agent plists and the
names and kinds of entries in Library, Desktop and Downloads. Each run builds a small synthetic home in tmp_path
with malformed, truncated or wrongly typed plists (a list or number at the top, a date for a version, a number for
Program), odd file names, dangling and looping symbolic links and duplicate files, then runs every script on it
with --no-commands. Bad input must never end in a traceback: exit 0, 1 or 2. Nothing outside tmp_path is read
for writing or moved; trash runs use a --trash-dir inside tmp_path. Raise FUZZ_RUNS locally to search harder."""

from __future__ import annotations

import datetime as dt
import json
import os
import plistlib
import random
from pathlib import Path

import pytest
from conftest import load_script, run_main

FUZZ_RUNS = int(os.environ.get("FUZZ_RUNS", "40"))
SURVEY = load_script("mac-cleanup", "mac_survey.py")
CLEAN = load_script("mac-cleanup", "safe_clean.py")
LEFTOVERS = load_script("mac-app-leftovers", "app_leftovers.py")
DUPES = load_script("mac-duplicate-finder", "find_dupes.py")
ODD = [0, -1, 1.5, "", "x", [], {}, True, b"\x00\xff", [1, 2], {"a": [None]}, "/no/such/program", "rel/prog",
       "/" + "a" * 2000, ["/no/such"], [{"x": 1}], [123], dt.datetime(2026, 1, 1), "é/ü"]
NAMES = ["a\nb", "é", "‮", " (1)", "x (1)", "(1)", ".hidden", "com.apple.x", "A" * 250, "dir.plist",
         "x.savedstate", "UBF8T346G9.Office", "12345678-1234-1234-1234-123456789012", "-rf", "*", "a:b", "IMG (1)"]
AREAS = ["Library/Caches", "Library/Application Support", "Library/Preferences", "Library/Containers",
         "Library/Group Containers", "Library/Saved Application State", "Library/Logs", "Library/HTTPStorages",
         "Library/WebKit", "Desktop", "Downloads"]
KEYS = ["CFBundleIdentifier", "CFBundleName", "CFBundleDisplayName", "CFBundleExecutable", "CFBundleShortVersionString",
        "CFBundleVersion", "Program", "ProgramArguments", "Label"]


def odd_plist(rng: random.Random) -> bytes:
    r = rng.random()
    fmt = rng.choice([plistlib.FMT_XML, plistlib.FMT_BINARY])
    if r < 0.2:
        return bytes(rng.randrange(256) for _ in range(rng.randrange(60)))
    if r < 0.35:
        return plistlib.dumps(rng.choice([[1, 2], "text", 5, True, []]), fmt=fmt)
    try:
        data = plistlib.dumps({k: rng.choice(ODD) for k in rng.sample(KEYS, 4)}, fmt=fmt)
    except (TypeError, ValueError, OverflowError):  # a value plistlib cannot write: plant a typed oddity instead
        data = b"<plist><dict><key>Program</key><integer>1</integer></dict></plist>"
    return data[: rng.randrange(len(data) + 1)] if rng.random() < 0.2 else data


def put(path: Path, rng: random.Random) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        kind = rng.randrange(5)
        if kind == 0:
            path.mkdir(exist_ok=True)
            (path / "f").write_bytes(b"x" * rng.randrange(5000))
        elif kind == 1:
            path.write_bytes(b"dup" * 1000)
        elif kind == 2:
            os.symlink("/no/such/target", path)
        elif kind == 3:
            os.symlink(path, path)
        else:
            path.write_bytes(odd_plist(rng))
    except (OSError, ValueError):
        pass  # a name the file system refuses is simply not planted


def build_home(rng: random.Random, root: Path) -> Path:
    home = root / "home"
    for rel in ("Applications", "tmp", "Library/LaunchAgents", "Documents", "Desktop"):
        (home / rel).mkdir(parents=True, exist_ok=True)
    for i in range(rng.randrange(4)):
        info = home / "Applications" / f"App{i}.app" / "Contents" / "Info.plist"
        info.parent.mkdir(parents=True)
        info.write_bytes(odd_plist(rng))
    for i in range(rng.randrange(4)):
        (home / "Library" / "LaunchAgents" / f"com.example.agent{i}.plist").write_bytes(odd_plist(rng))
    for area in AREAS:
        for _ in range(rng.randrange(3)):
            put(home / area / rng.choice(NAMES), rng)
    if rng.random() < 0.5:
        (home / "Desktop" / "copy.bin").write_bytes(b"same" * 3000)
        (home / "Desktop" / "copy (1).bin").write_bytes(b"same" * 3000)
    return home


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No tools on PATH, and the survey sizes a temporary folder inside tmp_path, not the real one."""
    (tmp_path / "bin").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp-env"))
    (tmp_path / "tmp-env").mkdir()


def commands(home: Path, root: Path) -> list[tuple[object, list[str]]]:
    apps = str(home / "Applications")
    return [
        (SURVEY, ["--home", str(home), "--apps-dir", apps, "--no-commands", "--json", "--quiet"]),
        (CLEAN, ["--home", str(home), "--tmpdir", str(home / "tmp"), "--no-commands", "--json"]),
        (LEFTOVERS, ["--home", str(home), "--apps-dir", apps, "--no-commands", "--json", "--min-mb", "0"]),
        (DUPES, ["--home", str(home), "--min-mb", "0", "--json", "--quiet", "--out-dir", str(root / "out")]),
        (DUPES, ["--home", str(home), "--min-mb", "0", "--quiet", "--trash-suffix-copies",
                 "--trash-dir", str(root / "trash" / "dupes")]),
    ]


def test_scripts_survive_malformed_plists_and_odd_entries(tmp_path):
    for run in range(FUZZ_RUNS):
        rng = random.Random(run)
        root = tmp_path / f"run{run}"
        home = build_home(rng, root)
        for script, argv in commands(home, root):
            try:
                rc, out, err = run_main(script, argv)
            except Exception as exc:  # noqa: BLE001 - the point is to catch any crash
                pytest.fail(f"run {run}: {script.__name__} {argv[-1]}: {type(exc).__name__}: {exc}")
            assert rc in (0, 1, 2) and "Traceback" not in err, (run, script.__name__, rc, err)
            if "--json" in argv and rc in (0, 1):
                json.loads(out)
        rc, out, _ = run_main(LEFTOVERS, commands(home, root)[2][1])
        ids = [c["id"] for c in json.loads(out)["candidates"]] if rc in (0, 1) else []
        if ids:
            argv = [a for a in commands(home, root)[2][1] if a != "--json"]
            argv += ["--trash", ",".join(ids), "--trash-dir", str(root / "trash" / "l")]
            rc, _, err = run_main(LEFTOVERS, argv)
            assert rc in (0, 1, 2) and "Traceback" not in err, (run, err)


# Regressions for the crash causes the fuzzer found on 2026-10-26.

@pytest.mark.parametrize("payload", [
    plistlib.dumps([1, 2]),                                            # a list at the top
    plistlib.dumps(7, fmt=plistlib.FMT_BINARY),                        # a number at the top
    plistlib.dumps({"Program": 1.5}),                                  # Program not a string
    plistlib.dumps({"ProgramArguments": 3}),                           # ProgramArguments not a list
    plistlib.dumps({"ProgramArguments": [{"x": 1}]}),                  # first argument not a string
    plistlib.dumps({"Program": "/" + "a" * 2000}),                     # a path too long to look up
    plistlib.dumps({"Label": "x"})[:-20],                              # truncated XML (ExpatError)
    b"bplist00" + b"\xff" * 40,                                        # corrupt binary plist
], ids=["list-root", "int-root", "float-program", "int-args", "dict-arg", "long-path", "truncated-xml", "bad-binary"])
def test_a_malformed_launch_agent_plist_is_skipped(payload, tmp_path):
    home = tmp_path / "home"
    (home / "Library" / "LaunchAgents").mkdir(parents=True)
    (home / "Applications").mkdir()
    (home / "Library" / "LaunchAgents" / "com.example.bad.plist").write_bytes(payload)
    for script, argv in commands(home, tmp_path)[:3]:
        rc, out, err = run_main(script, argv)
        assert rc in (0, 1) and "Traceback" not in err, (script.__name__, err)
        json.loads(out)


@pytest.mark.parametrize("info", [
    {"CFBundleIdentifier": ["com.example.x"], "CFBundleName": 5},
    {"CFBundleIdentifier": "com.example.app", "CFBundleShortVersionString": dt.datetime(2026, 1, 1)},
], ids=["list-bundle-id", "date-version"])
def test_wrongly_typed_info_plist_values_are_ignored_and_json_still_prints(info, tmp_path):
    home = tmp_path / "home"
    (home / "Applications" / "Odd.app" / "Contents").mkdir(parents=True)
    (home / "Applications" / "Odd.app" / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    rc, out, err = run_main(SURVEY, commands(home, tmp_path)[0][1])
    assert rc in (0, 1), err
    apps = json.loads(out)["sections"]["apps"]["apps"]
    assert [a["name"] for a in apps] == ["Odd"]
    assert all(isinstance(a["version"], (str, type(None))) for a in apps)
    rc, _, err = run_main(LEFTOVERS, commands(home, tmp_path)[2][1])
    assert rc in (0, 1) and "Traceback" not in err
