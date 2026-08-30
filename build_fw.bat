@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Nejdrive spust elaUIDtool.bat nebo install_windows.bat
    pause
    exit /b 1
)

set "CHANNEL=%~1"
if "%CHANNEL%"=="" set "CHANNEL=cdc"

set "RAW=%~2"
if "%RAW%"=="" set "RAW=E9B20DFF"

set "EXPECTED=%~3"
if "%EXPECTED%"=="" set "EXPECTED=01345801"

set "TAGTYPE=%~4"
if "%TAGTYPE%"=="" set "TAGTYPE=0x80"

echo ========================================================================
echo  Build FW  channel=%CHANNEL%  raw=%RAW%  expected=%EXPECTED%  tag=%TAGTYPE%
echo ========================================================================
echo.

"%PYTHON%" -m elatec_uid_tool export-fw --raw %RAW% --bits 32 --expected %EXPECTED% --channel %CHANNEL% --tag-type %TAGTYPE%
if errorlevel 1 (
    echo.
    echo Build selhal. Zkontroluj elafiles\ DevPack a parametry.
    pause
    exit /b 1
)

echo.
echo Hotovo. .bix je v FW_elatec\export\out\
echo Nahraj v AppBlasteru: Program Firmware Image -^> Select Image -^> Program Image
pause
exit /b 0
