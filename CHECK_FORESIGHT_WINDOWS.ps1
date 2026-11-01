# PowerShell 5: read-only application preflight, then optional manual launch.
param(
    [int]$Port = 8000,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { Write-Error 'Python is not installed or not on PATH. No files were changed.'; exit 2 }
Write-Host 'Foresight Build | Python interpreter:'
& python --version
Write-Host 'Checking module syntax...'
& python -m compileall -q run_reach.py modules/foresight_workspace.py modules/foresight_host_tools.py modules/foresight_file_formats.py
if ($LASTEXITCODE -ne 0) { Write-Error 'Python source did not compile'; exit 3 }
Write-Host 'Checking shipped scripts...'
foreach ($Name in @('static/foresight_counter.html','static/foresight_counter.js','static/foresight_canvas2d.js','static/foresight_programs.js','2i/writers-room-v22.html')) {
    if (-not (Test-Path -LiteralPath $Name)) { Write-Error ('Missing file: ' + $Name); exit 4 }
}
Write-Host 'Testing packaged routes and registered programs...'
& python tools/workbench_preflight.py
if ($LASTEXITCODE -ne 0) { Write-Error 'Preflight failed. Resolve missing requirements or packaging before continuing.'; exit 5 }
Write-Host 'PASS: Source and route preflight. Actual Windows UI has not yet been commissioned.'
if ($Start) {
    # This is a normal explicit user action. A fresh, isolated data directory is
    # used so testing does not overwrite personal PubCast data.
    & python run_reach.py --port $Port --data-dir ForesightAcceptanceData --start-page foresight-counter --no-legacy-2i
    exit $LASTEXITCODE
}
Write-Host 'To launch with isolated user data, run: .\CHECK_FORESIGHT_WINDOWS.ps1 -Start'
