#!/usr/bin/env python3
"""
Cross-platform release builder for FRAM (Windows & macOS).


Usage:
  python scripts/build_release.py                # Full build (PyInstaller backend + Tauri installer)
  python scripts/build_release.py --backend-only # Build & stage PyInstaller backend into src-tauri/resources/
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
RESOURCES_DIR = ROOT_DIR / "src-tauri" / "resources"
IS_WINDOWS = sys.platform == "win32"
BACKEND_BIN_NAME = "backend.exe" if IS_WINDOWS else "backend"


def run_step(cmd: list[str], cwd: Path = ROOT_DIR, shell: bool = False) -> None:
    print(f"\n==> Running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=str(cwd), shell=shell)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(result.returncode)


def build_backend(install_deps: bool = False) -> Path:
    if install_deps:
        run_step([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        run_step([sys.executable, "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt"), "pyinstaller"])

    spec_path = BACKEND_DIR / "backend.spec"
    run_step([sys.executable, "-m", "PyInstaller", str(spec_path), "--noconfirm", "--clean"], cwd=ROOT_DIR)

    candidates = [
        ROOT_DIR / "dist" / BACKEND_BIN_NAME,
        BACKEND_DIR / "dist" / BACKEND_BIN_NAME,
    ]
    built_binary = next((p for p in candidates if p.is_file()), None)
    if not built_binary:
        print(f"[ERROR] {BACKEND_BIN_NAME} was not found after PyInstaller build.", file=sys.stderr)
        sys.exit(1)

    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    target_path = RESOURCES_DIR / BACKEND_BIN_NAME
    shutil.copy2(built_binary, target_path)

    if not IS_WINDOWS:
        current_mode = target_path.stat().st_mode
        target_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    size_mb = target_path.stat().st_size / (1024 * 1024)
    print(f"==> Staged backend binary: {target_path} ({size_mb:.2f} MB)", flush=True)
    return target_path


def build_tauri() -> None:
    npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    run_step([npm_cmd, "run", "tauri:build"], cwd=ROOT_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FRAM release packages on Windows or macOS.")
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Only build the PyInstaller backend binary and copy it to src-tauri/resources/",
    )
    parser.add_argument(
        "--install-python-deps",
        action="store_true",
        help="Install backend/requirements.txt and pyinstaller before building",
    )
    args = parser.parse_args()

    build_backend(install_deps=args.install_python_deps)
    if not args.backend_only:
        build_tauri()
        print("\n==> Release build completed successfully! Check src-tauri/target/release/bundle/", flush=True)


if __name__ == "__main__":
    main()

