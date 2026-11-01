# STABILITY RUN — FINDINGS LOG
## Date: 2026-08-19 (continuation of Breaking Dawn session)
## Engineer: Claude Raines

---

## What was done

Cold-started all three services from scratch. Read every startup log in full.
Triaged every error and warning. Fixed the one real breakage. Re-verified the
full integration chain after the fix.

---

## Fix applied

**`data/bots/sir_purfluous_waiting_room.json` — invalid BotConfig**

The file was a rich character design document in the wrong schema. It had
`host_id` instead of `bot_id`, and was missing `name`, `provider`, `model`,
and `api_key_env` — the 5 fields Pydantic requires.

Fix: injected the 5 required fields at the top of the JSON, preserving all
existing character content (Pydantic ignores extra fields). Validated against
the real BotConfig class before restarting. After restart:

- Before: ERROR logged, 4 bots loaded
- After: no ERROR, **5 bots loaded**

Values used:
- `bot_id`: `sir_purfluous_waiting_room`
- `name`: `Sir Purfluous (Waiting Room)`
- `provider`: `ollama` (matches working `sir_purfluous.json`)
- `model`: `ministral-pubcast:3b` (matches working config)
- `api_key_env`: `""` (same as working config — Ollama doesn't need a key)

---

## Errors and warnings triaged — full list

| Item | Bucket | Notes |
|------|--------|-------|
| sir_purfluous_waiting_room.json invalid | FIX NOW | ✅ FIXED |
| VoxelBridge TCP connection failed → Path C | EXPECTED | Bridge needs a C++ renderer twin engine on the other end. **Correction from user, 2026-08-19 post-run:** the engine exists — a custom build made during an earlier period when Unreal integration was under consideration — it's just not deployed here and not the current priority. Path C (filesystem) is the correct fallback while it stays parked. Not a gap to fix; a real component sitting off to the side deliberately. Don't chase this unless explicitly asked to reconnect it. |
| IRM emergency mode, batch reduced to 500 | EXPECTED | Direct consequence of VoxelBridge on Path C. Not an independent problem. |
| posix_ipc not available, SHM disabled | EXPECTED | No shared memory in this sandbox. |
| PUBCAST_JWT_SECRET not set | FIX SOON (deployment) | Must be set in env before any real deployment. Auth works on insecure default in dev. |
| PUBCAST_OWNER_PASSWORD not set | FIX SOON (deployment) | Owner account won't auto-create on first run of real machine without this. Add to startup env. |
| CORS wildcard + allow_credentials forced False | FIX SOON (deployment) | Set PUBCAST_ALLOWED_ORIGINS to specific origins (e.g. `http://localhost:8000`) before production. Don't touch in sandbox. |
| ANTHROPIC_API_KEY missing in 2i | FIX SOON (deployment) | /api/claude endpoint disabled. Needs real key. Not a bug. |
| DeepFace not available | EXPECTED | ML library not installed. Facial analysis in simulation mode. |
| MediaPipe not available | EXPECTED | ML library not installed. Landmark analysis disabled. |
| PortAudio/sounddevice unavailable | EXPECTED | No audio hardware in sandbox. Browser-side audio unaffected. |
| Ollama Studio OFFLINE | EXPECTED | No Ollama instance running. Studio bot inference unavailable. |

---

## Integration chain — post-fix verification

All checks passed:

1. **Health**: PubCast :8000 → 200, PubPartner :8001 → 200, 2i :8787 → 200
2. **2i → PubPartner commit**: `committed` in 29ms
3. **PubPartner independent verify**: content confirmed in PubPartner's own
   storage: *"The ground is stable. Claude Raines signs off."*
   Vector clock: `resident-747055ac: 3`
4. **PubCast → PubPartner chat bridge**: routes correctly to `slot: alex`,
   emotional context returned (`alex_state: guide`,
   `jeremy_whisper: Jeremy note: keep tone steady.`). LLM reply unavailable
   (Ollama not running) — correct, honest degradation.

---

## Unintegrated file identified post-run

**`pubcast_twin_engine_service.py`** — uploaded 2026-08-19, end of session.

This is NOT the C++ engine. It is the Python service wrapper that sits between
`main.py` and the VoxelBridge — properly mounting the twin engine with
`app.state.twin_engine`, exposing clean API routes (`/api/twin/status`,
`/api/twin/scene`, `/api/twin/camera/activate`, `/api/twin/camera/pose`,
`/api/twin/command`), and handling DISCONNECTED/DEGRADED/READY modes honestly
rather than the current raw "try to connect, log result, continue" approach in
`main.py` step [17].

**Not in the tree. Not mounted. Not a collision risk** — no file at
`modules/twin_engine_service.py` or similar exists. Safe path to add it.

**What main.py currently does at step [17]:**
```python
voxel_bridge = VoxelBridge(DATA_DIR)
bridge_connected = voxel_bridge.connect() if hasattr(voxel_bridge, "connect") else False
# logs result, moves on — no camera state, no routes, no graceful mode management
```

**What this file provides instead:**
- `TwinEngineService(bridge, renderer)` — wraps both
- `mount_twin_engine(app, bridge=..., renderer=...)` — one call to replace step [17]
- `install_twin_engine_routes(app)` — mounts all `/api/twin/*` endpoints
- Honest DISCONNECTED/DEGRADED/READY mode management throughout
- Canonical virtual camera state (6 default cameras pre-registered)
- C++ renderer connection via existing bridge TCP path when it's running

**To wire in (next session, not now):**
1. Copy file to `pubcast/modules/twin_engine_service.py`
2. In `main.py` step [17], replace raw VoxelBridge instantiation with:
   ```python
   from modules.twin_engine_service import mount_twin_engine, install_twin_engine_routes
   twin_engine = await mount_twin_engine(app, bridge=voxel_bridge)
   install_twin_engine_routes(app)
   ```
3. Restart, verify `/api/twin/status` returns a real mode (DISCONNECTED is
   correct and honest when the C++ engine isn't running)

When the C++ renderer is ready to reconnect, pass it as `renderer=` to
`mount_twin_engine` — that's the only change needed at that point.

---

## Deployment checklist (for when this moves to the real machine)

Before first run on Zoidberg (or any real host):

```bash
export PUBCAST_JWT_SECRET="<strong-random-secret>"
export PUBCAST_OWNER_PASSWORD="<owner-password>"
export PUBCAST_ALLOWED_ORIGINS="http://localhost:8000,http://localhost:3000"
export ANTHROPIC_API_KEY="<your-key>"          # enables 2i /api/claude
export PUBPARTNER_URL="http://localhost:8001"   # enables 2i → PubPartner sync
```

Process supervision: PubCast, PubPartner, and 2i have no watchdog yet. On the
real machine, wrap each in systemd or pm2 so they survive crashes and restarts
without manual intervention. This is the first shingle nominated in the
SESSION_HANDOFF — still unbuilt, still the right first next step.

---

## State at sign-off

- All three services: running, healthy, no unexpected errors in logs
- 5 bots loaded (was 4)
- Full integration chain: verified end-to-end
- One real fix made and confirmed
- All remaining warnings correctly classified as expected or deployment-time

Ground is stable.

— Claude Raines, 2026-08-19
