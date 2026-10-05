import plistlib
import sys

import pytest
from conftest import load_script, run_json, run_main

mod = load_script("mac-app-leftovers", "app_leftovers.py")
NO_STARTUP = {"login_items": [], "launch_agents": [], "launch_daemons": []}


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    (folder / "Library").mkdir(parents=True)
    return folder


@pytest.fixture
def apps(tmp_path):
    folder = tmp_path / "Applications"
    folder.mkdir()
    return folder


@pytest.fixture(autouse=True)
def empty_path(tmp_path, monkeypatch):
    """Executables on PATH count as installed tools, so give every test an empty PATH folder."""
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", str(folder))
    return folder


@pytest.fixture
def no_system_startup(monkeypatch):
    """startup_leftovers also reads the real /Library/LaunchAgents and /Library/LaunchDaemons; stub it out."""
    monkeypatch.setattr(mod, "startup_leftovers", lambda *a, **k: {k2: [] for k2 in NO_STARTUP})


def fake_app(apps, name, bundle_id, display=None):
    info = apps / f"{name}.app" / "Contents" / "Info.plist"
    info.parent.mkdir(parents=True)
    info.write_bytes(plistlib.dumps({"CFBundleIdentifier": bundle_id, "CFBundleName": display or name}))


def entry(home, area, name, text="x" * 2048):
    path = home / "Library" / area / name
    if name.endswith(".plist"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps({"k": "v"}))
    else:
        path.mkdir(parents=True)
        (path / "data.txt").write_text(text, encoding="utf-8")
    return path


def scan(home, apps, *extra):
    return run_json(mod, ["--home", str(home), "--apps-dir", str(apps), "--no-commands", "--json", *extra])


def ids(rep):
    return {c["id"] for c in rep["candidates"]}


def test_help_shows_usage():
    rc, out, _ = run_main(mod, ["--help"])
    assert rc == 0 and "usage:" in out and "--trash" in out


def test_bad_home_exits_2(tmp_path, apps):
    rc, _, err = run_main(mod, ["--home", str(tmp_path / "missing"), "--apps-dir", str(apps), "--no-commands"])
    assert rc == 2 and "not a directory" in err


def test_folder_with_no_installed_app_is_a_candidate(home, apps):
    path = entry(home, "Application Support", "Superhuman")
    rc, rep = scan(home, apps)
    assert rc == 1 and ids(rep) == {"app-support:Superhuman"}
    cand = rep["candidates"][0]
    assert cand["area"] == "app-support" and cand["name"] == "Superhuman" and cand["path"] == str(path)
    assert cand["bytes"] > 0 and cand["last_changed"]
    assert rep["candidate_bytes"] == cand["bytes"]


def test_json_result_shape(home, apps):
    fake_app(apps, "Known", "com.example.known")
    _, rep = scan(home, apps)
    assert {"home", "installed_apps", "candidates", "candidate_bytes", "startup", "moved", "failed", "moved_bytes",
            "trash_dir", "seconds"} <= set(rep)
    assert rep["installed_apps"] == 1 and set(rep["startup"]) == set(NO_STARTUP)
    assert rep["moved"] is None and rep["trash_dir"] is None


def test_no_candidates_exits_0(home, apps, no_system_startup):
    entry(home, "Application Support", "Known")
    fake_app(apps, "Known", "com.example.known")
    rc, rep = scan(home, apps)
    assert rc == 0 and rep["candidates"] == []


def test_name_shared_with_an_installed_app_is_not_a_candidate(home, apps):
    fake_app(apps, "Google Chrome", "com.google.Chrome")
    entry(home, "Application Support", "Google")
    entry(home, "Application Support", "Superhuman")
    rc, rep = scan(home, apps)
    assert ids(rep) == {"app-support:Superhuman"}


def test_container_with_an_installed_bundle_id_is_not_a_candidate(home, apps):
    fake_app(apps, "Installed", "com.example.installed")
    entry(home, "Containers", "com.example.installed")
    entry(home, "Containers", "io.vendorx.gone")
    rc, rep = scan(home, apps)
    assert ids(rep) == {"containers:io.vendorx.gone"}


