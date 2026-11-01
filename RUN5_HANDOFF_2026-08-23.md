# RUN 5 HANDOFF — 2026-08-23

> **⚠️ UPDATE — same day, after this handoff was first written.** A third
> camera-related system was found: `PubCast_Rust_Virtual_Camera_Recovery.zip`,
> a reconstructed `pubcast_camera` Rust crate. It's real — compiled clean,
> ran successfully, verified with the actual toolchain this session installed
> (the archive's own environment had no compiler and could only brace-match).
> It does NOT overturn anything below — checked its source transcript
> directly, and it confirms the same conclusion from a different angle: this
> crate was deliberately built "camera brain first, before deep renderer
> integration" and was never wired to the live skeletal-animation bridge
> (Run 2/3) or to anything matching the May architecture doc. Full assessment
> in `CAMERA_RECOVERY_ASSESSMENT_2026-08-23.md` and the crate itself in
> `pubcast_camera_recovery/` in this same folder/bundle. The recommendation
> at the bottom of this document is updated accordingly — see the new final
> section.

## Headline: the architecture doc describes a system that was never built here; the patches were already applied; PubPartner tests pass clean.

This run does not close the way it was scoped. Read carefully — the premise
had two real problems, both caught before doing anything destructive.

---

## Problem 1: PUBWORLD_CAMERA_UNIFIED_ARCHITECTURE.md describes a different, unbuilt system

The doc is dated **2026-05-11**. It describes a Rust "Camera Engine" with
`FrameBuffer`, `EngineMode` (Program/Preview/Donor/Transition),
`PreheatState` (60s min, FPS>55), `DonationState`, `ComputeBudget`, NDI/RTMP
output, 60fps frame buffering with <50ms latency targets. **None of this
exists anywhere in the tree**, confirmed by grep for every specific type
name it uses — zero hits in any `.rs` file, and zero `camera_engine.rs` file
anywhere.

What DOES exist, and was checked individually so as not to conflate them
with the doc's design:

1. **`runtime/spine/stations/camera_station.py`** — real, live (confirmed
   via `/api/runtime-spine/status`, returns `import_ok: true`, exports
   `AnimationAuthority`, `LocomotionSystem`, etc.). But it's a simple
   event-driven tracker (`{"live": bool, "target": performer_id}`), not a
   frame engine. Reads and writes local state, emits events, nothing about
   frame buffers or FPS.

2. **`modules/evo/distributed_engine.py`'s `EngineMode.CAMERA`** — a
   coincidental name match. This is a distributed compute failover role
   ("Twin Engine" primary + camera nodes as backup compute during overload,
   "Audio Never Sacrificed" principle) — architecturally unrelated to a
   virtual camera for a 3D scene. Confirmed by reading the module header.

3. **`modules/pubworld.py` (live, 72 lines) + `pubworld_router.py`** — real,
   confirmed live in Run 1's boot log (`[13] PubWorld router ready —
   /pubworld/ws live broadcast`). Minimal scene-JSON CRUD + WebSocket
   broadcast. Nothing like the doc's frame-buffering engine.

4. **Run 2/3's `rust_crate` + `avatar_performer.py`** — real, tested,
   working (Run 3's verified round trip). But it's for skeletal/avatar
   animation streaming, not voxel scene camera output. Different payload
   shapes, different purpose.

**None of these four is "the Camera Engine."** The elaborate broadcast
system in the architecture doc — as specifically described — appears to
have never been built. This is not a wiring gap Run 5 can close; it's a
design document describing work that either happened somewhere I don't have
access to, or never happened at all.

## Problem 2: the "manifest" is for an unrelated, different bundle

`VISUAL_PATCH_KIT_COPY_MANIFEST.md` is dated **2026-06-11**, a month after
the architecture doc, and describes an entirely different effort: a "Visual
Patch-Up Kit" (adaptive prop fitting, digital makeup, repair workflows,
approval lifecycle) under `runtime/spine/visual/` and
`runtime/spine/performers/` (`voxel_patch_adapter.py`, `patch_workflow.py`,
`styling_aide.py`, `interaction_fit.py`, `contact.py`, `motion_feedback.py`).
It mentions `PubWorld.jsx` only in passing, as one of many "reference-only,
not integrated" files in a `voxel_engine_reference/` folder.

**Checked directly: none of the Visual Patch Kit's specific named files
exist in this tree.** `runtime/spine/` is real and live (confirmed via the
same status endpoint above), but it's populated with a *different* set of
files — `stations/` (camera/director/pub), `performers/` (animation_authority,
locomotion, performer_state, replication) — not the visual-patch files the
manifest names. Only `event_bus.py` overlaps by name between what the
manifest describes and what's actually here.

**This manifest cannot be followed as file-placement instructions** for
this run's uploaded `PubWorld.jsx`, because the manifest is documenting a
different copy bundle's contents, not this session's files. Its own text
says so explicitly: *"This is a copy bundle only. Original source files
remain in the spine work folder"* — a folder this session doesn't have.

**What this means for the uploaded files:** `PubWorld.jsx` (695 lines, React)
has no live counterpart — the actual served frontend is plain HTML
(`static/pubworld_stage.html`), confirmed via grep (zero `.jsx` files
anywhere in the tree). The uploaded `pubworld.py` (431 lines, claims Rust
rendering-core integration) is also NOT the live `modules/pubworld.py`
(72 lines, plain JSON CRUD) — diffed, 492 lines of difference, confirmed
these are different files with different scope, not a patch/update
relationship.

---

## What WAS done — the PubPartner patches, real and complete

Despite the above, Run 5's step 1 (apply the three PubPartner patches) was
executable and done properly:

1. **PubPartner wasn't in the working tree at all** — it lives in a sibling
   directory (`WORKING_PROGRAM/pubpartner/`, alongside `WORKING_PROGRAM/
   pubcast/`, not inside it). Copied it in to `/home/claude/pubpartner`.

2. **All three patches (`store_py.patch`, `service_py.patch`,
   `engine_py.patch`) reported "reversed or previously applied" on dry-run.**
   Verified this wasn't a `patch` tool false-positive by grepping for each
   patch's specific added content directly:
   - `store.py`: `load_clock()` (vector clock recovery on restart) — present
   - `service.py`: `MANUSCRIPT_AUTHORED_FIELDS` (authored-vs-provenance field
     distinction) — present
   - `engine.py`: `_register_order()`, `_lww()`, `_advance()` (LWW conflict
     resolution machinery) — present

   **All three patches were already fully applied in the source this session
   copied from.** Nothing to do. This mirrors the Rust renderer situation in
   Run 2 — work assumed missing that had actually already happened.

3. **Ran PubPartner's real test suite as instructed:** `14/14 passed`,
   including the exact concurrency and sync-conflict tests these patches
   exist to protect (`test_concurrent_manuscript_commits_do_not_crash_or_corrupt`,
   `test_same_field_conflict_is_not_silently_overwritten`,
   `test_offline_bidirectional_sync_converges`). PubPartner is confirmed
   healthy and correctly patched.

---

## What was NOT done, and why

Steps 2-4 of the original Run 5 prompt (follow the manifest for file
placement, wire PubWorld.jsx to the Rust engine via Run 3's bridge, prove a
camera round trip) were not attempted, because doing so would mean building
against a fabricated premise: there is no "Rust engine" matching what the
architecture doc describes for PubWorld.jsx to wire into, and the manifest
doesn't apply to these files. Forcing an integration here would produce
something that looks like progress but doesn't correspond to anything real
— exactly the failure mode this project's handoffs keep warning about.

---

## Recommendation for whoever scopes the next run on this — UPDATED

Originally this section said the choice was binary: build the full May-doc
camera engine, or archive the uploaded PubWorld.jsx/pubworld.py pair. That's
now a three-way picture, and the real recommendation has changed:

**There are three camera-related systems, none connected to each other:**
1. Skeletal/avatar animation renderer (`rust_crate`, `ws_renderer.rs`) —
   live, tested, real round trip proven (Run 2/3)
2. The May doc's broadcast camera engine (FrameBuffer/PreheatState/etc) —
   never built anywhere found (this run)
3. `pubcast_camera` crate — 4 named voxel virtual cameras, compiles and
   runs clean, deliberately built camera-logic-only, never wired to
   anything (see `CAMERA_RECOVERY_ASSESSMENT_2026-08-23.md`)

**Updated recommendation:** system 3 is the most promising near-term path,
not system 2. It's real, working, structurally sound Rust that already
thinks in the right terms (named cameras, targeting, world position/rotation)
— closer to usable than anything else camera-related found across this
whole run. The concrete next step isn't building a new engine from the May
doc; it's a scoped integration run that feeds `pubcast_camera`'s
`CameraEngine.get_active_camera()` output (`world_position`, `world_rotation`,
etc.) into the *existing* live renderer bridge from Run 2/3, rather than
building a second, separate rendering path. That's real, bounded work for a
dedicated run.

The uploaded `PubWorld.jsx`/`pubworld.py` pair (React frontend, larger scene
system) and the May architecture doc's elaborate broadcast design remain
open questions needing a human decision — same as originally stated, just
now correctly scoped as two of three open items instead of the whole
picture.

*Rear View Foresight LLC — Feic Mo Chroí*
