@echo off
setlocal
set "REPO_DIR=%~dp0"
if "%REPO_DIR:~-1%"=="\" set "REPO_DIR=%REPO_DIR:~0,-1%"
set "SCRIPT=%REPO_DIR%\ai_assistant.py"
set "VENV_PYTHON=%REPO_DIR%\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" "%SCRIPT%" %*
) else if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" (
    py -3 "%SCRIPT%" %*
) else (
    python "%SCRIPT%" %*
)
endlocal
