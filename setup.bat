@echo off
setlocal EnableExtensions
echo ========================================
echo  IMOS - Intelligent Machine OS Setup
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

cd /d "%~dp0"
echo [*] Python found
echo.

echo [*] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [*] Installing operator extras...
pip install faster-whisper sounddevice numpy scipy pystray pillow elevenlabs pyttsx3 pyautogui pygetwindow 2>nul

echo [*] Installing Playwright Chromium...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright Chromium
    pause
    exit /b 1
)

echo [*] Bootstrapping IMOS runtime...
python -c "from pathlib import Path; from setup.bootstrap import initialize_imos_runtime, print_bootstrap_summary; s=initialize_imos_runtime(Path('.')); print_bootstrap_summary(s)"
if errorlevel 1 (
    echo [WARN] Bootstrap had issues - continue manually with: python -m setup.bootstrap
)

if not exist ".env" if exist ".env.example" copy ".env.example" ".env" >nul

set /p IMOS_MCP=Configure Cursor / Windsurf MCP now? [y/N]: 
if /I "%IMOS_MCP%"=="Y" python -m imos.cli mcp install

set /p IMOS_WIZARD=Run IMOS first-time setup wizard (models + services)? [Y/n]: 
if /I not "%IMOS_WIZARD%"=="N" (
    python -c "from pathlib import Path; from setup.wizard import run_setup_wizard; run_setup_wizard(Path('.'), Path('.'), forced=True)"
)

if exist install_connect_command.bat (
    echo [*] Installing global connect launcher...
    call install_connect_command.bat
)

echo [*] Installing IMOS background service...
python setup\install_service.py 2>nul

echo.
echo ========================================
echo  IMOS Setup Complete
echo ========================================
echo.
echo   Start operator CLI:     imos
echo   Open dashboard:         imos dashboard  (http://127.0.0.1:7070)
echo   List all services:      imos  then  /services
echo   Add any model:          /model add ^<type^> ^<model-id^> [api_key] [base_url]
echo   Model types:            /model types
echo.
echo ========================================
pause
