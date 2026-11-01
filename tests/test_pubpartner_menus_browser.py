"""PubPartner's menus can actually be seen and clicked.

The top bar's notched shape is a CSS clip-path, which also hid every drop-down menu: they opened, but nothing showed
and nothing could be clicked (found 2026-10-28). An open menu is now shown outside the bar. This opens each of the
eight menus in the real page served by run_reach.py and checks that every item is the topmost thing at its own
centre, inside the window. It also checks that a click on an item runs it and that Escape puts the menu back.
Skips without Playwright/Chromium.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sync_api = pytest.importorskip("playwright.sync_api")
MENUS = ["file", "edit", "view", "media", "tools", "wardrobe", "memory", "settings"]


@pytest.fixture(scope="module")
def reach(tmp_path_factory):
    data = tmp_path_factory.mktemp("pp_menus")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k not in ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR")}
    log = open(data / "reach.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data), "--no-browser", "--no-legacy-2i"],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            assert proc.poll() is None, "run_reach.py exited during startup"
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.25)
        pw = secrets.token_urlsafe(20)
        token = httpx.post(base + "/api/auth/setup", json={"username": "josie-check", "password": pw, "confirm_password": pw}, timeout=10).json()["access_token"]
        yield base, token
    finally:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


@pytest.mark.parametrize("width,height", [(1440, 1000), (1280, 800)])
def test_every_pubpartner_menu_item_is_visible_and_clickable(reach, width, height):
    base, token = reach
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            ctx = browser.new_context(viewport={"width": width, "height": height})
            ctx.add_init_script("sessionStorage.setItem('pubcast_token', %r); sessionStorage.setItem('pubcast_user', JSON.stringify({username:'josie-check',user_id:'josie-check',role:'owner'}));" % token)
            page = ctx.new_page(); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/pubpartner")
            page.wait_for_function("document.getElementById('authGate').hidden", timeout=30000)
            for m in MENUS:
                page.click(f"[data-menu={m}]")
                items = page.evaluate("""() => [...document.querySelectorAll('.menu-pop.floating [role=menuitem]')].map(b => {
                    const r = b.getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                    return {text: b.textContent, top: e === b || b.contains(e), inside: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight, w: r.width};
                })""")
                assert items, f"{m} menu shows nothing"
                bad = [i["text"] for i in items if not (i["top"] and i["inside"] and i["w"] > 40)]
                assert bad == [], f"{m} menu items hidden or covered: {bad}"
                page.keyboard.press("Escape")
                assert page.evaluate(f"!document.querySelector('.menu-pop.floating') && !!document.querySelector('[data-menu={m}]').closest('.menu-root').querySelector('.menu-pop')")
            # a real click on an item runs it
            page.click("[data-menu=file]")
            page.click("[data-command=new-cartridge]")
            page.wait_for_selector("#cartridgeGate:not([hidden])")
            assert errors == []
        finally:
            browser.close()
