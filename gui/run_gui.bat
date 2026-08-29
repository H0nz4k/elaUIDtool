@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Nejdrive spust install_windows.bat
    pause
    exit /b 1
)

echo Instaluji zavislosti GUI...
".venv\Scripts\python.exe" -m pip install -q -r gui\requirements.txt
if errorlevel 1 goto :error

echo Spoustim desktopove okno aplikace...
".venv\Scripts\python.exe" gui\app.py
pause
exit /b 0

:error
echo.
echo Spusteni GUI selhalo.
pause
exit /b 1
