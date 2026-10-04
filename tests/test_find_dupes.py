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
    blob(home / "Pictures" / "y.bin", data)
    blob(home / "Elsewhere" / "z.bin", data)
    rc, rep = scan(home)
    assert rc == 1 and sorted(rep["roots"]) == [str(home / "Documents"), str(home / "Pictures")]
    assert len(rep["groups"][0]["paths"]) == 2


def test_suffix_copies_are_matched_to_their_originals(home):
    pics = home / "Pictures"
    data = blob(pics / "IMG_1.MOV")
    blob(pics / "IMG_1 (1).MOV", data)
    other = blob(pics / "other.mov")
    blob(pics / "other copy.mov", other)
    rc, rep = scan(home, str(pics))
    pairs = {c["copy"]: c["original"] for c in rep["suffix_copies"]}
    assert pairs == {str(pics / "IMG_1 (1).MOV"): str(pics / "IMG_1.MOV"),
                     str(pics / "other copy.mov"): str(pics / "other.mov")}
    assert rep["suffix_copies_bytes"] == 2 * SIZE and rc == 1


def test_suffix_name_without_an_original_is_not_a_suffix_copy(home):
    pics = home / "Pictures"
    data = blob(pics / "report (1).pdf")
    blob(pics / "unrelated.pdf", data)
    blob(pics / "sub" / "report.pdf", data)  # same name as the original, but in another folder
    rc, rep = scan(home, str(pics))
    assert rep["group_count"] == 1 and rep["suffix_copies"] == []


def test_trash_suffix_copies_moves_only_the_copies(home, tmp_path):
    pics = home / "Pictures"
    data = blob(pics / "trip" / "IMG_1.MOV")
    blob(pics / "trip" / "IMG_1 (1).MOV", data)
    twin = blob(pics / "plain-twin.mov")
    blob(pics / "elsewhere" / "plain-twin-b.mov", twin)  # a duplicate that is not a suffix copy
    trash = tmp_path / "trash"
    rc, rep = scan(home, str(pics), "--trash-suffix-copies", "--trash-dir", str(trash))
    assert rc == 1 and rep["failed"] == [] and rep["trash_dir"] == str(trash)
    moved_to = trash / "Pictures" / "trip" / "IMG_1 (1).MOV"
    assert [m["moved_to"] for m in rep["moved"]] == [str(moved_to)]
    assert rep["moved_bytes"] == SIZE
    assert moved_to.read_bytes() == data
    assert not (pics / "trip" / "IMG_1 (1).MOV").exists()
    assert (pics / "trip" / "IMG_1.MOV").read_bytes() == data
    assert (pics / "plain-twin.mov").exists() and (pics / "elsewhere" / "plain-twin-b.mov").exists()


def test_without_the_flag_nothing_is_moved(home, tmp_path):
    pics = home / "Pictures"
    data = blob(pics / "IMG_1.MOV")
    blob(pics / "IMG_1 (1).MOV", data)
    trash = tmp_path / "trash"
    scan(home, str(pics), "--trash-dir", str(trash))
    assert (pics / "IMG_1 (1).MOV").exists() and not trash.exists()


def test_trash_copies_does_not_move_a_copy_changed_after_the_scan(home, tmp_path):
    pics = home / "Pictures"
    data = blob(pics / "IMG_1.MOV")
    safe_copy = pics / "IMG_1 (1).MOV"
    blob(safe_copy, data)
    changed_original = blob(pics / "doc.txt", b"a" * SIZE)
    changed_copy = pics / "doc copy.txt"
    blob(changed_copy, changed_original)
    items = [{"copy": str(safe_copy), "original": str(pics / "IMG_1.MOV"), "bytes": SIZE},
             {"copy": str(changed_copy), "original": str(pics / "doc.txt"), "bytes": SIZE}]
    changed_copy.write_bytes(b"b" * SIZE)  # same size, different content, after the scan
    moved, failed = mod.trash_copies(items, tmp_path / "trash", home, None)
    assert [m["copy"] for m in moved] == [str(safe_copy)]
    assert [f["copy"] for f in failed] == [str(changed_copy)]
    assert "differ" in failed[0]["error"]
    assert changed_copy.read_bytes() == b"b" * SIZE
    assert not (tmp_path / "trash" / "Pictures" / "doc copy.txt").exists()


def test_trash_copies_reports_a_missing_copy_and_an_existing_destination(home, tmp_path):
    pics = home / "Pictures"
    data = blob(pics / "a.bin")
    blob(pics / "a (1).bin", data)
    blob(pics / "b.bin", data)
    trash = tmp_path / "trash"
    blob(trash / "Pictures" / "a (1).bin", b"already here")
    items = [{"copy": str(pics / "a (1).bin"), "original": str(pics / "a.bin"), "bytes": SIZE},
             {"copy": str(pics / "gone (1).bin"), "original": str(pics / "b.bin"), "bytes": SIZE}]
    moved, failed = mod.trash_copies(items, trash, home, None)
    assert moved == []
    assert "already in the trash folder" in failed[0]["error"]
    assert "no longer exists" in failed[1]["error"]
    assert (pics / "a (1).bin").exists()


