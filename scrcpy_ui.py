#!/usr/bin/env python3
"""
Scrcpy_UI - a small, dependency-free GUI front-end for scrcpy.
https://github.com/Genymobile/scrcpy

Pick a device, tweak the common recording settings, and hit Record / Stop
without touching the command line.

scrcpy is located automatically: a local `scrcpy*` subfolder, the folder this
script lives in, or anything on your PATH. If it can't be found you'll be asked
to point at scrcpy.exe once, and the choice is remembered.

Stopping sends scrcpy a CTRL_BREAK console event so the recording is finalized
cleanly (force-kill is only a fallback, which can corrupt an .mp4).

Works with scrcpy 2.0+ (tested on 4.0). Windows only (uses console-ctrl events).
"""

import os
import sys
import glob
import json
import shutil
import signal
import subprocess
import threading
import queue
import datetime
import ctypes

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(APP_DIR, "scrcpy_ui_config.json")

CREATE_NEW_PROCESS_GROUP = 0x00000200  # lets us send CTRL_BREAK to just this child
CREATE_NO_WINDOW = 0x08000000          # for adb helper calls, no flashing console

# --- Theme -------------------------------------------------------------------
BG = "#1e1f29"
PANEL = "#282a36"
FG = "#f8f8f2"
MUTED = "#9ba1b0"
ACCENT = "#50fa7b"
ACCENT_DK = "#2fa33f"
DANGER = "#ff5555"
DANGER_DK = "#c93b3b"


