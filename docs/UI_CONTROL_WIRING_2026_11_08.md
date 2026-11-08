# PubCast Control UI wiring — session-ending handoff
**Date:** 2026-11-08  
**Branch:** `gpt/control-ui-wiring-2026-11-08` (started from `chatgpt-work-2026-11-05`)  
**State:** IMPLEMENTED IN SOURCE; NO REAL HOST/PHYSICAL-DEVICE ACCEPTANCE; NOT MARKET-READY  
**Scope:** The legacy `/control` production/wardrobe interface, `control_room.html` VTR input label, production-state contract, and replay upload path. This is **not** a whole-PubCast UI audit.

## Confirmed source defects before the change

1. The upload form advertised `Replay (assets/vod)`, but `/api/upload` ignored `target` and wrote every file to `DATA_DIR/imports`. The VTR never received the promised file; the shared `/assets` mount could also be absent when the assets directory started empty.
2. VTR Load/Play/Stop and Chyron sent HTTP commands without verifying the response or saved production fields. An error could appear as successful UI behavior.
3. Replay URL composition doubled `assets/` when the input used the offered `assets/vod/` prefix. STOP could leave replay video visible and playing because display was based on `mode=REPLAY` even when `on_air=false`.
4. The `chy-bug` input was not included in the production update, and the model had no `bug` field.
5. Program monitor checkbox/level had no handler; AFV/VTR ducking did not have a shared runtime contract. Wardrobe saves did not inspect host acknowledgements.
6. Four literal `\\n` strings were present in the audio-mixer HTML, not actual line breaks.

## Changed behavior

- `/api/upload`: authenticated moderators/owners may select imports or replay VOD. Replay media is written to the mounted `ASSETS_DIR/vod` using a sanitized unique filename, exclusive creation, bounded 5 MiB streaming, empty-file rejection and MP4/WebM/Ogg signature/extension checks. Rejected/incomplete self-created files are deleted; an exclusive-create race does not delete another writer's file. Invalid destinations fail instead of being silently ignored. The response returns `asset: vod/<filename>` for replay uploads.
- `/assets` mounts even on initially empty installations. **Visibility warning:** replay uploads are served from the host's public static-asset URL. The UI now says so explicitly; private media must not be uploaded through this path.
- Dressing Room upload UI now checks `data.ok`, reports server errors, and inserts the returned asset path into the VTR input.
- VTR validates local paths; rejects URLs, traversal and unsupported extensions; HEAD-checks served video; loads off-air; requires a loaded replay before Play; and verifies both HTTP and returned production-state fields. Status is visible and buttons re-enable on error.
- The monitor now pauses/hides replay when taken off air, normalizes old/new asset path prefixes, avoids resetting unchanged video sources, and reports playback intervention where autoplay is blocked.
- Chyron stores both lower third and independent, bounded `bug` state and renders the bug in the Green Room Program monitor and Studio preview when on air.
- Production-station commands repaint local UI only after confirmed server state; WebSocket remains the cross-client authority.
- Monitor Program checkbox/level actually mute and set gain of the existing **local Program video monitor**, without affecting the shared broadcast mixer. The VTR AFV checkbox is now disabled and labeled unavailable; **AFV is not implemented** rather than being a deceptive no-op.
- Wardrobe and production-control forms require host acknowledgements and display errors/success. Display-name and badge lengths align with the host contract. The audio-mixer markup no longer contains literal escaped newlines.

## Evidence — RAN here

An isolated V8 source-execution harness ran the actual updated `static/control_stations.js` against a controlled DOM/fetch fake: **11 checks passed**. They covered normalized VTR loading off-air, Play/Stop state, bad path rejection, missing asset handling, unconfirmed-host rejection, Chyron field updates and feedback, and teleprompter start/stop status. Six additional isolated V8 assertions exercised the actual `static/app.js` production-state functions: legacy asset URLs resolve once, on-air replay becomes visible, off-air STOP pauses/hides it, on-air/off-air bug overlay behavior, and rejection of an external URL. Both full JavaScript files were also compiled by the V8 parser after changes. These are *not* browser/HTTP/device tests.

## WROTE, NOT RUN on a PubCast host

Added two acceptance tests in `tests/test_control_page_end_to_end.py`:
- `test_vtr_upload_graphics_and_monitor_wiring`: real FFmpeg-generated WebM uploaded through the real Chromium UI into the real host, HTTP HEAD under `/assets/vod`, VTR Load/Play/Stop verification, Chyron persisted bug, local monitor gain, AFV disabled.
- `test_replay_upload_rejects_bad_content_and_oversize`: invalid media signatures, >5 MiB and invalid destinations.

**Run on a supported checkout with FFmpeg and Playwright:**  
`python -m pytest -q tests/test_control_page_end_to_end.py -k 'vtr_upload_graphics_and_monitor_wiring or replay_upload_rejects_bad_content_and_oversize'`

No real host, live media, browser, full regression run, Windows check or deployment is claimed here. Run these tests and the adjacent host/audio/control suites before merging. Treat a passed HEAD as file existence/type evidence only, *not* proof that every browser can decode its codecs.

## Release blockers and intentionally unchanged systems

- The shared mixer still lacks an authoritative AFV/VTR ducking contract; the checkbox is explicitly unavailable. Independent headphone/audio-monitor output routing is also not commissioned; this pass controls the existing Program video monitor only.
- User-uploaded replay assets are **public to anyone with the host's asset URL**, and there is not yet a per-owner private media lifecycle (delete, retention, quota, audit). The asset directory may live outside the host-data checkpoint scope and needs an explicit backup/restore contract. Multipart parsing may spool request data before the 5 MiB file-size check, so full ingress/body-size defense also remains a release gate. Use only intentionally shared production assets. Review before external deployment.
- The VTR accepts local files in common formats, not arbitrary remote links. Browser codec compatibility and actual A/V frame timing need device acceptance.
- The 2.5D studio, Counter trays, notes, profiles, PubPartner, guest permissions, Primp, full editor and distributed workers were not re-audited or accepted by this change.
- No main/integration merge, launch, release seal, or GitHub Actions run was performed. Claude's work and the parallel Primp branch remain separate.

**Next acceptance gate:** Run the new real Chromium/FFmpeg tests on the branch; inspect production-state acceptance, actual playback start/stop, repeat upload collision/oversize, cross-client updates, permissions, and Windows device behavior. Then audit the entire visible UI route-by-route, binding each interactive element to a real event, a real service outcome and a regression test. Unsupported controls must stay visibly unavailable until the contract is implemented.
