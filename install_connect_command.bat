@echo off
setlocal

set "REPO_DIR=%~dp0"
if "%REPO_DIR:~-1%"=="\" set "REPO_DIR=%REPO_DIR:~0,-1%"

set "BIN_DIR=%USERPROFILE%\connect-bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

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
) > "%BIN_DIR%\connect.cmd"

echo [*] Installed launcher: "%BIN_DIR%\connect.cmd"

echo %PATH% | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    setx PATH "%PATH%;%BIN_DIR%" >nul
    echo [*] Added "%BIN_DIR%" to your user PATH
    echo [*] Open a new terminal, then run: connect --doctor
) else (
    echo [*] "%BIN_DIR%" is already in PATH
    echo [*] You can run: connect --doctor
)

endlocal
