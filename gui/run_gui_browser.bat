@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Nejdrive spust install_windows.bat
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -q -r gui\requirements.txt
if errorlevel 1 goto :error

echo Spoustim GUI v prohlizeci na http://127.0.0.1:8080
".venv\Scripts\python.exe" gui\app.py --browser
pause
exit /b 0

:error
echo Spusteni GUI selhalo.
pause
exit /b 1
