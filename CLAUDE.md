# Scrcpy_UI — Claude Code Entry Point

## Project docs
See `README.md` and `USAGE.md` for what this is and how to run it. Python UI bolt-on for scrcpy; entry point is `scrcpy_ui.py`.

## Claude cross-device memory
Persistent Claude memory for this project is versioned in the private repo **`Raziel64/Claude_Memory`**, laid out as `<DEVICE>/projects/<path-key>/memory/` (one top-level folder per machine).
- To pull richer or historical context — including notes written on another machine — read the `memory/` folder for this project under each device folder in that repo (match by project name; the path-key differs per machine, e.g. this device's key is `c--PROJECTS-Scrcpy_UI`).
- Live local memory stays at `~/.claude/projects/<path-key>/memory/` (Claude auto-loads it); the repo is the consolidated cross-device copy.
- On this machine (**Raz-Laptop**) the repo is cloned at `C:\PROJECTS\Claude_Memory` and auto-syncs to GitHub at the end of each session.
