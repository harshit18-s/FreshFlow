<#
.SYNOPSIS
    FreshFlow AI - First-time bootstrap (Windows / PowerShell)

.DESCRIPTION
    Sets up the development environment:
      1. Copies .env.example -> .env
      2. Creates data & project directories
      3. Installs Python dependencies
      4. Starts core Docker services
      5. Waits for service health checks

.EXAMPLE
    .\scripts\bootstrap.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipDocker,
    [switch]$SkipPython
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FreshFlow AI - Bootstrap Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. Environment file ---------------------------------------------
Write-Host "> Step 1/5 - Environment file" -ForegroundColor Yellow

$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "  [OK] Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "  * .env already exists - skipping" -ForegroundColor DarkGray
}

# ---------- 2. Create directories --------------------------------------------
Write-Host "> Step 2/5 - Creating directories" -ForegroundColor Yellow

$directories = @(
    "data/raw",
    "data/bronze",
    "data/silver",
    "data/gold",
    "data/sample",
    "data/quarantine",
    "dags",
    "plugins",
    "logs",
    "models",
    "reports",
    "config/prometheus",
    "tests/unit",
    "tests/integration",
    "tests/data",
    "tests/ml",
    "tests/e2e"
)

foreach ($dir in $directories) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-Host "  [OK] All directories created" -ForegroundColor Green

# ---------- 3. Python dependencies -------------------------------------------
if (-not $SkipPython) {
    Write-Host "> Step 3/5 - Installing Python dependencies" -ForegroundColor Yellow
    Push-Location $ProjectRoot
    try {
        pip install -r requirements/dev.txt
        Write-Host "  [OK] Python dependencies installed" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to install Python dependencies: $_" -ForegroundColor Red
        Write-Host "    Try running manually: pip install -r requirements/dev.txt" -ForegroundColor DarkGray
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "> Step 3/5 - Skipping Python install (--SkipPython)" -ForegroundColor DarkGray
}

# ---------- 4. Docker services -----------------------------------------------
if (-not $SkipDocker) {
    Write-Host "> Step 4/5 - Starting core Docker services" -ForegroundColor Yellow
    Push-Location $ProjectRoot
    try {
        docker compose --profile core up -d
        Write-Host "  [OK] Docker services started" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to start Docker services: $_" -ForegroundColor Red
        Write-Host "    Ensure Docker Desktop is running." -ForegroundColor DarkGray
    }
    finally {
        Pop-Location
    }

    # ---------- 5. Wait for health checks ------------------------------------
    Write-Host "> Step 5/5 - Waiting for services to become healthy" -ForegroundColor Yellow

    $services = @(
        @{ Name = "PostgreSQL"; Url = $null;                         Container = "freshflow-postgres" },
        @{ Name = "MinIO";      Url = "http://localhost:9000/minio/health/live"; Container = $null },
        @{ Name = "Airflow";    Url = "http://localhost:8080/health"; Container = $null },
        @{ Name = "MLflow";     Url = "http://localhost:5000/health"; Container = $null }
    )

    $maxAttempts = 30
    $sleepSeconds = 5

    foreach ($svc in $services) {
        $healthy = $false
        for ($i = 1; $i -le $maxAttempts; $i++) {
            try {
                if ($svc.Url) {
                    $response = Invoke-WebRequest -Uri $svc.Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                    if ($response.StatusCode -eq 200) { $healthy = $true; break }
                } else {
                    $status = docker inspect --format='{{.State.Health.Status}}' $svc.Container 2>$null
                    if ($status -eq "healthy") { $healthy = $true; break }
                }
            } catch {
                # Service not ready yet
            }
            Start-Sleep -Seconds $sleepSeconds
        }

        if ($healthy) {
            Write-Host "  [OK] $($svc.Name) is healthy" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] $($svc.Name) did not become healthy in time" -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "> Step 4/5 - Skipping Docker (--SkipDocker)" -ForegroundColor DarkGray
    Write-Host "> Step 5/5 - Skipping health checks" -ForegroundColor DarkGray
}

# ---------- Summary ----------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  [OK] Bootstrap Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Service URLs:" -ForegroundColor White
Write-Host "    Airflow      -> http://localhost:8080   (admin/admin)" -ForegroundColor Gray
Write-Host "    MLflow       -> http://localhost:5000" -ForegroundColor Gray
Write-Host "    FastAPI      -> http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "    MinIO Console-> http://localhost:9001   (freshflow_minio/freshflow_minio_secret)" -ForegroundColor Gray
Write-Host "    PostgreSQL   -> localhost:5432          (freshflow_admin/freshflow_dev_2026)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    make download-data    # Download the dataset" -ForegroundColor Gray
Write-Host "    make ingest           # Run batch ingestion" -ForegroundColor Gray
Write-Host "    make train            # Train ML models" -ForegroundColor Gray
Write-Host "    make demo             # Full pipeline" -ForegroundColor Gray
Write-Host ""
