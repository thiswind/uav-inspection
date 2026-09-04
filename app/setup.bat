@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    py -3 deploy.py install %*
) else (
    python deploy.py install %*
)
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo [ERROR] Installation failed. See the message above.
pause
exit /b %RESULT%
