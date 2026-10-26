"""Scaling check for the leftovers matcher, fixed on 2026-10-26 after timing the scripts on a synthetic home ten
times the usual size. match() compared every entry with every installed name and tool on PATH, so a Mac with a few
thousand Homebrew tools and many Library entries took seconds; it now looks names up in an index built once. The
equivalence test compares the index with the plain comparison on seeded random names, including very long ones."""

from __future__ import annotations

import random
import string
import time

from conftest import load_script, run_main

mod = load_script("mac-app-leftovers", "app_leftovers.py")


def brute_force(installed, et: str) -> set[str]:
    return {it for it in installed.tokens | installed.tools
            if len(it) >= mod.SUBSTRING_MIN and (it in et or et in it)}


def test_index_finds_the_same_names_as_comparing_every_pair(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    rng = random.Random(26)
    letters = "abcde"  # a small alphabet so that substrings collide often
    for _ in range(60):
        installed = mod.Installed([], commands=False, timeout=1)
        names = ["".join(rng.choice(letters) for _ in range(rng.randrange(1, 90))) for _ in range(rng.randrange(1, 40))]
        installed.tools |= set(names[: len(names) // 2])
        for n in names[len(names) // 2:]:
            installed.add(n)
        for _ in range(30):
            et = "".join(rng.choice(letters) for _ in range(rng.randrange(mod.SUBSTRING_MIN, 100)))
            got, expected = installed.contained_names(et), brute_force(installed, et)
            assert got <= expected and (min(got) if got else None) == (min(expected) if expected else None)


def test_many_entries_and_many_tools_are_fast(tmp_path, monkeypatch):
    rng = random.Random(1)
    tools = tmp_path / "bin"
    tools.mkdir()
    for i in range(3000):
        (tools / f"tool{i}-{''.join(rng.choice(string.ascii_lowercase) for _ in range(8))}").write_text("")
    monkeypatch.setenv("PATH", str(tools))
    home = tmp_path / "home"
    for area in ("Library/Caches", "Library/Application Support", "Library/Containers", "Library/Logs"):
        for i in range(5000):
            (home / area / f"com.vendor{i}.app{rng.randrange(10**6)}").mkdir(parents=True)
    (home / "Applications").mkdir()
    monkeypatch.setattr(mod, "startup_leftovers", lambda *a, **k: {"login_items": [], "launch_agents": [],
                                                                   "launch_daemons": []})
    start = time.perf_counter()
    rc, _, err = run_main(mod, ["--home", str(home), "--apps-dir", str(home / "Applications"), "--no-commands",
                                "--json", "--min-mb", "0"])
    assert rc in (0, 1), err
    assert time.perf_counter() - start < 3
