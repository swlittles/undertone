# Tests the build from build_windows.ps1 with its own Python: the test suite,
# the PyTorch download the app does for AI voice (CPU build), and a GUI launch.
# Point LOCALAPPDATA/APPDATA somewhere disposable first.
$ErrorActionPreference = "Stop"

function Run {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE) { throw "Failed ($LASTEXITCODE): $args" }
}

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$App = Join-Path $Dist "Undertone"
$PyExe = Join-Path $App "python\python.exe"

# Run from dist so the tests import the bundled app, not the checkout.
Copy-Item -Recurse "$Root\tests" "$Dist\tests"
Copy-Item "$Root\pytest.ini" $Dist
Push-Location $Dist
try {
    Run $PyExe -m pip install --disable-pip-version-check --no-warn-script-location pytest
    Run $PyExe -m pytest -q -p no:cacheprovider tests
    Run $PyExe -m undertone.runtime install --flavor cpu
    $env:QT_QPA_PLATFORM = "offscreen"
    Run $PyExe "$Root\scripts\smoke_release.py"
    Run $PyExe -m pip uninstall -y pytest pluggy iniconfig
} finally {
    Pop-Location
    Remove-Item -Recurse -Force "$Dist\tests", "$Dist\pytest.ini" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force "$App\python\Scripts" -ErrorAction SilentlyContinue
}

# Auto-update on a copy of the build: download the latest release, swap it in
# after the app process exits, and check user files in the folder survive.
$Copy = Join-Path ([IO.Path]::GetTempPath()) "UndertoneCopy"
Remove-Item -Recurse -Force $Copy -ErrorAction SilentlyContinue
Copy-Item -Recurse $App $Copy
Run (Join-Path $Copy "python\python.exe") "$Root\scripts\smoke_update.py"
$deadline = (Get-Date).AddMinutes(3)
while ((Test-Path "$Copy\_update") -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
Get-Content (Join-Path $env:APPDATA "Undertone\update.log")
if (Test-Path "$Copy\_update") { throw "the update wasn't applied" }
if (Get-ChildItem $Copy -Filter "_old_*") { throw "old files were left behind" }
if (-not (Test-Path "$Copy\my-notes.txt")) { throw "the update removed a user file" }
$expected = Get-Content (Join-Path ([IO.Path]::GetTempPath()) "undertone-expected-version.txt")
$got = & (Join-Path $Copy "python\python.exe") -c "import undertone; print(undertone.__version__)"
if ($got -ne $expected) { throw "expected version $expected after the update, got $got" }
"Updated a copy to $got"
Remove-Item -Recurse -Force $Copy -ErrorAction SilentlyContinue
