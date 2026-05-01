@echo off
setlocal EnableExtensions DisableDelayedExpansion
title IMOS Installer

set "REPO_URL=https://github.com/Ahmadjamil888/connect.git"
set "INSTALL_DIR=%USERPROFILE%\imos"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo.
echo  ========================================================
echo    IMOS -- Intelligent Machine Operating System
echo    Installer
echo  ========================================================
echo.

:: ── Step 1: Resolve repo directory ──────────────────────────────────────────
if exist "%SCRIPT_DIR%\imos_cli.py" (
    set "REPO_DIR=%SCRIPT_DIR%"
    echo [1/6] Using existing repo at %REPO_DIR%
    goto :resolve_python
)

set "REPO_DIR=%INSTALL_DIR%"

if exist "%REPO_DIR%\imos_cli.py" (
    echo [1/6] Updating existing install at %REPO_DIR%
    where git >nul 2>nul && git -C "%REPO_DIR%" pull --ff-only
    goto :resolve_python
)

where git >nul 2>nul
if %errorlevel%==0 (
    echo [1/6] Cloning IMOS into %REPO_DIR%
    git clone "%REPO_URL%" "%REPO_DIR%" || goto :error
) else (
    echo [1/6] Downloading IMOS archive...
    if not exist "%REPO_DIR%" mkdir "%REPO_DIR%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$z='%TEMP%\imos.zip';" ^
      "Invoke-WebRequest 'https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.zip' -OutFile $z;" ^
      "Expand-Archive $z '%TEMP%\imos-src' -Force;" ^
      "Copy-Item '%TEMP%\imos-src\connect-main\*' '%REPO_DIR%' -Recurse -Force;" ^
      "Remove-Item $z,'%TEMP%\imos-src' -Recurse -Force" || goto :error
)

:: ── Step 2: Resolve Python ───────────────────────────────────────────────────
:resolve_python
echo [2/6] Checking Python...
where py >nul 2>nul && set "PY=py -3" && goto :create_venv
where python >nul 2>nul && set "PY=python" && goto :create_venv
echo [!] Python 3.10+ is required. Download from https://python.org
goto :error

:: ── Step 3: Create venv ──────────────────────────────────────────────────────
:create_venv
echo [3/6] Creating virtual environment...
if not exist "%REPO_DIR%\venv\Scripts\python.exe" (
    %PY% -m venv "%REPO_DIR%\venv" || goto :error
)
set "VENV=%REPO_DIR%\venv\Scripts\python.exe"

:: ── Step 4: Install requirements ─────────────────────────────────────────────
echo [4/6] Installing requirements...
"%VENV%" -m pip install --upgrade pip -q
"%VENV%" -m pip install -r "%REPO_DIR%\requirements.txt" -q || goto :error
echo       Done.

:: ── Step 5: Copy .env.example to .env ────────────────────────────────────────
echo [5/6] Setting up environment file...
if not exist "%REPO_DIR%\.env" (
    if exist "%REPO_DIR%\.env.example" (
        copy "%REPO_DIR%\.env.example" "%REPO_DIR%\.env" >nul
        echo       Created .env from .env.example
    ) else (
        type nul > "%REPO_DIR%\.env"
        echo       Created empty .env
    )
) else (
    echo       .env already exists, skipping.
)

:: ── Step 6: Install imos command ─────────────────────────────────────────────
echo [6/6] Installing 'imos' command...
set "BIN_DIR=%USERPROFILE%\imos-bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

(
echo @echo off
echo "%VENV%" "%REPO_DIR%\imos_cli.py" %%*
) > "%BIN_DIR%\imos.cmd"

:: Add to PATH if not already there
echo %PATH% | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    setx PATH "%PATH%;%BIN_DIR%" >nul
    echo       Added %BIN_DIR% to PATH
    echo       Open a NEW terminal for PATH to take effect.
) else (
    echo       %BIN_DIR% already in PATH
)

:: Also copy to Python Scripts (usually already on PATH)
if exist "%REPO_DIR%\venv\Scripts\" (
    copy "%REPO_DIR%\imos.bat" "%REPO_DIR%\venv\Scripts\imos.bat" >nul 2>nul
)

echo.
echo  ========================================================
echo    IMOS installed successfully!
echo  ========================================================
echo.
echo    Open a NEW terminal and type:  imos
echo    The setup wizard will run on first launch.
echo.
echo    Repo:      %REPO_DIR%
echo    Dashboard: http://localhost:5000
echo.
pause
exit /b 0

:error
echo.
echo [!] Installation failed. Check the error above.
pause
exit /b 1
