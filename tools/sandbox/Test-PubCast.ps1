# PubCast test sandbox - Windows PowerShell 5 wrapper.
#
# STATUS: UNVERIFIED ON WINDOWS. This file was written in a Linux cloud sandbox
# that has no PowerShell, so it has been read and reasoned about but never run.
# The first real run on a Windows laptop is the test. If it fails, send the
# exact error text; do not assume the Python runner is at fault.
#
# What it does: finds a real Python (not the Microsoft Store stub), then hands
# every argument to tools\sandbox\run_sandbox.py. All real work is in Python so
# that Windows and the cloud sandbox run the very same logic.
#
# Examples (run from the repository root, or from anywhere):
#   powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier fast
#   powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier standard -Capture
#   powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Matrix "3.11,3.12,3.13"
#   powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Compare "A" "B"   (see note)
#
# Note on -Compare: PowerShell 5 binds two positional values awkwardly, so pass the
# two report folders as one string separated by a comma: -Compare "A,B".

param(
    [ValidateSet('fast', 'standard', 'full')]
    [string]$Tier = 'fast',
    [string]$Python = '3.12',
    [switch]$Reuse,
    [switch]$KeepVenv,
    [switch]$Capture,
    [switch]$BrowserProbe,
    [switch]$AllowBrowserDownload,
    [string]$PlaywrightVersion = '',
    [string]$Matrix = '',
    [string]$Label = '',
    [string]$Compare = ''
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $here 'run_sandbox.py'
if (-not (Test-Path $runner)) { throw "Cannot find $runner" }

function Test-RealPython([string[]]$cmd) {
    # The Microsoft Store 'python.exe' alias prints a hint and exits non-zero.
    try {
        $exe = $cmd[0]
        $rest = @()
        if ($cmd.Length -gt 1) { $rest = $cmd[1..($cmd.Length - 1)] }
        $out = & $exe @rest -c "import sys; print(sys.version_info[0])" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq '3')
    } catch { return $false }
}

# 1. Prefer the py launcher with the requested version, then plain py, then python.
$candidates = @(
    @('py', "-$Python"),
    @('py', '-3'),
    @('python')
)
$chosen = $null
foreach ($c in $candidates) {
    if ((Get-Command $c[0] -ErrorAction SilentlyContinue) -and (Test-RealPython $c)) { $chosen = $c; break }
}
if (-not $chosen) {
    Write-Host 'No working Python 3 was found.' -ForegroundColor Red
    Write-Host 'Install Python 3.12 from python.org (tick "Add python.exe to PATH"), then run this again.'
    exit 2
}

# 2. Build the argument list for the Python runner.
$runnerArgs = @('--tier', $Tier, '--python', $Python)
if ($Reuse) { $runnerArgs += '--reuse' }
if ($KeepVenv) { $runnerArgs += '--keep-venv' }
if ($Capture) { $runnerArgs += '--capture' }
if ($BrowserProbe) { $runnerArgs += '--browser-probe' }
if ($AllowBrowserDownload) { $runnerArgs += '--allow-browser-download' }
if ($PlaywrightVersion) { $runnerArgs += @('--playwright-version', $PlaywrightVersion) }
if ($Matrix) { $runnerArgs += @('--matrix', $Matrix) }
if ($Label) { $runnerArgs += @('--label', $Label) }
if ($Compare) {
    $pair = $Compare.Split(',')
    if ($pair.Length -ne 2) { throw '-Compare needs exactly two report folders separated by a comma: "A,B"' }
    $runnerArgs = @('--compare', $pair[0].Trim(), $pair[1].Trim())
}

# 3. Run it. UTF-8 output so the report characters survive the console.
$env:PYTHONUTF8 = '1'
$exe = $chosen[0]
$prefix = @()
if ($chosen.Length -gt 1) { $prefix = $chosen[1..($chosen.Length - 1)] }
Write-Host ("Using: " + ($chosen -join ' ')) -ForegroundColor Cyan
& $exe @prefix $runner @runnerArgs
exit $LASTEXITCODE
