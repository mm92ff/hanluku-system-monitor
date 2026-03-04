@echo off
setlocal EnableExtensions

pushd "%~dp0"

set "DEFAULT_APP_NAME=Hanluku_system_monitor_v1.0-beta"
set "APP_NAME=%DEFAULT_APP_NAME%"
set "BUILD_SCRIPT=build_exe.bat"
set "DEFAULT_EXE=%APP_NAME%.exe"
set "SCRIPT_NAME=%~nx0"
set "LOG_FILE=%~dp0release_to_github_debug.txt.log"
set "ZIP_FILE="
set "REPO_SLUG="
set "CHANGE_COUNT=0"
set "DO_TAG=N"
set "DO_BUILD=N"
set "DO_ZIP=N"
set "DO_RELEASE=N"
set "DRY_RUN=N"
set "BRANCH_NAME="

> "%LOG_FILE%" echo([%date% %time%] Starting %SCRIPT_NAME%
>> "%LOG_FILE%" echo([%date% %time%] Working directory: %CD%

call :prompt_yes_no "Dry run mode (no commit, push, build, tag, zip or release changes)" "N" DRY_RUN
>> "%LOG_FILE%" echo([%date% %time%] Dry run selected: %DRY_RUN%
echo.
if /I "%DRY_RUN%"=="Y" (
    echo ===== DRY RUN ENABLED =====
    echo No write actions will be executed.
    echo.
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    set "ERROR_MESSAGE=ERROR: This script must be run inside a git repository."
    goto :fail
)

call :resolve_repo_slug
if not defined REPO_SLUG (
    set "ERROR_MESSAGE=ERROR: Could not resolve the GitHub repository from origin."
    goto :fail
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH_NAME=%%B"
>> "%LOG_FILE%" echo([%date% %time%] Resolved repository: %REPO_SLUG%
>> "%LOG_FILE%" echo([%date% %time%] Current branch: %BRANCH_NAME%

echo Repository: %REPO_SLUG%
echo Branch:
echo %BRANCH_NAME%
echo.
echo ===== Current Git Status =====
git status --short
>> "%LOG_FILE%" echo([%date% %time%] Git status snapshot:
>> "%LOG_FILE%" git status --short 2>&1
echo.

for /f %%C in ('powershell -NoProfile -Command "@(git status --porcelain).Count"') do set "CHANGE_COUNT=%%C"
>> "%LOG_FILE%" echo([%date% %time%] Detected changed paths: %CHANGE_COUNT%

if not "%CHANGE_COUNT%"=="0" (
    set /p "COMMIT_MSG=Commit message: "
    if not defined COMMIT_MSG (
        set "ERROR_MESSAGE=ERROR: Commit message is required when there are local changes."
        goto :fail
    )
    >> "%LOG_FILE%" echo([%date% %time%] Commit message captured.
) else (
    echo No local changes detected. Commit step will be skipped.
    echo.
    >> "%LOG_FILE%" echo([%date% %time%] No local changes detected. Commit step skipped.
)

if defined COMMIT_MSG set "COMMIT_MSG=%COMMIT_MSG:"='%"

call :prompt_yes_no "Create and push a tag for this run" "N" DO_TAG
>> "%LOG_FILE%" echo([%date% %time%] Tag flow selected: %DO_TAG%

if /I not "%DO_TAG%"=="Y" (
    set "TAG_NAME="
    set "DO_BUILD=N"
    set "DO_ZIP=N"
    set "DO_RELEASE=N"
    >> "%LOG_FILE%" echo([%date% %time%] Commit-only flow selected.
    goto :tag_options_done
)

set /p "TAG_NAME=Tag name e.g. v1.1.0-beta: "
if not defined TAG_NAME (
    set "ERROR_MESSAGE=ERROR: Tag name is required."
    goto :fail
)

if not "%TAG_NAME: =%"=="%TAG_NAME%" (
    set "ERROR_MESSAGE=ERROR: Tag names must not contain spaces."
    goto :fail
)

set "APP_NAME=Hanluku_system_monitor_%TAG_NAME%"
if defined APP_NAME_OVERRIDE set "APP_NAME=%APP_NAME_OVERRIDE%"
if /I not "%SKIP_APP_NAME_PROMPT%"=="Y" (
    call :prompt_with_default "EXE name without .exe:" "Release EXE Name" "%APP_NAME%" APP_NAME
)
call :normalize_app_name APP_NAME
set "DEFAULT_EXE=%APP_NAME%.exe"
>> "%LOG_FILE%" echo([%date% %time%] Tag entered: %TAG_NAME%
>> "%LOG_FILE%" echo([%date% %time%] EXE name selected: %APP_NAME%
call :prompt_yes_no "Build the EXE now" "N" DO_BUILD
call :prompt_yes_no "Create a ZIP archive with the EXE" "N" DO_ZIP
call :prompt_yes_no "Create a GitHub release for this tag" "N" DO_RELEASE
>> "%LOG_FILE%" echo([%date% %time%] Build selected: %DO_BUILD%
>> "%LOG_FILE%" echo([%date% %time%] ZIP selected: %DO_ZIP%
>> "%LOG_FILE%" echo([%date% %time%] Release selected: %DO_RELEASE%

if /I "%DO_ZIP%"=="Y" (
    set "DO_BUILD=Y"
    >> "%LOG_FILE%" echo([%date% %time%] ZIP requires build. Build forced to Y.
)

:tag_options_done

echo.
echo ===== Commit / Push =====
>> "%LOG_FILE%" echo([%date% %time%] Entering commit/push stage.

if not "%CHANGE_COUNT%"=="0" (
    if /I "%DRY_RUN%"=="Y" (
        echo [DRY RUN] Would run: git add -A
        echo [DRY RUN] Would run: git add -f "%SCRIPT_NAME%"
        echo [DRY RUN] Would run: git commit -m "%COMMIT_MSG%"
        echo [DRY RUN] Would run: git push origin HEAD
        >> "%LOG_FILE%" echo([%date% %time%] Dry run: simulated git add/commit/push.
    ) else (
        >> "%LOG_FILE%" echo([%date% %time%] Running git add -A.
        git add -A
        >> "%LOG_FILE%" echo([%date% %time%] Running git add -f %SCRIPT_NAME%.
        git add -f "%SCRIPT_NAME%" >nul 2>&1
        >> "%LOG_FILE%" echo([%date% %time%] Running git commit.
        git commit -m "%COMMIT_MSG%"
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: git commit failed."
            goto :fail
        )

        >> "%LOG_FILE%" echo([%date% %time%] Running git push origin HEAD.
        git push origin HEAD
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: git push failed."
            goto :fail
        )
        >> "%LOG_FILE%" echo([%date% %time%] Commit/push completed successfully.
    )
) else (
    echo Nothing to commit.
    >> "%LOG_FILE%" echo([%date% %time%] Nothing to commit.
)

if /I "%DO_BUILD%"=="Y" (
    echo.
    echo ===== Build EXE =====
    >> "%LOG_FILE%" echo([%date% %time%] Entering EXE build stage.
    if not exist "%BUILD_SCRIPT%" (
        set "ERROR_MESSAGE=ERROR: Missing %BUILD_SCRIPT%"
        goto :fail
    )

    if /I "%DRY_RUN%"=="Y" (
        echo [DRY RUN] Would run: %BUILD_SCRIPT%
        echo [DRY RUN] Output EXE: %DEFAULT_EXE%
        >> "%LOG_FILE%" echo([%date% %time%] Dry run: simulated EXE build.
    ) else (
        set "APP_NAME_OVERRIDE=%APP_NAME%"
        set "SKIP_APP_NAME_PROMPT=Y"
        set "NO_PAUSE=1"
        call "%BUILD_SCRIPT%"
        set "NO_PAUSE="
        set "SKIP_APP_NAME_PROMPT="
        set "APP_NAME_OVERRIDE="
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: EXE build failed."
            goto :fail
        )
        >> "%LOG_FILE%" echo([%date% %time%] EXE build completed successfully.
    )
)

if /I "%DO_ZIP%"=="Y" set "ZIP_FILE=%APP_NAME%.zip"

if /I "%DO_ZIP%"=="Y" (
    echo.
    echo ===== Create ZIP =====
    >> "%LOG_FILE%" echo([%date% %time%] Entering ZIP stage. Target: %ZIP_FILE%
    if /I "%DRY_RUN%"=="Y" (
        echo [DRY RUN] Would create ZIP: %ZIP_FILE%
        echo [DRY RUN] Source EXE: %DEFAULT_EXE%
        >> "%LOG_FILE%" echo([%date% %time%] Dry run: simulated ZIP creation.
    ) else (
        if not exist "%DEFAULT_EXE%" (
            set "ERROR_MESSAGE=ERROR: Expected EXE not found: %DEFAULT_EXE%"
            goto :fail
        )

        if exist "%ZIP_FILE%" del /f /q "%ZIP_FILE%"

        powershell -NoProfile -Command "Compress-Archive -Path '%DEFAULT_EXE%' -DestinationPath '%ZIP_FILE%' -Force"
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: ZIP creation failed."
            goto :fail
        )

        echo ZIP created: %ZIP_FILE%
        >> "%LOG_FILE%" echo([%date% %time%] ZIP created successfully: %ZIP_FILE%
    )
)

if /I "%DO_TAG%"=="Y" (
    echo.
    echo ===== Create / Push Tag =====
    >> "%LOG_FILE%" echo([%date% %time%] Entering tag stage for %TAG_NAME%.

    git show-ref --verify --quiet "refs/tags/%TAG_NAME%"
    if not errorlevel 1 (
        set "ERROR_MESSAGE=ERROR: Tag %TAG_NAME% already exists locally."
        goto :fail
    )

    git ls-remote --exit-code --tags origin "refs/tags/%TAG_NAME%" >nul 2>&1
    if not errorlevel 1 (
        set "ERROR_MESSAGE=ERROR: Tag %TAG_NAME% already exists on origin."
        goto :fail
    )

    if /I "%DRY_RUN%"=="Y" (
        echo [DRY RUN] Would run: git tag "%TAG_NAME%"
        echo [DRY RUN] Would run: git push origin "%TAG_NAME%"
        >> "%LOG_FILE%" echo([%date% %time%] Dry run: simulated tag creation and push.
    ) else (
        >> "%LOG_FILE%" echo([%date% %time%] Running git tag %TAG_NAME%.
        git tag "%TAG_NAME%"
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: Failed to create tag %TAG_NAME%."
            goto :fail
        )

        >> "%LOG_FILE%" echo([%date% %time%] Running git push origin %TAG_NAME%.
        git push origin "%TAG_NAME%"
        if errorlevel 1 (
            set "ERROR_MESSAGE=ERROR: Failed to push tag %TAG_NAME%."
            goto :fail
        )
        >> "%LOG_FILE%" echo([%date% %time%] Tag created and pushed successfully: %TAG_NAME%
    )

    if /I "%DO_RELEASE%"=="Y" (
        echo.
        echo ===== GitHub Release =====
        >> "%LOG_FILE%" echo([%date% %time%] Entering GitHub release stage.
        if /I "%DRY_RUN%"=="Y" (
            if defined ZIP_FILE (
                echo [DRY RUN] Would create GitHub release %TAG_NAME% with asset %ZIP_FILE%
            ) else (
                echo [DRY RUN] Would create GitHub release %TAG_NAME% without assets
            )
            >> "%LOG_FILE%" echo([%date% %time%] Dry run: simulated GitHub release.
        ) else (
            call :create_release
            if errorlevel 1 (
                set "ERROR_MESSAGE=ERROR: GitHub release creation failed."
                goto :fail
            )
        )
    )
)

echo.
echo Done.
if /I "%DRY_RUN%"=="Y" (
    echo Dry run completed. No changes were written.
    if defined ZIP_FILE echo Planned release asset: %ZIP_FILE%
    if defined TAG_NAME echo Planned tag: %TAG_NAME%
) else (
    if defined ZIP_FILE echo Release asset: %ZIP_FILE%
    if defined TAG_NAME (
        echo Tag pushed: %TAG_NAME%
    ) else (
        echo Commit/push completed without tag or release.
    )
)
>> "%LOG_FILE%" echo([%date% %time%] Script completed successfully.

popd
if not defined NO_PAUSE pause
exit /b 0

:prompt_yes_no
set "PROMPT_TEXT=%~1"
set "DEFAULT_CHOICE=%~2"
set "ANSWER="
if /I "%DEFAULT_CHOICE%"=="Y" (
    set "CHOICE_HINT=Y/n"
) else (
    set "CHOICE_HINT=y/N"
)

:prompt_yes_no_retry
set "ANSWER="
set /p "ANSWER=%PROMPT_TEXT% [%CHOICE_HINT%]: "
if not defined ANSWER set "ANSWER=%DEFAULT_CHOICE%"

if /I "%ANSWER%"=="Y" (
    set "%~3=Y"
    >> "%LOG_FILE%" echo([%date% %time%] Prompt %~3 = Y
    exit /b 0
)

if /I "%ANSWER%"=="N" (
    set "%~3=N"
    >> "%LOG_FILE%" echo([%date% %time%] Prompt %~3 = N
    exit /b 0
)

echo Please enter Y or N.
goto prompt_yes_no_retry

:resolve_repo_slug
set "ORIGIN_URL="
for /f "usebackq delims=" %%R in (`git remote get-url origin 2^>nul`) do set "ORIGIN_URL=%%R"
if not defined ORIGIN_URL exit /b 0
for /f "usebackq delims=" %%R in (`powershell -NoProfile -Command "$u = $env:ORIGIN_URL; if ($u -match 'github\.com[:/](.+?)(?:\.git)?$') { $matches[1] }"`) do set "REPO_SLUG=%%R"
>> "%LOG_FILE%" echo([%date% %time%] Origin URL: %ORIGIN_URL%
if defined REPO_SLUG (
    >> "%LOG_FILE%" echo([%date% %time%] Repository slug resolved to %REPO_SLUG%
)
exit /b 0

:create_release
>> "%LOG_FILE%" echo([%date% %time%] Checking GitHub release creation method.
where gh >nul 2>&1
if not errorlevel 1 (
    >> "%LOG_FILE%" echo([%date% %time%] Using gh CLI for release creation.
    if defined ZIP_FILE (
        gh release create "%TAG_NAME%" "%ZIP_FILE%" --repo "%REPO_SLUG%" --title "%TAG_NAME%" --generate-notes
    ) else (
        gh release create "%TAG_NAME%" --repo "%REPO_SLUG%" --title "%TAG_NAME%" --generate-notes
    )
    if errorlevel 1 (
        >> "%LOG_FILE%" echo([%date% %time%] gh release create failed.
        echo ERROR: gh release create failed.
        exit /b 1
    )
    >> "%LOG_FILE%" echo([%date% %time%] GitHub release created successfully via gh.
    exit /b 0
)

if exist "add_gh_to_path.bat" (
    echo GitHub CLI is not currently available in PATH.
    >> "%LOG_FILE%" echo([%date% %time%] gh not found in PATH. Offering add_gh_to_path.bat.
    call :prompt_yes_no "Run add_gh_to_path.bat now and retry gh" "Y" FIX_GH_PATH
    if /I "%FIX_GH_PATH%"=="Y" (
        >> "%LOG_FILE%" echo([%date% %time%] Running add_gh_to_path.bat.
        set "NO_PAUSE=1"
        call "add_gh_to_path.bat"
        set "NO_PAUSE="
        where gh >nul 2>&1
        if not errorlevel 1 (
            >> "%LOG_FILE%" echo([%date% %time%] gh available after PATH fix. Retrying release creation.
            if defined ZIP_FILE (
                gh release create "%TAG_NAME%" "%ZIP_FILE%" --repo "%REPO_SLUG%" --title "%TAG_NAME%" --generate-notes
            ) else (
                gh release create "%TAG_NAME%" --repo "%REPO_SLUG%" --title "%TAG_NAME%" --generate-notes
            )
            if errorlevel 1 (
                >> "%LOG_FILE%" echo([%date% %time%] gh release create failed after PATH fix.
                echo ERROR: gh release create failed.
                exit /b 1
            )
            >> "%LOG_FILE%" echo([%date% %time%] GitHub release created successfully after PATH fix.
            exit /b 0
        )
        >> "%LOG_FILE%" echo([%date% %time%] gh still unavailable after PATH fix attempt.
    )
)

if defined GH_TOKEN (
    set "RELEASE_TOKEN=%GH_TOKEN%"
    >> "%LOG_FILE%" echo([%date% %time%] Using GH_TOKEN fallback for release creation.
    call :create_release_with_token
    exit /b %errorlevel%
)

if defined GITHUB_TOKEN (
    set "RELEASE_TOKEN=%GITHUB_TOKEN%"
    >> "%LOG_FILE%" echo([%date% %time%] Using GITHUB_TOKEN fallback for release creation.
    call :create_release_with_token
    exit /b %errorlevel%
)

echo WARNING: Neither GitHub CLI nor GH_TOKEN/GITHUB_TOKEN is available.
echo Opening the manual release page in your browser instead.
>> "%LOG_FILE%" echo([%date% %time%] No gh or token available. Falling back to manual release page.
start "" "https://github.com/%REPO_SLUG%/releases/new?tag=%TAG_NAME%"
if defined ZIP_FILE echo Upload this file manually: %ZIP_FILE%
exit /b 0

:create_release_with_token
set "PS_FILE=%TEMP%\release_to_github_upload.ps1"
if exist "%PS_FILE%" del /f /q "%PS_FILE%"
>> "%LOG_FILE%" echo([%date% %time%] Creating temporary PowerShell release uploader.

> "%PS_FILE%" echo param([string]$Repo,[string]$Tag,[string]$ZipPath)
>> "%PS_FILE%" echo $token = $env:RELEASE_TOKEN
>> "%PS_FILE%" echo if (-not $token) { throw "Missing RELEASE_TOKEN environment variable." }
>> "%PS_FILE%" echo $headers = @{
>> "%PS_FILE%" echo ^  Authorization = "Bearer $token"
>> "%PS_FILE%" echo ^  Accept = "application/vnd.github+json"
>> "%PS_FILE%" echo ^  "X-GitHub-Api-Version" = "2022-11-28"
>> "%PS_FILE%" echo }
>> "%PS_FILE%" echo $isPrerelease = $Tag -match '(?i)(alpha^|beta^|rc)'
>> "%PS_FILE%" echo $body = @{
>> "%PS_FILE%" echo ^  tag_name = $Tag
>> "%PS_FILE%" echo ^  name = $Tag
>> "%PS_FILE%" echo ^  draft = $false
>> "%PS_FILE%" echo ^  prerelease = $isPrerelease
>> "%PS_FILE%" echo ^  generate_release_notes = $true
>> "%PS_FILE%" echo } ^| ConvertTo-Json
>> "%PS_FILE%" echo $release = Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/$Repo/releases" -Headers $headers -Body $body -ContentType "application/json"
>> "%PS_FILE%" echo if ($ZipPath -and (Test-Path $ZipPath)) {
>> "%PS_FILE%" echo ^  $assetHeaders = @{
>> "%PS_FILE%" echo ^    Authorization = "Bearer $token"
>> "%PS_FILE%" echo ^    Accept = "application/vnd.github+json"
>> "%PS_FILE%" echo ^    "Content-Type" = "application/zip"
>> "%PS_FILE%" echo ^    "X-GitHub-Api-Version" = "2022-11-28"
>> "%PS_FILE%" echo ^  }
>> "%PS_FILE%" echo ^  $uploadBase = $release.upload_url -replace '\{\?name,label\}', ''
>> "%PS_FILE%" echo ^  $assetName = Split-Path -Path $ZipPath -Leaf
>> "%PS_FILE%" echo ^  $uploadUrl = "$uploadBase?name=$([uri]::EscapeDataString($assetName))"
>> "%PS_FILE%" echo ^  Invoke-RestMethod -Method Post -Uri $uploadUrl -Headers $assetHeaders -InFile $ZipPath
>> "%PS_FILE%" echo }

if defined ZIP_FILE (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_FILE%" -Repo "%REPO_SLUG%" -Tag "%TAG_NAME%" -ZipPath "%ZIP_FILE%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_FILE%" -Repo "%REPO_SLUG%" -Tag "%TAG_NAME%" -ZipPath ""
)
set "PS_ERROR=%errorlevel%"

if exist "%PS_FILE%" del /f /q "%PS_FILE%"
set "RELEASE_TOKEN="

if not "%PS_ERROR%"=="0" (
    >> "%LOG_FILE%" echo([%date% %time%] Release creation via token failed.
    echo ERROR: GitHub release creation via token failed.
    exit /b 1
)

>> "%LOG_FILE%" echo([%date% %time%] GitHub release created successfully via token.
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

:fail
echo.
echo %ERROR_MESSAGE%
>> "%LOG_FILE%" echo([%date% %time%] %ERROR_MESSAGE%
>> "%LOG_FILE%" echo([%date% %time%] Script aborted.
popd
if not defined NO_PAUSE pause
exit /b 1
