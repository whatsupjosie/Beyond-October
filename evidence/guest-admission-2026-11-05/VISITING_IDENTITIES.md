# Independent human visits — executed checkpoint

Signed: Codex / ChatGPT Work, 2026-11-05. No main merge, deployment or Actions.

## Result and boundary

RAN the combined selection below on the frozen application source: **109 passed,
one Starlette/AnyIO deprecation warning, 99.14 seconds, exit zero**. Raw output
and JUnit: `guest-checkpoint-final.log` / `.xml`. This is focused integration and
regression validation; it is neither required post-feature whole-codebase round.

The selection covers actual independent host processes, each with its own data
root, sole local owner, permanent ID, encrypted identity key and JWT secret.
Browser acceptance exercises invitation creation, popup signing on the visitor's
own origin, explicit recording/AI/terms/data consents, key comparison, owner
approval, phone layout, a read-only visiting profile, revocation and redirect to
sign-in. API tests verify private notes delivered to the visitor, no new local
password account, wrong-host credentials refused and guest owner powers refused.
Live socket tests reject both incoming messages and unsolicited outgoing frames
after revocation, including an already connected idle receiver.

The full pre-existing two-source recording acceptance also runs with **two
separately owned and admitted guest IDs**, instead of the owner's token:
mix/fader/EQ/mute/solo controls, overlapping tones, reconnect during capture,
independent pre-fader segments, actual FFmpeg decoding, Program mix, resumable
original server save and exact original bytes in the ZIP all passed. Its isolated
run passed in 31.71 seconds; the final combined run includes it again. Browser
oscillators replace physical microphones only. This does not certify physical
devices, WAN links or sample-accurate cross-device synchronization.

## Design and provenance

Compared three real identity approaches. Continuing local crew passwords would
contradict the owner's one-owner-per-copy model. A central identity provider
would require unavailable infrastructure and compromise independent/offline
operation. Chose own-copy Ed25519 keys, a one-use host challenge and an explicitly
approved visiting card; returning IDs are pinned to the first admitted key.

The ID remains the existing `u_` plus twenty hex characters; it is never
regenerated merely to add a key. The signature proves possession of that key,
not a real-world identity or globally certified human. The owner sees a first-
visit warning and the same fingerprint the guest sees. Host approval is still
required by default; the owner may explicitly let valid invitations enter.
No central directory or remote-host fetch/SSRF path was invented.

Local source comparison found the existing PubPartner federation identity to be
resident/portable node metadata, not authenticated human admission. Targeted
search of the owner's repositories found no reusable human visiting proof.
The existing GovernanceEngine remains admission authority. Its SQLite database
also owns invite use, challenge replay fencing, public key pins and guest leases.
Use and request creation commit together; duplicate submission is idempotent.

Private keys extend the **existing CredentialStore** and its Fernet master key,
not another vault. Atomic creation publishes complete encrypted files without
replacing the winning key. Fixed a master-key creation race in that same store;
twelve competing store instances keep one key, corruption fails explicitly,
and existing credential/checkpoint recovery tests still pass. Private keys never
enter the profile, visiting proof, model registry, browser or repository.

Only explicit shared fields travel; a private card carries only essential name,
handle and ID. Photos are not copied between hosts in this checkpoint. Profiles
cache admitted cards without creating `users` rows, and an older ticket cannot
overwrite a newer cached card. Guests edit their profile/password on their own
copy. Host-issued guest tokens are checked against durable admission on every
decode; the socket transport also checks before every incoming/outgoing frame.
Tokens stay out of URLs. The popup checks source window and exact home origin;
the signer posts only to the challenge's host origin. Manual exchange remains
available when a popup is blocked.

POST `/api/production/people` now returns 410 to privileged callers and directs
them to invitations. Existing local users, IDs, profiles and notes are retained;
no destructive identity migration or conversion is performed. Old notes tests
now explicitly seed pre-existing legacy accounts, while separate new acceptance
uses independently admitted visitors. Internal legacy DB helpers remain for
migration/regression compatibility; no new HTTP crew-account creation is offered.

## Corrections and limits

The first core run caught a real issue: session bans live in GovernanceEngine's
process memory and were missed by a database-only guest check. Validation now
checks current governance as well as durable bans. **Cross-worker session-ban
propagation and stale ban/unban caches remain an explicit targeted-debug gap**;
this checkpoint does not certify multi-worker moderation. Explicit guest-lease
revocation is durable and tested, including a second service reading that lease.

The first popup/browser runs reached approval and revocation, then failed in the
test observer. It expected an inline error even though shared auth redirects to
sign-in; it then called ReachAuth on a login page which intentionally uses its
own fallback. Corrected the observer to wait for the actual sign-in form and read
the real sessionStorage token. No product permission or assertion about removal
was weakened. Earlier failed outputs are retained alongside passing output.

Still open: own guest dressing-room/avatar customization acceptance; contact/DM
request UI and blocking; signed human cartridge portability/recovery UX; guest
photo transfer; actual studio entry after the shown Enter button; manual-exchange
browser acceptance; native Windows/PowerShell 5 and non-NTFS atomic-key behavior;
long sessions/network failure; complete replayable source-master/native render
gates; production groups, departments, schedules and note placement; their
targeted debugging; **both post-feature whole-codebase rounds**.

## Exact final test selection

`PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q tests/test_guest_identity.py tests/test_guest_identity_routes.py tests/test_identity_credentials.py tests/test_independent_guest_hosts.py tests/test_independent_guest_browser.py tests/test_governance_admission_persistence.py tests/test_human_profiles.py tests/test_human_profiles_browser.py tests/test_human_profile_onboarding_browser.py tests/test_production_notes.py tests/test_production_notes_browser.py tests/test_full_host_route_authority.py tests/test_main_route_authorization_parity.py tests/test_websocket_cookie_auth.py tests/test_three_solution_rounds_auth_foundation.py tests/test_host_control.py tests/test_strict_guards.py tests/test_data_checkpoint_host_recovery.py tests/test_admitted_guest_recording_browser.py --junitxml=../guest-checkpoint-final.xml`
