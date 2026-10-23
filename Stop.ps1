$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath 'data\server.pid') {
    $serverProcessId = [int](Get-Content -LiteralPath 'data\server.pid')
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$serverProcessId"
    if ($process -and $process.CommandLine -like '*voiceforge.backend.api.app:app*' -and $process.ExecutablePath -eq (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) {
        # Windows venv Python may launch the base interpreter as a child.
        # Stop only that validated studio runtime, then its launcher.
        $runtimeChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$serverProcessId" | Where-Object { $_.CommandLine -like '*voiceforge.backend.api.app:app*' }
        foreach ($runtimeChild in $runtimeChildren) { Stop-Process -Id $runtimeChild.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $serverProcessId -ErrorAction SilentlyContinue
        Write-Host 'Studio stopped. Interrupted jobs resume on next launch.'
    }
    Remove-Item -LiteralPath 'data\server.pid'
}
