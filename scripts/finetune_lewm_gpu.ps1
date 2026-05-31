# Fine-tune LeWM on GPU (Python 3.11 + CUDA PyTorch)
# Main .venv is Python 3.14 (sim/jsbsim); CUDA torch requires .venv311.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".venv311\Scripts\Activate.ps1")) {
    Write-Host "Creating .venv311 with Python 3.11..."
    $py311 = "C:\Users\mysph\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe"
    if (-not (Test-Path $py311)) {
        Write-Error "Python 3.11 not found. Install via: uv python install 3.11"
    }
    & $py311 -m venv .venv311
    .\.venv311\Scripts\Activate.ps1
    pip install torch --index-url https://download.pytorch.org/whl/cu124
    pip install -r requirements-lewm-gpu.txt
    pip install -e packages/skymind-data -e packages/skymind-core
} else {
    .\.venv311\Scripts\Activate.ps1
}

python scripts/finetune_lewm.py --device cuda @args
python scripts/eval_mse.py --device cuda @args
