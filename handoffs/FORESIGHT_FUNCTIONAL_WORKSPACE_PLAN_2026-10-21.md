# Foresight functional workspace execution plan

Priority: immediate, ahead of tray polish. Performance/background permissions remain deferred in PUBCAST_DEFERRED_FEATURES.md.

## Contract

A tray hosts capabilities and content, independent of its shape. A blank tray can receive a file or program. Reuse existing PubCast/2i/studio programs; preserve authoritative originals. Reading, editing, conversion, saving and reopening are separate capabilities and must be reported separately. Never label a download or saved window layout as a saved application document.

## Approach selected

Considered: OS file associations (requires originating applications and leaves the workspace); a monolithic replacement editor (duplicates existing programs and risks regressions); shared file workspace and format adapters feeding existing programs. Choose the third. Keep Counter geometry and renderer untouched.

## Execution order and tools

1. Durable file workspace: IndexedDB originals and working copies keyed by stable IDs; Counter serialization references IDs. Explicit save, save-copy/download, recovery, rename and supported native Save As. Preserve originals; surface quota/permission failures. Verify reload with actual bytes.
2. Text/code: UTF-8/UTF-16 text detection and editable textarea fallback for Markdown, scripts, XML, JSON and configuration. Native browser copy/paste and undo. Unknown binary files get original-download and explicit unsupported-format information, never garbled text presented as conversion.
3. Documents: authenticated local format API, bounded archive parsing and extraction, DOCX/ODT readable text plus conversion-loss notice; DOCX export of edited text. Original remains byte-identical. PDF viewer plus text extraction; spreadsheet data extraction separately from formula-preserving spreadsheet editing. Dependencies must be declared and absent converters must produce clear errors.
4. Images/media: browser decoding, image rotate/crop and PNG working-copy saving, original retained; persisted audio/video with playback. Do not claim full video editing from playback.
5. Existing-program handoff: feed text/scripts to the existing 2i editor through a validated same-origin import protocol; preserve unsaved manuscripts before switching. Confirm actual routes for PubPartner, studio, PubWorld and controls; route presence alone is not operational certification.
6. Development workspace: inventory existing execution tools; owner-authenticated terminal/session bridge with explicit process ownership, stop, cleanup and output; integrate with file editor. A command-output box must not be described as a full interactive terminal.
7. Browser: preserve existing embedded-webpage support; distinguish embedding from a real browser engine. Inspect supported desktop-host integration before selecting an implementation. Google online documents require authenticated retrieval; .gdoc shortcuts are not document contents. Do not bypass embedding restrictions with an unrestricted proxy.
8. Quit: flush/check document saves; list unsaved work and active tasks; terminate owned processes and sidecars through launcher supervision; verify no owned listeners/processes remain. Closing a tray remains distinct from quitting the host.
9. Regression and delivery: Playwright real file inputs/downloads/reload, format round trips and originals hashes, ASGI auth/error tests, existing Counter tests and launcher check. Package cumulative/incremental changes against exact upstream; no remote push. Report remaining unsupported formats and unverified hardware plainly.

## Completion evidence

For each feature record original input, user action, actual output, reload/reopen result and limitations. Required scenarios include Markdown/script edit-save-reopen; DOCX read-convert-edit-export-reopen; image crop/rotate-save-reopen; media reopen; 2i handoff; real terminal lifecycle; external browser handling and clean quit. No universal file-format promise, no placeholder controls, no weakened tests.

## Estimates

No credible full completion estimate until adapters and host lifecycle have been exercised. Work proceeds now; do not stop after this plan. A settings mockup or source inspection does not satisfy the user request.

## Execution checkpoint

Implemented and verified work, current failures and remaining dependencies are recorded in FORESIGHT_FUNCTIONAL_WORKSPACE_STATUS_2026-10-21.md. The entire plan is not declared complete. The animation/asset question is recorded separately for later and must not displace this work.

## Offline-first execution update

The user clarified that Google, browser-vendor APIs, Playwright and optional services must not control essential file work. Current implementation and per-capability evidence are in FORESIGHT_OFFLINE_CORE_2026-10-21.md. Local disk folder saving, native 2i manuscript saving, local Python checking/execution, offline browser checks and installer-free startup are implemented. Optional cloud retrieval, full browser embedding, full TTY emulation and physical studio commissioning remain explicitly bounded; do not claim those passed.
