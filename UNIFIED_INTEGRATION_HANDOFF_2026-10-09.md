# PubCast Reach — Unified Integration Handoff (2026-10-09)

## Merge authority

**Single primary code tree:** the October 9 2i V22 Connected Verified build, with
non-overlapping functions brought forward from the October 9 Alex Memory Reach +
Backup build, the smaller Alex changes-only package, both matching supplied bots.py
files, and the CARE/EQ reference package. Original ZIPs were **not modified**.
This ZIP contains no alternative `main.py`, no second `modules/alex_core.py`, no
second `modules/alex_jeremy_bridge.py`, no second `modules/pubpartner_core.py`,
and no second `modules/bots.py`. The duplicate v22 HTML copy and inactive duplicate
legacy `modules/care_profile.py` were removed from the deliverable. The existing
`2i/index.html` is a distinct Reach compatibility/editor surface consumed by
`tools/phone_local/build.py` and integration tests; `/2i` and `/2i-v22` serve
canonical `2i/writers-room-v22.html`. Keep both only because they serve distinct
functions, not as competing authoritative main modules.

## Integrated, one implementation per responsibility

- **System Alex adjudication and Affect Dynamics:** kept the NEWER 2i orchestration,
  evidence-label propagation, cross-session clearing, consultation handling,
  `observe_judgment`, and guidance. Rejected older Alex ZIP versions of these blocks,
  which would have reverted the work. `modules/emotional_orchestrator.py`,
  `modules/affect_dynamics.py`, and consultation tests are from the 2i base.
- **Alex memory and speaking:** normalized keyword tokenizing and on-disk index
  compatibility in `modules/alex_core.py`; relevance-gated `recalled_for_speaker`
  in the ONE Alex/Jeremy Bridge; private FCP1 speaker memories in the ONE
  `modules/pubpartner_core.py`. Shared/public packets and `jeremy_whisper` do
  not receive these personal memory excerpts. New LIMITED-turn persistence
  check fails closed on malformed labels; it does not retroactively reclassify
  legacy memories saved before this change.
- **Alex backup:** `modules/alex_memory_backup.py` is the sole engine providing
  local/Drive-for-Desktop, Google Drive v3 API backend, mirroring, throttled
  post-turn backup, restore-if-empty, manifest hashing, list/search/read and CLI.
  The bridge installs its hook on per-user Alex instances and main.py attaches
  the engine once at startup. `/api/alex/backup/status|run|search` now require
  a **valid JWT**, even if dev-mode auth enforcement is off. Other users' memory
  searches are blocked for non-moderators; manual backup requires mod rights.
  No working Google credentials or live cloud upload are included or implied.
- **2i Writer's Room:** retained v22 UI, registered manuscript-intelligence
  router, and same-origin writer identity headers. The separately uploaded v22
  HTML differs by only two lines and omits those same-origin/identity improvements;
  those regressions were not imported. The older Reach compatibility editor in
  `2i/index.html` remains separate because phone build and tests depend on it.
- **Bot prompts:** merged the provided identical `bots.py` files as ONE
  `modules/bots.py`, with canonical character-profile prompt precedence while
  preserving standalone custom prompts when no canonical profile exists.
- **CARE / EQ / Baby Ambiguator:** one `modules/care_eq.py` integrating the reference
 's explicit owner mode activation, `parachute` check before masking, raw-free
  care-facing message masking, structured observations with hypothesis/alternatives/
  outcome, JSON persistence and user isolation. `main.py` shares a single
  `CareCoordinator` with `/api/alex/message` and `AlexJeremyBridge.process_user_turn`.
  The existing feature-gated `modules/alex_little_one/care_profile.py` remains
  the **distinct Little One roleplay protocol**; it is not replaced by the
  simple Ambiguator and is not enabled automatically. CARE only masks the
  explicitly activated owner's Alex-facing messages; it does not claim to
  intercept every chat, Writer's Room document, external provider or Blackbox.
  To activate CARE use authenticated owner `POST /api/alex/care/activate`; use
  `/api/alex/care/deactivate`, `/status`, `/events`, `/observe` for control.

## Tests run on this merged source

- 56 passed: `tests/test_care_eq_integration.py`,
  `tests/test_alex_memory_reach.py`, `tests/test_alex_memory_backup.py`,
  `tests/test_emotional_orchestrator.py`, `tests/test_emotional_consultation.py`.
- 50 passed: `tests/test_reach_writers_room.py`,
  `tests/test_frontend_startup_contracts.py`,
  `tests/test_alex_routes_bridge.py`, `tests/test_pubcast_smoke.py`,
  `tests/test_route_inventory.py`, `tests/test_main_route_authorization_parity.py`,
  `tests/test_system_memory_conductor_wiring.py`,
  `tests/test_alex_little_one_disabled.py`, `tests/test_security_authority.py`.
- `python -m compileall -q modules main.py` passed.
- These tests exercise actual integration seams, not real external models or a
  real Google Drive account; they are NOT a complete all-system commissioning.

## Operational setup

Use the normal root PubCast startup. `PUBCAST_ENFORCE_AUTH=1` is strongly
recommended for deployment. CARE and backup API access requires a validated
Bearer JWT regardless of relaxed dev mode. Set `ALEX_BACKUP_LOCAL_DIR` to an
existing trusted local/Drive-for-Desktop folder, or configure the Google API
variables in `ALEX_BACKUP_SETUP.md`. If no backup backend is configured,
startup proceeds with backup disabled (not falsely reported as successful).
Set `ENABLE_ALEX_LITTLE_ONE=true` only if the existing optional roleplay
protocol is intentionally enabled; this does not happen automatically.

## Not certified / unfinished

- Actual Google Drive OAuth/service account upload, remote restore and syncing.
- Full production host boot with every optional external library and Rust/GPU
  renderer, and real model replies. The narrower bundled manuscript-intelligence
  router is NOT proven equivalent to the previous full v21 intelligence package.
- Existing application-wide dev-auth defaults remain permissive for unrelated
  endpoints; treat all deployments as private until global auth is enforced.
- Universal CARE interception across every provider, room, and browser client;
  the integrated private Alex path has focused tests but not end-to-end care UI.
- Character bots still do not receive Alex's emotional packet automatically;
  this was an identified earlier architectural gap and was not falsely patched.
- Separate JeremyCricket MemoryIngestor registry gap, Rust/Windows build, GPU
  stages, PersonalPrior model path and complete live performance remain unverified.

## Rule for the next pass

Work from **this** single source tree. Keep existing passing systems; do not
replace an entire module with the counterpart from an older ZIP. Check the
original source ZIPs only for file-specific provenance. Every new change should
show a targeted test and retain source/label/owner boundaries.