def test_out_dir_writes_the_three_lists(home, tmp_path):
    pics = home / "Pictures"
    data = blob(pics / "IMG_1.MOV")
    blob(pics / "IMG_1 (1).MOV", data)
    out = tmp_path / "reports"
    rc, rep = scan(home, str(pics), "--out-dir", str(out))
    assert sorted(p.name for p in out.iterdir()) == ["duplicates.txt", "folder-pairs.txt", "suffix-copies.txt"]
    assert (out / "suffix-copies.txt").read_text(encoding="utf-8").splitlines() == [str(pics / "IMG_1 (1).MOV")]
    duplicates = (out / "duplicates.txt").read_text(encoding="utf-8")
    assert "2 copies" in duplicates and str(pics / "IMG_1.MOV") in duplicates
    assert "Pictures" in (out / "folder-pairs.txt").read_text(encoding="utf-8")
    assert rep["out_dir"] == str(out)


def test_node_modules_and_other_default_excludes_are_skipped(home):
    data = blob(home / "proj" / "x.bin")
    blob(home / "proj" / "node_modules" / "pkg" / "x.bin", data)
    blob(home / "proj" / ".git" / "objects" / "x.bin", data)
    rc, rep = scan(home, str(home / "proj"))
    assert rc == 0 and rep["group_count"] == 0 and rep["files_seen"] == 1


def test_exclude_dir_replaces_the_default_list(home):
    data = blob(home / "proj" / "x.bin")
    blob(home / "proj" / "node_modules" / "x.bin", data)
    blob(home / "proj" / "skipme" / "x.bin", data)
    rc, rep = scan(home, str(home / "proj"), "--exclude-dir", "skipme")
    assert rc == 1 and len(rep["groups"][0]["paths"]) == 2
    assert str(home / "proj" / "node_modules" / "x.bin") in rep["groups"][0]["paths"]
    assert str(home / "proj" / "skipme" / "x.bin") not in rep["groups"][0]["paths"]


def test_symlinked_files_and_folders_are_skipped(home, tmp_path):
    data = blob(home / "a" / "x.bin")
    (home / "a" / "link.bin").symlink_to(home / "a" / "x.bin")
    outside = tmp_path / "outside"
    blob(outside / "x.bin", data)
    (home / "a" / "linked-dir").symlink_to(outside, target_is_directory=True)
    rc, rep = scan(home, str(home / "a"))
    assert rc == 0 and rep["group_count"] == 0 and rep["files_seen"] == 1


def test_folder_pairs_aggregate_by_the_folders_a_group_spans(home):
    for name in ("one.bin", "two.bin"):
        data = blob(home / "a" / name)
        blob(home / "b" / name, data)
    inner = blob(home / "a" / "inner" / "x.bin")
    blob(home / "a" / "inner" / "y.bin", inner)
    rc, rep = scan(home, str(home / "a"), str(home / "b"), "--pair-depth", "1")
    pairs = {tuple(p["folders"]): p for p in rep["folder_pairs"]}
    assert pairs[("a", "b")]["groups"] == 2 and pairs[("a", "b")]["wasted"] == 2 * SIZE
    assert pairs[("a",)]["groups"] == 1
    assert rep["folder_pairs"][0]["wasted"] >= rep["folder_pairs"][-1]["wasted"]


def test_pair_depth_controls_the_folder_levels(home):
    data = blob(home / "a" / "deep" / "x.bin")
    blob(home / "a" / "other" / "x.bin", data)
    _, rep = scan(home, str(home / "a"), "--pair-depth", "2")
    assert rep["folder_pairs"][0]["folders"] == ["a/deep", "a/other"]
    _, rep = scan(home, str(home / "a"), "--pair-depth", "1")
    assert rep["folder_pairs"][0]["folders"] == ["a"]


def test_groups_are_ordered_by_wasted_bytes(home):
    small = blob(home / "a" / "s1.bin", os.urandom(2000))
    blob(home / "a" / "s2.bin", small)
    big = blob(home / "a" / "b1.bin", os.urandom(9000))
    blob(home / "a" / "b2.bin", big)
    blob(home / "a" / "b3.bin", big)
    _, rep = scan(home, str(home / "a"))
    assert [g["wasted"] for g in rep["groups"]] == [18000, 2000]


def test_text_output_summarises_the_scan(home):
    data = blob(home / "a" / "x.bin")
    blob(home / "a" / "y.bin", data)
    rc, out, _ = run_main(mod, ["--home", str(home), "--min-mb", "0.001", "--quiet", str(home / "a")])
    assert rc == 1 and "1 duplicate groups" in out and "Suffix copies next to an identical original: 0" in out
    assert json.dumps(out)  # plain text, not JSON
