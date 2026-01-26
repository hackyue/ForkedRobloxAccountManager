@echo off
setlocal

rem Build a single-file, no-console Windows executable
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --collect-all selenium ^
  --collect-all webdriver_manager ^
  main.py

echo.
echo Build finished.
echo Output: dist\FRAM.exe
endlocal
