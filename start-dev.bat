@echo off
echo Starting Account Manager Development Environment
echo ================================================

echo.
echo [1/3] Starting Python Backend Server...
start "Python Backend" cmd /k "cd backend && python app.py"

echo.
echo [2/3] Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

echo.
echo [3/3] Starting Vite Development Server...
start "Vite Dev Server" cmd /k "npm run dev"

echo.
echo Development servers are starting in separate windows.
echo - Python Backend: http://localhost:5050
echo - Vite Dev Server: http://localhost:5173
echo.
echo To start the Tauri app, run: npm run tauri:dev
echo.
pause