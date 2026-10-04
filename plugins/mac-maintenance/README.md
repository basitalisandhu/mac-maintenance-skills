# mac-maintenance

Three skills for cleaning up and speeding up a Mac, each with a tested standard-library Python script. Install with `/plugin marketplace add basitalisandhu/mac-maintenance-skills` and then `/plugin install mac-maintenance@mac-maintenance-skills`. Skills appear as `/mac-maintenance:<skill>`, and Claude also invokes them on its own when a request matches a skill's description.

| Skill | Script | Use it to |
|---|---|---|
| `mac-cleanup` | `skills/mac-cleanup/scripts/mac_survey.py`, `skills/mac-cleanup/scripts/safe_clean.py` | survey what takes space and memory without changing anything, then remove only the caches and leftovers programs recreate (dry run by default), then write the decision list for everything else |
| `mac-duplicate-finder` | `skills/mac-duplicate-finder/scripts/find_dupes.py` | find byte-identical files in the user folders, see which folders mirror each other, and move verified " (1)" copies to a dated Trash folder |
| `mac-app-leftovers` | `skills/mac-app-leftovers/scripts/app_leftovers.py` | list data, preferences, login items and launch agents left by uninstalled apps, and move the ones the user names to a dated Trash folder |

Requirements: macOS with Python 3.11 or newer on `PATH` as `python3`. No network access, no third-party packages, no sudo. Optional tools (docker, brew, uv, pip3, xcrun, mdls, osascript) are used when present and reported as unverified when not.
