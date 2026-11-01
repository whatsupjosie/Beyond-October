# Executed engineering report — October 31, 2026

Status: engineering progress verified in the stated environment; product remains **UNSEALED**.

## Source and environment

Authoritative source: `whatsupjosie/October-24`, branch
`lead-engineering-control-room-tv-studio-2026-10-31`.

- Starting commit: `6d3ff0df79f35c8d881b410bbabbaf0147093b6d`.
- First implementation commit: `46249afd87e8d5a133d1273337d748817e98df59`.
- Emergency-cue implementation commit: `73ca8bba3acad765c5388ce5b8e56fe37d093a82`.
- Latest source: `4f6c5d3f48eb0b4d157f8947eaea1a51d7a8f610`, tree `caae611345449faf9935a1531b79a5239a39ce74`.
- Broad-suite source: `73ca8bba3acad765c5388ce5b8e56fe37d093a82`, tree `258afcb06cbe2b14493fbb34545790e82219996a`; the final change is the separately retested editor diagnostic fix.
- Linux, Python 3.12.14, Node 24.22.1, npm 11.9.0.
- FastAPI 0.115.14, Starlette 0.41.3, Playwright 1.56.0, Chromium 141.0.7390.37.
- Software WebGL via SwiftShader; desktop 1440×1000 and mobile layout 390×844.
- Runtime and test requirements installed into an isolated venv; `npm ci` executed.
  Exact installed Python versions are in `evidence/2026-10-31/python-versions.txt`.
  `python -m pip check` reported no broken requirements.
- All full-host browser fixtures use disposable data directories and real first-run
  authentication. No provider credentials or physical microphone are required.
- Shell push had no GitHub credential helper. The connected repository API committed
  the identical Git trees with a checked parent lease. Local commits `793e040...`
  and `0c895fd...` have identical trees to their corresponding connected commits.
  This was an authenticated repository update, not a deployment or main merge.

## Real defects corrected

1. **In-flight camera ownership race.** A publisher checked a lease before reading
   its HTTP body. Another publisher or session release could intervene, and the
   first request could overwrite the new owner or resurrect a released feed.
   Revalidate camera existence, session release, capacity, ownership and rate at
   commit time, without an await before assignment. Three delayed-body tests first
   reproduced the failures and then passed. The finite lease/tombstone retention
   policy remains a bounded confidence-feed mechanism, not a durable ingest ledger.
2. **Repeated takes replaced earlier media.** Recording twice in one production
   reused the same IndexedDB media key. Every take now has its own ID and timing;
   the session lists each take independently. A browser test hashes the first real
   recording before and after the second and verifies both survive reload.
3. **Failed saves discarded the only recording.** Keep an unsaved Blob available
   for download and retry, show the recovery controls, prevent another recording
   from replacing it, and warn before leaving. A real recording with an injected
   quota error is downloaded, saved on retry and reopened for playback.
4. **Recorder errors discarded available partial media.** Preserve captured bytes
   with an explicit INCOMPLETE label. A deliberately injected recorder error does
   not turn the partial take into a success claim or destroy its bytes.
5. **Set reload could clear a replacement actor.** Serialize stale avatar loads
   before reusing the stable performer IDs; old cleanup cannot delete new actors.
6. **Gestures returned success without advancing the rig.** Advance the animation
   mixer independently of Walk/Idle availability. Actual rig-render pixels now
   change during the bundled Wave clip.
7. **Bundled walking bones were never found.** GLTFLoader sanitizes colons from
   Mixamo node names. Support the sanitized names so procedural walking activates.
   Release owned geometry, materials, textures and mixer bindings on teardown.
8. **Mobile political-panel layout overflowed.** Wrap long actor identifiers and
   constrain the control column and file inputs; all eight genres fit the tested
   mobile viewport without horizontal overflow.
9. **Portable exports could omit or replace sources.** Always preserve original
   media bytes under collision-free names; put optional converted files separately
   in `renders/`. Relative metadata relinks on import. Include file sizes and
   SHA-256 integrity information, and explicit conversion warnings. Missing media
   fails export. Concurrent requests have independent staging and archive names.
10. **Import and restart could lose or misidentify saved takes.** Validate and
    stage imports before publication, verify supplied integrity manifests, reject
    ambiguous/nonportable media paths, relink legacy Windows paths, stream upload
    bytes and keep previous uploads. Restore persisted metadata on service restart;
    interrupted sessions are identified as interrupted. Existing take directories
    cannot be reused, and metadata writes use the existing atomic persistence helper.
11. **Storage indicators invented available space and backup activity.** Measure
    the actual filesystem; cloud usage is unknown and backup is unconfigured until
    a real provider supplies that state. Reject unsuccessful storage responses.
12. **2i failed at account setup.** Its account-specific LLM storage key was declared
    const and reassigned. Correct the declaration; existing manuscript/owner tests pass.
