import json
import os

import pytest
from conftest import load_script, run_json, run_main

mod = load_script("mac-duplicate-finder", "find_dupes.py")

SIZE = 4096


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    folder.mkdir()
    return folder


def blob(path, data=None):
    """Write a small file of random bytes (or the given bytes) and return its content."""
    data = os.urandom(SIZE) if data is None else data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def scan(home, *extra):
    return run_json(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--json", *extra])


def test_help_shows_usage():
    rc, out, _ = run_main(mod, ["--help"])
    assert rc == 0 and "usage:" in out and "--trash-suffix-copies" in out


def test_bad_home_exits_2(tmp_path):
    rc, _, err = run_main(mod, ["--home", str(tmp_path / "missing"), "--quiet"])
    assert rc == 2 and "not a directory" in err


def test_no_existing_roots_exits_2(home):
    rc, _, err = run_main(mod, ["--home", str(home), "--quiet"])
    assert rc == 2 and "no existing root" in err


def test_three_identical_files_across_two_roots_form_one_group(home):
    data = os.urandom(SIZE)
    for rel in ("a/one.bin", "a/two.bin", "b/three.bin"):
        blob(home / rel, data)
    blob(home / "a" / "different.bin")
    rc, rep = scan(home, str(home / "a"), str(home / "b"))
    assert rc == 1 and rep["group_count"] == 1
    group = rep["groups"][0]
    assert group["bytes"] == SIZE and group["wasted"] == 2 * SIZE
    assert group["paths"] == sorted(str(home / rel) for rel in ("a/one.bin", "a/two.bin", "b/three.bin"))
    assert rep["wasted_bytes"] == 2 * SIZE and rep["files_seen"] == 4
    assert rep["moved"] is None and rep["trash_dir"] is None


def test_json_result_shape(home):
    data = blob(home / "a" / "x.bin")
    blob(home / "a" / "y.bin", data)
    _, rep = scan(home, str(home / "a"))
    assert {"home", "roots", "files_seen", "group_count", "wasted_bytes", "groups", "folder_pairs",
            "suffix_copies", "suffix_copies_bytes", "out_dir", "moved", "failed", "moved_bytes",
            "trash_dir"} <= set(rep)
    assert rep["roots"] == [str(home / "a")] and rep["groups"][0]["hash"]


def test_no_duplicates_exits_0(home):
    blob(home / "a" / "x.bin")
    blob(home / "a" / "y.bin")
    rc, rep = scan(home, str(home / "a"))
    assert rc == 0 and rep["groups"] == [] and rep["wasted_bytes"] == 0


def test_same_size_with_different_content_is_not_a_duplicate(home):
    blob(home / "a" / "x.bin", b"a" * SIZE)
    blob(home / "a" / "y.bin", b"b" * SIZE)
    rc, rep = scan(home, str(home / "a"))
    assert rc == 0 and rep["group_count"] == 0


def test_same_head_with_a_different_tail_is_not_a_duplicate(home):
    head = os.urandom(mod.HEAD_BYTES)
    blob(home / "a" / "x.bin", head + b"tail-one")
    blob(home / "a" / "y.bin", head + b"tail-two")
    rc, rep = scan(home, str(home / "a"))
    assert rc == 0 and rep["group_count"] == 0


def test_files_below_min_mb_are_ignored(home):
    data = blob(home / "a" / "x.bin")
    blob(home / "a" / "y.bin", data)
    rc, rep = run_json(mod, ["--home", str(home), "--min-mb", "1", "--quiet", "--json", str(home / "a")])
    assert rc == 0 and rep["group_count"] == 0 and rep["files_seen"] == 2


def test_default_roots_come_from_the_home_folder(home):
    data = blob(home / "Documents" / "x.bin")
    blob(home / "Documents" / "y.bin", data)
    rc, rep = scan(home)
    assert rc == 1 and rep["roots"] == [str(home / r) for r in mod.DEFAULT_ROOTS if (home / r).is_dir()]
    assert rep["group_count"] == 1


def test_suffix_copies_are_matched_to_their_originals(home):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG.MOV", data)
    blob(home / "a" / "IMG (1).MOV", data)
    blob(home / "a" / "IMG copy.MOV", data)
    rc, rep = scan(home, str(home / "a"))
    assert rc == 1 and len(rep["suffix_copies"]) == 2
    copies = {c["copy"] for c in rep["suffix_copies"]}
    assert str(home / "a" / "IMG (1).MOV") in copies
    assert str(home / "a" / "IMG copy.MOV") in copies


def test_suffix_name_without_an_original_is_not_a_suffix_copy(home):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG (1).MOV", data)
    blob(home / "a" / "other.MOV", data)
    rc, rep = scan(home, str(home / "a"))
    assert rc == 1 and rep["suffix_copies"] == []


def test_trash_suffix_copies_moves_only_the_copies(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG.MOV", data)
    blob(home / "a" / "IMG (1).MOV", data)
    trash = tmp_path / "trash"
    rc, rep = run_json(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--json",
                             "--trash-suffix-copies", "--trash-dir", str(trash), str(home / "a")])
    assert rc == 1
    assert (trash / "a" / "IMG (1).MOV").is_file()
    assert (home / "a" / "IMG.MOV").is_file()
    assert not (home / "a" / "IMG (1).MOV").exists()
    assert len(rep["moved"]) == 1 and rep["failed"] == []


def test_without_the_flag_nothing_is_moved(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG.MOV", data)
    blob(home / "a" / "IMG (1).MOV", data)
    rc, rep = scan(home, str(home / "a"))
    assert (home / "a" / "IMG (1).MOV").is_file()
    assert rep["moved"] is None


def test_trash_copies_does_not_move_a_copy_changed_after_the_scan(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG.MOV", data)
    copy = home / "a" / "IMG (1).MOV"
    blob(copy, data)
    # change the copy after the scan would have hashed it
    copy.write_bytes(data + b"changed")
    trash = tmp_path / "trash"
    rc, rep = run_json(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--json",
                             "--trash-suffix-copies", "--trash-dir", str(trash), str(home / "a")])
    assert rc == 1
    assert rep["moved"] == [] and len(rep["failed"]) == 1
    assert "differ" in rep["failed"][0]["error"]
    assert copy.is_file()


def test_trash_copies_reports_a_missing_copy_and_an_existing_destination(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "IMG.MOV", data)
    blob(home / "a" / "IMG (1).MOV", data)
    trash = tmp_path / "trash"
    (trash / "a").mkdir(parents=True)
    (trash / "a" / "IMG (1).MOV").write_bytes(b"already there")
    rc, rep = run_json(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--json",
                             "--trash-suffix-copies", "--trash-dir", str(trash), str(home / "a")])
    assert len(rep["failed"]) == 1 and "already" in rep["failed"][0]["error"]


def test_out_dir_writes_the_three_lists(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "x.bin", data)
    blob(home / "a" / "y.bin", data)
    out = tmp_path / "out"
    rc, rep = run_json(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--json",
                             "--out-dir", str(out), str(home / "a")])
    assert (out / "duplicates.txt").is_file()
    assert (out / "suffix-copies.txt").is_file()
    assert (out / "folder-pairs.txt").is_file()
    text = (out / "duplicates.txt").read_text()
    assert str(home / "a" / "x.bin") in text


