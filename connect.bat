@echo off
setlocal
set "SCRIPT=%~dp0ai_assistant.py"
where python >nul 2>nul
if %errorlevel%==0 (
    python "%SCRIPT%" %*
) else (
    py -3 "%SCRIPT%" %*
)
endlocal
