import os
import time
from pathlib import Path

import pytest
from conftest import load_script, run_json, run_main

mod = load_script("mac-cleanup", "safe_clean.py")

DAY = 86400
COMMAND_ACTIONS = ["brew-cleanup", "uv-cache", "docker-build-cache", "docker-dangling-images",
                   "docker-anon-volumes", "docker-orphan-buildx", "orphan-login-items"]


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    folder.mkdir()
    return folder


@pytest.fixture
def tmpdir_(tmp_path):
    folder = tmp_path / "tmpdir"
    folder.mkdir()
    return folder


def write(path, text="data" * 1024):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def age(path, days):
    stamp = time.time() - days * DAY
    os.utime(path, (stamp, stamp))


def populate(home):
    """One of each cache the path actions know about, plus entries that must be kept."""
    paths = {
        "npm": write(home / ".npm" / "_cacache" / "content" / "a"),
        "go": write(home / "Library" / "Caches" / "go-build" / "ab" / "obj"),
        "updater": write(home / "Library" / "Caches" / "foo-updater" / "pending" / "update.zip"),
        "old_log": write(home / "Library" / "Logs" / "old.log"),
        "new_log": write(home / "Library" / "Logs" / "new.log"),
    }
    age(paths["old_log"], 30)
    old_npx = write(home / ".npm" / "_npx" / "aaaa1111" / "package.json")
    age(old_npx.parent, 40)
    paths["npx_old"] = old_npx.parent
    paths["npx_new"] = write(home / ".npm" / "_npx" / "bbbb2222" / "package.json").parent
    return paths


def argv(home, tmpdir_, *extra):
    return ["--home", str(home), "--tmpdir", str(tmpdir_), "--no-commands", "--json", *extra]


def run(home, tmpdir_, *extra):
    rc, result = run_json(mod, argv(home, tmpdir_, *extra))
    return rc, result, {a["id"]: a for a in result["actions"]}


def test_help_shows_usage_and_action_ids():
    rc, out, _ = run_main(mod, ["--help"])
    assert rc == 0 and "usage:" in out and "npm-cache" in out and "--apply" in out


def test_bad_home_exits_2(tmp_path, tmpdir_):
    rc, _, err = run_main(mod, ["--home", str(tmp_path / "missing"), "--tmpdir", str(tmpdir_), "--no-commands"])
    assert rc == 2 and "not a directory" in err


@pytest.mark.parametrize("flag", ["--only", "--skip"])
def test_unknown_action_id_exits_2(home, tmpdir_, flag):
    rc, _, err = run_main(mod, argv(home, tmpdir_, flag, "npm-cache,no-such-action"))
    assert rc == 2 and "no-such-action" in err


def test_json_result_shape(home, tmpdir_):
    populate(home)
    rc, result, _ = run(home, tmpdir_)
    assert {"applied", "home", "actions", "bytes_planned_or_done", "count_planned_or_done", "free_before",
            "free_after"} <= set(result)
    assert result["applied"] is False and result["free_after"] is None
    assert {"id", "title", "status", "bytes", "detail", "targets"} <= set(result["actions"][0])
    ran = [a["id"] for a in result["actions"]]
    assert ran == [i for i in mod.ACTION_IDS if i in ran]


def test_dry_run_plans_every_path_action_and_deletes_nothing(home, tmpdir_):
    paths = populate(home)
    rc, result, by_id = run(home, tmpdir_)
    for action_id in ("npm-cache", "go-build", "electron-updaters", "old-logs", "npx-stale"):
        assert by_id[action_id]["status"] == "planned", action_id
        assert by_id[action_id]["bytes"] > 0
    assert by_id["old-logs"]["targets"] == [str(paths["old_log"])]
    assert by_id["npx-stale"]["targets"] == [str(paths["npx_old"])]
    assert by_id["electron-updaters"]["targets"] == [str(home / "Library" / "Caches" / "foo-updater")]
    assert result["count_planned_or_done"] == 5
    assert rc == 1
    assert all(p.exists() for p in paths.values())


def test_dry_run_on_an_empty_home_exits_0(home, tmpdir_):
    rc, result, by_id = run(home, tmpdir_)
    assert rc == 0 and result["count_planned_or_done"] == 0
    assert by_id["npm-cache"]["status"] == "nothing to do"


def test_apply_removes_the_planned_entries_and_keeps_the_rest(home, tmpdir_, tmp_path):
    paths = populate(home)
    log = tmp_path / "clean.log"
    rc, result, by_id = run(home, tmpdir_, "--apply", "--log", str(log))
    assert rc == 0 and result["applied"] is True and result["free_after"] is not None
    for action_id in ("npm-cache", "go-build", "electron-updaters", "old-logs", "npx-stale"):
        assert by_id[action_id]["status"] == "done", action_id
    assert not paths["npm"].exists() and not paths["go"].exists() and not paths["updater"].exists()
    assert not paths["old_log"].exists() and not paths["npx_old"].exists()
    assert paths["new_log"].exists() and paths["npx_new"].exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert any("safe_clean apply" in line for line in lines)
    assert any("npm-cache: done" in line for line in lines)
    assert any("old-logs: done" in line for line in lines)


def test_log_option_also_records_a_dry_run(home, tmpdir_, tmp_path):
    populate(home)
    log = tmp_path / "dry.log"
    run(home, tmpdir_, "--log", str(log))
    assert "dry-run" in log.read_text(encoding="utf-8")


def test_day_thresholds_are_options(home, tmpdir_):
    paths = populate(home)
    _, _, by_id = run(home, tmpdir_, "--log-days", "60", "--npx-days", "60")
    assert by_id["old-logs"]["status"] == "nothing to do"
    assert by_id["npx-stale"]["status"] == "nothing to do"
    assert paths["old_log"].exists()


