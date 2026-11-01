# PubCast emotional systems wiring — 2026-10-02

## Implemented

Added `modules/emotional_orchestrator.py`, a session/subject/room-scoped coordination broker between the existing Alex AffectContextEngine, Affect Dynamics, Jeremy-facing guidance, PubPartner packets, and secondary EQ/PEQ/CRE-EQ/conversation observers.

The broker does not create a new appraisal authority. Signals carry source, subject, session, room, confidence, provenance, expiry and event identity. Retries are idempotent by source/event. Stale signals expire. Room-scoped signals do not leak across rooms. Cross-engine disagreement is retained and exposed instead of silently averaged away. Clinical-style PEQ/CRE-EQ hypotheses are explicitly advisory-only and down-weighted.

`AlexJeremyBridge.process_user_turn()` now publishes the authoritative Alex affect reading plus Affect Dynamics trajectory into the coordinator and persists the resulting `emotional_coordination` snapshot in the bridge-safe packet. `PubPartner` includes that bounded snapshot in its compact Alex block, so guest/provider context can use coordinated emotional evidence without receiving Alex private memory.

`AlexJeremyBridge.publish_emotional_signal()` is the production broker seam for secondary EQ, Jeremy EQ, Conversation, PEQ and CRE-EQ engines. It accepts observations only; it cannot request room actions or mutate Alex appraisal. `jeremy_whisper()` consumes only high-level conversation pressures (processing time / clarification pressure), preserving Jeremy's protocol role.

## Authority map

- AffectContextEngine / Alex: primary personal-baseline appraisal.
- Affect Dynamics: temporal continuity/performance trajectory, downstream of appraisal.
- EQ / Jeremy EQ: secondary observations.
- PEQ / CRE-EQ: secondary hypothesis signals only until donor evaluation promotes a demonstrated responsibility; clinical-style hypotheses are down-weighted and never treated as validated truth.
- Conversation systems: may publish conversation-state observations and consume pressures, but retain their own conversation authority.
- Jeremy: receives bounded guidance; no private Alex memory is exposed.
- PubPartner/cartridges: receive the coordinated snapshot as context; the speaking model retains final language ownership.
- Choreography/Director: remain downstream advisory consumers; no camera or animation authority was moved into emotional coordination.

## Verification

`python -m compileall` passed for all modified emotional/bridge/PubPartner modules.

Focused emotional + PubPartner + vessel regression suite: **139 passed**.

This slice does not bulk-promote the preserved September 7 PEQ/CRE-EQ donor. The October recovery handoff explicitly requires isolated comparison, subject authorization, lifecycle cleanup, room-scoped delivery and provenance review before authority promotion. The new broker is the safe production seam through which that donor can now be evaluated without creating competing emotional truth or persistence.
