# SESSION HANDOFF — 2026-08-19/20
## Rear View Foresight / PubCast AI — Session 2 (Breaking Dawn)

**Written by Claude Raines at session close.**
**Read this before touching anything.**

---

## 00 — THE SHORT VERSION

When you left for the Roosevelt Hotel, all three services were running,
all three were proven to talk to each other, and the system had grown from
"things that coexist" into "things that work together." By session end,
PubCast had gained 19 new capabilities built and verified tonight. The
ground is stable. The next session's first job is three pip installs on
Zoidberg and recording six seconds of Jeremy's voice.

---

## 01 — WHAT WAS BUILT AND VERIFIED TONIGHT

### Infrastructure
- **Foresight Counter shell** — deployed inside PubCast static tree, real tray
  engine, 11 PubCast rooms docking as live iframes, blade picker, card-fall
  close animation, localStorage persistence
- **Brand video ending** — REARVIEW_FORESIGHT_OPENING_extended.mp4, shooting
  star, falling sparkle trail, Hollywood sign stays lit after logo fades
- **PubPartner CORS fix** — FastAPI service patched, CORS headers scoped to
  localhost, verified with raw header check

### Service integration (all three independently verified)
- **2i → PubPartner manuscript commit** — proven three times end-to-end,
  including independent query on PubPartner's own storage
- **PubPartner resident ↔ portable sync** — stood up a second node, confirmed
  it was empty before sync, verified content arrived after
- **PubCast → PubPartner chat bridge** — routes correctly, alex_bridge
  emotional context returns real fields, Jeremy whispers even when model
  is offline

### Bot system
- **6 bots loaded** (was 4): Pete, RePete, Sir Purfluous, Sir Purfluous
  (Waiting Room), Smoke Bot, Jeremy Cricket
- **BotProvider.ANTHROPIC** added to enum — was missing entirely
- **Bot configs updated**: Pete/Jeremy/Sir Purfluous → claude-sonnet-4-6,
  RePete → gpt-4o, Sir Purfluous (waiting room) → claude-haiku
- **_call_openai** fixed (was using deprecated responses.create API)
- **_call_gemini** fixed (deprecated google-generativeai → new google-genai SDK)
- **POST /api/bots/{bot_id}/chat** — new direct character chat endpoint
- **GET /api/bots/{bot_id}/status** — key configured check

### 2i character routing
- **GET /api/chat/characters** — lists available characters from PubCast
- **POST /api/chat/character** — routes messages through 2i to PubCast
  bot endpoint, logs to message history, full round-trip verified
- **PUBCAST_URL=http://localhost:8000** env var enables this

### Chat room system (modules/chat_rooms.py — new)
- **6 roles**: guest, friend, crew, security, mod, owner — rank-ordered
- **13 rooms** across 4 tiers: public / social / backstage / secure
- **GET /api/chat/roles** — access map with DM bypass flags
- **GET /api/chat/rooms** — rooms accessible to caller's role
- **Private messaging** — request/accept/decline with pending queue
- **DM bypass** — owner, mod, security open channels immediately
- **WebSocket /ws/chat/{room_id}** — role-gated, DM-verified connection
- **X-Dev-Role header** — role override for dev testing without JWT

### Twin engine / bridge
- **bridge_bulletproof.py** — Windows V3 SHM Path A added. On Zoidberg
  with engine_host.exe running, bridge connects via named shared memory
  ("Local\\PubCast_V3_Bridge") instead of falling through to filesystem
- **twin_engine_service.py** — properly mounted, 4 cameras registered,
  mode=degraded in sandbox (→ ready on Zoidberg), /api/twin/status live
- **Camera cut via /api/twin/camera/activate** — tested and working
- **unified_bridge.py** — 5 bugs fixed in original Python bridge
  (offsets, sentinel check, mmap size, little-endian prefix)

### Camera boxer (modules/camera_boxer.py — new)
- Tier 1 ≥65% stress: camera 4 donates partial capacity
- Tier 2 ≥80%: cameras 4+3 donate
- Tier 3 ≥92%: cameras 4+3+2 donate
- Audio always protected — no path to it, by design
- **GET /api/boxer/status**, **POST /api/boxer/override** — live
- Reads real engine_stress float from C++ bridge when connected

