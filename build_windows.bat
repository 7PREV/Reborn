@echo off
setlocal

echo [1/5] Moving to project root...
cd /d "%~dp0"

echo [2/5] Installing build dependencies...
py -m pip install --upgrade pip
py -m pip install -r backend\rivals_guard\requirements.txt pyinstaller

echo [3/5] Building RivalsGuard.exe...
cd /d backend\rivals_guard
py -m PyInstaller --clean --noconfirm --onefile --windowed --name RivalsGuard guard_client.py

echo [4/5] Copying EXE to backend\static\downloads...
if not exist ..\static\downloads mkdir ..\static\downloads
copy /Y dist\RivalsGuard.exe ..\static\downloads\RivalsGuard.exe >nul
if exist ..\static\downloads\RivalsGuard_Setup.zip del /f /q ..\static\downloads\RivalsGuard_Setup.zip
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '..\static\downloads\RivalsGuard.exe' -DestinationPath '..\static\downloads\RivalsGuard_Setup.zip' -Force"

echo [5/5] Done.
echo Output: backend\static\downloads\RivalsGuard_Setup.zip
pause
