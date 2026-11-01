# Foresight / PubCast Reach — commissioning challenge audit

**Date:** 2026-10-09 (release label). **Input:** `PubCast_Foresight_COHESIVE_2026-10-09.zip` (999 archive entries, valid ZIP).
**Deliverable:** A *single patched source tree*, with one authoritative Reach server and Foresight front door. This is a hardening/audit build, **not** a statement that the whole studio is production commissioned.

## Method and authority

This pass audited the supplied ZIP, not a guessed project snapshot. It traced `run_reach.py → main:app → Foresight portals → gateway / CARE / Alex / BotManager / Hub / optional Node`, compared advertised capabilities against code, tested auth and foreign-user attacks, performed targeted tests, ran the broad repository pytest suite, compiled Python, parsed Node, ran its mocked contract tests, and booted a real loopback Reach server with a new owner account.

No wholesale module replacements from older source ZIPs. Existing Alex emotional/affect, memory/backup, manuscript and CARE implementations remain. A new *private conversation transcript store* is a distinct data-security responsibility, not a second character engine. Byte-identical old federation source and test duplicates were removed; the historical manifests remain as records of their original releases, not as authoritative manifests of this patched build. The optional 2i Node sidecar still owns distinct legacy utilities; its duplicate character endpoints are disabled **when managed as the Reach sidecar**.

## Confirmed integration defects corrected

| Severity | Finding on the supplied build | Correction in this release | Verification |
|---|---|---|---|
| **Critical** | Foresight direct character chat read `Hub.get_recent_history(room_id)` for arbitrary caller-supplied room, allowing unrelated room content into the model's prompt. | Direct bot calls now use **private owner + bot + conversation scoped SQLite histories** under `reach_userdata/private_character_transcripts/`. No public Hub room history is loaded or written. Both `/api/bots/{bot_id}/chat` and the Foresight gateway use the same `modules/character_service.py`. | Adversarial test plants unrelated studio secret and checks model prompt; verifies different users cannot retrieve it; checks persistence and direct-room log absence. |
| **High** | `Hub._log_path()` built a filesystem path directly from unchecked room IDs, permitting separators/traversal in a shared primitive. | Reject invalid, traversing and Windows-reserved room names before resolving the path. | Traversal/drive/device-name test. |
| **Critical** | Alex `/message`, `/memory/recent`, `/state`, `/grounding` selected a user-supplied profile without binding it to the authenticated user. One endpoint only checked ownership if CARE was active. | Require verified identity on every route; default to the caller; prevent speaking/grounding for others. Owner can perform explicit read-only state/memory inspection, while reset additionally requires real moderator rights. CARE scope stays stricter. | HTTP tests exercise no-token, wrong-user and legitimate owner calls; live server verified anonymous 401 and owner 200. |
| **High** | Global Node legacy `/api/messages` could be proxied to any signed-in role; manuscript and provider utilities also lacked role separation. | Owner/admin required to forward global legacy messages, clear, manuscript commit and paid model proxy; allowlisted thesaurus remains available to signed-in users. | Gateway authorization tests, including guest 403. |
| **High** | Direct character service accepted role-privileged identity override in the alternate `/api/bots` entry; plus the shared `bound_actor()` treated an absent `X-Client-Id` header as an actual mismatch for guest JWT holders. | Forbid direct-chat speaker overrides even for owner; only compare header to token when an actual header was supplied. | JWT-only normal-user and impersonation tests. |
| **High** | Character UI accepted an arbitrary `bridge=` URL query value, potentially sending conversation text to another host if linked deceptively. | Character UI uses fixed same-origin Foresight gateway; Foresight launches it without a query URL override. | Static and HTTP gateway checks. |
| **Medium** | Character message metadata interpolated directly into `innerHTML`, and provider key indicators used a missing field, reporting false configuration problems. | Metadata is inserted via `textContent`; server returns a credentials-presence boolean without exposing keys; local Ollama remains *unverified* rather than incorrectly described as configured. | JS syntax and Foresight-focused tests. |
| **Medium** | Character chat history existed only inside the page during a session, and the model request did not append its own private reply to a proper direct conversation. | Persistent private dialogue and authenticated history retrieval added; Foresight character selector can reload the most recent messages after opening. | Isolated DB persistence and live owner history endpoint checks. |
| **Medium** | Browser-facing Node duplicate character endpoints were still present on the optional sidecar, creating two active character surfaces. | `PUBCAST_SIDECAR_ONLY=1` disables Node character listing/replies when Reach supervises it. Standalone Node compatibility remains for historical test contracts, but canonical Foresight characters are always handled by Python BotManager. | Node syntax and contract checks, static sidecar lifecycle check. |
| **Medium** | Public bot listing returned entire character configurations including system prompts and operator metadata. | In the authenticated host, ordinary participants receive a reduced metadata projection; authenticated mod/admin/owner can inspect full configs. | Main route smoke/parity tests. |
| **Reliability** | Full pytest run passed assertions but emitted an asynchronous `session.tmp` → `session.json` rename error at shutdown. The timer and exit handler used the **same temporary filename** without serializing writes or first stopping the worker. | Recorder now locks all writes, wakes and stops its flush worker before final flush, and unregisters the shutdown callback on clean stop. | New tests run eight parallel flushes, assert preserved event JSON and final stop, and exercise the atexit handler. The subsequent full pytest run had no trailing flush error. |
| **Canonicalization** | The archive included a byte-identical duplicate of `pubpartner/pubpartner_federation` and its tests in `pubpartner_verified/`. Worse, `conftest.py` imported the duplicate copy during tests. | Removed the redundant verified folder; tests now import the canonical `pubpartner/pubpartner_federation` code. The original ZIP remains untouched. | Bytewise SHA-256 comparisons across seven modules and three test files; 18 federation/privacy focused checks; final broad suite. |
| **Test defect** | One static-route test marked dynamic route prefixes `/api/alex/care/` and `/api/foresight/bridge` as absent. | The test now checks registered child routes for known prefix patterns; real endpoint tests remain separate. | Full suite. |
| **Minor UI** | The only Writer’s Room top tab, “Manuscript,” was a clickable-looking button without any handler. | Converted to a static current-section label; no inoperative control pretending to navigate. | HTML contract and existing 2i tests. |
| **Test defect** | Node contract test's mocked `listen()` assumed 2 parameters; Node server properly called `listen(port, host, callback)`. | Adjusted mock signature; did **not** hide the test failure or rewrite the runtime to please its mock. | Node mocked contract: 6 passed, 1 skipped due absence of live paired service. |

