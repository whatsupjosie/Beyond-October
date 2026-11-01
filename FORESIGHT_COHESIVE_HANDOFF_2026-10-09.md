# Foresight / PubCast Reach — One-Program Integration Handoff

Date: October 9, 2026 (user-local). Starting authority: `PubCast_Reach_UNIFIED_2026-10-09.zip`.

## What now starts and where

The authoritative host is **root `main.py`**, launched through **`run_reach.py`**.
Windows: extract the ZIP, double-click `OPEN_REACH_WINDOWS.bat` (which uses `start_reach.py` → `run_reach.py`).
macOS/Linux with dependencies: `python3 run_reach.py`. The existing `start_pubcast.sh` now delegates to the same launcher.
The host opens `http://127.0.0.1:8000/foresight` by default, with owner sign-in on first run.

The Foresight Counter is the main interface, not an alternate application. Its fan has direct launch blades for PubPartner, Character Chat, 2i, and CARE even before those trays have been opened. All entries below are movable/persistent portal windows:

| Foresight menu | Single real implementation |
|---|---|
| World Chat, additional chats | Existing World/General Chat + conversation ownership |
| Character Chat | Same-origin `/api/foresight/bridge` → **existing** BotManager and Hub. The provider call is now shared with `/api/bots/{id}/chat` through `modules/character_service.py`. |
| PubPartner · Alex & Cartridges | `/pubpartner` native PubPartner UI; Alex selected by default; existing PubPartnerSpine, vessel, Alex memory, affect, Jeremy Bridge, provider/credential configuration. |
| 2i Writer's Room | `/writers-room` canonical v22; same-origin PubPartner manuscript endpoints and shared Reach authentication. |
| CARE / EQ & Little Mode | New control surface `static/foresight_care.html` drives the **existing** `/api/alex/care/*` and shared CareCoordinator. No second care engine. |
| 2i Bridge Status | Same-origin service status and honest optional legacy-utility availability |
| Stage, World, studio, directors, teleprompter, gallery, etc. | The original direct portal targets and existing PubCast services; these were retained rather than copied or redesigned. |

## The removed disconnect

Previously Foresight and its Character Chat accessed `http://localhost:8787` in browser JavaScript. This failed when opened from another device and required a separately launched server. **No browser now needs that port.** Character selection/replies use the canonical Python BotManager in Reach, not an independent bot config registry. The `get_recent_history` and `_call_provider` logic now lives in one `modules/character_service.py`, used by both public bot routes and the Foresight bridge.

The old Node 2i server remains as an **optional utility sidecar** for functions not owned by the Python host (its existing thesaurus, Anthropic proxy, legacy manuscript commit, and separate message utilities). `run_reach.py` can install its npm dependencies on first start and automatically supervises its lifecycle. It listens on a random loopback-only port and is exposed only via a **path-allowlisted, identity-protected** Reach proxy. If the runtime/dependencies are absent, Foresight's character chat, manuscript UI, and PubPartner still run; the optional legacy utilities report unavailable (503). This is not a claim that those utilities were executed in this environment.

## Security and identity

- Reach's owner JWT and same-origin auth client are shared by embedded portals. PubPartner and Character Chat populate the actual signed-in username, not a hard-coded display name.
- Character Chat validates `character_id`, message length, room name, and actor binding against the JWT; it cannot impersonate a different account through the body.
- Optional legacy utility forwarding is restricted to explicitly allowed HTTP methods/paths, loopback destinations, bounded request bodies and authenticated actors; message-clear requires owner/admin, with the original Node admin key gate also unchanged.
- CARE controls require the real authenticated owner to activate. It does **not** automatically intercept all PubCast rooms or ChatGPT. Its observation and monitoring data remain in its existing privacy scope.

## Verification run on the consolidated source

- **80 focused checks passed**, including real gateway API tests, Foresight front-door, manuscript, CARE, Alex memory and backup, emotional systems, and script parsing.
- Additional broader smoke cases executed without an assertion failure; a long test command timed out during teardown, so that run is **not** represented as a complete pass.
- Python compilation and JavaScript syntax checks passed.
- **Actual running host** launched via `run_reach.py --no-browser --no-legacy-2i`, then HTTP 200 was observed for Foresight, PubPartner, Writer's Room, CARE UI and bridge health. Anonymous protected endpoints returned 401.
- **Actual first-owner setup** accepted a securely generated password; authenticated requests returned four bundled bot configs, PubPartner spine status 200, CARE ordinary status, CARE activation to baby and deactivation to ordinary. Test accounts/data were created outside this release folder and are **not packaged**.

## Known limits / not commissioned

- External model inference (actual provider API keys and local Ollama model) and live voice/avatar/GPU/Rust performance have **not** been verified in this session. No simulated reply should be mistaken for a real AI conversation.
- Original Node `2i-backend` dependencies were not available in this environment, so optional Node utility startup and live proxy round-trips are **not verified**. One-command startup attempts first-run `npm ci` when Node/npm are available; it degrades explicitly if unavailable.
- Google Drive API backup with real OAuth, remote restore and background synchronization are not verified; local-memory routes retain earlier tested behavior.
- CARE observation, activate/deactivate and masking are integrated into the Alex API/Bridge. This does not assert comprehensive Little One roleplay integration or every-room interception.
- Legacy incomplete studio capabilities remain as documented in prior handoffs. A working portal pointing to a page does not certify every control on that page or a commissioned production environment.

**Do not re-introduce** hard-coded browser port 8787, duplicate `main.py`, separate browser character managers, or copies of Alex's emotional/memory authority modules. Changes should build from this one tree.
