> Historical audit: current file-workspace implementation and current test limitations are in FORESIGHT_FUNCTIONAL_WORKSPACE_STATUS_2026-10-21.md. The later regression run includes a failing physics timing test.

# Foresight Counter — self-audit and debugging, October 21, 2026

This is the current audit. The first update's handoff is retained as history,
not as the final statement of verification. The ten supplied volumes and
Josie's original design documents have not been edited.

## Where my first pass fell short

1. **I overstated the interaction evidence.** The initial five-tray test called
   buttons through JavaScript and checked focus without advancing physics.
   That established state changes, not that a person could click the rendered
   controls or that focus stayed stable over subsequent frames. The revised
   tests use actual browser mouse events, advance physics after selection,
   exercise a genuinely compressed tray, and check save/restore.
2. **The sample contents are test doubles.** A button labelled Keyboard is not
   a working audio keyboard. The tests prove the Counter's container behavior;
   they do not prove the live audio workflow, article readability, sound-library
   installation, or synchronization between tools. Graphics output is explicitly
   stubbed in the interaction tests to separate those claims from GPU rendering.
3. **I used an easier large-window case.** Earlier development reduced a failing
   860 × 580 two-window case to 680 × 420 before establishing the larger case.
   The smaller passing case was insufficient evidence of general packing or
   performance. The larger stress case remains outside a verified frame budget;
   its feasibility at every permitted scale has not been established.
4. **The first pass was too narrow.** It did not exercise interruption, rapid
   opening, automatic persistence, smaller laptop screens, or application
   startup. This audit added those checks and found real defects.
5. **I initially had only the Counter subset locally.** For the broader audit,
   additional runtime modules, pages, configuration and 2i integration files
   were retrieved from the same upstream commit and checked by Git blob hash.
   This is still not a claim that every optional binary, asset or external
   service was installed and operated.

## Defects found and corrected

| Defect | Effect | Correction and evidence |
| --- | --- | --- |
| Interrupted admission retained its growth job | Closing could serialize as parked; hidden trays retained unfinished work | Close/park cancel growth and preserve the requested lifecycle; interruption regressions reproduced the defect before the fix |
| New requests could compete with an unfinished admission | Multiple opening jobs could alter the same crowded layout | Requests wait for the current admission; rapid requests and queued-admission tests cover intermediate states |
| Focus did not schedule persistence | Clicking another tray could leave the saved selection stale | All content selection goes through the shared selection function and schedules autosave |
| Debounced state was vulnerable to immediate reload | The last selection/content change could be lost before the timer ran | Flush on page hide, document hiding and destruction; immediate real reload is tested |
| Rejected resize did not restore the whole physical state | Deformation or pressure history could change after a failed trial | Restore prior geometry and physical history instead of rebuilding an undeformed frame; rollback regression compares both |
| Content minima could make a compression target unreachable | Separately clamped width/height changed the intended visible aspect, causing false parking | Derive one uniform content scale, then layout dimensions that attain both requested visible dimensions; numeric and laptop-layout regressions |
| Admission pressure was applied to unrelated trays | A remote indicator could shrink while a window opened elsewhere | Request yielding only inside the intended footprint; check the indicator throughout the attempt, not only at the end |
| Locking could freeze an admission seed at an unusable tiny size | A temporary opening frame could become permanent | Locking waits until admission completes; locking an ordinary expansion still stops it immediately |
| Messages checked a frame's window but not its origin | A known iframe navigating elsewhere could still request host conversation actions | Require the host origin; native iframe navigation and postMessage reproduce rejection while same-origin actions still work |
| Bot discovery treated identity metadata as runnable configuration | Packaged Pete identity metadata produced a false configuration error | Recognize its explicit companion-metadata schema without altering its bytes |
| A non-object JSON bot file could abort loading | A JSON array raised TypeError and prevented normal loading | Report the invalid file and continue loading valid bots; regression covers both outcomes |
| Launcher could not select the new Counter directly | Manual URL navigation was needed | Add `--start-page foresight-counter`; preserve the previous default and existing options; actual subprocess/HTTP check passes |

The earlier fixes for refitted-frame clearance, bounded admission and run-only
picker compatibility remain in the update. The picker was already fixed in the
upstream source; it was not counted as a new repair.

