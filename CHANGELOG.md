# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog, and the project uses semantic versioning.

## [Unreleased]

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
