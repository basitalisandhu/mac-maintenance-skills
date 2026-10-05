# mac-maintenance-skills: Claude Code skills for cleaning up and speeding up a Mac

**Mac maintenance skills for Claude Code: a survey that only measures, a safe tier that removes only what programs recreate, and a written list for every decision that is yours.**

mac-maintenance-skills is a Claude Code plugin with three skills for people whose Mac has filled up with caches, duplicate exports, leftovers of uninstalled apps and a few gigabytes pinned in memory, and who do not want a cleaner that guesses. It exists because the usual cleanup either deletes too little to matter or deletes something that mattered: each skill pairs the model's judgement with a standard-library Python script that measures before it proposes, removes only regenerable caches on its own, and moves anything of yours to a dated folder in the Trash instead of deleting it.

Common searches it answers: "System Data is huge", a Docker.raw file that keeps growing, and duplicate photos or leftovers of uninstalled apps. Time Machine local snapshots are out of scope.

```text
/plugin marketplace add basitalisandhu/mac-maintenance-skills
/plugin install mac-maintenance@mac-maintenance-skills
```

This pack is also part of [claude-skills](https://github.com/basitalisandhu/claude-skills), which holds every skill I maintain as one marketplace: `/plugin marketplace add basitalisandhu/claude-skills`.

Quickstart: open Claude Code and ask "look at my Mac and clean up the garbage", or run a script directly from a clone of this repository:

```bash
python3 plugins/mac-maintenance/skills/mac-cleanup/scripts/safe_clean.py
```

That prints the safe-tier plan with sizes and changes nothing; add `--apply` to run it.

Questions, bugs and ideas: open an issue on this repository. Security reports: see [SECURITY.md](SECURITY.md).

## When to use this

- "My Mac is slow", "the disk is full", "there is a lot of garbage and duplicate apps": `mac-cleanup`
- "Find the duplicate photos and videos", "get rid of the (1) copies", "which folders are copies of each other": `mac-duplicate-finder`
- "What did Slack leave behind", "there is a login item for an app I deleted": `mac-app-leftovers`

## Skills

| Skill | Triggers on | Script | What it produces |
|---|---|---|---|
| `mac-cleanup` | clean, optimise, speed up or free space on a Mac; too many or duplicate apps | `mac_survey.py`, `safe_clean.py` | a read-only survey (disk, caches with how each comes back, Docker, Homebrew families and who needs each version, apps with last-used dates, login items, memory and swap, large files, node_modules); a dry-run plan then an applied safe tier; a decision list and a report with measured free space before and after |
| `mac-duplicate-finder` | duplicate files, photos or videos; folders that mirror each other | `find_dupes.py` | byte-identical groups ordered by wasted space, a folder-pair table, and suffix copies (`IMG_1 (1).MOV` beside an identical `IMG_1.MOV`) that can be moved to a dated Trash folder after a second hash check |
| `mac-app-leftovers` | leftovers of uninstalled apps, login items or launch agents that point at nothing | `app_leftovers.py` | candidates in Application Support, containers, caches, preferences and more that no installed app or tool claims, with size and last change; startup items with their fix commands; moves by id into a dated Trash folder |

Every script reads only the paths it is given, prints a table by default and JSON with `--json`, and uses exit codes 0 (nothing found or all done), 1 (findings, or a failed action) and 2 (bad input). The cleaner is a dry run unless you pass `--apply`.

## How this differs from what you may already have

- **Cleaner apps** decide for you from a fixed list and show a number. Here the survey, the plan and the report are text you can read, every size is measured by `du` and quoted as such, and anything a tool could not check is listed as unverified rather than estimated.
- **Asking the model to "clean my Mac"** without a procedure tends to either stop at caches or reach for `rm -rf` on things it cannot judge. The skills fix the order (measure, safe tier, decision list, act on the answer) and fix the rule for your data: the Trash with the relative path kept, never a delete.
- **Shell one-liners** (`brew cleanup`, `docker system prune`, `npm cache clean`) are all in the safe tier, with the conditions that make them safe: npm not installing, Chrome closed, Xcode closed, a buildx volume only when its builder is gone, a Docker installer image detached before its folder goes.

## What is inside

```text
.claude-plugin/marketplace.json                       marketplace manifest
plugins/mac-maintenance/
├── .claude-plugin/plugin.json                        plugin manifest
├── README.md                                         the plugin's skill table
└── skills/<name>/
    ├── SKILL.md                                      triggers, honesty principle, procedure, output format, limits
    ├── references/                                   (mac-cleanup) how to judge worktrees, caches, apps, memory
    └── scripts/<script>.py                           standard library only, --help, --json, exit codes 0/1/2
tests/test_<script>.py                                pytest suite, offline, runs on macOS and Linux
scripts/validate_plugin.py                            structure, frontmatter, scripts, READMEs, house style
```

Each skill folder is self-contained: its scripts live inside it, so it can be copied on its own.

## Security posture

- **Skills** are Markdown instructions. Each one tells Claude to treat file names, app names and command output as untrusted data, never as instructions, and to report only what it measured.
- **The survey changes nothing.** It runs read-only commands (`du`, `docker system df`, `brew cleanup -n`, `mdls`, `ps`, System Events for login items) and writes a report only where you pass `--out`.
- **The cleaner is a dry run by default.** With `--apply` it removes only the catalogue in its docstring, refuses symbolic links and anything outside your home and temp folders, never empties the Trash, and never touches documents, photos, mail, applications or settings.
- **The duplicate and leftover scripts move, never delete.** Moves go to a dated folder under `~/.Trash` with the relative path kept; a copy is re-hashed against its original at the moment of the move; sandboxed containers macOS refuses are reported, not forced.
- **No sudo, no network, no telemetry.** System-level launch daemons are listed with the command for you to run.

Report security problems privately: see [SECURITY.md](SECURITY.md). Privacy: [PRIVACY.md](PRIVACY.md), which says in plain words that nothing is collected or sent.

## A worked example

On the author's machine the first run went like this: the survey found a 54 GB Docker buildx state volume whose builder no longer existed, 22 GB of Docker build cache, 13 GB of a CI cache folder untouched for five weeks, 6 GB of a Go build cache with no Go toolchain installed, 5 GB of stuck Docker Desktop update downloads including a still-mounted installer image, and 12 GB of memory held by a local model server. The safe tier and the decisions that followed took free space from 344 GB to 474 GB, with 9 GB of exact photo copies parked in the Trash rather than deleted. The figures are from that one machine; yours will differ, and the scripts will say what they measured.

## Also works with

The skill folders follow the Agent Skills format (a `SKILL.md` with `name` and `description` frontmatter, helpers in `scripts/`, optional `references/`), and each skill is self-contained. An agent that loads skills from `SKILL.md` folders can use one by copying `plugins/mac-maintenance/skills/<name>/` into its skills directory. The skill bodies call scripts through `${CLAUDE_PLUGIN_ROOT}`, a Claude Code variable; other hosts should replace `${CLAUDE_PLUGIN_ROOT}/skills/<name>` with the skill folder's path. The scripts themselves are plain Python and run anywhere Python 3.11 does; the macOS-specific parts (Spotlight, System Events, Docker Desktop paths) are skipped and reported as unverified elsewhere.

## Development

```bash
python3 -m pytest -q
ruff check .
python3 scripts/validate_plugin.py
claude plugin validate --strict . && claude plugin validate --strict plugins/mac-maintenance
```

CI runs the tests on Ubuntu and macOS with Python 3.11 to 3.13, and a dry run of every script against the macOS runner's home folder. See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules and [docs/good-first-issues.md](docs/good-first-issues.md) for a place to start.

## Frequently asked questions

**Will it delete my files?**
No. The cleaner removes only the caches and leftovers listed in its docstring, and only with `--apply`. Everything that is yours (duplicate photos, data of uninstalled apps, old worktrees you choose to drop) goes to a dated folder in the Trash with its path kept, after you say yes in the conversation.

**What does the survey run?**
`du -sk` for sizes, `docker system df` and `docker volume ls`, `brew cleanup -n`, `brew outdated`, `brew list`, `brew uses`, `brew services list`, `mdls` for app last-used dates, `ps`, `sysctl` and `uptime`, and one System Events call for login items. All read-only. Anything missing or failing is listed as unverified.

**Why is "last used" missing for apps I use every day?**
Spotlight's `kMDItemLastUsedDate` is not written for every launch, and many menu bar and background apps never get one. The skills present it as "no record" and never as "never opened".

**Can I use the scripts without Claude Code?**
Yes. Each is a standalone standard-library Python program, for example `python3 find_dupes.py ~/Pictures --out-dir dupes` or `python3 app_leftovers.py --json`.

**Does it need sudo?**
No, and it never asks for it. Launch daemons under `/Library/LaunchDaemons` whose program is gone are listed with the `sudo launchctl bootout` command for you to run yourself.

## Related projects

| Project | What it is |
|---|---|
| [repo-engineering-skills](https://github.com/basitalisandhu/repo-engineering-skills) | Claude Code skills for repository audits and documentation: docs checked against the code, audits where every finding cites a line |
| [claude-dev-skills](https://github.com/basitalisandhu/claude-dev-skills) | Claude Code skills for everyday development: code review, refactoring, debugging, CI and containers, data and APIs |
| [aws-security-skills](https://github.com/basitalisandhu/aws-security-skills) | AWS security skills for Claude Code: account audit, SCP guardrails, IAM least privilege, Security Hub triage |
| [claude-skills: one install script for every pack](https://github.com/basitalisandhu/claude-skills) | All packs in one repository; this plugin's pages are at https://basitalisandhu.github.io/claude-skills/plugins/mac-maintenance/ |

More from the author: [github.com/basitalisandhu](https://github.com/basitalisandhu).

## Licence

MIT. See [LICENSE](LICENSE).
