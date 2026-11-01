# NEXT TEN RUNS
## Long, self-contained sessions. Paste one, let it run, come back when it's done.

> **⚠️ CORRECTION — added 2026-08-23, after Run 1 actually executed.**
> This document's original premise (below) was wrong. Run 1 found that the
> affect engine was ALREADY wired into `alex_core.py`, live, with a better
> integration than this plan specified — `affect_wiring.py` was an
> unnecessary duplicate I built without checking first. It has been marked
> deprecated in the codebase. **Skip Run 1 as originally written below — it's
> done.** Run 4's plan to "migrate affect_wiring.py's persistence into the
> canonical store" is also moot — that migration already exists via
> MemoryCore. Read `RUN1_HANDOFF_2026-08-23.md`, `RUN2_HANDOFF_2026-08-23.md`,
> and `RUN3_HANDOFF_2026-08-23.md` in this folder for what's actually true
> and what's actually been done (Runs 1–3 are complete as of this correction).
> The rest of this document (Runs 4–10) is left as originally written and is
> still a reasonable starting point, but re-verify premises with `grep`
> before trusting any specific claim in it — that's the recurring lesson of
> this whole project.

---

Written 2026-08-23, grounded in the actual state as of the affect-wiring session:
`affect_wiring.py` exists and is verified working standalone (real smoke test,
real persisted baseline JSON) but is NOT yet called from anywhere live. The
Rust renderer files and PubWorld/camera components are uploaded but completely
unread. Three PubPartner patches are sitting unapplied. This plan sequences
real work against real gaps — nothing here is invented busywork.

Every third run ends with a **file-check step** — confirm what's on disk,
what's been pushed, what's missing — before starting the next one. Don't skip
these; they're what keeps the next AI from re-doing work or losing track of
what's real, which has happened before in this project.

---

## RUN 1 — Finish wiring the affect engine into live traffic
### (Do this first. Everything else assumes it's done.)

```
You are continuing work on PubCast AI / The-Prime. Read
NowCurtsey_Build/SESSION_HANDOFF_2026-08-23.md (Google Drive) or the
equivalent in this session's context before touching anything.

THE STATE: affect_wiring.py exists in modules/, imports clean, and passed a
standalone smoke test (4-turn synthetic conversation, correct 'observing'
states, real baseline persisted to disk). It is called from NOWHERE in the
live app. Your job is to close that gap completely, not add features.

1. Open modules/room_conductor.py and find on_message() (~line 459) and
   process_conversation_turn() (~line 649). Determine which one fires first
   when a user turn lands, before any bot composes a reply.

2. At that point, call affect_wiring.evaluate_user_message(session_id,
   user_id, text). Store the result somewhere the bot's reply-generation path
   can reach it — check how state currently flows from room_conductor into
   alex_core.py to find the existing pattern, don't invent a new one.

3. In modules/alex_core.py, find the ~5 places that set self._user_battery
   directly (grep for it — there were multiple spots in the last session, not
   just one). At each one, call affect_wiring.get_battery_for_user() and only
   overwrite _user_battery if the return value is not None (None means
   'observing' — see the docstring in affect_wiring.py, this is a deliberate
   design invariant, do not remove it).

4. Wire route()['everyday']['meet_them_at'] (via get_route_guidance() in
   affect_wiring.py) into wherever the bot's system prompt gets assembled.
   Find that assembly point first — likely in bots.py or alex_core.py's reply
   generation — before adding anything.

5. Call affect_wiring.AffectEngineManager.persist_state() somewhere sane —
   after each turn, or on a timer, or on session end. Pick one, justify it in
   the handoff, don't do all three.

6. PROVE IT: run a REAL 15+ turn conversation through the actual
   /api/bots/{id}/chat route (not a standalone script). Print the routed
   payload after each turn — state, confidence, battery, whether route()
   guidance fired. Include this raw output in your handoff, not a summary of
   it claiming success.

Do not touch the scoring logic inside affect_context_engine.py. If you find a
bug while wiring it in, fix only what's needed to wire it — log anything else
rather than fixing it in the same pass. Write a handoff doc when done:
what you changed, the 15-turn transcript, what's still open.
```

---

## RUN 2 — Inventory and integrate the Rust renderer
### (Fresh budget, dedicated pass — don't squeeze this into Run 1's leftover tokens.)

