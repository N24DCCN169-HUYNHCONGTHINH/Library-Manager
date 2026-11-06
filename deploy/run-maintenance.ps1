param([Parameter(Mandatory=$true)][string]$BackupDirectory)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoRoot 'web/.venv/Scripts/python.exe'
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$lockPath = Join-Path $BackupDirectory 'maintenance.lock'
$lock = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
Push-Location (Join-Path $repoRoot 'web')
try {
    foreach ($command in @('expire_reader_profiles', 'refresh_overdue_loans', 'expire_reservations', 'send_reservation_notifications', 'clearsessions')) {
        & $pythonPath manage.py $command
        if ($LASTEXITCODE -ne 0) { throw "Maintenance failed: $command" }
    }
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-ffff')
    & $pythonPath manage.py backup_library --output (Join-Path $BackupDirectory ("library-$stamp.zip"))
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed.' }
} finally { Pop-Location; $lock.Dispose() }
