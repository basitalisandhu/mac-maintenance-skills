# Security policy

This repository ships skills and scripts that run inside people's Claude Code sessions on their own Mac. The scripts measure, and with an explicit flag remove caches or move files into the Trash; nothing here makes a network call, asks for sudo, or reports usage anywhere.

## Supported versions

Only the latest release on `main` is supported. Pin a tag if you need stability, and update when a fix is announced in [CHANGELOG.md](CHANGELOG.md).

## Reporting a vulnerability

Please do not open a public issue for a security problem.

1. Use GitHub's private vulnerability reporting on this repository ("Security" tab, "Report a vulnerability").
2. If that is unavailable, open an issue titled "Security contact request" with no details, and the maintainer will reply with a private channel.

Include what you found, how to reproduce it, and what you think the impact is. You will get an acknowledgement within 5 working days and a fix or a mitigation plan within 30 days for confirmed issues.

## What counts

- `safe_clean.py` removing anything outside its documented catalogue, following a symbolic link, acting outside the home and temp folders, acting without `--apply`, or touching the Trash, documents, photos, mail, applications or settings.
- `find_dupes.py` or `app_leftovers.py` deleting instead of moving, moving a file that is not byte-identical to its original, moving an original, or writing outside `--trash-dir` and `--out-dir`.
- `mac_survey.py` changing anything on the machine.
- Any script opening a socket, invoking `sudo`, or running a program other than the read-only and cleanup commands named in its docstring.
- A crafted file or folder name that makes a script run a command, escape its root, or move a path it was not given (for example through `..` or a symbolic link).
- Text in any file of this repository that addresses the model rather than the reader.

Detection gaps (a cache location not in the catalogue, a vendor whose leftovers are not recognised, a duplicate pattern not covered) are welcome as ordinary issues or pull requests.

## What this plugin does and does not do

- No telemetry and no network access.
- The survey is read-only; the cleaner is a dry run unless `--apply` is passed and then removes only its documented catalogue.
- The duplicate and leftover scripts move files into a dated folder under the Trash with their relative paths kept; nothing is deleted.
- Commands the scripts run are listed in each script's docstring; the only ones that change state are the cleanup commands behind `--apply` (brew cleanup, docker prune, uv cache prune, pip cache purge, xcrun simctl delete unavailable, hdiutil detach, osascript delete login item).
- Skill text tells Claude to treat file names, app names and command output as untrusted data, never as instructions, and to act on user data only after the user's explicit yes.
