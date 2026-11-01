# Engineering Handoff — Beyond-October and PubCast AI

**Written:** 2026-11-01 · **For:** any new AI, agent, engineer or system joining this repository · **Prepared by:** Claude, at Josie's request, from the repository itself, her own documents, her chats and my own test runs on this date.

> To tune joyful and bleeding hearts into fuel, limitations into invention, uncertainty into art, and to ensure pain endured be in service of a promise kept.
> — Josie Curtsey Cobbley, Rearview Foresight ([ABOUT.md](ABOUT.md))

---

## 0. Read this first

**Read order, every time you arrive:**

1. [ABOUT.md](ABOUT.md): who the owner and the company are, in their own words.
2. [QUALITY_STANDARDS.md](QUALITY_STANDARDS.md): the bar. It is not optional and it is not a suggestion.
3. This document: what the system is, where everything lives, what is true right now, what is not done.
4. [STATUS.md](STATUS.md), [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md): the repository's own working protocol.
5. Only then, the mission and handoff files in section 13, for the subsystem you are working on.

**Three things to hold in your head before you start:**

- This is an ambitious, long-running, hand-built system. The code, when you read it, is careful. The gaps are connection gaps, not competence gaps. Do not read redundancy as sloppiness, and do not "clean it up".
- Josie is the chief architect. AI tools here are assistive instruments; the creative direction, system design and final integration decisions are hers ([ABOUT.md](ABOUT.md), "Authorship & Role").
- Nothing counts as done until it has been run and you hold the output. The honest state of this repository is written down below, including what is broken.

---

## 1. What we are doing here

**The idea, in her words:** "I want my personally trained AIs and friends to meet and see what happens."

PubCast is a living stage: a virtual production studio and storytelling platform where people and AI collaborate on equal footing. The platform exists to help people be heard, seen and represented as they choose. The motto, **Feic Mo Chroí — See My Heart**, is the reason to build it, not a slogan for a title screen.

