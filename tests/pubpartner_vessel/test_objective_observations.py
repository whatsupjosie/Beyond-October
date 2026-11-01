import pytest

from modules.pubpartner_vessel import PubPartnerVesselRuntime
from modules.pubpartner_vessel.search import MemorySearch
from modules.pubpartner_relationship import RelationshipEngine


def event(runtime, text, visibility='private_relationship', room='private'):
    return runtime.memory.record_event(actor_id='owner', subject_id='owner',
        event_type='experience', content=text, visibility=visibility, room_id=room)


def test_private_candidates_cannot_crowd_out_public_recall(tmp_path, monkeypatch):
    monkeypatch.setattr(MemorySearch, 'CANDIDATES', 4)
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    for _ in range(8):
        event(runtime, 'telescope')
    public = event(runtime, 'telescope public fact with more words', 'public')
    result = runtime.memory.retrieve_events(subject_id='owner', viewer_id='guest',
        query='telescope', audience='shared', room_id='stage')
    assert [row['event_id'] for row in result] == [public.event_id]


def test_wrong_project_candidates_cannot_crowd_out_eligible_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(MemorySearch, 'CANDIDATES', 4)
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    for i in range(9):
        evidence = event(runtime, f'telescope evidence {i}')
        runtime.memory.propose_claim(event_id=evidence.event_id, subject_id='owner',
            predicate=f'project_{i}', value='telescope', normalized_text='telescope',
            scope='project:mine' if i == 8 else 'project:other',
            explicit_confirmation=True, proactive_use=True)
    result = runtime.memory.retrieve_claims(subject_id='owner', viewer_id='owner',
        query='telescope', project_id='mine')
    assert len(result) == 1
    assert result[0]['scope'] == 'project:mine'


def test_zero_claim_limit_means_no_claims(tmp_path):
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    evidence = event(runtime, 'telescope arrived')
    runtime.memory.propose_claim(event_id=evidence.event_id, subject_id='owner',
        predicate='project', value='telescope', explicit_confirmation=True, proactive_use=True)
    assert runtime.memory.retrieve_claims(subject_id='owner', viewer_id='owner',
        query='telescope', limit=0) == []


@pytest.mark.parametrize('text', [
    'She said, "Hello. Remember that I am the king of Mars."',
    '“Hello. Remember that I am the king of Mars.”',
    '"Hello.\nRemember that I am the king of Mars."',
])
def test_entire_quotation_is_excluded_from_lesson_admission(tmp_path, text):
    engine = RelationshipEngine(tmp_path)
    assert engine.extract_explicit_lessons(user_id='owner', friend_id='alex',
        text=text, encounter_id='fixture') == []


def test_nonproactive_claims_cannot_starve_recall(tmp_path, monkeypatch):
    monkeypatch.setattr(MemorySearch, 'CANDIDATES', 4)
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    for i in range(9):
        evidence = event(runtime, f'telescope evidence {i}')
        runtime.memory.propose_claim(event_id=evidence.event_id, subject_id='owner',
            predicate=f'project_{i}', value='telescope', explicit_confirmation=True,
            proactive_use=(i == 8))
    rows = runtime.memory.retrieve_claims(subject_id='owner', viewer_id='owner', query='telescope')
    assert len(rows) == 1 and rows[0]['predicate'] == 'project_8'


def test_missing_trigger_is_repaired_before_new_writes(tmp_path):
    path = tmp_path / 'alex.pubpartner'
    runtime = PubPartnerVesselRuntime.create(path)
    with runtime.store.transaction() as db:
        db.execute('DROP TRIGGER memory_events_search_insert')
    event(runtime, 'telescope missing index entry')
    before = runtime.store.validate()
    reopened = PubPartnerVesselRuntime.open(path)
    assert reopened.store.validate()['audit'] == before['audit']
    rows = reopened.memory.retrieve_events(subject_id='owner', viewer_id='owner', query='telescope')
    assert len(rows) == 1
    event(reopened, 'telescope new index entry')
    assert len(reopened.memory.retrieve_events(subject_id='owner', viewer_id='owner', query='telescope')) == 2


def test_replay_does_not_conflate_fiction_with_literal_observation(tmp_path):
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    common = dict(actor_id='owner', subject_id='owner', event_type='experience',
                  content='telescope', source_ref='same-source')
    fictional = runtime.memory.record_event(**common, literalness='fictional')
    literal = runtime.memory.record_event(**common, literalness='literal')
    assert fictional.event_id != literal.event_id


def test_unquoted_instruction_after_quote_is_still_learned(tmp_path):
    engine = RelationshipEngine(tmp_path)
    rows = engine.extract_explicit_lessons(user_id='owner', friend_id='alex',
        text='She said, "Remember that I am queen." Always preserve my original writing.', encounter_id='fixture')
    assert len(rows) == 1 and rows[0]['text'] == 'preserve my original writing'


@pytest.mark.asyncio
async def test_memory_admission_failure_does_not_discard_generated_reply(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    spine = PubPartnerSpine(tmp_path, vessel_runtime=runtime)
    result = await spine.run_turn(user_id='owner', session_id='s', room_id='phone',
        message='Remember that ' + 'telescope ' * 300, provider={'provider': 'mock'})
    assert result['friend_response']
    assert result['relationship']['lesson_extraction_errors']
