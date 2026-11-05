"""First installation through the real login page, without precreated users."""
import os
import secrets
import subprocess
import sys
import time

import httpx
import pytest

from tests.test_production25d_browser import ROOT, production_browser
from tests.test_production_notes_browser import _free_port


@pytest.fixture
def fresh_host(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    base = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'PUBCAST_DATA_DIR': str(tmp_path / 'data'),
           'PUBCAST_ENFORCE_AUTH': '1', 'PUBCAST_JWT_SECRET': secrets.token_urlsafe(48)}
    with (tmp_path / 'server.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1',
                                 '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, timeout=2, trust_env=False) as api:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        if api.get('/health').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if proc.poll() is not None or time.monotonic() > deadline:
                        pytest.fail('Host failed to start: ' + (tmp_path / 'server.log').read_text()[-3000:])
                    time.sleep(.1)
                yield base, api
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(5)


@pytest.mark.parametrize('visibility', ['private', 'discoverable'])
def test_first_setup_optional_profile_skip_and_permanent_identity(fresh_host, production_browser, visibility):
    base, api = fresh_host
    context = production_browser.new_context(viewport={'width': 390, 'height': 844})
    try:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(base + '/login?next=%2Fstatic%2Fhuman_profile.html')
        page.wait_for_selector('#formRegister:visible')
        assert page.locator('#regVisibility').input_value() == 'private'
        page.fill('#regUser', 'first-owner')
        page.fill('#regPass', 'strong-owner-password-A19!')
        page.fill('#regPass2', 'strong-owner-password-A19!')
        page.select_option('#regVisibility', visibility)
        page.click('#regBtn')
        page.wait_for_url('**/static/human_profile.html?onboarding=1&next=**')
        page.wait_for_selector('#editor:not([hidden])')
        identity = page.evaluate('ReachAuth.getUser()')
        assert identity['user_id'].startswith('u_') and identity['user_id'] != identity['username']
        assert page.locator('#visibility').input_value() == visibility
        page.click('#skip')
        page.wait_for_url(base + '/static/human_profile.html')
        page.wait_for_selector('#editor:not([hidden])')
        token = page.evaluate('ReachAuth.getToken()')
        headers = {'Authorization': 'Bearer ' + token}
        me = api.get('/api/profile/me', headers=headers).json()
        assert me['user_id'] == identity['user_id']
        assert me['details']['onboarding_complete']
        assert me['details']['about'] == {} and me['details']['public_fields'] == []
        assert me['details']['discoverable'] == (visibility == 'discoverable')
        page.goto(base + '/login')
        page.wait_for_selector('#formLogin:visible')
        assert not page.locator('#tabRegister').is_visible()
        assert not errors
    finally:
        context.close()
