"""One end-to-end cleanup on the synthetic demo home, the way the three skills chain on a real Mac: survey, move the
verified suffix copy and the uninstalled app's leftovers to a Trash folder, run the safe tier for real, then survey
again and check each script now reports what was done. Everything happens inside tmp_path: --home, --tmpdir,
TMPDIR and every --trash-dir point there, and PATH is empty, so no tool on this machine is run."""

from __future__ import annotations

import importlib.util
import sys

import pytest
from conftest import ROOT, load_script, run_json, run_main

spec = importlib.util.spec_from_file_location("demo_home_chain", ROOT / "scripts" / "demo_home.py")
demo = importlib.util.module_from_spec(spec)
sys.modules["demo_home_chain"] = demo
spec.loader.exec_module(demo)

SURVEY = load_script("mac-cleanup", "mac_survey.py")
CLEAN = load_script("mac-cleanup", "safe_clean.py")
LEFTOVERS = load_script("mac-app-leftovers", "app_leftovers.py")
DUPES = load_script("mac-duplicate-finder", "find_dupes.py")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    (tmp_path / "tmp-env").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp-env"))
    monkeypatch.setattr(LEFTOVERS, "startup_leftovers",
                        lambda *a, **k: {"login_items": [], "launch_agents": [], "launch_daemons": []})


def cache_bytes(report: dict, rel: str) -> int | None:
    return next((r["bytes"] for r in report["sections"]["caches"]["known"] if r["path"].endswith(rel)), None)


def test_survey_trash_clean_and_survey_again(tmp_path):
    home = tmp_path / "demo-home"
    assert run_main(demo, [str(home)])[0] == 0
    survey = ["--home", str(home), "--apps-dir", str(home / "Applications"), "--fast", "--no-commands", "--json",
              "--quiet"]
    leftovers = ["--home", str(home), "--apps-dir", str(home / "Applications"), "--no-commands", "--json"]
    dupes = ["--home", str(home), "--json", "--quiet"]

    # 1. Survey: the npm cache is a candidate; duplicates and leftovers are found by their own skills.
    rc, before = run_json(SURVEY, survey)
    assert rc == 1 and cache_bytes(before, ".npm/_cacache") > 0
    rc, found = run_json(DUPES, dupes)
    assert rc == 1 and [c["copy"].rsplit("/", 1)[-1] for c in found["suffix_copies"]] == ["IMG_0412 (1).MOV"]
    rc, left = run_json(LEFTOVERS, leftovers)
    ids = sorted(c["id"] for c in left["candidates"])
    assert rc == 1 and ids == ["app-support:QuillNote", "caches:net.quillnote.QuillNote",
                               "preferences:net.quillnote.QuillNote.plist"]

    # 2. Move the suffix copy and the leftovers to Trash folders inside tmp_path (the user named them).
    trash = tmp_path / "Trash"
    rc, moved = run_json(DUPES, [*dupes, "--trash-suffix-copies", "--trash-dir", str(trash / "dupes")])
    assert rc in (0, 1) and len(moved["moved"]) == 1 and not (home / "Desktop" / "IMG_0412 (1).MOV").exists()
    assert (home / "Desktop" / "IMG_0412.MOV").is_file()  # the original stays
    rc, out, err = run_main(LEFTOVERS, [*leftovers[:-1], "--trash", ",".join(ids), "--trash-dir", str(trash / "l")])
    assert rc in (0, 1), err
    assert not (home / "Library" / "Application Support" / "QuillNote").exists()
    assert (trash / "l").is_dir() and any((trash / "l").rglob("notes.db"))

    # 3. The safe tier for real, with external commands off.
    rc, cleaned = run_json(CLEAN, ["--home", str(home), "--tmpdir", str(home / "tmp"), "--no-commands", "--apply",
                                   "--only", "npm-cache,old-logs", "--json"])
    assert rc == 0, cleaned
    assert {a["id"]: a["status"] for a in cleaned["actions"]} == {"npm-cache": "done", "old-logs": "done"}

    # 4. Survey and the other two again: nothing left to report from what was planted.
    rc, after = run_json(SURVEY, survey)
    assert cache_bytes(after, ".npm/_cacache") in (None, 0)
    assert run_json(DUPES, dupes)[1]["suffix_copies"] == []
    rc, left = run_json(LEFTOVERS, leftovers)
    assert rc == 0 and left["candidates"] == []
    rc, again = run_json(CLEAN, ["--home", str(home), "--tmpdir", str(home / "tmp"), "--no-commands",
                                 "--only", "npm-cache,old-logs", "--json"])
    assert rc == 0 and all(a["status"] == "nothing to do" for a in again["actions"])
