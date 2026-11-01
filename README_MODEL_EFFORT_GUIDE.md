# README — Run Bundle Contents & Model/Effort Guidance

> **⚠️ Note added 2026-08-23, after Runs 1-3 actually executed:** the folder
> map below (esp. "the actual working base for Run 1") describes the state
> as planned, before Run 1 discovered `affect_wiring.py` was unnecessary
> duplicate work — the real integration was already live in `alex_core.py`.
> Runs 1, 2, and 3 are now complete. See `RUN1_HANDOFF_2026-08-23.md`,
> `RUN2_HANDOFF_2026-08-23.md`, `RUN3_HANDOFF_2026-08-23.md`, and
> `NEXT_TEN_RUNS_CORRECTED_2026-08-23.md` for current state. The model/effort
> guidance below for Runs 4-10 is unaffected and still applies.

This zip pairs with `NEXT_TEN_RUNS.md` (included at the root). Start a fresh
session, upload the relevant files for that run (see the map below), paste
the run's prompt block, and let it go.

---

## Folder map

```
NEXT_TEN_RUNS.md          — the ten prompts themselves
modules/                  — the full merged The-Prime modules tree (166 files),
                             including affect_context_engine.py, affect_wiring.py,
                             unified_bridge.py — the actual working base for Run 1
                             and everything after it
handoffs/                 — session handoff docs, audits, the affect model's own
                             design docs. Reference material Runs 1 and 4 point to.
run2_rust/                — the 8 Rust/WGSL files for the renderer inventory pass
run3_bridge/               — unified_bridge.py + bulletproof bridge + twin engine
                             demo/service/test files for Run 3's wiring pass
run5_pubworld_camera/     — PubWorld.jsx, pubworld.py, marching_cubes.py,
                             distributed_engine.py, the architecture doc, the
                             copy manifest
run5_patches/              — the three PubPartner patches (store/service/engine)
run6_bubble_stack/         — Bubble_Stack_Dossier.zip, the reconciliation doc,
                             the choreography/physics handoff zip
```

Runs 4, 7, 8, 9, and 10 don't have a dedicated folder — they work directly
against whatever's in `modules/` plus whatever the live repo state is by the
time you get there. That's intentional: those runs are about reading and
wiring existing code, not receiving new files.

---

## Model and effort level per run

This maps run complexity to model choice. The pattern: **read-heavy,
single-file, or verification-only work doesn't need your top model — save
that for runs that require holding a lot of cross-file state at once and
making judgment calls under ambiguity.**

| Run | What it actually demands | Model | Effort |
|---|---|---|---|
| **1** | Multi-file wiring (room_conductor → alex_core → bots.py), has to trace existing patterns before extending them, then prove it with a live 15-turn test. Medium-high complexity, moderate length. | **Opus** | High — this is the highest-value run and small mistakes here (like the three wrong method signatures caught this session) cascade into everything after it |
| **2** | Read 8 files, run `cargo build`, report findings. No code written, no design decisions. Long but mechanically simple. | **Sonnet** | Medium — thoroughness matters more than reasoning depth |
| **3** | Real systems wiring across a process boundary (Python↔Rust/C++), plus a file-check. Genuine debugging likely required if the SHM path doesn't work in a sandboxed environment. | **Opus** | High — cross-language bridge work with real failure modes (this run explicitly anticipates the Windows SHM path may not work in-sandbox and needs a judgment call on fallback) |
| **4** | Reading seven-ish modules, comparing what they do, deciding on ONE canonical store. Real architectural judgment, but bounded scope. | **Opus** | Medium-high — the decision quality here (a wrong canonical store choice) is expensive to undo later |
| **5** | Apply patches (mechanical), then follow a manifest (mechanical), then wire per an existing architecture doc (moderate). Not much novel reasoning — mostly following written instructions faithfully. | **Sonnet** | Medium |
| **6** | Re-run an existing regression test (mechanical), then real integration work replacing a synthetic stub with real geometry (moderate-high, since "don't repeat the fake verification mistake" is an explicit constraint). | **Opus** | Medium-high |
| **7** | Two fairly independent, well-scoped features (mount an orphan module, build an onboarding wizard) reusing existing patterns. Clear success criteria. | **Sonnet** | Medium |
| **8** | Investigative — "does this even exist/work in this environment" is the real question, with an explicit permission to find a negative result. Low risk of costly mistakes since the honest failure mode is well-specified. | **Sonnet** | Medium — could drop to low if the environment clearly lacks GPU/audio hardware and the run resolves to "documented the gap" quickly |
| **9** | Cross-wiring two already-built systems (affect engine, choreography). Requires reading dispatch code carefully to find the right insertion point without over-building. | **Opus** | Medium — narrow scope keeps this from needing max effort, but "read the actual dispatch code, don't guess" makes it not a Sonnet-safe skim job |
| **10** | Full-stack bring-up, cross-checking everything, writing the doc that future sessions will trust most. This is the run most likely to surface accumulated drift from 1-9 and needs to make good judgment calls about what's real vs claimed. | **Opus** | High — this is the integrity checkpoint for the whole ten-run arc; a sloppy pass here undermines the verification discipline the whole plan is built on |

**General principle for you, Josie, choosing in the moment:** if a run
mostly involves reading, running, and reporting — Sonnet, medium effort is
plenty and saves you cost/quota. If a run involves making an architectural
call that's expensive to reverse (which store is canonical, how a bridge
fallback should behave, what the final handoff claims), that's where Opus
and higher effort earns its cost. When in doubt, the "verification standard"
language baked into each prompt (claim nothing without execution evidence)
does a lot of the safety work regardless of model — but a stronger model is
less likely to convince itself a shortcut counts as verification.

---

## Every 2-3 runs: reload files

Since these are meant to be separate sessions, upload this zip's relevant
subfolder fresh each time rather than assuming a prior session's container
state persists — it won't. Runs 3, 6, and 10 have file-check steps built in
specifically to catch drift and tell you what to re-collect before the next
batch.

*Rear View Foresight LLC — Feic Mo Chroí*
