@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ============================================================
REM  Build Wiegand 3+5 User App for TWN4 (DevPack v elafiles)
REM
REM  Pouziti:
REM    build.bat              → USB CDC  (CHANNEL_USB)
REM    build.bat cdc          → USB CDC
REM    build.bat uart         → COM1 UART onboard
REM    build.bat both         → sestavi CDC i UART
REM
REM  Vystup: out\TWN4_xCx520_W35_*.bix
REM ============================================================

set "CHANNEL_ARG=%~1"
if "%CHANNEL_ARG%"=="" set "CHANNEL_ARG=cdc"

set "REPO=%~dp0..\.."
set "DEVPACK=%REPO%\elafiles"
set "TOOLS=%DEVPACK%\Tools"
set "SYS=%TOOLS%\sys"
set "GCC=%TOOLS%\Yagarto-20110328\bin\arm-none-eabi-gcc.exe"
set "OBJCOPY=%TOOLS%\Yagarto-20110328\bin\arm-none-eabi-objcopy.exe"
set "MAKEAPP=%TOOLS%\makeapp.exe"
set "BASE_BIX=%DEVPACK%\Firmware\TWN4_xCx520_STD207_Multi_CDC_Standard.bix"

if not exist "%GCC%" (
    echo CHYBA: Nenalezen toolchain: %GCC%
    echo Dopln / aktualizuj DevPack ve slozce elafiles.
    exit /b 1
)
if not exist "%MAKEAPP%" (
    echo CHYBA: Nenalezen makeapp.exe: %MAKEAPP%
    exit /b 1
)
if not exist "%BASE_BIX%" (
    echo CHYBA: Nenalezeno zakladni CDC image:
    echo   %BASE_BIX%
    exit /b 1
)

if not exist "out" mkdir "out"

if /I "%CHANNEL_ARG%"=="both" (
    call :build_one cdc
    if errorlevel 1 exit /b 1
    call :build_one uart
    if errorlevel 1 exit /b 1
    echo.
    echo Hotovo: CDC i UART.
    exit /b 0
)

call :build_one %CHANNEL_ARG%
exit /b %ERRORLEVEL%

:build_one
set "MODE=%~1"
if /I "%MODE%"=="cdc" (
    set "HOST_DEF=CHANNEL_USB"
    set "SUFFIX=CDC"
) else if /I "%MODE%"=="uart" (
    set "HOST_DEF=CHANNEL_COM1"
    set "SUFFIX=UART"
) else (
    echo Neznamy kanal "%MODE%". Pouzij: cdc ^| uart ^| both
    exit /b 1
)

set "ELF=out\App_W35_%SUFFIX%.elf"
set "HEX=out\App_W35_%SUFFIX%.hex"
set "MAP=out\App_W35_%SUFFIX%.map"
set "LST=out\App_W35_%SUFFIX%.lst"
set "BIX=out\TWN4_xCx520_W35_%SUFFIX%.bix"

echo.
echo === Sestavuji Wiegand 3+5 / %SUFFIX%  (W35_HOST_CHANNEL=%HOST_DEF%) ===

"%GCC%" -std=c99 -mcpu=cortex-m0 -Os -ffunction-sections -gdwarf-2 -mthumb -fomit-frame-pointer -Wall -Wstrict-prototypes -fverbose-asm -Wa,-ahlms="%LST%" -DAPPCHARS=W35 -DAPPVERSION=0x101 -DW35_HOST_CHANNEL=%HOST_DEF% -I. -I"%SYS%" "%SYS%\twn4.crt.c" "App_W35_Wiegand35.c" -nostartfiles -T"%SYS%\app.ld" -Wl,--gc-sections,-e,AppHeader,--no-print-gc-sections,-Map="%MAP%",--cref,--no-warn-mismatch "%SYS%\libapp.a" -lc -o "%ELF%"
if errorlevel 1 (
    echo GCC selhal.
    exit /b 1
)

"%OBJCOPY%" -O ihex "%ELF%" "%HEX%"
if errorlevel 1 (
    echo objcopy selhal.
    exit /b 1
)

REM -v4 = MultiBIX (nCF + dalsi sloty); -v3 AppBlaster na Nano odmítne
REM -b0520 = DevPack 5.20 (BCD); jinak: Inconsistent branch version (app)
"%MAKEAPP%" -v4 -tTWN4 -nTWN4 -b0520 "-i%BASE_BIX%" "-h%HEX%" "-o%BIX%"
if errorlevel 1 (
    echo makeapp selhal.
    exit /b 1
)

echo.
echo Vystup: %BIX%
echo Nahraj do ctecky AppBlasterem: Program Firmware Image → Select Image → Program Image
exit /b 0
