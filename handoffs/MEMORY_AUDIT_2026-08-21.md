# MEMORY ARCHITECTURE — AUDIT AND WIRING
## 2026-08-21

Executed the prompt from CONTINUE_FROM_HERE/NEXT_THREE_PROMPTS.md, prompt 2.
All required docs read first. All seven modules read in full, not sampled.
Two additional real facts discovered beyond the original seven, both load-
bearing. All findings below are evidence-backed — grep results, direct code
reads, and live process tests — not inferred from filenames or docstrings.

---

## THE REAL SHAPE (not seven competing systems)

The honest finding: it isn't seven memory stores in competition. It's a much
smaller number of real things, plus several thin layers that only *look* like
separate stores from the outside.

```
memory_engine.py          ← the one real durable substrate for character/
  (SQLite, memory_events)   production memory. Flat event log, room/session/
                             user scoped.

universal_memory_system.py ← NOT separate storage. In-memory per-character
  (CharacterMemoryBank)      cache/view. write-through's every entry to
                             memory_engine on add(), reloads from
                             memory_engine on load_from_db(). Confirmed by
                             direct read of _persist_entry() and
                             load_from_db().

memory_ingestor.py        ← the real gatekeeper. Dedup (fingerprint cache),
  (MemoryIngestor)           decay filter, importance scoring, kind
                             classification, correction handling. Fans a
                             single ContextBlock out to up to FOUR
                             destinations by content kind: Alex,
                             JeremyCricket, UniversalMemorySystem,
                             memory_engine.

personal_ai_memory_api.py ← thin REST facade. NOT its own store. /write and
                             /query delegate to MemoryIngestor. /recent
                             passes through to memory_engine directly.

alex_memory.py            ← a complete, sophisticated, real, PARALLEL
  (the Alex class)           reimplementation of Alex — own AIState,
                             UserBattery, EmotionalState, grounding anchors,
                             remember_moment(), generate_bridge_packet().
                             COMPLETELY DORMANT. Instantiated nowhere in
                             production — only in tests/test_memory_systems.py.
                             1,363 lines, zero live use.

cc_memory_store.py        ← Code Collector's own product memory (code capture,
                             version lineage, telemetry-weighted importance).
                             Different product, different domain, by its own
                             docstring's explicit words. Correctly separate —
                             not part of this question.

alex_core.py's MemoryCore ← NOT ONE OF THE ORIGINAL SEVEN, BUT THE ACTUAL LIVE
  (not in the original 7)   ANSWER. Alex's real, live, private continuity
                             store. Confirmed independent of memory_engine —
                             own diary dict, own keyword/emotion indices,
                             own disk format (one JSON file per memory,
                             data/alex/{user_id}/{YYYY-MM}/mem_*.json). This
                             is what /api/alex/message actually writes to.
```

---

## TASK 1 — What each stores, who writes, who reads, is it live

| Module | Stores | Writers (live) | Readers (live) | Live? |
|---|---|---|---|---|
| `memory_engine.py` | Flat event log, room/user/session scoped | `UniversalMemorySystem.add()` (write-through), `MemoryIngestor._write_to_engine()` | `recent_for_room`, `recent_for_user`, `context_summary`, `personal_ai_memory_api`'s `/recent` | ✅ Real, live, actively written |
| `universal_memory_system.py` | Per-character in-memory bank + relevance search | `MemoryIngestor._write_to_universal()`, `.store()` API | `room_conductor.py` (Jeremy Cricket), `.search()`/`.get_recent()` | ✅ Live — wired at `[7h]`, consumed by `RoomConductor` at `[15b]` |
| `memory_ingestor.py` | Nothing itself — router only | N/A | N/A | ✅ Live — 3 confirmed real callers: `personal_ai_memory_api.py`, `session_resurrector.py`, internal `ingest_many()` |
| `personal_ai_memory_api.py` | Nothing itself — facade only | N/A | N/A | ✅ Live — mounted, `configure_personal_memory_api()` called with the real ingestor instance |
| `alex_memory.py` | Own SQLite (schema real, never initialized) | Nothing in production | Nothing in production | ❌ **Dormant.** Only caller anywhere in the tree is `tests/test_memory_systems.py` |
| `cc_memory_store.py` | Code capture, versioning, telemetry weights | Code Collector extension (separate product) | Code Collector extension | Different domain — out of scope |
| `alex_core.MemoryCore` | Alex's private diary — content, emotional valence/intensity, keywords, per-date JSON files | `AlexCore.process_message()`, `MemoryIngestor._write_to_alex()` fallback path | `AlexCore.recall()`, `AlexJeremyBridge._packet_from_alex()` | ✅ **This is the real one.** Confirmed via `/api/alex/message` live test |

