# 2i integration readiness and wiring audit

**Date:** 2026-11-18  
**Audit branch:** `codex/2i-integration-readiness-2026-11-18`  
**Parent:** `codex/2i-typewriter-manuscript-bridge-2026-11-18` at `4ca32875bcc58ecefe5b06ce718398457340c32d`.

## Objective

Answer whether 2i's actual hosted entry points, dependent scripts, editor controls, Foresight file-tray integration and Claude's typewriter are wired together. Do **not** confuse structural readiness with real end-to-end runtime acceptance. Do not rebuild working components merely to check their wiring.

## Confirmed entry points

- PubCast's `main.py` maps `/writers-room` to `2i/writers-room-v22.html`, and `/typewriter-console` to the original Claude typewriter page.
- The 2i and static asset directories have explicit FastAPI mounts. Writer's Room declares 14 external JavaScript files and three CSS files. All those referenced asset paths are present in the checked Git tree.
- The original typewriter page declares its own four classic scripts, manifest and styling. Its 48 hotspot IDs are unique, and the specified `/static/typewriter_keys.webp` asset exists.
- The Writer's Room page declares 128 unique DOM IDs with no duplicates.
- The bootstrap order includes formatting and narrative prerequisites before Reach, and Reach before the typewriter input, studio presentation, formatting menus and file adapter.
- Source syntax parsed for 14 main external classic JS scripts, four typewriter scripts and two inline scripts: **20 source-level parse checks passed, no failures**.

## Confirmed wiring defects and repairs

### 1. Foresight file-tray documents could not select the interactive typewriter

Before: `2i/2i-assets/studio-desk.js` immediately exited when `reachFileMode` was active, so the presentation switch and Claude iframe were absent. The normal authoring menus are deliberately off in Foresight file mode, so even a hidden presentation API would not be a usable integration.

After: the file route initializes the same typewriter iframe and key bridge, begins in Document mode, and offers an accessible **View** chooser for Document, Notebook and Typewriter. Studio-specific notes controls are installed only in normal studio mode. The existing Foresight file adapter remains responsible for session saving; no second save engine was introduced.

### 2. The file-tray adapter announced readiness before installing its command listener

Before: `file-workspace.js` emitted `foresight:file-ready` twice in the file route. The first was sent before registration of the host's message command handler. An immediate host Save or status request could be missed.

After: it sends exactly one ready signal only after the command listener is installed. The final signal includes the original file ID, nonce, version and capabilities.

### 3. Login prompt was mistaken for authenticated readiness

Before: Reach's `startReach()` can resolve after displaying the account modal while `initializing` remains `true`. The file adapter awaited the resolved promise and could then mount a session or announce readiness despite incomplete authentication.

After: the adapter additionally checks `initializing`; it disables Save and returns with an explicit sign-in notice until the authenticated reload finishes. It does not notify the host or mount a file session prematurely.

## Focused tests and evidence

- **7 source-executed structural checks passed:** PubCast routes, asset references, module order, distinct DOM IDs, typewriter asset/manifest, Foresight view selector and save-authority presence, and Reach-before-file mount ordering.
- **20 JavaScript syntax checks passed:** 14 2i external scripts, four typewriter scripts and two HTML inline scripts.
- **4 source-executed DOM harness checks passed** with the actual `studio-desk.js`: hosted mode still has notes controls; Foresight file mode gets a working chooser and the iframe; keys route to the active Write editor; wrong-origin messages and active generation are rejected.
- **3 source-executed file-adapter host harness checks passed** using actual `file-workspace.js`: exactly one ready signal after listener subscription, immediate Save command routes to the mounted file session and receives a response, failures to initialize an account and unresolved sign-in prompt both block readiness.

Permanent test files committed:
- `tests/test_2i_wiring_contract_node.js` (8 checks; its JS-parse check was executed independently in this audit, not through native Node runner)
- `tests/test_2i_file_presentation_wiring_node.js` (4 checks)
- `tests/test_2i_file_host_ready_node.js` (3 checks)

Source-level test execution used the GitHub connector and isolated V8 compatibility stand-ins. **This does not substitute for `node --test` in a complete checkout, real FastAPI startup, true Foresight file persistence or Chromium through the full host.** Earlier typewriter input tests against native Node and isolated Chromium are documented in the predecessor branch and are not being recounted as new host tests.

## Release gates still open

1. Start the complete integrated PubCast host, authenticate, open both `/writers-room` and `/writers-room?file=...`, and confirm every declared module loads with no page errors.
2. Write, Save Now, close, reopen, compare and recover a manuscript with real file/server storage. Also verify the file-tray host Save/prepare-close protocol with a real parent iframe, not just a mock.
3. Test Claude's typewriter from both editor contexts, including cursor selection, Unicode, multiline editing, sound preference, touch at phone sizes, real undo and protected passages.
4. Reconcile Claude's separate `2i-beta-polish` mobile/undo changes that are still preserved on its source and backup branches; do not merge unexamined overlapping CSS/HTML onto Fable's source.
5. Real recording, 30-minute capture, crash/restart, packaging and independent release review.

**Decision:** improvements are committed on a protected integration-audit branch; **full-app integration remains unverified**, and beta release approval is blocked. Keep `main`, the original Claude/Fable branches and their exact-head backups unchanged.
