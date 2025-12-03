@echo off
title RAM Launcher
chcp 65001 >nul
cls
setlocal enabledelayedexpansion

echo [96m📦 Installing Python dependencies from requirements.txt...[0m
py -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [91m❌ Failed to install one or more dependencies![0m
    echo Make sure requirements.txt exists and pip is working.
    echo.
    pause
)
echo.
echo [92m✔ requirements.txt install completed[0m
echo.
pause


:MENU
cls
echo.
echo [96m============================[0m
echo   🚀 RAM Launcher
echo [96m============================[0m
echo.
echo [92m[1] Run Roblox Account Manager[0m
echo [93m[2] Exit[0m
echo.
set /p choice="Select an option: "

if "%choice%"=="1" goto CHECKS
if "%choice%"=="2" exit
goto MENU



:CHECKS
cls
echo.
echo [96m🔍 Running Environment Checks...[0m
echo.

:: ---------------- OS CHECK ----------------
echo [94m🖥️ Checking Operating System...[0m
ver | find "Windows" >nul
if %errorlevel%==0 (
    echo [92m✔ Windows detected[0m
) else (
    echo [91m✖ Non-Windows OS detected![0m
    echo.
    pause
    goto MENU
)
echo.  


:: ---------------- PYTHON CHECK ----------------
echo [94m🐍 Checking Python Installation...[0m
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [91m✖ Python not found![0m
    echo Python must be installed.
    echo.
    pause
    goto MENU
)
echo ✔ Python found:
python --version
echo.  


:: ---------------- PYTHON VERSION ----------------
echo [94m📦 Checking Python Version...[0m
for /f "tokens=2 delims= " %%v in ('python --version') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% LSS 3 (
    echo [91m✖ Python 3+ required![0m
    echo.
    pause
    goto MENU
)

echo [92m✔ Python version OK[0m
echo.  



:: ---------------- BLOXSTRAP / FISHSTRAP CHECK ----------------
echo [94m🔐 Checking for Bloxstrap / Fishstrap...[0m

set BLOX1="%LOCALAPPDATA%\Bloxstrap\Bloxstrap.exe"
set BLOX2="%PROGRAMFILES%\Bloxstrap\Bloxstrap.exe"
set BLOX3="%PROGRAMFILES(x86)%\Bloxstrap\Bloxstrap.exe"

set FISH1="%LOCALAPPDATA%\Fishstrap\Fishstrap.exe"
set FISH2="%PROGRAMFILES%\Fishstrap\Fishstrap.exe"
set FISH3="%PROGRAMFILES(x86)%\Fishstrap\Fishstrap.exe"

set LOGIN_TOOL_FOUND=0

if exist %BLOX1% set LOGIN_TOOL_FOUND=1
if exist %BLOX2% set LOGIN_TOOL_FOUND=1
if exist %BLOX3% set LOGIN_TOOL_FOUND=1

if exist %FISH1% set LOGIN_TOOL_FOUND=1
if exist %FISH2% set LOGIN_TOOL_FOUND=1
if exist %FISH3% set LOGIN_TOOL_FOUND=1

if %LOGIN_TOOL_FOUND%==1 (
    echo [92m✔ Bloxstrap/Fishstrap detected — Auto Login available[0m
) else (
    echo [91m⚠ WARNING: Neither Bloxstrap nor Fishstrap is installed![0m
    echo [93m→ Auto Login will NOT work for past Roblox versions.[0m
    echo.
    echo Install one of these to enable Auto Login:
    echo   • Bloxstrap
    echo   • Fishstrap (recommended)
    echo.
)
echo.



echo [92m🎉 All checks completed![0m
pause
cls
echo.  


:: ---------------- RUN main.py ----------------
echo [96m🚀 Launching main.py ...[0m
echo.

python "%~dp0main.py"

echo.
echo [93m(Account Manager was closed! — press any key to return to menu)[0m
pause
goto MENU
