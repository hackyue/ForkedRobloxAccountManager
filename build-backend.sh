#!/usr/bin/env bash
set -e

echo "================================================"
echo "Building FRAM Backend (PyInstaller - macOS/Unix)"
echo "================================================"
echo

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "[ERROR] PyInstaller is not installed."
    echo "Run: pip install pyinstaller"
    exit 1
fi

echo "[1/2] Cleaning previous build artifacts..."
rm -f "dist/backend" "backend/dist/backend"
rm -rf "build"

echo
echo "[2/2] Building backend binary with PyInstaller..."
pyinstaller backend/backend.spec --noconfirm --clean

if [ -f "dist/backend" ]; then
    BIN_PATH="dist/backend"
elif [ -f "backend/dist/backend" ]; then
    BIN_PATH="backend/dist/backend"
else
    echo "[ERROR] Build failed. Check output above for errors."
    exit 1
fi

chmod +x "$BIN_PATH"
echo
echo "================================================"
echo "[SUCCESS] backend binary built successfully!"
echo "  Location: $BIN_PATH"
echo "================================================"