## Performance work and rejected changes

The heavy two-large-tray stress check exposed slow admission. Trial work is now
bounded and the prospective footprint is cached. This does **not** certify a
60 fps budget.

An experimental exact segment/box minimizer produced correct distance results
but changed contact-point selection and failed five existing physics regressions.
It was rejected and is not in this update. The retained optimization preserves
the original 22-step search and avoids constructing unused points/normals;
5,004 deterministic cases check identical returned contact parameters. Existing
physics tolerances and the 16 ms timing assertion were not relaxed.

Two existing source-text launcher assertions were updated to include the new
explicit option and mapping. Their old options and default checks remain. The
real launcher is tested separately, so those text checks are not its sole proof.

## Verification scope

See `VALIDATION.md` in this package for the final test command and results.

- Geometry and physics checks execute the actual JavaScript under Node.
- Browser interaction checks use actual DOM controls and mouse events, with
  deterministic physics stepping and graphics output stubbed.
- Mixed-size five-tray checks cover 1600 × 1000 and compact working dimensions
  at 1366 × 768 and 1280 × 800. Compact tests do not prove full-size application
  pages are readable at those dimensions.
- The real Reach ASGI lifespan is tested, including the Counter route, assets,
  initialized character bridge, and anonymous versus owner authorization.
- The real launcher was also started as a subprocess with disposable data.
  Loopback HTTP returned the exact updated page/script bytes, denied anonymous
  PubPartner status with 401 and returned bridge health with 200. The optional
  Node sidecar was deliberately not started by that check.
- JavaScript syntax, Python compilation, new Python-file linting and patch
  application checks accompany the behavioral tests.

## Remaining limitations and next debugging priorities

1. **Dense large-window performance is not cleared.** Preserve a repeatable
   stress scene and profile the whole animation path. Do not call this build
   production-ready on the strength of the functional checks.
2. **Strict non-overlap is not mathematically established.** Existing solver
   regressions allow numerical penetration of roughly 4–4.6 CSS pixels in some
   crowded cases. Passing that threshold is not proof of perfectly impenetrable
   frames. The thresholds were preserved, not changed to conceal failures.
3. **The local packing attempt is not exhaustive.** Awkward arrangements can
   still park a tray. Crowded-pocket dragging and the old reopen/unpark landing
   search remain follow-up work.
4. **Real audio and content workflows remain unverified.** Test the actual
   timeline, keyboard/switcher, browser/articles and effect libraries together.
   The exact audio workspace is not an automatic preset in this update.
5. **Actual hardware remains untested.** GPU rendering speed, physical audio,
   camera/mocap and Windows operation have not been certified here. Optional
   renderer, audio and facial-analysis services were unavailable in the audit
   environment; startup fallback messages are not proof those systems worked.
6. **The original full lab/page check scripts and the entire PubCast suite have
   not been rerun.** This is a targeted Counter/integration audit. An inherited
   fixture named `client_no_lifespan` actually enters TestClient's lifespan;
   its name must not be used as evidence of startup-free testing. It was not
   changed globally without checking its other consumers.

## Deferred feature reminder

On future project status and remaining-work reviews, include Performance settings
and protected background tasks from `PUBCAST_DEFERRED_FEATURES.md`. Requested
2026-10-21; deliberately deferred until current stabilization work is complete.
This is a backlog addition, not implemented functionality.

## Apply and run

This ZIP is an update for the existing October repository, not the full program.
From that repository in PowerShell 5, check the patch before applying it:

```powershell
git apply --check C:\path\to\extracted-update\changes.patch
git apply C:\path\to\extracted-update\changes.patch
python run_reach.py --start-page foresight-counter
```

The patch is based on upstream commit
`82ebf26755d3706f8d4d7d75d823bb73f4d1b07e`. If the check conflicts, preserve
the current work and reconcile it; do not overwrite a newer build. Changes have
not been pushed to GitHub. The supplied original documents remain authoritative.

If the earlier first-pass update has already been applied, use
`changes-from-first-update.patch` in both commands instead of `changes.patch`.
Both paths are checked against their corresponding source snapshots.
