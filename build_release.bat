@echo off
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0build_release.py"
) else (
    python "%~dp0build_release.py"
)
endlocal
