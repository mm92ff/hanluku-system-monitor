@echo off
setlocal EnableExtensions

pushd "%~dp0"

set "APP_NAME=SystemMonitorOverlay"
set "PYI=py -3 -m PyInstaller"

echo Building %APP_NAME%...
echo.
echo ===== Pre-cleanup =====

if exist "dist" (
    for %%F in ("dist\*.exe") do (
        echo Preserving previous build: %%~nxF
        copy /y "%%F" "." >nul
    )
    rmdir /s /q "dist"
)

if exist "build" rmdir /s /q "build"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo.
echo ===== Checks =====

if not exist "main.py" (
    echo ERROR: main.py not found.
    popd
    exit /b 1
)

if not exist "libs\LibreHardwareMonitorLib.dll" (
    echo ERROR: Missing libs\LibreHardwareMonitorLib.dll
    popd
    exit /b 1
)

if not exist "libs\HidSharp.dll" (
    echo ERROR: Missing libs\HidSharp.dll
    popd
    exit /b 1
)

if not exist "assets\fonts\FiraCode-Regular.ttf" (
    echo ERROR: Missing assets\fonts\FiraCode-Regular.ttf
    popd
    exit /b 1
)

if not exist "assets\fonts\FiraCode-Bold.ttf" (
    echo ERROR: Missing assets\fonts\FiraCode-Bold.ttf
    popd
    exit /b 1
)

set "ICON_ARG="
if exist "assets\icons\phoenix_outline_on_dark.ico" (
    set "ICON_ARG=--icon=assets\icons\phoenix_outline_on_dark.ico"
) else (
    echo Warning: No icon file found at assets\icons\phoenix_outline_on_dark.ico
)

echo.
echo ===== Build =====

%PYI% --noconfirm --clean --onefile --windowed ^
  --name="%APP_NAME%" ^
  %ICON_ARG% ^
  --add-data="libs\LibreHardwareMonitorLib.dll;libs" ^
  --add-data="libs\HidSharp.dll;libs" ^
  --add-data="assets\fonts\FiraCode-Regular.ttf;assets\fonts" ^
  --add-data="assets\fonts\FiraCode-Bold.ttf;assets\fonts" ^
  --hidden-import="clr" ^
  --hidden-import="pythonnet" ^
  --hidden-import="clr_loader" ^
  --hidden-import="psutil" ^
  --collect-all="pythonnet" ^
  --collect-all="PySide6" ^
  --uac-admin ^
  main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed.
    popd
    exit /b 1
)

echo.
echo ===== Post-build: copy EXE + cleanup =====

if exist "dist\*.exe" (
    for %%F in ("dist\*.exe") do (
        echo Copying %%~nxF to current folder...
        copy /y "%%F" "." >nul
    )
) else (
    echo ERROR: No executable found in dist.
    popd
    exit /b 1
)

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo.
echo Build complete. The executable is next to this batch file.

popd
if not defined NO_PAUSE pause
