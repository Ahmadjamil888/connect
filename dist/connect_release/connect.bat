@echo off
setlocal
set "SCRIPT=%~dp0ai_assistant.py"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%SCRIPT%" %*
) else (
    python "%SCRIPT%" %*
)
endlocal
