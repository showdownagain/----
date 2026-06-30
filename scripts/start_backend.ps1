$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host ""
Write-Host "MT5 Trading System - Backend" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
    Write-Host "backend\.env was not found. Creating it from backend\.env.example..." -ForegroundColor Yellow
    Copy-Item (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env")
}

New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "logs") | Out-Null

Write-Host "Dashboard: http://127.0.0.1:8000/dashboard"
Write-Host "API docs:  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Keep this window open while using the dashboard." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop."
Write-Host ""

Set-Location $BackendDir
& $PythonExe run.py --host 127.0.0.1 --port 8000
