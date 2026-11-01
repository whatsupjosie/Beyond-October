import asyncio
import signal
import subprocess
import pytest
from modules.turn_serialization import serialized_turn
from modules.pubpartner_voice import AlexPersonalizationEngine
from modules.provider_neutralizer import ProviderNeutralizer
import run_smollm


@pytest.mark.asyncio
async def test_same_owner_session_serialized_but_others_independent():
    class Worker:
        active={}
        maximum={}
        @serialized_turn
        async def run(self, *, user_id, session_id, fail=False):
            key=(user_id,session_id)
            self.active[key]=self.active.get(key,0)+1
            self.maximum[key]=max(self.active[key],self.maximum.get(key,0))
            try:
                await asyncio.sleep(.005)
                if fail: raise ValueError('expected')
            finally:self.active[key]-=1
    w=Worker()
    await asyncio.gather(*(w.run(user_id='a',session_id='s') for _ in range(8)), w.run(user_id='b',session_id='s'))
    assert w.maximum=={('a','s'):1,('b','s'):1}
    with pytest.raises(ValueError):await w.run(user_id='a',session_id='s',fail=True)
    await w.run(user_id='a',session_id='s')
    assert not w._live_turn_locks


def test_voice_cleanup_does_not_remove_sentence_subject():
    engine=AlexPersonalizationEngine()
    for text in ["I'd be happy to greet you.","I would be happy to explain.","As an AI, I cannot verify that."]:
        assert engine._strip_boilerplate_prefix(text)==text
    assert engine._strip_boilerplate_prefix('Sure,')=='Sure,'
    assert ProviderNeutralizer().neutralize('Sure,',provider='openai_compatible').neutral_response=='Sure,'
    phrase="I'd be happy to help solve the problem."
    assert ProviderNeutralizer().neutralize(phrase,provider='openai_compatible').neutral_response==phrase


def test_bad_model_checksum_stops_before_launch(tmp_path, monkeypatch):
    # verify_model now takes the file and the registry checksum (model swap layer).
    model=tmp_path/'bad.gguf';model.write_bytes(b'corrupted')
    registered=run_smollm.get_model('smollm2').sha256
    with pytest.raises(RuntimeError,match='checksum'):run_smollm.verify_model(model,registered)


def test_stop_escalates_only_when_graceful_shutdown_times_out():
    class Process:
        calls=[]
        def poll(self):return None
        def send_signal(self,s):self.calls.append('signal')
        def wait(self,timeout):
            self.calls.append('wait')
            if len(self.calls)==2:raise subprocess.TimeoutExpired('test',timeout)
            return 0
        def terminate(self):self.calls.append('terminate')
    p=Process();run_smollm.stop(p)
    assert p.calls==['signal','wait','terminate','wait']


def test_personalization_preserves_meaningful_uncertainty():
    engine=AlexPersonalizationEngine()
    raw="In general, this works, but I cannot guarantee it."
    result=engine.restore(raw_response=raw,provider={"p":"openai_compatible"})
    assert result.friend_response==raw


def test_first_integration_data_is_not_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(run_smollm,'ROOT',tmp_path)
    assert run_smollm.default_data_dir()==tmp_path/'reach_userdata'
    secret=tmp_path/'data'/'secure'/'jwt_secret.txt'
    secret.parent.mkdir(parents=True);secret.write_text('test')
    assert run_smollm.default_data_dir()==tmp_path/'data'
