# PubCast Console Image Hotspot Handoff - 2026-06-18

## Scope

This pass turns the audio console and director console art into real, clickable studio control surfaces. It is non-destructive and lives inside the Big Zip construction build copy.

## Source Image Dimensions

These dimensions are now stored directly in the hotspot manifests. Do not remove them. The normalized hotspot map depends on them.

- Audio console clean image: `static/audio_console.png` - 1408 x 768
- Audio console overlay map: `static/audio_console_overlay_map.png` - 1408 x 768
- Director console clean image: `static/director_console.png` - 1024 x 1024
- Director console overlay map: `static/director_console_overlay_map.png` - 1024 x 1024

## Files Added

- `static/audio_console_hotspot_manifest.json`
- `static/director_console_hotspot_manifest.json`
- `static/console_hotspot_renderer.js`
- `static/console_hotspot_renderer.css`
- `static/audio_console.html`
- `static/director_console.html`
- `tests/test_console_hotspot_manifests.py`

## Routes Added

- `/audio-console`
- `/director-console`

## Control Mapping

The manifests translate user-marked overlay colors into PubCast control types:

- Dark hot pink: monitors/status panes
- Light blue: push buttons
- Light green: knobs/rotary controls
- Grey/white: sliders and slider paths
- Light pink: fan/seashell button groups
- Blue stick: guarded lever, currently mapped as a safe stop/lock style control
- Red circles: director dials/status dials

The controls call existing studio actions through `static/studio_console_hotspots.js`, including:

- `studio.readiness`
- `camera.switch.preview`
- `camera.switch.program`
- `camera.cut`
- `audio.event`
- `audio.stop_all`

## Validation

Passed:

- JavaScript syntax checks for `studio_console_hotspots.js` and `console_hotspot_renderer.js`
- Existing Node test: `tests/test_studio_console_hotspots_node.js`
- Inline script parsing for audio, director, switcher, studio control, and control-room pages
- JSON parsing for both manifests
- Focused pytest suite: 18 passed

Focused pytest command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPYCACHEPREFIX='C:\tmp\pubcast_pycache'
& 'C:\Users\hardc\anaconda3\python.exe' -B -m pytest tests\test_console_hotspot_manifests.py tests\test_studio_console_actions.py tests\test_studio_console_action_routes.py tests\test_studio_camera_preflight.py tests\test_program_audio_routes.py tests\test_program_audio_contract.py -q
```

## Honest Remaining Polish

- The controls are functional hotspot layers, not yet final luxury instrument behavior.
- Slider paths are normalized rectangular hit areas; curved path following can be refined later.
- Knobs support wheel and drag-style value changes, but final tactile animation can improve.
- The blue lever needs final product semantics. It is currently safe-mapped instead of destructive.
- The overlay maps are good enough for working controls, but final hotspots should be adjusted by eye in browser against the actual rendered art.
