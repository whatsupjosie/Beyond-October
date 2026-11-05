"""Real host and browser: selective disclosure, recovery and stale draft safety."""
import json

import pytest

from tests.test_production25d_browser import production_server, production_browser


@pytest.fixture
def profile_page(production_server, production_browser):
    base, auth, api = production_server
    context = production_browser.new_context(viewport={"width": 390, "height": 844})
    context.add_init_script("if(location.origin === " + json.dumps(base) + ") sessionStorage.setItem('pubcast_token'," + json.dumps(auth['access_token']) + ");")
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base + '/static/human_profile.html')
    page.wait_for_selector('#editor:not([hidden])')
    yield page, api, auth
    context.close()
    assert not errors


def test_optional_profile_save_reel_consent_and_phone_layout(profile_page):
    page, api, auth = profile_page
    headers = {'Authorization': 'Bearer ' + auth['access_token']}
    uid = api.get('/api/profile/me', headers=headers).json()['user_id']
    requests = []
    page.route('https://www.youtube-nocookie.com/**', lambda route: (requests.append(route.request.url), route.abort()))
    page.fill('#displayName', 'Creative engineer')
    page.select_option('#visibility', 'discoverable')
    page.fill('#field-pronouns', 'they/them')
    page.check('#share-pronouns')
    page.fill('#field-city', 'Private city')
    page.fill('#field-reel', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    page.check('#share-reel')
    page.click('#save')
    page.wait_for_function("document.getElementById('status').textContent === 'Profile saved.'")
    card = api.get('/api/profiles/' + uid, headers=headers).json()
    assert card['about'] == {'pronouns': 'they/them', 'reel': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
    assert 'email' not in card
    page.click('#preview')
    assert page.locator('iframe').count() == 0 and not requests
    page.get_by_role('button', name='Load reel', exact=True).click()
    page.wait_for_function('document.querySelectorAll("iframe").length === 1')
    assert page.locator('iframe').get_attribute('src') == 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'
    page.reload()
    page.wait_for_selector('#editor:not([hidden])')
    assert page.locator('#field-city').input_value() == 'Private city'
    assert uid in page.locator('#identity').inner_text()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_unsaved_draft_reload_does_not_overwrite_newer_profile(profile_page):
    page, api, auth = profile_page
    headers = {'Authorization': 'Bearer ' + auth['access_token']}
    before = api.get('/api/profile/me', headers=headers).json()
    page.fill('#field-bio', 'Unsaved work in this tab')
    page.wait_for_function("document.getElementById('status').textContent.includes('Unsaved draft kept')")
    updated = api.patch('/api/profile/me', headers=headers, json={
        'revision': before['revision'], 'display_name': 'Changed in another window'})
    assert updated.status_code == 200
    page.reload()
    page.wait_for_function("document.getElementById('status').textContent.includes('host profile changed')")
    assert page.locator('#field-bio').input_value() == 'Unsaved work in this tab'
    page.click('#save')
    page.wait_for_function("document.getElementById('status').textContent.includes('another window')")
    after = api.get('/api/profile/me', headers=headers).json()
    assert after['display_name'] == 'Changed in another window'
    assert after['details']['about'].get('bio') != 'Unsaved work in this tab'
