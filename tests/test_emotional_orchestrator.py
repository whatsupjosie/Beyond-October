import time
import pytest
from modules.emotional_orchestrator import EmotionSignal, EmotionalOrchestrator
from modules.affect_dynamics import AffectDynamics
from modules.limited_exposure import DataClass, DataLabel, ExposurePurpose, LimitedExposurePolicy

class Clock:
    def __init__(self): self.t=1000.0
    def __call__(self): return self.t
    def advance(self,n): self.t += n

def pub(o, source, value, *, confidence=1.0, clinical=False, room="", event="e", label=None):
    o.publish_secondary(source=source,subject_id="u",session_id="s",room_id=room,
        confidence=confidence,dimensions={"load":value},provenance=f"{source} evidence",
        clinical_hypothesis=clinical,event_id=event,data_label=label or DataLabel())

def test_system_alex_selects_evidence_instead_of_weighted_voting():
    o=EmotionalOrchestrator(clock=Clock())
    pub(o,"alex_affect",.9,confidence=.9,event="a")
    pub(o,"eq",.1,confidence=.8,event="b")
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.dimensions["load"] == .9
    assert j.selected_source["load"] == "alex_affect"
    assert j.disagreement["load"] >= .7

def test_higher_credibility_can_override_primary_without_averaging():
    o=EmotionalOrchestrator(clock=Clock())
    pub(o,"alex_affect",.9,confidence=.35,event="a")
    pub(o,"eq",.2,confidence=.95,event="b")
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.dimensions["load"] == .2 and j.selected_source["load"] == "eq"

def test_clinical_hypothesis_cannot_become_canonical_alone():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"peq",.9,clinical=True)
    j=o.adjudicate(subject_id="u",session_id="s")
    assert "load" not in j.dimensions
    assert any("withheld" in n for n in j.notes)

def test_clinical_hypothesis_can_register_disagreement_without_taking_authority():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"eq",.8,event="a"); pub(o,"peq",0,clinical=True,event="b")
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.dimensions["load"] == .8 and j.disagreement["load"] >= .7

def test_duplicate_event_retry_does_not_amplify():
    o=EmotionalOrchestrator(clock=Clock())
    for _ in range(3): pub(o,"eq",.7,event="same")
    assert len(o._signals[("u","s")]) == 1

def test_expired_signal_disappears():
    c=Clock(); o=EmotionalOrchestrator(clock=c)
    o.publish_secondary(source="eq",subject_id="u",session_id="s",confidence=1,dimensions={"load":1},provenance="x",expires_after=10)
    c.advance(11); assert "load" not in o.adjudicate(subject_id="u",session_id="s").dimensions

def test_room_scope_prevents_cross_room_leakage():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"eq",.8,room="a")
    assert "load" not in o.adjudicate(subject_id="u",session_id="s",room_id="b").dimensions

def test_session_scope_prevents_cross_session_leakage():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"eq",.8)
    assert "load" not in o.adjudicate(subject_id="u",session_id="other").dimensions

def test_unknown_source_fails_loudly():
    o=EmotionalOrchestrator()
    with pytest.raises(ValueError): pub(o,"mystery",.5)

def test_affect_dynamics_is_not_accepted_as_upstream_evidence():
    o=EmotionalOrchestrator()
    with pytest.raises(ValueError): pub(o,"affect_dynamics",.5)

def test_publish_alex_ignores_legacy_dynamics_argument():
    o=EmotionalOrchestrator(clock=Clock())
    o.publish_alex(subject_id="u",session_id="s",affect={"turn_id":"x","reading":{"confidence":.9},"affect":{"load_z":2.5}},dynamics={"bracing":1})
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.dimensions["load"] == 1 and "bracing" not in j.dimensions

def test_limited_provenance_is_redacted_in_judgment():
    o=EmotionalOrchestrator(clock=Clock())
    label=DataLabel(classification=DataClass.LIMITED, policy=LimitedExposurePolicy(
        allowed_consumers=frozenset({"system_alex"}),
        allowed_purposes=frozenset({ExposurePurpose.EMOTIONAL_ADJUDICATION}),
    ))
    pub(o,"eq",.6,label=label)
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.provenance == ("LIMITED evidence; details withheld",)
    assert j.data_class == "LIMITED"

def test_judgment_contains_no_execution_authority():
    o=EmotionalOrchestrator(); pub(o,"conversation",.5)
    d=o.adjudicate(subject_id="u",session_id="s").to_dict()
    assert "action" not in d and "camera" not in d and "authority" not in d

def test_dynamics_consumes_canonical_judgment():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"eq",.8)
    j=o.adjudicate(subject_id="u",session_id="s").to_dict()
    d=AffectDynamics().observe_judgment(j).to_dict()
    assert d["state"] == "adjudicated" and d["event_id"] == "e"

