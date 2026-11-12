# Continuous engineering handoff — October 31, 2026

## Beyond-October update — November 1 session / November 2 UTC

Signed: `Codex / ChatGPT Work / speech-system-2026-11-01`, task PC-035.
Work branch: `gpt-work`, starting at `123474459c472fb449d3fd56a07331f4650ae69e`.
The dated source hashes and executed results are in
`evidence/speech-system-2026-11-01/`; see [speech handoff](../../SPEECH_SYSTEM.md).
RAN: local CPU Whisper/Kokoro, authenticated HTTP, actual browser dictation/review,
2i reading, actual mixer recording decoded/transcribed, cancellation/failure
recovery, saved choices after restart, recovery/auth/studio regressions. Combined:
124 passed, zero skipped, sixteen supporting subtests; nine Node entries and the
separate audio-room script passed. A final uppercase-language correction was
followed by thirteen passing speech/boundary checks.

Native Windows/PowerShell 5, physical microphones, SAPI/XTTS and sample-accurate
lip sync are UNKNOWN. The browser run uses reduced motion; its normal compositor
transition clock stalled. A separate existing Blackbox close-on-disconnect log at
`modules/blackbox_routes.py:146` belongs to PC-024 and remains open. Exact model
install inputs are pinned; no startup download, main merge or deployment occurred.
No required owner voice audition blocks this engineering. Claude retains capture
ownership. This update does not seal the Control Room/studio. The earlier report
below is retained as its original source-specific history.

---

Project: PubCast AI / Rearview Foresight.
Branch: `lead-engineering-control-room-tv-studio-2026-10-31`.
Current implementation: `4f6c5d3f48eb0b4d157f8947eaea1a51d7a8f610`.
Source tree: `caae611345449faf9935a1531b79a5239a39ce74`.
State: real runtime brought up, reproducible defects repaired, verification and limits
recorded. **The Control Room/studio is not sealed or release complete.**

Read `AGENTS.md`, the directive, `RUNTIME_REPORT.md`, the acceptance matrix and the
executed evidence in this folder. The earlier onboarding-only state is historical;
its source and branch history remain available. Do not repeat its missing-clone
or uninstalled-environment statements as the current state.

## What actually runs

The complete checkout was installed and launched on Linux with Python 3.12.14,
Node 24.22.1, FastAPI 0.115.14 and real Chromium/SwiftShader. Both signed-in studio
and Director pages share the canonical switcher. Eight genre sets load actual GLB
actors, render different Program/Preview framing and fit desktop/mobile viewports.
The remote Director decodes actual 640×360 confidence frames; these are not full-rate
video feeds. An actual CUT is reflected across two browser pages.

Local 1280×720 browser recording writes retrievable WebM data. Every take has a
separate media key. Reload/playback and preservation of the first take through a
second recording are tested. Failed storage retains a downloadable recovery Blob
and supports retry. Available media from a recorder failure is saved as INCOMPLETE.
A raw local browser proxy is not a source-level master.

PANIC is now tested against a real running browser recording and actual program
mixer output: it stops the capture, blacks Program, suppresses a measured tone,
preserves the take and leaves a visible PANIC status. The prior model silently
discarded the sequence fields; that defect is corrected at the Hub boundary.

The existing server RecordingService now restores persisted session metadata,
identifies interrupted capture, refuses to reuse existing take directories, writes
metadata atomically, and produces portable hashed archives preserving source bytes.
Converted outputs are separate and explicitly derived. Tests cover fresh-host data
trees, tampering, conversion failure, duplicate filenames, legacy paths and concurrent
exports. This service work does not connect the browser recorder to server ingest.

2i account startup, secure IDs on plain local HTTP, truthful storage indicators,
actor rig/lifecycle problems and slow Counter admission were also repaired. Room
artwork, walkable-world geometry and owner-written content were retained.

## Reproduce this environment

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q
npm run test:node
node --test tests/production25d.test.cjs tests/test_production25d_core.cjs tests/test_production25d_wiring.cjs tests/test_production25d_switcher_bridge.cjs tests/test_studio25d_confidence.cjs tests/test_editor_sync_interchange.cjs tests/test_foresight_file_close_node.js tests/test_foresight_owner_recovery_node.js tests/test_twoi_rich_browser_contract_node.js
```

Exact installed Python versions and executed results are under
`evidence/2026-10-31/`. Use a disposable `PUBCAST_DATA_DIR`, a generated signing
secret, enforced auth and real first-run setup for browser tests. Existing fixtures
do this automatically. Browser and uvicorn must share the same execution network
namespace; separately launched sandbox commands did not share localhost. Port 8765
is used by an internal renderer bridge, so the standalone smoke probe used 8780.

## Evidence and known limits

`RUNTIME_REPORT.md` records defects, failures before correction and test commands.
The broad complete-suite outcome and subsequent focused repair are recorded in `evidence/2026-10-31/README.md`.
Overlapping focused runs are not additive test totals. Desktop viewport tests are
not physical phone performance proof. SwiftShader is not target-device GPU evidence.

GitHub Actions run `41239084129` failed with empty step arrays and no runner name.
No failing command or successful CI execution was observable. Local executed tests
are the runtime evidence. The integrity workflow now runs actual Python/browser
checks when an operational runner is available; do not announce green CI from a
workflow definition alone.

## Final verification boundary

The full run on `73ca8bba...` completed with 2,166 passed, one failed and two
skipped research modules. Its single failure exposed an autosave overwriting the
Python syntax diagnostic. Commit `4f6c5d3...` fixes that race; the complete affected
file workspace module passes 14 tests, three file Node cases pass, and the
strengthened individual test passes again. No all-green whole-suite rerun on the
last two-file correction is claimed. The new broad evidence is retained verbatim.

## Next engineering work — keep ownership

1. Implement a real encoded browser-origin ingest path through the existing
   RecordingService/Blackbox contracts, with bounded flow control, source ownership,
   timestamps, restart recovery and observable committed bytes. Keep the canonical
   CameraManager and program-audio mixer. A camera ID/JPEG is not an ingest stream.
2. Carry actual audio between participating clients and preserve independent tracks.
   Validate mute/gain/solo and clock behavior using recorded waveforms and real media.
3. Build a complete replayable shoot master: original GLB/texture/scene dependencies,
   performer/animation state, camera/light/graphics/cue histories, timestamps, separate
   audio, provenance and integrity. A marker JSON plus proxy is not sufficient.
4. Implement deterministic reconstruction and selective genuine native 4K rendering
   from that source package. Test repeatable frames after restart and alternatives
   over chosen time ranges. Never upscale the proxy and rename it a cinema master.
5. Finish the real 15-second clacker/video mark/separate blip capture path and measure
   per-track offsets. The Node-tested +0.030-second sidecar is not recorded sync proof.
6. Exercise every Control Room station and the rough-cut editor end to end; perform
   actual finishing import/relink on an independent machine. Resolve is not installed
   in this execution environment. Full station acceptance remains open.
7. Continue compatibility/license review of source candidates. Recursive inventories
   for October, The-Prime and Wednesday- are present; absent blobs are not automatic
   imports. The only absent October blob is an older minified vendor file.
8. Profile physical modest hardware and mobile devices, long sessions, reconnect,
   competing publishers and failure recovery. The confidence-feed release tombstones
   have bounded retention; they are not a permanent production ingest ledger.

The owner-only list remains final switcher photographs/set plates, aesthetic approval,
license or credential decisions genuinely unavailable to engineering, physical-device
acceptance and release authorization. They did not block this engineering pass.

Main was not merged, nothing was deployed, and no launch or sealing was announced.
