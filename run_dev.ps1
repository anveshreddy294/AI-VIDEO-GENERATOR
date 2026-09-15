# LearnOS Monorepo Dev Launcher
# Sets up environment, checks dependencies, and launches both services in parallel

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         LearnOS Dev Server Launcher" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Self-Healing FFmpeg check
$binDir = Join-Path $PSScriptRoot "backend\bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
$ffprobeExe = Join-Path $binDir "ffprobe.exe"

if (!(Test-Path $ffmpegExe) -or !(Test-Path $ffprobeExe)) {
    Write-Host "[1/3] Local FFmpeg executables missing. Provisioning..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "backend\scripts\setup_ffmpeg.ps1")
} else {
    Write-Host "[1/3] FFmpeg binaries verified locally in: $binDir" -ForegroundColor Green
}

# 2. Sync and Install Python dependencies
Write-Host "[2/3] Resolving Python backend dependencies..." -ForegroundColor Cyan
try {
    # Check if pip is available
    python -m pip --version | Out-Null
    # Install dependencies quietly
    python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt") --quiet
    Write-Host "      Python dependencies verified!" -ForegroundColor Green
}
catch {
    Write-Host "Warning: Failed to install Python dependencies automatically: $_" -ForegroundColor Yellow
}

# 3. Sync and Install Frontend Node dependencies
Write-Host "[3/3] Resolving Frontend npm dependencies..." -ForegroundColor Cyan
try {
    Push-Location (Join-Path $PSScriptRoot "frontend")
    # Verify package-lock or run npm install
    if (!(Test-Path "node_modules")) {
        Write-Host "      node_modules missing in frontend. Running npm install (this may take a minute)..." -ForegroundColor Yellow
        npm install --no-audit --no-fund --loglevel=error
    }
    Write-Host "      npm packages verified!" -ForegroundColor Green
    Pop-Location
}
catch {
    Write-Host "Warning: Failed to verify npm dependencies: $_" -ForegroundColor Yellow
    Pop-Location
}

# 4. Spawns servers concurrently in separate PowerShell windows
Write-Host "`nLaunching servers..." -ForegroundColor Cyan
Write-Host "------------------------------------------" -ForegroundColor Gray
Write-Host "  * Starting FastAPI Backend on port 5000..." -ForegroundColor Cyan
Write-Host "  * Starting Vite React Frontend on port 3000..." -ForegroundColor Cyan
Write-Host "------------------------------------------" -ForegroundColor Gray

# Start Backend
Start-Process cmd -ArgumentList "/k title LearnOS-Backend && cd backend && python api.py"
# Start Frontend
Start-Process cmd -ArgumentList "/k title LearnOS-Frontend && cd frontend && npm run dev"

Write-Host "Both servers launched successfully in separate console windows!" -ForegroundColor Green
Write-Host "Press any key to return..." -ForegroundColor Gray
