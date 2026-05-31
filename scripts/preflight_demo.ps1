# SkyMind demo preflight checks (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "SkyMind Demo Preflight" -ForegroundColor Cyan

# Python venv
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Warning "Main .venv not found — run setup from README"
} else {
    Write-Host "[OK] .venv present"
}

# OpenRouter key
if (Test-Path ".env") {
    Write-Host "[OK] .env file present"
} else {
    Write-Warning ".env missing — copy .env.example and set OPENROUTER_API_KEY"
}

# Packages
$packages = @(
    "packages/skymind-core",
    "packages/skymind-sim",
    "packages/skymind-data",
    "packages/skymind-llm"
)
foreach ($p in $packages) {
    if (Test-Path $p) { Write-Host "[OK] $p" } else { Write-Error "Missing $p" }
}

# Checkpoint (optional for mock planner)
if (Test-Path "checkpoints/lewm_flight_v1.pt") {
    Write-Host "[OK] LeWM checkpoint"
} else {
    Write-Warning "LeWM checkpoint missing — use: python scripts/run_demo.py --mock-planner"
}

Write-Host "`nPreflight complete. Start demo:" -ForegroundColor Green
Write-Host "  python scripts/run_demo.py"
Write-Host "  cd apps/dashboard && npm run dev"