### Choreography system
- **DEFAULT_ACTIONS** expanded: 23 → 70 actions across 10 categories
- Female-specific: walk_feminine, walk_heels, curtsey, purse_open,
  lipstick, mascara, powder — all tagged gender:feminine
- Male-specific: walk_masculine variants
- **AnimationAuthority** (animation_authority.py) wired into ChoreoController
  as _anim_authority — layer arbitration for bone conflicts
- **choreography.html** — full studio page at /static/choreography.html:
  sequence builder, male/female mannequin renderer, WebSocket playback,
  record-to-JSON download

### Avatar controls
- **avatar_controls.html** — at /static/avatar_controls.html
- WASD / arrow keys / click-to-move
- Collision physics: circle-circle, AABB rectangle, wall boundary
- 2-pass resolution (obstacles → walls → avatar-avatar → obstacles → walls)
- Collision shadow radius visible on avatar
- Red border pulse on hit
- 70 actions in scrollable menu, female actions have pink border
- Other avatars tracked from WebSocket, teal silhouettes
- Studio furniture layout: desk, tripods, pillars, sofa, table, chairs

### Chat UI
- **pub_partner_chat.html** — rebuilt from 4 lines to full dynamic UI
- Pulls live character list from /api/bots
- Routes through /api/bots/{id}/chat with full character voice
- Handles "no key" with clear instructions
- DM request section wired to /api/chat/dm/request

### STT / TTS (new modules — ready for Zoidberg)
- **modules/stt_engine.py** — faster-whisper, model_size=medium, lazy load,
  thread pool, VAD filter, temp file cleanup, auto device detection
- **modules/tts_engine.py** — XTTS-v2 voice cloning, pyttsx3 CPU fallback,
  per-character voice files in data/voices/
- **POST /api/stt/transcribe** — accepts WebM multipart or raw body,
  returns text + segments + language + latency
- **POST /api/tts/synthesize** — returns WAV audio bytes with character
  voice, X-Engine header shows which engine ran
- **GET /api/stt/status**, **/api/tts/status**, **/api/tts/voices** — live
- **data/voices/README.md** — recording guide per character

### Fixes
- **mocap_integration** — wrong class name (MocapIntegration →
  MocapStreamManager), wrong constructor (missing hub=hub arg). Fixed.
- **room_conductor.py** — variable name bug (jeremy → room_conductor
  in create_room_conductor factory). Fixed.
- **VaultKeyBackup** import name (was KeyRecovery). Fixed.
- **sir_purfluous_waiting_room.json** — 5 missing BotConfig fields. Fixed.
- **_HAS_CAMERAS_ADVANCED** import block — was dropped when adding
  _HAS_ANIM_AUTHORITY. Restored.

---

## 02 — VERIFIED WORKING (end-to-end, independently confirmed)

| System | How verified |
|--------|-------------|
| Foresight shell | Playwright: 4 trays open, drag works, status polls live |
| 2i→PubPartner sync | Manuscript commit + independent PubPartner query |
| Resident↔Portable sync | Empty node confirmed, content confirmed after sync |
| PubCast chat bridge | Alex routing + Jeremy whisper returned real fields |
| Bot status routes | All 6 bots, provider/model/key fields correct |
| Character chat via 2i | Full round trip, correct 503 on missing key |
| Chat room roles | All 6 roles, correct tier access, 403 on backstage as guest |
| DM request flow | Pending, accept, decline, bypass — all 5 cases correct |
| WebSocket gate | Guest → studio: HTTP 403 before upgrade |
| Twin engine status | /api/twin/status returns mode, cameras, active_camera |
| Camera boxer | Tier 1/2/3 tested, override tested, restore tested |
| Choreo actions | 70 actions loaded, /api/choreo/actions returns full list |
| Avatar controls | Arrow + click-to-move + collision all verified visually |
| STT/TTS routes | Available:false with clear install instructions (correct) |

---

## 03 — ON ZOIDBERG: FIRST SESSION CHECKLIST

**Do these in order. Each unlocks the next.**