### Explicit data-handling note

The new direct-character SQLite DB is durable, owned by the current Reach data directory, uses private POSIX directory/file permissions where available, and is *not served through ordinary Hub room history*. It is **not encrypted at rest**. Its contents are **not included in current Save All / Google Drive Alex memory backups**. The normal BlackBox event API is notified on a best-effort basis if available; a fully durable witness reconciliation process has not been verified. Model failures preserve the user’s text, which remains visible in the private archive on reopening.

## File provenance and change footprint

Relative to the 999-entry input ZIP, this hardening changes **19 existing files**, removes **10 byte-identical archived federation/test copies** in `pubpartner_verified/`, and adds the privacy-regression tests plus the audit, startup guidance, and fresh audited checksum manifest. The canonical Python entrypoint remains root `main.py`, `modules/bots.py` is still the sole BotManager implementation, and the original System Alex, PubPartner memory and emotional modules have **not** been overwritten. Existing historical `FORESIGHT_FILE_MANIFEST_SHA256.json` and `MERGE_FILE_MANIFEST_SHA256.json` are preserved as prior-release records; use **`AUDITED_FILE_MANIFEST_SHA256.json`** to check this patched package.

## Runtime checks actually performed

- Real `run_reach.py --no-browser --no-legacy-2i` host boot using a clean data directory and free loopback port.
- HTTP 200: `/foresight`, `/pubpartner`, `/writers-room`, `/static/foresight_care.html`, `/api/foresight/bridge/health`.
- HTTP 401 as anonymous: private character history, Alex state, Alex recent memories.
- Real initial owner creation: HTTP 201; subsequent authenticated characters, PubPartner status, CARE status, Alex memory and character history endpoints: HTTP 200.
- CARE activated and deactivated successfully on that authenticated owner account.
- Python import/compile checks; Node source syntax check; ZIP integrity checks on both original and outgoing packages.
- Broad Python suite: **964 passed, 2 skipped** after recorder shutdown hardening. This is the **final complete run after removing byte-identical federation copies and repairing the recorder shutdown path**; no failures or trailing recorder errors were reported. The skipped tests belong to an opt-in Little One research protocol; they are **not** hidden failures. The test suite uses relaxed mode because legacy unit tests intentionally exercise developer compatibility. A separate live-host check verifies enforced-auth behavior; forcing auth during the *developer-mode* suite caused unrelated 401 expectation failures and is not represented as the normal regression result.
- Attempted headless Chromium walkthrough was **blocked by container policy** (`net::ERR_BLOCKED_BY_ADMINISTRATOR` on localhost). It is **not** a passing UI click-through, and is not counted as an application bug.

