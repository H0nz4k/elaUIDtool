@echo off
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
    echo Nejdrive spust elaUIDtool.bat
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\pack_release.py %*
echo.
echo Hotovo. Slozka a ZIP jsou v releases\
pause
