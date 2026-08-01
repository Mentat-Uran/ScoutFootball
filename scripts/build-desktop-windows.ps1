# ScoutFootball Desktop — Windows Build Script
# Builds the Electron app with embedded Python backend for Windows x64.
#
# Usage:
#   .\scripts\build-desktop-windows.ps1              # Full build
#   .\scripts\build-desktop-windows.ps1 -BackendOnly  # Build Python backend only
#   .\scripts\build-desktop-windows.ps1 -SkipNpm      # Skip npm install (use existing node_modules)

param(
    [switch]$BackendOnly = $false,
    [switch]$SkipNpm = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$DesktopDir = Join-Path $ProjectDir "desktop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  ScoutFootball Desktop Build (Windows)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Build Python backend ───────────────────────────────
Write-Host "[1/4] Building Python backend with PyInstaller..." -ForegroundColor Yellow

# Install Python dependencies
Push-Location $ProjectDir
uv sync --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: uv sync failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Install PyInstaller if not present
uv run pip install pyinstaller --quiet

# Build the backend executable
Push-Location $DesktopDir
uv run python -m PyInstaller `
    --clean `
    --noconfirm `
    --distpath "backend-dist" `
    --workpath "backend-build" `
    "scoutfootball-server.spec"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    Pop-Location
    Pop-Location
    exit 1
}

Pop-Location
Write-Host "      Backend built: desktop/backend-dist/scoutfootball-server/"
Write-Host ""

if ($BackendOnly) {
    Write-Host "Backend build complete (-BackendOnly flag). Skipping Electron build." -ForegroundColor Green
    Pop-Location
    exit 0
}

# ── Step 2: Copy frontend files ────────────────────────────────
Write-Host "[2/4] Copying frontend files..." -ForegroundColor Yellow

$FrontendDest = Join-Path $DesktopDir "frontend"
if (Test-Path $FrontendDest) {
    Remove-Item $FrontendDest -Recurse -Force
}
New-Item -ItemType Directory -Path $FrontendDest -Force | Out-Null

$FrontendSrc = Join-Path $ProjectDir "frontend"
$FrontendFiles = @("index.html", "style.css", "app.js", "tactical-board.js", "tactical-renderer.js", "config.js", "user-guide.html")
foreach ($file in $FrontendFiles) {
    $src = Join-Path $FrontendSrc $file
    if (Test-Path $src) {
        Copy-Item $src $FrontendDest
    } else {
        Write-Host "      WARNING: $file not found in frontend/" -ForegroundColor DarkYellow
    }
}

# Copy frontend static data for offline fallback
$FrontendDataSrc = Join-Path $FrontendSrc "data"
$FrontendDataDest = Join-Path $FrontendDest "data"
if (Test-Path $FrontendDataSrc) {
    Copy-Item -Path $FrontendDataSrc -Destination $FrontendDataDest -Recurse -Force
    Write-Host "      Frontend data copied."
} else {
    Write-Host "      WARNING: frontend/data/ not found, static fallback will be unavailable" -ForegroundColor DarkYellow
}

Write-Host "      Frontend copied."

# Copy app icon to build/
$BuildDir = Join-Path $DesktopDir "build"
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
$IconPng = Join-Path $DesktopDir "icon.png"
if (Test-Path $IconPng) {
    Copy-Item $IconPng (Join-Path $BuildDir "icon.png") -Force
    Write-Host "      App icon copied to build/"
}

# Generate icon.ico for Windows if not present
$IconIco = Join-Path $BuildDir "icon.ico"
if (-not (Test-Path $IconIco)) {
    Write-Host "      NOTE: icon.ico not found in build/. NSIS will use default icon." -ForegroundColor DarkYellow
    Write-Host "      To set a custom icon, place icon.ico in desktop/build/" -ForegroundColor DarkYellow
}

Write-Host ""

# ── Step 3: Verify backend executable ──────────────────────────
Write-Host "[3/4] Verifying backend executable..." -ForegroundColor Yellow

$BackendExe = Join-Path (Join-Path (Join-Path $DesktopDir "backend-dist") "scoutfootball-server") "scoutfootball-server.exe"
if (Test-Path $BackendExe) {
    $size = (Get-Item $BackendExe).Length / 1MB
    Write-Host "      Backend executable: $([math]::Round($size, 1)) MB"
} else {
    Write-Host "      WARNING: Backend executable not found at expected path" -ForegroundColor DarkYellow
}
Write-Host ""

# ── Step 4: Install Electron dependencies and build ────────────
Write-Host "[4/4] Building Electron app for Windows x64..." -ForegroundColor Yellow

Push-Location $DesktopDir

if (-not $SkipNpm -and -not (Test-Path "node_modules")) {
    Write-Host "      Installing Node dependencies..."
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: npm install failed" -ForegroundColor Red
        Pop-Location
        Pop-Location
        exit 1
    }
}

npx electron-builder --win --x64 -p never
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: electron-builder failed" -ForegroundColor Red
    Pop-Location
    Pop-Location
    exit 1
}

Pop-Location
Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Windows build complete!" -ForegroundColor Green
Write-Host "  Output: desktop/dist/" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# List output files
$DistDir = Join-Path $DesktopDir "dist"
if (Test-Path $DistDir) {
    Get-ChildItem $DistDir -Recurse -Include "*.exe","*.msi","*.zip" | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 1)
        Write-Host "  $($_.Name) ($size MB)"
    }
}
