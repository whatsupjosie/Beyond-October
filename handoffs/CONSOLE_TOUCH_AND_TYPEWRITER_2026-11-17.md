# Console touch support and typewriter key hotspots - 2026-11-17

Josie's request: the typewriter keys must be touchable (iPad finger or mouse) and actually type; the control-room consoles must be touchable too. She knows few people will use it and wants it anyway.

## What was found first (verified in Chromium with emulated iPad touch)
- Audio and director consoles already existed (static/console_hotspot_renderer.js + manifests). Extended, not rebuilt.
- Every console button failed for a signed-in user: the page never sent the login token, so the server answered "Authentication required". (Mouse or touch, same.)
- Knobs and dials ignored a finger drag (no touch-action, value only on release, no cancel handling).
- Sliders sent their action twice per drag. Small controls had no larger touch target.

## Changed
- static/studio_console_hotspots.js: adds the token (sessionStorage pubcast_token, else localStorage pubpartner.auth.token.v1) to studio API calls.
- static/console_hotspot_renderer.js / .css: knobs follow a finger live and send once on release (cancel puts the knob back); sliders send once; touch-action and larger invisible touch targets on touchscreens; new "key" hotspot kind (acts on touch-down, many fingers at once, hardware keyboard mirrors and animates the same keys, Shift lasts one key); optional "view" crop that fits the picture to the screen so paper and keys are visible together.
- main.py: route /typewriter-console (3 lines).

## Added
- static/typewriter_console.html, typewriter_console_demo.js, typewriter_console_hotspot_manifest.json, typewriter_keys.webp (2560 x 1430 painting with readable key letters).
- tools/build_typewriter_manifest.py: regenerates the manifest. Key positions are measured from the painting; if the art is repainted, nudge the table in that file and re-run.
- tests/test_typewriter_console_manifest.py, tests/test_console_touch_browser.py.

## Contract for the real typewriter mode (not built yet)
Listen for "pubcast:key" on the frame: detail.text (what to insert), detail.char (A, 7, SPACE, RETURN, SHIFT, BACKSPACE), detail.source ("pointer" or "keyboard"). Sound and key-press animation hook in here. Keys carry no studio action.

## Second pass (self-audit) - problems found in the first delivery and fixed
- Tapping a volume knob sent the 0.5 default, jumping the volume. It now sends the knob's current level.
- A touch drag on a knob left a flag set that silently swallowed the next tap. Found by a new test; fixed (flag cleared on every press).
- Shift gave no visual sign and could not be cancelled. Both Shift keys now light while armed; tapping again cancels; one Shift lasts exactly one key from touch or keyboard.
- The hardware-keyboard mirror took keys from text boxes and left keys stuck when the window lost focus. It now ignores inputs, textareas, selects, editable areas and Ctrl/Cmd/Alt shortcuts, and releases keys on blur.
- Touch screens' sticky hover wiped the pressed/active highlight. Fixed.
- Slider could not resend the same value after a failed send. Fixed.
- iPad Safari 100vh taller than the screen: added 100dvh. Paper type size now follows the picture width, not the window.
- Manifest validation now rejects a bad "view" and a key with no char.
- Removed a sloppy leftover line in the browser test.

## Third pass (hostile review) - found and fixed
- Hardware typing used a US-only shifted table: wrong on other layouts and with Caps Lock. It now types exactly what the keyboard reports (event.key); only a Shift armed by touch is added. Dead keys, IME composition and Ctrl/Cmd/Alt shortcuts type nothing.
- Holding a key did not repeat, so holding Backspace deleted one character. Key repeat now works.
- A click with no pointer behind it (screen reader, switch control, Enter/Space on a focused key) is detected by pointerType, not by a fragile detail check.
- A knob at 0 (muted) was treated as unset: dragging from zero started at 0.5, and default_value 0 became 0.5. Zero is now a real level (knob and slider).
- Wheel/trackpad over a knob sent a request per tick; it now turns live and sends once when it settles.
- Layout used visualViewport.height, which shrinks while pinch-zooming and would shrink the machine. Now uses window.innerHeight.
- The 8 px touch padding could reach into neighbouring controls. Padding is now capped at half the on-screen gap to the nearest neighbour (measured from real boxes, because CSS enlarges some sliders).
- The blank key used up an armed Shift. It no longer does. Long-press context menu over the machine is blocked.
- A failed map or picture load now says so in the status bar.
- Test that used Playwright press("Shift+1") (not what a real keyboard sends) now uses Shift+Digit1.

## Found, not changed (existing data)
- In audio_console_hotspot_manifest.json some hotspots overlap each other on the art: audio.knob.room_gain with audio.fan.music_cue (about 30 px at 1100 px wide), audio.knob.sfx_gain with audio.knob.ui_gain (about 11 px). Where they overlap, the later one in the file takes the tap. Needs a look against the painting.
- control_room.html, studio_control_room.html and director_switcher.html load studio_console_hotspots.js, so they now send the login token too. Not tested on those pages.
- Several *_SHA256 manifest files list older copies of these files; no test checks them against the live files.

## Verified
- 163 related Python tests pass (2 skipped, unrelated); Node test passes. Earlier: 94 related Python tests pass (2 skipped, unrelated research protocol); existing Node console test passes. Browser tests drive real Chromium with touch: every key legend types what it says (plain and shifted), 200 rapid taps in order, real mouse clicks, two fingers, hardware keyboard incl. Shift+1 and Backspace, text-box guard, blur release, long text scroll, knob drag/tap/cancel, slider single send, token header, rotation refit.
- Screenshots with outlines checked by eye at landscape (1180 x 820) and portrait (820 x 1180): hotspots line up with the painted keys.

## Not verified / not done
- Not tried on a real iPad or Safari; only emulated touch in Chromium.
- In portrait the keys are about 35 px wide; the size test only enforces landscape. The return-lever hotspot is a 135 x 131 px circle around a thin diagonal lever (generous, but not shaped to it).
- The console pages show no sign-in prompt: with no token the buttons fail with the server's "Authentication required".
- Keys are about 41 x 34 px on an 11-inch iPad in landscape (the whole key pitch is the hit area). The art limits this while paper and keys stay on screen together.
- Sound is not wired. The typewriter is not inside 2i: this is the bench page /typewriter-console.
- The control-room consoles' remaining items from the 2026-06-18 handoff (curved slider paths, lever meaning) are untouched. Studio actions themselves were mocked in tests, not run against a live studio.
- The control_room.html and studio_control_room.html pages were not changed or tested for touch.
- Not committed or pushed: this session had read-only access to the repo.
