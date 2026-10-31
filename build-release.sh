#!/usr/bin/env bash
set -e

echo "================================================"
echo "FRAM Full Release Build (macOS/Unix)"
echo "================================================"
echo

./build-backend.sh

if [ -f "dist/backend" ]; then
    BIN_PATH="dist/backend"
elif [ -f "backend/dist/backend" ]; then
    BIN_PATH="backend/dist/backend"
else
    echo "[ERROR] Backend binary not found."
    exit 1
fi

echo "[2/3] Copying backend binary into Tauri resource directory..."
mkdir -p "src-tauri/resources"
cp -f "$BIN_PATH" "src-tauri/resources/backend"
chmod +x "src-tauri/resources/backend"
echo "[SUCCESS] Copied to src-tauri/resources/backend"
echo

echo "[3/3] Building Tauri application..."
npm run tauri:build

echo
echo "Build complete! Bundles can be found in src-tauri/target/release/bundle/"

