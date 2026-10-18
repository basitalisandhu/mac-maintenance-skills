"""scripts/demo_home.py builds the synthetic home the README samples come from; the scripts must find its plants."""

from __future__ import annotations

import importlib.util
import sys

import pytest
from conftest import ROOT, load_script, run_json, run_main

spec = importlib.util.spec_from_file_location("demo_home", ROOT / "scripts" / "demo_home.py")
demo = importlib.util.module_from_spec(spec)
sys.modules["demo_home"] = demo
spec.loader.exec_module(demo)

DUPES = load_script("mac-duplicate-finder", "find_dupes.py")
LEFTOVERS = load_script("mac-app-leftovers", "app_leftovers.py")
CLEAN = load_script("mac-cleanup", "safe_clean.py")


@pytest.fixture(autouse=True)
def empty_path(tmp_path, monkeypatch):
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", str(folder))


@pytest.fixture
def demo_home(tmp_path):
    home = tmp_path / "demo-home"
    assert run_main(demo, [str(home)])[0] == 0
    return home


def test_demo_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    run_main(demo, [str(a)])
    run_main(demo, [str(b)])
    for rel in demo.build.__code__.co_consts:
        if isinstance(rel, str) and "/" in rel and (a / rel).is_file():
            assert (a / rel).read_bytes() == (b / rel).read_bytes()


def test_demo_refuses_a_non_empty_folder(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "keep.txt").write_text("mine", encoding="utf-8")
    rc, _, err = run_main(demo, [str(tmp_path / "x")])
    assert rc == 2 and "not an empty folder" in err
    assert (tmp_path / "x" / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_demo_refuses_a_file(tmp_path):
    (tmp_path / "f").write_text("", encoding="utf-8")
    rc, _, _ = run_main(demo, [str(tmp_path / "f")])
    assert rc == 2


def test_dupes_find_both_planted_groups_and_the_suffix_copy(demo_home):
    rc, rep = run_json(DUPES, ["--home", str(demo_home), "--quiet", "--json"])
    assert rc == 1
    assert rep["group_count"] == 2
    assert [c["copy"].endswith("IMG_0412 (1).MOV") for c in rep["suffix_copies"]] == [True]


def test_dupes_text_labels_copies_inside_one_folder(demo_home):
    _, out, _ = run_main(DUPES, ["--home", str(demo_home), "--quiet"])
    assert "Desktop (copies inside it)" in out
    assert "Documents/Invoices <-> Downloads" in out


def test_leftovers_list_the_three_planted_entries(demo_home):
    rc, rep = run_json(LEFTOVERS, ["--home", str(demo_home), "--apps-dir", str(demo_home / "Applications"),
                                   "--no-commands", "--json"])
    assert rc in (0, 1)
    ids = {c["id"] for c in rep["candidates"]}
    assert {"app-support:QuillNote", "caches:net.quillnote.QuillNote",
            "preferences:net.quillnote.QuillNote.plist"} <= ids


def test_safe_clean_plans_the_npm_cache_and_the_old_log(demo_home):
    rc, rep = run_json(CLEAN, ["--home", str(demo_home), "--tmpdir", str(demo_home / "tmp"), "--no-commands",
                               "--json"])
    assert rc == 1 and rep["applied"] is False
    planned = {a["id"] for a in rep["actions"] if a["status"] == "planned"}
    assert {"npm-cache", "old-logs"} <= planned
    assert (demo_home / ".npm" / "_cacache").exists()  # dry run changed nothing
