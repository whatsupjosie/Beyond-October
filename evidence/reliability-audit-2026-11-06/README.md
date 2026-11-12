# Post-completion reliability audit — executed evidence

Signed: Codex / ChatGPT Work, November 6 UTC. See `handoffs/SESSION_ENDING_2026-11-06_RELIABILITY_AUDIT.md` for findings, source paths, decisions and explicit limits.

## Tested source

- Prior published checkpoint `3e7e460cbb207d85f83fc3e72783dbdd2204649b`, tree twin local `edd3fad`.
- First repair local `6666261`, tree `c95430fb92339d1414a1597fd773869f946e5484`: attachment staging leases, single guest-ban authority, bounded chat acknowledgement wait, group limit and new regressions.
- Second source local `81598014a8d40f086a67e5ee03d96d9261c775a8`, tree `7884f403b5db9e74efb39c1efef069c5d56b9833`: recipient/placement fix, real browser acceptance and same-length corruption/hash mutation proof. The first completed broad run exposed a staging bookkeeping invariant.
- Final source local `bf20f7f520f0422b9c560f22e83d05a9035764a3`, tree `8bd568419b03703b4d113a20b966975c972b4c78`: parent lease metadata moved outside payload staging. Production source is frozen for the final confirmation. Later commits contain only documentation/evidence.

## Executed reproduction and repair ledger

| Artifact | What actually ran / observed |
| --- | --- |
| `before.log/.xml` | Two actual failures: a second router deletes staged attachment during HTTP send; expired session ban still denies guest |
| `first-repairs.log/.xml` | Eighteen passed after those repairs, including existing notes and guest-signature tests |
| `group-limit-before.log` | One failure: two hundred members accepted plus automatic owner exceeds bound |
| `receipt-before.log` | Four Node cases: three passed, lost-ack deadline case failed |
| `repairs.log/.xml` | Twenty-two passed including spawned-worker staging and group boundary |
| `receipt-after.log` | Four Node cases passed after bounded receipt wait |
| `real-journeys.log/.xml` | Nine passed, one new browser test failed because history assertion raced old conversation state; test wait corrected, no app repair claimed for that failure |
| `real-journeys-repaired.log/.xml` | Five passed: independent guests and audit boundaries |
| `atomic-boundaries.log/.xml` | Five passed, including membership change after preview but before save: no partial note/attachment |
| `placement-before.log/.xml` | Real browser recipient edit returns HTTP 400 because removed person's placement remains |
| `last-repairs.log/.xml` | Five passed: both new real-browser journeys, existing group/contact UI and hash mutation proof |
| `hash-mutation.log/.xml` | One passed: same-length corruption rejected; removing only hash enforcement in an isolated in-memory copy makes rejection assertion fail |
| `full.log` | Intentionally interrupted first broad run, exit 130 after continued review found placement bug; partial, not a passing result |
| `full-final.log/.xml` | First completed broad audit on `8159801`: 2370 passed, 6 skipped, 1 cleanup-invariant failure, 16 subtests, 1022.73 s. Persistent lock metadata was inside payload staging; source corrected while original assertion remains unchanged. |
| `cleanup-repair.log/.xml` | Twenty-four passed after moving parent lock outside staging; existing assertions unchanged |
| `full-confirmed.log/.xml` | 2,371 passed, six skipped, zero failures/errors, 217 warnings and sixteen subtests passed in 990.44 seconds (exit zero). Twenty-nine Node files reported 105 cases, all exit zero; canonical npm selection also exited zero with nine overlapping cases. |
| `npm-node-final.log` | Canonical `npm run test:node`, exit zero, nine reported cases; overlaps the per-file Node selection |
| `node-final/` | Twenty-nine real Node files, 105 reported cases, all exit zero; each run uses `node --test --test-reporter=tap <file>` with ninety-second timeout |

Targeted counts overlap and must not be summed as unique coverage. Original failed evidence is retained. Test JWTs, if present in copied diagnostics, are redacted before publication; no real user databases, credentials or media are included.

Final broad command (Linux execution environment):

```sh
PLAYWRIGHT_NODEJS_PATH=$(command -v node) PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q --junitxml=../audit-2026-11-06/full-confirmed.xml
```

The focused log name corresponds to its `--junitxml` name; standard pytest `-q` and explicit test paths were used. Python 3.12.14, Node 24.22.1, Playwright 1.56 / Chromium 141, FFmpeg/FFprobe, software WebGL. `pip check`: no broken requirements. Tests use isolated temporary data roots.

## Limits of the evidence

Six prior skips are two disabled Alex research-module collections, three optional neural-speech-model cases and one optional decoder-dependency case; inspect final XML for exact entries. Native Windows, physical devices, WAN, cross-device clock drift, sustained load and power-loss durability are not certified here. The attachment lease uses Windows APIs according to Microsoft documentation, but native Windows execution remains UNKNOWN. Crash cleanup proves process-exit behavior, not power-cut guarantees.

A 250 ms clacker regression assertion is not a frame-accuracy or millisecond-accuracy claim. The automatic three-probe calibration/compensation UI is still design only. Full replayable scene-source master, selective native 4K and actual Resolve import/relink remain open acceptance gates. The studio is not sealed or declared release-ready by this audit.

Published application source twin: `885707b079f71b17b3f84e0a801e129eb61538d1`, exact tested tree `8bd568419b03703b4d113a20b966975c972b4c78`. Local/public source commit twins and exact skips are in `tested-source.json`. Final decoded clacker offsets: 94/38 ms; earlier first-run observation 15/16 ms is retained separately under `clacker-final/`. Neither pair is a universal accuracy guarantee.
