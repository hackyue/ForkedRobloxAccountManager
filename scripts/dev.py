#!/usr/bin/env python3
"""
Cross-platform launcher for running FRAM in development mode on Windows or macOS.
Automatically sets up a local .venv and installs backend/requirements.txt if needed,
cleans up lingering processes on ports 5050/5173, starts the Python backend,
and launches the Tauri/Vite dev server.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
BACKEND_SCRIPT = BACKEND_DIR / "app.py"
REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"
IS_WINDOWS = sys.platform == "win32"

cargo_bin = Path.home() / ".cargo" / "bin"
if cargo_bin.is_dir():
    os.environ["PATH"] = f"{cargo_bin}{os.pathsep}{os.environ.get('PATH', '')}"


def ensure_python_with_deps() -> str:
    """Return a Python executable that has backend dependencies installed."""
    check_code = "import flask, flask_cors, requests, psutil, PIL, Crypto, selenium"
    if subprocess.run([sys.executable, "-c", check_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return sys.executable

    venv_dir = ROOT_DIR / ".venv"
    venv_py = venv_dir / ("Scripts/python.exe" if IS_WINDOWS else "bin/python3")

    if venv_py.is_file():
        if subprocess.run([str(venv_py), "-c", check_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return str(venv_py)

    print("[Setup] Missing Python backend packages. Setting up .venv and installing requirements...", flush=True)
    if not venv_py.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    subprocess.run([str(venv_py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(venv_py), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)], check=True)
    return str(venv_py)


def cleanup_existing_processes() -> None:
    print("[1/3] Checking for existing processes on ports 5050 and 5173...", flush=True)
    if IS_WINDOWS:
        for port in (5050, 5173):
            try:
                out = subprocess.check_output(
                    f'netstat -ano | findstr :{port}',
                    shell=True,
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                pids = set()
                for line in out.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and "LISTENING" in line.upper():
                        pids.add(parts[-1])
                for pid in pids:
                    if pid and pid != "0":
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
            except Exception:
                pass
        for driver in ("chromedriver.exe", "geckodriver.exe", "msedgedriver.exe"):
            subprocess.run(
                ["taskkill", "/F", "/IM", driver],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        for port in (5050, 5173):
            subprocess.run(
                f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        for driver in ("chromedriver", "geckodriver", "msedgedriver"):
            subprocess.run(
                ["pkill", "-9", "-f", driver],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def wait_for_backend(timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 5050), timeout=0.3):
                return
        except OSError:
            time.sleep(0.2)


def main() -> None:
    npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    mode = sys.argv[1] if len(sys.argv) > 1 else "tauri:dev"

    print("Starting Complete Tauri Development Environment", flush=True)
    print("================================================", flush=True)

    py_exe = ensure_python_with_deps()
    cleanup_existing_processes()
    time.sleep(0.5)

    print(f"[2/3] Starting Python Backend Server ({py_exe})...", flush=True)
    backend_proc = subprocess.Popen(
        [py_exe, str(BACKEND_SCRIPT)],
        cwd=str(BACKEND_DIR),
    )

    print("[3/3] Waiting for backend to initialize...", flush=True)
    wait_for_backend()

    if mode == "tauri:dev" and not shutil.which("cargo"):
        print(
            "\n[Notice] Rust ('cargo') is not installed on this machine, which is required for the Tauri desktop window.\n"
            "  -> To install Rust for Tauri desktop mode, run:\n"
            "     curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y\n"
            "  -> Falling back to Web Mode (http://localhost:5173) so you can use FRAM right now!\n",
            flush=True,
        )
        mode = "dev"

    print(f"Starting Frontend ({npm_cmd} run {mode})...", flush=True)
    try:
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", mode],
            cwd=str(ROOT_DIR),
        )
        if mode == "dev":
            time.sleep(1.5)
            webbrowser.open("http://localhost:5173")
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
