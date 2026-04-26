@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   AI ASSISTANT - WINDOWS INSTALLER
echo ========================================

:: ---------- Check Git ----------
echo [*] Checking Git...
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Git is not installed.
    echo Please install Git from: https://git-scm.com/download/win
    pause
    exit /b
)

:: ---------- Clone Repo ----------
if exist connect (
    echo [!] Folder 'connect' already exists. Skipping clone.
) else (
    echo [*] Cloning repository...
    git clone https://github.com/Ahmadjamil888/connect
)

cd connect

:: ---------- Check Python ----------
echo [*] Checking Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python is not installed.
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b
)

for /f "tokens=*" %%i in ('python --version') do set PYVER=%%i
echo [✓] %PYVER%

:: ---------- Create Virtual Env ----------
echo [*] Creating virtual environment...
python -m venv venv

:: ---------- Activate ----------
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: ---------- Upgrade pip ----------
echo [*] Upgrading pip...
python -m pip install --upgrade pip

:: ---------- Install Dependencies ----------
echo [*] Installing dependencies...
pip install -r requirements.txt

:: ---------- Setup .env ----------
if not exist .env (
    echo [*] Creating .env file...
    (
        echo AI_PROVIDER=groq
        echo GROQ_API_KEY=
        echo.
        echo ANTHROPIC_API_KEY=
        echo OPENAI_API_KEY=
        echo OPENROUTER_API_KEY=
        echo GOOGLE_GEMINI_API_KEY=
        echo HUGGINGFACE_API_KEY=
        echo.
        echo AI_ASSISTANT_DEBUG=false
    ) > .env
)

:: ---------- Data Directory ----------
set DATA_DIR=%USERPROFILE%\.ai_assistant

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

type nul > "%DATA_DIR%\user_data.json"
type nul > "%DATA_DIR%\history.json"
type nul > "%DATA_DIR%\projects.json"
type nul > "%DATA_DIR%\analytics.json"
type nul > "%DATA_DIR%\credentials.enc.json"

echo [✓] Data directory ready at %DATA_DIR%

:: ---------- Ask API Key ----------
echo.
set /p GROQ_KEY=Enter your GROQ API Key (or press Enter to skip): 

if not "%GROQ_KEY%"=="" (
    powershell -Command "(Get-Content .env) -replace 'GROQ_API_KEY=', 'GROQ_API_KEY=%GROQ_KEY%' | Set-Content .env"
    echo [✓] API key saved
)

:: ---------- Run Assistant ----------
echo.
echo ========================================
echo   STARTING AI ASSISTANT...
echo ========================================
echo.

python ai_assistant.py

pause
