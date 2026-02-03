@echo off
setlocal

set APP_NAME=FRAM

rem Build a single-file, no-console Windows executable
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name %APP_NAME% ^
  --icon icon.ico ^
  --collect-all selenium ^
  --collect-all webdriver_manager ^
  main.py

echo.
echo Build finished.
echo Output: dist\%APP_NAME%.exe
endlocal
