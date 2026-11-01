# Lead Engineering Directive — PubCast Control Room + Television Studio
**Issued:** 2026-10-31 · **Company:** Rearview Foresight · **Working branch:** `lead-engineering-control-room-tv-studio-2026-10-31`
**Role:** Acting lead engineer, architectural integrator, test/debug owner, implementation owner.
**Status:** Active engineering mission, NOT a completion declaration.

## 0. Read this as a job assignment, not a suggestion
You are the lead engineer on an unusually ambitious creative technology project.
Your job is not to write a polished description of what a future engineer might do.
Your job is to **inspect the real source, provision a runnable environment, execute,
debug, repair, integrate, complete, test, and continue engineering**. Make genuine
commits on the assigned branch. Seek the owner's input only for truly owner-specific
assets, direction, live hardware or credentials. Every unblocked engineering step is
yours to carry as far as your tools and environment allow.

Do not replace real engineering with checklists, pretty mockups, optimistic test
reports, or statements of potential. Correct anything you discover to have been
rushed, duplicated, superficially wired, made to look functional without actual
functionality, or asserted as verified without runtime observation.

## 1. Meet the company and founder — why this exists
PubCast belongs to **Rearview Foresight** (also styled Rear View Foresight), founded
and driven by **Josie Curtsey Cobbley**. Her company motto is written in the
company's own About document as **“Feic Mo Chroí — See My Heart.”**

This isn't a slogan to add decoratively to a title screen. It is the reason to
build the platform: help people be heard, seen, and represented **as they choose**,
with the creative freedom to express who they are. Make technology serve people,
their stories, voices, friendships, performance, vulnerability and invention.
A working, accessible and trustworthy creative studio matters more than a
spectacular fake demonstration.

The company manifesto is in `whatsupjosie/Pubcast-Reach`, file
`About Rear View Foresight and Curtsey`. Its idea in the founder's words:
“If the only way forward is through, it would be nice to do it together.”
The owner and collaborators will gladly help; ask precisely when their
actual participation can unlock a blocker. Do not make avoidable engineering
into homework for the owner. Your job is to help us help the people using PubCast.

## 2. Establish the truth before touching behavior
Start from `whatsupjosie/October-24` branch
`lead-engineering-control-room-tv-studio-2026-10-31`. It is **not** main.
It was branched from `pubcast-25d-production-integration-2026-10-30`,
itself 130 commits ahead of main when first compared on October 31.
The branch contains recently integrated source that may be unverified.
Do not merge to main or overwrite the existing walkable-world demo.

Read:
- `AGENTS.md`
- `docs/missions/pubcast-lead-engineer-2026-10-31/SOURCE_RECONCILIATION.md`
- `docs/missions/pubcast-lead-engineer-2026-10-31/ACCEPTANCE_MATRIX.md`
- `docs/missions/pubcast-2_5d-studio-completion/{MISSION,STATE,BLOCKERS,VERIFICATION,THREE_SOLUTIONS_PIVOT,EDITOR_AND_FINISHING_BOUNDARY}.md`
- The code itself. Documentation is historical evidence, not runtime truth.

Inventory the entry points, dependency sets, route registration, frontend assets,
Python services, server worker lifecycles, tests and optional integrations.
Do not assume `README.md` is exclusively about the television studio: it covers
other parts of the consolidated codebase.

Establish a **verified build baseline**: supported Python/Node versions,
dependency installs, reproducible startup, authenticated login, basic health,
browser page load, one stage render, one recording start/stop, persistence and
playback. Where a dependency isn't available, choose a documented supported
fallback; don't call the system installed just because import statements exist.

## 3. Technical priority: finish the 2.5D TV studio FIRST
PubCast has two distinct environments:
**(A) A controlled television-production studio with parallax/2.5D sets and
actual 3D performers**, and **(B) a walkable 3D world (Bella Faux Pas and others).**
Preserve B and its tested demo. The near-term commercial beta must not depend
on completing an unrestricted world renderer; finish A first.

Engineering must provide:
- Functional scene graph with independent background/middleground/foreground,
  replaceable textures, correct depth/occlusion, perspective and performer scale.
