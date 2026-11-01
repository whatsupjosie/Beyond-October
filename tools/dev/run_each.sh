#!/bin/bash
# Run the test suite one file at a time and write a tab-separated summary.
# Usage: tools/dev/run_each.sh [results-file]   (set PYTHON to choose the interpreter)
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-python3}"
OUT="${1:-$REPO/.test-results.tsv}"
cd "$REPO"
: > "$OUT"
for f in $(ls tests/*.py | sort); do
  b=$(basename "$f")
  case $b in conftest.py|__init__.py) continue;; esac
  start=$(date +%s)
  out=$(timeout 240 "$PY" -m pytest -q -p no:cacheprovider "$f" 2>&1); rc=$?
  end=$(date +%s)
  summ=$(echo "$out" | grep -E "[0-9]+ (passed|failed|error|skipped)|no tests ran" | tail -1)
  [ $rc -eq 124 ] && summ="TIMEOUT(240s)"
  printf '%s\t%s\t%ss\t%s\n' "$b" "$rc" "$((end-start))" "$summ" >> "$OUT"
done
echo DONE >> "$OUT"