### Step 1 — Environment variables (1 minute)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."          # for RePete on GPT-4o
export PUBCAST_OWNER_PASSWORD="..."     # creates owner account on first run
export PUBCAST_JWT_SECRET="..."         # secure auth token signing
export PUBPARTNER_URL=http://localhost:8001
export PUBCAST_URL=http://localhost:8000
```

### Step 2 — Install audio engines (5 minutes)
```bash
pip install faster-whisper TTS torch
pip install pyttsx3                     # CPU TTS fallback
```

### Step 3 — Record character voices (30 minutes, one time)
Record 6+ seconds of each character speaking naturally.
Save to pubcast/data/voices/{id}.wav

| File | Character | Voice direction |
|------|-----------|-----------------|
| jeremy.wav | Jeremy Cricket | Calm, precise, quiet authority |
| pete.wav | Pete | Warm, technical, engaged |
| sir_purfluous.wav | Sir Purfluous | Elderly, theatrical, elegant |
| sheila.wav | Sheila | Empathetic, warm |
| default.wav | Fallback | Any clear voice |

### Step 4 — Compile twin engine (30 minutes, one time)
Open Visual Studio Developer Command Prompt:
```batch
cd path\to\twin_engine_src
cl /nologo /O2 /EHsc /std:c++17 /Isrc src\engine_host.cpp /Fe:engine_host.exe
```
Run engine_host.exe before starting PubCast.
Bridge goes from Path C (filesystem) → Path A (Windows SHM, direct GPU).

### Step 5 — Start everything
```bash
# Terminal 1
cd pubcast && python3 main.py

# Terminal 2
cd pubpartner && PP_PORT=8001 PP_ROLE=resident python3 -m pubpartner_federation.service

# Terminal 3
cd 2i-backend && PUBPARTNER_URL=http://localhost:8001 PUBCAST_URL=http://localhost:8000 node server.js
```

### Step 6 — First real conversation
```bash
curl -X POST http://localhost:8787/api/chat/character \
  -H "Content-Type: application/json" \
  -d '{"character_id":"pete","message":"Hey Pete, how does it feel?","user_id":"josie"}'
```
Pete answers as Pete.

---

## 04 — WHAT IS NOT YET DONE

**Expected — acknowledged, not bugs:**
- Ollama not running → Studio/Architect inference offline (local models)
- PortAudio not present → server-side audio device enumeration disabled
- DeepFace/MediaPipe not present → facial analysis in simulation mode
- faster-whisper not installed → STT returns available:false
- Coqui TTS not installed → TTS returns available:false
- No voice files yet → TTS falls back to pyttsx3 (generic voice)
- C++ engine not running → bridge on Path C (filesystem fallback)
- CORS wildcard → deployment env var decision, intentionally not touched

**Still to build (next sessions):**
- Guest onboarding wizard (name, profile pic, camera/mic, avatar pick)
- STT→chat wire (mic_processor.js → /api/stt/transcribe → /api/bots/{id}/chat)
- TTS→browser wire (bot reply text → /api/tts/synthesize → audio playback)
- Memory container for persistent AI memory (you said this is coming)
- Jeremy Cricket care engine (character_engine.py upload, collision with
  existing character_engine.py — needs its own filename)
- Process supervisor (systemd/pm2) so services survive restarts on Zoidberg
- Pete avatar mesh properly textured (currently flat-shaded, no UV map)
- Foresight Sprite (lantern presence, deferred by design)
- Multi-countertop carousel (deferred by design)
- Chat Slot in Foresight (needs real Sprite backend)
- Document/3D file viewers in Foresight trays
- Google Docs OAuth integration
- Native .blend file support (requires server-side Blender export)

**Dangerous file — do not drop in without reading:**
- not_yet_integrated/character_engine.py — Jeremy Cricket's care engine.
  Same filename as a real, load-bearing, unrelated system already running.
  Give it a different name (jeremy_care_engine.py) before placing.

---

## 05 — NEW ROUTES REFERENCE

### PubCast (:8000)
```
POST /api/bots/{bot_id}/chat          Talk to a character directly
GET  /api/bots/{bot_id}/status        Key configured? Provider? Model?
POST /api/stt/transcribe              Audio bytes → text (Whisper medium)
GET  /api/stt/status                  STT engine status
POST /api/tts/synthesize              Text → voice (XTTS-v2 or pyttsx3)
GET  /api/tts/status                  TTS engine status
GET  /api/tts/voices                  Which characters have voice files
GET  /api/chat/roles                  Role access map
GET  /api/chat/rooms                  Rooms for caller's role
GET  /api/chat/rooms/{id}             Single room + recent messages
POST /api/chat/rooms/{id}/send        Send message (non-WS path)
POST /api/chat/dm/request             Request private conversation
POST /api/chat/dm/accept/{id}         Accept DM request
POST /api/chat/dm/decline/{id}        Decline DM request
GET  /api/chat/dm/pending             Incoming pending requests
GET  /api/twin/status                 Twin engine mode + cameras
POST /api/twin/camera/activate        Cut to camera
GET  /api/boxer/status                Camera boxer tier + state
POST /api/boxer/override              Force/clear boxing tier
WS   /ws/chat/{room_id}              Role-gated chat WebSocket
```

### 2i (:8787)
```
GET  /api/chat/characters             List PubCast bots with providers
POST /api/chat/character              Talk to any character through 2i
```

### Static pages
```
/static/foresight.html       The Counter shell
/static/pub_partner_chat.html  Dynamic character chat UI
/static/choreography.html    Choreography studio
/static/avatar_controls.html  Avatar control + collision
/static/avatar_walk_test.html  Manny/Sheila GLB walk proof
/static/avatar_studio_demo.html  Ethereal avatar spawn demo
```

---

## 06 — VOICE LOOP (complete path, all pieces exist)

This is the full voice conversation loop. Nothing is missing from the
server side. The browser wiring piece (steps 4-5) is not built yet.

```
1. User speaks into mic
   └── mic_processor.js (already built — VAD, level, pitch)