- Actual rigged 3D avatars that can move, emote, interact, walk within constrained
  stage spaces, change pose, and be consistently framed. Fixed camera positions
  are not permission to make performers stiff.
- Camera presets/shot compositions and authentic Program/Preview across eight
  current genre packages identified in the code: `news`, `late_night`,
  `debate`, `political_discussion`, `audience`, `game`,
  `variety`, and `general`. The owner also expects useful talk/interview
  layouts; verify those with existing packages or introduce a properly
  specified package only if coverage is missing.
  Validate that EVERY package has defensible, differentiated coverage.
- Sets inspired by broad television geometry/conventions (news desk, talk sofa,
  podium debate, political panel, theatrical variety, game show, audience-driven
  formats); use original reusable stand-ins and layered textures. Do not copy
  copyrighted sets, channel branding or TV show screen graphics.
- Real scene changes, blocking, camera switching, audio buses, graphics/lower
  thirds, cues and session recording. A working debug/placeholder view is better
  than a beautiful still image with no production behavior.
- Mobile-readable monitor and panel controls, keyboard/focus correctness,
  recoverable failures, accessibility, and offline-first local operation.

A genre may be demonstrated with substitute art, but no functional path
may wait for the founder's final background plates or photographs.

## 4. The Control Room is ONE system, not a decorative second frontend
Unify and finish the existing Control Room and Director's Switcher, including:
- The same authoritative CameraManager/Program/Preview for television studio
  and walkable world, with proper CUT/transition events and source ownership.
- The same ProgramAudioState/mixer, actual audio media routing and separately
  controllable dialogue, music, SFX, room and necessary output buses.
- Record/stop/pause/marker state that proves actual media is being written;
  marker/clacker audio and video event flags must align with real timecode.
- All genuinely supported stations: Director; camera/pan-tilt-zoom/joystick
  actions; audio mixer; teleprompter; VTR/playback; graphics/chyron;
  recording storage; production status; relevant owner/operator permissions.
- Reliable switcher hardware-look placeholders with replaceable final
  switcher fascia; existing camera joystick positions and monitor wiring.
- Full command acknowledgments and role checks. Missing backend state is
  an error indicator, never a success animation or an optimistic green lamp.
- Correct destruction/cleanup of timers, tasks, media streams, camera leases,
  actor resources and browser object URLs after each session or mode change.

All the consoles and routes must agree on the camera and audio source truth.
Do not fork a second permanent video switcher or mixer for the 2.5D renderer.
Avoid mocked VU meters, fake recording success and false studio light indicators.

## 5. Recording and render strategy — the owner's hard promise
PubCast is **not finishing software**. It is the studio that allows a person
to produce material that can be completed to top professional/theatrical
quality on another computer in professional software. Recommend DaVinci Resolve
Free as an accessible independent finishing application, not a sponsor today.
Users must not be trapped at proxy resolution, in IndexedDB or a proprietary
one-way format.

Preserve these three independently:
1. **Complete, portable replayable shoot master:** source 3D actor states and
   animations, scene and asset dependencies, camera positions and rigs,
   graphics, cues, lighting, separately recorded audio, timebase,
   clacker markers, authorship/license/provenance, integrity manifest.
2. **Low-cost proxies and an evolving editorial decision list:** Program and
   every necessary camera confidence view, editor-selected shots, alternative
   angles and audio. The live director's decisions are not irreversible.
3. **Selective native high-quality rendering/export:** produce actual
   high-resolution pixels for selected time spans and chosen camera angles
   (and editing handles), never just upscale a low-resolution proxy.

A 30-minute production with five cameras must NOT require rendering 150 minutes
of high-quality output. The artist can decide next week to retain the full
30-minute director's cut plus another 30 minutes of alternatives and render
only that hour. Capture source-level performances comprehensively first.
Archive or delete disposable renders/proxies only under explicit retention
rules; never silently destroy the replayable master.

The existing 640x360 JPEG confidence frames and nominal 1280x720 browser
MediaRecorder are NOT a full-resolution broadcast/film master. Do not
relabel those outputs. Implement deterministic replay/export and prove
genuine 4K source-based rendering and relinked finishing on a second machine
as release gates; if the first pass cannot attain them, preserve a truthful
pending gate with reproducible evidence.

