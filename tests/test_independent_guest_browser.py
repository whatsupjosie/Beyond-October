"""Actual popup signing and owner approval across two independently running copies."""
from contextlib import contextmanager
import json

from tests.test_human_profile_onboarding_browser import fresh_host
from tests.test_independent_guest_hosts import setup
from tests.test_production25d_browser import production_browser


def seed(context, base, token):
    context.add_init_script('if(location.origin===' + json.dumps(base) + ') sessionStorage.setItem("pubcast_token",' + json.dumps(token) + ');')


def test_browser_invite_home_popup_owner_approval_and_revoke(tmp_path, production_browser):
    start = contextmanager(fresh_host.__wrapped__)
    with start(tmp_path/'production') as (host_url, host), start(tmp_path/'visitor') as (home_url, home):
        owner, owner_headers = setup(host, 'production-owner')
        human, home_headers = setup(home, 'visiting-owner')
        owner_context = production_browser.new_context(viewport={'width': 1200, 'height': 900})
        visitor_context = production_browser.new_context(viewport={'width': 390, 'height': 844})
        seed(owner_context, host_url, owner['access_token'])
        seed(visitor_context, home_url, human['access_token'])
        errors = []
        for context in [owner_context, visitor_context]:
            context.on('page', lambda page: page.on('pageerror', lambda exc: errors.append(str(exc))))
        try:
            director = owner_context.new_page()
            director.goto(host_url+'/static/human_visits.html?mode=host')
            director.wait_for_function('document.getElementById("pending").textContent.includes("No verified guests")')
            director.click('#createInvite')
            director.wait_for_selector('#inviteOut:visible')
            invitation = director.locator('#inviteOut').input_value()
            visitor = visitor_context.new_page()
            visitor.goto(host_url+'/static/human_visits.html?mode=join')
            visitor.fill('#invite', invitation)
            visitor.click('#prepareButton')
            visitor.wait_for_selector('#homeOrigin:visible')
            visitor.fill('#homeOrigin', home_url)
            with visitor.expect_popup() as opened:
                visitor.click('#openHome')
            home_page = opened.value
            home_page.wait_for_selector('#signCard:visible')
            assert host_url in home_page.locator('#target').inner_text()
            home_page.check('#consent')
            home_page.click('#signCard')
            home_page.wait_for_selector('#signed:not([hidden])')
            visitor.wait_for_function('document.getElementById("status").textContent.includes("Waiting for your host")')
            assert visitor.locator('#enter').is_hidden()
            director.click('#refresh')
            director.wait_for_selector('#pending article')
            assert human['user_id'] in director.locator('#pending').inner_text()
            assert home_page.locator('#fingerprint').inner_text() in director.locator('#pending').inner_text()
            pending = host.get('/api/guests/pending', headers=owner_headers).json()['pending'][0]
            director.get_by_role('button', name='Approve visit', exact=True).click()
            visitor.wait_for_selector('#enter:visible', timeout=15000)
            assert visitor.evaluate('ReachAuth.getUser().user_id') == human['user_id']
            assert visitor.evaluate('document.documentElement.scrollWidth <= innerWidth')
            private_note=host.post('/api/notes',headers=owner_headers,json={'subject':'Owner private mirror note','to':[owner['user_id']]})
            assert private_note.status_code==201
            visitor.click('#enter')
            visitor.wait_for_function('document.documentElement.dataset.ready === "1"')
            visitor.wait_for_function('window.PubCastWalk?.S.key === "green_room/main"')
            visitor.evaluate("PubCastWalk.setView('dressing_room','wide',{})")
            visitor.wait_for_function('window.PubCastNotes?.state.enabled')
            assert not visitor.evaluate('PubCastNotes.state.notes.some(n=>n.subject==="Owner private mirror note")')
            visitor.goto(host_url+'/static/human_profile.html')
            visitor.wait_for_function('document.getElementById("status").textContent.includes("visiting card")')
            assert visitor.locator('#editor').is_hidden()
            assert human['user_id'] in visitor.locator('#identity').inner_text()
            director.fill('#revokeId', pending['entry_id'])
            director.locator('#revoke button').click()
            director.wait_for_function('document.getElementById("status").textContent.includes("revoked")')
            visitor.reload()
            visitor.wait_for_url('**/login?next=**')
            visitor.wait_for_selector('#loginUser:visible')
            assert visitor.evaluate('sessionStorage.getItem("pubcast_token")') is None
            assert not errors
        finally:
            owner_context.close()
            visitor_context.close()
