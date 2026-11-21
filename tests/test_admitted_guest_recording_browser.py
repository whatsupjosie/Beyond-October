"""Run the full existing media acceptance with separately owned, admitted guests.

Reuses the recording assertions unchanged. Only contributor authentication is
replaced with real host-issued leases after each own copy signs its visit.
Oscillators still replace physical microphones; that hardware gate remains open.
"""
from contextlib import ExitStack, contextmanager

from tests import test_participant_audio_browser as recording
from tests.test_guest_identity import CONSENTS
from tests.test_human_profile_onboarding_browser import fresh_host
from tests.test_independent_guest_hosts import setup
from tests.test_production25d_browser import production_browser, production_server, studio


def test_independently_admitted_guests_mix_record_reconnect_and_export(studio, production_browser, production_server, tmp_path, monkeypatch):
    _, host_auth, host = production_server
    owner = {'Authorization': 'Bearer ' + host_auth['access_token']}
    with ExitStack() as stack:
        leases = {}
        for index, frequency in enumerate([440, 880]):
            _, home = stack.enter_context(contextmanager(fresh_host.__wrapped__)(tmp_path/f'own-copy-{index}'))
            human, home_headers = setup(home, f'visitor-{index}')
            invitation = host.post('/api/guests/invites', headers=owner, json={}).json()['invite_code']
            challenge = host.post('/api/guests/challenge', json={'invite_code': invitation}).json()
            proof = home.post('/api/guests/sign', headers=home_headers, json={'challenge': challenge['challenge'], 'consents': CONSENTS})
            assert proof.status_code == 200, proof.text
            entry = host.post('/api/guests/request', json=proof.json()).json()['entry_id']
            pending = next(p for p in host.get('/api/guests/pending', headers=owner).json()['pending'] if p['entry_id'] == entry)
            assert host.post('/api/guests/entries/'+entry+'/approve', headers=owner, json={'fingerprint': pending['fingerprint']}).status_code == 200
            lease = host.post('/api/guests/status', json={'poll_token': challenge['poll_token']})
            assert lease.status_code == 200, lease.text
            leases[frequency] = lease.json()
            assert leases[frequency]['user_id'] == human['user_id']
        assert leases[440]['user_id'] != leases[880]['user_id']
        original_contributor = recording.contributor

        def contributor(browser, base, _owner_auth, room, frequency):
            context, page = original_contributor(browser, base, leases[frequency], room, frequency)
            identity = page.evaluate("async()=>(await fetch('/api/profile/me')).json()")
            assert identity['user_id'] == leases[frequency]['user_id'] and identity['visiting']
            return context, page

        monkeypatch.setattr(recording, 'contributor', contributor)
        try:
            recording.test_two_peers_mix_controls_separate_durable_stems_and_original_server_export(
                studio, production_browser, production_server, tmp_path)
        except Exception:
            # When the test reports that #recordStop is disabled, don't guess
            # whether setControls is wrong. Capture the actual recorder and
            # finalization state, user-visible errors, and the recent event log.
            # Never print authentication tokens or participant profile data.
            page, _ = studio
            try:
                snapshot = page.evaluate("""() => ({
                  ui: {
                    recordStopDisabled: document.querySelector('#recordStop')?.disabled,
                    recordDisabled: document.querySelector('#record')?.disabled,
                    recordStopLabel: document.querySelector('#recordStop')?.textContent,
                    recBadge: document.querySelector('#recBadge')?.textContent,
                    captureStatus: document.querySelector('#captureStatus')?.textContent,
                    alert: document.querySelector('#alert')?.textContent,
                    audioStatus: document.querySelector('#participantAudioStatus')?.textContent
                  },
                  studio: window.PubCast25DStudio?.state?.(),
                  liveInputs: window.PubcastProgramAudio?.inputs?.size,
                  deskClosed: window.PubCastAudioDesk?.closed,
                  events: Array.from(document.querySelectorAll('#events > *'))
                    .slice(-20).map(x => x.textContent)
                })""")
                print("ADMITTED_GUEST_RECORDING_STATE_AT_FAILURE", snapshot, flush=True)
                print("ADMITTED_GUEST_BROWSER_ERRORS", getattr(page, "problems", []), flush=True)
            except Exception as diagnostic_error:
                print("ADMITTED_GUEST_DIAGNOSTIC_UNAVAILABLE",
                      type(diagnostic_error).__name__, str(diagnostic_error), flush=True)
            raise
