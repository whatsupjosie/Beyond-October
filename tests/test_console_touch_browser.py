"""Touch, pen and mouse behaviour of the image consoles, in real Chromium.

Drives the typewriter keys and the audio console with emulated touch (including
two fingers at once and a knob drag), a hardware keyboard, and checks the
signed-in token reaches the studio action API. Skips when Playwright or its
browser is unavailable, like the other optional browser checks. The studio API
is mocked; nothing here talks to the network.
"""
from __future__ import annotations

import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "test-token-123"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(_Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def tablet(base_url):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        context = browser.new_context(viewport={"width": 1180, "height": 820}, has_touch=True, is_mobile=True)
        context.add_init_script(f"sessionStorage.setItem('pubcast_token', '{TOKEN}');")
        calls = []

        def api(route):
            request = route.request
            if request.method == "POST":
                calls.append({"url": request.url, "auth": request.headers.get("authorization", ""), "body": request.post_data})
            body = {"actions": []} if request.method == "GET" else {"ok": True}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        context.route("**/api/studio/**", api)
        page = context.new_page()
        page.calls = calls
        page.base_url = base_url
        yield page
        browser.close()


def _open(page, name):
    page.goto(f"{page.base_url}/static/{name}")
    page.wait_for_selector(".pc-console-hotspot")


def _center(page, selector):
    box = page.query_selector(selector).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _paper(page):
    return page.evaluate("document.querySelector('[data-typewriter-paper]').textContent")


def _tap_char(page, char):
    x, y = _center(page, f'[data-key-char="{char}"]')
    page.touchscreen.tap(x, y)


def test_touch_typing_writes_on_the_paper(tablet):
    _open(tablet, "typewriter_console.html")
    for char in "HELLO":
        _tap_char(tablet, char)
    _tap_char(tablet, "SPACE")
    for char in "JOSIE":
        _tap_char(tablet, char)
    assert _paper(tablet) == "hello josie"


def test_key_acts_on_touch_down_not_release(tablet):
    _open(tablet, "typewriter_console.html")
    x, y = _center(tablet, '[data-key-char="Q"]')
    cdp = tablet.context.new_cdp_session(tablet)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    assert _paper(tablet) == "q"
    assert tablet.evaluate("document.querySelector('[data-key-char=\"Q\"]').classList.contains('is-pressed')")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    assert not tablet.evaluate("document.querySelector('[data-key-char=\"Q\"]').classList.contains('is-pressed')")


def test_two_fingers_press_two_keys_at_once(tablet):
    _open(tablet, "typewriter_console.html")
    ax, ay = _center(tablet, '[data-key-char="A"]')
    sx, sy = _center(tablet, '[data-key-char="S"]')
    cdp = tablet.context.new_cdp_session(tablet)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": ax, "y": ay, "id": 1}, {"x": sx, "y": sy, "id": 2}]})
    assert sorted(_paper(tablet)) == ["a", "s"]
    pressed = tablet.evaluate("[...document.querySelectorAll('.is-pressed')].map(e => e.dataset.keyChar).sort()")
    assert pressed == ["A", "S"]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def test_shift_lasts_one_key_and_return_lever_starts_a_new_line(tablet):
    _open(tablet, "typewriter_console.html")
    x, y = _center(tablet, '[data-key-char="SHIFT"]')
    tablet.touchscreen.tap(x, y)
    _tap_char(tablet, "J")
    _tap_char(tablet, "O")
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="SHIFT"]'))
    _tap_char(tablet, "1")
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="RETURN"]'))
    _tap_char(tablet, "X")
    assert _paper(tablet) == "Jo!\nx"


