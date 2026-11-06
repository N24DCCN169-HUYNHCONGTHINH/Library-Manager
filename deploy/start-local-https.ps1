param([Parameter(Mandatory=$true)][string]$RestoredDatabase)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$webRoot = Join-Path $repoRoot 'web'
$workRoot = Join-Path $repoRoot 'work/day10'
$pythonPath = Join-Path $webRoot '.venv/Scripts/python.exe'
$caddyPath = Join-Path $workRoot 'tools/caddy.exe'
$configPath = Join-Path $PSScriptRoot 'Caddyfile.local'
foreach ($item in @($RestoredDatabase, $pythonPath, $caddyPath)) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "Required file missing: $item" }
}
foreach ($port in @(9080, 9443)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use." }
}
$env:DJANGO_SETTINGS_MODULE = 'config.local_https'
$env:LIBRARY_HTTPS_DB = (Resolve-Path -LiteralPath $RestoredDatabase).Path
$env:LIBRARY_CADDY_DATA = (Join-Path $workRoot 'caddy-data').Replace('\','/')
$env:LIBRARY_STATIC_ROOT = (Join-Path $webRoot 'staticfiles').Replace('\','/')
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $webRoot
try {
    & $pythonPath manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Application check failed.' }
    & $pythonPath manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Static file collection failed.' }
    & $caddyPath validate --config $configPath --adapter caddyfile
    if ($LASTEXITCODE -ne 0) { throw 'Caddy configuration validation failed.' }
    $backend = Start-Process -FilePath $pythonPath -ArgumentList @('serve_waitress.py') -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $workRoot 'waitress.out.log') -RedirectStandardError (Join-Path $workRoot 'waitress.err.log')
    try {
        $proxy = Start-Process -FilePath $caddyPath -ArgumentList @('run', '--config', ('"' + $configPath + '"'), '--adapter', 'caddyfile') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $workRoot 'caddy.out.log') -RedirectStandardError (Join-Path $workRoot 'caddy.err.log')
    } catch { $backend.Kill(); throw }
    @(@{Id=$backend.Id;Path=$pythonPath;Started=$backend.StartTime.ToUniversalTime().Ticks}, @{Id=$proxy.Id;Path=$caddyPath;Started=$proxy.StartTime.ToUniversalTime().Ticks}) | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workRoot 'local-https-processes.json')
    Write-Output 'Local HTTPS started: https://localhost:9443/ (isolated restored data; local CA not installed in Windows).'
} finally { Pop-Location }
