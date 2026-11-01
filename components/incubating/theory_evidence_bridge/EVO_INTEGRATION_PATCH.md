# Wiring theory_graph / evidence_layer / contradiction_engine into evo_integration.py

## 1. File placement

```
modules/theory_graph.py
modules/evidence_layer.py
modules/contradiction_engine.py
modules/theory_evidence_bridge.py   <- new, composes the three per their own
                                        documented integration contracts
```

## 2. Add to EVOOrchestrator.__init__ (evo_integration.py)

Alongside the existing:
```python
self.epete = EPete(...)
self.pete  = PeteCharacter(epete=self.epete)
```

add:
```python
from modules.theory_evidence_bridge import create_theory_evidence_bridge

self.theory_bridge = create_theory_evidence_bridge(session_id=session_id)
```

(`EVOOrchestrator.__init__` doesn't currently take a `session_id` — add one,
defaulting to a generated id the same way `EvidenceLayer`/`TheoryGraph`
already do internally when none is passed.)

## 3. Call it from tick()

`tick()`'s real steps are Facial analysis → VDI → Prosody → SSML →
Switchblade → Engine → Camera manager. Add the bridge call after Step 2
(VDI calculation), since both `evidence_layer.py` and `theory_graph.py`'s
own docstrings specify "after VDI update":

```python
# ── Step 2.5: Theory/Evidence/Contradiction tick ─────────────────────────
bridge_result = self.theory_bridge.tick(
    vdi_report=vdi_report,
    emotional_state=emotional_state,
    current_topic=getattr(scene_state, "current_topic", ""),
    audience_size=getattr(scene_state, "characters_in_frame", []) and
                  len(scene_state.characters_in_frame) or 0,
    is_live_broadcast=False,  # wire to your real broadcast-state flag
    identity_moment_active=vdi_report.identity_moment,
)
```

## 4. Feed the briefing to Pete

Wherever `main.py`/`bots.py` builds Pete's system context (the same place
`byok_manager.py`'s `build_character_packet` or similar assembles
character state), add:

```python
theory_briefing = evo_orchestrator.theory_bridge.get_briefing()
```

and include it in the prompt the way other context blocks are included.

## 5. Distill at session end

Wherever `EVOOrchestrator.stop()` or the session-end hook lives:

```python
async def stop(self) -> None:
    self.theory_bridge.distill()
    self._running = False
    await self.epete.stop()
```

## Verified before delivery

`theory_evidence_bridge.py` was run standalone against six synthetic ticks
(identity-moment entry, identity-moment sustained after 5 ticks, a
tension+arousal spike, and a presence-mode shift from `INTIMATE_GROUP` to
`PUBLIC`). Real markers were created, real theories tracked, real presence
computation ran, `distill()` completed without error. This was NOT run
inside the actual `evo_integration.py` — that file wasn't available as a
full, editable copy this session, only via read-only search — so the
`EVOOrchestrator.tick()` call site above is written correctly against its
real signature but hasn't been executed inside the live class itself.
Confirm step 3's exact insertion point against your real file before
merging.

## Honest, flagged design decision inside the bridge

`contradiction_engine.py`'s own docstring says its instability signals are
"Used by TheoryGraph to influence theory confidence," but no code doing
that exists in any of the three files as uploaded. `theory_evidence_bridge.py`
implements that stated intent itself (instability level → confidence delta
→ `graph.propagate()`), using weights this bridge invented, not weights
recovered from existing code. Worth a real design pass rather than treating
it as settled.
