> Superseded by FORESIGHT_OFFLINE_CORE_2026-10-21.md for current behavior, offline constraints, save destinations and test evidence.

# Foresight functional workspace — implementation and evidence

This supersedes the earlier 2026-10-21 audit for the current implementation status. It does not declare the entire PubCast studio commissioned. Source baseline remains 82ebf26755d3706f8d4d7d75d823bb73f4d1b07e. No remote push or installation into the user's computer was performed.

## Implemented

- Existing Counter file picker and blank-tray Import now route ordinary documents, text and scripts into the actual served 2i v22 editor. A shared file adapter provides basic rotate/crop image editing inside 2i, rather than replacing the typing program.
- Original file bytes and independent working copies are persisted in IndexedDB under stable file IDs. Counter layouts reference those IDs. Saved files are discoverable from Programs > Saved files. Original download remains available even for unsupported formats.
- Text/scripts/XML/Markdown/JSON use strict Unicode text decoding, native textarea editing, copy/paste and native undo. Invalid binary data is not silently decoded into garbage. Text exports use UTF-8; source bytes are preserved separately.
- Save saves a working copy. Save As uses the native destination chooser where supported and otherwise downloads an edited copy through the browser. A chosen filesystem handle is retained where the browser can persist it; further writes require permission. Native filesystem permissions and picker behavior on the user's OS remain unverified. Ordinary file-input selection does not grant permission to overwrite the original.
- DOCX, ODT, PPTX, XLSX and PDF have local authenticated text-copy conversion. DOCX export writes edited text to a new DOCX. Conversion loss is displayed persistently: this is not an Office layout editor. DOCX extraction covers main-body paragraphs and table cells, not headers, footers or footnotes; spreadsheet formulas are text, not calculated results; scanned PDF OCR is unavailable.
- 2i manuscript export retains its full native state, separately from plain-text exports. Normal 2i trays gain persistent recovery and Counter Save/Export messaging. File-mode recovery is isolated by file ID. Separate writers cannot silently overwrite a newer file working copy.
- Picked audio/video originals are retained for reopening and continue using the existing browser media player. Dedicated VLC/FFmpeg integration is deliberately deferred by the user.
- Browser .url shortcuts and recognized tray-metadata JSON have a matching import route. File export now obtains actual working content from 2i rather than merely saving window metadata.
- Open… > Development > Host shell starts a real authenticated-owner shell with streamed input/output, a workspace directory and explicit Stop. Disconnect and host exit terminate its process group. This is a shell console over pipes, not a full TTY emulator; full-screen terminal applications are not certified. Windows process cleanup is implemented but untested here.
- File > Quit PubCast saves supported file/2i working or recovery copies, lists local open trays and warns to finish other programs' own work. Authenticated owner Quit then shuts down the supervised Reach launcher, owned shells and its sidecar. It does not close the user's browser application or claim automatic task protection for recordings/rendering. The advanced protected-task feature remains deferred.

## Evidence

- Latest new functional suite: 17 passed. Includes actual browser file-to-2i mounting, editing, saving, reload/reopen, original-byte preservation, edited Save As download, full 2i state export, native undo/clipboard paste, image rotation/crop/restore and cancelled crop, binary fallback, stale-writer rejection, shortcut/tray import round trips; real format adapters and authentication; real shell process execution and cleanup.
- Broader targeted regression run: 87 passed, 1 failed. The unchanged drag-physics timing assertion measured 20.19 ms against its 16 ms limit. Geometry/progress assertions in that test passed. Earlier concurrent run measured 26.83 ms. No timing threshold or collision assertion was relaxed. Newer extra functional cases were subsequently checked in the 17-test suite; do not add these overlapping counts together.
- Actual launcher/loopback HTTP check passed: Counter and exact updated script served, anonymous protected route rejected, character bridge healthy, owner setup and host status available, authenticated Quit exited the launcher with code zero. This check used --no-legacy-2i and no physical hardware; a complete production run still needs verification of all other service/process cleanup.
- JavaScript syntax, Python compilation, targeted Ruff checks and patch whitespace checks passed. The inherited Starlette AnyIO deprecation warning remains.
- Browser tests execute repository source and real 2i/IndexedDB operations; intercepted same-origin requests serve local source and call actual format parsers. They do not establish a signed-in Google session, a native file-picker dialog on Windows, real audio hardware, GPU performance, or complete studio operation.

## Remaining functional work — do not hide it

1. Online Google Docs/Drive retrieval and writeback need runtime account authorization and a provider adapter. Downloaded DOCX/ODT documents are supported locally; a .gdoc shortcut is not the document body.
2. Legacy binary .doc/.xls/.ppt, RTF conversion, format-preserving Office editing, PDF annotation/OCR, advanced image operations and specialized project formats are not complete. Unsupported originals remain recoverable. No arbitrary-file universal opening promise.
3. A full embedded Chrome/Firefox-class browser is not supplied by an iframe. Existing embedded-webpage and external-browser opening remain; blocked sites still require an external browser or a later supported desktop-host integration.
4. A full TTY terminal, run/debug integration with the code editor, cross-platform file-picker verification, and full application-specific save/stop contracts remain work. The new shell console is useful but not an IDE.
5. PubPartner, studio, PubWorld, camera and control-room routes remain hosted in trays. Route presence is not evidence that every hardware and production workflow operates. Those end-to-end workflows remain to be commissioned.
6. Dense Counter physics performance and strict zero-overlap certification remain unresolved. This update did not switch back to physics optimization.

## Scope guard

The user asked about FBX/OBJ/GLB animation preview and 2D/3D/parallax modes, then explicitly clarified not to abandon the current work. Some isolated exploratory files were started prematurely; they are unwired and excluded from this deliverable. Record the asset-viewer requirement for later; do not claim it is implemented. Existing asset and animation code should be reused when that work is selected.

The deferred Performance/protected-task proposal remains in PUBCAST_DEFERRED_FEATURES.md. Include it in project status reviews without starting it automatically.

## Apply

This package updates the existing October repository; it is not a full source distribution. Preserve a backup or clean git state. Use exactly one patch:

- `changes.patch`: original upstream baseline 82ebf26755d3706f8d4d7d75d823bb73f4d1b07e.
- `changes-from-audited-update.patch`: previous audited update (74-test report / prior package version).

Run `git apply --check PATH_TO_PATCH`, then `git apply PATH_TO_PATCH`. Install declared dependencies with `python -m pip install -r requirements.txt`. Launch `python run_reach.py --start-page foresight-counter`. Do not apply both patches. A newer or independently modified repository must be reconciled rather than overwritten. Native user documents remain untouched by applying the source update.