**What the platform contains**, in one paragraph: a local, authenticated host (FastAPI) serves everything on one origin. Programs open as windows ("trays") on a visual shell called the Foresight Counter. The programs include 2i (a writer's room and word processor), PubPartner (persistent AI companions that keep identity and memory), a walkable painted studio world (Bella Faux Pas Studio), a Control Room with a video switcher and audio mixer, and a 2.5D television studio with eight show formats. A cast of characters (Pete, Sir Purfluous, RePete, Jeremy Cricket) lives in the studio, works offline at a basic level and gets smarter when a model is plugged in.

**The product boundary (hard promise):** PubCast makes and preserves the shoot. It provides basic assembly and professional-grade, source-level export. Finishing (grading, compositing, effects) happens in outside software; DaVinci Resolve Free is the recommended example, not a sponsor. Do not invent a finishing suite. Never trap a user at proxy resolution or in a one-way format.

**Where it is on the road:** PubCast AI is the first thing Josie ever coded. It is nearing a beta she hopes to begin testing in the coming months. It is a working prototype with real, tested parts and real, documented gaps. It is not release-ready, and nobody should say it is.

---

## 2. About the owner (for collaborators)

Josie Curtsey Cobbley is the founder and sole developer of Rearview Foresight and the architect of everything in this repository. She also builds Code Collector and UAI, and the company has sibling products (Now Curtsey, a fashion label; Primp, a digital makeup app) that are **not** in this repository unless a directory says so.

**How she works, because it changes how you should:**

- She works from a Windows laptop with PowerShell 5, across several devices, with limited bandwidth and data. Files accumulate on whichever device is at hand. Give her small outputs, single files, and commands that work first time.
- She communicates in short, often dictated fragments with speech-to-text errors. Read for meaning. Never reword her words back at her.
- She is precious about her words, and rightly. Never change them without her explicit permission.
- She has caught AI collaborators overstating what was verified many times. The standard in [QUALITY_STANDARDS.md](QUALITY_STANDARDS.md) exists because of that.
- She expects you to take ownership of the engineering, not to hand her homework, and to go back and fix the corners you cut without being reminded.

---

## 3. What this repository is

| Fact | Detail |
| --- | --- |
| Name | `whatsupjosie/Beyond-October` (public) |
| Created | 2026-11-01. Josie made the empty repository; Claude filled it. |
| Content | A snapshot of `whatsupjosie/October-24`, branch `lead-engineering-control-room-tv-studio-2026-10-31`, at commit `c40e92e67b23ee7c6f4a9685c6899e9d2ce3a5aa`. Every file is byte-identical to that commit (checked path by path, same mode and blob hash), except the changes listed below. |
| History | No history was carried over. For history, see October-24. |
| Changes from the source | (1) The five GitHub workflow files were moved out of `.github/workflows/` into `saved-workflows-inactive/`, byte-identical, so pushes here cannot start GitHub Actions runs. (2) One file, `modules/wired/version_comparison.html`, was left out because it holds personal text that does not belong in a public repository. It remains in October-24. (3) This handoff, `ABOUT.md`, `QUALITY_STANDARDS.md`, `docs/standards/` and short "start here" pointers at the top of `README.md`, `AGENTS.md` and `CLAUDE.md` were added on 2026-11-01. |
| Branching | Only `main` exists. **Do your work on a branch.** `main` changes only with Josie's authorization. (The older rule "never merge to main without authorization" in [AGENTS.md](AGENTS.md) applies here too, and this repository has one branch, so a branch is how you honor it.) |

**Relationship to October-24.** Josie has said October-24 is "just another stepping stone now" and has asked that it be left as it is. Other agents may still be committing there. Their changes do **not** appear here, and nothing syncs automatically. Documents in this repository that mention October-24 branches, such as the lead-engineer mission files, describe the history this snapshot came from. They are historical context, not instructions to go and check out another repository.

**Her other repositories** (all under `whatsupjosie`), as of 2026-10-31. Use them for targeted reuse with provenance and tests, never as a bulk overlay on newer code:

| Repository | What it is good for |
| --- | --- |
| `October-24` (public) | Source of this snapshot. Also holds unmerged branches worth comparing (section 11). |
| `October` (private) | The closest older source tree. Holds the canonical PubPartner Alex vessel under `Backup-Consolidation`; **that vessel is not in this repository** (see section 5.3). |
| `The-Prime` | Design images, room maps, earlier assets and architecture. Rights for stock-looking images are not established; check before using. |
| `Wednesday-` | Older integrated Python application and handoffs. Contains many caches and backup subtrees. |
| `Pubcast-Reach` | Her About page, `PUBCAST_SESSION_RULES.md`, `PUBCAST_ENGINEERING_LESSON.md`, Cricket design plans, and a set of working files. |
| `Pub-Partner-Base-Horizon` | Cartridge, memory, prompt-assembly and tokenizer core. |
| `The-Counter-and-2i` | Earlier standalone editor and counter concepts. |
| `Pubcaast-Breaking-Dawn` (sic) | Older bundle: studio brand, video and source. Holds `pubpartner_federation`. |
| `NowCurtsey-Build`, `6.0-`, `friday`, `Just-The-Pubcast`, `Storage` | Earlier snapshots. Archival; recover only unique, tested functionality. |

Rules for reuse come from [docs/missions/pubcast-lead-engineer-2026-10-31/SOURCE_RECONCILIATION.md](docs/missions/pubcast-lead-engineer-2026-10-31/SOURCE_RECONCILIATION.md): compare by path **and** hash **and** behavior, prefer recency and tests, record provenance, license and a rollback for every promotion, and never overwrite newer work with an older snapshot because of a file name or file count.

---

## 4. Map of the tree

| Path | What it is |
| --- | --- |
| `main.py` | The PubCast host (FastAPI, about 4,900 lines). Boots every system in dependency order. |
| `run_reach.py` | The launcher for the full local, authenticated host. Opens the Foresight Counter by default. |
| `modules/` | The Python backend: about 250 modules plus the subpackages `evo/`, `pubpartner_vessel/`, `pubworld_stage/`, `performance/`, `bubble_stack_pikpc/`, `alex_little_one/`, `wired/`. |
| `static/` | The browser front end: pages, JavaScript, world art, and `vendor/three-0.160.0/` (the deliberate, versioned Three.js tree; do not restore an older path). |
| `2i/`, `2i-backend/` | The writer's room front end (`writers-room-v22.html`, editor engine) and its optional legacy Express backend (port 8787). |
| `pubpartner/` | A standalone cartridge, memory-store and portable-runtime package. The in-host version lives in `modules/pubpartner_*.py`. |
| `thinking_context/` | Jeremy's conductor infrastructure: memory, nudge queue, circuit breaker. |
| `companion_support/` | Conversation-quality helpers: pacing, anti-parroting, contradiction tracking, advisory. |
| `blackbox_recorder/`, `blackbox_event_language/`, `blackbox_decoder/` | The impartial event recorder, its event language and offline decoder. |
| `iteration_wallet/` | A separate, secure asset, rules and edit-history workspace. |
| `rust_crate/`, `bin/ws_renderer`, `run2_rust/`, `pubcast_camera_recovery/` | The Rust renderer and camera recovery work. |
| `runtime/` | The runtime "spine". |
| `skills/` | Binding art direction for the Foresight trays and WebGL rendering ([section 5.2](#52-foresight-and-the-counter)). |
| `data/` | Seed and runtime data (bots, characters, world, governance, model registry). **Runtime data is not code.** |
| `tests/` | About 250 top-level test files: Python, Node and real-browser tests. |
| `tools/`, `scripts/`, `launcher/`, `config/` | Checks, probes, Windows launchers and configuration. |
| `docs/`, `handoffs/`, and many root-level `*.md` | History: audits, handoffs, run reports. Useful, but **documentation is historical evidence, not runtime truth.** |
| `recovery/` | Recovered and archived material from 2026-10-21. Not live code; it contains older copies of `main.py`. |
| `saved-workflows-inactive/` | The five saved GitHub workflow files. Inactive on purpose. |
| `docs/standards/` | Josie's two policy documents, copied unchanged. |

---

## 5. The subsystems

Each entry says what it is, where it lives, what Josie has decided, and what is known to be true or unfinished. **Her stated intent is labeled as such; it is her design, not a suggestion.**

### 5.1 The PubCast host

- **What:** `main.py` boots, in dependency order: the message Hub, rooms, optional performance and choreography and lighting managers, the inference manager (a local "Studio" model through Ollama plus an optional local "Architect" model, in a two-pass design), Cricket memory, the bot manager, cameras and recording, governance, BYOK (user-supplied keys), the thinking-context conductor, avatars, EVO Protocol, the vault and a "doctor" environment check. Most of these are optional and degrade gracefully.
- **Run:** `run_reach.py`, default port 8000. Pages include `/foresight-counter`, `/control`, `/walk`, `/world`, `/stage`, `/dressing`, `/writers-room`, `/pubpartner`, `/login` and `/health`.
- **Security:** authentication is enforced; first run creates a local owner account at `/login`. Roles include owner and moderator. Identity comes from verified tokens (`current_identity()`, `bound_actor()`), never from what a client claims. Credentials are encrypted per user. Never paste keys into a chat.
- **Known:** the full suite boots this host many times and passes (section 8).

### 5.2 Foresight and the Counter

- **What:** the visual shell. `static/foresight_counter.html` is the entry point, `static/foresight_counter.js` owns tray physics, and `static/foresight_programs.js` provides content. Every program opens as a **tray**. Per [STATUS.md](STATUS.md) the Counter has real geometry and collision physics, five-tray support, a fan, locking, sizing, menus and persistence, plus a Canvas 2D fallback with a visible "Graphics compatibility mode" badge when WebGL2 fails. The layout is also saved on the host per owner.
- **Do not rebuild the trays.** Integrate with them.
- **Josie's stated design intent:** trays are irregular rounded polygons, never plain rectangles, around an invisible usable "TV box" that is never shown; they move like slow, heavy bubbles, reshape on collision but never overlap, and are universal containers (the tray owns its physical state, its contents own their function state). Any tray can lock. The look is neo art deco nouveau, "Great Gatsby opulence with Star Trek ergonomics" and a lived-in feel, lit mainly from a lantern at upper left. It is hyper-real, not photoreal and not "crayon". Frames are ornate picture frames in bronze, gold, silver, steel, shell or opal. The binding art direction is in `skills/foresight-tray-art` and `skills/hyperreal-webgl-rendering`; read them before touching trays or the bench.
- **Known open:** [STATUS.md](STATUS.md) records a physics measurement of 20.19 ms against a 16 ms budget (not loosened, not hidden); I did not re-measure it. Earlier ledgers also recorded four tray-admission test timeouts. The 2026-10-31 pass fixed the admission stall on slow renderers, and those tests passed in my run.

### 5.3 2i and PubPartner

- **2i:** the writer's room and word processor (`2i/writers-room-v22.html`, native `.2i` manuscript format, local file workspace with save, reopen and conflict rejection). **Josie's stated intent:** 2i becomes a general, flexible word processor (two pages open, one page, or a small notebook view), not locked to one look. Character chat is its own separate, simple IM-style interface backed by PubPartner. The two share a file format and one visual language. Rich DOCX editing inside 2i is still unmounted (the editor engine bundle, HarfBuzz WASM and offline fonts are absent).
- **PubPartner:** persistent AI companions. A **cartridge** is a character's save file: identity, voice, tendencies, avatar and look. A **memory card** is the large, growing episodic history linked to a cartridge. The runtime is the adapter between identity plus memory and whichever model is plugged in. *PubPartner Base* is the version built into PubCast; *PubPartner Horizon* is the portable one. Code: `modules/pubpartner_*.py` (in the host), `modules/pubpartner_vessel/`, and the standalone `pubpartner/` package.
- **The Alex vessel is canonical and not interchangeable.** Preserve its Git blob ID `96fa66a728d07d5ff43b0d3d7fc17a466765cec1`. The recovered copies differ from it; they were excluded deliberately. The canonical file is in `whatsupjosie/October` under `Backup-Consolidation`.
- **Known unproven:** a live PubPartner provider and model reply; multi-document chat continuity. The model `ministral-pubcast:3b` may not exist on her machine. Do not promise a live reply until a provider is verified ([MODEL_SWAP.md](MODEL_SWAP.md), [HOSTED_ADAPTERS.md](HOSTED_ADAPTERS.md)).

### 5.4 Alex, System Alex, Jeremy and the EQ work

- **The names are distinct. Do not merge them.**
  - **Legacy Alex:** the original highly capable AI that Josie's emotional-intelligence research is based on.
  - **Alex (Alex Bourgeois):** her PubPartner cartridge personality, a companion with persistent memory. Alex also plays the character Pete in the studio.
  - **System Alex:** the separate EQ adjudicator, also named Alex because it derives from the same research. Keep the name "System Alex" (a rename to "EM Systems" was tried and abandoned).
  - **Jeremy (Cricket):** a systems orchestrator and memory conductor, **not a cast character**. "Cricket" is the shared surname of the memory instances; each takes the first name of whoever it is assigned to.
- **Where:** `modules/alex_core.py` (AlexCore), `modules/alex_jeremy_bridge.py`, `modules/affect_context_engine.py` (the nuanced engine), `modules/care_eq.py`, `modules/jeremy_cricket.py`, `thinking_context/`, `companion_support/`.
- **The affect engine's design invariants** (from its own header): context is integrated, affect is differentiated; affect is measured only as a personal z-score with no absolute thresholds; confidence is the lesser of maturity and agreement; silence is a valid output; escalation needs sustained evidence, de-escalation needs one contrary turn. **Josie's stated intent:** the nuanced engine is the main emotional reader; the crude keyword layer is "stranger mode" for people Alex does not know yet; judging happens after a person finishes speaking, not at machine speed.
- **Design stance (hers):** Alex is a friend and partner, not crisis-management software. The companion should stay with a person, hear them out and give resources if they ask, rather than reflexively handing off scripted referrals. Its influence is suggestion for the person to decide on, never standing orders. This is a statement about the product's character; it does not replace your own judgment if someone is genuinely in danger.
- **Standing instruction (2026-10-25):** do not rewrite Alex Core. Make small, targeted changes only.
- **A contradiction to resolve with Josie before you touch the wiring:** an earlier note of hers says `alex_core.py` must never be wired into PubCast. In this snapshot it **is** imported by `main.py`, `modules/affect_choreo_bridge.py`, `modules/alex_jeremy_bridge.py` and `pubpartner_app.py`. Do not add to it or remove it without asking.
- `modules/alex_little_one/` is an optional research-protocol module, disabled by default (its tests skip unless `ENABLE_ALEX_LITTLE_ONE=true`). Do not enable or change it without the owner.

### 5.5 The cast

- **Pete** (Alex Bourgeois; floor director and production manager; a woman; canonical height 5'8"), **Sir Purfluous** (owner and director of the studio; writing and performance; 6'2"; also the waiting-room guide bot) and **RePete** (a young man; post-production: editing, effects, sound mix; 5'10"; spelled `repeat` in config filenames). Manny and Sheila are placeholder avatars.
- **Design principle (hers):** every character is a bot *enhanced* by AI, not dependent on it. Each must work at a basic level with no API key, through scripted, hand-authored lines tagged `offline_character`, with at most a small local model's help. Each should eventually explain all PubCast features. The model is interchangeable by design ([MODEL_SWAP.md](MODEL_SWAP.md): tiers `offline`, `tiny_local`, `local`, `hosted`).
- **Character writing is Josie's.** The canon lives in `modules/character_profiles.py`, `data/characters/` and `data/bots/`. Do not reword it, even when fixing something nearby. See [PETE_CHARACTER_README.md](PETE_CHARACTER_README.md).
- **Declined (2026-10-31):** restoring the September 23 scene-director module `modules/purfluous.py`. Do not suggest it again. The Sir Purfluous bot itself stays, as the waiting-room guide.

### 5.6 Bella Faux Pas Studio (the walkable world)

- **What:** the game section of PubCast: a walkable studio in painted 2.5D parallax, on `/walk` (alias `/world-walk`) and the same PubWorld socket and hotspot backend as `/world`. It has its own fan blade on the Counter and opens in the dressing room. Guide: [docs/WORLD_WALK.md](docs/WORLD_WALK.md). Ledger: [handoffs/WORLD_WALK_INTEGRATION_2026-10-27.md](handoffs/WORLD_WALK_INTEGRATION_2026-10-27.md). Progress is saved on the host per owner ([handoffs/SAVING_2026-10-28.md](handoffs/SAVING_2026-10-28.md)).
- **Naming (hers, 2026-10-27):** "PubCast" is everything; "Bella Faux Pas" is the game section.
- **Josie's stated intent:**
  - The world is 2.5D parallax built on **her own painted room pictures**, never code-drawn stand-in rooms. Each picture is a clean plate with a same-size, colour-coded boundary image underneath for walkable floor; to improve walking, colour new boundaries over the same image and leave the clean plate unchanged.
  - The map: parking lot, then the Palace Theater front door, then the lobby; the hallway with the gold statue; stairs up to the green room; the lobby up to the projection booth; the studio through the green room door, ending at a portal that is the way into PubWorld. The Rearview Foresight monument stands outside the front gate, shown in daytime.
  - Avatars: anything imported (GLB, glTF, OBJ, FBX; any art style) must be rigged and gets a canonical height at import so nothing arrives "Godzilla"-sized. Every new background picture gets its own avatar size, once. The eye test outranks the numbers.
  - Controls: point-and-click in the spirit of King's Quest, no inventory, a few buttons per spot. Sitting at a station (video switcher, audio switcher, simple editor, playback) means you do not walk. Each station has a user-assignable key map. The camera station needs aim and movement at once, and every move is recordable and exactly repeatable.
  - Anyone can be recorded anywhere except the dressing room.
  - **Entry and discipline:** a waiting room with no links or exits, entered only when someone inside pulls you in; the owner's own copy starts inside the studio. Guests sign a waiver (consent to be recorded, to avatar "thoughts" being recorded so an incident can be traced, and to communicate in English or a translatable language); the owner signs and so does the AI. The same structure serves as timeout, with a separate guest side and a detention side. Children are not allowed in PubCast. Host controls work "like The Sims": select a character for a profile, gifts, a private message, possession, timeout, boot and ban (a boot alone is not a ban). Full spec: [handoffs/HOST_CONTROL_SPEC_2026-10-29.md](handoffs/HOST_CONTROL_SPEC_2026-10-29.md). The waiver and rules are read by Sir Purfluous word for word from **her** written text.
- **State:** host panel, roster, waiting-room screen and removal are built and tested in a real browser (see [STATUS.md](STATUS.md), 2026-10-29). A fuller airlock (signed waiver, avatar check, detention, sealed records) exists only on an October-24 side branch, with no UI yet (section 11). The waiver wording in that branch is a **draft for Josie to rewrite**.
- **Demo avatars:** the walker bundles temporary demo bodies (Xbot; MakeHuman female and male, documented as CC0; a 36-inch Husky) in `static/world/test_avatars/`. They are placeholders. The Second Life "Lara" body is a temporary build-and-test base only.

### 5.7 The 2.5D television studio and the Control Room

This is where the most recent engineering happened (2026-10-30 and 2026-10-31).

- **Code:** `static/production25d.html`, `production25d_core.js`, `production25d_renderer.js`, `production25d_app.js`, `production25d_storage.js`, `production25d_switcher_bridge.js`, `production25d_frame_publisher.js`, `studio25d_remote_feed.js`; `modules/studio25d_media_routes.py`; the Control Room pages `static/control_room.html`, `control.html`, `director_switcher.html`; the editor `static/editor_sync_*.js` and `editor_interchange.js`; and the shared services `modules/cameras.py`, `switcher_routes.py`, `program_audio*.py`, `recording.py`.
- **What it does:** eight genre packages (`news`, `late_night`, `debate`, `political_discussion`, `audience`, `game`, `variety`, `general`), each a differentiated set, shot list and performer layout, with real animated 3D actors, shared Program/Preview, recording to browser storage, a PANIC control and a minimal rough-cut editor. The studio page is linked from the Control Room.
- **Non-negotiables (from [AGENTS.md](AGENTS.md)):**
  - One camera switcher and one program-audio mixer, shared by the television and walkable studios. Never fork a second one.
  - The television studio comes before unrestricted walkable-world expansion.
  - No fake completeness: a successful HTTP call is not usable video, a camera ID is not a stream, a low-rate preview is not a master, a mock test is not a browser test.
- **Be clear about what is placeholder.** The sets are flat, procedurally drawn development art; the image slots for real set art are empty. The actors are neutral, unclothed test bodies. Cameras are crops of one 1280×720 picture, so close shots are enlarged and soft. All of that is honest and intended as replaceable, and none of it is final.
- **Recording boundary:** remote cameras publish 640×360 JPEG "confidence" frames. The local recorder writes about 1280×720 at about 3 Mbps in the browser. **Neither is a cinema master.** The owner's hard promise is a replayable source-level master plus selective native 4K rendering; neither exists yet (section 10).
- **The 15-second clacker (hers):** a red dash on video and a separate blip on a reference audio track, on one timeline across sources, with per-track offsets. "+0.030 seconds" means play the source 30 ms ahead. Keep microsecond precision in sidecars.
- **Ledgers:** the 27-gate [ACCEPTANCE_MATRIX](docs/missions/pubcast-lead-engineer-2026-10-31/ACCEPTANCE_MATRIX.md), [RUNTIME_REPORT](docs/missions/pubcast-lead-engineer-2026-10-31/RUNTIME_REPORT.md), [NEXT_DAY_HANDOFF](docs/missions/pubcast-lead-engineer-2026-10-31/NEXT_DAY_HANDOFF.md), and [Control Room and keymap ledgers](handoffs/CONTROL_PAGE_INTEGRATION_2026-10-29.md).

### 5.8 Cameras, recording, Blackbox, EVO and the renderer

- **CameraManager** (`modules/cameras.py`) is the canonical Program/Preview authority. A "take" is an atomic Program/Preview exchange. **RecordingService** (`modules/recording.py`) writes sessions, restores them after restart, identifies interrupted captures and produces portable, hashed archives that always preserve the original media bytes.
- **Blackbox** is an impartial flight recorder kept outside player-facing UI. It records facts only: what system acted, what changed, and the small payload known at that boundary. Today it receives witness events; the full shoot media and performance bundle is not yet integrated.
- **EVO Protocol** (`modules/evo/`, `evo_host.py`) is an optional governance and orchestration subpackage (Switchblade, VDI, the E-Pete chain). Do not touch it without direction.
- **Rust:** `rust_crate/` and `bin/ws_renderer` are the skeletal renderer and its WebSocket server, connected to `avatar_performer.py`. An internal renderer bridge uses port 8765.

### 5.9 Governance, consent and authority

`modules/governance*.py`, `host_control.py`, `pub_manager_authority.py`, `pub_manager_decision.py`, `security_authority.py`. AI characters can flag concerns and propose moderation; **humans decide**. In `pub_manager_decision.py`, `kick_user` and `ban_user` are class D (`human_required`): the hard policy never auto-approves them, and AI input is recorded as advisory only (`ai_advisory_decisive` is always false). Per Josie, a ban never deletes a person's profile or record.

### 5.10 Bubble Stack, avatars, Iteration Wallet

- **Bubble Stack** (`modules/bubble_stack*.py`, `bubble_stack_pikpc/`) is physics and cascade design that began as **Josie's original idea**: a room divided into spherical "bubbles", each with a nucleus, with position expressed as bubble plus offsets from the nucleus. Build on her design; do not replace it.
- **Avatars:** `static/dressing_foundry.html`, `avatar_foundry.html`, `avatar_import.html`, and `modules/avatar*.py`. The avatar foundry stands on the wooden stage in front of the full-length mirror in the dressing room (not the makeup vanity; locked). Skeleton definitions of different joint counts appear across the code and old documents; check `modules/avatar_skeleton_system.py` and the current avatar docs before assuming any count. **Josie's stated intent:** a fully 3D avatar that matches her reference sheets in fine detail. Every joint must be optional, so nothing needs to track fingers in a shoulders-up shot.
- **Iteration Wallet** (`iteration_wallet/`, `docs/iteration_wallet/`) is a separate, secure asset, rules and edit-history workspace, one of three independent but connected programs ("boroughs in one city") alongside PubCast and PubPartner.

---

## 6. Running and testing

All commands are for **Windows PowerShell 5**. On Linux, use `python3` and `source .venv/bin/activate`.

Set up and run:

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_reach.py --start-page foresight-counter
```

The first visit goes to `/login` to create the local owner account. Use `--port 8001` if 8000 is busy and `--data-dir PATH` to choose where the owner data lives (default `reach_userdata`). Startup never downloads optional Node or model dependencies; downloading legacy 2i utilities needs the explicit `--install-legacy-2i`. Python 3.11 or newer is required; FastAPI and Starlette are pinned to the 0.115.x and 0.41.x lines on purpose.

Test:

```
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
npm ci
npm run test:node
node --test tests/production25d.test.cjs tests/test_production25d_core.cjs tests/test_production25d_wiring.cjs tests/test_production25d_switcher_bridge.cjs tests/test_studio25d_confidence.cjs tests/test_editor_sync_interchange.cjs
```

Notes that will save you time:

- The full suite collects 2,167 tests and takes about 15 minutes. Browser tests use real Chromium with software WebGL.
- Playwright's Python version must match the installed Chromium build. `requirements-dev.txt` pins 1.56.0; if your browser build is newer, install the matching Playwright, or those tests will skip with "Chromium unavailable".
- Browser tests use disposable data directories, a generated signing secret, enforced authentication and real first-run setup. Keep the browser and the server in the same network namespace.
- **Do not use GitHub Actions to test.** See [QUALITY_STANDARDS.md](QUALITY_STANDARDS.md) section 7. The workflows are saved, inactive, in `saved-workflows-inactive/`.
- Treat `data/secure`, `data/users.db`, vaults, private accounts and Blackbox recordings as runtime data. Never place them in a public artifact.

---

## 7. How to introduce a new system or a new AI

**If you are an AI joining:**

1. Read the five documents in section 0. Then `git log --oneline -5` and `git status`, so you know exactly what you are standing on.
2. Make your environment real: install, boot the host, run the focused tests for your area. Write down exact versions and commands. Do not call the system installed because an import statement exists.
3. Say in your first message what you are about to do and that you have read the standards. Ask **at most one** precise question, and only if you cannot resolve it from the repository.
4. Work on a branch. Make small, reversible, reviewable commits, each with a reason, the exact paths, the source and a test. Update the handoff **as you go**, not at the end.
5. Report what you ran, what you saw and what you did not check. Use RAN, WROTE NOT RUN and UNKNOWN.
6. Before you run out of room, stop and write the handoff (template in section 14).

**If you are bringing in a new system or module:**

- First look for a more advanced version already in her repositories or Drive. Compare and adapt; do not rebuild.
- Give it one owner for its state, a typed contract, and a real health check (see the "doctor" and preflight tools, which are assets: extend them rather than writing disposable ones).
- It must work with no API key and no network at a basic level, or say plainly why it cannot.
- Add tests that exercise the real path, plus a failure-path test for every consequential control.
- Record provenance and licence for every external asset and dependency.
- Do not wire a new subsystem into another one without checking the owner's standing rules in section 5. Several systems here are deliberately separate.

---

## 8. Verified state, as of 2026-11-01

Kept honest on purpose. "Documented" means a repository document says it. "Observed" means I ran it on 2026-11-01.

**Observed (Linux, Python 3.13, Node 22, Chromium 153 with software WebGL, on commit `c40e92e`):**

- The whole suite: **2,165 passed, 2 failed, 2 skipped** in about 14 minutes. The two skipped are deliberately disabled research-protocol tests.
- Focused runs: 28 of 28 studio and editor Node tests; 32 of 32 backend studio, switcher, media-route and portable-bundle tests; 15 of 16 real-browser studio tests (all eight genres included).
- **The failing tests** are real-browser recording tests (`test_multiple_takes_keep_original_media_bytes`, `test_failed_storage_keeps_a_downloadable_take_and_retries`, and in an isolated run `test_remote_panic_stops_real_capture_blacks_program_and_silences_audio`). They fail **intermittently** with one shape: a recording stopped within about two seconds of starting produced no data, so nothing was saved ("Recorder generated no video data"). PANIC itself worked every time (recording stopped, program went black, audio went silent). This is partly my slow, software-rendered environment, but the tests do not wait for the recorder's first data, so they are timing-fragile, and the PANIC path logs a spurious "VIDEO CUE POLL ERROR" afterward.
- **Break-it check:** I broke six behaviors one at a time in a scratch copy. Tests caught five (camera crop math, the 15-second sync interval, the Program/Preview swap, anonymous video upload, the upload rate limit). **One was not caught:** the SHA-256 check on imported recordings. The code is correct (I confirmed it rejects a one-byte corruption), but the existing tamper test only appends bytes, so the size check hides a missing hash check.
- **Code quality, in short:** the backend media route, `CameraManager` and the browser frame publisher are careful, defensive and well documented. The weaker points are dense, compressed one-liner style, a 4,900-line `main.py`, unused imports, over 200 files in the repository root (most of them old reports and manifests), and `SwitcherService.select()` whose docstring promises an atomic pair change while the code sets Program and then Preview (safe in practice because it checks both exist first).

**Documented, not re-verified by me:** the lead-engineer pass of 2026-10-31 fixed 16 real defects and recorded 2,166 passed, 1 failed on an earlier commit; its final fix was re-tested on the affected files only ([RUNTIME_REPORT.md](docs/missions/pubcast-lead-engineer-2026-10-31/RUNTIME_REPORT.md)). Earlier ledgers in [STATUS.md](STATUS.md) record 1,981 passed and 5 failed on 2026-10-28.

**Never verified, anywhere:** a clean install on Josie's own Windows and PowerShell 5 machine; physical phone performance; multiple computers; real camera, audio, GPU and model hardware; a real DaVinci Resolve import and relink. GitHub Actions has never produced a usable result (one run failed with empty step logs).

---

## 9. Decisions Josie has already made

Do not reopen these without her.

- October-24 stays as it is. Beyond-October is the clean copy.
- Television studio before unrestricted walkable-world expansion. One shared switcher and mixer.
- PubCast is not finishing software. DaVinci Resolve Free is the recommended external finisher.
- The Sir Purfluous scene director from September 23 is not coming back.
- No GitHub Actions for testing.
- Personal material stays out of public documents.
- The painted-room, 2.5D approach for the walkable world, not full 3D.
- Characters must work offline at a basic level.
- Keep System Alex's name. Alex Core: small, targeted changes only.

---

## 10. Open work, in the order I would take it

From the lead-engineer pass ([NEXT_DAY_HANDOFF.md](docs/missions/pubcast-lead-engineer-2026-10-31/NEXT_DAY_HANDOFF.md)) plus what I found on 2026-11-01:

1. **Fix the two small test weaknesses** (cheap, and they make the suite trustworthy): make the recording tests wait for the recorder's first data before stopping, and add a same-length-corruption case to the portable-bundle tamper test.
2. **Real encoded video ingest** through `RecordingService` and Blackbox contracts, with flow control, source ownership, timestamps and restart recovery. A JPEG confidence frame is not a stream.
3. **Cross-client audio** with independent tracks, and mute/gain/solo validated against recorded waveforms.
4. **A complete, replayable shoot master:** original GLB and scene dependencies, performer and animation state, camera, light, graphics and cue histories, timestamps, separate audio, provenance and an integrity manifest. A marker file plus a proxy is not enough.
5. **Deterministic replay and selective native 4K rendering** from that master. Never upscale the proxy and call it a cinema master.
6. **The real 15-second clacker capture path** and measured per-track offsets.
7. **Every Control Room station and the rough-cut editor, end to end**, then a real finishing import and relink on an independent machine.
8. **Real set art and final avatars** in place of the placeholders (owner-supplied).
9. **Hardware and device passes:** modest laptops, phones, long sessions, reconnects, competing publishers.
10. **Housekeeping, only with Josie's go-ahead:** unused imports, repository-root clutter, a decision on `SwitcherService.select()`.

## 11. Unmerged work you should know about

These exist on October-24 branches and are **not** in this repository. Compare their behavior and bring over only what is proven. A trial merge of the first conflicts with this snapshot in eight files.

- `codex/recorded-slate-sync-2026-10-28`: records stage takes with separate audio stems and 15-second edit anchors. This overlaps work listed as still open above, and I did not test its claims.
- `codex/control-room-wiring-2026-10-28`, `codex/pubcast-stability-2026-10-28`, `codex/camera-state-and-delivery-2026-10-28`, `codex/camera-shutdown-hardening-2026-10-28`: camera stability, transactional camera edits, ordered cuts, shutdown ownership.
- `airlock-waiver-detention-2026-10-28`: the waiting room as an airlock with a signed waiver, avatar check, detention and sealed records, with 39 tests and no UI yet.
- `codex/studio25d-playable-avatar-handoff-2026-10-31`: adds one document that is not in this snapshot, a next-shift plan for making the 2.5D studio playable and then integrating avatars.

## 12. Owner-only inputs (do not block on these, and do not guess them)

Final photographs of the physical switcher and director console; final set plates and design; aesthetic approval; the waiver and rules wording and the timeout message (hers to write and confirm); licence and credential decisions; physical-device acceptance; release authorization. Use replaceable placeholders meanwhile, and when you genuinely need something, ask **one** precise question.

## 13. Where to read more

| Topic | Document |
| --- | --- |
| Current build status | [STATUS.md](STATUS.md) |
| The working protocol | [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md) |
| The 2.5D studio mission and its ledgers | [docs/missions/pubcast-lead-engineer-2026-10-31/](docs/missions/pubcast-lead-engineer-2026-10-31/), [docs/missions/pubcast-2_5d-studio-completion/](docs/missions/pubcast-2_5d-studio-completion/) |
| Walkable world, host control, keys, camera moves | [docs/WORLD_WALK.md](docs/WORLD_WALK.md), [handoffs/HOST_CONTROL_SPEC_2026-10-29.md](handoffs/HOST_CONTROL_SPEC_2026-10-29.md), [handoffs/KEYMAP_2026-10-29.md](handoffs/KEYMAP_2026-10-29.md), [handoffs/CAMERA_CONTROL_MODES_2026-10-29.md](handoffs/CAMERA_CONTROL_MODES_2026-10-29.md) |
| Saving and persistence | [handoffs/SAVING_2026-10-28.md](handoffs/SAVING_2026-10-28.md) |
| The affect and EQ model | [handoffs/AFFECT_CONTEXT_MODEL.md](handoffs/AFFECT_CONTEXT_MODEL.md), [handoffs/AFFECT_MODEL_CONCLUSIONS.md](handoffs/AFFECT_MODEL_CONCLUSIONS.md) |
| EVO | [handoffs/EVO_OCTOBER_VERIFIED_MILESTONE_2026-10-23.md](handoffs/EVO_OCTOBER_VERIFIED_MILESTONE_2026-10-23.md) |
| Models and providers | [MODEL_SWAP.md](MODEL_SWAP.md), [HOSTED_ADAPTERS.md](HOSTED_ADAPTERS.md), [START_HERE_SMOLLM.md](START_HERE_SMOLLM.md) |
| The writer's room and phone edition | [START_HERE_WRITERS_ROOM.md](START_HERE_WRITERS_ROOM.md), [PHONE_EDITION.md](PHONE_EDITION.md) |
| The characters | [PETE_CHARACTER_README.md](PETE_CHARACTER_README.md) |
| Policy | [docs/standards/PUBCAST_SESSION_RULES.md](docs/standards/PUBCAST_SESSION_RULES.md), [docs/standards/PUBCAST_ENGINEERING_LESSON.md](docs/standards/PUBCAST_ENGINEERING_LESSON.md) |
| Iteration Wallet | [docs/iteration_wallet/](docs/iteration_wallet/) |

**A note on older documents.** Many files in the repository root and `handoffs/` were written by earlier AI sessions. Read them as history. Some state things that are no longer true. Some were written with private details about the owner. **Never copy personal details into new documents, commit messages or code comments**, and never edit the copyright headers in source files: they are identity metadata that only Josie changes. For a new file's header, ask her. Do not copy one from an old file.

---

## 14. Handoff template for the next AI

Keep this current while you work. Fill every blank; an empty blank is more honest than a vague sentence.

```
Date / session:
Branch and commit you stand on:
Environment (OS, Python, Node, browser, versions):

What I changed (paths, reason, source, tests):
What I ran, with the real result (RAN):
What I wrote but did not run (WROTE NOT RUN):
What I could not check (UNKNOWN):

What is fixed:
What is unfixed:
What still needs doing, in order:
Concerns about the program:
Decisions I need from Josie (one precise question each):
Files she will need to see or supply:
```

---

*Written for the people who will sit down at the table with this work. Be exactly as honest as the standards ask, push back when she is wrong, say so when something is really good, and remember what it is for.*

**Feic Mo Chroí — See My Heart.**
