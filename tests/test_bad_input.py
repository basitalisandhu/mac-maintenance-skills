"""Bad input is exit 2 with a one-line message in every script, never a traceback or a silent pass.

Covers numeric options (negative, zero, not a number), output paths that cannot be written (checked before the
scan, so a long survey is not lost at the end), --trash ids that are malformed or not candidates (nothing moves),
and the exit codes printed by --help, which must match the SKILL.md wording.
"""

from __future__ import annotations

import pytest
from conftest import ROOT, load_script, run_json, run_main

SURVEY = load_script("mac-cleanup", "mac_survey.py")
CLEAN = load_script("mac-cleanup", "safe_clean.py")
LEFTOVERS = load_script("mac-app-leftovers", "app_leftovers.py")
DUPES = load_script("mac-duplicate-finder", "find_dupes.py")
ALL = [SURVEY, CLEAN, LEFTOVERS, DUPES]


@pytest.fixture(autouse=True)
def empty_path(tmp_path, monkeypatch):
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", str(folder))


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    for rel in ("Library/Caches", "Documents", "Desktop", "Applications"):
        (folder / rel).mkdir(parents=True)
    return folder


def base(script, home):
    return {
        SURVEY: ["--home", str(home), "--apps-dir", str(home / "Applications"), "--fast", "--no-commands", "--quiet"],
        CLEAN: ["--home", str(home), "--tmpdir", str(home), "--no-commands"],
        LEFTOVERS: ["--home", str(home), "--apps-dir", str(home / "Applications"), "--no-commands"],
        DUPES: ["--home", str(home), "--quiet"],
    }[script]


@pytest.mark.parametrize("script", ALL, ids=lambda m: m.__name__.split("_", 3)[-1])
def test_help_states_the_exit_codes(script):
    rc, out, _ = run_main(script, ["--help"])
    assert rc == 0
    assert "Exit codes:" in out and "2 bad input or usage" in out


@pytest.mark.parametrize("script,option", [
    (SURVEY, "--top"), (SURVEY, "--timeout"), (SURVEY, "--large-mb"),
    (CLEAN, "--timeout"), (CLEAN, "--npx-days"), (CLEAN, "--log-days"),
    (LEFTOVERS, "--top"), (LEFTOVERS, "--min-mb"), (DUPES, "--min-mb"), (DUPES, "--top"), (DUPES, "--pair-depth"),
], ids=lambda v: v if isinstance(v, str) else v.__name__.split("_", 3)[-1])
@pytest.mark.parametrize("value", ["-3", "abc", "nan"])
def test_bad_numbers_are_usage_errors(home, script, option, value):
    rc, out, err = run_main(script, base(script, home) + [option, value])
    assert rc == 2, (option, value)
    assert option in err and out == ""


def test_zero_is_fine_where_zero_means_no_minimum(home):
    rc, _, err = run_main(DUPES, base(DUPES, home) + ["--min-mb", "0"])
    assert rc in (0, 1), err
    rc, _, err = run_main(CLEAN, base(CLEAN, home) + ["--log-days", "0"])
    assert rc in (0, 1), err


def test_survey_out_in_a_missing_folder_fails_before_the_survey(home, tmp_path):
    rc, out, err = run_main(SURVEY, base(SURVEY, home) + ["--out", str(tmp_path / "missing" / "survey.json")])
    assert rc == 2 and out == ""
    assert "--out" in err and "existing folder" in err


def test_survey_out_that_is_a_folder_fails(home, tmp_path):
    rc, _, err = run_main(SURVEY, base(SURVEY, home) + ["--out", str(tmp_path)])
    assert rc == 2 and "--out" in err


def test_dupes_out_dir_that_is_a_file_fails_before_the_scan(home, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    rc, out, err = run_main(DUPES, base(DUPES, home) + ["--out-dir", str(blocker)])
    assert rc == 2 and out == ""
    assert "not a folder" in err


def test_clean_log_that_cannot_be_written_is_bad_input(home, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    rc, out, err = run_main(CLEAN, base(CLEAN, home) + ["--log", str(blocker / "clean.log")])
    assert rc == 2 and out == ""
    assert "cannot write --log" in err


@pytest.mark.parametrize("ids", ["nocolon", "attic:Thing", "app-support:", ",", ""])
def test_malformed_trash_ids_are_refused_before_the_scan(home, tmp_path, ids):
    trash = tmp_path / "trash"
    rc, out, err = run_main(LEFTOVERS, base(LEFTOVERS, home) + ["--trash", ids, "--trash-dir", str(trash)])
    assert rc == 2 and out == ""
    assert "area:name" in err
    assert not trash.exists()


def test_one_unknown_trash_id_means_nothing_moves(home, tmp_path):
    left = home / "Library" / "Application Support" / "Leftover"
    left.mkdir(parents=True)
    (left / "data.bin").write_bytes(b"x" * 4096)
    trash = tmp_path / "trash"
    argv = base(LEFTOVERS, home) + ["--json", "--trash", "app-support:Leftover,app-support:Typo",
                                    "--trash-dir", str(trash)]
    rc, rep = run_json(LEFTOVERS, argv)
    assert rc == 2
    assert rep["moved"] == [] and left.exists() and not trash.exists()
    errors = {f["id"]: f["error"] for f in rep["failed"]}
    assert errors["app-support:Typo"] == "not a candidate in this run"
    assert "nothing was moved" in errors["app-support:Leftover"]


def test_valid_trash_id_still_moves(home, tmp_path):
    left = home / "Library" / "Application Support" / "Leftover"
    left.mkdir(parents=True)
    (left / "data.bin").write_bytes(b"x" * 4096)
    trash = tmp_path / "trash"
    rc, rep = run_json(LEFTOVERS, base(LEFTOVERS, home) + ["--json", "--trash", "app-support:Leftover",
                                                         "--trash-dir", str(trash)])
    assert rc == 1
    assert [m["id"] for m in rep["moved"]] == ["app-support:Leftover"]
    assert (trash / "Library" / "Application Support" / "Leftover" / "data.bin").is_file()


def test_documented_exit_codes_match_the_skill_files():
    skills = ROOT / "plugins" / "mac-maintenance" / "skills"
    survey = (skills / "mac-cleanup" / "SKILL.md").read_text(encoding="utf-8")
    assert "mac_survey.py` exits 0 when it finds no cleanup candidates, 1 when it lists some" in survey
    leftovers = (skills / "mac-app-leftovers" / "SKILL.md").read_text(encoding="utf-8")
    assert "nothing is moved" in leftovers
