@echo off
setlocal

cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run run.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" scripts\check.py
set CHECK_EXIT=%ERRORLEVEL%

echo.
echo [INFO] Developer check exited with code %CHECK_EXIT%.
pause
exit /b %CHECK_EXIT%

