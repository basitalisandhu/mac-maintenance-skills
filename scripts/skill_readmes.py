#!/usr/bin/env python3
"""Write or check plugins/mac-maintenance/skills/<skill>/README.md: what the skill does, the commands to try it on
the synthetic demo home from scripts/demo_home.py, and the real output of the sample command.

    python3 scripts/skill_readmes.py           write every README from a fresh run on a fresh demo home
    python3 scripts/skill_readmes.py --check   exit 1 if any README's sample no longer matches a fresh run

The demo home is built in a temporary folder and the commands run there with an empty PATH and TMPDIR inside the
demo home, so nothing on this Mac is read for the sample except the system launch agent folders, and nothing outside
the temporary folder is written. Sizes depend on the file system's block size, so --check is meant for macOS.
Standard library only. Exit codes: 0 written or all match, 1 a README is out of date (with --check), 2 bad input.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "mac-maintenance" / "skills"
PREFIX = "plugins/mac-maintenance/skills"

# skill: sample command, run from the folder that holds demo-home (paths are relative to the repository root)
SAMPLES: dict[str, str] = {
    "mac-app-leftovers": f"{PREFIX}/mac-app-leftovers/scripts/app_leftovers.py --home demo-home"
                         " --apps-dir demo-home/Applications --no-commands",
    "mac-cleanup": f"{PREFIX}/mac-cleanup/scripts/safe_clean.py --home demo-home --tmpdir demo-home/tmp --no-commands"
                   " --only npm-cache,old-logs,xcode-derived-data,chrome-cache",
    "mac-duplicate-finder": f"{PREFIX}/mac-duplicate-finder/scripts/find_dupes.py --home demo-home --quiet",
}
NOTES = {
    "mac-app-leftovers": "On your own Mac, tools on your `PATH` and in Homebrew also count as installed, and launch "
    "agents in `/Library` are checked too, so the list can differ. Add `--trash ID,...` to move named candidates "
    "into a dated Trash folder.",
    "mac-cleanup": "This is the dry run of the safe tier; nothing changes until `--apply`. The survey "
    "(`mac_survey.py`) reports disk, caches, apps and memory for the same home but its numbers depend on the "
    "machine, so it has no fixed sample here. `safe_clean.py --list-actions` lists every action.",
    "mac-duplicate-finder": "Add `--trash-suffix-copies` to move the `(1)` copy into a dated Trash folder after a "
    "second hash check; the original stays.",
}
SAFETY = {
    "mac-app-leftovers": "Nothing is deleted: only the candidates you name move to a dated Trash folder.",
    "mac-cleanup": "Without `--apply` nothing changes; with it, only caches and logs that programs recreate are "
    "removed, and everything else goes on a written decision list for you.",
    "mac-duplicate-finder": "Nothing is deleted: only verified suffix copies move to a dated Trash folder, and only "
    "with `--trash-suffix-copies`.",
}
START, END = "<!-- sample-output: start -->", "<!-- sample-output: end -->"


def load_demo():
    spec = importlib.util.spec_from_file_location("demo_home_for_readmes", ROOT / "scripts" / "demo_home.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def description(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r'^description: "(.*)"$', text, re.M)
    if not m:
        raise SystemExit(f"skill_readmes.py: {skill}/SKILL.md has no one-line double-quoted description")
    return m.group(1).replace('\\"', '"')


def run_samples() -> dict[str, tuple[int, str]]:
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "bin").mkdir()
        load_demo().build(work / "demo-home")
        env = {**os.environ, "PATH": str(work / "bin"), "TMPDIR": str(work / "demo-home" / "tmp")}
        for skill, command in SAMPLES.items():
            argv = shlex.split(command)
            proc = subprocess.run([sys.executable, str(ROOT / argv[0]), *argv[1:]], cwd=work, env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=300, check=False)
            if proc.returncode not in (0, 1):
                raise SystemExit(f"skill_readmes.py: {skill} sample exited {proc.returncode}: {proc.stderr.strip()}")
            out[skill] = (proc.returncode, proc.stdout)
    return out


def render(skill: str, rc: int, output: str) -> str:
    desc = description(skill)
    what = desc.split(" Use when")[0]
    not_for = next((s for s in re.split(r"(?<=\.) ", desc) if s.startswith("Not for")), "")
    meaning = "nothing to report" if rc == 0 else "something for you to decide"
    lines = [
        f"# {skill}",
        "",
        what,
        "",
        not_for,
        "",
        f"How Claude runs it, step by step: [SKILL.md](SKILL.md). {SAFETY[skill]}",
        "",
        "## Try it",
        "",
        "From the repository root, on a synthetic home folder (your own files are not touched):",
        "",
        "```bash",
        "python3 scripts/demo_home.py demo-home",
        f"python3 {SAMPLES[skill]}",
        "```",
        "",
        NOTES[skill],
        "",
        "## Sample output",
        "",
        f"The real output of the second command (exit code {rc}, {meaning}):",
        "",
        START,
        "```text",
        output.rstrip("\n"),
        "```",
        END,
        "",
        "This README is generated by `scripts/skill_readmes.py` and checked against a fresh run by the tests on macOS.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write or check the per-skill README samples.",
                                 epilog="Exit codes: 0 written or all match, 1 out of date (--check), 2 bad input.")
    ap.add_argument("--check", action="store_true", help="compare instead of writing")
    args = ap.parse_args(argv)
    missing = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md") if p.parent.name not in SAMPLES)
    if missing:
        print(f"skill_readmes.py: no sample command for {', '.join(missing)}", file=sys.stderr)
        return 2
    stale = []
    for skill, (rc, output) in run_samples().items():
        text = render(skill, rc, output)
        path = SKILLS / skill / "README.md"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(skill)
        else:
            path.write_text(text, encoding="utf-8")
    if stale:
        print("skill_readmes.py: out of date, run python3 scripts/skill_readmes.py: " + ", ".join(stale),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
