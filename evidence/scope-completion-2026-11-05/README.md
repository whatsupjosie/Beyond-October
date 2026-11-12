# Scoped feature completion and two debugging rounds

Signed: Codex / ChatGPT Work, November 5 Los Angeles session. The actual tested application is local commit `878ef65`, tree `e33526b9b2cba7da5f5df0030e6af6166a9cc761`. Documentation and evidence are committed afterward. The earlier published parent is `df7c400cbcf37c62e8efd38451298cedb71a0fb3`.

## Broad runs

| Run | Application source/tree | Outcome |
| --- | --- | --- |
| Round 1 | `3326b06` / `4c60a98b12a3d843f8076c7a9929fd8fbc32c3c3` | 2357 passed, 6 skipped, 1 failure, 4 teardown errors; 16 subtests; 967.25 s |
| Round 2 initial | `5e3331f` / `3d70db0b70183d339cc0f3874cddbe96117bb367` | 2362 passed, 6 skipped, 1 failure; 16 subtests; 962.94 s |
| Round 2 repaired confirmation | `878ef65` / `e33526b9b2cba7da5f5df0030e6af6166a9cc761` | 2363 passed, 6 skipped, no failures/errors; 16 subtests; 963.46 s |

Each full command runs the whole collected repository suite, not only the changed tests:

```sh
PLAYWRIGHT_NODEJS_PATH=$(command -v node) PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q --junitxml=../whole-round1.xml
PLAYWRIGHT_NODEJS_PATH=$(command -v node) PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q --junitxml=../whole-round2.xml
PLAYWRIGHT_NODEJS_PATH=$(command -v node) PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q --junitxml=../whole-round2-confirmed.xml
```

stdout/stderr was redirected to the correspondingly named `.log`. Preserve failed-run evidence alongside successful repairs. JUnit includes subtests/collection skips in its aggregate count; report pytest's terminal summary separately rather than conflating them.

## Reproduced defects and proof

| Defect | Reproduction | Repair / proof |
| --- | --- | --- |
| Guest entered nonexistent green-room view | `scope-targeted.log` | Canonical `green_room/main`; `scope-final-targeted.log`, 35 passed |
| API base contract and partial offline auth adapter | `whole-round1.log/.xml` | Normalize guest API stem, guard optional adapter method; `round1-repairs.log/.xml`, 27 passed |
| Concurrent additive migrations/WAL startup | `startup-race-before.log`, `migration-races-before.log` | Immediate migration transactions and bounded WAL retry; 12 simultaneous constructors x 8 roots, included in 27-pass selection |
| Session bans stale between workers | Targeted moderation selection | Shared session cohort in SQLite; actual spawned worker sees ban/unban; `moderation-current.*`, `round1-repairs.*` |
| Late private frame leaked into newly selected conversation, drafts lost | `contact-switch-before.log` | Generation/socket fence, per-actor/conversation drafts, stable retry ID and receipt handling; `contact-switch-after.log`, 3 Node cases |
| Full host rejected advertised valid photo at 1 MiB global cap | `photo-limit-before.log` | Explicit 2 MiB endpoint body allowance; real full-host photo tests `photo-after.*`, 3 passed |
| Whole group omitted the sender member | `whole-group-before.log` | Resolve all members including sender; group/notes/browser regressions |
| Audio-clock clacker mark waited on rendering | `whole-round2.*`, `clacker-round2-failure/` (285/132 ms) | Paint on audio-clock callback, keep 250 ms bound and visual quality; focused `clacker-round2-repair/` 2 passed (100/26 ms), full-confirmation measured 8/90 ms |

Groups/contacts acceptance is in `groups-api.*`, `group-contact-browser.*`; moderation/DM selection in `moderation-current.*`. Selections overlap; do not sum them into a unique test total. These are test-generated data and identities. Any test JWTs found in copied diagnostics are redacted; original media bytes stay outside the text evidence bundle. The failed clacker artifact hashes preserve provenance.

## Node coverage

All top-level `tests/test*.cjs` and `tests/test*_node.js` were executed separately with `node --test --test-reporter=tap <file>`, 90-second per-file timeout, preserving stdout/stderr and return code. Round 1: 28 files, 101 reported cases, all exit 0. Round 2 and repaired confirmation: 29 files, 104 reported cases, all exit 0. Per-file logs and `results.json` reside in `round1-node/`, `round2-node/`, `round2-confirmed-node/`. Earlier combined-run output was not used to invent totals.

## Six skipped cases and limits

- `tests.alex_little_one.test_public_baby_role` and `tests.test_public_baby_role`: disabled research-module collection skips.
- `test_real_host_browser_dictation_recordable_speech_stop_and_restart`: explicitly installed `PUBCAST_SPEECH_TEST_MODELS` required.
- `test_real_neural_roundtrip_word_times_two_voices_and_clean_shutdown` and `test_real_worker_busy_cancel_timeout_and_next_request_recovers`: same missing optional speech models.
- `test_decoder_rejects_playlists_and_decoded_duration_not_just_upload_size`: optional `requirements-speech.txt` decoder dependencies required.

Linux Python 3.12.14, Node 24.22.1, Chromium 141 / Playwright 1.56, software WebGL, FFmpeg/FFprobe. Isolated test data roots, no real owner data changes. No native Windows, physical GPU/microphone/phone, WAN or cross-device timing certification. Automatic three-probe calibration is design-reviewed only; see the synchronization review. Exact source hashes and full skip entries are in `tested-source.json` and XML.
