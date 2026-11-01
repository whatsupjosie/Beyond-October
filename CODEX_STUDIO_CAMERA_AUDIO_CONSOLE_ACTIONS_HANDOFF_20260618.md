# PubCast Studio Camera/Audio Console Actions Handoff

Date: 2026-06-18

## Status

The studio is hooked up at the service/API level for the current construction build:

- Camera visibility checks are available.
- Recording preflight is available.
- Program audio state and recovery actions are available.
- Studio readiness aggregates camera, recording, and audio health.
- Future console/hotspot art now has a stable action mechanism to call.
- A no-UI browser adapter can bind future DOM hotspots to those stable action IDs.
- Successful studio action calls are witnessed by BlackBox as `studio.action`.

This does not create the final console art, room map, or hotspot coordinates. It creates the mechanism those hotspots can call once the console image exists.

## New Hotspot Mechanism

Frontend or image hotspot overlay should first call:

```text
GET /api/studio/actions
```

That returns stable action IDs and required payload fields. A hotspot can then call:

```text
POST /api/studio/actions/{action_id}
```

With a JSON payload.

Example:

```json
{
  "source_id": "medium_shot"
}
```

Posted to:

```text
POST /api/studio/actions/camera.switch.program
```

## Current Action IDs

- `studio.readiness`
- `camera.visibility.all`
- `camera.visibility.one`
- `camera.switch.program`
- `camera.switch.preview`
- `camera.cut`
- `recording.preflight`
- `recording.start`
- `recording.stop`
- `audio.status`
- `audio.event`
- `audio.stop_all`

Recording start and stop require explicit confirmation in the payload.

## Files Created Or Updated

- `modules/studio_console_actions.py`
  - Stable action registry and executor for future console/hotspot bindings.
- `modules/production_routes.py`
  - Mounted `/api/studio/actions`.
  - Mounted `/api/studio/actions/{action_id}`.
  - Calls `execute_studio_action(...)`.
  - Records successful action execution to BlackBox.
- `blackbox_recorder/pubcast_event_adapter.py`
  - Added `studio.action` event mapping.
- `tests/test_studio_console_actions.py`
  - Unit tests for action manifest and direct action execution.
- `tests/test_studio_console_action_routes.py`
  - Route tests for manifest, action execution, camera switching, BlackBox event, and confirmation guard.
- `static/studio_console_hotspots.js`
  - No-UI browser adapter for binding future image hotspots to studio action IDs.
- `tests/test_studio_console_hotspots_node.js`
  - Node smoke test for browser adapter request building and payload parsing.

## Validation

Focused console checks:

```text
6 passed
```

Broader camera/audio/BlackBox/runtime focused suite:

```text
36 passed
```

Syntax sanity check:

```text
AST OK
```

Node hotspot adapter smoke test:

```text
test_studio_console_hotspots_node.js passed
```

## Next Wiring Point

When the console image exists, the frontend only needs a hotspot overlay that stores:

- `hotspot_id`
- `label`
- `action_id`
- optional payload fields

The backend action contract is ready. The UI can remain visual and player-first while the backend stays stable and testable.

Optional future hotspot markup:

```html
<button
  data-studio-action="camera.switch.program"
  data-studio-param-source-id="medium_shot">
</button>
```

Then:

```javascript
const consoleHotspots = new PubCastStudioConsoleHotspots.StudioConsoleHotspots();
consoleHotspots.bind(document);
```

## Remaining Polish

- Add frontend hotspot overlay once console art exists.
- Add operator-facing affordances for confirm actions before recording start/stop.
- Add WebSocket broadcast after generic studio action execution if the final console UI wants instant live feedback without polling.
- Add action categories/icons/tooltips in the future manifest if the frontend wants to auto-render temporary controls.
