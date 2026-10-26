#!/usr/bin/env python3
"""Build a small synthetic home folder to try the mac-maintenance scripts on, without touching your own.

    python3 scripts/demo_home.py demo-home
    python3 plugins/mac-maintenance/skills/mac-duplicate-finder/scripts/find_dupes.py --home demo-home --quiet
    python3 plugins/mac-maintenance/skills/mac-app-leftovers/scripts/app_leftovers.py --home demo-home \\
        --apps-dir demo-home/Applications --no-commands
    python3 plugins/mac-maintenance/skills/mac-cleanup/scripts/safe_clean.py --home demo-home --tmpdir demo-home/tmp \\
        --no-commands

Planted: two byte-identical videos (one a " (1)" suffix copy) and a PDF saved in both Documents and Downloads;
leftovers of an app that is not installed (Application Support, Caches, Preferences); an npm cache and a log file
older than seven days for the safe tier. Every planted file and folder is dated 1 September 2026, and file
contents come from a fixed seed, so every run gives the same sizes and dates.
Standard library only; writes only inside the folder you name, which must not exist yet or be empty.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

MB = 1024 * 1024
OLD_DAYS = 10
STAMP = datetime(2026, 9, 1, 12, 0)  # local noon, so the date is the same in every time zone


def blob(seed: int, size: int) -> bytes:
    return random.Random(seed).randbytes(size)


def build(home: Path) -> dict:
    """Create the demo files under home and return what was planted."""
    files = {
        "Desktop/IMG_0412.MOV": blob(1, 3 * MB),
        "Desktop/IMG_0412 (1).MOV": blob(1, 3 * MB),
        "Documents/Invoices/invoice-2026-09.pdf": blob(2, 2 * MB + 512 * 1024),
        "Downloads/invoice-2026-09.pdf": blob(2, 2 * MB + 512 * 1024),
        "Pictures/holiday.jpg": blob(3, 2 * MB + 256 * 1024),
        "Library/Application Support/QuillNote/notes.db": blob(4, 4 * MB),
        "Library/Caches/net.quillnote.QuillNote/cache.bin": blob(5, 2 * MB),
        "Library/Preferences/net.quillnote.QuillNote.plist": b"<?xml version=\"1.0\"?><plist><dict/></plist>\n",
        ".npm/_cacache/content-v2/sha512/demo": blob(6, 3 * MB),
        "Library/Logs/QuillNote/old.log": b"demo log line\n" * 2000,
    }
    for rel, data in files.items():
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for rel in ("Applications", "tmp"):
        (home / rel).mkdir(parents=True, exist_ok=True)
    # Every planted file and folder gets the same fixed time, so "last changed" dates in the output are the same on
    # every run (the README samples rely on it). It is long enough ago for the log to count as old.
    stamp = min(STAMP.timestamp(), time.time() - OLD_DAYS * 86400)
    for path in sorted(home.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        os.utime(path, (stamp, stamp), follow_symlinks=False)
    return {"home": str(home), "files": sorted(files), "duplicate_groups": 2, "suffix_copies": 1,
            "leftover_app": "QuillNote"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 epilog="Exit codes: 0 demo folder written, 2 bad input or usage.")
    ap.add_argument("folder", help="folder to create (must not exist yet, or be empty)")
    ap.add_argument("--json", action="store_true", help="print what was planted as JSON")
    args = ap.parse_args(argv)
    home = Path(args.folder).expanduser()
    if home.exists() and (not home.is_dir() or any(home.iterdir())):
        print(f"error: {home} exists and is not an empty folder; pick a new path", file=sys.stderr)
        return 2
    try:
        planted = build(home)
    except OSError as exc:
        print(f"error: cannot write {home}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(planted, indent=2))
    else:
        print(f"Demo home written to {home}: {len(planted['files'])} files. See the commands in this script's --help.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
