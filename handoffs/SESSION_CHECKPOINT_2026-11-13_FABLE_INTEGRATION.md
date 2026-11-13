# Session checkpoint, 2026-11-13, Fable integration run

Written for a cold reader. Every line says whether it was verified by running it, only read, or only listed.

## Where the work is

- Branch: `fable/integration-2026-11-13`, created from `11-12-merge` at `d70952e52c81f89178f4ab557206fcde109bf970`.
- Commits on it: `082b622` (the Alex fix below) and the commit that adds this file.
- `main` is unchanged at `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae`. Nothing was merged, force-pushed or deleted. No other branch was touched.
- Environment for everything below: Linux sandbox, Python 3.13.18, `requirements.txt` + `requirements-dev.txt`, fresh throwaway data folders. Not Windows, not PowerShell, no real camera or microphone, no model server (Ollama unreachable), no speech packages.
- No GitHub Actions were used.

## What was NOT read

- `ABOUT.md`, `QUALITY_STANDARDS.md`, `ENGINEERING_HANDOFF_BEYOND_OCTOBER.md`: not read (budget). `STATUS.md`: first 60 lines read.
- From the private handoff ZIP: only `00_EXECUTE_NOW_FABLE.md`, `GITHUB_BRANCH_SNAPSHOT_2026-11-13.md` and `01_GAPS_AND_REQUIRED_INPUTS.md` were read. The two 2026-11-13 documents (`First_Person_Account_Contextual_Recall_2026-11-13.md`, `Alex_Original_Portraits_Witness_Statement_2026-11-13(1).md`), the earlier witness statement, the redundancy audit and `ALL_TEXT_HANDOFF_BUNDLE_2026-11-12.md` were unpacked and left intact but NOT opened. Their provenance is the ZIP's own `SHA256SUMS.txt` and `SOURCE_MANIFEST.json`. None of the ZIP is in this repository.

## What boots (verified by running)

- `python main.py` boots cleanly (auth not enforced in that mode). HTTP 200 from `/health`, `/api/timeline/status`, `/api/logs/recent`, `/`, `/foresight-counter`, `/control`, `/walk`. 493 routes registered.
- `python run_reach.py --no-browser` boots with auth enforced; owner login works; quit and restart works.
- Port 8765 is taken by something the app itself starts, so `PUBCAST_PORT=8765` fails to bind. Use another port.

## The fixed and retested slice

- Fault (proven live, then in isolation): `AlexCore._estimate_valence` counted feeling words by raw substring. The turn "No, you misread me. I'm not upset, I'm just tired." was saved to Alex memory tagged `negative` (and `distress` when intensity was high), and that tag came back as memory context on later turns. `_analyze_input` already used the negation-aware matcher `_keyword_hit`; valence did not.
- Fix: `_estimate_valence` now uses the existing `_keyword_hit`. No new matcher and no new judge. Paths: `modules/alex_core.py`, `tests/test_alex_keyword_matching.py`.
- Retest: 80 passed, 1 expected failure across the keyword, Alex route/bridge, CARE EQ, EQ transition, personality continuity, memory reach and user-id tests. Live through `run_reach.py` and the real PubPartner turn route: the same correction is now stored `neutral`.
- Left open on purpose (strict xfail in the test file): the three-word negation window crosses a comma, so "I'm not happy, I'm angry." scores neutral. Changing the window also changes the stress and fatigue reads, so it is a design decision, not a silent fix.

## The EQ bridge result (verified live, no model)

Path run through `run_reach.py` with a logged-in owner: `POST /api/pubpartner/sessions` then `POST /api/pubpartner/turns`.

- Each turn goes through `AlexJeremyBridge.process_user_turn`; the packet and Jeremy's whisper are rebuilt every turn (`bridge_scope: message_analysis`, new `generated_at`).
- A Jeremy signal with `requested_action` came back `blocked_pending_authority` / `pending_pub_manager_decision`. The action was not allowed without the Pub Manager.
- Alex state, memory, the packet and CARE events were all still there after quit and restart.
- Blackbox hash chain verified (`ok: true`, 12 events) and the turn reported `blackbox_started` and `blackbox_committed`.
- Real reply: BLOCKED here. With `allow_fallback: false` the reply is empty and the result says Ollama is not reachable. With fallback allowed the reply is the offline rule-based line, labelled `provider: offline`, `local_rule_based: true`. No model-written reply was produced or claimed.
- Privacy, one path only: on a private-audience turn the model prompt contains the user's own remembered text (checked with an invented marker phrase). That prompt goes to whichever provider is configured. About thirty modules can make outbound calls; only this one path was checked. The others are NOT verified.

## Three things seen in the trace that need the owner's decision (nothing was changed)

