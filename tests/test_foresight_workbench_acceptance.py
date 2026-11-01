"""Integrated workbench smoke gate: real Reach routes and Foresight application wiring.

This does not pretend to test GUI gestures or a live language-model provider.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_reach_serves_the_counter_and_real_primary_apps(client):
    counter = client.get('/foresight-counter')
    assert counter.status_code == 200
    assert 'foresight_programs.js' in counter.text
    assert 'foresight_counter.js' in counter.text
    assert 'foresight_chain.js' in counter.text
    for path, required in [('/writers-room', 'reach_auth.js'),
                           ('/pubpartner', 'reach_auth.js')]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text[:250])
        assert required in response.text, path


def test_counter_dependencies_and_program_targets_are_packaged(client):
    html = (ROOT / 'static/foresight_counter.html').read_text(encoding='utf-8')
    for asset in re.findall(r'<script[^>]+src="(/static/[^\"]+)"', html):
        response = client.get(asset)
        assert response.status_code == 200, asset
    programs = (ROOT / 'static/foresight_programs.js').read_text(encoding='utf-8')
    assert "id: 'twoi'" in programs and "twoIUi: '/writers-room'" in programs
    assert "id: 'pubpartner_workspace'" in programs and "url: '/pubpartner'" in programs
    assert "id: 'pubpartner_chat'" in programs and "url: '/pub-partner-chat'" in programs
    for path in ['/pub-partner-chat', '/static/world_chat.html', '/static/foresight_care.html']:
        assert client.get(path).status_code == 200, path


def test_blank_counter_is_default_and_restore_is_opt_in_by_saved_state():
    html = (ROOT / 'static/foresight_counter.html').read_text(encoding='utf-8')
    assert "params.has('fresh') ? null" in html
    assert 'if(saved) counter.restore(saved);' in html
    assert 'programs.autostart()' not in html
    programs = (ROOT / 'static/foresight_programs.js').read_text(encoding='utf-8')
    assert "id: 'world_chat'" in programs
    assert 'autostart: true' not in programs
    assert 'counter.open(\'world_chat\')' not in html


def test_writers_room_reach_runtime_is_actually_loaded(client):
    page = client.get('/writers-room')
    assert page.status_code == 200
    html = page.text
    assert '<script src="/2i-assets/reach.js"></script>' in html
    assert '<link rel="stylesheet" href="/2i-assets/reach.css">' in html
    for element in ('shelfBtn', 'partnerSelect', 'partnerNote', 'reachProvider', 'reachModel', 'reachCredential', 'reachBaseURL'):
        assert 'id="' + element + '"' in html, element
    for asset in ('/2i-assets/reach.js', '/2i-assets/reach.css'):
        assert client.get(asset).status_code == 200


def test_writers_room_preserves_partner_conversations_in_document_state():
    html = (ROOT / '2i/writers-room-v22.html').read_text(encoding='utf-8')
    assert 'conversations: {...conversations, [partnerId]: [...chatHistory]}' in html
    assert 'conversationIds: {...conversationIds}' in html
    assert 'chatHistory = conversations[partnerId] || []' in html
    assert 'restoreConversation();' in html


def test_2i_shelf_reports_unavailable_reach_instead_of_claiming_no_manuscripts():
    """Offline browsing must not suggest that saved server documents disappeared."""
    runtime = (ROOT / '2i/2i-assets/reach.js').read_text(encoding='utf-8')
    assert 'remoteError=error' in runtime
    assert 'Reach manuscripts unavailable' in runtime
    assert 'do not assume your server manuscripts are missing' in runtime
    assert 'Reconnect Reach to view server manuscripts' in runtime


def test_writers_room_document_api_stays_on_local_reach_even_with_remote_ai():
    """A remote Pub Partner endpoint must not receive private manuscript writes."""
    runtime = (ROOT / '2i/2i-assets/reach.js').read_text(encoding='utf-8')
    assert "function baseURL() { return (networked ? location.origin : 'http://localhost:8000')" in runtime
    assert "const endpoint=(cfg.pubpartner.endpoint || baseURL())" in runtime
    assert "await fetch(baseURL() + path" in runtime


def test_writers_room_does_not_require_character_profiles_to_load_manuscripts():
    runtime = (ROOT / '2i/2i-assets/reach.js').read_text(encoding='utf-8')
    assert "Character profiles are optional" in runtime
    assert "try {\n    const profiles=await api('/api/pubpartner/profiles/friend');" in runtime
    assert "$('partnerSelect').value=partnerId;" in runtime
