# Builds the portable Windows release in dist\Undertone: the app plus its own
# Python with every dependency except PyTorch, which the app downloads on first
# use of AI voice (the CUDA build is too big for a release asset).
#
#   pwsh scripts/build_windows.ps1
param([string]$PythonVersion = "3.12.10")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest is very slow with a progress bar

function Run {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE) { throw "Failed ($LASTEXITCODE): $args" }
}

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$App = Join-Path $Dist "Undertone"
$Py = Join-Path $App "python"
$PyExe = Join-Path $Py "python.exe"

if (Test-Path $Dist) { Remove-Item -Recurse -Force $Dist }
New-Item -ItemType Directory $Py | Out-Null

Write-Host "Python $PythonVersion (embeddable)"
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile "$Dist\python.zip"
Expand-Archive "$Dist\python.zip" $Py
Remove-Item "$Dist\python.zip"
# Search path: the stdlib zip, the python folder, the app folder (..), then
# Lib\site-packages, which `import site` adds.
$Pth = Get-ChildItem $Py -Filter "python3*._pth" | Select-Object -First 1
Set-Content $Pth.FullName "python312.zip`r`n.`r`n..`r`nimport site`r`n" -NoNewline -Encoding ascii

Write-Host "pip"
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "$Dist\get-pip.py"
Run $PyExe "$Dist\get-pip.py" --no-warn-script-location --disable-pip-version-check
Remove-Item "$Dist\get-pip.py"

Write-Host "Dependencies"
# torchcrepe/torchfcpe need torch to install, and PyTorch's own dependencies
# (sympy, networkx, ...) are wanted. Install the CPU build, then remove it.
Run $PyExe -m pip install --no-warn-script-location --disable-pip-version-check `
    torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cpu
Run $PyExe -m pip install --no-warn-script-location --disable-pip-version-check -r "$Root\requirements.txt"
Run $PyExe -m pip uninstall -y torch torchaudio
# Console-script launchers have this machine's paths baked in.
Remove-Item -Recurse -Force "$Py\Scripts" -ErrorAction SilentlyContinue

Write-Host "App"
foreach ($item in "undertone", "vendor", "README.md", "THIRD_PARTY_NOTICES.md", "Undertone.bat", "Undertone (debug).bat") {
    Copy-Item -Recurse (Join-Path $Root $item) $App
}
Get-ChildItem $App -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Remove-Item -Recurse -Force "$App\vendor\rvc\models" -ErrorAction SilentlyContinue

$Files = Get-ChildItem $App -Recurse -File
$Longest = ($Files | ForEach-Object { $_.FullName.Length - $App.Length } | Measure-Object -Maximum).Maximum
$MB = [math]::Round(($Files | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Built $App : $($Files.Count) files, $MB MB, longest path inside: $Longest chars"
