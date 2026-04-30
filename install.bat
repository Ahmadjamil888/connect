@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "REPO_URL=https://github.com/Ahmadjamil888/connect.git"
set "ZIP_URL=https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.zip"
set "INSTALL_DIR=%CONNECT_INSTALL_DIR%"
if not defined INSTALL_DIR set "INSTALL_DIR=%USERPROFILE%\connect"
set "DATA_DIR=%USERPROFILE%\.connectai"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ========================================
echo   CONNECT INSTALLER
echo ========================================

call :resolve_repo_dir || exit /b 1
call :resolve_python || exit /b 1
call :create_venv || exit /b 1
call :install_requirements || exit /b 1
call :ensure_env || exit /b 1
call :ensure_data_dir || exit /b 1
call :install_launcher || exit /b 1
call :print_next_steps
exit /b 0

:resolve_repo_dir
if exist "%SCRIPT_DIR%\ai_assistant.py" (
    set "REPO_DIR=%SCRIPT_DIR%"
    echo [*] Using existing repo at %REPO_DIR%
    exit /b 0
)

set "REPO_DIR=%INSTALL_DIR%"

if exist "%REPO_DIR%\.git" (
    where git >nul 2>nul || (
        echo [!] Git is required to update the existing CONNECT clone.
        exit /b 1
    )
    echo [*] Updating existing clone in %REPO_DIR%
    git -C "%REPO_DIR%" pull --ff-only || exit /b 1
    exit /b 0
)

if exist "%REPO_DIR%\ai_assistant.py" (
    echo [*] Reusing existing install in %REPO_DIR%
    exit /b 0
)

if exist "%REPO_DIR%" (
    dir /b "%REPO_DIR%" 2>nul | findstr . >nul && (
        echo [!] %REPO_DIR% already exists and is not a CONNECT repo.
        echo [!] Set CONNECT_INSTALL_DIR to an empty directory or run install.bat from the repo itself.
        exit /b 1
    )
) else (
    mkdir "%REPO_DIR%" || exit /b 1
)

where git >nul 2>nul
if %errorlevel%==0 (
    echo [*] Cloning CONNECT into %REPO_DIR%
    git clone "%REPO_URL%" "%REPO_DIR%" || exit /b 1
    exit /b 0
)

echo [*] Downloading CONNECT archive into %REPO_DIR%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$zipPath = Join-Path $env:TEMP 'connect-main.zip';" ^
  "Invoke-WebRequest '%ZIP_URL%' -OutFile $zipPath;" ^
  "Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force;" ^
  "$src = Join-Path $env:TEMP 'connect-main';" ^
  "Copy-Item -Path (Join-Path $src '*') -Destination '%REPO_DIR%' -Recurse -Force;" ^
  "Remove-Item $zipPath -Force;" ^
  "Remove-Item $src -Recurse -Force;" || exit /b 1
exit /b 0

:resolve_python
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    exit /b 0
)
echo [!] Python 3 is required. Install Python 3.10+ and rerun the installer.
exit /b 1

:create_venv
if not exist "%REPO_DIR%\venv\Scripts\python.exe" (
    echo [*] Creating virtual environment
    call %PYTHON_CMD% -m venv "%REPO_DIR%\venv" || exit /b 1
) else (
    echo [*] Using existing virtual environment
)
set "VENV_PYTHON=%REPO_DIR%\venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo [!] Virtual environment creation failed.
    exit /b 1
)
exit /b 0

:install_requirements
echo [*] Installing Python dependencies
"%VENV_PYTHON%" -m pip install --upgrade pip || exit /b 1
"%VENV_PYTHON%" -m pip install -r "%REPO_DIR%\requirements.txt" || exit /b 1
exit /b 0

:ensure_env
exit /b 0

:ensure_data_dir
echo [*] Preparing local data directory
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" || exit /b 1
type nul > "%DATA_DIR%\.keep"
exit /b 0

:install_launcher
set "BIN_DIR=%USERPROFILE%\connect-bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%" || exit /b 1
set "LAUNCHER=%BIN_DIR%\connect.cmd"

(
echo @echo off
echo setlocal
echo set "REPO_DIR=%REPO_DIR%"
echo set "VENV_PYTHON=%%REPO_DIR%%\venv\Scripts\python.exe"
echo if exist "%%VENV_PYTHON%%" ^(
echo     "%%VENV_PYTHON%%" "%%REPO_DIR%%\ai_assistant.py" %%*
echo ^) else if exist "%%LocalAppData%%\Programs\Python\Launcher\py.exe" ^(
echo     py -3 "%%REPO_DIR%%\ai_assistant.py" %%*
echo ^) else ^(
echo     python "%%REPO_DIR%%\ai_assistant.py" %%*
echo ^)
echo endlocal
) > "%LAUNCHER%"

echo [*] Installed launcher at "%LAUNCHER%"

echo %PATH% | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    setx PATH "%PATH%;%BIN_DIR%" >nul
    echo [*] Added "%BIN_DIR%" to your user PATH
    echo [*] Open a new terminal before running connect
) else (
    echo [*] "%BIN_DIR%" is already in PATH
)
exit /b 0

:print_next_steps
echo.
echo ========================================
echo   CONNECT INSTALL COMPLETE
echo ========================================
echo Repo: %REPO_DIR%
echo Launcher: %USERPROFILE%\connect-bin\connect.cmd
echo.
echo Next steps:
echo   1. Run: connect
echo   2. Complete the first-run setup wizard
echo   3. Open a new terminal if PATH was updated
echo   4. Config will be saved to %USERPROFILE%\.connectai\config.json
echo.
exit /b 0
