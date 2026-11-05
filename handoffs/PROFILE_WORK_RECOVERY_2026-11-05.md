# Profile work recovery — workspace interruption, November 5, 2026

Signed: Codex / ChatGPT Work. This is a recovery record, not implemented guest acceptance.

## Last durable application source

Branch `chatgpt-work-2026-11-05`, published application commit
`f997d5418903522d62a2aa10e4afc9755800ee09`, tree
`ab251b65a2b294ffb75d4975ac3ee971a93c001d`.
That is identical to local `aacf59d`. The preceding recording reconciliation is
`c5589bbefa56f1de4ac4e7d85daccfb5c00a8963` (local `0a4f89e`).

The full Python/browser integration suite on this frozen application finished:
**2,328 passed, six skipped, zero failed, sixteen subtests passed**, 217 warnings,
921.01 seconds, exit zero. The six skips: two explicitly disabled Alex research
modules, three explicitly configured real-model speech cases, one optional audio
decoder dependency case. This is not either post-feature debugging round.

## What became inaccessible

The environment changed to unavailable during the next profile UI patch/test
operation. The pending orchestration was canceled after it stopped returning.
Do not assume that the last patch completed or that its dependent browser test
started. No profile application changes were published before this interruption.

Last workspace: `/workspace/scratch/d6f0985b33b2/pubcast`.
It was on local `aacf59d` with uncommitted profile work. If that workspace returns,
inspect its actual status and file contents before replaying or rebuilding.

Confirmed local writes before the unavailable environment:

- New `modules/human_profiles.py`: strict optional human profile schema, private
  discovery defaults, explicit public-field selection, bounded text and HTTP(S)
  links, still-image validation/resizing/metadata removal.
- `modules/userdb.py`: additive profile columns `details_json`,
  `profile_revision`, `photo_data`, `photo_sha256`; old permanent IDs remain.
  Atomic revision checks reject stale edits; photo bytes stay in the existing
  user database so the existing backup scope includes them.
- `modules/production_notes.py`: extend existing /api/profile/me rather than
  creating another authority; profile discovery and photo routes honor opt-in
  field visibility. Anonymous requests and private-photo reads are rejected.
- `requirements.txt`: Pillow is a runtime dependency for profile-photo validation.
- New `tests/test_human_profiles.py`: four real SQLite/API tests using the
  existing notes fixture.
- `modules/auth_routes.py`: setup visibility choice, permanent user ID in
  setup/login/verify responses.
- `static/reach_auth.js`: preserve the returned permanent ID in browser session
  metadata while keeping the legacy username-based authenticated actor behavior.
- `static/login.html`: explicit private/discoverable choice and navigation to
  optional profile onboarding after first owner setup.
- New `static/human_profile.html` and `static/human_profile.js`: optional fields,
  explicit sharing, normalized photo upload, same-origin profile pictures,
  click-only embedded reels, session-scoped drafts, phone layout and host-scoped
  discovery. These UI changes were written but have no executed UI acceptance yet.
- `static/foresight_programs.js`: profile as an existing-style singleton tray.
- `static/foresight_counter.html`: an initial profile menu entry.

The last **unconfirmed** patch was meant to move the profile entry to a compact
Me menu, fence stale restored draft revisions, preserve drafts during a photo
upload, and add `tests/test_human_profiles_browser.py`. Inspect before assuming
any of those changes exist. Its intended test command was:

`PLAYWRIGHT_NODEJS_PATH=<installed-node-path> .venv/bin/python -m pytest -q tests/test_human_profiles_browser.py tests/test_websocket_cookie_auth.py tests/test_three_solution_rounds_auth_foundation.py tests/test_production_notes.py`

No result exists for that command in the observed session.

## Actual profile evidence before the later auth/UI edits

Executed:

`python -m pytest -q tests/test_human_profiles.py tests/test_production_notes.py`

Observed: **15 passed, one warning, 8.70 seconds**. The new checks cover private
migration with stable IDs, explicit field disclosure without email, stale edit
rejection and atomic invalid-link failure, private/normalized photos, upload
size/content validation and photo revision fencing.

Local artifacts, if accessible again:
`../profiles-backend.log` and `../profiles-backend.xml`.
The complete recording baseline log/XML were copied locally to
`evidence/clacker-integration-2026-11-05/recording-wide.log` and `.xml`
after the published application commit; they were not uploaded before access was
lost. Their final summary was directly observed and is recorded above.

The 15-pass result belongs to the initial backend profile stage. It does not
verify the subsequent auth response changes or UI.

## Contracts to preserve when resuming

Human profiles are distinct from PubPartner AI profiles. Optional fields:
real name, nickname, pronouns, city, professional/hobbyist/learner, biography,
education, skills, résumé, hobbies, favorite books/movies/podcasts, internet
recommendations, current projects, dream project, desired collaborations,
website, portfolio, LinkedIn, reel and a photo/avatar. Real name is optional.

Discovery is off by default. Public fields are independently selected; email
does not enter discovery. Current search is explicitly scoped to this host,
not a fabricated global directory. Third-party reel assets load only after the
user clicks. Private profile drafts remain scoped to this browser tab and UID;
a restored stale draft must retain its old revision so saving cannot silently
overwrite a newer server profile. Photo upload must not discard other edits.

Photo limits implemented in the initial backend: 2 MB input; still PNG/JPEG/WebP;
maximum 2048 pixels per side; normalized image at most 512 pixels per side,
stripped metadata, served as PNG with private/no-store and nosniff headers.

Profile details schema is strict, rejects unknown/control fields, bounds all
text and total JSON to 24 KB, and rejects unsafe/credential-bearing links.
Permanent IDs cannot be changed by a profile update. Existing notes and old IDs
must survive migration and restart.

## Still outstanding — do not claim these are built

- One owner per independent copy, real invited guest identity, admission and
  guest privacy. Existing local crew-account creation is still the old model.
- The actual user-owned human cartridge / signed visiting-card mechanism.
  No crypto, invitation or cross-host identity implementation was completed.
- Real independent guest recording acceptance: recovered browser voice tests
  still share the owner's token.
- Production groups, role/department addressing and structured schedule notes.
- Connections/contact-request journey and shared notifications as needed.
- Full guest/profile/group targeted debugging and both post-feature whole-code
  debugging rounds.
- Cross-device clock alignment, asset-complete source masters and hardware gates.

Inspect existing `GovernanceEngine` and its full-host waiting-room adapters
before adding admission state. They are the existing admission authority.
Likewise inspect `modules/chat_rooms.py` before adding contact/messaging state:
DM request/accept/decline machinery already exists. Keep Base and Horizon
independent. Do not replace existing note artwork, counter geometry or 2i.

Resume by recovering the uncommitted working tree if possible, testing the
profile auth/UI changes, then implementing actual guest identity and joining it
to the existing admission authority. A fresh runtime cannot treat these recovery
notes as a substitute for source or executed tests.