```
Josie uploaded six-plus Rust files that were previously flagged as missing:
skeleton_v2_hardened.rs, pubcast_renderer_v5_5_ready.rs, lib.rs, skeleton.rs,
motion_capture.rs, renderer.rs, scene.rs, voxel.rs. None of these have been
read yet. Also present: unified_bridge.py (Python side of the C++ shared-
memory bridge, verified importable) and bridge_bulletproof.py.

1. Read every one of these files in full before writing any integration code.
   For each: what does it implement, what does it depend on (other Rust
   modules? external crates?), and does it duplicate anything already in the
   twin_engine/ directory from the Aug 19-21 sessions.

2. Check Cargo.toml / Cargo.lock (present in The-Prime repo root) against what
   these files actually import. Confirm whether this compiles as-is or needs
   dependency changes. Try `cargo build` and report the REAL output, not a
   guess about whether it would work.

3. Determine whether these files ARE the twin engine C++ bridge target
   referenced in unified_bridge.py's docstring (V3.9-BULLETPROOF-DUAL-VOXEL-
   DX12, magic 0x50554243, protocol version 300) or a separate/newer renderer.
   The offsets and protocol version in unified_bridge.py are the ground truth
   to check these files against — if they don't match, say so explicitly
   rather than assuming they're compatible.

4. Do NOT wire this into the live Python app yet. This run is inventory +
   compile-verification only. Write a handoff naming exactly what each file
   is, whether it compiles, and what the actual integration points would be
   for Run 3.

Verification standard for this whole project: claim nothing without
execution evidence. "It looks like it should compile" is not a finding.
Either run cargo build and paste the output, or say plainly that you
couldn't run it and why.
```

---

## RUN 3 — Wire the Rust renderer to the Python bridge + FILE CHECK

```
Part A — continue from Run 2's inventory.

Using unified_bridge.py as the Python-side contract, wire the Rust renderer
from Run 2 so that:
1. The C++/Rust engine can be compiled and started as a standalone process
2. unified_bridge.py connects to it (real connection, not mocked) and reads
   real engine_stress / engine_pulse values
3. At least one command round-trip works: push_command() from Python causes
   an observable, verifiable effect on the Rust side (log line, state change,
   whatever is checkable given the environment's hardware limits)

If this environment lacks the hardware/OS to actually run the Windows SHM
path (bridge.h references Windows shared memory specifically), say so
immediately and pursue the filesystem or socket fallback path instead —
check bridge.py and bridge_raw.py for what fallback already exists rather
than inventing one.

Part B — FILE CHECK (do this even if Part A ran long):

1. List every file that now exists in modules/ and confirm none of the
   affect engine wiring from Run 1 got overwritten or lost.
2. Confirm what's actually on GitHub (The-Prime) vs. what's only local to
   this session's container — Claude has no GitHub write access, so anything
   not explicitly pushed by Josie is at risk of being lost between sessions.
3. Write a short manifest: file name, what it is, last verified working
   (with date), any known gap. Put this in CONTINUE_FROM_HERE/ or the
   Drive folder, whichever this session has write access to.
4. Flag anything uploaded in past sessions that you have NOT yet found a use
   for or read — don't let files silently vanish from the plan.
```

---

## RUN 4 — Memory unification (the seven-modules problem)

```
Read SYSTEM_AUDIT / SESSION_HANDOFF docs referencing the memory audit before
starting. THE GAP: PubCast has multiple memory-related modules (grep for
universal_memory_system.py, alex_memory.py, cc_memory_store.py,
memory_engine.py, personal_ai_memory_api.py, memory_ingestor.py — confirm
which of these actually exist in the current modules/ tree, some names from
past sessions may be stale) and no single answer to "if I want to remember
something about this person, which one do I write to?"

1. For each memory module that actually exists: what does it store, who
   writes to it, who reads from it, does anything currently call it. Use
   grep, not memory of past session summaries — those may be describing an
   earlier state of the code.

2. Determine ONE canonical store based on evidence (what's actually wired
   into main.py, what Jeremy/Alex actually call today), not assumption.

3. Migrate affect_context_engine's PersonalBaseline/PersonalPrior persistence
   (currently flat JSON files via affect_wiring.py, from Run 1) into the
   canonical store as a real entity type — same pattern used for whatever
   else already lives there.

4. This closes a real gap named in AFFECT_MODEL_CONCLUSIONS.md: exhaustion vs
   never-invested cannot be told apart in a short rolling window — needs
   session-scale memory. Once the canonical store exists, extend the affect
   engine's antecedent diagnosis to query it. Verify with a specific test
   case: someone energetic an hour ago, flat now, should read as exhaustion.

Do not build an eighth memory system. If the honest finding is that several
need to collapse into two or three, say so and propose which — do not
silently create another one while investigating.
```

