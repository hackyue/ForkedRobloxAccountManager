#!/usr/bin/env python3
"""
Cross-platform launcher for running FRAM in development mode on Windows or macOS.
Starts the Python backend and Tauri/Vite dev server together and cleans up on exit.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_SCRIPT = ROOT_DIR / "backend" / "app.py"
IS_WINDOWS = sys.platform == "win32"


def main() -> None:
    npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    mode = sys.argv[1] if len(sys.argv) > 1 else "tauri:dev"

    print(f"==> Starting Python backend ({sys.executable} {BACKEND_SCRIPT})...", flush=True)
    backend_proc = subprocess.Popen(
        [sys.executable, str(BACKEND_SCRIPT)],
        cwd=str(ROOT_DIR / "backend"),
    )

    time.sleep(1.0)
    print(f"==> Starting frontend ({npm_cmd} run {mode})...", flush=True)
    try:
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", mode],
            cwd=str(ROOT_DIR),
        )
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\n==> Shutting down...", flush=True)
    finally:
        if backend_proc.poll() is None:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                backend_proc.kill()


if __name__ == "__main__":
    main()

