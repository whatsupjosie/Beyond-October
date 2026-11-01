# PubCast 2.5D television studio — developer launch and asset replacement

**Status:** Integration work in progress. Browser runtime acceptance is NOT verified. This is a separate local production console, not yet the fully integrated established Control Room or Blackbox.

## Launch

Serve the repository's `static/` directory with an ordinary local HTTP server. For example, from the repository root:

```sh
python3 -m http.server 8000 --directory static
```

Open `http://localhost:8000/production25d.html`. Do not use `file://` for module loading. On a phone, serve via an HTTPS origin for microphone permission. Browsers may limit IndexedDB or recording in private mode.

The existing `world_walk_glb.js` imports three.js from `static/vendor/three-0.160.0/` and test GLB models from `static/world/test_avatars/`. Verify those files exist in the chosen branch. The stage displays an explicit missing-avatar status instead of inventing a sprite actor.

## Real local production test

1. Load News and verify separate Program and Preview images.
2. Choose a camera and CUT. Program image must visibly change.
3. Start a production; change camera and trigger a cue.
4. Start recording with mic unchecked; run several seconds; stop recording.
5. End production; select the saved session; play back actual captured video.
6. Download the manifest and confirm the camera/cue events match actions.
7. Repeat with a microphone after granting browser permission; check real meter, mute and level.
8. Load each other genre and verify different set configurations and at least three camera compositions.
9. Reload and confirm previously stored session records remain accessible.
10. Check console errors, mobile layout, and stage avatar loading.

## Placeholder artwork

Each genre package uses independently replaceable procedural backgrounds, midground and foreground furniture/occlusion. The operator may load local images through three independent image inputs. These overrides are currently **browser-session temporary** and are not yet persistent across reloads. The generic placeholder rendering is intentionally original, not a copy of any television show's proprietary set.

Recommended starting image size: 1280×720 (16:9). Larger images are supported within browser memory limits. For foreground and midground layers, use transparent PNG/WebP with alpha. The renderer uses cover scaling and center crop, so align artwork to the stage geometry.

| Layer | Control | Suggested format | Behavior |
| --- | --- | --- | --- |
| Background | Background layer image | 1280×720 JPG/PNG/WebP | Replaces distant set wall |
| Midground | Mid-ground layer image | 1280×720 transparent PNG/WebP | Replaces middle-stage geometry |
| Foreground | Foreground transparent image | 1280×720 transparent PNG/WebP | Drawn after performers for occlusion |

Camera positions are independent of the artwork and live in `production25d_core.js`; genre packages are distinct declarative configurations.

## Engineering boundaries

The local console currently has its own MediaRecorder and IndexedDB. It must not be described as fully integrated with the established PubCast server-side Blackbox. Production-state events and recording media are saved locally in the browser. Browser storage is not a reliable long-term archive: export the media and JSON manifest.

The owner still needs to provide final art, outstanding Control Room photographs, and device-level acceptance; these do not excuse unfinished server/station wiring.

## Tests

```sh
node --test tests/test_production25d_core.cjs
node --check static/production25d_core.js
node --check static/production25d_renderer.js
node --check static/production25d_storage.js
node --check static/production25d_app.js
```

These are instructions, not claims that the commands have already passed.

## Shared audio and video control (work in progress)

When served by the authenticated full PubCast host, starting a 2.5D production attempts to register its genre-specific virtual cameras with the **existing** CameraManager via `/api/cameras/register` and selects Program/Preview through **the same** `/api/switcher` used by the ordinary Control Room and Director Switcher. This requires moderator permission. The 2.5D UI displays `VIDEO: SHARED SWITCHER` only after server acknowledgment; otherwise it displays `VIDEO: LOCAL ONLY` and logs the actual error.

The established Director Switcher and Control page now select Program/Preview from shared server state. The Director Switcher's audio controls use actual `/api/program-audio` mute/status actions; synthetic bouncing audio meters were removed. The Control page mixer Apply updates program master, dialogue, and music gain with checked HTTP responses.

The local production recorder can capture the established browser program audio mixer output and optionally mix a microphone track. The backend audio status snapshot initializes new clients to the current master/bus settings. **This does not yet deliver media streams from other browsers into the local recorder or place live 2.5D frames into the server video transport.** That is a distinct, outstanding integration requirement.

On a standalone static HTTP server, those backend APIs will be unavailable, so the stage operates in explicitly local-only mode; do not call it multi-client synchronized. Studio browser recordings are IndexedDB-backed, not a complete server Blackbox session.

Additional test source files:

```sh
node --test tests/test_production25d_switcher_bridge.cjs
python -m pytest -q tests/test_shared_studio_switchers.py
```

These commands still require execution on a full local checkout or available CI system.

The production package list now includes a dedicated political roundtable separate from formal debate (eight packages in total). The Director Switcher consults the shared camera registry, including 2.5D sources, rather than treating only its original static five labels as canonical. Its monitor frames still show 'video feed unbound' until real transport integration is verified.