---

## RUN 5 — PubWorld / camera architecture reconciliation

```
Read PUBWORLD_CAMERA_UNIFIED_ARCHITECTURE.md in full first — it already
describes the intended design. Do not replan from scratch.

Uploaded but not yet integrated: PubWorld.jsx, pubworld.py, marching_cubes.py,
distributed_engine.py, voxel.wgsl, and (from Run 2/3) the Rust renderer/scene/
voxel files. Also present: three patches (store_py.patch, service_py.patch,
engine_py.patch) for PubPartner, and a VISUAL_PATCH_KIT_COPY_MANIFEST.md
describing where files should land.

1. Apply the three PubPartner patches first — they're small, scoped, and
   nothing else should depend on unpatched PubPartner. Verify with
   PubPartner's existing test suite (grep for test files, run them, paste
   real output).

2. Follow VISUAL_PATCH_KIT_COPY_MANIFEST.md's instructions for where the
   PubWorld/camera files should actually live in the repo structure. Don't
   guess a layout — the manifest says what it should be.

3. Wire PubWorld.jsx to read live camera state from the Rust engine via the
   bridge established in Run 3, per PUBWORLD_CAMERA_UNIFIED_ARCHITECTURE.md's
   description of how these connect.

4. Prove one real round trip: a camera move initiated in the UI reaches the
   Rust engine and back. This is the same "smallest test that proves the big
   claim" standard used earlier in this project for PubCast/2i/PubPartner —
   apply it here too.
```

---

## RUN 6 — Bubble Stack physics integration + FILE CHECK

```
Part A: Bubble_Stack_Dossier.zip and bubble_stack_reconciliation.md are
uploaded. This is the physics/deformation engine (kinematics, collision
chains, deformation math) built and debugged extensively in an earlier
session — the reference regression test is a 4-level car crash scenario
(car_a → car_b → fire_hydrant → water → shopping_cart → cart → groceries).

1. Read bubble_stack_reconciliation.md first — it likely documents what
   changed since the original build and what state it's actually in now.
2. Re-run the 4-level car crash regression test for real. Paste the actual
   output. This has been re-run after every fix in the original session —
   keep that discipline.
3. Wire engine_adapter.py's BuilderAdapter to real Builder API geometry
   instead of the synthetic fake block cube flagged as a problem in the
   original session (this was called out explicitly as a false "verified"
   claim previously — don't repeat that mistake).
4. Connect choreography_physics_bridge output to the animation/choreography
   system so a physics event can actually trigger a character animation.

Part B — FILE CHECK:
Same as Run 3's Part B. Confirm nothing has drifted, list current file
state, flag anything still unread or unintegrated, push what you can to
wherever Josie has established write access this session (ask if unclear
rather than assuming).
```

---

## RUN 7 — Guest onboarding + avatar mounting

```
Two concrete, previously-scoped-but-unbuilt pieces:

1. Mount pete_avatar.py if it still exists and is still an orphan (check
   first — grep for it, confirm it imports clean, confirm nothing already
   loads it). It should have a full dual-rig skeleton definition. No renderer
   is needed to load the rig data structurally — only to display it. If the
   Rust renderer from Runs 2-3 is far enough along, this is where rig data
   and renderer meet for the first time; note that connection point if you
   find it, but don't force it if the renderer isn't ready.

2. Build the guest onboarding wizard: name entry, camera/mic permission
   request, avatar selection (check what preset avatars exist — Manny,
   Sheila, Pete, or a foundry/GLB import path), session registration via
   whatever the current session registration endpoint is (grep for it, don't
   assume the endpoint name from an old session summary). Reuse whatever
   three.js loading path already exists and is proven, rather than rebuilding
   avatar loading from scratch — check for an existing walk-test or demo HTML
   file first.

Verify both end to end: a fresh guest can go from nothing to a visible,
selected avatar in a room, through the actual UI, not a script.
```

---

## RUN 8 — Voice: STT/TTS real audio path

