param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run Install.ps1 first.' }
New-Item -ItemType Directory -Force -Path 'data\logs' | Out-Null
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
    if ($health.version -ne '0.1.0') { throw 'Another service is using port 8765.' }
    $running = $true
} catch { $running = $false }
if (-not $running) {
    $process = Start-Process -FilePath $python -ArgumentList '-m','voiceforge.backend.server','voiceforge.backend.api.app:app' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'data\logs\server.log' -RedirectStandardError 'data\logs\server-errors.log' -PassThru
    $process.Id | Set-Content -LiteralPath 'data\server.pid'
    $ready = $false
    for ($i=0; $i -lt 45; $i++) {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) { throw 'Studio failed to start. See data\logs\server-errors.log.' }
        try { Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 1 | Out-Null; $ready=$true; break } catch {}
    }
    if (-not $ready) { throw 'Startup timed out. See data\logs.' }
}
Write-Host 'RPG VoiceForge: http://127.0.0.1:8765'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8765' }
