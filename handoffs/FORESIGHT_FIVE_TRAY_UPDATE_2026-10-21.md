# Foresight Counter update — October 21, 2026

> Historical first-pass handoff. The current self-audit, corrections and remaining
> limitations are in `FORESIGHT_AUDIT_2026-10-21.md`. Verification counts below
> describe the earlier package, not the audited replacement.

## Starting point

Used the existing GitHub implementation from `whatsupjosie/October`, branch
`foresight/hdr-pipeline`, commit `82ebf26755d3706f8d4d7d75d823bb73f4d1b07e`.
The branch still points at that commit. Retrieved the Counter's actual source,
assets, tests and handoffs from the repository; did not extract or rewrite the
source from the ten Markdown volumes. Downloaded bytes were checked against
the repository's Git blob hashes. The original volumes are unchanged.

The actual source already includes run-only picker entries. The handoff's
claim that this picker fix remained unapplied is stale.

## Changes

- A new tray that cannot fit at its working size first opens a small frame in
  available space and attempts bounded growth while existing unlocked trays
  move and compress. It parks only if this attempt cannot reach its content's
  permitted working scale. Locked trays remain fixed.
- Focus no longer requests rapid inflation of a compressed tray. Explicit
  growth and resizing retain that behavior; ordinary recovery after pressure
  is released remains available.
- Fit calculations measure the actual refitted frame. Corner radii and frame
  widths have minimum sizes, so multiplying the original outline by a scale
  factor previously predicted incorrect clearance.
- Explicit opening coordinates are checked for collisions before use.
- Growth can finish its final fraction of a pixel instead of getting stuck
  just short of its own completion threshold. Successful steps reset the
  consecutive blockage count.
- Saving during an incomplete admission preserves the content as a parked
  tray at its allowed scale rather than restoring a permanently tiny frame.
- Locking cancels an in-progress expansion immediately.

## Verification

Final targeted run: **34 passed in 32.76 seconds** — 28 geometry/physics tests
and six Chromium browser tests. An earlier run during concurrent software
rendering exceeded the existing 16 ms physics timing threshold (16.82 ms);
the isolated timing rerun and final full targeted run passed. The browser tests
exercise the real geometry, physics, tray manager and
renderer initialization, using isolated test contents and intercepted local
file requests rather than a live Reach server. They cover:

1. Five different working sizes: a largest keyboard-shaped working tray near
   the bottom, a secondary timeline tray, two reference/library trays and a
   tiny indicator. All five remain visible, their controls respond, focus
   preserves the arrangement, and saved content state and geometry restore.
2. Opening a second large tray after the initial free-space search fails.
3. Locked geometry remaining unchanged while another tray seeks room.
4. Run-only picker actions remaining usable.
5. Saving and restoring during admission.
6. Locking during expansion.

The new admission and exact-frame prediction regressions were also run against
the unmodified upstream source: both fail there. A five-tray render was inspected
locally with software graphics. That image uses test contents, not working audio
programs.

## Limits and remaining work

- This is a Counter update, not a complete PubCast distribution or a new audio
  engine. It does not demonstrate effect installation, live keyboard audio,
  recording, or synchronization between the real audio tools.
- Live Reach authentication, APIs, external program pages and real GPU speed
  remain unverified in this pass. The original 34-check lab and 19-check page
  scripts were not rerun in full.
- Five mixed-size trays were tested at 1600 × 1000. Other screen sizes and
  long-form readability inside actual program iframes still need testing.
- Admission is a bounded local attempt, not an exhaustive packing solver.
  Some dense or awkward arrangements can still park a tray. The existing
  crowded-pocket dragging issue is not declared fixed.
- Reopening or unparking an existing tray still uses the previous landing
  search; the new admission attempt currently applies to newly opened trays.
- The exact audio arrangement described in conversation is not shipped as an
  automatic preset. The five-tray test verifies mixed sizes, not a fixed grid
  or mandatory roles for every tray.
- Admission can use up to 240 physics frames after the opening animation.
  Its performance has not been certified at 60 fps on a real GPU.

## Applying this update to the existing repository

The accompanying ZIP contains `changes.patch` and the changed files. It is an
update package, not a replacement for the full existing repository.

From your existing October repository, use PowerShell 5:

```powershell
git apply --check C:\path\to\extracted-update\changes.patch
git apply C:\path\to\extracted-update\changes.patch
```

If the check reports a conflict, preserve your current changes and reconcile
the patch; do not overwrite a newer version with the included files.

Run the targeted checks from the repository:

```powershell
python -m pytest -q tests/test_foresight_chain.py tests/test_foresight_frames.py tests/test_foresight_shapes.py tests/test_foresight_counter_workspaces.py
```

The browser checks require the Python Playwright package and its installed
Chromium browser. Existing routes and renderer artwork are unchanged. No changes
were pushed to GitHub.
