$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

Write-Host ""
Write-Host "MT5 Trading System - Windows install" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11 or 3.12 first, then run install.bat again."
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv $VenvDir
}

Write-Host "Upgrading pip..."
& $PythonExe -m pip install --upgrade pip

Write-Host "Installing backend dependencies..."
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")

New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "logs") | Out-Null

$EnvFile = Join-Path $BackendDir ".env"
$ExampleEnv = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $ExampleEnv $EnvFile
    Write-Host ""
    Write-Host "Created backend\.env from backend\.env.example." -ForegroundColor Yellow
    Write-Host "Edit backend\.env before starting if you need a specific MT5 server/account."
} else {
    Write-Host "backend\.env already exists. Keeping it unchanged."
}

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "1. Install and open MetaTrader 5 on this computer."
Write-Host "2. Log in to the MT5 account in the MT5 Terminal."
Write-Host "3. Run start.bat."
