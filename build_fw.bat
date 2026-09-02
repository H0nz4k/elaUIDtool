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

REM build_fw.bat [cdc|uart|both] [raw] [expected] [tag] [base-bix] [branch]
set "CHANNEL=%~1"
if "%CHANNEL%"=="" set "CHANNEL=cdc"

set "RAW=%~2"
if "%RAW%"=="" set "RAW=E9B20DFF"

set "EXPECTED=%~3"
if "%EXPECTED%"=="" set "EXPECTED=01345801"

set "TAGTYPE=%~4"
if "%TAGTYPE%"=="" set "TAGTYPE=0x80"

set "BASEBIX=%~5"
set "BRANCH=%~6"
if "%BRANCH%"=="" set "BRANCH=0520"

set "EXTRA="
if not "%BASEBIX%"=="" set "EXTRA=--base-bix "%BASEBIX%""

echo ========================================================================
echo  Build FW  channel=%CHANNEL%  raw=%RAW%  expected=%EXPECTED%
echo  tag=%TAGTYPE%  branch=%BRANCH%
if not "%BASEBIX%"=="" echo  base=%BASEBIX%
echo ========================================================================
echo.

if "%BASEBIX%"=="" (
    "%PYTHON%" -m elatec_uid_tool export-fw --raw %RAW% --bits 32 --expected %EXPECTED% --channel %CHANNEL% --tag-type %TAGTYPE% --branch %BRANCH%
) else (
    "%PYTHON%" -m elatec_uid_tool export-fw --raw %RAW% --bits 32 --expected %EXPECTED% --channel %CHANNEL% --tag-type %TAGTYPE% --branch %BRANCH% --base-bix "%BASEBIX%"
)
if errorlevel 1 (
    echo.
    echo Build selhal. Over, ze existuje:
    echo   elafiles\Firmware\TWN4_xCx520_STD207_Multi_CDC_Standard.bix
    pause
    exit /b 1
)

echo.
echo Hotovo. .bix je v FW_elatec\export\out\
echo Nahraj TWN4_xCx520_EXP_CDC.bix ^(nebo _UART^) v AppBlasteru.
pause
exit /b 0
