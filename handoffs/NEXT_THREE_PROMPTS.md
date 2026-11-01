# NEXT THREE PROMPTS
## Ready to paste into a fresh session. Each is self-contained.

Written at the close of the affect/context modeling conversation. See
AFFECT_MODEL_CONCLUSIONS.md for the reasoning behind why prompt 1 is not
"add more to the engine" but "make it real" — the engine was never wired
into live traffic. Verified before writing this: zero callers outside
itself, alex_core.py still runs entirely on the old UserBattery enum.

---

## PROMPT 1 — Wire the emotional state engine into live traffic
### (Highest value. Do this one first.)

```
You are continuing work on PubCast AI. Read CONTINUE_FROM_HERE/affect_model/
AFFECT_MODEL_CONCLUSIONS.md and AFFECT_CONTEXT_MODEL.md in full before touching
anything — they contain corrected reasoning you must not re-break.

THE GAP: modules/affect_context_engine.py is complete, tested standalone, and
imported by nothing. Your job is not to add features to it. Your job is to make
it real.

1. Find the actual point where a user turn is first available before Alex or
   Jeremy generate a reply (start in modules/bots.py and modules/room_conductor.py).
   Call AffectContextEngine.evaluate() there, once per turn, per user_id/session_id.

2. Wire AffectContextEngine.to_legacy_battery() into modules/alex_core.py at the
   points that currently set self._user_battery directly (around lines 715-721).
   Do not remove the old enum — bridge to it, so nothing downstream breaks.
   Confirm 'observing' readings never overwrite existing battery state, per the
   model doc's explicit rule.

3. Wire route()['everyday']['meet_them_at'] into wherever the bot's system
   prompt gets assembled, as a steering line the model sees but the user never
   does.

4. Wire the persistence hooks (export_baseline/import_baseline,
   export_prior/import_prior) to actually save and load — even a flat JSON file
   per user_id under data/affect/ is enough for now. Verify: restart the
   process, confirm a known user's baseline survives.

5. Prove it end-to-end with a REAL multi-turn conversation through the actual
   /api/bots/{id}/chat route — not the standalone demo script. Fifteen turns
   minimum, and print the routed payload after each one.

Do not touch the scoring logic inside the engine. If you find a bug while
wiring it in, fix only what's needed to wire it — log anything else in the
handoff rather than fixing it in the same pass.
```

---

## PROMPT 2 — Build the memory state engine

```
Read CONTINUE_FROM_HERE/SESSION_HANDOFF_2026-08-19.md section 01.8 and
SYSTEM_AUDIT_2026-08-19.md before starting.

THE GAP: PubCast has seven memory-related modules and no single answer to "if
I want to remember something about this person, which one do I write to?"

1. Read all seven in full: universal_memory_system.py, alex_memory.py,
   cc_memory_store.py, memory_engine.py, personal_ai_memory_api.py,
   memory_ingestor.py, and the affect engine's baseline/prior persistence
   from prompt 1's work. For each: what does it actually store, who writes to
   it, who reads from it, does anything currently call it.

2. Determine ONE canonical store. This is likely universal_memory_system.py
   given it's already wired into main.py at [7h] and Jeremy Cricket already
   registers characters against it — but verify rather than assume.

3. Migrate the affect engine's PersonalBaseline/PersonalPrior into it as a
   real entity type, the same way manuscripts became a real entity type in
   PubPartner's sync protocol tonight. Confirm: a baseline persists correctly
   through the canonical store, not through the flat-file placeholder from
   prompt 1.

4. This closes a real gap named in AFFECT_MODEL_CONCLUSIONS.md: exhaustion vs.
   never-invested cannot be told apart in a 7-turn rolling window — the
   discriminator is whether the person was EVER engaged, which requires
   session-scale memory. Once the canonical store exists, extend
   diagnose_antecedent() to query it for "has this user ever shown high
   engagement in this session" rather than only looking at the last 7 turns.
   Verify this specific case: a person who was energetic an hour ago and flat
   now should read as exhaustion, not uninvested.

5. Note whether memory candidates (PubPartner's existing but unsynced
   MemoryGate/memory.db, flagged in session 1) should also route through this
   canonical store, or stay separate. Don't build it — just answer the
   question with evidence and put it in the handoff.

Do not build a new eighth memory system. If the honest answer is that the
seven need to collapse into two or three, say so and propose which, but do not
silently create another one while investigating.
```

---

## PROMPT 3 — Push PubCast toward market-ready completion

```
Read CONTINUE_FROM_HERE/SYSTEM_AUDIT_2026-08-19.md in full — it already has the
priority order. Do not replan from scratch.

THIS SESSION'S SCOPE — pick based on what's actually available in the
environment, in this order of value:

IF this is running on Zoidberg with real hardware:
1. Start Ollama, pull ministral-pubcast:3b and the Architect model. Confirm
   /api/bots/pete/chat produces a REAL reply, not a 503. This is the single
   highest-value unlock in the whole project — nothing has talked back yet.
2. Compile engine_host.cpp per the batch file in twin_engine/. Confirm the
   Python bridge finds it via Path A (Windows SHM), not Path C. Confirm
   /api/twin/status flips from mode=degraded to mode=ready.
3. Record real voice reference clips for at least Jeremy and Pete
   (data/voices/*.wav, 6+ seconds each). Confirm /api/tts/synthesize returns
   audio in their actual cloned voice, not the pyttsx3 fallback.

IF this is running in a sandbox without that hardware:
1. Resolve the character_engine.py collision from session 1 — give Jeremy
   Cricket's care engine (in not_yet_integrated/) its own filename
   (jeremy_care_engine.py) and wire it into modules/, without touching the
   existing modules/character_engine.py (bot turn-taking, unrelated system).
   Build the input scorer (score_complexity/score_velocity) the April handoff
   doc says it's still missing.
2. Mount pete_avatar.py — it imports clean, has a full 56-bone dual-rig
   definition, and is still an orphan. No renderer is needed to load the rig
   data; only a renderer is needed to display it.
3. Build the guest onboarding wizard that was scoped in detail earlier this
   session but never built: name, camera/mic permission, avatar pick from
   Manny/Sheila/Pete/foundry sprites or GLB import, session registration via
   the already-working /api/session/register endpoint. The three.js loading
   path is already proven in avatar_walk_test.html — reuse it, don't rebuild it.

Either way: run the five-round debug pattern from earlier tonight (cold start,
full log sweep, integration chain, error paths, edge cases) before declaring
anything done. Update the handoff. Rebuild the bundle zip. That is not
optional cleanup — it is the deliverable.
```

---

*One order-of-value note: prompt 1 matters most, because it's the only one
that turns tonight's entire emotional-modeling conversation from a well-
reasoned file into something Pete can actually act on. Prompts 2 and 3 are
real and valuable, but PubCast can survive not having them yet. It cannot
become "seeming genuine and on point, helping someone get through their day"
while the thing that would make that true has never once been called.*
