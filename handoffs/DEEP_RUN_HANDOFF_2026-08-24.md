# DEEP RUN — WIRING, BUGS, AND HONEST ACCOUNTING
## 2026-08-24

---

## 1. THE THREE OPEN WIRING ITEMS — ALL CLOSED AND VERIFIED

These were documented across Runs 3, 6, and 9 and left open. All three are now
live, and each was verified by execution, not by inspection.

### 1a. AvatarPerformerManager — now actually starts

**A real hang bug was found and fixed before wiring.** `PerformerStreamer.connect()`
was `while True:` with no exit condition. Calling `start()` from the FastAPI
lifespan with no renderer running — the normal case at boot — would have hung
app startup **forever**. My earlier caution about not wiring this blindly was
justified.

Fix: `connect(max_attempts=N)` and `start(max_attempts=N)` returning bool.
Unbounded retry is preserved for the background reconnect path, where it's correct.

Verified both directions:
```
renderer down:  "[5b/12] AvatarPerformerManager started — renderer offline
                 (frames will buffer)"     boot time 4.7s, no hang
renderer up:    "[5b/12] AvatarPerformerManager started — renderer connected"
```
**The app now genuinely links to the Rust renderer at boot. That connection had
never existed.**

### 1b. Bubble Stack routes — mounted

`/api/bubble-stack` and `/api/bubble-stack/schema` both return **200**.

Two more missing modules were found during wiring and recovered from the dossier
using the same extraction method as Run 6:
- `modules/skeleton_tracker.py` (47 lines)
- `modules/posture_library.py` (57 lines)

Transitive dependency chain resolved fully. The guarded try/except worked as
designed — the app booted normally while the routes were still failing.

### 1c. Affect→Choreography bridge — wired to live traffic

Not just instantiated. Registered as a hook on `/api/alex/message` via a
`set_choreo_hook()` setter (matching the file's existing DI pattern, avoiding
a circular import with main).

Verified end-to-end through real HTTP POSTs:
```
Affect choreo: pete state=flow drama=1.00 → action='relaxed_idle' intensity=2.50 weight=0.36
Affect choreo: pete state=flow drama=0.59 → action='relaxed_idle' intensity=1.67 weight=0.44
response codes: {200}
```
Hook failures are caught and logged non-fatally — a choreography problem can
never break the chat response a user is waiting on.

---

## 2. A REAL PRODUCTION BUG FOUND AND FIXED

**`/studio/ws` crashed on every single connection.**

```
AttributeError: 'StudioWebSocketHandler' object has no attribute 'handle'
```

`main.py` called `studio_ws_handler.handle(ws)`. That method **has never
existed**. The class exposes `connect()`, `handle_message()`, `disconnect()`.

The Studio Control Room was silently broken — nobody would have found this
until someone opened it. Fixed by driving the real lifecycle with proper
`WebSocketDisconnect` handling and a `finally` cleanup.

Verified: `/studio/ws` now connects and sends `initial_state`.

**This is the single most valuable find of this run.** It was only surfaced
because the test suite got run, and only diagnosed because I tested the real
endpoint instead of trusting the test's stale assumption about the path.

---

## 3. TEST SUITE: 556 → 562 PASSING, 25 → 19 FAILING

Six fixed, zero regressions.

### What was actually wrong with the WebSocket tests (7 → 0 failures)

Two genuinely different problems, and it mattered to tell them apart:

**Problem A — tests assumed the first frame is a reply.** The Hub pushes
server-initiated frames on connect: `history` (last 50 messages) and `presence`
(join announcement). That is **correct, deliberate chat behaviour** — a room
should announce joins. The tests asserted on frame #1 and got `presence`.

Fixed with a `recv_type()` drain helper that skips known server-push types —
which is what a real client does. **This is a test bug, not an app bug**, and
I verified the frame ordering directly before deciding that.

**Problem B — tests encoded a stale architecture.** They connected to
`/ws/unity` and `/ws/studio`. The real endpoints are `/unity/ws/{client_id}`
and `/studio/ws`. So `/ws/unity` correctly falls to the `/ws/{room}` catch-all
and is just an ordinary room name. Updated to assert the real contract — and
doing so is what exposed the `/studio/ws` crash above.

**Problem C — my own first fix was wrong.** I asserted global hub cleanliness,
but sibling tests in the same file deliberately dirty the hub. Corrected to
before/after delta snapshots.

