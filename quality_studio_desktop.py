"""Local desktop launcher for a checked-out VPP repository. Requires Tk and installed VPP."""
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent


def main():
    root = tk.Tk()
    root.title("VPP Quality Studio — Local review")
    root.geometry("800x490")
    fields = (
        ("video", "Video file", False), ("lyrics", "Exact German lyrics (.txt)", False),
        ("srt", "Original subtitles (.srt)", False), ("demucs-repo", "Demucs weights folder", True),
        ("whisper-model", "WhisperX model folder", True), ("ctc-model", "German CTC model folder", True),
        ("output", "Output parent folder", True),
    )
    values = {}
    busy = False
    latest = None
    server = None
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="Local WhisperX + CTC · review-only SRT").grid(row=0, columnspan=3, sticky="w")
    for row, (key, label, folder) in enumerate(fields, 1):
        value = tk.StringVar()
        values[key] = value
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=value).grid(row=row, column=1, sticky="ew", padx=8)

        def choose(var=value, directory=folder):
            selected = filedialog.askdirectory() if directory else filedialog.askopenfilename()
            if selected:
                var.set(selected)

        ttk.Button(frame, text="Browse…", command=choose).grid(row=row, column=2)
    status = tk.StringVar(value="Select local files and model folders. No automatic downloads.")
    ttk.Label(frame, textvariable=status, wraplength=720).grid(row=9, columnspan=3, sticky="w", pady=10)

    def open_studio():
        nonlocal server
        if server is None:
            handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "web"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        webbrowser.open(f"http://127.0.0.1:{server.server_port}/quality-studio.html")

    def start():
        nonlocal busy, latest
        if busy:
            return
        inputs = {key: value.get() for key, value in values.items()}
        if any(not value or not Path(value).exists() for value in inputs.values()):
            messagebox.showerror("Missing input", "Select every required local file and folder.")
            return
        output = Path(inputs.pop("output")) / datetime.now().strftime("VPP_%Y%m%d_%H%M%S_%f")
        log = output.with_suffix(".log")
        command = [sys.executable, "-m", "vpp.cli", "studio-review", "--output", str(output)]
        for key, value in inputs.items():
            command.extend(["--"+key, value])
        busy = True
        run.configure(state="disabled")
        status.set("Running local models. See log: "+str(log))
        try:
            with log.open("x", encoding="utf-8") as handle:
                process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, cwd=ROOT)
        except OSError as exc:
            busy = False
            run.configure(state="normal")
            status.set(str(exc))
            return

        def poll():
            nonlocal busy, latest
            code = process.poll()
            if code is None:
                root.after(500, poll)
                return
            busy = False
            run.configure(state="normal")
            latest = output
            if code == 3:
                status.set("Review-only draft created: "+str(output))
            else:
                status.set("Blocked or failed. Inspect report and log: "+str(log))

        root.after(500, poll)

    def show_folder():
        if latest and latest.exists():
            webbrowser.open(latest.as_uri())

    def close():
        if busy:
            messagebox.showinfo("Review running", "Keep the launcher open until the local job finishes.")
            return
        if server is not None:
            server.shutdown()
            server.server_close()
        root.destroy()

    run = ttk.Button(frame, text="Run local review", command=start)
    run.grid(row=10, column=0, sticky="w")
    ttk.Button(frame, text="Open review studio", command=open_studio).grid(row=10, column=1)
    ttk.Button(frame, text="Open output folder", command=show_folder).grid(row=10, column=2)
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


if __name__ == "__main__":
    main()
