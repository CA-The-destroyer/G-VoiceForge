param([switch]$SkipModels,[switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" } }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11 with the Python launcher first.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 LTS first.' }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { nvidia-smi } else { Write-Warning 'NVIDIA driver unavailable; inference will use CPU.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { py -3.11 -m venv .venv; Check-Exit }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip; Check-Exit
& $python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128; Check-Exit
& $python -m pip install -r requirements.txt; Check-Exit
if (-not $SkipModels) { & $python scripts\download_models.py; Check-Exit }
& $python -c 'from voiceforge.backend.database.models import initialize; initialize()'; Check-Exit
Push-Location frontend
try { npm ci; Check-Exit; npm run build; Check-Exit } finally { Pop-Location }
if (-not $NoLaunch) { & (Join-Path $PSScriptRoot 'Launch.ps1') }