### The remaining 19, honestly categorised

**6 are test-ordering pollution, not real failures.** All of
`test_main_route_authorization_parity.py` **passes in isolation** (6/6) and
only fails in the full-suite run. Shared global state between tests.

**13 are real** — they fail in isolation too:
```
test_06_regression                4
test_pubcast_smoke                3
test_02_routing                   1   (1 failed / 61 passed)
test_no_user_audit                1
test_frontend_contract_compat     1
test_cast_staged_integration      1
test_alex_little_one_disabled     1
test_memory_systems               1
```

I did **not** fix these. Thirteen real failures across eight files, several
touching auth and contract semantics, is its own scoped run. Rushing them at
the end of a long session is how regressions get introduced — and I'd rather
hand you an accurate count than a rushed green.

---

## 4. FINAL STATE — VERIFIED

```
health:                    200
/api/bubble-stack:         200
doctor required failures:  0
boot time:                 ~4.7s
tests:                     562 passed / 19 failed (6 of which are pollution)
```

Files changed this run:
```
main.py                          AvatarPerformerManager.start, bubble routes
                                 mount, affect bridge + hook, /studio/ws fix
modules/avatar_performer.py      bounded connect() and start() — hang fix
modules/alex_routes.py           logger, _choreo_hook, set_choreo_hook(), hook call
modules/skeleton_tracker.py      NEW — recovered from dossier
modules/posture_library.py       NEW — recovered from dossier
tests/test_04_websockets.py      recv_type() helper, real-contract assertions
```

---

## 5. WHAT'S NEXT — ordered by value

### Immediate (next run)
1. **The 13 real test failures.** Start with `test_06_regression` (4) and
   `test_pubcast_smoke` (3) — biggest clusters, likely shared root causes.
2. **Test isolation.** 6 failures are pollution from shared global state. A
   conftest fixture resetting `hub.rooms` between tests likely fixes all six
   and prevents a whole class of future false alarms.

### The subsystems you named
3. **Alex / EQ actually working.** The affect engine is live and now drives
   choreography. The next real step is the **`dramatic_intensity` → prosody
   and facial performance** link — the affect model's own docs call for it,
   and the bridge pattern from this run is directly reusable.
4. **Mocap accuracy + facial mocap + phone camera.** `mocap_precision.py` and
   `modules/evo/facial_performance.py` both exist. Facial currently reports
   *"DeepFace not available — simulation mode"* and *"MediaPipe not available —
   landmark analysis disabled"* at every boot. **That's the concrete blocker:
   two missing packages.** Installing and testing them is a well-scoped run.
   The phone-camera path needs WebRTC ingest, which does not exist yet.
5. **Studio actually assembled.** `/studio/ws` works as of today. Next:
   verify `studio_control_room.html` against the now-working socket, and check
   `studio_camera_preflight.py` (currently orphaned).

### Structural, still open
6. **`BoneMask` / `AnimationLibrary` / 3 more undefined types** blocking
   `full-animation`. Needs design scoping before implementation — do not guess.
7. **`pubcast_camera` crate** — compiles and runs standalone, never connected.
8. **PubWorld decision** — a human call: build the May-doc camera engine, or
   archive it? Nothing should proceed there until you decide.
9. **`alex_memory.py` deprecation banner** — proposed in Run 4, still unwritten.
   1,363 lines that look current at a glance.
10. **Deployment reality:** `PUBCAST_JWT_SECRET` still unset (insecure default
    warns at every boot), and **everything is container-only — no GitHub push
    has ever happened.** The bundle zip is the only durable artifact.

---

## 6. THE HONEST NOTE

Three things in this run I got wrong before getting right, all caught by
running rather than reasoning:

- I nearly wired `AvatarPerformerManager.start()` without checking `connect()`.
  It would have hung boot forever.
- My first WebSocket test fix asserted global state that sibling tests dirty.
  Wrong for a reason I should have anticipated.
- I assumed the auth-parity count went 5→6 was a regression I caused. It
  wasn't — running the file alone showed 6/6 passing.

The pattern that keeps holding: **the errors that got caught were caught by
execution; the ones that would have shipped were the ones where I reasoned
about code instead of running it.**

*Rear View Foresight LLC — Feic Mo Chroí*
