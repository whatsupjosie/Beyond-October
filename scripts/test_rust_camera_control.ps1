$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$token = [guid]::NewGuid().ToString("N")
Push-Location "$root\rust_crate"
try {
  cargo test
  cargo build --bin ws_renderer
  $env:PUBCAST_CAMERA_CONTROL_TOKEN = $token
  $proc = Start-Process -FilePath "cargo" -ArgumentList "run --bin ws_renderer" -PassThru -NoNewWindow
  Start-Sleep -Seconds 3
  python "$root\scripts\probe_rust_camera_control.py" --token $token
} finally {
  if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
  Remove-Item Env:PUBCAST_CAMERA_CONTROL_TOKEN -ErrorAction SilentlyContinue
  Pop-Location
}
