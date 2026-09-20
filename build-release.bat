@echo off
echo ================================================
echo FRAM Full Release Build
echo ================================================
echo.
echo This script will:
echo   1. Build the Python backend into backend.exe (PyInstaller)
echo   2. Build the Tauri desktop application (installer)
echo.

echo [1/4] Building backend.exe...
echo.

where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller is not installed. Run: pip install pyinstaller
    pause
    exit /b 1
)

if exist "dist\backend.exe" del /q "dist\backend.exe"
if exist "backend\dist\backend.exe" del /q "backend\dist\backend.exe"
if exist "build" rmdir /s /q "build"

pyinstaller backend/backend.spec --noconfirm --clean

if exist "dist\backend.exe" (
    set "EXE_PATH=dist\backend.exe"
) else if exist "backend\dist\backend.exe" (
    set "EXE_PATH=backend\dist\backend.exe"
) else (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

for %%A in ("%EXE_PATH%") do echo [SUCCESS] backend.exe built (%%~zA bytes)
echo.

echo [2/4] Copying backend.exe into Tauri resource directory...

if not exist "src-tauri\resources" mkdir "src-tauri\resources"
copy /y "%EXE_PATH%" "src-tauri\resources\backend.exe" >nul
echo [SUCCESS] Copied to src-tauri\resources\backend.exe
echo.

echo [3/4] Building Tauri application...
echo.

npm run tauri:build

echo.
echo [4/4] Build complete!
echo.
echo The installer can be found in:
echo   src-tauri\target\release\bundle\
echo.
pause
