@echo off
setlocal

set APP_NAME=FRAM

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%APP_NAME%" ^
  --icon "icon.ico" ^
  --add-data "icon.ico;." ^
  --collect-data selenium ^
  --collect-data webdriver_manager ^
  --collect-all Crypto ^
  --hidden-import pywintypes ^
  --hidden-import win32timezone ^
  --hidden-import win32api ^
  --hidden-import win32con ^
  --hidden-import win32event ^
  --hidden-import win32gui ^
  --hidden-import win32process ^
  --hidden-import win32ui ^
  --hidden-import charset_normalizer ^
  --collect-data certifi ^
  main.py

if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b %errorlevel%
)

echo.
echo Build finished.
echo Output: dist\%APP_NAME%.exe
endlocal
