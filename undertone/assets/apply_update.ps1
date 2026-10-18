# Moves a downloaded Undertone update into place once the app has closed.
# Started by undertone/updater.py; runs from a temp copy so nothing here is locked.
param(
    [int]$AppPid,
    [string]$Root,
    [string]$Staging,
    [string]$Log,
    [switch]$Restart
)
$ErrorActionPreference = "Stop"

function Say($msg) {
    Add-Content -LiteralPath $Log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $msg) -ErrorAction SilentlyContinue
}

# Antivirus and Explorer can hold files for a moment after the app exits.
function Move-WithRetry($from, $to) {
    for ($i = 1; ; $i++) {
        try {
            Move-Item -LiteralPath $from -Destination $to
            return
        } catch {
            if ($i -ge 30) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
}

Say "Waiting for Undertone (pid $AppPid) to close"
Wait-Process -Id $AppPid -Timeout 60 -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# The app's own files: what the new version ships plus what older versions shipped.
# Anything else in the folder belongs to the user and is left alone.
$new = @(Get-ChildItem -LiteralPath $Staging -Force | ForEach-Object Name)
$owned = @("python", "undertone", "vendor", "README.md", "THIRD_PARTY_NOTICES.md",
           "Undertone.bat", "Undertone (debug).bat") + $new | Select-Object -Unique
$backup = Join-Path $Root ("_old_" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Path $backup | Out-Null

$moved = @()
$placed = @()
$ok = $false
try {
    foreach ($name in $owned) {
        $path = Join-Path $Root $name
        if (Test-Path -LiteralPath $path) {
            Move-WithRetry $path (Join-Path $backup $name)
            $moved += $name
        }
    }
    foreach ($name in $new) {
        Move-WithRetry (Join-Path $Staging $name) (Join-Path $Root $name)
        $placed += $name
    }
    $ok = $true
    Say "Updated $Root"
} catch {
    Say "Update failed, putting the old version back: $_"
    foreach ($name in $placed) {
        Move-Item -LiteralPath (Join-Path $Root $name) -Destination (Join-Path $Staging $name) -ErrorAction SilentlyContinue
    }
    foreach ($name in $moved) {
        Move-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $Root $name) -ErrorAction SilentlyContinue
    }
}

if ($Restart) {
    Start-Process -FilePath (Join-Path $Root "python\pythonw.exe") -ArgumentList "-m", "undertone" -WorkingDirectory $Root
}

if ($ok) {
    Remove-Item -LiteralPath $backup, $Staging -Recurse -Force -ErrorAction SilentlyContinue
} elseif (-not (Get-ChildItem -LiteralPath $backup -Force)) {
    Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
}
