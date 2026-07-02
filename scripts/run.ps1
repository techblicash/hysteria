param(
    [switch]$Check,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

function Fail($Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Fail "Python was not found. Please install Python 3.11+ and make sure python.exe is in PATH."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[INFO] Creating virtual environment..."
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to create virtual environment."
    }
}

if ($NoInstall) {
    Write-Host "[INFO] Skipping dependency installation because -NoInstall was provided."
} else {
    Write-Host "[INFO] Installing/updating dependencies..."
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to install dependencies."
    }
}

if ($Check) {
    Write-Host "[INFO] Running project checks..."
    & $VenvPython scripts/check.py
    if ($LASTEXITCODE -ne 0) {
        Fail "Project checks failed."
    }
}

Write-Host "[INFO] Starting Proxy GUI Client..."
& $VenvPython -m proxy_gui_client.main
exit $LASTEXITCODE