```
THE GAP: voice engines have been described in past sessions as "staged" —
real code present, not yet installed/tested with actual audio. Do not trust
that description without verifying it against the current repo state first.

1. Grep for faster-whisper, XTTS, whisper, pyttsx3 across the repo. Confirm
   what's actually imported/called right now vs. what's dead code.
2. If real STT/TTS provider code exists but the actual model weights/services
   aren't running, get ONE path working end to end — pick STT or TTS, not
   both, based on which has fewer missing pieces.
3. For TTS specifically: check whether real voice reference clips exist
   anywhere in the repo (data/voices/*.wav or similar). If not, this run
   cannot complete the "cloned voice" claim — say so and fall back to
   verifying the pyttsx3 or equivalent fallback path actually works, rather
   than leaving the run half-finished with no verified state.
4. Wire whichever path you complete into one real bot interaction — text in,
   audio out (TTS) or audio in, text out (STT) — through the actual API route,
   with real output you can point to (a saved audio file, a transcript).

This run may reveal the environment simply lacks the hardware/models to do
this at all (e.g., no GPU, no model weights downloaded). If so, that is a
valid and complete finding — document exactly what's missing and what
installing it would require, rather than forcing a fake pass.
```

---

## RUN 9 — Choreography + affect engine cross-wire

```
Now that Run 1 has the affect engine live and Run 5/6 have camera and
physics wired, close a loop named explicitly in AFFECT_MODEL_CONCLUSIONS.md
NEXT section: "Feed animation.intensity to prosody_engine and
facial_performance."

1. Confirm affect_context_engine.py's output includes a dramatic/animation
   intensity value distinct from chat intensity (the docs claim this exists
   — verify in the actual code, find the field name).
2. Trace how choreography_controller.py and animation_authority.py currently
   select actions/intensity. Find the actual insertion point for affect-
   engine-driven modulation — don't guess, read the dispatch code.
3. Wire it so a sustained high-load or escalation reading from the affect
   engine can influence which of the ~70 choreography actions gets selected,
   or its intensity/pacing. Keep this narrow — modulate existing selection,
   don't build a new selection system.
4. Verify with a scripted scenario: a conversation that ramps from steady to
   escalation should visibly change the animation intensity value passed
   downstream. Print the actual values at each turn.
```

---

## RUN 10 — Full-stack integration proof + comprehensive handoff

```
This is a verification and consolidation run, not a new-feature run.

1. Bring up the full stack — PubCast, 2i, PubPartner, and (if Run 3
   succeeded) the Rust renderer — together, per whatever the current
   RUN_GUIDE.md / STARTUP.md says. Fix whatever's broken from drift across
   the last nine runs before doing anything else.

2. Run one real round trip through EVERY major subsystem touched in Runs
   1-9: a chat message that produces an affect reading, that reading
   influencing bot response tone, a camera command reaching the renderer,
   a guest completing onboarding, one physics event triggering an animation.
   This is the "one roof, not four garages" test from an earlier session —
   apply it to the full current scope.

3. Run whatever automated test suites exist (pytest, cargo test, etc).
   Paste real output, reconcile pass/fail counts against the last known
   counts rather than reporting fresh numbers with no comparison.

4. Write ONE comprehensive handoff doc superseding all prior ones: current
   verified state of every subsystem, what's real vs. aspirational, and a
   clear-eyed list of what the NEXT ten runs should be — don't assume this
   document's job is done just because ten runs happened. Push everything
   final to whichever repos Josie has designated, and confirm what actually
   landed where (GitHub write access may still be Josie's job, not Claude's
   — don't claim a push succeeded without evidence it did).
```

---

## Notes on using this doc

- These are meant to be pasted whole into a fresh session. Each is
  self-contained on purpose so you don't have to re-explain context — but
  each also tells the AI to go read the relevant handoff/reconciliation docs
  first rather than trusting stale memory of past sessions.
- Runs 3, 6, and 10 have file-check / consolidation built in. If a run stalls
  or runs long, it's fine to stop early and do the file-check anyway — better
  a short verified state than a long unverified one.
- If hardware or environment limits block a run (no GPU, no Windows SHM, no
  cargo toolchain), the correct outcome is a clear written finding about the
  limit, not a forced fake pass. Several past session notes in this project
  explicitly flag "claimed verified but wasn't" as the worst failure mode —
  worse than saying "couldn't verify, here's why."
- Order matters for 1-3 (affect engine, then Rust renderer, then wiring them
  together) but 4-9 are more independent — reorder them if something more
  urgent comes up, as long as the prerequisite pieces they depend on are
  actually done.

*Rear View Foresight LLC — Feic Mo Chroí*
