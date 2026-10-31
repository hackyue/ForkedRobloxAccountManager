#!/usr/bin/env bash
set -e

echo "Starting Complete Tauri Development Environment"
echo "================================================"

echo "[1/3] Checking for existing processes on ports 5050 and 5173..."
lsof -ti:5050 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
pkill -9 -f chromedriver 2>/dev/null || true
pkill -9 -f geckodriver 2>/dev/null || true
pkill -9 -f msedgedriver 2>/dev/null || true
sleep 1

echo "[2/3] Starting Python Backend Server..."
(cd backend && python3 app.py) &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

echo "[3/3] Waiting for backend to initialize..."
sleep 2

echo "Starting Tauri Development Application..."
npm run tauri:dev

