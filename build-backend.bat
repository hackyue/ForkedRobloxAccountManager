@echo off
echo ================================================
echo Building FRAM Backend (PyInstaller)
echo ================================================
echo.

where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller is not installed.
    echo Run: pip install pyinstaller
    echo.
    pause
    exit /b 1
)

echo [1/2] Cleaning previous build artifacts...
if exist "dist\backend.exe" del /q "dist\backend.exe"
if exist "backend\dist\backend.exe" del /q "backend\dist\backend.exe"
if exist "build" rmdir /s /q "build"

echo.
echo [2/2] Building backend.exe with PyInstaller...
echo This may take 1-2 minutes on first build.
echo.

pyinstaller backend/backend.spec --noconfirm --clean

if exist "dist\backend.exe" (
    set "EXE_PATH=dist\backend.exe"
) else if exist "backend\dist\backend.exe" (
    set "EXE_PATH=backend\dist\backend.exe"
) else (
    echo.
    echo [ERROR] Build failed. Check output above for errors.
    pause
    exit /b 1
)

echo.
echo ================================================
echo [SUCCESS] backend.exe built successfully!
for %%A in ("%EXE_PATH%") do echo   Size: %%~zA bytes
echo   Location: %EXE_PATH%
echo ================================================

echo.
pause
