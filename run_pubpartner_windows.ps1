$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Log = Join-Path $Root "pubpartner_windows_launcher.log"
function Log($m) { $line = "[$(Get-Date -Format s)] $m"; Write-Host $line; Add-Content -Path $Log -Value $line }
Set-Content -Path $Log -Value "==== PubPartner Windows Launcher ===="

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $base = @("py", "-3") }
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "Python 3.10+ was not found. Install Python and run this launcher again." }
    $base = @("python")
}

$baseExe = $base[0]
$baseArgs = @($base | Select-Object -Skip 1)
& $baseExe @baseArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "PubPartner requires Python 3.10 or newer." }

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Log "Creating isolated .venv"
    & $baseExe @baseArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }
}

Log "Checking dependencies inside .venv"
& $venvPython scripts/bootstrap_dependencies.py 2>&1 | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -ne 0) { throw "Dependency setup failed. See $Log" }

Log "Running preflight"
& $venvPython run_pubpartner.py --preflight 2>&1 | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -ne 0) { throw "Preflight failed. See data/pubpartner/preflight_latest.json" }

Log "Starting PubPartner-only runtime at http://127.0.0.1:8000/pubpartner"
Log "Keep this window open. Press Ctrl+C to stop PubPartner."
& $venvPython run_pubpartner.py 2>&1 | Tee-Object -FilePath $Log -Append