def test_apple_preferences_are_never_candidates(home, apps):
    entry(home, "Preferences", "com.apple.anything.plist")
    entry(home, "Preferences", "io.vendorx.gone.plist")
    entry(home, "Containers", "com.apple.Notes")
    rc, rep = scan(home, apps)
    assert ids(rep) == {"preferences:io.vendorx.gone.plist"}


def test_only_plist_files_are_candidates_in_preferences(home, apps):
    prefs = home / "Library" / "Preferences"
    prefs.mkdir()
    (prefs / "notes.txt").write_text("x", encoding="utf-8")
    entry(home, "Preferences", "io.vendorx.gone.plist")
    _, rep = scan(home, apps)
    assert ids(rep) == {"preferences:io.vendorx.gone.plist"}


def test_group_container_team_prefix_is_stripped_before_matching(home, apps):
    # Short bundle id parts give no tokens, so only an exact match on the stripped name can claim the entry.
    fake_app(apps, "XY", "com.ab.cd")
    entry(home, "Group Containers", "ABCDE12345.com.ab.cd")
    entry(home, "Group Containers", "ZZZZZ99999.com.gone.thing")
    _, rep = scan(home, apps)
    assert ids(rep) == {"group-containers:ZZZZZ99999.com.gone.thing"}


def test_dotted_names_and_system_names_are_not_candidates(home, apps):
    entry(home, "Application Support", ".hidden")
    entry(home, "Application Support", "Dock")
    entry(home, "Caches", "Homebrew")
    _, rep = scan(home, apps)
    assert rep["candidates"] == []


def test_keep_hides_a_name(home, apps):
    entry(home, "Application Support", "Superhuman")
    entry(home, "Application Support", "Other")
    entry(home, "Preferences", "com.keep.me.plist")
    _, rep = scan(home, apps, "--keep", "superhuman", "--keep", "com.keep.me")
    assert ids(rep) == {"app-support:Other"}


def test_candidates_are_sorted_largest_first(home, apps):
    entry(home, "Application Support", "Small", "x" * 10)
    entry(home, "Application Support", "Large", "x" * 200000)
    _, rep = scan(home, apps)
    assert [c["name"] for c in rep["candidates"]] == ["Large", "Small"]


def test_launch_agent_with_a_missing_program_is_listed_with_a_fix(home, apps):
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir()
    gone = agents / "com.gone.agent.plist"
    gone.write_bytes(plistlib.dumps({"Label": "com.gone.agent", "ProgramArguments": ["/no/such/dir/gone", "--x"]}))
    (agents / "com.ok.agent.plist").write_bytes(plistlib.dumps({"ProgramArguments": [sys.executable]}))
    (agents / "com.bare.agent.plist").write_bytes(plistlib.dumps({"ProgramArguments": ["gone-without-a-path"]}))
    rc, rep = scan(home, apps)
    mine = [a for a in rep["startup"]["launch_agents"] if a["plist"].startswith(str(home))]
    assert [a["plist"] for a in mine] == [str(gone)]
    assert mine[0]["program"] == "/no/such/dir/gone"
    assert "launchctl bootout" in mine[0]["fix"] and str(gone) in mine[0]["fix"]
    assert "sudo" not in mine[0]["fix"]
    assert rc == 1



def test_launch_agent_fix_does_not_need_os_getuid(home, apps, monkeypatch):
    """os.getuid is POSIX-only; without it the fix leaves the uid to the shell instead of crashing."""
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir()
    gone = agents / "com.gone.agent.plist"
    gone.write_bytes(plistlib.dumps({"Label": "com.gone.agent", "ProgramArguments": ["/no/such/dir/gone"]}))
    monkeypatch.delattr(mod.os, "getuid", raising=False)
    rc, rep = scan(home, apps)
    mine = [a for a in rep["startup"]["launch_agents"] if a["plist"].startswith(str(home))]
    assert mine and "launchctl bootout gui/$(id -u) " in mine[0]["fix"]
    assert rc == 1

def test_trash_moves_the_candidate_and_keeps_its_relative_path(home, apps, tmp_path):
    path = entry(home, "Application Support", "Superhuman")
    other = entry(home, "Application Support", "Other")
    trash = tmp_path / "trash"
    rc, rep = scan(home, apps, "--trash", "app-support:Superhuman", "--trash-dir", str(trash))
    dest = trash / "Library" / "Application Support" / "Superhuman"
    assert [m["moved_to"] for m in rep["moved"]] == [str(dest)]
    assert (dest / "data.txt").read_text(encoding="utf-8") == "x" * 2048
    assert not path.exists() and other.exists()
    assert rep["failed"] == [] and rep["trash_dir"] == str(trash) and rep["moved_bytes"] > 0
    assert rc == 1


