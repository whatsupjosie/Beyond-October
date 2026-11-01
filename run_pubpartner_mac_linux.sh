#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
"$PY" scripts/bootstrap_dependencies.py
"$PY" run_pubpartner.py --preflight
printf '\nPubPartner is starting at http://127.0.0.1:8000/pubpartner\n'
printf 'Keep this terminal open. Press Ctrl+C to stop PubPartner.\n\n'
"$PY" run_pubpartner.py
