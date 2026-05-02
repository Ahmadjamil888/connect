@echo off
setlocal
set "IMOS_DIR=%~dp0"
if "%IMOS_DIR:~-1%"=="\" set "IMOS_DIR=%IMOS_DIR:~0,-1%"
set "VENV_PY=%IMOS_DIR%\venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" -m imos.cli %*
) else (
    python -m imos.cli %*
)