**One precise, previously-undocumented gap found:** `MemoryIngestor` is constructed in `main.py` with `memory_system=universal_memory_system` and `alex=alex_core_instance` — both live. `cricket_registry=` is **never passed**, defaults to empty, and `register_cricket()` is never called for any character anywhere in the tree. JeremyCricket's per-character persistent memory routing is fully built into `MemoryIngestor`'s code and **completely dead in practice**. A block classified as needing character-specific persistent memory silently reaches nothing — `_resolve_cricket()` always returns `None`.

---

## TASK 2 — ONE canonical store: verified, and corrected

The prompt's own working hypothesis — `universal_memory_system.py` is likely
canonical — is **half right, verified, and needs one real correction.**

`UniversalMemorySystem` is genuinely canonical **for character memory** — this
is confirmed, live, and correct as-is. Room Conductor and Jeremy Cricket
correctly use it for what Pete, RePete, Sir Purfluous, and Jeremy know as
characters.

But the prompt's task 3 needs a **different** canonical store, and applying
the character-memory answer to it would have been a real mistake.
`PersonalBaseline`/`PersonalPrior` from the affect engine are **private,
per-user behavioral data about one specific person's relationship with Alex**
— not character-shared memory. `AlexJeremyBridge`'s own docstring states the
design principle directly: *"Alex stays sovereign and private. Jeremy only
receives a minimal packet."* Writing someone's personal baseline into the same
store Pete and Sir Purfluous read from would violate that stated principle,
even though it would have technically worked.

**Conclusion: two canonical destinations, not one, matching a distinction the
architecture already draws for itself:**

| Data is... | Canonical store |
|---|---|
| Character-shared (what Pete/Jeremy/Sir Purfluous know) | `universal_memory_system.py` |
| Private per-user (what Alex knows about *you* specifically) | `alex_core.py`'s `MemoryCore` |

This is not "two systems where there should be one" — it's the same
private/shared split `AlexJeremyBridge` already enforces for everything else
it does. The affect engine's data belongs on the private side.

**`alex_memory.py` should be marked deprecated, not deleted.** It's real,
well-built, and 1,363 lines of work — but it's an orphan that already
happened once, silently, and nobody flagged it until this audit. Recommend a
clear docstring warning at the top of the file rather than removal, so a
future session doesn't build against it thinking it's live.

---

## TASK 3 — Migration executed and verified

Moved the affect engine's `PersonalBaseline`/`PersonalPrior` persistence out
of prompt 1's flat-file placeholder (`data/affect/{user_id}.json`, explicitly
called a placeholder in that prompt's own text) and into `MemoryCore` as a
real, first-class entity — matching `MemoryCore`'s own existing pattern (it
already privately owns `_alex_state.json` as a sibling to the dated diary
folders; `_affect_state.json` follows the identical convention).

**Code changes — `modules/alex_core.py`:**
- `MemoryCore.save_affect_state()` / `load_affect_state()` — new methods,
  same atomic-write pattern (`.tmp` then `.replace()`) already used elsewhere
  in the class.
- `AlexCore._load_affect_state()` / `_save_affect_state()` — rewritten to
  call through `self.memory.save_affect_state()`/`load_affect_state()`
  instead of writing to the old flat file. One-time migration: if
  `MemoryCore` has no affect state yet, checks the old placeholder path once,
  imports it if found, and never writes there again.

**Verified against the real running app, not asserted:**
1. Confirmed the old placeholder file from prompt 1's actual test
   (`data/affect/wiring_test_user.json`, 16 real observations) still existed.
2. Restarted PubCast clean.
3. Queried the same `user_id` through `POST /api/alex/message`. Result:
   recognized immediately — `ai_state: companion`, correct operating note —
   not a cold start.
4. Confirmed the new canonical file exists at
   `data/alex/wiring_test_user/_affect_state.json`, inside `MemoryCore`'s own
   directory, with 18 observations (16 migrated + new turns from this
   session).
5. Confirmed the **old** placeholder file's mtime is frozen at the timestamp
   from *before* this session's restart — proof the code genuinely stopped
   writing there, not just that a new file also happens to exist.

---

## TASK 4 — Exhaustion vs. never-invested: closed, with a real test-design
## catch worth recording

**The fix:** `SessionState` gained an uncapped, session-lifetime peak-arousal
tracker (`peak_arousal_this_session`, `peak_arousal_turn`) — deliberately
*not* subject to the 7-turn `ANTECEDENT_WINDOW`'s eviction, unlike everything
else in that class. `diagnose_antecedent()` now accepts this as two new
optional parameters and uses them two ways:
- `exhaustion`'s score gains a real term when a genuine peak exists outside
  the current window (`had_real_peak`), with the evidence stated explicitly:
  *"was highly engaged N turns ago (arousal X), flat since."*
