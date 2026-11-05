"""Independent home/host stores, real signatures, replay fences and durable approval."""
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.credentials import CredentialStore
from modules.governance import GovernanceEngine
from modules.guest_identity import GuestAdmission, sign_visit


CONSENTS = dict(tos=True, recording=True, ai_disclosure=True, data_processing=True)


def profile(uid='u_1234567890abcdef1234'):
    return {'user_id': uid, 'username': 'visiting-person', 'display_name': 'A visitor',
            'details': {'discoverable': True, 'public_fields': ['pronouns'],
                        'about': {'pronouns': 'they/them', 'city': 'Private city'}}}


@pytest.fixture
def rig(tmp_path):
    host = GuestAdmission(GovernanceEngine(tmp_path/'host'))
    home = CredentialStore(tmp_path/'home')
    code = host.invite()
    challenge = host.challenge(code, 'http://host.example:8000')
    proof = sign_visit(home, profile(), challenge['challenge'], CONSENTS)
    return host, home, challenge, proof


def claims(host, entry, uid=None):
    return {'sub': uid or profile()['user_id'], 'role': 'guest', 'guest_host': host.host_id, 'guest_entry': entry}


def test_own_identity_only_shared_card_and_owner_admission_survive_restart(rig, tmp_path):
    host, home, challenge, proof = rig
    assert proof['payload']['card']['details']['about'] == {'pronouns': 'they/them'}
    entry = host.submit(proof)
    assert host.submit(proof) == entry  # Retry a lost HTTP response without another invite use.
    assert host.status(challenge['poll_token'])['status'] == 'waiting'
    assert not host.validate_claims(claims(host, entry))
    host.governance.approve_entry(entry, 'owner')
    accepted = host.status(challenge['poll_token'])
    assert accepted['card']['user_id'] == profile()['user_id']
    assert host.validate_claims(claims(host, entry))
    restarted = GuestAdmission(GovernanceEngine(tmp_path/'host'))
    assert restarted.host_id == host.host_id
    assert restarted.validate_claims(claims(host, entry))
    code = restarted.invite()
    fresh = restarted.challenge(code, 'http://host.example:8000')
    again = sign_visit(CredentialStore(tmp_path/'home'), profile(), fresh['challenge'], CONSENTS)
    assert again['payload']['card']['public_key'] == proof['payload']['card']['public_key']
    assert restarted.submit(again) != entry
    restarted.revoke(entry)
    assert not host.validate_claims(claims(host, entry))
    assert host.status(challenge['poll_token'])['status'] == 'expired'


def test_tamper_wrong_host_missing_consent_and_replay_are_refused(rig, tmp_path):
    host, home, challenge, proof = rig
    tampered = copy.deepcopy(proof)
    tampered['payload']['card']['display_name'] = 'Impersonator'
    with pytest.raises(ValueError, match='signature'):
        host.submit(tampered)
    other = GuestAdmission(GovernanceEngine(tmp_path/'another-host'))
    with pytest.raises(ValueError, match='challenge'):
        other.submit(proof)
    no_consent = sign_visit(home, profile(), challenge['challenge'], {**CONSENTS, 'recording': False})
    with pytest.raises(ValueError, match='consents'):
        host.submit(no_consent)
    with pytest.raises(ValueError, match='local account'):
        host.submit(proof, [profile()['user_id']])
    host.submit(proof)
    different = sign_visit(home, {**profile(), 'display_name': 'Different request'}, challenge['challenge'], CONSENTS)
    with pytest.raises(ValueError, match='already been used'):
        host.submit(different)
    with pytest.raises(ValueError):
        host.status('wrong-ticket')


def test_returning_id_cannot_change_key_or_escalate_role(rig, tmp_path):
    host, home, challenge, proof = rig
    entry = host.submit(proof)
    host.governance.approve_entry(entry, 'owner')
    host.status(challenge['poll_token'])
    new = host.challenge(host.invite(), 'http://host.example:8000')
    attacker = sign_visit(CredentialStore(tmp_path/'attacker'), profile(), new['challenge'], CONSENTS)
    with pytest.raises(ValueError, match='different identity key'):
        host.submit(attacker)
    assert not host.validate_claims({**claims(host, entry), 'role': 'owner'})
    assert not host.validate_claims(claims(host, entry, 'u_00000000000000000000'))
    assert not host.validate_claims({**claims(host, entry), 'guest_host': '0'*32})
    host.governance.ban_user(profile()['user_id'], 'test ban', 'owner')
    assert not host.validate_claims(claims(host, entry))


def test_invite_use_is_atomic_between_workers_and_unlock_still_needs_valid_proof(tmp_path):
    host = GuestAdmission(GovernanceEngine(tmp_path/'host'))
    host.set_locked(False)
    code = host.invite()
    proofs = []
    challenges = []
    for index in range(2):
        challenge = host.challenge(code, 'http://host.example')
        challenges.append(challenge)
        proofs.append(sign_visit(CredentialStore(tmp_path/f'home-{index}'),
                                 profile('u_' + str(index)*20), challenge['challenge'], CONSENTS))
    def submit(index):
        worker = GuestAdmission(GovernanceEngine(tmp_path/'host'))
        try:
            return worker.submit(proofs[index])
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sum(result is not None for result in results) == 1
    winner = next(index for index, result in enumerate(results) if result)
    assert host.status(challenges[winner]['poll_token'])['status'] == 'approved'
    assert len(host.governance.list_waiting()) == 0


def test_challenge_and_admitted_lease_expiry_are_enforced(rig):
    host, home, challenge, proof = rig
    with host.connect() as db:
        db.execute('UPDATE guest_challenges SET expires=0')
    with pytest.raises(ValueError, match='expired'):
        host.submit(proof)
    fresh = host.challenge(host.invite(), 'http://host.example')
    entry = host.submit(sign_visit(home, profile(), fresh['challenge'], CONSENTS))
    host.governance.approve_entry(entry, 'owner')
    host.status(fresh['poll_token'])
    with host.connect() as db:
        db.execute('UPDATE guest_sessions SET expires=0 WHERE entry_id=?', (entry,))
    assert not host.validate_claims(claims(host, entry))
    assert host.status(fresh['poll_token'])['status'] == 'expired'
