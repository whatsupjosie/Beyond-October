# Reach Writer’s Room: original-picture candidate and verification

Date: 2026-09-13 UTC  
Candidate: Reach_Writers_Room_001  
Decision: **usable for the next local review; canonical-base promotion remains on hold.**

## Audio and window controls revision

The user reported missing reading controls and mixed button behavior in the phone desk, then requested a general menu, settings, shrink and close. The new `reader.js` is a read-only speech controller with its own state; the donor playback loop generated new prose and moved it into the draft, so simply exposing those old buttons would have been incorrect for manuscript read-aloud. The new panel reads existing manuscript/draft/partner-reply text and offers start, play/pause/resume, stop, previous/next nonempty paragraph, ten-word seek, source, voice, rate, volume and cursor controls.

Speech cancellation invalidates callbacks before stopping the voice, preventing stale end/error events from advancing. Text/document changes stop the old reading queue. Long passages are chunked; unsupported, blocked or stalled speech gives a visible failure. Speech-boundary positions depend on the device, so resume can repeat a short chunk. This is the selected browser/device voice, not a configured personal Alex voice. See the [Web Speech API](https://webaudio.github.io/web-speech-api/#tts-section) for speech-event, voice and error semantics.

`desk-controls.js` adds the top-right Menu/Settings/—/× controls, general settings, a compact reader during shrink, and a reopen dock after closing. Closing awaits preservation and retains the editor state; it does not call window.close. The source picture remains byte-identical. General Settings contains phone text size, audio options and the existing PubPartner connection panel.

The source HTML’s remaining inline `onclick` attributes were replaced with explicit `button-bindings.js` assignments. The previous test harness compiled these handlers specially; it no longer does that. Archive filtering and dialog Close/Back now pass with inline handlers disabled. This is a plausible explanation for the user’s mixed button behavior; their exact browser policy was not observable here. Reference deletion now uses an in-page confirmation instead of a native confirm dialog. Inline modals are positioned near the tapped control.

Verification: **16 integrated editor groups**, **3 reader-controller groups**, and **8 standalone/inline groups** passed. Audio and close/shrink actions preserve the manuscript; control tests use simulated speech events and do not establish audible output. A full bootstrap over real HTTP served byte-matched audio/chrome assets and passed account/save/restart checks. Native handset rendering, actual sound, physical touch and live model generation remain unverified. The prior canonical-base hold remains.

Evidence: `writer_room_audit/audio-editor.log`, `audio-reader.log`, `audio-standalone.log`, and `audio-http.json`. The reproducible local-phone builder is now included at `tools/phone_local/`:

```bash
npm --prefix writer_room_audit ci
npm --prefix writer_room_audit test
python tools/phone_local/build.py --output-dir dist
NODE_PATH=writer_room_audit/node_modules node tools/phone_local/check.cjs dist
python tests/probe_reach_http.py --launcher start_reach.py
```

The `NODE_PATH` environment syntax shown is for Unix shells; the script itself is platform-independent. These steps reproduce logic/HTTP checks, not native audio. Rollback copies are in `build_backups/20260913_audio_controls/`, and the release manifest records every changed file.

## Phone edition added after the final pass

The user requested a separate cell-phone-sized version. The release now includes `2i-assets/phone.js` and `phone.css`, loaded after the desktop artwork layer. `?view=phone` or Menu → Phone view activates Write/Partner/Archive panels; Whole desk picture restores the existing desk. A first visit at 600 CSS pixels or less chooses the phone layout unless an explicit layout was requested. The original image remains unchanged and supplies the notebook/framing; this is a responsive arrangement of existing controls rather than a uniformly shrunken landscape picture.

The implementation moves the original elements and restores them through positional markers. No manuscript editor or coordinating runtime is duplicated. It adds 48-pixel minimum touch targets, 18-pixel manuscript type, keyboard-accessible tabs, visible reference/suggestion controls and a viewport-height handler. Switching layouts keeps the current document and draft. Storage/account/backend behavior is unchanged; another signed-in browser must open the server-saved document from My manuscripts.

The combined suite passed **16 component/state groups**. It exercises phone writing/save, synthetic partner-to-draft/commit, archive/settings/export/shelf, keyboard tabs and repeated desktop restoration. All 26 original controls are present once with callable handlers, visible captions and minimum heights. The real-HTTP bootstrap/restart probe additionally served and byte-checked the phone assets. Logs are `writer_room_audit/phone-editor.log` and `phone-http.json`. The prior 18-test API/startup result remains applicable evidence for the unchanged backend; it was not redundantly rerun solely for CSS/JS layout work.

A real phone connection is **not configured**: the supplied launcher binds loopback. This update is a phone web view, not a native mobile app or a hosted service. Real browser paint, touch hit testing, font wrapping and on-screen keyboard behavior remain unverified because browser rendering was blocked. DOM/state checks at several viewport sizes are not visual-layout proof. See `PHONE_EDITION.md` for access instructions, scope and limits. Rollback copies for this addition live under `build_backups/20260913_before_phone/`.

## Final pass: controls, preservation, and presentation

This additional pass found concrete omissions and fixed them. It supersedes the earlier 20-control map and the 9-group editor result. The original image remains byte-identical.

- The pictured search icon now runs reference filtering. Lock Mode now opens real writing/lock options. All four archive tabs have their own picture-aligned rectangles, instead of equal-width replacement tabs. The complete map now has **26 controls**.
- The scene-lock hit area covers the pictured button while an inset caption preserves its border. The Save and View All Ideas rectangles were adjusted against the original artwork. Controls remain at original-image coordinates and scale with the picture. **Show clickable areas** exposes the actual hit rectangles for local inspection.
- The test harness now evaluates the three scripts separately in their real order, loads both local stylesheets, and explicitly exercises the trusted inline click handlers. It checks actions and state changes for every mapped button; a callable function alone is no longer the completion criterion.
- A save already in progress now drains edits made during that write before document switching completes. Browser recovery is stored separately for each manuscript, and those copies can be opened through My manuscripts. Starting another offline manuscript no longer overwrites the only recovery copy. A storage-full condition prevents switching away from unpreserved work.
- Scene positions follow edits inserted before them. Navigation uses the rendered line position or a text measurement that accounts for wrapping, rather than treating every source paragraph as a single 25-pixel row. Actual wrapping geometry still needs a real-browser check. Collab mode preserves visible blank lines and spaces.
- Modal fields have an explicit dark background and readable text. Opening a modal makes the underlying desk inert; closing or pressing Escape restores it. Unused donor canvas decoration is skipped for the original-picture shell. The desk controls stay hidden while their map is loading, preventing a flash of misplaced HTML controls.

Verification for this revision:

| Gate | Result |
| --- | --- |
| Focused API, document ownership/revisions, PubPartner routing and launcher regressions | **18 passed**, one upstream deprecation warning |
| Editor/component checks | **13 PASS groups**, including click actions for all 26 mapped controls, save-during-switch, offline recovery, scene anchors, and modal state |
| Original-picture geometry | All 26 independently inspected button-center points are inside their corresponding rectangles; **zero pairwise button overlaps** |
| Proportional placement | Geometry checked at 1344×896, 1366×768, 1280×720, 1920×1080, 672×448, and 390×844 |
| Full bootstrap over real HTTP | **Passed**, including owner setup, protected document APIs, exact artwork hash, save/read and process restart |
| Browser rendering / native Windows execution / real model generation | **Still unverified** |

The geometry check compares the map to manually inspected points in the original image. The component checks use JSDOM and synthetic API/model responses. They cannot prove browser paint, actual pointer hit testing, font wrapping, operating-system launch behavior, or a model's real reply. Browser rendering remains blocked by the environment's browser security policy; no alternate browser or rendering workaround was attempted. The user's earlier Windows failure still needs its actual error message if it persists.

Reproduction additions:

```bash
python tests/check_reach_hotspots.py
python -m pytest -q tests/test_reach_launcher.py tests/test_reach_writers_room.py tests/test_pubcast_smoke.py
python tests/probe_reach_http.py --launcher start_reach.py
npm --prefix writer_room_audit test
```

The existing test dependency setup still applies. Evidence lives in `writer_room_audit/final-pass-*`, with the independently inspected points in `hotspot_alignment_review.json`. Rollback copies precede these edits under `build_backups/20260913_final_pass/`. This pass does not promote the whole Reach tree to canonical status.

## Startup repair after “it won’t run”

The delivered archive was intact and still passed Linux boot tests, but that does not reproduce the user's Windows failure. No screenshot or error text from the user's computer was available when this repair was made. The exact cause there remains unknown.

The Windows wrapper previously depended on `py`, used LF line endings, and provided only a generic failure message. It now uses CRLF, checks an existing environment plus `py`, `python`, and `python3`, verifies that Python is recent enough and 64-bit, forwards launch arguments, detects an incomplete extraction, and retains the error window. No claim is made that LF alone caused the reported failure.

The new standard-library `start_reach.py` creates and checks the private environment, retries dependency installation instead of trusting the old marker file, fingerprints requirements, and saves startup output to `reach-startup.log`. An incomplete environment is preserved under a new name before rebuilding. Manuscript/account data is not deleted. The Unix launcher also uses this bootstrap.

`run_reach.py` now reserves its port before polling the page and passes that reserved socket to Uvicorn. An occupied port produces an actionable error before the application starts or user data is created, preventing the earlier browser poll from accidentally opening another process on the same port. It does not automatically create another coordinating runtime on a different port.

Repair verification: a fresh private environment installed successfully from the declared requirements; its imports and `pip check` passed. The full bootstrap then passed the real-HTTP account/save/restart probe. Two additional regression tests passed for an occupied port and an incomplete extraction. The earlier 74-test backend and 9-group editor results below remain evidence from the previous revision; the whole suite was not redundantly rerun for this launcher-only change. Native Windows execution and the actual failure on the user's machine remain unverified.

Evidence: `writer_room_audit/launcher-repair-http.json`, `launcher-repair-tests.log`, and `launcher-repair-install.txt`. Reproduce with `python start_reach.py --check`, then `python tests/probe_reach_http.py --launcher start_reach.py`; the test driver requires HTTPX in the invoking interpreter. The actual first install needs internet access.

The user’s chosen implementation is now explicit: retain the original Writer’s Room picture, put real controls over its pictured buttons, and use an annotated copy as a placement guide when supplied. This candidate implements that approach. It also closes the paused 2i-to-PubPartner connection and adds persistent manuscript storage. It is not a claim that every subsystem in Reach is complete.

## 1. Exact inputs and preservation

| Input | Provenance and treatment |
| --- | --- |
| Reach source | `PUBCAST_REACH_CANONICAL_SNAPSHOT_2026-09-13.zip`, root `reach_now_seed_v1/`, 18,997,453 bytes, 1,760 ZIP entries |
| Snapshot SHA-256 | `a61faf48882ae4699a5c1377b48f394d3626f076a79b337a27f182817fa20418` |
| Editor mechanics | Supplied 2i v20 `pubcast-2i-writers-room.html`; `.2i` version 4, committed lines, draft buffer, locks, references, chapter boundaries, playback mechanics |
| Visible artwork | Uploaded `UI Sugestion(1).webp`, 1344 × 896, 171,662 bytes |
| Artwork SHA-256 | `495970f71a5615c947e73e1f32c0e56906037d4099a19152a19abba1e9134de7` |
| Later handoff | The later September 13 handoff was read as context. Its newer camera repairs and other source changes were not supplied in this snapshot and are not claimed as included here. |
| Personal Alex uploads | Preserved separately; not silently installed, merged, converted into system memory, or sent to a model. |

Original uploaded files and the canonical snapshot were not overwritten. This is an isolated candidate. The release is assembled from the original archive, with an explicit list of source replacements and new files. Runtime debris from the test directory is not copied into the release. Cache entries are omitted. `writer_room_audit/RELEASE_MANIFEST.json` records every released file hash, its original hash where applicable, and whether it was preserved, replaced, or added.

Rollback copies of the changed snapshot sources are in `build_backups/20260913_writers_room/`. The earlier HTML interpretation is preserved under `build_backups/20260913_before_exact_artwork/`; it is not the active screen. Each rollback directory has a SHA-256 manifest.

Do not unzip this candidate over a later Reach working directory. In particular, it must not roll back newer camera authority, Rust control, Foresight, or other work that exists outside the supplied snapshot. The release manifest identifies changes for selective reconciliation.

## 2. What changed

| Area | Change and resulting behavior |
| --- | --- |
| Original picture | `2i/2i-assets/writers-room-art.webp` is byte-identical to the upload. The screen scales this one picture and its overlaid controls together. It is not a generated replacement. |
| Button placement | `hotspots.json` defines 26 labeled controls and 7 live regions in original-image pixels. `artwork.js` validates bounds and binds actions; `artwork.css` places live content and suppresses the old HTML shell. |
| Live content | The editable manuscript, chapter heading, word count, references, partner conversation, suggestions, ideas, time, and connection state cover the picture’s sample content. Thus the shell is the same picture while its displayed information changes. |
| Manuscripts | New caller-owned SQLite storage under `reach_userdata/writers_room/documents.sqlite3`; document list, read, and revision-checked write APIs. Writes use a transaction. A stale revision returns 409 rather than replacing the stored copy. |
| Recovery and export | Account-scoped browser recovery and autosave history, `.2i` import/export, Markdown export, manuscript shelf, and explicit Save a copy for revision conflicts. References render as text rather than executing imported metadata. |
| Scene controls | Scene creation and rename, outline navigation, previous/next jumps, scene locks, and draft insertion/commit are wired. Navigation jumps within a single manuscript; it does not split the work into separate files. |
| Partner selection | The selected personal partner and its conversation history are carried through the real integrated PubPartner route. Changing partners restores the separate conversation for that partner. |
| Runtime ownership | The full host mounts the existing PubPartner router once and binds requests to its own spine. That spine receives the existing System Alex/Jeremy bridge and Cricket keeper; it does not instantiate a second coordinating pair. A separate standalone app cannot overwrite the full host’s request binding by reconfiguring a module global. |
| Model failure | Live calls request no deterministic fallback. Failure returns a failed result/503, and the UI reports model unavailability. Synthetic/offline/mock replies are not presented as genuine live generation by this UI. |
| Auth and exposed routes | The new launcher binds loopback and enforces existing local account auth. Document ownership and live-turn caller identity are checked. Newly exposed legacy backup/launch-check routes require owner authority, profile mutation requires mod authority, and user profile reads are caller-scoped. |
| Dependencies | Added `psutil`, missing from the declared environment and required by the supplied test/runtime imports. First-install launchers retry dependency installation after an interrupted installation. |

The gear opens model settings; the menu opens the manuscript shelf, import/export, rename, draft commit, and actual-size/fit control. Characters, Worldbuilding, Notes, and Scene Ideas use stored reference collections. “Insert” explicitly copies the latest assistant reply into the draft, without modifying locked manuscript lines. “Dismiss” hides the current suggestion for this open document/partner view; it does not delete conversation history. Its dismissal state is not durable across a reload.

The UI selects the integrated PubPartner adapter. The model service can still change inside that host. The original direct-provider adapters remain in the donor editor source but are not selectable in this room’s settings.

## 3. Identity and continuity contract

The user’s distinctions remain controlling:

- Personal PubPartner Alex is a relationship/language partner. System Alex is a coordinator with Jeremy.
- The full wired-in PubPartner host can use the shared coordinating pair. A bridge in that host is not inherently an error.
- The author can select another personal partner. Other partners must not inherit Alex’s personal identity or vessel merely because Alex’s lessons helped establish the design.
- Horizon is the portable host. Future docking is expected to reconcile experiences through the authoritative integrated services; this change does not implement that docking protocol or duplicate those services.

The new full-host spine uses a derived Cricket namespace scoped by authenticated user, friend, project, and room. Existing ambiguous namespaces are preserved rather than automatically migrated. The test provider spy confirms that a Craig request carries Craig’s profile and conversation history without Alex’s vessel. The host points at the preexisting bridge/keeper objects by identity.

Writer’s Room requests carry `content_kind=writing_request`. The vessel marks that content as fictional and automatic relationship-lesson extraction is skipped for writing/manuscript/fiction kinds. This is a concrete safeguard against turning invented scenes into personal biographical lessons. It is not a complete proof of every downstream memory, docking, or privacy behavior in the donor tree.

The launcher starts a new `reach_userdata/` directory by default. It does not silently use the snapshot’s old data folder or import the uploaded personal archive. Connecting a model and intentionally migrating verified continuity remain separate tasks.

## 4. Independent verification

| Check | Result | What it establishes |
| --- | --- | --- |
| Fresh environment from declared requirements | Initially failed collection: missing `psutil` | A real dependency gap, repaired in requirements |
| Supplied baseline gate after dependency repair | 27 passed | A working reference point for the selected supplied hardening tests |
| Final focused backend gate | **74 passed**, one upstream deprecation warning | Documents, revision conflicts, caller isolation, PubPartner profiles/history/provider failure, vessel integration, shared bridge ownership/lifecycle, and selected auth/WebSocket hardening |
| Editor component/state check | **9 PASS groups** | Exact words/spaces/title/references survive save/reload; partner histories remain separate; failed models do not invent assistant turns; locks resist editing; image-map actions insert/commit/navigate; invalid imports preserve work; reference metadata stays inert; stale revision preserves the server copy |
| Full-host HTTP process probe | **Passed** | Real loopback launch; owner setup; unauthenticated document rejection; actual document save/read; PubPartner runtime mounted; UI, map, and image served |
| Stop/restart in a fresh process | **Passed** | Persistent account, JWT secret/token validity, manuscript content, and revision survive process restart |
| Artwork byte identity | **Passed** in the DOM/state suite and over real HTTP | The released asset is the exact original picture described above |
| Browser rendering and physical clicks | **Not verified** | Browser access was rejected by the environment’s browser security policy. No workaround or alternate browser was used. JSDOM is a state/DOM test, not a screenshot or layout proof. |
| Live language model reply | **Not verified** | No local model service or cloud credential was connected. Unit provider spies and synthetic replies are labeled tests. |
| Windows/macOS launch | **Not executed** | Launchers are supplied; the actual runtime/restart probe was on Linux/Python 3.12.14. |
| Physical camera, Sheila, voxel rendering, Rust renderer, Horizon docking | **Not exercised** | They are outside this Writer’s Room change and must not be inferred from a successful boot. |

The 26 mapped controls have accessible labels and callable handlers. The map rejects duplicate IDs, unknown actions, invalid dimensions, and out-of-image rectangles. Its scaling test verifies the same coordinate transform for artwork and controls; it does not establish pixel-perfect visual placement. The user has offered to provide a marked guide; no annotated guide had been received when this candidate was packaged.

The original smoke tests expected an empty live message to return success and previous history to be ignored by a compatibility handler. Those expectations were deliberately changed: an empty message is rejected, and prior conversation is preserved by the real route. Test providers are explicitly synthetic. A green result must not be interpreted as a model-generation test.

A preliminary HTTP probe attempted `/api/peq/health`, which is not an established endpoint in this snapshot. Its 404 was not evidence of PEQ success or failure. The final Writer’s Room probe does not make a PEQ claim.

## 5. Reproduce the checks

Use a separate environment and disposable data. The evidence bundle includes full output, not just counts. The tested Linux package versions are in `writer_room_audit/requirements-tested-linux.txt`; this is an environment record, not a portable Windows requirements lock (`uvloop`, for example, is platform-specific).

```bash
python3 -m venv .audit-venv
.audit-venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.audit-venv/bin/python -m pytest -q \
  tests/test_reach_writers_room.py tests/test_pubcast_smoke.py \
  tests/horizon_ref_pubpartner_routes.py tests/horizon_ref_pubpartner_live_loop.py \
  tests/horizon_ref_pubpartner_spine.py tests/horizon_ref_pubpartner_vessel_routes.py \
  tests/horizon_ref_pubpartner_vessel_integration_unittest.py \
  tests/test_04_websockets.py tests/test_bubble_route_hardening.py \
  tests/test_main_route_authorization_parity.py tests/test_system_memory_conductor_wiring.py \
  tests/test_shared_bridge_lifecycle.py tests/test_full_host_shared_bridge_lifecycle.py \
  tests/horizon_ref_auth_productization.py
.audit-venv/bin/python tests/probe_reach_http.py
npm --prefix writer_room_audit ci
npm --prefix writer_room_audit test
```

The recorded JSDOM package requires Node `^22.22.2 || ^24.15.0 || >=26.0.0`; Node 24.19.0 was used here. The HTTP probe creates a disposable directory, uses synthetic credentials without printing the password/token, stops its process, and removes its temporary data. The component test uses a fake API store and synthetic provider responses. It now includes a completion deadline so an unfinished async test cannot silently exit with an apparent pass.

## 6. Canonical-base decision and remaining gates

**The original PR #2 verdict remains HOLD for the reviewed donor commit `8920494ba7594221f7985f22fa6ce3ad89b2c386`.** The earlier saved audit found that its PEQ import correction and BOM cleanup were real, but its boot/API claims were too narrow: important authorization, PEQ room delivery, timeline effects, Vision, Studio, and lifecycle defects remained. Those findings apply to that pinned NowCurtsey revision. They must not be casually relabeled as defects in later Reach repairs.

This work independently runs a focused gate against Reach and supplies a working Writer’s Room candidate. It does not repeat the original complete-tree audit for every subsystem of the assembled Reach source, and therefore does not authorize promotion of the whole build to the canonical base.

Before that promotion:

1. Reconcile this delta with the actual latest Reach source, including the newer camera and hardening changes described by the later handoff. Preserve the separate Foresight work.
2. Open this exact artifact in a real browser, check alignment at the intended screen sizes, and apply the user’s annotated button guide. Exercise writing, archive controls, locks, reload, and a conflicting edit in two windows.
3. Connect the intended model service and verify real replies through the selected partner with retained history and no unintended identity changes. Keep server readiness distinct from successful generation.
4. Verify any desired personal archive migration from provenance-preserving copies, with an explicit relationship/system separation. Do not infer successful personal Alex installation from a dropdown name.
5. Rerun the whole-build readiness audit on the final reconciled Reach revision, including important studio/camera/PEQ/timeline paths and the remaining memory/docking boundaries. A passing Writer’s Room gate cannot substitute for those checks.

No merge, push, deployment, external comment, or message to another person was performed. The delivered files are a reviewable local candidate and its evidence.
