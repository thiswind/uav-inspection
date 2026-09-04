@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-deploy\Scripts\python.exe" (
    echo [ERROR] Please run setup.bat first.
    pause
    exit /b 1
)
".venv-deploy\Scripts\python.exe" deploy.py dev %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
