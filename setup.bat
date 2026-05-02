@echo off
echo ========================================
echo  AI ASSISTANT - Setup
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo [*] Python found
echo.

REM Install dependencies
echo [*] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [*] Installing Playwright Chromium...
playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright Chromium
    pause
    exit /b 1
)

echo [*] Creating IMOS home...
if not exist "%USERPROFILE%\.imos" mkdir "%USERPROFILE%\.imos"

echo [*] Generating default IMOS config...
python -c "from imos.config import ensure_default_files; ensure_default_files()"

set /p IMOS_MCP=Configure Cursor and Windsurf MCP now? [y/N]: 
if /I "%IMOS_MCP%"=="Y" (
    python -m imos.cli mcp install
)

echo [*] Installing global CONNECT command...
call install_connect_command.bat
if errorlevel 1 (
    echo [ERROR] Failed to install CONNECT command
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Verify your .env file contains the provider and adapter credentials you need
echo.
echo 2. Open a new terminal and run:
echo    connect
echo    imos status
echo.
echo ========================================

pause
