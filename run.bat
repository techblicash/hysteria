@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found. Please install Python 3.11+ and make sure python.exe is in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [INFO] Starting Proxy GUI Client...
".venv\Scripts\python.exe" -m proxy_gui_client.main
set APP_EXIT=%ERRORLEVEL%

echo.
echo [INFO] Proxy GUI Client exited with code %APP_EXIT%.
pause
exit /b %APP_EXIT%

