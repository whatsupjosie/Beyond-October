#!/bin/bash
# Start the program for local testing only. Run from anywhere; paths are relative to the repo.
# The password below is a throwaway test credential, not a real one.
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${PUBCAST_TEST_DATA:-$REPO/.testdata}"
PY="${PYTHON:-python3}"
mkdir -p "$DATA"
cd "$REPO"
PUBCAST_OWNER_PASSWORD='Test-Only-Pass-123!' exec "$PY" run_reach.py --no-browser --no-legacy-2i --port 8123 --data-dir "$DATA"
