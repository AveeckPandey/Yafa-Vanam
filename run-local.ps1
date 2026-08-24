# YAFA VANAM local development launcher.
# Loads the repository-root .env into process environment (nothing auto-loads
# it: Go reads os.Getenv only, Next.js only reads apps/web/.env*) and starts
# all three services:
#   FastAPI recommendation-engine  -> http://localhost:8000
#   Go commerce API                -> http://localhost:4000
#   Next.js storefront             -> http://localhost:3000
#
# Usage:  powershell -File run-local.ps1 [-SkipBuild]
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# --- load root .env -----------------------------------------------------------
Get-Content (Join-Path $root '.env') | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $name, $value = $line -split '=', 2
    if ($name) { [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process') }
}

# Server-side proxies read ADVISOR_URL; .env carries the NEXT_PUBLIC_ spelling.
if (-not $env:ADVISOR_URL -and $env:NEXT_PUBLIC_ADVISOR_URL) {
    $env:ADVISOR_URL = $env:NEXT_PUBLIC_ADVISOR_URL
}
if (-not $env:WHISPER_ENABLED -and $env:WHISPER_SERVICE_URL) {
    Write-Warning 'WHISPER_SERVICE_URL points to an external service; built-in Whisper stays OFF unless WHISPER_ENABLED=true.'
}

$processes = @()

try {
    # --- FastAPI recommendation-engine :8000 ---------------------------------
    Write-Host '[1/3] starting recommendation-engine on :8000' -ForegroundColor Cyan
    $processes += Start-Process python -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000' `
        -WorkingDirectory (Join-Path $root 'services/recommendation-engine') `
        -PassThru -WindowStyle Minimized

    # --- Go commerce API :4000 ------------------------------------------------
    Write-Host '[2/3] starting Go API on :4000' -ForegroundColor Cyan
    if ($env:DATABASE_URL -and $env:REDIS_URL) {
        Write-Host '      DATABASE_URL + REDIS_URL present -> persistent mode'
    } else {
        Write-Host '      no DATABASE_URL/REDIS_URL -> ephemeral in-memory mode'
    }
    $processes += Start-Process go -ArgumentList 'run', './cmd/api' `
        -WorkingDirectory (Join-Path $root 'apps/api') `
        -PassThru -WindowStyle Minimized

    # --- Next.js storefront :3000 --------------------------------------------
    Write-Host '[3/3] starting Next.js on :3000' -ForegroundColor Cyan
    if (-not $SkipBuild) {
        Push-Location (Join-Path $root 'apps/web')
        npm run build 2>&1 | Out-Null
        Pop-Location
    }
    $processes += Start-Process cmd -ArgumentList '/c', 'npx next start -p 3000' `
        -WorkingDirectory (Join-Path $root 'apps/web') `
        -PassThru -WindowStyle Minimized

    # --- health checks ---------------------------------------------------------
    Write-Host "`nwaiting for services..." -ForegroundColor Yellow
    Start-Sleep -Seconds 12

    foreach ($check in @(
        @{ Name = 'FastAPI   :8000'; Url = 'http://127.0.0.1:8000/health' },
        @{ Name = 'Go API    :4000'; Url = 'http://127.0.0.1:4000/health' },
        @{ Name = 'Next.js   :3000'; Url = 'http://127.0.0.1:3000/shop' }
    )) {
        try {
            $r = Invoke-WebRequest $check.Url -TimeoutSec 15 -UseBasicParsing
            Write-Host ("  {0}  OK ({1})" -f $check.Name, $r.StatusCode) -ForegroundColor Green
        } catch {
            Write-Host ("  {0}  FAILED: {1}" -f $check.Name, $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
        }
    }

    Write-Host "`nAll services launched. Storefront: http://localhost:3000" -ForegroundColor Green
    Write-Host 'Press Enter here to stop every service...'
    Read-Host | Out-Null
}
finally {
    foreach ($p in $processes) {
        if ($p -and -not $p.HasExited) {
            # Kill the whole child tree (go run spawns a child binary).
            & taskkill "/PID" $p.Id "/T" "/F" 2>$null | Out-Null
        }
    }
    Write-Host 'services stopped.' -ForegroundColor Yellow
}
