$ErrorActionPreference = 'Stop'
$statePath = Join-Path (Split-Path $PSScriptRoot -Parent) 'work/day10/local-https-processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No recorded local HTTPS processes.'; return }
$items = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($item in $items) {
    $process = Get-Process -Id $item.Id -ErrorAction SilentlyContinue
    if ($process -and $process.Path -eq $item.Path -and $process.StartTime.ToUniversalTime().Ticks -eq $item.Started) {
        Stop-Process -Id $process.Id
    }
}
Write-Output 'Recorded local HTTPS processes stopped.'
