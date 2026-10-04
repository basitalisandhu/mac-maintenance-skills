import json
import plistlib
import sys

import pytest
from conftest import load_script, run_json, run_main

mod = load_script("mac-cleanup", "mac_survey.py")


@pytest.fixture(autouse=True)
def private_tmpdir(tmp_path, monkeypatch):
    """The survey measures $TMPDIR; point it at an empty folder so no real temp data is walked."""
    folder = tmp_path / "tmpdir"
    folder.mkdir()
    monkeypatch.setenv("TMPDIR", str(folder))


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    folder.mkdir()
    return folder


def write(path, size=65536, byte=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(byte * size)
    return path


def args(tmp_path, home, *extra):
    apps = tmp_path / "Applications"
    apps.mkdir(exist_ok=True)
    return ["--home", str(home), "--apps-dir", str(apps), "--no-commands", "--quiet", "--json", *extra]


def survey(tmp_path, home, *extra):
    return run_json(mod, args(tmp_path, home, *extra))


def test_help_shows_usage():
    rc, out, _ = run_main(mod, ["--help"])
    assert rc == 0 and "usage:" in out and "--fast" in out


def test_bad_home_exits_2(tmp_path):
    rc, _, err = run_main(mod, ["--home", str(tmp_path / "missing"), "--no-commands", "--quiet"])
    assert rc == 2 and "not a directory" in err


def test_json_report_has_the_documented_keys(tmp_path, home):
    _, rep = survey(tmp_path, home, "--fast")
    assert {"home", "sections", "unverified", "candidates", "seconds"} <= set(rep)
    assert rep["home"] == str(home)
    assert {"disk", "home", "caches", "apps", "startup", "processes"} <= set(rep["sections"])


def test_caches_are_listed_with_byte_counts_and_become_candidates(tmp_path, home):
    write(home / ".npm" / "_cacache" / "content" / "a.bin")
    write(home / "Library" / "Caches" / "go-build" / "ab" / "obj")
    rc, rep = survey(tmp_path, home, "--fast")
    known = {row["path"]: row for row in rep["sections"]["caches"]["known"]}
    npm = known[str(home / ".npm" / "_cacache")]
    go = known[str(home / "Library" / "Caches" / "go-build")]
    assert isinstance(npm["bytes"], int) and npm["bytes"] > 0
    assert isinstance(go["bytes"], int) and go["bytes"] > 0
    assert npm["comes_back"] == "npm re-downloads packages"
    wanted = {c["what"] for c in rep["candidates"] if c["kind"] == "cache"}
    assert {str(home / ".npm" / "_cacache"), str(home / "Library" / "Caches" / "go-build")} <= wanted
    assert rc == 1


def test_empty_home_has_no_candidates_and_exits_0(tmp_path, home, monkeypatch):
    # The startup section also reads the real /Library/LaunchAgents; keep this test independent of the machine.
    monkeypatch.setattr(mod.Survey, "startup", lambda self: None)
    rc, rep = survey(tmp_path, home, "--fast")
    assert rep["candidates"] == []
    assert rc == 0


def test_trash_and_downloads_are_listed_but_not_candidates(tmp_path, home):
    write(home / ".Trash" / "old.bin")
    write(home / "Downloads" / "notes.txt")
    _, rep = survey(tmp_path, home, "--fast")
    paths = {row["path"] for row in rep["sections"]["caches"]["known"]}
    assert {str(home / ".Trash"), str(home / "Downloads")} <= paths
    assert not [c for c in rep["candidates"] if c["kind"] == "cache"]


def test_installer_files_in_downloads_are_listed(tmp_path, home):
    write(home / "Downloads" / "tool.dmg", size=2048)
    write(home / "Downloads" / "readme.txt", size=2048)
    _, rep = survey(tmp_path, home, "--fast")
    names = [row["path"] for row in rep["sections"]["caches"]["installers"]]
    assert names == [str(home / "Downloads" / "tool.dmg")]


def test_out_writes_the_json_report(tmp_path, home):
    write(home / ".npm" / "_cacache" / "a.bin")
    target = tmp_path / "report.json"
    rc, rep = survey(tmp_path, home, "--fast", "--out", str(target))
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["home"] == rep["home"] and saved["candidates"] == rep["candidates"]
    assert rc == 1


def test_unverified_entries_say_commands_are_disabled(tmp_path, home):
    _, rep = survey(tmp_path, home, "--fast")
    sections = {u["section"] for u in rep["unverified"]}
    assert {"docker", "brew", "processes"} <= sections
    assert all("commands disabled" in u["reason"] for u in rep["unverified"])


def test_large_file_and_node_modules_are_reported_without_fast(tmp_path, home):
    big = write(home / "Movies" / "big.bin", size=2 * 1024 * 1024)
    write(home / "projects" / "app" / "node_modules" / "pkg" / "data.bin", size=2 * 1024 * 1024)
    rc, rep = survey(tmp_path, home, "--large-mb", "1", "--node-mb", "1")
    assert [row["path"] for row in rep["sections"]["large"]] == [str(big)]
    assert rep["sections"]["large"][0]["bytes"] == 2 * 1024 * 1024
    node = rep["sections"]["node"]
    assert [row["path"] for row in node] == [str(home / "projects" / "app" / "node_modules")]
    assert any(c["kind"] == "node_modules" for c in rep["candidates"])
    assert rc == 1


def test_fast_skips_the_home_walk(tmp_path, home):
    write(home / "Movies" / "big.bin", size=2 * 1024 * 1024)
    _, rep = survey(tmp_path, home, "--fast", "--large-mb", "1")
    assert "large" not in rep["sections"] and "node" not in rep["sections"]


def test_files_below_the_thresholds_are_not_reported(tmp_path, home):
    write(home / "Movies" / "small.bin", size=2048)
    write(home / "projects" / "node_modules" / "pkg" / "data.bin", size=2048)
    _, rep = survey(tmp_path, home, "--large-mb", "1", "--node-mb", "1")
    assert rep["sections"]["large"] == [] and rep["sections"]["node"] == []


def test_library_and_symlinked_folders_are_not_walked_for_large_files(tmp_path, home):
    write(home / "Library" / "Application Support" / "big.bin", size=2 * 1024 * 1024)
    outside = tmp_path / "outside"
    write(outside / "big.bin", size=2 * 1024 * 1024)
    (home / "linked").symlink_to(outside, target_is_directory=True)
    _, rep = survey(tmp_path, home, "--large-mb", "1")
    assert rep["sections"]["large"] == []


def test_apps_section_reads_bundles_and_flags_likely_duplicates(tmp_path, home):
    apps = tmp_path / "Applications"
    for name, bundle in (("Foo", "com.example.foo"), ("Foo 2", "com.example.foo2")):
        info = apps / f"{name}.app" / "Contents" / "Info.plist"
        info.parent.mkdir(parents=True)
        info.write_bytes(plistlib.dumps({"CFBundleIdentifier": bundle, "CFBundleShortVersionString": "1.2"}))
    _, rep = survey(tmp_path, home, "--fast")
    rows = {r["name"]: r for r in rep["sections"]["apps"]["apps"]}
    assert rows["Foo"]["bundle_id"] == "com.example.foo" and rows["Foo"]["version"] == "1.2"
    assert rows["Foo"]["last_used"] is None
    assert sorted(rep["sections"]["apps"]["likely_duplicates"][0]) == ["Foo", "Foo 2"]
    assert any(c["kind"] == "apps" for c in rep["candidates"])


def test_launch_agent_with_a_missing_program_is_a_candidate(tmp_path, home):
    plist = home / "Library" / "LaunchAgents" / "com.gone.agent.plist"
    plist.parent.mkdir(parents=True)
    plist.write_bytes(plistlib.dumps({"Label": "com.gone.agent", "ProgramArguments": ["/no/such/dir/gone"]}))
    ok = home / "Library" / "LaunchAgents" / "com.ok.agent.plist"
    ok.write_bytes(plistlib.dumps({"Label": "com.ok.agent", "ProgramArguments": [sys.executable]}))
    rc, rep = survey(tmp_path, home, "--fast")
    agents = {a["plist"]: a for a in rep["sections"]["startup"]["launch_agents"]}
    assert agents[str(plist)]["program_missing"] is True
    assert agents[str(ok)]["program_missing"] is False
    startup = [c["what"] for c in rep["candidates"] if c["kind"] == "startup"]
    assert str(plist) in startup and str(ok) not in startup
    assert rc == 1


def test_text_output_lists_candidates(tmp_path, home):
    write(home / ".npm" / "_cacache" / "a.bin")
    rc, out, _ = run_main(mod, [a for a in args(tmp_path, home, "--fast") if a != "--json"])
    assert rc == 1
    assert "Reclaimable candidates:" in out and "npm download cache" in out
    assert "Unverified (not measured, so not claimed):" in out