@pytest.mark.parametrize("bad", [float("nan"),float("inf"),-99,99,None,"bad"])
def test_hostile_dimension_inputs_are_bounded(bad):
    o=EmotionalOrchestrator(clock=Clock())
    o.publish_secondary(source="eq",subject_id="u",session_id="s",confidence=1,dimensions={"load":bad},provenance="x")
    value=o.adjudicate(subject_id="u",session_id="s").dimensions["load"]
    assert 0 <= value <= 1

def test_tie_break_is_deterministic_and_prefers_declared_source_priority():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"conversation",.2,event="a"); pub(o,"eq",.8,event="b")
    j=o.adjudicate(subject_id="u",session_id="s")
    assert j.selected_source["load"] == "eq"

def test_clear_session_removes_evidence():
    o=EmotionalOrchestrator(clock=Clock()); pub(o,"eq",.8); o.clear_session(subject_id="u",session_id="s")
    assert not o.adjudicate(subject_id="u",session_id="s").dimensions

def test_bridge_secondary_clinical_only_is_withheld_from_canonical_judgment(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge=AlexJeremyBridge(data_dir=tmp_path); bridge.build_entry_packet(user_id="u",session_id="s",project_id="p",room_id="r")
    snap=bridge.publish_emotional_signal(source="peq",user_id="u",session_id="s",room_id="r",dimensions={"uncertainty":.8},confidence=.9,provenance="PEQ",clinical_hypothesis=True,event_id="p1")
    assert snap["schema"] == "pubcast.system_alex.judgment.v1" and "uncertainty" not in snap["dimensions"]
    bridge.shutdown()

def test_system_alex_is_a_separate_injectable_authority():
    from modules.emotional_orchestrator import SystemAlexAdjudicator
    class Spy(SystemAlexAdjudicator):
        def __init__(self): self.called=False
        def adjudicate(self,bundle): self.called=True; return super().adjudicate(bundle)
    spy=Spy(); o=EmotionalOrchestrator(clock=Clock(), adjudicator=spy); pub(o,"eq",.5)
    o.adjudicate(subject_id="u",session_id="s")
    assert spy.called

def test_unauthorised_limited_evidence_is_withheld_from_system_alex():
    o=EmotionalOrchestrator(clock=Clock())
    label=DataLabel(classification=DataClass.LIMITED)
    pub(o,"eq",.9,label=label)
    j=o.adjudicate(subject_id="u",session_id="s")
    assert "load" not in j.dimensions
    assert any("withheld from System Alex" in n for n in j.notes)

def test_session_id_cleanup_removes_all_subject_evidence():
    o=EmotionalOrchestrator(clock=Clock())
    for subject in ("u1","u2"):
        o.publish_secondary(source="eq",subject_id=subject,session_id="s",confidence=1,dimensions={"load":.5},provenance="x")
    o.clear_session_id(session_id="s")
    assert not o._signals


def test_bridge_exposes_advisory_conversation_guidance_from_canonical_judgment(tmp_path):
    import asyncio
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    b = AlexJeremyBridge(data_dir=tmp_path)
    b.build_entry_packet(user_id="u", session_id="s", project_id="p", room_id="r")
    # A real secondary producer can disagree with Alex, but guidance must be
    # derived from the adjudicated result rather than directly from this signal.
    b.emotional_orchestrator.publish_secondary(
        source="context", subject_id="u", session_id="s", room_id="r",
        dimensions={"uncertainty": .9, "bracing": .8, "load": .7},
        confidence=.99, provenance="structured context producer", event_id="ctx-1",
    )
    packet = asyncio.run(b.process_user_turn(
        user_id="u", session_id="s", text="I am trying to work this out",
        project_id="p", room_id="r", metadata={"message_id": "m-1"},
    ))
    g = packet["system_alex_guidance"]
    assert g["schema"] == "pubcast.system_alex.conversation_guidance.v1"
    assert g["advisory_only"] is True
    assert g["judgment_schema"] == "pubcast.system_alex.judgment.v1"
    assert "allow_processing_time" in g["guidance"]
    assert "clarify_before_assuming" in g["guidance"]
    assert "rush_or_fill_silence" in g["avoid"]
    b.shutdown()


def test_limited_canonical_guidance_does_not_bypass_shared_view(tmp_path):
    import asyncio
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    from modules.limited_exposure import DataClass
    b = AlexJeremyBridge(data_dir=tmp_path)
    b.build_entry_packet(user_id="u", session_id="s", project_id="p", room_id="r")
    packet = asyncio.run(b.process_user_turn(
        user_id="u", session_id="s", text="private emotional content",
        project_id="p", room_id="r",
        metadata={"message_id":"lim-1", "data_handling":{"classification":"LIMITED", "categories":["emotional"], "allowed_consumers":["system_alex"], "allowed_purposes":["emotional_adjudication"]}},
    ))
    assert packet["data_class"] == DataClass.LIMITED.value
    # The conversation guidance is a derivative of the LIMITED judgment and
    # must remain opaque to the ordinary shared PubPartner packet.
    assert packet["system_alex_guidance"].get("details_withheld") is True
    assert "signals" not in packet["system_alex_guidance"]
    b.shutdown()
