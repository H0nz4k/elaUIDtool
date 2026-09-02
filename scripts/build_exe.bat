@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
chcp 65001 >nul

if not exist ".venv\Scripts\python.exe" (
  echo Nejdrive spust elaUIDtool.bat
  pause
  exit /b 1
)

set "PY=.venv\Scripts\python.exe"

echo [1/3] Instaluji GUI + PyInstaller...
"%PY%" -m pip install -q -r gui\requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [2/3] Sestavuji Windows EXE - pouze GUI...
if exist "dist\elaUIDtool" rmdir /s /q "dist\elaUIDtool"
"%PY%" -m PyInstaller --noconfirm --clean elaUIDtool.spec
if errorlevel 1 goto :error

if not exist "dist\elaUIDtool\elaUIDtool.exe" (
  echo CHYBA: dist\elaUIDtool\elaUIDtool.exe nevznikl
  goto :error
)

echo [3/3] Pripravuji release slozku...
for /f "delims=" %%V in ('"%PY%" -c "from elatec_uid_tool import __version__; print(__version__)"') do set "VER=%%V"
set "OUT=releases\elaUIDtool-%VER%-win64-gui"
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"
xcopy /e /i /q "dist\elaUIDtool\*" "%OUT%\"
if errorlevel 1 goto :error

mkdir "%OUT%\elafiles" 2>nul
(
echo Sem zkopiruj TWN4DevPack520 ^(Tools + Apps CCx/MCx/NCx^).
echo Nebo v GUI - Nastaveni zadej cestu k DevPacku.
echo Bez DevPacku funguje Porovnani a nacteni karty; Vytvorit FW ne.
) > "%OUT%\elafiles\README.txt"

(
echo elaUIDtool %VER% - Windows GUI
echo.
echo Spust: elaUIDtool.exe
echo.
echo Porovnani kodu z ctecky vs DB funguje ihned.
echo Pro Vytvorit FW zkopiruj DevPack520 do slozky elafiles vedle EXE
echo nebo nastav cestu v GUI - Nastaveni.
echo.
echo Vystup FW: FW_elatec\export\out\ vedle EXE.
) > "%OUT%\START_HERE.txt"

echo.
echo Hotovo: %OUT%\elaUIDtool.exe
dir "%OUT%\elaUIDtool.exe"
pause
exit /b 0

:error
echo.
echo Build EXE selhal.
pause
exit /b 1