def test_only_runs_just_the_named_actions(home, tmpdir_):
    paths = populate(home)
    rc, result, by_id = run(home, tmpdir_, "--apply", "--only", "go-build, old-logs")
    assert set(by_id) == {"go-build", "old-logs"}
    assert not paths["go"].exists() and paths["npm"].exists() and paths["updater"].exists()


def test_skip_leaves_the_named_actions_out(home, tmpdir_):
    paths = populate(home)
    rc, result, by_id = run(home, tmpdir_, "--apply", "--skip", "npm-cache,old-logs")
    assert "npm-cache" not in by_id and "old-logs" not in by_id
    assert paths["npm"].exists() and paths["old_log"].exists()
    assert not paths["go"].exists()


@pytest.mark.parametrize("rel", [".npm/_cacache", "Library/Caches/go-build"])
def test_symlinked_cache_is_refused_and_its_target_is_untouched(home, tmpdir_, tmp_path, rel):
    elsewhere = tmp_path / "elsewhere"
    keep = write(elsewhere / "precious.txt")
    link = home / rel
    link.parent.mkdir(parents=True)
    link.symlink_to(elsewhere, target_is_directory=True)
    rc, result, by_id = run(home, tmpdir_, "--apply")
    assert link.is_symlink() and keep.exists() and keep.read_text() == "data" * 1024
    assert by_id["npm-cache" if "npm" in rel else "go-build"]["targets"] == []


def test_dry_run_names_the_refused_symlink(home, tmpdir_, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    write(elsewhere / "precious.txt")
    link = home / ".npm" / "_cacache"
    link.parent.mkdir(parents=True)
    link.symlink_to(elsewhere, target_is_directory=True)
    _, _, by_id = run(home, tmpdir_, "--only", "npm-cache")
    assert "symbolic link" in by_id["npm-cache"]["detail"]
    assert by_id["npm-cache"]["bytes"] == 0 and by_id["npm-cache"]["targets"] == []


def test_apply_does_not_report_a_refused_symlink_as_done(home, tmpdir_, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    write(elsewhere / "precious.txt")
    link = home / ".npm" / "_cacache"
    link.parent.mkdir(parents=True)
    link.symlink_to(elsewhere, target_is_directory=True)
    _, _, by_id = run(home, tmpdir_, "--apply", "--only", "npm-cache")
    row = by_id["npm-cache"]
    assert row["status"] != "done" or "refused" in row["detail"]


def test_safe_path_refuses_outside_and_top_level_folders(home, tmpdir_, tmp_path):
    cleaner = mod.Cleaner(home, tmpdir_, False, False, 1, 14, 7, None)
    assert "outside" in cleaner.safe_path(tmp_path / "elsewhere")
    assert "top-level" in cleaner.safe_path(home / "Library")
    assert cleaner.safe_path(home / ".npm" / "_cacache") is None
    assert cleaner.safe_path(tmpdir_ / "DockerDesktopUpdates") is None


@pytest.mark.parametrize("action_id", COMMAND_ACTIONS)
def test_command_actions_are_skipped_when_commands_are_disabled(home, tmpdir_, action_id):
    rc, result, by_id = run(home, tmpdir_, "--only", action_id)
    assert by_id[action_id]["status"] == "skipped"
    assert by_id[action_id]["bytes"] == 0
    assert rc == 0


def test_apply_never_touches_the_trash(home, tmpdir_):
    populate(home)
    trash_file = write(home / ".Trash" / "x")
    trash_dir_file = write(home / ".Trash" / "folder" / "y")
    rc, _, _ = run(home, tmpdir_, "--apply")
    assert rc == 0
    assert trash_file.read_text() == "data" * 1024 and trash_dir_file.exists()


def test_docker_stuck_installer_removes_update_downloads(home, tmpdir_):
    in_progress = write(home / "Library" / "Application Support" / "com.docker.install" / "in_progress" / "u.dmg")
    updates = write(tmpdir_ / "DockerDesktopUpdates" / "update.bin")
    keep = write(home / "Library" / "Application Support" / "OtherApp" / "settings.json")
    rc, result, by_id = run(home, tmpdir_, "--only", "docker-stuck-installer")
    row = by_id["docker-stuck-installer"]
    assert row["status"] == "planned" and rc == 1
    assert set(row["targets"]) == {str(in_progress.parent), str(updates.parent)}
    assert in_progress.exists() and updates.exists()
    rc, _, by_id = run(home, tmpdir_, "--apply", "--only", "docker-stuck-installer")
    assert by_id["docker-stuck-installer"]["status"] == "done" and rc == 0
    assert not in_progress.parent.exists() and not updates.parent.exists()
    assert keep.exists()
    assert (home / "Library" / "Application Support" / "com.docker.install").is_dir()


def test_docker_stuck_installer_with_nothing_present(home, tmpdir_):
    _, _, by_id = run(home, tmpdir_, "--only", "docker-stuck-installer")
    assert by_id["docker-stuck-installer"]["status"] == "nothing to do"


def test_text_output_describes_the_mode(home, tmpdir_):
    populate(home)
    plain = [a for a in argv(home, tmpdir_) if a != "--json"]
    rc, out, _ = run_main(mod, plain)
    assert rc == 1 and "dry run" in out and "npm-cache" in out
    rc, out, _ = run_main(mod, [*plain, "--apply"])
    assert rc == 0 and "Mode: apply" in out and Path(home / ".npm" / "_cacache").exists() is False
