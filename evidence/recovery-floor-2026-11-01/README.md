# Recovery floor evidence — November 1, 2026

Signed: **Codex / ChatGPT Work / recovery-floor-2026-11-01**.
Work record: [PC-003 and whole-code review](https://github.com/whatsupjosie/Beyond-October/issues/1).

Base commit: `bfbdcf0676c11163063ef369cd419b5667792cfe`.
Environment: Linux, Python 3.12.14, standard library only. The full host's FastAPI,
uvicorn, httpx and pytest dependencies were not installed in this local execution
environment. This work's checks deliberately execute without importing the host.

## RAN

1. `python -m unittest discover -s tests -p test_data_checkpoint.py -v`
   — 31 passed, 0 failures, 0 skipped, 0.747 seconds in the final run.
   See `unittest.log`. An initial 24-test run had one incorrect assertion against
   the string representation of a returned dictionary; it was corrected to compare
   the actual restored message field, preserving exact whitespace and Unicode.
2. `python evidence/recovery-floor-2026-11-01/scale_probe.py`
   — 501 real temporary files, 67,136,254 uncompressed bytes; exact 64 MiB payload
   hash recovered after making the original path unavailable. See `scale-probe.json`.
   This is a synthetic byte-payload exercise, not a media-codec acceptance test.
3. Source inventory comparison against the full current Git tree — 1,702 blobs,
   1,661 exact local matches, 41 different/absent. See `source-inventory.json` and
   `docs/CODEBASE_WORK_REVIEW_2026-11-01.md` for the scope. Parsed new Python sources
   and the separately retrieved current differing backend sources for syntax.

Checks include actual ZIP files, restored original bytes, SHA-256 corruption
rejection, injected storage failures, concurrent publication attempts, subprocess
CLI execution, committed SQLite WAL recovery and existing native document and
conversation stores reopening with owner filters retained. Test data and keys are
disposable fixtures; no actual owner runtime data is included in these artifacts.

## Boundaries

No full application/browser startup from the restored copy; no physical Windows,
PowerShell, phone, GPU or production-media checks; no live multi-store consistency,
power-loss test or acceptance of external data roots; no full-suite rerun.
Claude's two persistent environments were not tested or changed. No GitHub Actions
test run, main merge, deployment or release was performed.

The host-data recovery primitive is ready for review within this tested scope.
It does not complete all startup/recovery commissioning, browser-data recovery,
source reconciliation or PubCast's production-master requirements.