def test_hardware_keyboard_types_and_animates_the_same_keys(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.keyboard.down("q")
    assert tablet.evaluate("document.querySelector('[data-key-char=\"Q\"]').classList.contains('is-pressed')")
    tablet.keyboard.up("q")
    tablet.keyboard.type("ab")
    tablet.keyboard.press("Shift+Digit1")
    assert _paper(tablet) == "qab!"
    tablet.keyboard.press("Backspace")
    assert _paper(tablet) == "qab"


def test_every_key_is_a_usable_touch_target_on_a_tablet(tablet):
    _open(tablet, "typewriter_console.html")
    sizes = tablet.evaluate(
        "[...document.querySelectorAll('.pc-console-hotspot--key')].map(e => { const r = e.getBoundingClientRect(); return [e.dataset.keyChar, r.width, r.height]; })"
    )
    # ~41 x 34 px at 1180 x 820: the most this art allows while paper and keys
    # stay on screen together. Each hit area is the whole key pitch (no dead gaps).
    too_small = [s for s in sizes if s[0] not in ("BLANK", "SPACE") and (s[1] < 38 or s[2] < 30)]
    assert not too_small, too_small


def test_paper_and_space_bar_are_visible_together_without_scrolling(tablet):
    _open(tablet, "typewriter_console.html")
    top = tablet.evaluate("document.querySelector('[data-typewriter-paper]').getBoundingClientRect().top")
    bottom = tablet.evaluate("document.querySelector('[data-key-char=\"SPACE\"]').getBoundingClientRect().bottom")
    height = tablet.evaluate("innerHeight")
    assert top >= 0 and bottom <= height, (top, bottom, height)
    assert tablet.evaluate("document.documentElement.scrollHeight") <= height + 2


def test_layout_refits_when_the_tablet_rotates(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.set_viewport_size({"width": 820, "height": 1180})
    tablet.wait_for_timeout(300)
    right = tablet.evaluate("document.querySelector('[data-key-char=\"SHIFT\"]:last-of-type, [data-key-char=\"/\"]').getBoundingClientRect().right")
    assert right <= 820 + 1, right
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="Z"]'))
    assert _paper(tablet) == "z"


def test_console_buttons_send_the_signed_in_token(tablet):
    _open(tablet, "audio_console.html")
    tablet.touchscreen.tap(*_center(tablet, ".pc-console-hotspot--button"))
    tablet.wait_for_timeout(400)
    assert tablet.calls, "tap did not reach the studio API"
    assert all(call["auth"] == f"Bearer {TOKEN}" for call in tablet.calls)


def test_knob_follows_a_finger_and_sends_one_action_on_release(tablet):
    _open(tablet, "audio_console.html")
    x, y = _center(tablet, ".pc-console-knob")
    cdp = tablet.context.new_cdp_session(tablet)
    turn = lambda: tablet.evaluate("document.querySelector('.pc-console-knob').style.getPropertyValue('--turn')")
    before = turn()
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 9):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + step * 12, "y": y, "id": 1}]})
    during = turn()
    assert during != before, "knob did not move under the finger"
    assert not tablet.calls, "action must wait for release"
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    tablet.wait_for_timeout(500)
    assert len(tablet.calls) == 1
    assert json.loads(tablet.calls[0]["body"])["value"] > 0.5


def test_cancelled_knob_drag_puts_the_knob_back(tablet):
    _open(tablet, "audio_console.html")
    x, y = _center(tablet, ".pc-console-knob")
    cdp = tablet.context.new_cdp_session(tablet)
    before = tablet.evaluate("document.querySelector('.pc-console-knob').style.getPropertyValue('--turn')")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 6):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + step * 12, "y": y, "id": 1}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchCancel", "touchPoints": []})
    tablet.wait_for_timeout(300)
    assert tablet.evaluate("document.querySelector('.pc-console-knob').style.getPropertyValue('--turn')") == before
    assert not tablet.calls


# ---- Exactness of typing -----------------------------------------------------

def test_armed_shift_is_visible_and_tapping_it_again_cancels_it(tablet):
    _open(tablet, "typewriter_console.html")
    shift = '[data-key-char="SHIFT"]'
    tablet.touchscreen.tap(*_center(tablet, shift))
    assert tablet.evaluate("document.querySelector('.pc-console-frame').classList.contains('is-shifted')")
    tablet.touchscreen.tap(*_center(tablet, shift))
    assert not tablet.evaluate("document.querySelector('.pc-console-frame').classList.contains('is-shifted')")
    _tap_char(tablet, "A")
    assert _paper(tablet) == "a"


def test_shift_applies_to_exactly_one_key_whatever_device_types_it(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="SHIFT"]'))
    tablet.keyboard.press("a")          # hardware key consumes the touch Shift
    tablet.keyboard.press("b")
    assert _paper(tablet) == "Ab"


