# PubCast Reach — 2i v22 compatibility integration (2026-10-09)

## Applied
- Preserved the existing `/2i` and `/writers-room` endpoints, existing `2i/index.html`, and existing document-store router.
- Added `/2i-v22` to serve the supplied, unchanged v22 Writer's Room HTML.
- No original files deleted. This is a reversible, additive integration.

## Critical limitation
- v22 calls `/api/pubpartner/manuscript/...` for intelligence, generation, commit and voice signals.
- The verified October 2 baseline does not contain those manuscript-intelligence endpoints. The `pubpartner-manuscript-intelligence.zip` referenced in the engineering log was not available as raw source here.
- Accordingly, manuscript intelligence is **NOT** integrated or live in this package. The v22 UI is staged at a separate route, not promoted as the default.
- This package is based on the verified October 2 agent-wiring archive, **not** a proven merge of later October 3–9 PubCast packages.
- Do not deploy over newer builds without reconciling differences.

## Verification
- Python syntax compilation of modified `main.py` passed.
- ZIP CRC integrity test passed.
- Confirmed old route and new route both present; v22 file is byte-identical to uploaded file.
- No live browser or complete application runtime test performed for the integrated ZIP.

## Next integration gate
Obtain the actual manuscript-intelligence module ZIP and the current canonical PubCast source; compare route contracts and dependencies, wire its router to startup, run Python tests and HTTP live tests, then promote v22 only after end-to-end validation.