1. `POST /api/alex/message` calls Alex directly and does not go through `process_user_turn`, so the Alex/Jeremy packet is not refreshed by that route. After a message there, the packet still showed the earlier state.
2. A high-urgency Jeremy room signal raises Alex's read of that user's stress (`modules/alex_jeremy_bridge.py`, around lines 266 to 270). In the trace the next message from that user put Alex in ANCHOR with a breathing exercise, although the message itself was calm.
3. A CARE observation (`POST /api/alex/care/observe`) is stored and survives restart, but stayed `unreviewed` and did not appear in the packet. Seen in the trace only; `modules/care_eq.py` was not read in full.

## Real-browser tests (proxy: installed Chrome for Testing 153, not Playwright's own Chromium, which could not be downloaded)

- Passed: `test_bella_faux_pas_launch_acceptance.py`, `test_camera_try_browser.py`, and the other tests in `test_recording_integration_browser.py`.
- Failed twice in a row:
  - `test_clacker_recording_browser.py::test_recorded_clacker_is_separate_silent_in_program_and_aligned_to_video` (45 s wait at line 21 timed out).
  - `test_admitted_guest_recording_browser.py::test_independently_admitted_guests_mix_record_reconnect_and_export` (`#recordStop` stayed disabled).
  - `test_recording_integration_browser.py::test_panic_interrupts_an_already_waiting_ordinary_stop` (PANIC stop took longer than its 1,000 ms limit; 1,165 ms on the first run).
- NOT established: whether these three are faults in the code or effects of this sandbox's software-rendered browser. They were not investigated further.

## Component ledger

| Component | State | Basis |
| --- | --- | --- |
| Boot, health, timeline status, recent logs | verified live | HTTP against running app |
| Counter, Control page, walkable studio pages | verified live (served); launch flow passed in proxy browser | HTTP + launch acceptance test |
| Auth, owner login, restart | verified live | `run_reach.py` trace |
| Alex Core | verified live | trace + focused tests |
| Alex/Jeremy bridge, authority gate | verified live | trace + focused tests |
| PubPartner turn path, receipts | verified live; model reply blocked | trace |
| CARE EQ | verified live for storage; present-unwired to the packet (see item 3) | trace |
| Blackbox | verified live + focused tests | chain verify, 5 test files |
| Cameras, camera moves, camera pool, preflight | focused-test only | 6 test files; `write_json` import present in `modules/cameras_advanced.py` (read) |
| Control Room vision mixer | present, not exercised this run | page served only |
| Stop / PANIC | route verified live; browser test fails in proxy | see above |
| Recording | routes live, integrity test passed; browser partly failing | see above |
| Guest audio recording | blocked: browser test fails in proxy | see above |
| Clacker | blocked: browser test fails in proxy | see above |
| STT / TTS | present, not exercised (speech packages not installed) | listed only |
| Visemes | not found by file name or route path; file contents not searched | listed only |
| Avatar | present; only the launch flow exercised | listed + launch test |
| Guest profiles | no file by that name; PubPartner `/profiles/{kind}` exists, not traced | listed only |
| Primp | present (static + three tests), not run this session | listed only |
| Filler cream | present (two modules, docs, two tests), not run this session | listed only |
| Iteration Wallet | design-only / present-unwired: folder, docs, one test, no routes; design doc is the PARTIAL recovery | listed only |
| PEQ lineage (75 files) | absent from the remote; not recovered, not recreated | gap register |
| Original Alex portraits and prompts | absent; not recovered | gap register |

## Why main was not merged

The owner authorized a safe merge if boot, meaningful user flows, focused regressions and privacy boundaries pass. Not cleared:

1. Three recording-area browser tests fail here and the cause is not established.
2. The full suite was not run on this HEAD, so the 107 commits ahead of `main` are not shown to work together beyond three focused non-browser runs (82 passed; 80 passed with 1 expected failure; 23 passed with 1 skipped; some test files are in more than one run, so these do not add up to a unique count) and the live traces above.
3. Outbound-call privacy was checked on one path out of roughly thirty modules.
4. Nothing was run on Windows, with real media, or with a real model.

## Next smallest action

Run the three failing browser tests on the owner's laptop build (real Chromium via `playwright install chromium`). If they pass there, the failures are this sandbox and gate 1 clears. If they fail there, start with `test_panic_interrupts_an_already_waiting_ordinary_stop`: it is the smallest, and it is the safety path.

## How to repeat the evidence

Files in `handoffs/evidence_2026-11-13/` (invented test phrases only, no personal content):

- `live_trace_alex_message_and_bridge.py <repo> <data-dir> <port>`
- `live_trace_pubpartner_turn.py <repo> <data-dir> <port> /api/pubpartner`
- `use_system_chrome.py`: pytest plugin used only in this sandbox (`PYTHONPATH=<folder> pytest -p use_system_chrome ...`). Not needed on a machine with Playwright's browser installed.
