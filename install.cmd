@echo off
setlocal EnableExtensions DisableDelayedExpansion
title IMOS Installer

set "REPO_URL=https://github.com/Ahmadjamil888/connect.git"
set "INSTALL_DIR=%USERPROFILE%\imos"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo.
echo  ========================================================
echo    IMOS Installer
echo    One command, one runtime, one setup flow
echo    Guided install with loader and staged verification
echo  ========================================================
echo.

call :step 1/7 Resolving repository source
if exist "%SCRIPT_DIR%\setup.py" if exist "%SCRIPT_DIR%\imos" (
    set "REPO_DIR=%SCRIPT_DIR%"
    call :ok Using current repository
    goto :resolve_python
)

set "REPO_DIR=%INSTALL_DIR%"
if exist "%REPO_DIR%\setup.py" if exist "%REPO_DIR%\imos" (
    where git >nul 2>nul
    if %errorlevel%==0 (
        call :progress Updating repository git -C "%REPO_DIR%" pull --ff-only
    ) else (
        call :ok Using existing installation
    )
    goto :resolve_python
)

if exist "%REPO_DIR%" rmdir /s /q "%REPO_DIR%"
mkdir "%REPO_DIR%" >nul 2>nul
where git >nul 2>nul
if %errorlevel%==0 (
    call :progress Cloning repository git clone "%REPO_URL%" "%REPO_DIR%"
) else (
    call :progress Downloading repository archive powershell -NoProfile -ExecutionPolicy Bypass -Command "$z='%TEMP%\imos-main.zip'; Invoke-WebRequest 'https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.zip' -OutFile $z; Expand-Archive $z '%TEMP%\imos-src' -Force; Copy-Item '%TEMP%\imos-src\connect-main\*' '%REPO_DIR%' -Recurse -Force; Remove-Item $z,'%TEMP%\imos-src' -Recurse -Force"
)

:resolve_python
call :step 2/7 Checking Python runtime
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
    goto :create_venv
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    goto :create_venv
)
echo [!] Python 3.10+ is required
goto :error

:create_venv
call :ok Python found
call :step 3/7 Preparing virtual environment
if not exist "%REPO_DIR%\venv\Scripts\python.exe" (
    call :progress Creating virtual environment %PY% -m venv "%REPO_DIR%\venv"
) else (
    call :ok Using existing virtual environment
)
set "VENV=%REPO_DIR%\venv\Scripts\python.exe"
if not exist "%VENV%" goto :error

call :step 4/7 Installing IMOS runtime
call :progress Upgrading pip "%VENV%" -m pip install --upgrade pip
call :progress Installing project dependencies "%VENV%" -m pip install -r "%REPO_DIR%\requirements.txt"
call :progress Installing IMOS command "%VENV%" -m pip install -e "%REPO_DIR%"

call :step 5/7 Preparing local configuration
if not exist "%REPO_DIR%\.env" (
    if exist "%REPO_DIR%\.env.example" (
        copy "%REPO_DIR%\.env.example" "%REPO_DIR%\.env" >nul
        call :ok Created .env from template
    ) else (
        type nul > "%REPO_DIR%\.env"
        call :ok Created empty .env
    )
) else (
    call :ok Existing .env preserved
)
if not exist "%USERPROFILE%\.imos" mkdir "%USERPROFILE%\.imos" >nul 2>nul
call :progress Initializing IMOS home "%VENV%" -c "from imos.config import ensure_default_files; ensure_default_files()"

call :step 6/7 Installing global launcher
set "BIN_DIR=%USERPROFILE%\imos-bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%" >nul 2>nul
(
echo @echo off
echo "%VENV%" -m imos.cli %%*
) > "%BIN_DIR%\imos.cmd"
call :ok Installed launcher at %BIN_DIR%\imos.cmd
echo %PATH% | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    setx PATH "%PATH%;%BIN_DIR%" >nul
    call :ok Added launcher directory to PATH
) else (
    call :ok Launcher directory already on PATH
)

call :step 7/7 Running guided setup checks
call :progress Installing editor bridge config "%VENV%" -m imos.cli mcp install
call :progress Installing wake listener "%VENV%" -m imos.cli wake install
call :progress Checking runtime status "%VENV%" -m imos.cli status

echo.
echo  ========================================================
echo    IMOS is installed
echo  ========================================================
echo.
echo    Start IMOS from any terminal with: imos
echo    Open the dashboard with:           imos dashboard
echo    Open beast mode shell with:        imos shell --beast
echo    Run one prompt with:               imos run "create a landing page"
echo.
exit /b 0

:step
echo [%~1] %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
exit /b 0

:ok
echo       OK - %*
exit /b 0

:progress
setlocal
set "LABEL=%~1"
shift
echo       ... %LABEL%
%* >nul 2>nul
if errorlevel 1 (
    endlocal
    echo [!] %LABEL% failed
    goto :error
)
endlocal
echo       OK - %LABEL%
exit /b 0

:error
echo.
echo [!] Installation failed. Review the message above.
exit /b 1
