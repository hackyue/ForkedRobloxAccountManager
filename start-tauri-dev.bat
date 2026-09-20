@echo off
echo Starting Complete Tauri Development Environment
echo ================================================

echo.
echo [1/3] Checking for existing processes on ports 5050 and 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5050 ^| findstr LISTENING') do (
    echo Found existing process on port 5050 (PID: %%a), terminating...
    taskkill /F /T /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo Found existing process on port 5173 (PID: %%a), terminating...
    taskkill /F /T /PID %%a >nul 2>&1
)
taskkill /F /IM chromedriver.exe >nul 2>&1
taskkill /F /IM geckodriver.exe >nul 2>&1
taskkill /F /IM msedgedriver.exe >nul 2>&1
timeout /t 1 /nobreak >nul
echo No conflicting processes found.

echo.
echo [2/3] Starting Python Backend Server...
start "Python Backend" cmd /k "cd backend && python app.py"

echo.
echo [3/3] Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

echo.
echo Starting Tauri Development Application...
echo Tauri will automatically start the Vite dev server.
echo.

npm run tauri:dev

echo.
echo If Tauri failed to start, ensure the backend is running on port 5050
echo You can manually start the backend with: cd backend && python app.py
echo.
pause