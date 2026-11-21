#!/usr/bin/env bash
# Preview-only launcher, isolated to a Codespace. Does not alter code or deploy.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .preview-runtime
pid_file=".preview-runtime/2i.pid"
log_file=".preview-runtime/2i.log"
if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
  echo "2i is already starting or running (PID $(cat "$pid_file"))."
else
  if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
    export PUBCAST_ALLOWED_ORIGINS="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN},http://127.0.0.1:8000,http://localhost:8000"
  fi
  nohup python run_reach.py --no-browser --start-page writers-room >"$log_file" 2>&1 </dev/null &
  echo "$!" > "$pid_file"
  echo "Launching 2i with Reach: PID $(cat "$pid_file")."
fi
echo "Preview: open port 8000 in the Codespaces PORTS panel and append /writers-room"
echo "Local health: http://127.0.0.1:8000/health"
echo "Log: $log_file"
