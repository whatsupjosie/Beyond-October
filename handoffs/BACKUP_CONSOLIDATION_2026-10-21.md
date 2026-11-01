# Backup consolidation — October 21, 2026

Owner: Josie Curtsey Cobbley. Repository: whatsupjosie/October. Delivery branch: Backup-Consolidation. The October-Foresight-Doc-Integration branch preserves the earlier offline workspace and recovery snapshot.

## Preserved work

recovery/2026-10-21 contains 142 previously verified recovery files: communications and workbench source, segmented capture, menu/settings donor archive, avatar source and GLBs, historical evidence and plans. The recovered upstream editor free-core source is now added with its acquisition record. Compiled caches, runtime databases and credentials are excluded. Existing repository files and the user's design records are retained. Nested donor archives are source references, not active application code.

## Consolidated application changes

Reconciled the October 20 communications implementation and earlier workbench improvements with the October 21 offline file workspace using the verified 82ebf267 source as the common comparison. Resolved conflicts in the launcher, actual served v22 editor and wiring tests. Kept the explicit foresight-counter launcher option and existing default route, offline optional-service policy, local filesystem saves, host shell and supervised quit.

Restored the real Reach 2i conversation/manuscript runtime and styles alongside local file editing. File-mode startup skips unrelated server manuscript restoration and account recovery; ordinary manuscript initialization completes before local recovery runs. Normal local save retains the Reach save path as well. A targeted browser failure exposed a stale Save indicator and the normal-save timer conflict; both were repaired without weakening assertions.

Integrated communications source includes selected-microphone processing, STT/TTS lifecycle fixes, room playback policy, bounded partner-turn requests, durable Blackbox PCM capture and separate health/recording indicators. This preserves the implementation checkpoint's limitations: genuine providers, physical audio, Windows launch and full recording coverage remain unverified.

SegmentedCaptureRecorder and RangePreserver plus their tests are present at their intended module paths. They passed their real FFmpeg tests here. The optional supervisor-owned segmented backend is NOT wired into the active PCM capture path; do not claim that UI lifecycle integration is complete. That wiring must choose one source owner and preserve the operator-only boundary.

## 2i editor acquisition

See 2i/editor-engine/README.md and ACQUISITION.json. Downloaded EigenPal 2.32.0 Apache-2.0 core, local fonts, CMU pronunciations and WordNet 3.1 data. Built an offline browser bundle with font-shaping WASM, local fonts and third-party notices. A real browser open/edit/save/reopen fixture preserved bold, font size, indentation, header, table and margin; it attempted no external requests. A reproducible qualification is tools/2i_editor_checks/qualify_editor.py. These are engine qualification results, not production 2i rich-document integration. The production importer still creates explicitly labelled text copies. Replacing it is the next document gate.

2i owns file/edit/format/save/speech/writing-tool behavior. Trays organize, frame, resize and position programs. They do not implement a second editor. Planned 2i tools include exact text handling, full rich-format saves, script styles, optional poetry forms and syllable guidance, local dictionary/thesaurus/rhyme lookup, word and selection count, adjustable read-aloud estimates, page numbers, phrase/quotation search and undoable replacement. Preserve source formats; native .2i copies keep recognizable names, stable IDs and conflict-safe destination handling. Existing local STT/TTS code should be reused; installed offline models/voices and physical-device acceptance are separate gates.

## Validation in this consolidation

- 24 Python capture/turn/host/workspace checks passed.
- 34 format/workbench/HTTP/route checks passed. An initial browser attempt had 14 setup errors because its development browser binary was absent. The binary was then installed for testing only.
- Browser file-workspace run: 13 passed, one normal-manuscript save check failed. After repairing its status/timer race, that exact check passed. No test assertions were weakened. The logs retain the failure rather than pretending it never happened.
- Segmented capture: 17 passed with real FFmpeg using --asyncio-mode=auto. The recovered async tests were marked explicitly for normal collection afterward; no behavioral assertion changed. The initial unmarked run is not a product failure.
- Node room policy, capture/browser contracts and program audio runtime checks passed.
- Actual launcher audit passed: served Counter, same-origin bridge, anonymous authorization denial, local disk save/reopen, Python syntax check and supervised quit.
- Downloaded engine browser fixture and pronunciation/rhyme/haiku component checks passed, with zero external browser requests.
- Previously observed Counter drag timing failure remains unresolved; no new physics optimization or full-suite pass is claimed.

## Work still tracked

Keep handoffs/PUBCAST_DEFERRED_FEATURES.md in status reviews: performance/background permissions, protected tasks and outgoing delivery remain deferred; the broader FBX/OBJ/GLB animation and 2D/3D/parallax request remains tracked. Menu/settings and avatar donor collections need capability-by-capability integration, not blind overlay. Manuscript-intelligence donor routes remain separate from the authenticated live service. Preserve the automatic-conversation-capture repair handoff; a real ChatGPT producer is not established by a downstream recorder.

## Launch and rollback

Install requirements.txt into your chosen Python environment, then run python run_reach.py --start-page foresight-counter. Runtime startup does not install browser tools or download optional Node utilities. Browser verification dependencies belong in requirements-dev.txt only. Copy an existing user-data directory separately; this package does not replace it. Previous commit 50194be26763bde7735e3c986e2b87155d507084 preserves the complete recovered snapshot before active consolidation.
