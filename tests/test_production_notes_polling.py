"""The notes client must not hammer a host that is not answering.

It used to ask for new notes every 20 seconds forever, signed out or with no host at all (every ask a console error
and a line in the host's log). It now waits twice as long after each failed ask, up to five minutes, and returns to 20
seconds on the first answer. The page here is a bare one with the real script and a controllable clock, so ten simulated
minutes take a moment. Skips without Playwright/Chromium.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "static" / "production_notes.js").read_text(encoding="utf-8")
SPOTS = (ROOT / "static" / "world" / "note_spots.json").read_text(encoding="utf-8")
ORIGIN = "http://notes.test"


def _page(browser, answer):
    """A page with the real notes script; `answer` is a mutable dict deciding what /api/notes replies."""
    context = browser.new_context()
    page = context.new_page()
    asks = []

    def route(r):
        url = r.request.url
        path = url[len(ORIGIN):].split("?")[0]
        if path == "/":
            r.fulfill(status=200, content_type="text/html", body='<!doctype html><html><body><div id="stage"></div><script src="/static/production_notes.js"></script></body></html>')
        elif path == "/static/production_notes.js":
            r.fulfill(status=200, content_type="text/javascript", body=SCRIPT)
        elif path == "/static/world/note_spots.json":
            r.fulfill(status=200, content_type="application/json", body=SPOTS)
        elif path == "/api/notes":
            asks.append(page.evaluate("Date.now()"))
            r.fulfill(status=answer["status"], content_type="application/json", body=answer["body"])
        else:
            r.fulfill(status=404, body="")
    context.route("**/*", route)
    page.clock.install()
    page.goto(ORIGIN + "/")
    return context, page, asks


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        yield b
        b.close()


def _run(page, seconds):
    for _ in range(seconds):
        page.clock.run_for(1000)


def test_an_unanswered_host_is_asked_less_and_less_often(browser):
    context, page, asks = _page(browser, {"status": 404, "body": ""})
    try:
        page.wait_for_function("!!window.PubCastNotes")
        page.wait_for_timeout(300)
        _run(page, 600)                                   # ten minutes
        page.wait_for_timeout(300)
        # 1 immediate ask, then after 20, 40, 80, 160 and 300 s, then every 300 s: 6 or 7 asks in ten minutes, not 31.
        assert 5 <= len(asks) <= 8, len(asks)
        gaps = [round((b - a) / 1000) for a, b in zip(asks, asks[1:])]
        for got, want in zip(gaps[:5], [20, 40, 80, 160, 300]):
            assert abs(got - want) <= 3, gaps
    finally:
        context.close()


def test_signed_out_is_treated_the_same_way_and_the_first_answer_restores_the_pace(browser):
    answer = {"status": 401, "body": '{"detail":"Sign in"}'}
    context, page, asks = _page(browser, answer)
    try:
        page.wait_for_function("!!window.PubCastNotes")
        page.wait_for_timeout(300)
        _run(page, 150)                                   # asks at 0, 20, 60 and 140 seconds
        n = len(asks)
        assert n == 4, n
        answer.update(status=200, body='{"notes": [], "unread": 0}')
        _run(page, 165)                                   # the next ask is due 160 s after the one at 140 s
        page.wait_for_timeout(300)
        assert len(asks) == n + 1
        _run(page, 70)                                    # answered: back to every 20 s
        page.wait_for_timeout(300)
        assert len(asks) >= n + 4, len(asks)
    finally:
        context.close()
