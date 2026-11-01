"""Real Chromium DOM/JS check with in-process REST bridge for restricted CI.

The browser renders the exact shared component markup used by Foresight's
world_chat.html iframe and 2i's sidebar and executes the actual widget JS.
Only HTTP fetch is bridged to a real FastAPI TestClient because this execution
host blocks Chromium localhost navigation. This is NOT a full-page or real
WebSocket/desktop-device acceptance test; those remain separate release gates.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router
from modules.hub import Hub
from modules.route_security import current_identity

ROOT = Path(__file__).resolve().parents[2]


def test_world_widgets_render_exchange_messages_and_retry_lost_receipt(tmp_path, monkeypatch):
    pytest.importorskip('bs4')
    playwright = pytest.importorskip('playwright.sync_api')
    from bs4 import BeautifulSoup
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    client = TestClient(app)
    token = create_access_token({'sub': 'owner-test', 'role': 'guest'})
    js = (ROOT / 'static' / 'world_chat_widget.js').read_text(encoding='utf-8')
    surfaces = (
        ('Foresight iframe', ROOT / 'static' / 'world_chat.html'),
        ('2i sidebar', ROOT / '2i' / 'index.html'),
    )
    fail_once = {'pending': True}
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True,
                **({'executable_path': chromium} if chromium else {}), args=['--no-sandbox'])
        except playwright.Error as exc:
            pytest.skip('Chromium unavailable: ' + str(exc).splitlines()[0])
        try:
            pages = []
            for _name, source in surfaces:
                html = source.read_text(encoding='utf-8')
                widget = BeautifulSoup(html, 'html.parser').select_one('[data-world-chat]')
                assert widget is not None, f'Shared World Chat widget missing: {source}'
                page = browser.new_page()

                def backend_binding(_source, url, options):
                    method = options.get('method', 'GET')
                    body = options.get('body')
                    response = client.request(method, url,
                                              headers={'Authorization': 'Bearer ' + token},
                                              content=body)
                    if method == 'POST' and fail_once['pending']:
                        fail_once['pending'] = False
                        raise RuntimeError('Injected lost receipt AFTER server commit')
                    return {'status': response.status_code, 'body': response.text}

                page.expose_binding('worldBackend', backend_binding)
                page.set_content('<html><body>' + str(widget) + '</body></html>')
                page.evaluate('''() => {
                    window.ReachAuth = {
                      getUser: () => ({username:'owner-test'}), getToken: () => ''
                    };
                    window.fetch = async (url, options={}) => {
                      const r = await window.worldBackend(url, {
                        method: options.method || 'GET', body:options.body || null
                      });
                      return new Response(r.body, {status:r.status,
                        headers:{'Content-Type':'application/json'}});
                    };
                }''')
                page.add_script_tag(content=js)
                pages.append(page)

            foresight, two_i = pages
            message = '  The exact Foresight sentence.  \n'
            foresight.locator('[data-world-input]').fill(message)
            foresight.locator('[data-world-send]').click()
            foresight.locator('[data-world-status]').get_by_text('Delivery unconfirmed', exact=False).wait_for()
            assert foresight.locator('[data-world-input]').input_value() == message
            assert len(hub._read_history_sync(hub._log_path('world'), 100)) == 1
            foresight.locator('[data-world-send]').click()
            from playwright.sync_api import expect
            expect(foresight.locator('[data-world-input]')).to_have_value('', timeout=5000)
            assert len(hub._read_history_sync(hub._log_path('world'), 100)) == 1
            two_i.evaluate('''() => document.querySelector('[data-world-chat]')
                  .dispatchEvent(new Event('world-chat:refresh'))''')
            two_i.locator('[data-world-messages]').get_by_text('The exact Foresight sentence.', exact=False).wait_for()
            two_i.locator('[data-world-input]').fill('  Reply from 2i.  ')
            two_i.locator('[data-world-send]').click()
            foresight.evaluate('''() => document.querySelector('[data-world-chat]')
                  .dispatchEvent(new Event('world-chat:refresh'))''')
            foresight.locator('[data-world-messages]').get_by_text('Reply from 2i.', exact=False).wait_for()
            history = hub._read_history_sync(hub._log_path('world'), 100)
            assert [record['text'] for record in history] == [message, '  Reply from 2i.  ']
            assert history[0]['client_message_id'] != history[1]['client_message_id']
        finally:
            browser.close()