13. **Plain local HTTP could not allocate secure tray IDs.** Use cryptographic
    `getRandomValues` when `randomUUID` is unavailable. Keep the save/close handshake
    and nonce rotation; do not fall back to predictable IDs.
14. **Crowded tray growth could hold every queued open on a slow renderer.** Bound
    growth by elapsed time as well as physics frames. Readability/overlap guards and
    retained contents remain; slow-device tests prove the next request is released.
15. **PANIC acknowledged but did not reach the real studio.** The persisted
    ProductionState model silently dropped panic/blackout/test-pattern fields.
    Declare finite typed cue fields, persist the black cue, and keep PANIC status
    visible through recorder cleanup. The real-browser test records canvas video,
    creates a measured 440 Hz signal through the program mixer, invokes PANIC from
    another HTTP client, observes recording stop, black pixels and near-zero audio
    RMS, and confirms that the recorded media survived.

16. **Autosave erased syntax diagnostics.** A background save could replace a Python
    check result before it could be read. Retain diagnostics for their exact text/edit
    revision and ignore stale check replies after an edit. All 14 native file workspace
    browser tests and three file lifecycle Node cases pass after the fix. The syntax
    check regression now waits beyond the autosave debounce and is also rerun alone.

The corresponding test fixes preserve their original behavioral assertions:
eight genre packages supersede seven; account-scoped storage supersedes shared
keys; extracted function harnesses supply their real dependencies; default-room
checks explicitly start without progress saved by earlier tests. Real room resume
behavior remains intact. No owner-written text or room artwork was replaced.

## Executed verification

Exact commands, source revisions, outcomes and logs are recorded in
`evidence/2026-10-31/README.md`. The broad run completed with 2,166 passed, one
failed and two deliberately skipped research modules. The single failure exposed
the autosave/diagnostic race above; the final repair then passed all 14 affected
browser tests and three file Node cases. The complete suite was not rerun again
after that isolated final change. Do not relabel the recorded broad run as green.

Already executed focused evidence:

- 37 Python cases: authenticated studio/browser, eight genres, actual rig animation,
  two-page CUT and decoded remote confidence frames, recording/reload, multiple
  takes, quota recovery, walkable avatars, and camera transport/role checks.
- 107 Python cases: recording persistence, portable bundles, conversion, integrity,
  collision and import guards, service/startup coverage.
- 40 Counter/physics/browser cases, including real Canvas fallback and slow growth.
- 31 studio/editor/file/owner Node cases; project `npm run test:node`: 9 cases.
- PANIC: one additional real-browser test and nine focused backend checks.
- Original full run: 2,122 passed, 4 failed, 3 skipped. Corrected the Counter
  admission problem and default-room fixture isolation; equipped the previously
  skipped widget test to use Playwright's installed browser.
- Subsequent full run: 2,163 passed, 2 failed, 2 skipped. Both failures were
  extracted reload harnesses still naming the old ID helper. The corrected pair
  passed in a focused rerun. The next broad run and the final focused editor correction are documented below.
- Broad run on `73ca8bba...`: 2,166 passed, 1 failed, 2 skipped, 211 warnings,
  614.48 seconds. Final affected file workspace module on `4f6c5d3...`: 14 passed;
  three file lifecycle Node cases passed; the individual strengthened syntax test
  passed again. No all-green complete-suite result is claimed.

These are distinct runs with overlap, not additive test totals.

## GitHub CI is not verified

At implementation commit `46249afd...`, Actions run `41239084129` reported failure.
Both returned job records had **empty step arrays and an empty runner name**.
There is no executed failing command to diagnose from those records. No CI pass is
claimed. The workflow now installs dependencies and runs the actual backend/browser
and recording regressions, rather than Python syntax alone. Local executed results
remain separate from the unresolved runner/Actions gate.

## Explicitly open release work

- Production-rate encoded video ingest, independent camera coverage and cross-client
  audio media transport; confidence JPEGs are still only operator previews.
- Full source-level, asset-backed production master and deterministic scene replay.
- Selective native 4K rendering from that replayable master, including real fidelity,
  separate tracks, timing/color provenance and rendering only chosen coverage.
- Blackbox integration of the full shoot media/performance bundle; a witness event
  alone is insufficient. The local recorder remains a browser proxy recorder.
- Real 15-second red video marker plus separate blip audio capture across sources.
- End-to-end editor controls, subframe offsets and actual Resolve import/relink on
  an independent machine. Source ZIP byte preservation is now tested; it does not
  fulfill the entire cinema-master or finishing round-trip promise.
- Physical phone performance, multiple computers/devices, licensed final avatars,
  final imagery and full station-by-station acceptance.
- Historical source candidates require semantic/compatibility/license review before
  promotion. Recursive blob inventories do not imply that every capability is integrated.

No sealing, deployment, main merge or product-launch claim was made.
