# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog, and the project uses semantic versioning.

## [Unreleased]

## [0.1.4] - 2026-10-18

### Fixed

- `mac_survey.py --out` into a missing folder, and `find_dupes.py --out-dir` pointing at a file, crashed with a traceback and exit 1 after the whole scan; `safe_clean.py --log` that could not be written did the same. Each is now checked before the scan and exits 2 with one line.
- Negative, zero or non-numeric `--top`, `--timeout`, `--large-mb`, `--node-mb`, `--pair-depth`, `--min-mb`, `--npx-days` and `--log-days` were accepted (a negative `--top` printed empty tables). They are usage errors now (exit 2); `--min-mb 0` and `--log-days 0` stay allowed.
- `app_leftovers.py --trash` took a malformed id such as `nocolon` and exited 0 with "not a candidate", which read as success. Malformed ids are refused before the scan, and if any id is not a candidate in this run nothing is moved and the exit code is 2 (before, the valid ids were moved and the exit code did not show the failure).
- `find_dupes.py` printed a single folder under "Folders that duplicate each other" when the copies were inside it; it now says "Desktop (copies inside it)".

### Added

- `scripts/demo_home.py` builds a synthetic home folder with planted duplicates, app leftovers, an npm cache and an old log, so a first-time user can see every script's output before running it on their own Mac. The README shows its real output.
- Every script's `--help` ends with its exit codes; the README has one exit code table and each SKILL.md the same wording, including `mac_survey.py`, whose codes were not documented.
- `tests/test_bad_input.py` and `tests/test_demo_home.py`: 126 tests before, 183 after.

### Changed

- Version 0.1.4 in `plugin.json` and `marketplace.json`.

## [0.1.3] - 2026-10-05

### Changed

- mac-cleanup's description now leads with the goal (free disk space and speed up a Mac) and quotes "my Mac feels slow", the way people ask. On the labelled trigger prompts recall rose from 0.60 to 1.00, and precision against other skills' prompts from 0.75 to 1.00 (the old quoted "System Data" also matched an unrelated threat-model request).
- `scripts/validate_plugin.py` now fails on a description without a double-quoted trigger phrase of 2 to 8 words, with tests.

## [0.1.2] - 2026-10-05

### Changed

- Rewrote all three skill descriptions to 374 to 546 characters (from 767 to 1,012): each starts with a verb, states the goal before the mechanism, carries one quoted phrase a user would type, a "Use when ..." sentence and a "Not for ..." boundary, and stays double-quoted.
- `app_leftovers.py` no longer calls `os.getuid` unguarded: where it does not exist the launch agent fix command leaves the uid to the shell (`gui/$(id -u)`), with a test.
- Tests open text files with `encoding="utf-8"` (the scripts already did). CI keeps Ubuntu and macOS only: the skills are macOS-only by design, so there is no Windows leg.
- The plugin and root READMEs mention "System Data is huge", Docker.raw and Time Machine local snapshots (out of scope, with the command that lists them).
- `scripts/validate_plugin.py` now fails when a description is over 600 characters, is not double-quoted, or lacks "Use " or "Not for"; `tests/test_skill_frontmatter.py` covers each rule and the existing `## Limits` requirement.
- Version 0.1.2 in `plugin.json` and `marketplace.json`.

## [0.1.1] - 2026-10-04

### Fixed

- Quoted SKILL.md descriptions that contained a colon so the frontmatter parses under strict YAML readers such as the skills CLI; the validator now fails on unquoted scalars with ': ' or ' #'.

## [0.1.0] - 2026-10-04

### Added

- Plugin marketplace `mac-maintenance-skills` with one plugin, `mac-maintenance`, and three skills, each with a tested standard-library script.
- `mac-cleanup`: `mac_survey.py`, a read-only survey of disk, home folder and ~/Library sizes, known caches with how each comes back, Docker usage and orphan buildx volumes, Homebrew cleanup estimate, outdated count, versioned families and which formulae need each, applications with size, version, bundle id and Spotlight last-used date, login items and third-party launch agents with missing programs, memory, swap and top processes, large files and node_modules; and `safe_clean.py`, a dry-run-by-default cleaner for npm, npx, Go, uv, pip and Homebrew caches, Docker build cache, dangling images, anonymous volumes and orphan buildx state volumes, stuck Docker Desktop update downloads (detaching a mounted installer image first), Electron updater downloads, Xcode DerivedData, unavailable simulators, old logs, Chrome cache when Chrome is closed, and login items whose app is gone, with per-action conditions, a log file and measured free space before and after. A `references/decision-tiers.md` on judging worktrees, node_modules, CI and model caches, app duplicates, Homebrew families, personal folders and startup items.
- `mac-duplicate-finder`: `find_dupes.py` groups files by size, hashes the first 64 KiB and then the whole file, reports groups by wasted bytes and a folder-pair table, singles out suffix copies next to an identical original, skips files whose data is not on disk, and with `--trash-suffix-copies` moves re-verified copies into a dated Trash folder with their relative paths.
- `mac-app-leftovers`: `app_leftovers.py` lists entries in Application Support, Containers, Group Containers, Caches, Preferences, Saved Application State, HTTPStorages, WebKit and Logs that no installed app, tool on PATH, Homebrew formula, Spotlight record or shared team id claims, with size, last change and kind; login items and launch agents or daemons whose target is gone, each with a fix command; and `--trash` moves by id into a dated Trash folder, reporting sandboxed containers macOS refuses.
- An offline pytest suite that builds fake home folders in temporary directories, `scripts/validate_plugin.py`, and a CI workflow that runs the tests on Ubuntu and macOS, ruff, the validator, `claude plugin validate --strict`, and a dry run of every script on a macOS runner.