## Gaps deliberately NOT represented as working

### P0 — privacy and archival completion before multiuser release

1. **Export/backup:** private direct character transcripts need user/owner-controlled Save All, restore and protected backup behavior; presently the data is durable only within the Reach host's own data directory. Decide encryption and retention for sensitive conversations; don't silently add them to Alex's different memory backup scheme.
2. **Broader authorization review:** the official `run_reach.py` forces `PUBCAST_ENFORCE_AUTH=1`, but direct `uvicorn main:app` still inherits historical relaxed-development defaults. Production operators **must** use the launcher or set auth enforcement explicitly. This pass corrected specific IDORs; it did not formally prove every API and WebSocket route is free of authorization issues.
3. **Global DM experience:** Character Chat's DM selector includes hard-coded names. Its request creates a real DM request/grant in the core subsystem, but this page does **not** yet provide a complete accepted-channel viewer. Do not call that UX fully integrated. The separate PubChat DM permissions remain the authority.
4. **Concurrent direct turns:** SQLite storage transactions are cross-process safe; model-generation order for simultaneous requests to the *same* private conversation is not serialized. A rapid multi-tab conversation could interleave messages; concurrency ordering/idempotency still needs a workflow test and design.

### P1 — actual provider and peripheral integration

5. **Real inference:** no live OpenAI/Anthropic/Gemini/Ollama/GGUF response demonstrated with owner credentials, and the character prompt path uses the same existing BotManager but not the complete Alex affect packet. PubPartner/Alex remains a separate specialized character context via its existing spine.
6. **2i Node service:** missing `2i-backend/node_modules/express` here. Its standalone route contracts pass under mocks, but actual npm-install, process lifecycle, proxy round-trip and unique thesaurus/manuscript utility calls were not exercised. The unified launcher can supervise it, but this is not a verified live outcome.
7. **2i Writer’s Room:** the v22 UI and manuscript endpoints are served from Reach. This does not prove the complete earlier manuscript intelligence feature set is mounted, nor that browser-direct Ollama endpoints work on a separate phone; that code still has `localhost:11434` assumptions.
8. **CARE/Little One:** explicit CARE activation, masked observations and Alex/Jeremy bridge seam work. Complete Little One roleplay, human-like emotion inference and universal intercept across PubCast rooms/providers are not enabled or verified. `ENABLE_ALEX_LITTLE_ONE` is a distinct research feature gate; don't equate it with CARE's shorter semantic mask.
9. **Alex memory backup:** local/Drive-for-Desktop functionality has tests, but real Google Drive OAuth/API uploads and remote restore were not tried; neither were historical-memory migration or owner-on-device key configuration validated here.

### P2 — full production studio commissioning

10. **Studio/world/avatars:** Foresight provides the original portal entry points. Some underlying voxel, camera, facial-performance and wired legacy modules still explicitly say `placeholder`, `TODO` or `stub`. No real webcam, microphone, Windows/Rust build, renderer, GPU choreography or full show playback was commissioned.
11. **Windows/offline installation:** provided BAT and `start_reach.py` are source/virtualenv installers, not a standalone offline executable. First run requests pip dependencies from the internet and optional Node utilities may request npm packages. Windows launch and older/low-resource hardware performance are not verified in this Linux host.
12. **Browser layout/accessibility:** HTML/JS source checks and HTTP serving are confirmed. Actual graphical interactions on Android/Windows, touch/resize behavior, focus management and visual overflow await an environment that permits browser navigation.
13. **Observability/recovery:** ongoing log reconciliation after partial BlackBox/AI side-effect failure, private transcript backup, bounded CARE event retention and cross-worker orchestration need dedicated hardening before a public multiuser deployment.

## Recommended next real work (not a request to restart the audit)

Keep this single source tree. First finish the *private transcript export/backup + DM UI* surfaces and reverify identity boundaries; then run a genuine owner-computer model inference through both Foresight Character Chat and PubPartner Alex. After those pass, commission the optional Node writer utilities and production studio devices separately. Do not roll back System Alex's adjudication to obtain an easier bot reply; do not hide incomplete studio paths by changing labels to “verified.”

**Final status:** Foresight is a functioning authenticated **integration host and navigation shell** with several live, tested subsystems. The entire PubCast virtual production stack is **not yet production commissioned**.
