$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $ProjectRoot "release"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$PackageName = "mt5-trading-system-$Stamp"
$StageDir = Join-Path $ReleaseDir $PackageName
$ZipPath = Join-Path $ReleaseDir "$PackageName.zip"

Write-Host ""
Write-Host "MT5 Trading System - Build release package" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

if (Test-Path $StageDir) {
    Remove-Item $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

$ExcludeDirs = @(
    "\.claude",
    "\release",
    "\backend\.venv",
    "\backend\__pycache__",
    "\backend\app\__pycache__",
    "\backend\app\routers\__pycache__",
    "\backend\app\services\__pycache__"
)

$ExcludeFiles = @(
    "\backend\.env",
    "\backend\data\trading.db",
    "\backend\data\trading.db-wal",
    "\backend\data\trading.db-shm",
    "\backend\logs\app.log",
    "\backend\logs\server.out.log",
    "\backend\logs\server.err.log"
)

function Test-IsExcluded([string]$FullName) {
    $relative = $FullName.Substring($ProjectRoot.Length)
    foreach ($dir in $ExcludeDirs) {
        if ($relative.StartsWith($dir, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    foreach ($file in $ExcludeFiles) {
        if ($relative.Equals($file, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

Get-ChildItem -Path $ProjectRoot -Recurse -Force | ForEach-Object {
    if (Test-IsExcluded $_.FullName) { return }
    $relative = $_.FullName.Substring($ProjectRoot.Length).TrimStart("\")
    if (-not $relative) { return }
    $target = Join-Path $StageDir $relative

    if ($_.PSIsContainer) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "backend\data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "backend\logs") | Out-Null

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipPath -Force

Write-Host "Package created:" -ForegroundColor Green
Write-Host $ZipPath
Write-Host ""
Write-Host "Notes:"
Write-Host "- backend\.env is not included."
Write-Host "- backend\data\trading.db is not included by default."
Write-Host "- On the target computer, unzip, run install.bat, edit backend\.env if needed, then run start.bat."
