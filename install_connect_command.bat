@echo off
setlocal

set "REPO_DIR=%~dp0"
if "%REPO_DIR:~-1%"=="\" set "REPO_DIR=%REPO_DIR:~0,-1%"

set "BIN_DIR=%USERPROFILE%\connect-bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

(
echo @echo off
echo cd /d "%REPO_DIR%"
echo python nexus.py %%*
) > "%BIN_DIR%\connect.cmd"

echo [*] Installed launcher: "%BIN_DIR%\connect.cmd"

echo %PATH% | find /I "%BIN_DIR%" >nul
if errorlevel 1 (
    setx PATH "%PATH%;%BIN_DIR%" >nul
    echo [*] Added "%BIN_DIR%" to your user PATH
    echo [*] Open a new terminal, then run: connect
) else (
    echo [*] "%BIN_DIR%" is already in PATH
    echo [*] You can run: connect
)

endlocal
