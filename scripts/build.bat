@echo off
setlocal

cd /d "%~dp0\.."

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

echo [INFO] Building ProxyGUI...
".venv\Scripts\python.exe" -m PyInstaller proxy_gui_client/main.py ^
  --name ProxyGUI ^
  --noconsole ^
  --clean ^
  --noconfirm ^
  --add-data "proxy_gui_client/data;data" ^
  --add-data "cores;cores" ^
  --add-data "version.txt;."
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [INFO] Copying writable runtime files next to ProxyGUI.exe...
if not exist "dist\ProxyGUI\data" mkdir "dist\ProxyGUI\data"
xcopy /E /I /Y "proxy_gui_client\data" "dist\ProxyGUI\data" >nul
if exist "cores" (
    if not exist "dist\ProxyGUI\cores" mkdir "dist\ProxyGUI\cores"
    xcopy /E /I /Y "cores" "dist\ProxyGUI\cores" >nul
)
copy /Y "version.txt" "dist\ProxyGUI\version.txt" >nul

echo [INFO] Writing portable default settings...
".venv\Scripts\python.exe" -c "import json; from pathlib import Path; from proxy_gui_client.core.models import DEFAULT_SETTINGS; p=Path('dist/ProxyGUI/data'); p.mkdir(parents=True, exist_ok=True); (p/'settings.json').write_text(json.dumps(DEFAULT_SETTINGS, indent=2, ensure_ascii=False), encoding='utf-8'); (p/'nodes.json').write_text('[]', encoding='utf-8')"
if errorlevel 1 (
    echo [ERROR] Failed to write portable default settings.
    pause
    exit /b 1
)

echo.
echo [OK] Build completed: dist\ProxyGUI\ProxyGUI.exe
pause
exit /b 0
