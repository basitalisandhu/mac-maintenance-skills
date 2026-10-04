# Good first issues

Small, well-specified pieces of work for a first contribution. Each is self-contained, comes with the test to add, and needs no account, token or network access. Read [CONTRIBUTING.md](../CONTRIBUTING.md) first: standard library only, a fake home folder in `tmp_path` with every detection change, no network calls, no sudo, plain language without em-dashes.

To claim one, open an issue with the title below (or comment on the existing one) and say you are working on it. Run `python3 -m pytest -q`, `ruff check .` and `python3 scripts/validate_plugin.py` before opening the pull request.

## 1. safe-clean: add the Gradle and Maven caches to the catalogue

**Labels:** good first issue, mac-cleanup, python

**Context.** `safe_clean.py` knows npm, Go, uv, pip and Homebrew. Java developers carry `~/.gradle/caches` and `~/.m2/repository`, often several gigabytes, both re-downloaded by the next build.

**Acceptance criteria.**
- Two actions, `gradle-cache` and `maven-cache`, with a condition that no `gradle` or `mvn` process is running (check `ps` output as `npm_cache` does).
- Rows in the docstring table and in `ACTION_IDS`.
- Tests in `tests/test_safe_clean.py` that plant both folders in a fake home, assert the dry run plans them with sizes and `--apply` removes them, and that `--skip gradle-cache` leaves the Gradle folder alone.

## 2. mac-survey: report the Photos library and Mail data sizes as read-only rows

**Labels:** good first issue, mac-cleanup, python

**Context.** The survey lists caches but not the two folders that most often explain a full disk: `~/Pictures/Photos Library.photoslibrary` and `~/Library/Mail`. Neither is a cleanup target, so they belong in a "user data, not for cleanup" table rather than in the candidates.

**Acceptance criteria.**
- A new `user_data` section with size rows for the Photos library, `Library/Mail`, `Library/Messages` and `Library/Mobile Documents` when present, labelled as not candidates.
- The text renderer prints the section after the caches; the JSON carries it; nothing from it reaches `candidates`.
- A test that plants a `Photos Library.photoslibrary` folder in a fake home and asserts its size appears in `user_data` and not in `candidates`.

## 3. find-dupes: optional `--same-name-only` mode

**Labels:** good first issue, mac-duplicate-finder, python

**Context.** On a photo archive the hashing step dominates. When the user only wants the `IMG_1 (1).MOV` class, the script could hash only files whose suffix-stripped name matches another file in the same folder.

**Acceptance criteria.**
- With `--same-name-only`, `walk()` keeps only files that have a same-folder sibling with the same stem after stripping the suffix pattern, and the report says the mode was on.
- Groups and suffix copies are otherwise unchanged in shape.
- A test with three files (`a.mov`, `a (1).mov`, `b.mov`) where `b.mov` is identical to `a.mov`: default mode reports a three-file group, the new mode reports a two-file group and one suffix copy.

## 4. app-leftovers: read vendor names from code signatures when `codesign` is present

**Labels:** good first issue, mac-app-leftovers, python

**Context.** Group Containers are named by team id. The script vouches for a team id only when another entry with that id matched an installed app. `codesign -dv --verbose=2 <app>` prints `TeamIdentifier=` and would let the script map every installed app's team id directly.

**Acceptance criteria.**
- When commands are enabled and `codesign` is on PATH, `Installed` collects `TeamIdentifier` for each app and `match()` accepts a Group Containers entry whose prefix is a known team id, with the reason "team id of an installed app".
- No change when `--no-commands` is passed.
- A test that monkeypatches the codesign call to return a team id and asserts a group container with that prefix is not a candidate.

## 5. app-leftovers: a `--since` filter on last change

**Labels:** good first issue, mac-app-leftovers, python

**Context.** Entries changed in the last few days are usually alive (a tool that just ran). A `--since YYYY-MM-DD` option would hide candidates changed after that date so the list shows the stale ones first.

**Acceptance criteria.**
- `--since` parses an ISO date and drops candidates whose `last_changed` is on or after it; the text output says how many were hidden.
- Startup leftovers are unaffected.
- A test with two candidates and different mtimes (set with `os.utime`) asserting only the older one is reported.

## 6. mac-cleanup: a `references/` page on iCloud Drive and "Optimize Mac Storage"

**Labels:** good first issue, mac-cleanup, documentation

**Context.** On a Mac with iCloud Drive syncing Desktop and Documents, local copies can be evicted, sizes in Finder differ from `du`, and reading a placeholder downloads it. The duplicate finder skips such files, but the cleanup skill has no guidance on explaining this to the user or on when freeing local space means evicting rather than deleting.

**Acceptance criteria.**
- A `references/icloud.md` under `mac-cleanup` that explains placeholders, why `du` and Finder disagree, how to tell an evicted file (`st_blocks` against `st_size`, the cloud icon), and that evicting is not a cleanup step the scripts take.
- A pointer to it from the "Limits" section of `SKILL.md`.
- No script changes; `scripts/validate_plugin.py` must still pass (relative links resolve).
