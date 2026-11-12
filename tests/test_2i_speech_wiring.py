"""2i speech wiring: the page must work with and without the local speech client.

2i is opened two ways. Inside the host, /static/speech_client.js defines window.PubcastSpeech and 2i hands
read-aloud and dictation to it. Opened on its own (from disk, offline) that script is absent, and 2i has to
fall back to the browser's own read-aloud and voice input instead of failing.

The real speech models are not needed here: the browser speech objects and the local client are replaced by
recording stand-ins that are installed before the page's own scripts run, so what is checked is that 2i calls
them correctly and reacts correctly to what they report.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"

BROWSER_SPEECH_STUB = """
window.__spoken = [];
window.__utterances = [];
window.SpeechSynthesisUtterance = function (text) { this.text = text; this.rate = 1; };
// window.speechSynthesis is a built-in accessor; plain assignment is ignored, so it is redefined.
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  cancel() { window.__cancels = (window.__cancels || 0) + 1; },
  speak(u) { window.__spoken.push({ text: u.text, rate: u.rate }); window.__utterances.push(u); },
} });
"""

LOCAL_CLIENT_STUB = """
window.__calls = { speak: [], stop: 0, bound: null };
window.__pending = [];
window.PubcastSpeech = {
  speak(text, options) {
    window.__calls.speak.push({ text, speed: options.speed, hasOnStart: typeof options.onStart === 'function' });
    window.__lastOptions = options;
    return new Promise((resolve, reject) => window.__pending.push({ resolve, reject }));
  },
  stop() { window.__calls.stop += 1; },
  bindDictation(button, input) { window.__calls.bound = { button: button && button.id, input: input && input.id }; },
};
"""


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binary not installed
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        yield b
        b.close()


def open_page(browser, init_script):
    context = browser.new_context()
    # Offline: only the file on disk loads. The local speech script therefore 404s exactly as it does standalone.
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
    context.add_init_script(init_script)
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda exc: page.problems.append(str(exc)))
    page.goto(PAGE.as_uri())
    page.wait_for_function("typeof speechRead === 'function' && typeof stopPlaying === 'function'")
    return page, context


# ── standalone: no local speech client ─────────────────────────────────────────────────────────────────

def test_standalone_read_aloud_uses_browser_speech_and_finishes(browser):
    page, context = open_page(browser, BROWSER_SPEECH_STUB)
    try:
        assert page.evaluate("typeof window.PubcastSpeech") == "undefined"
        page.evaluate("window.__done = 0; speechRead('Hello there.', () => { window.__done += 1; })")
        assert page.evaluate("window.__spoken") == [{"text": "Hello there.", "rate": 1}]
        page.evaluate("window.__utterances[0].onstart()")
        assert page.evaluate("speaking") is True
        page.evaluate("window.__utterances[0].onend()")
        assert page.evaluate("speaking") is False
        assert page.evaluate("window.__done") == 1
        assert page.problems == []
    finally:
        context.close()


def test_standalone_read_aloud_ignores_a_superseded_utterance(browser):
    page, context = open_page(browser, BROWSER_SPEECH_STUB)
    try:
        page.evaluate("window.__done = []; speechRead('first', () => window.__done.push('first')); speechRead('second', () => window.__done.push('second'))")
        # The first utterance ends late, after the second was started: it must not advance the show.
        page.evaluate("window.__utterances[0].onend()")
        assert page.evaluate("window.__done") == []
        page.evaluate("window.__utterances[1].onend()")
        assert page.evaluate("window.__done") == ["second"]
    finally:
        context.close()


def test_standalone_cancel_stops_browser_speech_and_silences_pending_callbacks(browser):
    page, context = open_page(browser, BROWSER_SPEECH_STUB)
    try:
        page.evaluate("window.__done = 0; speechRead('Hello', () => { window.__done += 1; })")
        before = page.evaluate("window.__cancels || 0")
        page.evaluate("cancelSpeech()")
        assert page.evaluate("window.__cancels") == before + 1
        page.evaluate("window.__utterances[0].onend()")
        assert page.evaluate("window.__done") == 0
        assert page.problems == []
    finally:
        context.close()


def test_standalone_without_any_browser_speech_still_completes_the_callback(browser):
    page, context = open_page(browser, "delete window.speechSynthesis; delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
    try:
        page.evaluate("window.__done = 0; speechRead('Hello', () => { window.__done += 1; })")
        assert page.evaluate("window.__done") == 1
        # And the mic button says why it is off instead of looking broken.
        assert page.locator("#chatMicBtn").is_disabled()
        assert page.locator("#chatMicBtn").get_attribute("title") == "Speech not supported in this browser"
        assert page.problems == []
    finally:
        context.close()


def test_standalone_voice_input_keeps_the_browser_recognizer(browser):
    stub = """
    window.__recs = [];
    window.SpeechRecognition = window.webkitSpeechRecognition = function () {
      this.start = () => { window.__recs.push('start'); };
      this.stop = () => { window.__recs.push('stop'); this.onend && this.onend(); };
      window.__rec = this;
    };
    """
    page, context = open_page(browser, stub)
    try:
        assert not page.locator("#chatMicBtn").is_disabled()
        page.fill("#chatInput", "hello")
        page.click("#chatMicBtn")
        assert page.evaluate("window.__recs") == ["start"]
        assert "listening" in page.locator("#chatMicBtn").get_attribute("class")
        page.evaluate("window.__rec.onresult({resultIndex: 0, results: [[{transcript: 'world'}]]})")
        assert page.input_value("#chatInput") == "hello world"
        page.click("#chatMicBtn")
        assert page.evaluate("window.__recs") == ["start", "stop"]
        assert "listening" not in (page.locator("#chatMicBtn").get_attribute("class") or "")
    finally:
        context.close()


def test_standalone_keeps_the_original_read_speed_range_and_hosted_uses_the_local_voice_range(browser):
    page, context = open_page(browser, BROWSER_SPEECH_STUB)
    try:
        assert page.evaluate("[speedSlider.min, speedSlider.max]") == ["0.5", "2.5"]
        page.evaluate("speedSlider.value = '2.25'; speechRead('fast', () => {})")
        assert page.evaluate("window.__spoken[0].rate") == 2.25
    finally:
        context.close()
    page, context = open_page(browser, LOCAL_CLIENT_STUB)
    try:
        assert page.evaluate("[speedSlider.min, speedSlider.max]") == ["0.7", "1.5"]
    finally:
        context.close()


# ── hosted: local speech client present ────────────────────────────────────────────────────────────────

def test_hosted_dictation_is_bound_to_the_mic_button_and_chat_input(browser):
    page, context = open_page(browser, LOCAL_CLIENT_STUB)
    try:
        assert page.evaluate("window.__calls.bound") == {"button": "chatMicBtn", "input": "chatInput"}
        assert page.problems == []
    finally:
        context.close()


def test_hosted_read_aloud_goes_through_the_local_client_with_a_clamped_speed(browser):
    page, context = open_page(browser, LOCAL_CLIENT_STUB + BROWSER_SPEECH_STUB)
    try:
        page.evaluate("window.__done = 0; speechRead('A line.', () => { window.__done += 1; })")
        call = page.evaluate("window.__calls.speak[0]")
        assert call == {"text": "A line.", "speed": 1, "hasOnStart": True}
        # The browser's own voice must not also speak.
        assert page.evaluate("window.__spoken.length") == 0
        page.evaluate("window.__lastOptions.onStart()")
        assert page.evaluate("speaking") is True
        page.evaluate("window.__pending[0].resolve({canceled: false})")
        page.wait_for_function("window.__done === 1")
        assert page.evaluate("speaking") is False

        # Speed is clamped into the local voice's range whatever the slider holds.
        page.evaluate("window.__done = 0; speedSlider.min = '0.1'; speedSlider.max = '9'; speedSlider.value = '5'; speechRead('x', () => {})")
        assert page.evaluate("window.__calls.speak[1].speed") == 1.5
        page.evaluate("speedSlider.value = '0.2'; speechRead('y', () => {})")
        assert page.evaluate("window.__calls.speak[2].speed") == 0.7
        assert page.problems == []
    finally:
        context.close()


def test_hosted_cancel_stops_the_local_client_and_a_stale_result_is_ignored(browser):
    page, context = open_page(browser, LOCAL_CLIENT_STUB)
    try:
        page.evaluate("window.__done = 0; speechRead('A line.', () => { window.__done += 1; })")
        page.evaluate("cancelSpeech()")
        assert page.evaluate("window.__calls.stop") == 1
        page.evaluate("window.__pending[0].resolve({canceled: false})")
        page.wait_for_timeout(100)
        assert page.evaluate("window.__done") == 0
    finally:
        context.close()


def test_hosted_client_failure_stops_playback_and_tells_the_writer(browser):
    page, context = open_page(browser, LOCAL_CLIENT_STUB)
    try:
        page.evaluate("playing = true; speechRead('A line.', () => {})")
        page.evaluate("window.__pending[0].reject(new Error('voice not installed'))")
        page.wait_for_function("playing === false")
        assert "Speech stopped: voice not installed" in page.locator("body").inner_text()
        assert page.problems == []
    finally:
        context.close()


def test_hosted_canceled_result_stops_playback(browser):
    page, context = open_page(browser, LOCAL_CLIENT_STUB)
    try:
        page.evaluate("playing = true; window.__done = 0; speechRead('A line.', () => { window.__done += 1; })")
        page.evaluate("window.__pending[0].resolve({canceled: true})")
        page.wait_for_function("playing === false")
        assert page.evaluate("window.__done") == 0
    finally:
        context.close()
