# LearnOS FFmpeg Provisioner
# Automatically downloads and extracts a static build of FFmpeg for Windows

$ErrorActionPreference = "Stop"

$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptsDir
$binDir = Join-Path $backendDir "bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
$ffprobeExe = Join-Path $binDir "ffprobe.exe"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " LearnOS Self-Healing FFmpeg Provisioner" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
    Write-Host "FFmpeg and FFprobe are already installed locally in: $binDir" -ForegroundColor Green
    Exit 0
}

Write-Host "FFmpeg binaries missing in $binDir." -ForegroundColor Yellow
Write-Host "Initiating local self-healing setup..." -ForegroundColor Yellow

if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    Write-Host "Created local bin directory: $binDir" -ForegroundColor Gray
}

# Use a highly-stable GyanD GitHub release for fast download speeds
$url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
$zipPath = Join-Path $binDir "ffmpeg.zip"
$extractPath = Join-Path $binDir "extracted"

Write-Host "Downloading FFmpeg static essentials build from:" -ForegroundColor Gray
Write-Host $url -ForegroundColor DarkCyan

# Silence progress bar to make Invoke-WebRequest significantly faster
$oldProgressPreference = $ProgressPreference
$ProgressPreference = 'SilentlyContinue'

try {
    Write-Host "Downloading archive..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $url -OutFile $zipPath
    Write-Host "Download complete. Extracting files (this may take a few moments)..." -ForegroundColor Gray
    
    if (Test-Path $extractPath) {
        Remove-Item -Recurse -Force $extractPath
    }
    
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
    
    Write-Host "Locating executables and copying to bin..." -ForegroundColor Gray
    Get-ChildItem -Path $extractPath -Filter "*.exe" -Recurse | ForEach-Object {
        $destPath = Join-Path $binDir $_.Name
        Copy-Item -Path $_.FullName -Destination $destPath -Force
        Write-Host "Provisioned: $_.Name" -ForegroundColor Gray
    }
    
    Write-Host "Cleaning up temporary files..." -ForegroundColor Gray
    Remove-Item -Recurse -Force $extractPath
    Remove-Item -Force $zipPath
    
    if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
        Write-Host "FFmpeg and FFprobe successfully provisioned and verified!" -ForegroundColor Green
    } else {
        throw "Verification failed: Executables were not successfully extracted."
    }
}
catch {
    Write-Host "Failed to provision FFmpeg automatically: $_" -ForegroundColor Red
    Write-Host "Please ensure your internet connection is active, or manually download ffmpeg.exe and ffprobe.exe and place them inside: $binDir" -ForegroundColor Red
    
    # Clean up anyway
    if (Test-Path $extractPath) { Remove-Item -Recurse -Force $extractPath }
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    Exit 1
}
finally {
    $ProgressPreference = $oldProgressPreference
}

Write-Host "==========================================" -ForegroundColor Cyan