def test_node_modules_and_other_default_excludes_are_skipped(home):
    data = os.urandom(SIZE)
    blob(home / "a" / "x.bin", data)
    blob(home / "node_modules" / "x.bin", data)
    rc, rep = scan(home, str(home))
    assert rep["group_count"] == 0  # the one in node_modules is skipped, so no group


def test_exclude_dir_replaces_the_default_list(home):
    data = os.urandom(SIZE)
    blob(home / "keep" / "x.bin", data)
    blob(home / "skipme" / "x.bin", data)
    rc, rep = scan(home, str(home), "--exclude-dir", "skipme")
    assert rep["group_count"] == 0


def test_symlinked_files_and_folders_are_skipped(home, tmp_path):
    data = os.urandom(SIZE)
    blob(home / "a" / "x.bin", data)
    (home / "a" / "link.bin").symlink_to(home / "a" / "x.bin")
    rc, rep = scan(home, str(home / "a"))
    assert rep["files_seen"] == 1 and rep["group_count"] == 0


def test_ext_filters_to_named_extensions_only(home):
    """--ext mov keeps the video pair and drops the PDF pair (as on the demo home)."""
    video = os.urandom(SIZE)
    pdf = os.urandom(SIZE)
    blob(home / "Desktop" / "IMG.MOV", video)
    blob(home / "Desktop" / "IMG (1).MOV", video)
    blob(home / "Documents" / "a.pdf", pdf)
    blob(home / "Downloads" / "a.pdf", pdf)
    rc, rep = scan(home, "--ext", "mov")
    assert rc == 1 and rep["group_count"] == 1
    assert rep["extensions"] == ["mov"]
    paths = rep["groups"][0]["paths"]
    assert all(p.endswith(".MOV") for p in paths)
    assert not any(p.endswith(".pdf") for p in paths)


def test_ext_accepts_dot_and_mixed_case_and_multiple(home):
    jpg = os.urandom(SIZE)
    png = os.urandom(SIZE)
    blob(home / "a" / "x.JPG", jpg)
    blob(home / "a" / "y.jpg", jpg)
    blob(home / "a" / "z.PNG", png)
    blob(home / "a" / "w.png", png)
    rc, rep = scan(home, str(home / "a"), "--ext", ".jpg,PNG")
    assert rc == 1 and rep["group_count"] == 2
    assert set(rep["extensions"]) == {"jpg", "png"}


def test_ext_empty_or_blank_is_usage_error(home):
    for bad in (",", " , ", "  ", ""):
        rc, _, err = run_main(mod, ["--home", str(home), "--ext", bad, "--quiet"])
        assert rc == 2 and "extensions" in err.lower()


def test_report_mentions_extensions_when_filtered(home):
    data = os.urandom(SIZE)
    blob(home / "a" / "x.mov", data)
    blob(home / "a" / "y.mov", data)
    rc, out, _ = run_main(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", "--ext", "mov", str(home / "a")])
    assert rc == 1 and "Only files with extensions: mov" in out