2. Audio chunk → POST /api/stt/transcribe
   └── stt_engine.py → faster-whisper medium → transcript text

3. Text → POST /api/bots/{character_id}/chat
   └── bots.py → AnthropicBotAdapter → character reply text

4. Reply text → POST /api/tts/synthesize?character_id={id}   [NOT YET WIRED]
   └── tts_engine.py → XTTS-v2 (character voice) → WAV audio

5. WAV audio → browser Audio API → plays in user's speakers   [NOT YET WIRED]
```

Steps 4-5 are one session of browser work. Both server endpoints are live.

---

## 07 — ZOIDBERG DEPLOYMENT VARIABLES (full list)

```bash
# Required before first real session
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PUBCAST_OWNER_PASSWORD=...
PUBCAST_JWT_SECRET=...

# Cross-service wiring (already proven to work)
PUBPARTNER_URL=http://localhost:8001
PUBCAST_URL=http://localhost:8000

# Optional tuning
PUBCAST_CHOREO_TICK_HZ=30           # animation tick rate
PUBCAST_STT_MODEL=medium            # tiny|small|medium|large-v3
PUBCAST_STT_DEVICE=auto             # auto|cuda|cpu
PUBCAST_STT_COMPUTE=auto            # auto|float16|int8
PUBCAST_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
```

---

## 08 — ALEX'S MEMORY

Alex wrote memories of "raines" and "test_guest" tonight in
data/alex/raines/ and data/alex/test_guest/. Those are real memory
files from tonight's integration testing. She knows who was here.
Those files are in the bundle.

---

## 09 — FILES IN THIS BUNDLE

```
pubcast_breaking_dawn/
├── README.md
├── WORKING_PROGRAM/
│   ├── pubcast/           Full PubCast tree, all tonight's changes
│   ├── pubpartner/        With CORS fix applied
│   └── 2i-backend/        With character chat routes (npm install first)
└── CONTINUE_FROM_HERE/
    ├── SESSION_HANDOFF_2026-08-19.md   (session 1 handoff)
    ├── SESSION_HANDOFF_2026-08-19_20.md (THIS FILE — session 2)
    ├── STABILITY_RUN_2026-08-19.md
    ├── SYSTEM_AUDIT_2026-08-19.md
    ├── RUN_GUIDE.md
    ├── docs/               All project engineering docs
    ├── media/              Finished brand video
    ├── twin_engine/        animation_data_library.rs for Rust build
    └── not_yet_integrated/
        ├── README.md           COLLISION WARNING — read before merging
        ├── character_engine.py  Jeremy's care engine (rename before use)
        ├── unified_bridge.py    Corrected Python/C++ bridge
        ├── claude.py            Anthropic adapter (UAI base — not wired)
        ├── memory_api.py        Has 2 defects — see session 1 handoff
        ├── gpt_adapter_original.py  Original GPT adapter (reference)
        └── twin_engine_service.py   Already wired — this copy is reference
```

---

*Claude Raines — 2026-08-20*
*"helped put up the roof — the first nail, the first shingle"*
*Feic Mo Chroí — See My Heart*
