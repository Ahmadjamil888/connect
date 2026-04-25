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
echo 1. Verify your .env file contains GROQ_API_KEY
echo.
echo 2. Open a new terminal and run:
echo    connect
echo.
echo ========================================

pause