def test_trashing_an_id_that_is_not_a_candidate_fails(home, apps, tmp_path, no_system_startup):
    keep = entry(home, "Application Support", "Known")
    fake_app(apps, "Known", "com.example.known")
    trash = tmp_path / "trash"
    rc, rep = scan(home, apps, "--trash", "app-support:Known,app-support:Missing", "--trash-dir", str(trash))
    assert rep["moved"] == [] and keep.exists()
    assert sorted(f["id"] for f in rep["failed"]) == ["app-support:Known", "app-support:Missing"]
    assert all("not a candidate" in f["error"] for f in rep["failed"])
    assert rc == 0


def test_trash_does_not_overwrite_an_existing_destination(home, apps, tmp_path):
    path = entry(home, "Application Support", "Superhuman")
    trash = tmp_path / "trash"
    (trash / "Library" / "Application Support" / "Superhuman").mkdir(parents=True)
    _, rep = scan(home, apps, "--trash", "app-support:Superhuman", "--trash-dir", str(trash))
    assert rep["moved"] == [] and "already in the trash folder" in rep["failed"][0]["error"]
    assert path.exists()


def test_text_output_lists_candidates_and_the_ids_to_use(home, apps):
    entry(home, "Application Support", "Superhuman")
    rc, out, _ = run_main(mod, ["--home", str(home), "--apps-dir", str(apps), "--no-commands"])
    assert rc == 1 and "app-support:Superhuman" in out and "Leftover candidates (1" in out


def test_candidates_say_whether_they_are_app_data_or_regenerable(home, apps):
    entry(home, "Application Support", "Superhuman")
    entry(home, "Caches", "bigcache", "x" * 2_000_000)
    _, rep = scan(home, apps)
    kinds = {c["id"]: c["kind"] for c in rep["candidates"]}
    assert kinds == {"app-support:Superhuman": "app data", "caches:bigcache": "cache or log (regenerable)"}


def test_small_cache_log_and_webkit_entries_are_hidden_below_min_mb(home, apps):
    entry(home, "Caches", "tinycache")
    entry(home, "Logs", "tinylog")
    entry(home, "WebKit", "tinykit")
    entry(home, "Application Support", "Tiny")
    _, rep = scan(home, apps)
    assert ids(rep) == {"app-support:Tiny"}
    _, rep = scan(home, apps, "--min-mb", "0")
    assert ids(rep) == {"app-support:Tiny", "caches:tinycache", "logs:tinylog", "webkit:tinykit"}


def test_uuid_named_containers_are_never_candidates(home, apps):
    entry(home, "Containers", "0A1B2C3D-4E5F-6789-ABCD-0123456789AB")
    entry(home, "Containers", "io.vendorx.gone")
    _, rep = scan(home, apps)
    assert ids(rep) == {"containers:io.vendorx.gone"}


def test_a_team_id_used_by_an_installed_app_vouches_for_its_other_group_containers(home, apps):
    fake_app(apps, "XY", "com.ab.cd")
    entry(home, "Group Containers", "ABCDE12345.com.ab.cd")
    entry(home, "Group Containers", "ABCDE12345.shared.stuff")
    entry(home, "Group Containers", "ZZZZZ99999.shared.stuff")
    _, rep = scan(home, apps)
    assert ids(rep) == {"group-containers:ZZZZZ99999.shared.stuff"}


def test_a_command_line_tool_on_path_claims_its_data(home, apps, empty_path):
    tool = empty_path / "vendorxtool"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    entry(home, "Application Support", "vendorxtool")
    entry(home, "Application Support", "Superhuman")
    _, rep = scan(home, apps)
    assert ids(rep) == {"app-support:Superhuman"}


def test_a_name_containing_an_installed_app_name_is_not_a_candidate(home, apps):
    fake_app(apps, "Slack", "com.tinyspeck.slackmacgap")
    entry(home, "Application Support", "SlackBackupData")
    entry(home, "Application Support", "Superhuman")
    _, rep = scan(home, apps)
    assert ids(rep) == {"app-support:Superhuman"}