def test_every_legend_types_exactly_what_it_says(tablet):
    _open(tablet, "typewriter_console.html")
    plain = {"-": "-", ";": ";", "'": "'", ",": ",", ".": ".", "/": "/", "\u00bd": "\u00bd"}
    plain.update({d: d for d in "1234567890"})
    plain.update({c: c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
    typed = ""
    for char, text in plain.items():
        _tap_char(tablet, char)
        typed += text
        assert _paper(tablet) == typed, (char, _paper(tablet))
    shifted = {"1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
               "-": "_", ";": ":", "'": '"', ",": "<", ".": ">", "/": "?", "Q": "Q"}
    for char, text in shifted.items():
        tablet.reload()
        tablet.wait_for_selector(".pc-console-hotspot")
        tablet.touchscreen.tap(*_center(tablet, '[data-key-char="SHIFT"]'))
        _tap_char(tablet, char)
        assert _paper(tablet) == text, (char, _paper(tablet))


def test_two_hundred_rapid_taps_are_all_typed_in_order(tablet):
    _open(tablet, "typewriter_console.html")
    cells = {c: _center(tablet, f'[data-key-char="{c}"]') for c in "ETAOINSHRDLU"}
    sequence = "".join("ETAOINSHRDLU"[(i * 7) % 12] for i in range(200))
    for char in sequence:
        tablet.touchscreen.tap(*cells[char])
    assert _paper(tablet) == sequence.lower()


def test_real_mouse_clicks_type_too(tablet):
    _open(tablet, "typewriter_console.html")
    for char in "MOUSE":
        x, y = _center(tablet, f'[data-key-char="{char}"]')
        tablet.mouse.click(x, y)
    assert _paper(tablet) == "mouse"


def test_long_text_keeps_the_newest_line_in_view(tablet):
    _open(tablet, "typewriter_console.html")
    for _ in range(40):
        tablet.touchscreen.tap(*_center(tablet, '[data-key-char="W"]'))
        tablet.touchscreen.tap(*_center(tablet, '[data-key-char="RETURN"]'))
    state = tablet.evaluate(
        "(() => { const p = document.querySelector('[data-typewriter-paper]'); return [p.scrollHeight, p.clientHeight, p.scrollTop]; })()"
    )
    assert state[0] > state[1], "test must overflow the paper"
    assert state[2] + state[1] >= state[0] - 2, state


def test_hardware_keys_are_left_alone_inside_a_text_box(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.evaluate("document.body.insertAdjacentHTML('beforeend', '<input id=box>'); document.getElementById('box').focus()")
    tablet.keyboard.type("hello")
    assert tablet.evaluate("document.getElementById('box').value") == "hello"
    assert _paper(tablet) == ""


def test_window_blur_releases_stuck_keys(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.keyboard.down("q")
    assert tablet.evaluate("document.querySelectorAll('.is-pressed').length") == 1
    tablet.evaluate("window.dispatchEvent(new Event('blur'))")
    assert tablet.evaluate("document.querySelectorAll('.is-pressed').length") == 0


def test_bad_manifest_view_or_keyless_key_is_rejected(tablet):
    _open(tablet, "typewriter_console.html")
    check = "m => { try { PubCastConsoleHotspotRenderer.validateManifest(m); return 'ok'; } catch (e) { return e.message; } }"
    base = {"image": {"width_px": 10, "height_px": 10}, "hotspots": []}
    assert tablet.evaluate(check, {**base, "view": {"x": 0.5, "w": 0.7}}) != "ok"
    assert tablet.evaluate(check, {**base, "view": {"x": 0, "w": 0}}) != "ok"
    keyless = {**base, "hotspots": [{"id": "k", "kind": "key", "x": 0, "y": 0, "w": 0.1, "h": 0.1}]}
    assert tablet.evaluate(check, keyless) != "ok"
    assert tablet.evaluate(check, {**base, "view": {"x": 0.16, "w": 0.68}}) == "ok"


# ---- Consoles: knobs, dials, sliders under a finger ---------------------------

def _drag(page, cdp, x, y, dx, dy=0, steps=8):
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + dx * step / steps, "y": y + dy * step / steps, "id": 1}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(400)


def test_tapping_a_volume_knob_sends_its_current_level_not_the_default(tablet):
    _open(tablet, "audio_console.html")
    x, y = _center(tablet, ".pc-console-knob")
    cdp = tablet.context.new_cdp_session(tablet)
    _drag(tablet, cdp, x, y, 60)                 # raise it
    raised = json.loads(tablet.calls[-1]["body"])["level"]
    assert raised > 0.5
    tablet.touchscreen.tap(x, y)                 # a plain tap afterwards
    tablet.wait_for_timeout(400)
    tapped = json.loads(tablet.calls[-1]["body"])
    assert tapped["level"] == pytest.approx(raised), tapped
    assert len(tablet.calls) == 2


def test_dragging_a_knob_up_the_screen_also_raises_it(tablet):
    _open(tablet, "audio_console.html")
    x, y = _center(tablet, ".pc-console-knob")
    _drag(tablet, tablet.context.new_cdp_session(tablet), x, y, 0, -60)
    assert json.loads(tablet.calls[-1]["body"])["level"] > 0.5


def _slot_points(page, selector, near_bottom, near_top):
    """Screen points along a fader's painted slot, from its tilt and length."""
    return page.evaluate(
        """([sel, lo, hi]) => {
            const wrap = document.querySelector(sel);
            const r = wrap.getBoundingClientRect();
            const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            const deg = parseFloat(getComputedStyle(wrap).getPropertyValue('--pc-track-angle')) || 0;
            const a = deg * Math.PI / 180, half = wrap.offsetHeight / 2;
            const at = f => [cx + Math.sin(a) * half * f, cy - Math.cos(a) * half * f];
            return [at(lo), at(hi)];
        }""",
        [selector, near_bottom, near_top],
    )


def test_pushing_a_fader_up_its_slot_raises_the_level_and_sends_once(tablet):
    _open(tablet, "audio_console.html")
    slider = '.pc-console-slider[title="Channel 1 level"]'
    cdp = tablet.context.new_cdp_session(tablet)
    (bx, by), (tx, ty) = _slot_points(tablet, slider, -0.85, 0.85)
    _drag(tablet, cdp, bx, by, tx - bx, ty - by, steps=12)
    assert len(tablet.calls) == 1, tablet.calls
    assert json.loads(tablet.calls[0]["body"])["level"] > 0.9
    (hx, hy), (lx, ly) = _slot_points(tablet, slider, 0.85, -0.85)
    _drag(tablet, cdp, hx, hy, lx - hx, ly - hy, steps=12)
    assert len(tablet.calls) == 2, tablet.calls
    assert json.loads(tablet.calls[1]["body"])["level"] < 0.1


def test_every_fader_lies_along_its_slot_and_holds_an_upright_control(tablet):
    _open(tablet, "audio_console.html")
    faders = tablet.evaluate(
        """() => [...document.querySelectorAll('.pc-console-slider')].map(w => {
            const i = w.querySelector('input');
            return [w.title, getComputedStyle(w).getPropertyValue('--pc-track-angle').trim(),
                    i.offsetWidth, w.clientHeight, w.clientWidth];
        })"""
    )
    assert len(faders) == 8
    for title, angle, input_length, slot_length, slot_width in faders:
        assert angle.endswith("deg"), title
        assert abs(input_length - slot_length) <= 1, (title, input_length, slot_length)
        assert slot_length > slot_width, title


def test_active_highlight_survives_the_sticky_touch_hover(tablet):
    _open(tablet, "audio_console.html")
    button = ".pc-console-hotspot--button"
    tablet.touchscreen.tap(*_center(tablet, button))
    tablet.wait_for_timeout(200)
    shade = tablet.evaluate(f"getComputedStyle(document.querySelector('{button}')).backgroundColor")
    assert shade != "rgba(0, 0, 0, 0)", shade


# ---- Hostile pass: layouts, repeat, accessibility, zero, zoom, failures ------------

def _key_event(page, code, key, shift=False, repeat=False, composing=False, ctrl=False):
    page.evaluate(
        "a => window.dispatchEvent(new KeyboardEvent('keydown', {code: a[0], key: a[1], shiftKey: a[2], repeat: a[3], isComposing: a[4], ctrlKey: a[5], bubbles: true, cancelable: true}))",
        [code, key, shift, repeat, composing, ctrl],
    )


def test_holding_backspace_and_letters_repeats_like_any_keyboard(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.keyboard.type("abcd")
    for _ in range(3):
        tablet.keyboard.down("Backspace")      # 2nd and 3rd arrive with repeat=true
    tablet.keyboard.up("Backspace")
    assert _paper(tablet) == "a"
    for _ in range(4):
        tablet.keyboard.down("x")
    tablet.keyboard.up("x")
    assert _paper(tablet) == "axxxx"


def test_other_layouts_caps_lock_and_dead_keys_type_what_the_keyboard_says(tablet):
    _open(tablet, "typewriter_console.html")
    _key_event(tablet, "KeyQ", "a")                      # AZERTY: the Q position types "a"
    assert tablet.evaluate("document.querySelector('[data-key-char=\"Q\"]').classList.contains('is-pressed')")
    _key_event(tablet, "KeyB", "B")                      # Caps Lock on, no Shift
    _key_event(tablet, "KeyC", "c", shift=True)          # Caps Lock on, Shift held
    _key_event(tablet, "Digit1", "&")                    # AZERTY digit row
    _key_event(tablet, "KeyE", "Dead")                   # dead key: types nothing
    _key_event(tablet, "KeyF", "f", composing=True)      # IME in progress: types nothing
    _key_event(tablet, "KeyG", "g", ctrl=True)           # a shortcut: types nothing
    assert _paper(tablet) == "aBc&"


def test_a_screen_reader_or_script_click_on_a_key_types_exactly_once(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.evaluate("document.querySelector('[data-key-char=\"K\"]').click()")
    assert _paper(tablet) == "k"
    _tap_char(tablet, "L")                               # a real tap still types once, not twice
    assert _paper(tablet) == "kl"


def test_a_blank_key_does_not_use_up_an_armed_shift(tablet):
    _open(tablet, "typewriter_console.html")
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="SHIFT"]'))
    tablet.touchscreen.tap(*_center(tablet, '[data-key-char="BLANK"]'))
    assert tablet.evaluate("document.querySelector('.pc-console-frame').classList.contains('is-shifted')")
    _tap_char(tablet, "A")
    assert _paper(tablet) == "A"


def test_no_long_press_menu_over_the_machine(tablet):
    _open(tablet, "typewriter_console.html")
    prevented = tablet.evaluate(
        "(() => { const e = new MouseEvent('contextmenu', {bubbles: true, cancelable: true}); "
        "document.querySelector('[data-key-char=\"A\"]').dispatchEvent(e); return e.defaultPrevented; })()"
    )
    assert prevented


def test_a_muted_knob_drags_from_zero_not_from_the_default(tablet):
    _open(tablet, "audio_console.html")
    x, y = _center(tablet, ".pc-console-knob")
    cdp = tablet.context.new_cdp_session(tablet)
    _drag(tablet, cdp, x, y, -400)                       # all the way down to 0
    assert json.loads(tablet.calls[-1]["body"])["level"] == 0
    _drag(tablet, cdp, x, y, 16)                         # a small nudge up
    nudged = json.loads(tablet.calls[-1]["body"])["level"]
    assert 0.05 < nudged < 0.2, nudged                   # from 0, not from 0.5
    tablet.evaluate("document.querySelector('.pc-console-knob').dispatchEvent(new WheelEvent('wheel', {deltaY: 100, bubbles: true, cancelable: true}))")
    tablet.wait_for_timeout(400)
    assert json.loads(tablet.calls[-1]["body"])["level"] == pytest.approx(max(0, nudged - 0.05), abs=1e-6)


def test_a_burst_of_wheel_ticks_sends_once(tablet):
    _open(tablet, "audio_console.html")
    tablet.evaluate(
        "(() => { const k = document.querySelector('.pc-console-knob'); "
        "for (let i = 0; i < 10; i++) k.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, bubbles: true, cancelable: true})); })()"
    )
    tablet.wait_for_timeout(500)
    assert len(tablet.calls) == 1, tablet.calls
    assert json.loads(tablet.calls[0]["body"])["level"] == pytest.approx(1.0)


def test_pinch_zoom_does_not_shrink_the_machine(base_url, tablet):
    # visualViewport.height collapses while a person pinch-zooms; the layout must ignore it.
    tablet.context.add_init_script(
        "Object.defineProperty(window, 'visualViewport', {value: {height: 90, width: 90, scale: 4, addEventListener() {}}});"
    )
    _open(tablet, "typewriter_console.html")
    box = tablet.query_selector(".pc-console-viewport").bounding_box()
    assert box["height"] > 400, box


def test_touch_padding_never_reaches_into_a_neighbour(tablet):
    _open(tablet, "audio_console.html")
    rects = tablet.evaluate(
        """() => [...document.querySelectorAll('.pc-console-layer > .pc-console-hotspot:not(.pc-console-hotspot--monitor):not(.pc-console-hotspot--key)')].map(n => {
            const r = n.getBoundingClientRect();
            const pad = parseFloat(getComputedStyle(n, '::before').top) * -1 || 0;
            return [n.title, r.left - pad, r.top - pad, r.right + pad, r.bottom + pad, r.left, r.top, r.right, r.bottom];
        })"""
    )
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            raw_overlap = a[5] < b[7] and b[5] < a[7] and a[6] < b[8] and b[6] < a[8]
            if raw_overlap:
                continue                                   # art-level overlap in the manifest, not padding
            padded_overlap = a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]
            assert not padded_overlap, (a[0], b[0])


def test_a_missing_map_says_so_instead_of_failing_silently(tablet):
    tablet.context.route("**/typewriter_console_hotspot_manifest.json", lambda route: route.fulfill(status=404, body="no"))
    tablet.goto(f"{tablet.base_url}/static/typewriter_console.html")
    tablet.wait_for_function("document.querySelector('[data-console-status]').dataset.level === 'error'")
    assert "Could not load the console map (404)" in tablet.inner_text("[data-console-status]")


# ---- Signed out, host errors, overlapping requests ------------------------------

def _fresh_page(tablet, token=None, auth_enforced=True, studio=None):
    context = tablet.context.browser.new_context(viewport={"width": 1180, "height": 820}, has_touch=True, is_mobile=True)
    if token:
        context.add_init_script(f"sessionStorage.setItem('pubcast_token', '{token}');")
    context.route("**/api/auth/status", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps({"auth_enforced": auth_enforced, "setup_required": False})))
    if studio:
        context.route("**/api/studio/**", studio)
    page = context.new_page()
    page.base_url = tablet.base_url
    return page


def test_signed_out_visitor_is_told_to_sign_in_and_brought_back(tablet):
    page = _fresh_page(tablet)
    _open(page, "audio_console.html")
    page.wait_for_selector("[data-console-signin]")
    assert page.inner_text("[data-console-status]") == "Signed out. Sign in to use the console."
    assert page.get_attribute("[data-console-signin]", "href") == "/login?next=%2Fstatic%2Faudio_console.html"


def test_no_sign_in_line_when_the_host_does_not_require_it(tablet):
    page = _fresh_page(tablet, auth_enforced=False)
    _open(page, "audio_console.html")
    page.wait_for_timeout(300)
    assert page.query_selector("[data-console-signin]") is None


def test_the_typewriter_never_asks_for_sign_in(tablet):
    page = _fresh_page(tablet)
    _open(page, "typewriter_console.html")
    page.wait_for_timeout(300)
    assert page.query_selector("[data-console-signin]") is None


def test_an_expired_token_shows_the_sign_in_line_on_first_touch(tablet):
    refuse = lambda route: route.fulfill(status=401, content_type="application/json", body=json.dumps({"detail": "Invalid or expired token"}))
    page = _fresh_page(tablet, token="stale", studio=refuse)
    _open(page, "audio_console.html")
    page.touchscreen.tap(*_center(page, ".pc-console-hotspot--button"))
    page.wait_for_selector("[data-console-signin]")


def test_a_host_error_page_is_reported_plainly(tablet):
    crash = lambda route: route.fulfill(status=502, content_type="text/html", body="<html>Bad gateway</html>")
    page = _fresh_page(tablet, token="t", studio=crash)
    _open(page, "audio_console.html")
    page.touchscreen.tap(*_center(page, ".pc-console-hotspot--button"))
    page.wait_for_function("document.querySelector('[data-console-status]').dataset.level === 'error'")
    assert page.inner_text("[data-console-status]") == "Studio console request failed (502)"


def test_a_slow_earlier_answer_never_covers_the_newest_status(tablet):
    page = _fresh_page(tablet, token="t", studio=lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps({"ok": True, "actions": []})))
    # Hold back the answer to the first studio action by 900 ms, in the page.
    page.add_init_script("""(() => {
        const real = window.fetch.bind(window);
        let first = true;
        window.fetch = (url, opts) => {
            const slow = first && opts && opts.method === 'POST' && String(url).includes('/api/studio/actions/');
            if (slow) first = false;
            return slow ? new Promise(r => setTimeout(() => r(real(url, opts)), 900)) : real(url, opts);
        };
    })();""")
    _open(page, "audio_console.html")
    page.evaluate("document.querySelector('.pc-console-hotspot--button').click()")
    page.wait_for_timeout(100)
    page.evaluate("document.querySelector('.pc-console-hotspot--fan').click()")
    page.wait_for_timeout(1400)
    assert page.inner_text("[data-console-status]") == "Dialogue cue fan ok."
