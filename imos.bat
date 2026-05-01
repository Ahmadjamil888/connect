@echo off
:: IMOS launcher — always uses absolute path to imos_cli.py
set "IMOS_DIR=C:\Users\Admin\Desktop\connect"
set "VENV_PY=%IMOS_DIR%\venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%IMOS_DIR%\imos_cli.py" %*
) else (
    python "%IMOS_DIR%\imos_cli.py" %*
)
