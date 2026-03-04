@echo off
setlocal EnableExtensions

pushd "%~dp0"

set "DEFAULT_APP_NAME=Hanluku_system_monitor_v1.0-beta"
if defined APP_NAME_OVERRIDE (
    set "APP_NAME=%APP_NAME_OVERRIDE%"
) else (
    set "APP_NAME=%DEFAULT_APP_NAME%"
)
set "PYI=py -3 -m PyInstaller"

if /I not "%SKIP_APP_NAME_PROMPT%"=="Y" (
    call :prompt_with_default "EXE name without .exe:" "Build EXE Name" "%APP_NAME%" APP_NAME
)
call :normalize_app_name APP_NAME

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
echo Build complete. Created %APP_NAME%.exe next to this batch file.

popd
if not defined NO_PAUSE pause
exit /b 0

:prompt_with_default
set "PROMPT_RESULT="
for /f "usebackq delims=" %%R in (`powershell -NoProfile -Command "Add-Type -AssemblyName Microsoft.VisualBasic | Out-Null; $value = [Microsoft.VisualBasic.Interaction]::InputBox('%~1','%~2','%~3'); if ($null -ne $value) { [Console]::Write($value) }"`) do set "PROMPT_RESULT=%%R"
if not defined PROMPT_RESULT set "PROMPT_RESULT=%~3"
set "%~4=%PROMPT_RESULT%"
exit /b 0

:normalize_app_name
call set "NORMALIZED_VALUE=%%%~1%%"
setlocal EnableDelayedExpansion
set "NORMALIZED_VALUE=!NORMALIZED_VALUE:"=!"
if /I "!NORMALIZED_VALUE:~-4!"==".exe" set "NORMALIZED_VALUE=!NORMALIZED_VALUE:~0,-4!"
if not defined NORMALIZED_VALUE set "NORMALIZED_VALUE=%DEFAULT_APP_NAME%"
endlocal & set "%~1=%NORMALIZED_VALUE%"
exit /b 0