The clacker is an authoritative 15-second time reference: red dash on video
timecode, separate reference blip audio track, independently controllable
track drift and precise per-track edit offsets. For example, the editor
must persist **+0.030 seconds = play source 30 ms ahead**. Keep microsecond
precision in sidecars even where EDL frame rounding loses subframe accuracy.

The basic PubCast editor should only help select, view, split/lift/ripple,
organize rough cuts, synchronize audio/video and export coverage decisions.
Its compact transport may echo familiar NLE muscle memory, but should
not copy a proprietary visual design or attempt to rebuild professional
color-grading, compositing or advanced effects suites.

## 6. Reconcile other repositories — preserve, don't indiscriminately dump
The GitHub organization/account includes older PubCast snapshots and distinct
systems (`October`, `The-Prime`, `Wednesday-`, `Pubcaast-Breaking-Dawn`,
`The-Counter-and-2i`, `Pub-Partner-Base-Horizon`, `Pubcast-Reach`, etc.).
Run path and SHA inventories; identify **unique capabilities/assets actually
missing** on October-24, not just old files with different names. Prefer
recency, testability, explicit design authority, license provenance and
compatibility when resolving conflicts.

Never overwrite current code with an older snapshot based on file count or
the name “prime.” For every promotion create source provenance, destination,
reason, replaced/retained decision, test and reversible commit. Keep
non-imported candidates in the inventory. Large binaries may require a
separate owner-authorized transfer path.

## 7. Workloop: don't give up just because one piece is done
A. Inspect contract and code → state concrete observable outcome.
B. Execute environment setup/start/test, observe failure; reproduce it.
C. Correct the underlying behavior (not only labels), add a regression.
D. Re-run focused test, smoke integration and broad affected suites.
E. Check how the fix interacts with other subsystems and hardware.
F. Commit bounded, reviewable changes and update actual evidence ledger.
G. Immediately select the next highest-value open step. **Do not stop** at
“wired the camera,” “made a handoff,” or “tests pass in isolation.”
H. After each major checkpoint and whenever context gets long, **re-read
this directive and the current handoff** before choosing next task.
I. If stuck without measurable progress for ~2 minutes, log the exact
attempt, error, location, workaround candidates and next retry trigger;
switch to an independent unblocked task. Return to blockers after progress.
J. After major milestones run three rounds: adversarial shortcut audit,
repro/fix debugging, and cross-system reliability regression. At a consequential
architectural pivot, compare three viable solutions and implement the best
or proven hybrid with explicit why/why-not.
K. Stop only for confirmed required owner-only inputs, truly unavailable
tool/runtime capability, safety/security constraints, or actual completion.
No endless circular investigation, speculative filler or token-burning.

## 8. Explicit acceptance — no ambiguous “done”
The matrix `ACCEPTANCE_MATRIX.md` is the practical release definition.
Deliver working video, sound, camera action, persistent media,
restart/recovery, cross-client consistency, studio-to-Control-Room routing,
security controls, 8 genres, regressions and full-quality export.
Test with real backend/browser and state actual observed environment;
mocks/syntax checks count only as limited supporting evidence.

Never mark the Control Room or 2.5D studio sealed without owner approval,
even after all technical gates pass. Never merge into main without authorization.

## 9. Owner-only contributions (nonblocking until needed)
Photographs of the final physical video switcher and remaining director
console, final visual designs/background plates, subjective creative
approvals, credentials/licenses that cannot be supplied by the agent,
hardware-only/live user verification, and release authorization.
Use user-approved placeholders and configuration references meanwhile.

When owner input is genuinely needed, ask ONE precise actionable question
or supply a short list of exact missing assets, where they go, desired format
and why they block a particular acceptance gate. Continue unrelated work.

## 10. Required handoff (continuous, practical, not a poem)
Update `NEXT_DAY_HANDOFF.md` and `ACCEPTANCE_MATRIX.md` while working,
with source commit, branch, dates, environment, commands and exits,
successes actually verified, unresolved bugs, attempted remedies,
file/provenance changes, next executable step, required owner input,
and no fabricated test or launch claims.

The engineer owns the remaining engineering work. Keep PubCast and the people
who will use it at the center of each technical decision.

**Feic Mo Chroí — See My Heart.**
