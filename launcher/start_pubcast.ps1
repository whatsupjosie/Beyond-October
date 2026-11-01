param()

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\hardc\OneDrive\Documents\Playground"
$HealthUrl = "http://127.0.0.1:8000/api/health"
$StartUrl = "http://127.0.0.1:8000/"
$RuntimeDir = Join-Path $ProjectRoot "data\runtime"

function Test-PubCastHealth {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        "C:\Users\hardc\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Users\hardc\OneDrive\Desktop\ALL AIs can only work in this folder and stay in this folder and access nothing outside of it\Pubcast AI V9\.venv\Scripts\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Show-LauncherError([string]$message) {
    Add-Type -AssemblyName PresentationFramework
    [void][System.Windows.MessageBox]::Show($message, "PubCast Launcher")
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if (Test-PubCastHealth) {
    Start-Process $StartUrl | Out-Null
    exit 0
}

$pythonExe = Find-Python
if (-not $pythonExe) {
    Show-LauncherError "PubCast could not find a usable Python runtime."
    exit 1
}

$serverArgs = @(
    "-m",
    "uvicorn",
    "main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000"
)

Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $serverArgs `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden | Out-Null

for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 750
    if (Test-PubCastHealth) {
        Start-Process $StartUrl | Out-Null
        exit 0
    }
}

Show-LauncherError "PubCast started but did not pass health check in time."
exit 1
