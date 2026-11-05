"""Production notes in the studio, the way people use them: run_reach.py with a throwaway data folder, the owner and
two crew accounts, real notes, a real browser signed in through the real login page.

Proves: unread notes are painted on the makeup mirror and on the spots their senders chose; a wide shot's hotspot
bubble offers to read its note; reading one takes it off every spot; the corkboard's own sticky note opens the menu
(grouped by date or project); writing a note to yourself and a crew member sticks it and offers the email copy addressed
to their profile emails; Escape closes; no page errors. Skips without Playwright/Chromium.
"""
from __future__ import annotations

import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sync_api = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def reach(tmp_path_factory):
    data = tmp_path_factory.mktemp("notes_userdata")
    port = _free_port()
    log = open(data / "reach.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data),
                             "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    c = httpx.Client(base_url=base, timeout=20, trust_env=False)
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise AssertionError("run_reach.py exited during startup:\n" + (data / "reach.log").read_text(encoding="utf-8")[-4000:])
            try:
                if c.get("/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.3)
        else:
            raise AssertionError("PubCast did not start within 120 s")
        pw = secrets.token_urlsafe(18) + "A1!"
        r = c.post("/api/auth/setup", json={"username": "owner-notes", "password": pw, "confirm_password": pw,
                                             "display_name": "Josie", "email": "josie@example.com"})
        assert r.status_code == 201, r.text
        owner = {"Authorization": "Bearer " + r.json()["access_token"]}
        # Regression fixture for pre-existing local crew; the creation API is retired.
        from modules.auth import get_password_hash
        with sqlite3.connect(data / 'users.db') as db:
            for u, d in (("repete-notes", "RePete"), ("pete-notes", "Pete")):
                db.execute('INSERT INTO users(username,hashed_password,role) VALUES(?,?,?)', (u,get_password_hash(pw),'guest'))
        # Let the same additive backfill create their permanent legacy profiles.
        for p in c.get('/api/production/people', headers=owner).json()['people']:
            if p['username'] != 'owner-notes':
                token = c.post('/api/auth/login', json={'username':p['username'],'password':pw}).json()['access_token']
                assert c.patch('/api/profile/me', headers={'Authorization':'Bearer '+token},
                               json={'display_name':'RePete' if p['username']=='repete-notes' else 'Pete',
                                     'email':p['username']+'@example.com'}).status_code == 200
        people = {p["username"]: p for p in c.get("/api/production/people", headers=owner).json()["people"]}

        def login(u):
            return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": u, "password": pw}).json()["access_token"]}
        rp, pt, me = login("repete-notes"), login("pete-notes"), people["owner-notes"]["user_id"]
        assert c.post("/api/notes", headers=pt, json={"subject": "Call time 6 am", "to": ["@production"], "project": "Episode 3"}).status_code == 201
        assert c.post("/api/notes", headers=rp, json={"subject": "Mix notes, ep. 3", "body": "The cold open is hot.",
                                                       "to": [me], "spots": ["audio_console"], "project": "Episode 3"}).status_code == 201
        assert c.post("/api/notes", headers=pt, json={"subject": "Rehearsal 11/10", "to": [me], "spots": ["director_console"]}).status_code == 201
        yield base, "owner-notes", pw
    finally:
        c.close()
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


def _bubble(page, hotspot_id):
    page.evaluate("(id) => { const W = PubCastWalk; W.showHotspotBubble(W.S.view.hotspots.find(h => h.id === id)); }", hotspot_id)
    return page.evaluate("[...document.querySelectorAll('#bubble button')].map(b => b.textContent)")


def test_notes_on_the_mirror_and_consoles_the_menu_and_writing_one(reach):
    base, user, pw = reach
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/login?next=%2Fwalk")
            page.fill("#loginUser", user); page.fill("#loginPass", pw); page.keyboard.press("Enter")
            page.wait_for_url("**/walk**", timeout=20000)
            page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=30000)
            page.wait_for_function("window.PubCastNotes && PubCastNotes.state.enabled && PubCastNotes.state.notes.length === 3", timeout=20000)

            # the dressing room: all three unread notes on the makeup mirror, painted into the picture
            page.evaluate("PubCastWalk.setView('dressing_room', 'wide', {})")
            page.wait_for_function("PubCastWalk.S.key === 'dressing_room/wide'")
            on_mirror = page.evaluate("PubCastNotes.state.notes.filter(n => n.unread && n.spots.includes('mirror')).length")
            assert on_mirror == 3
            assert _bubble(page, "makeup-station")[:3] == ["Read note: Rehearsal 11/10", "Read note: Mix notes, ep. 3", "Read note: Call time 6 am"]
            page.evaluate("PubCastWalk.hideBubble()")
            # each note lies on the glass: every corner of its three slots falls inside the mirror's measured surface
            inside = page.evaluate("""() => { const f = PubCastNotes, s = f.state.file.spots.mirror.surfaces[0];
                const inQ = (p, q) => { let c = false; for (let i = 0, j = 3; i < 4; j = i++) { const [xi, yi] = q[i], [xj, yj] = q[j];
                    if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi) c = !c; } return c; };
                return s.slots.every(sl => f._noteQuad(s, sl, s.note_w).every(p => inQ(p, s.quad))); }""")
            assert inside is True

            # the control room: the audio console's note is offered from its bubble; reading it takes it off every spot
            page.evaluate("PubCastWalk.setView('control_room', 'main', {})")
            page.wait_for_function("PubCastWalk.S.key === 'control_room/main'")
            assert _bubble(page, "audio-console") == ["Read note: Mix notes, ep. 3", "Close"]
            assert _bubble(page, "director-console")[0] == "Read note: Rehearsal 11/10"
            _bubble(page, "audio-console")
            page.get_by_role("button", name="Read note: Mix notes, ep. 3").click()
            page.wait_for_selector("#pnLayer .pn-sheet h1", timeout=10000)
            assert page.locator("#pnLayer .pn-sheet h1").inner_text() == "Mix notes, ep. 3"
            assert "The cold open is hot." in page.locator("#pnLayer .pn-body").inner_text()
            page.get_by_role("button", name="Close").click()
            page.wait_for_selector("#pnLayer .pn-card", timeout=10000)           # closing a note lands on the menu
            page.keyboard.press("Escape")
            page.wait_for_function("document.getElementById('pnLayer').hidden && PubCastNotes.state.unread === 2", timeout=10000)
            assert _bubble(page, "audio-console") == ["Close"]
            page.evaluate("PubCastWalk.hideBubble()")

            # the corkboard: its own sticky note opens the menu
            page.evaluate("PubCastWalk.setView('dressing_room', 'corkboard', {})")
            page.wait_for_function("PubCastWalk.S.key === 'dressing_room/corkboard' && PubCastNotes.state.hits.some(h => h.open === null)", timeout=10000)
            q = page.evaluate("PubCastNotes.state.hits.find(h => h.open === null).quad")
            cx, cy = sum(x for x, _ in q) / 4, sum(y for _, y in q) / 4
            sx, sy = page.evaluate("([x, y]) => { const r = document.getElementById('c').getBoundingClientRect(); const s = PubCastWalk.toScreen([x, y]); return [r.left + s[0], r.top + s[1]]; }", [cx, cy])
            page.mouse.click(sx, sy)
            page.wait_for_selector("#pnLayer .pn-card", timeout=10000)
            assert page.locator("#pnLayer .pn-card h3").all_inner_texts() == ["Rehearsal 11/10", "Mix notes, ep. 3", "Call time 6 am"]
            page.get_by_role("button", name="By project").click()
            page.wait_for_function("[...document.querySelectorAll('#pnLayer .pn-group')].map(g => g.textContent).join('|') === 'Episode 3|No project'")

            # writing one: to yourself, CC Pete, also on the audio console, with the email copy
            page.get_by_role("button", name="New sticky note").click()
            page.wait_for_selector("#pnLayer form", timeout=10000)
            page.locator(".pn-pick[data-kind='to']", has_text=re.compile(r"^Me$")).click()
            page.locator(".pn-pick[data-kind='cc']", has_text=re.compile(r"^Pete$")).click()
            page.locator("input.pn-subject").fill("Lav mics in green room")
            page.locator(".pn-form textarea").fill("Two new lavs on the couch.")
            page.get_by_role("button", name="Audio console").click()
            page.locator(".pn-form input[type=checkbox]").check()
            page.get_by_role("button", name="Stick it").click()
            page.wait_for_selector("a.pn-mail", timeout=10000)
            href = page.get_attribute("a.pn-mail", "href")
            assert href.startswith("mailto:josie%40example.com?cc=pete-notes%40example.com&subject=Lav%20mics%20in%20green%20room")
            page.get_by_role("button", name="Back to notes").click()
            page.wait_for_function("[...document.querySelectorAll('#pnLayer .pn-card h3')].some(h => h.textContent === 'Lav mics in green room')", timeout=10000)
            page.keyboard.press("Escape")
            page.wait_for_function("PubCastNotes.state.notes.some(n => n.subject === 'Lav mics in green room' && n.unread && n.spots.join() === 'mirror,audio_console')", timeout=10000)
            assert errors == []
        finally:
            browser.close()


def test_place_sticky_note_picks_a_room_then_a_place_and_opens_the_writer_with_it_chosen(reach):
    base, user, pw = reach
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/login?next=%2Fwalk")
            page.fill("#loginUser", user); page.fill("#loginPass", pw); page.keyboard.press("Enter")
            page.wait_for_url("**/walk**", timeout=20000)
            page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=30000)
            page.wait_for_function("window.PubCastNotes && PubCastNotes.state.enabled", timeout=20000)
            page.evaluate("PubCastWalk.setView('control_room', 'main', {})")
            page.wait_for_function("PubCastWalk.S.key === 'control_room/main'")

            page.evaluate("PubCastNotes.open()")
            page.get_by_role("button", name="Place sticky note").click()
            page.wait_for_selector("#pnLayer [data-room]", timeout=10000)
            rooms = page.locator("#pnLayer [data-room]").all_inner_texts()
            assert rooms[0] == "Control room (you are here)"              # the room you stand in comes first
            assert {"Dressing room", "Green room"} <= set(rooms)

            page.locator("#pnLayer [data-room='control_room']").click()
            page.wait_for_selector("#pnLayer [data-spot]", timeout=10000)
            assert page.locator("#pnLayer [data-spot]").all_inner_texts() == ["Audio console", "Director's console (video mixer)"]
            page.keyboard.press("Escape")                                  # Escape steps back to the rooms
            page.wait_for_selector("#pnLayer [data-room]", timeout=10000)
            page.locator("#pnLayer [data-room='control_room']").click()
            page.locator("#pnLayer [data-spot='audio_console']").click()

            page.wait_for_selector("#pnLayer form", timeout=10000)
            assert page.get_by_role("button", name="Audio console").get_attribute("aria-pressed") == "true"
            assert page.get_by_role("button", name="Director's console (video mixer)").get_attribute("aria-pressed") == "false"
            page.locator(".pn-pick[data-kind='to']", has_text=re.compile(r"^Me$")).click()
            page.locator("input.pn-subject").fill("Check the talkback")
            page.get_by_role("button", name="Stick it").click()
            page.wait_for_selector("#pnLayer .pn-card", timeout=10000)
            page.keyboard.press("Escape")
            page.wait_for_function("PubCastNotes.state.notes.some(n => n.subject === 'Check the talkback' && n.spots.join() === 'mirror,audio_console')", timeout=10000)
            assert errors == []
        finally:
            browser.close()
