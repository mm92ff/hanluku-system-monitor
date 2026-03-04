@echo off
setlocal EnableExtensions

pushd "%~dp0"

echo ===== GitHub CLI PATH Setup =====
echo.

where gh >nul 2>&1
if not errorlevel 1 (
    echo gh is already available in PATH.
    gh --version
    popd
    if not defined NO_PAUSE pause
    exit /b 0
)

set "GH_EXE="
if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH_EXE=%ProgramFiles%\GitHub CLI\gh.exe"
if not defined GH_EXE if exist "%LocalAppData%\Programs\GitHub CLI\gh.exe" set "GH_EXE=%LocalAppData%\Programs\GitHub CLI\gh.exe"
if not defined GH_EXE if exist "%ProgramFiles(x86)%\GitHub CLI\gh.exe" set "GH_EXE=%ProgramFiles(x86)%\GitHub CLI\gh.exe"

if not defined GH_EXE (
    echo ERROR: gh.exe was not found in the common installation folders.
    echo Install GitHub CLI first or add it to PATH manually.
    popd
    if not defined NO_PAUSE pause
    exit /b 1
)

for %%D in ("%GH_EXE%") do set "GH_DIR=%%~dpD"
if "%GH_DIR:~-1%"=="\" set "GH_DIR=%GH_DIR:~0,-1%"

echo Found GitHub CLI:
echo %GH_EXE%
echo.

powershell -NoProfile -Command ^
  "$target = $env:GH_DIR; " ^
  "$userPath = [Environment]::GetEnvironmentVariable('Path', 'User'); " ^
  "$entries = @(); if ($userPath) { $entries = $userPath -split ';' | Where-Object { $_ }; } " ^
  "if ($entries -contains $target) { exit 0 } " ^
  "$newPath = if ($userPath) { $userPath.TrimEnd(';') + ';' + $target } else { $target }; " ^
  "[Environment]::SetEnvironmentVariable('Path', $newPath, 'User')"

if errorlevel 1 (
    echo ERROR: Failed to update the user PATH.
    popd
    if not defined NO_PAUSE pause
    exit /b 1
)

set "PATH=%GH_DIR%;%PATH%"

echo Added to user PATH:
echo %GH_DIR%
echo.

where gh >nul 2>&1
if errorlevel 1 (
    echo WARNING: PATH was updated, but this shell still cannot resolve gh.
    echo Open a new terminal and run: gh --version
    popd
    if not defined NO_PAUSE pause
    exit /b 0
)

echo gh is now available in this shell:
gh --version
echo.
echo Done. New terminals will also pick up the updated PATH.

popd
if not defined NO_PAUSE pause
exit /b 0
