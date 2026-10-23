$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
do {
    Write-Host "`n======================================`n          RPG VOICEFORGE`n======================================"
    Write-Host "1. Start Voice Studio`n2. Stop Voice Studio`n3. GPU Diagnostics`n4. Download / Manage Models`n5. Manage Character Library`n6. Run Batch Generation`n7. Export to Unreal Engine`n8. Run Tests`n9. View Logs`n0. Exit"
    $choice=Read-Host 'Choose'
    try {
        switch ($choice) {
            '1' { & .\Launch.ps1 }
            '2' { & .\Stop.ps1 }
            '3' { & $python -c 'from voiceforge.backend.hardware import detect_gpu,torch_info; print(detect_gpu()); print(torch_info())' }
            '4' { $model=Read-Host 'qwen_base / qwen_custom / qwen_design / qwen_custom_large (empty = defaults)'; if ($model) { & $python scripts\download_models.py $model } else { & $python scripts\download_models.py } }
            '5' { & .\Launch.ps1 }
            '6' { & .\Launch.ps1; Write-Host 'Open Batch Generator in the studio; import CSV or JSON.' }
            '7' { Invoke-RestMethod 'http://127.0.0.1:8765/api/export/unreal' -Method Post | Format-List }
            '8' { & $python -m pytest -q }
            '9' { Get-Content -LiteralPath 'data\logs\server-errors.log' -Tail 60 }
        }
    } catch { Write-Host $_ -ForegroundColor Red }
} while ($choice -ne '0')
