@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set "PYTHON=.venv\Scripts\python.exe"

where py >nul 2>nul
if errorlevel 1 (
    echo CHYBA: Python launcher "py" nebyl nalezen.
    echo Nainstaluj Python 3.10 nebo novejsi a zapni volbu Add Python to PATH.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Vytvarim virtualni prostredi...
    py -m venv .venv
    if errorlevel 1 goto :install_error
)

echo Kontroluji instalaci ELATEC UID Tool...
"%PYTHON%" -m pip install --disable-pip-version-check -q -e .
if errorlevel 1 goto :install_error

for /f "delims=" %%V in ('"%PYTHON%" -m elatec_uid_tool --version') do set "TOOL_VERSION=%%V"

:menu
cls
echo ========================================================================
echo                     %TOOL_VERSION%
echo ========================================================================
echo.
echo   1. Tests - otestovat medium a vypsat jeho typ
echo   2. Interactive mode - hledani UID a pravidla pro AppBlaster
echo   3. Update reader - priprava PRS a vlastniho firmware
echo   4. GUI - desktopova aplikace
echo   5. Build FW - sestavit .bix (Wiegand 3+5 / export-fw)
echo   0. Konec
echo.
echo   Navod: docs\NAVOD.md
echo.
set /p "CHOICE=Vyber 0-5: "

if "%CHOICE%"=="1" goto :test_medium
if "%CHOICE%"=="2" goto :interactive
if "%CHOICE%"=="3" goto :update_reader
if "%CHOICE%"=="4" goto :gui
if "%CHOICE%"=="5" goto :build_fw
if "%CHOICE%"=="0" goto :end

echo.
echo Neplatna volba.
pause
goto :menu

:test_medium
cls
"%PYTHON%" -m elatec_uid_tool test-medium
call :pause_and_menu
goto :menu

:interactive
cls
"%PYTHON%" -m elatec_uid_tool interactive
call :pause_and_menu
goto :menu

:update_reader
cls
if exist "%~dp0elafiles\Tools\makeapp.exe" (
    "%PYTHON%" -m elatec_uid_tool update-reader --devpack "%~dp0elafiles"
) else (
    "%PYTHON%" -m elatec_uid_tool update-reader --devpack "%~dp0files520"
)
call :pause_and_menu
goto :menu

:gui
cls
call "%~dp0gui\run_gui.bat"
goto :menu

:build_fw
cls
call "%~dp0build_fw.bat"
goto :menu

:pause_and_menu
echo.
pause
exit /b 0

:install_error
echo.
echo Instalace nebo aktualizace projektu selhala.
pause
exit /b 1

:end
exit /b 0
