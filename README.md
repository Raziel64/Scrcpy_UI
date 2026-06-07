# Scrcpy_UI — a tiny GUI for recording your Android phone

A no-dependency Python/Tkinter front-end for
[scrcpy](https://github.com/Genymobile/scrcpy). Pick a device, tweak the common
settings, and hit **Record / Stop** — no command line required.

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)

## Features

- One-click **Record / Stop** with a clean stop (file is finalized, not corrupted)
- **Mirror only** mode (view your phone without recording)
- Device picker (auto-detects connected phones, flags unauthorized ones)
- Settings: max size, video bit-rate, max FPS, codec (h264/h265/av1),
  orientation, time limit, record-audio toggle, headless vs. live mirror window
- Output folder + auto-timestamped filenames, `.mp4` or `.mkv`
- **Finds scrcpy automatically** — bundled folder, same folder, or on your PATH;
  otherwise asks you to locate `scrcpy.exe` once and remembers it

## Quick start

1. **Get scrcpy** (if you don't have it): download a Windows build from the
   [scrcpy releases](https://github.com/Genymobile/scrcpy/releases) and unzip it.
   Either:
   - put the unzipped `scrcpy-win64-*` folder **next to** `phone_recorder.py`, **or**
   - install scrcpy so it's on your PATH (`scoop install scrcpy`,
     `choco install scrcpy`, or `winget install Genymobile.scrcpy`), **or**
   - just launch the app and point it at `scrcpy.exe` when asked.
2. **Get Python 3.8+** from [python.org](https://www.python.org/downloads/)
   (Tkinter is included; tick "Add Python to PATH" during install).
3. **On your phone (one-time):** enable **Developer options → USB debugging**,
   plug in via USB, and tap **Allow** on the prompt.
4. **Run it:** double-click **`Phone Recorder.bat`** (or `python phone_recorder.py`),
   click **⟳ Refresh**, then **● Record**.

Recordings save to the chosen folder (default `~/Videos`).

## What the controls map to

| Control | scrcpy flag |
|---|---|
| Max size | `-m` (cap longest side; *original* = no cap) |
| Video bit-rate | `-b` |
| Max FPS | `--max-fps` |
| Video codec | `--video-codec` (h264 / h265 / av1) |
| Orientation | `--orientation` |
| Time limit | `--time-limit` (auto-stop after N seconds) |
| Record audio | off → `--no-audio` (audio needs Android 11+) |
| Show live mirror window | off → `--no-window` (record headless) |
| Format | `.mp4` / `.mkv` filename |

**Stop** sends scrcpy a `CTRL_BREAK` so the recording is finalized properly. If
scrcpy doesn't stop within 8 s it's force-killed — an `.mp4` may then be
incomplete, so choose **mkv** if you expect abrupt stops.

## Notes

- **Windows only.** The clean-stop mechanism uses Windows console control events.
- Works with **scrcpy 2.0+** (developed against 4.0).
- This repo does **not** bundle scrcpy's binaries (they're large and maintained
  upstream) — see step 1 above.

## License

[MIT](LICENSE) for this UI. scrcpy itself is Apache-2.0 and is a separate project.
