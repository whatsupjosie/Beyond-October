# Standard-first engineering audit | 2026-11-19

**Status:** source/documentation review and external standards research; **NO runtime changes or executed application acceptance in this audit**.
**Scope:** principal known technical challenges in 2i, Foresight, PubPartner/Alex, 2.5D studio, audio, local inference, test infrastructure and Windows distribution. Not an exhaustive audit of every file or every separate Rearview Foresight repository.
**Checked baseline:** branch `claude/2i-coalesce-saves-2026-11-18` (including 2i's improvements after draft PR #13). `main` is not the assembled product.
**Governing rule:** `QUALITY_STANDARDS.md` remains authoritative. Preserve originals, use existing tested code first, no silent deployment/merge to main, and never change author text/assets or persistent personal data without authorization.

## Permanent decision rule: STANDARD FIRST

Before implementing a subsystem, the engineer must:
1. State the actual user-visible requirement and the observed defect or unmet acceptance criterion.
2. Inspect the repository and saved branches for a **working existing solution**. Reuse it instead of building a duplicate.
3. Search for published standards, platform capabilities and maintained open-source libraries. Cite upstream docs and exact package/license version. Compare **reuse current**, **standard built-in**, and **open-source package** (three genuine options) against functionality, offline runtime, installation size, Windows/phone support, security, failure handling, commercial redistribution, model/asset licensing, upgrade/rollback and integration risk.
4. Prefer the smallest proven standard solution **that fixes the defect**. A library is not a substitute for deciding ownership, identity, sequencing, durability or recovery. No dependency merely for a green test or the appearance of progress.
5. Preserve native formats, originals and data backups. Test pre-change failure (red), post-change success (green), independent storage/readback, real-host start, browser/device where applicable, and rollback. Record evidence on the **exact** resulting branch.
6. Routine reversible adapters, tests and dependency evaluation can proceed on a new branch. **Ask Josie first** before data migrations, irreversible format changes, new paid/non-open licensing, replacing core editors/renderers, disabling features, altering original creative assets/words, deployment, merging main or discarding user data.
7. If a standard method is already in use, improve correct application of it rather than replacing it.

**Core integrity invariants:** a writer always knows which document is open; a save updates only that document and its authorized revision; a save status never asserts newer text was committed; exceptions never silently erase recoverable edits; locks and annotations survive legal undo/redo; unknown/out-of-sync records remain available separately rather than overwritten.

## Decision register (each is a *candidate*, not a claim of completed implementation)

| Problem / repo evidence | Established practice or project (license) | Decision / condition |
| --- | --- | --- |
| 2i duplicate save authorities in Reach and Foresight; PR #13 fixes wrong route; Claude reproduces 41 writes for 40 keystrokes | Existing IndexedDB transactions and server persistence; optional **idb** (ISC) for transaction promises, existing SQLite on host | **P0: reuse/fix first.** One authority per document and revision; await transaction completion; bounded coalescing; independent readback. Do **not** switch databases or add idb blindly. |
| Reload, mobile kill, loss before async commit; new exit journal on Claude branch | Write durable incremental checkpoints while editing; keep revisions and separate recovery record; optional `StorageManager.persist()`; use `visibilitychange` as last *opportunity*, never promise `unload/pagehide` | **P0.** Preserve Claude's journal; test tab kill/storage full/crash; host file export remains separately necessary. Browser storage may be evicted or lost. |
| False Saved / stalled save and document-switch races | CAS/optimistic concurrency, monotonically increasing revision, fingerprint the exact committed snapshot, abort or block close while unresolved | **P0.** Failure-inject held and rejected writes. Do not announce saved based on a button click or unresolved promise. |
| DOCX formatted editing, import/export, original preservation | Existing **@docx-editor.dev/core 2.32.0** (Apache-2.0) plus pinned local fonts (OFL), native OOXML/ZIP, existing rich editor wrapper | **P1: finish existing integration** and direct DOCX open if fidelity tests pass. Avoid `@docx-editor.dev/pro`, `editor-api`, `docx-to-pdf` (separate proprietary terms). Validate commercial notice/assets and round trips. |
| Protected spans, Unicode, typewriter undo | DOM `beforeinput`, `Intl.Segmenter`, one editor history; for structured future changes **ProseMirror** or **Lexical** (MIT) | **P0 behavior test first.** Existing editor and DOCX core already contain editing machinery; switching editor engines is high-risk and requires approval. Test IME, emoji, paste, lock, undo, redo in real host. |
| True simultaneous human coauthoring and offline reconciliation, if required | **Yjs** shared CRDT types/persistence (MIT), or documented server revision conflicts without real-time merging | **Architecture decision later**; current AI collaboration should not be mistaken for multiuser CRDT editing. Do not install until a concrete concurrent-write requirement and protocol is accepted. |
| Tests that pass from source slices but break when code moves; five stale Node harnesses | **Playwright** browser E2E (Apache-2.0), pytest (MIT), **Hypothesis** generated state sequences (MPL-2.0) | **P0.** Repair/replace brittle extraction harnesses, run Node and Python in acceptance gate, seeded fault injection, compare bytes via independent raw storage reads. |
| 2.5D stage, avatar glTF, camera positions, animation | Existing **Three.js** (MIT), glTF 2.0, built-in animation/blend, standard WebGL rendering | **Reuse** current Three.js; measure performance on target hardware. Do not write a competing scene graph, animation file format or renderer. |
| Counter drag/resize/touch vs bespoke irregular collision physics | Browser Pointer Events, `requestAnimationFrame`; **interact.js** gestures (MIT), optional | **Conditional.** Gesture normalization may be reusable, but it cannot replace unique polygon collision and damping requirements. Profile and regression-test before adoption. |
| WebRTC ingest, multi-camera distribution, remote participants | Browser **WebRTC** and RTCP standards; **LiveKit SFU** (Apache-2.0) or **coturn** TURN (BSD-3-Clause) where needed | **Conditional** on real multi-peer need, bandwidth and offline networking. Never treat WebRTC stream ID as a working media feed. SFU adds server/ops load; requires architecture approval. |
| Camera/audio synchronization and clacker offsets | RTP timestamps, RTCP sender reports and W3C WebRTC stats; preserve stable media time-base and separate sync sidecar | **P1.** Measured timebase per source; explicit offsets and cross-correlation test. Standards help but do **not** automatically align unsynchronized cameras or create high-resolution source masters. |
| Capture/export and media codecs | MediaStream/MediaRecorder for previews, preserved original media; **FFmpeg** for mux/transcode when verified; **OpenTimelineIO** for edit interchange (Apache-2.0) | **P1.** MediaRecorder MIME support varies; FFmpeg build may invoke LGPL/GPL compliance obligations; verify exact binaries and Resolve interchange tests before shipping. Do not promote 640x360 confidence frames as masters. |
| Offline STT / TTS and viseme pipeline | **whisper.cpp** (MIT), **sherpa-onnx** (Apache-2.0); standardized word/phoneme time offsets; evaluate model-licensing separately | **Benchmark only until accepted.** Distinguish ASR word timestamps from validated visemes and live low-latency lip sync. Library's permissive license does not necessarily license model weights/voices. |
| Local modest-hardware LLM inference | **llama.cpp** (MIT) and GGUF as an existing portable inference path | **Optional benchmark** against actual RAM/latency requirements. Models have their **own** licenses; no hidden runtime downloads or assumption a 26B model will work well on phone/CPU. |
| Windows offline executable and true application lifecycle | Existing Python/FastAPI host; **PyInstaller** (GPL with commercial-use exception) for packaging; optional **pywebview** (BSD-3-Clause) or Tauri (Apache-2.0/MIT) for desktop shell | **P1.** Test on Windows/PowerShell 5 with bundled Python, assets, models/engine, WebView/runtime availability, updates and user data stored outside installation directory. No renderer rewrite solely for an .exe. |
| Authentication, account identity and embedded iframes | Existing FastAPI auth; OWASP session/CSRF/cookie guidance; same-origin and nonce checks | **Audit current behavior.** Do not invent a second auth protocol or trust client-supplied file IDs without checking identity. |
| Canonical Alex memory file accidentally mutated by preflight or launchers | Immutable seed/template + separate live data directory + verified backup and migration; existing Git blob guard | **P0 preserve; ASK FIRST.** No auto migration; identify which vessel has meaningful live memory; dry-run verified backups and byte hashes before changing a path. |
| Multiple branches/partially assembled releases; runtime source overshadowed by older merge | Git preserved branches, provenance hashes, integration PRs and one complete acceptance branch; source-level tests plus real-host runs | **P0.** Reconcile by feature with backward-compatible tests. No giant unreviewed copy, no declaration of beta from branch-level unit pass. |

## Current known source facts, not extrapolations

- Foresight/Reach save routing and premature file-ready problems: draft [PR #13](https://github.com/whatsupjosie/Beyond-October/pull/13) and [PR #12](https://github.com/whatsupjosie/Beyond-October/pull/12).
- Claude's actual Chromium save tests on `claude/2i-coalesce-saves-2026-11-18`: 40 keystrokes yielded 41 IndexedDB writes before coalescing, 1 after; crash-reload journal and stale writer preservation tested. Real phone kill and Windows still untested. [Findings](https://github.com/whatsupjosie/Beyond-October/blob/claude/2i-coalesce-saves-2026-11-18/docs/2i-adversarial-save-findings-2026-11-18.md).
- The bundled DOCX core pin, font license, reproducible SHA256 artifacts and no external runtime requests are declared in [provenance](https://github.com/whatsupjosie/Beyond-October/blob/claude/2i-coalesce-saves-2026-11-18/2i/2i-assets/vendor/docx/PROVENANCE.json). Note Pro product licensing is separate.
- Actual served `2i/writers-room-v22.html` and painted `2i/index.html` remain distinct; the design was not wholly integrated, per [readiness audit](https://github.com/whatsupjosie/Beyond-October/blob/claude/2i-coalesce-saves-2026-11-18/docs/2i-integration-readiness-audit-2026-11-18.md).
- Follow repository [QUALITY_STANDARDS.md](https://github.com/whatsupjosie/Beyond-October/blob/claude/2i-coalesce-saves-2026-11-18/QUALITY_STANDARDS.md) including no unapproved merge, no overwrites, and executed tests rather than inferred success.

## Upstream references reviewed

- SQLite atomic commit: https://www.sqlite.org/atomiccommit.html ; WAL: https://sqlite.org/wal.html
- IndexedDB transactional and browser durability limitations: https://developer.mozilla.org/en-US/docs/Web/API/IDBTransaction
- Page lifecycle: https://developer.chrome.com/docs/web-platform/page-lifecycle-api
- Browser storage and persistence: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
- idb (ISC): https://github.com/jakearchibald/idb ; ProseMirror (MIT): https://github.com/ProseMirror/prosemirror ; Lexical (MIT): https://github.com/facebook/lexical
- DOCX core vs Pro licensing: https://www.docx-editor.dev/docs/latest/installation ; https://github.com/eigenpal/docx-editor
- Yjs (MIT): https://github.com/yjs/yjs ; Playwright (Apache-2.0): https://github.com/microsoft/playwright ; Hypothesis (MPL-2.0): https://github.com/HypothesisWorks/hypothesis
- Three.js (MIT): https://github.com/mrdoob/three.js ; interact.js (MIT): https://github.com/taye/interact.js
- LiveKit (Apache-2.0): https://github.com/livekit/livekit ; coturn (BSD-3-Clause): https://github.com/coturn/coturn ; WebRTC statistics: https://www.w3.org/TR/webrtc-stats/
- MediaRecorder: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder ; FFmpeg licensing: https://ffmpeg.org/legal.html ; OpenTimelineIO (Apache-2.0): https://github.com/AcademySoftwareFoundation/OpenTimelineIO
- whisper.cpp (MIT): https://github.com/ggml-org/whisper.cpp ; sherpa-onnx (Apache-2.0): https://github.com/k2-fsa/sherpa-onnx ; llama.cpp (MIT): https://github.com/ggml-org/llama.cpp
- PyInstaller commercial-use license exception: https://pyinstaller.org/en/stable/license.html ; pywebview (BSD-3-Clause): https://github.com/r0x0r/pywebview ; Tauri: https://github.com/tauri-apps/tauri
- OWASP session security: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

## Immediate executable next slice

1. No new library in the save path yet. Reconcile Claude's proven journal/coalescing into the full-host integration line and test save A in flight while B is typed, late completion, wrong document identity, failed/held host PUT, quota, browser reload and independent raw readback.
2. Make the actual Node and Python tests run together and surface existing failures; replace brittle source-slicing tests with supported browser tests, not blind string-marker repairs.
3. Use the existing Apache DOCX engine to test formatted open/edit/save/reopen, including deliberate exit and font/layout differences. Never touch original bytes.
4. Build Windows installer/executable on test hardware with runtime artifacts and independent launch/save/reopen confirmation.
5. For recording, prove source-level capture/clock alignment and portable editorial interchange before considering a new server/SFU.

**This audit document is deliberately documentation only, not a merged runtime modification or a passing integration test.**