def hide_console_window():
    """Hide (but keep) the console so CTRL_BREAK delivery still works."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def discover_scrcpy():
    """Return a path to scrcpy.exe, or None. Tries config, local folders, PATH."""
    # 1. remembered choice
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            saved = json.load(f).get("scrcpy")
        if saved and os.path.isfile(saved):
            return saved
    except Exception:
        pass
    # 2. a scrcpy* subfolder next to this script (the bundled layout)
    for pat in ("scrcpy*/scrcpy.exe", "scrcpy.exe"):
        hits = glob.glob(os.path.join(APP_DIR, pat))
        if hits:
            return hits[0]
    # 3. anything on PATH (installed via scoop/choco/winget)
    found = shutil.which("scrcpy")
    if found:
        return found
    return None


def save_scrcpy_choice(path):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump({"scrcpy": path}, f)
    except Exception:
        pass


class PhoneRecorder(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scrcpy_UI")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.proc = None
        self.log_queue = queue.Queue()
        self.devices = []

        self.scrcpy = discover_scrcpy()
        self.scrcpy_dir = os.path.dirname(self.scrcpy) if self.scrcpy else APP_DIR
        self.adb = self._find_adb()

        try:
            png = glob.glob(os.path.join(self.scrcpy_dir, "scrcpy.png"))
            if png:
                self.iconphoto(True, tk.PhotoImage(file=png[0]))
        except Exception:
            pass

        self._build_styles()
        self._build_ui()
        self._update_scrcpy_label()

        if not self.scrcpy:
            self.after(300, self.prompt_locate_scrcpy)
        else:
            self.refresh_devices()

        self.after(100, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _find_adb(self):
        if self.scrcpy:
            local = os.path.join(self.scrcpy_dir, "adb.exe")
            if os.path.isfile(local):
                return local
        return shutil.which("adb") or "adb"

    # ------------------------------------------------------------------ styles
    def _build_styles(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, fieldbackground=PANEL,
                     bordercolor="#44475a", lightcolor=PANEL, darkcolor=PANEL)
        st.configure("TFrame", background=BG)
        st.configure("Panel.TLabelframe", background=PANEL, bordercolor="#44475a")
        st.configure("Panel.TLabelframe.Label", background=PANEL, foreground=ACCENT,
                     font=("Segoe UI Semibold", 10))
        st.configure("TLabel", background=PANEL, foreground=FG, font=("Segoe UI", 9))
        st.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 8))
        st.configure("TCheckbutton", background=PANEL, foreground=FG, font=("Segoe UI", 9))
        st.map("TCheckbutton", background=[("active", PANEL)])
        st.configure("TCombobox", fieldbackground=BG, background=PANEL, foreground=FG,
                     arrowcolor=FG)
        st.configure("TEntry", fieldbackground=BG, foreground=FG)
        st.configure("TButton", background="#44475a", foreground=FG, font=("Segoe UI", 9),
                     borderwidth=0, focuscolor=PANEL, padding=6)
        st.map("TButton", background=[("active", "#565a72")])
        st.configure("Record.TButton", background=ACCENT_DK, foreground="#0b160d",
                     font=("Segoe UI Semibold", 11), padding=10)
        st.map("Record.TButton", background=[("active", ACCENT), ("disabled", "#3a4a3d")])
        st.configure("Stop.TButton", background=DANGER_DK, foreground="#1a0707",
                     font=("Segoe UI Semibold", 11), padding=10)
        st.map("Stop.TButton", background=[("active", DANGER), ("disabled", "#4a3030")])

    # ---------------------------------------------------------------------- ui
    def _build_ui(self):
        pad = dict(padx=10, pady=6)
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")

        # Device row -------------------------------------------------------
        dev = ttk.Labelframe(root, text=" Device ", style="Panel.TLabelframe", padding=10)
        dev.grid(row=0, column=0, sticky="ew", **pad)
        dev.columnconfigure(0, weight=1)
        self.device_cb = ttk.Combobox(dev, state="readonly", width=40)
        self.device_cb.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(dev, text="⟳ Refresh", command=self.refresh_devices).grid(row=0, column=1)
        self.scrcpy_lbl = ttk.Label(dev, text="", style="Muted.TLabel", cursor="hand2")
        self.scrcpy_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.scrcpy_lbl.bind("<Button-1>", lambda e: self.prompt_locate_scrcpy())

        # Output -----------------------------------------------------------
        out = ttk.Labelframe(root, text=" Output ", style="Panel.TLabelframe", padding=10)
        out.grid(row=1, column=0, sticky="ew", **pad)
        out.columnconfigure(1, weight=1)

        ttk.Label(out, text="Folder").grid(row=0, column=0, sticky="w", pady=3)
        self.folder_var = tk.StringVar(value=os.path.join(APP_DIR, "recordings"))
        ttk.Entry(out, textvariable=self.folder_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(out, text="Browse…", command=self.browse_folder).grid(row=0, column=2)

        ttk.Label(out, text="File name").grid(row=1, column=0, sticky="w", pady=3)
        self.name_var = tk.StringVar(value=self._default_name())
        ttk.Entry(out, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(out, text="↺", width=3,
                   command=lambda: self.name_var.set(self._default_name())).grid(row=1, column=2)

        ttk.Label(out, text="Format").grid(row=2, column=0, sticky="w", pady=3)
        self.format_var = tk.StringVar(value="mp4")
        ttk.Combobox(out, textvariable=self.format_var, state="readonly", width=10,
                     values=["mp4", "mkv"]).grid(row=2, column=1, sticky="w", padx=8)
        ttk.Label(out, text="mkv survives a force-stop better than mp4",
                  style="Muted.TLabel").grid(row=2, column=1, sticky="e", padx=8)

        # Settings ---------------------------------------------------------
        cfg = ttk.Labelframe(root, text=" Settings ", style="Panel.TLabelframe", padding=10)
        cfg.grid(row=2, column=0, sticky="ew", **pad)
        for c in (1, 3):
            cfg.columnconfigure(c, weight=1)

        self.maxsize_var = tk.StringVar(value="0  (original)")
        self._combo(cfg, 0, 0, "Max size", self.maxsize_var,
                    ["0  (original)", "2560", "1920", "1600", "1280", "1024", "800"])

        self.bitrate_var = tk.StringVar(value="8M")
        self._combo(cfg, 0, 2, "Video bit-rate", self.bitrate_var,
                    ["2M", "4M", "8M", "12M", "16M", "20M", "30M"])

        self.fps_var = tk.StringVar(value="—  (max)")
        self._combo(cfg, 1, 0, "Max FPS", self.fps_var,
                    ["—  (max)", "60", "48", "30", "24", "15"])

        self.codec_var = tk.StringVar(value="h264")
        self._combo(cfg, 1, 2, "Video codec", self.codec_var, ["h264", "h265", "av1"])

        self.orient_var = tk.StringVar(value="0  (auto)")
        self._combo(cfg, 2, 0, "Orientation", self.orient_var,
                    ["0  (auto)", "90", "180", "270"])

        ttk.Label(cfg, text="Time limit (s)").grid(row=2, column=2, sticky="w",
                                                   padx=(0, 8), pady=4)
        self.timelimit_var = tk.StringVar(value="0")
        ttk.Entry(cfg, textvariable=self.timelimit_var, width=12).grid(row=2, column=3, sticky="w")

        self.audio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Record audio", variable=self.audio_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.mirror_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Show live mirror window", variable=self.mirror_var).grid(
            row=3, column=2, columnspan=2, sticky="w", pady=(8, 0))

        # Controls ---------------------------------------------------------
        ctl = ttk.Frame(root)
        ctl.grid(row=3, column=0, sticky="ew", **pad)
        ctl.columnconfigure(0, weight=1)
        ctl.columnconfigure(1, weight=1)
        self.record_btn = ttk.Button(ctl, text="●  Record", style="Record.TButton",
                                     command=self.start_recording)
        self.record_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.stop_btn = ttk.Button(ctl, text="■  Stop", style="Stop.TButton",
                                   command=self.stop_recording, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(ctl, text="Mirror only (no record)", command=self.start_mirror_only).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # Status + log -----------------------------------------------------
        self.status_var = tk.StringVar(value="● Idle")
        self.status_label = tk.Label(root, textvariable=self.status_var, bg=BG, fg=MUTED,
                                     anchor="w", font=("Segoe UI Semibold", 9))
        self.status_label.grid(row=4, column=0, sticky="ew", padx=10)

        self.log = tk.Text(root, height=8, width=64, bg="#15161e", fg="#cdd2de",
                           insertbackground=FG, relief="flat", font=("Consolas", 8),
                           wrap="word", padx=8, pady=6)
        self.log.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 4))
        self.log.configure(state="disabled")

    def _combo(self, parent, r, c, label, var, values):
        ttk.Label(parent, text=label).grid(row=r, column=c, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(parent, textvariable=var, state="readonly", width=12,
                     values=values).grid(row=r, column=c + 1, sticky="w")

    # ------------------------------------------------------------------ scrcpy location
    def _update_scrcpy_label(self):
        if self.scrcpy:
            ver = self._scrcpy_version()
            self.scrcpy_lbl.configure(
                text=f"scrcpy: {self.scrcpy}" + (f"   ({ver})" if ver else "")
                     + "   — click to change")
        else:
            self.scrcpy_lbl.configure(text="⚠ scrcpy not found — click to locate scrcpy.exe")

    def _scrcpy_version(self):
        try:
            out = subprocess.run([self.scrcpy, "--version"], capture_output=True, text=True,
                                 creationflags=CREATE_NO_WINDOW, timeout=8)
            first = (out.stdout or out.stderr).splitlines()[0]
            return first.strip()
        except Exception:
            return ""

    def prompt_locate_scrcpy(self):
        path = filedialog.askopenfilename(
            title="Locate scrcpy.exe",
            filetypes=[("scrcpy", "scrcpy.exe"), ("Executable", "*.exe"), ("All", "*.*")])
        if not path:
            if not self.scrcpy:
                messagebox.showwarning(
                    "scrcpy required",
                    "scrcpy was not found.\n\nDownload it from\n"
                    "https://github.com/Genymobile/scrcpy/releases\n"
                    "and either put the folder next to this app or click the scrcpy "
                    "line to locate scrcpy.exe.")
            return
        self.scrcpy = path
        self.scrcpy_dir = os.path.dirname(path)
        self.adb = self._find_adb()
        save_scrcpy_choice(path)
        self._update_scrcpy_label()
        self.refresh_devices()

    # ------------------------------------------------------------------ helpers
    def _default_name(self):
        return "phone_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def browse_folder(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get() or os.path.expanduser("~"))
        if d:
            self.folder_var.set(d)

    def _selected_serial(self):
        idx = self.device_cb.current()
        if idx < 0 or idx >= len(self.devices):
            return None
        return self.devices[idx][0]

    def log_line(self, text):
        self.log_queue.put(text)

    def _drain_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line == "__EXITED__":
                    self._on_proc_exit()
                    continue
                self.log.configure(state="normal")
                self.log.insert("end", line.rstrip() + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def _env(self):
        env = os.environ.copy()
        if self.adb and os.path.isfile(self.adb):
            env["ADB"] = self.adb  # make scrcpy use the same adb we do
        return env

    def _set_status_color(self, color):
        self.status_label.configure(fg=color)

    # ------------------------------------------------------------------ devices
    def refresh_devices(self):
        self.devices = []
        labels = []
        try:
            out = subprocess.run([self.adb, "devices", "-l"], capture_output=True, text=True,
                                 creationflags=CREATE_NO_WINDOW, env=self._env(), timeout=10)
            for line in out.stdout.splitlines()[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                serial, state = parts[0], parts[1]
                model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "")
                if state == "device":
                    self.devices.append((serial, model))
                    labels.append(f"{model or 'device'}   ({serial})")
                elif state == "unauthorized":
                    self.devices.append((serial, "unauthorized"))
                    labels.append(f"⚠ unauthorized ({serial}) — accept the prompt on the phone")
        except FileNotFoundError:
            self.log_line("adb not found. Install scrcpy (it bundles adb) or add adb to PATH.")
        except Exception as e:
            self.log_line(f"adb error: {e}")

        if labels:
            self.device_cb["values"] = labels
            self.device_cb.current(0)
        else:
            self.device_cb["values"] = ["No device — plug in & enable USB debugging"]
            self.device_cb.current(0)

    # ------------------------------------------------------------------ args
    def _common_args(self):
        args = []
        serial = self._selected_serial()
        if serial:
            args += ["-s", serial]

        ms = self.maxsize_var.get().split()[0]
        if ms != "0":
            args += ["-m", ms]

        args += ["-b", self.bitrate_var.get()]

        fps = self.fps_var.get()
        if fps and fps[0].isdigit():
            args += ["--max-fps", fps.split()[0]]

        args += ["--video-codec", self.codec_var.get()]

        ori = self.orient_var.get().split()[0]
        if ori != "0":
            args += ["--orientation", ori]

        if not self.audio_var.get():
            args.append("--no-audio")
        if not self.mirror_var.get():
            args.append("--no-window")
        return args

    def _record_path(self):
        folder = self.folder_var.get().strip() or os.path.expanduser("~")
        os.makedirs(folder, exist_ok=True)
        name = self.name_var.get().strip() or self._default_name()
        ext = "." + self.format_var.get()
        if not name.lower().endswith(ext):
            name += ext
        return os.path.join(folder, name)

    # ------------------------------------------------------------------ launch
    def start_recording(self):
        self._launch(record=True)

    def start_mirror_only(self):
        self._launch(record=False)

    def _launch(self, record):
        if not self.scrcpy:
            self.prompt_locate_scrcpy()
            return
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Busy", "scrcpy is already running. Stop it first.")
            return

        args = [self.scrcpy] + self._common_args()
        path = None
        if record:
            path = self._record_path()
            args += ["--record", path]
        else:
            args = [a for a in args if a != "--no-window"]

        tl = self.timelimit_var.get().strip()
        if record and tl.isdigit() and int(tl) > 0:
            args += ["--time-limit", tl]

        self.log_line("$ " + " ".join(f'"{a}"' if " " in a else a for a in args))
        try:
            self.proc = subprocess.Popen(
                args, cwd=self.scrcpy_dir, env=self._env(),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as e:
            messagebox.showerror("Launch failed", str(e))
            return

        threading.Thread(target=self._reader, daemon=True).start()
        self.record_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        if record:
            self.status_var.set("● Recording →  " + os.path.basename(path))
            self._set_status_color(DANGER)
        else:
            self.status_var.set("● Mirroring (not recording)")
            self._set_status_color(ACCENT)
        self._recording_path = path

    def _reader(self):
        try:
            for line in self.proc.stdout:
                self.log_queue.put(line)
        except Exception:
            pass
        self.log_queue.put("__EXITED__")

    def _on_proc_exit(self):
        self.record_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        path = getattr(self, "_recording_path", None)
        if path and os.path.isfile(path):
            size = os.path.getsize(path) / (1024 * 1024)
            self.status_var.set(f"● Saved  {os.path.basename(path)}  ({size:.1f} MB)")
            self._set_status_color(ACCENT)
            self.name_var.set(self._default_name())
        else:
            self.status_var.set("● Idle")
            self._set_status_color(MUTED)
        self.proc = None

    # ------------------------------------------------------------------ stop
    def stop_recording(self):
        if not self.proc or self.proc.poll() is not None:
            return
        self.status_var.set("● Stopping (finalizing file)…")
        self.stop_btn.configure(state="disabled")
        threading.Thread(target=self._graceful_stop, daemon=True).start()

    def _graceful_stop(self):
        p = self.proc
        if not p:
            return
        try:
            os.kill(p.pid, signal.CTRL_BREAK_EVENT)  # scrcpy finalizes the file
        except Exception as e:
            self.log_queue.put(f"(ctrl-break failed: {e})")
        try:
            p.wait(timeout=8)
        except Exception:
            self.log_queue.put("(did not stop in time — force killing; file may be incomplete)")
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               creationflags=CREATE_NO_WINDOW)
            except Exception:
                pass

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Recording in progress",
                                       "A recording is still running. Stop and quit?"):
                return
            try:
                os.kill(self.proc.pid, signal.CTRL_BREAK_EVENT)
                self.proc.wait(timeout=6)
            except Exception:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                                   creationflags=CREATE_NO_WINDOW)
                except Exception:
                    pass
        self.destroy()


if __name__ == "__main__":
    hide_console_window()
    PhoneRecorder().mainloop()