- `uninvested`'s score is **zeroed, not merely discounted**, when
  `had_real_peak` is true — because a real session-scale peak is direct
  evidence *against* "never engaged," not just a competing explanation.

This is genuinely session-scale (kept for the life of the in-process
`SessionState` object, spanning the whole open session) rather than
cross-session — cross-session would require a `MemoryCore` round-trip on
every turn, which this deliberately avoids for cost reasons. That scope
matches exactly what the prompt's own test case needs: "an hour ago,"
within one still-open session.

**Verified against the exact case in the prompt — and a real bug caught along
the way.** First attempt at the test read `unknown`, not `exhaustion`. Root
cause: `arousal_z` in this engine is driven by punctuation/caps/profanity —
not by message length or exploratory content, which is what "energetic"
intuitively suggested for the test script. Long, thoughtful, punctuation-free
messages never crossed the peak threshold the new code checks for. Fixed the
*test*, not the implementation — rewrote the burst with real exclamation-mark
energy matching the engine's actual, already-correct definition of arousal.
Re-run:

```
cause: exhaustion
evidence: ['response gaps shortening', 'novelty collapsing',
           'was highly engaged 10 turns ago (arousal 1.6), flat since']
PASSED
```

Worth recording precisely because it's the kind of mistake a future session
would repeat: "energetic" in this model means *measured* energy (punctuation,
caps, pace), not a human reader's intuitive sense of an exciting message.

---

## TASK 5 — PubPartner's memory candidates: answered, not built

`pubpartner_federation/memory.py`'s `MemoryGate` read in full — 26 lines. Its
entire schema: `candidate_id, text, metadata, created_at, promoted_at`. A
flat capture → list → promote triage queue. No author/character/session
association anywhere in the schema (`metadata` is a free JSON blob a caller
*could* stuff a user_id into, but nothing in the schema requires or expects
it).

**Recommendation: memory candidates should stay in PubPartner, get the same
sync treatment manuscripts already have, and remain architecturally separate
from PubCast's canonical stores. Not routed through PubCast at all.** Three
concrete reasons:

1. **Different service boundary, on purpose.** PubPartner runs detached from
   PubCast by design — the whole resident/portable "twin" architecture proven
   in session 1 depends on a portable node working with PubCast unreachable.
   Routing candidates through PubCast's in-process `MemoryIngestor` would
   break exactly the portability the user described building toward.

2. **Different workflow shape.** `MemoryGate` is a human-reviewed queue, not
   a scored/classified/routed store. It has no `importance`, `memory_type`,
   `author_id`, or destination concept — forcing it through
   `MemoryIngestor`'s `ContextBlock` model would need a real schema migration
   on PubPartner's side, out of scope for "answer, don't build."

3. **The actual missing piece was already identified in session 1, correctly,
   and it isn't canonicalization.** Manuscripts sync between resident and
   portable nodes via a real vector-clock protocol. Memory candidates don't —
   `engine.py`/`store.py`/`protocol.py` have zero references to memory, and
   `Entity.entity_type` is a free string, meaning extending sync to cover
   memory candidates is the same bounded task session 1 already scoped, not a
   new one. That gives your portable Alex and resident Alex the same memory
   for the same reason manuscripts already do — which is the actual feature
   being described, and has nothing to do with PubCast's canonical stores.

If these two systems should ever meet, the right shape is a **deliberate
integration at the API boundary** — a promoted PubPartner candidate calling
PubCast's already-live `personal_ai_memory_api.py`'s `/write` endpoint — not
folding one system into the other's storage.

---

## WHAT WAS NOT BUILT (per the prompt's own constraint)

No eighth memory system was created. Every change extended an existing file's
existing pattern:
- `MemoryCore` gained two methods matching its own established convention.
- `diagnose_antecedent()` gained two optional, backward-compatible
  parameters.
- `SessionState` gained three fields, following the class's existing shape.

`JeremyCricket`'s dead routing path and `alex_memory.py`'s dormant status are
both left exactly as found — flagged, not touched, per the prompt's actual
scope.

---

## FOR THE NEXT SESSION

- Wire `register_cricket()` for at least one character, if JeremyCricket's
  persistent-memory routing should actually go live — currently built,
  dead.
- Add the deprecation docstring to `alex_memory.py`.
- If PubPartner memory sync is picked up: extend `Entity.entity_type` to
  cover `memory_candidate`, following the exact pattern that already made
  manuscripts sync — session 1's own finding, still the correct next step.
