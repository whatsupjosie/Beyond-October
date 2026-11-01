import pytest
from modules.emotional_consultation import ConsultationKind, ConsultationRequest, ConsultationResult
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.limited_exposure import DataClass, DataLabel


def request(**kw):
    base=dict(kind=ConsultationKind.PARTICIPANT_REACTION,subject_id="u",session_id="s",requester="system_alex",consultant="pubpartner_alex",question="How did that land?")
    base.update(kw); return ConsultationRequest(**base)


def test_consultation_has_correlation_id_and_bounded_children():
    root=request(max_depth=1); child=root.child(requester="pubpartner_alex",consultant="jeremy",question="Context?")
    assert child.correlation_id == root.correlation_id and child.depth == 1
    with pytest.raises(RecursionError): child.child(requester="jeremy",consultant="system_alex",question="Again?")


def test_self_consultation_rejected():
    with pytest.raises(ValueError): request(requester="same",consultant="same")


def test_consultation_is_evidence_not_authority(tmp_path):
    b=AlexJeremyBridge(data_dir=tmp_path)
    r=ConsultationResult(request(), {"load":.7}, .8, "private rationale")
    out=b.publish_consultation_result(r)
    assert out["schema"] == "pubcast.system_alex.judgment.v1"
    assert out["selected_source"]["load"] == "participant_self_report"
    assert "action" not in out and "authority" not in out


def test_limited_consultation_defaults_to_withheld(tmp_path):
    b=AlexJeremyBridge(data_dir=tmp_path)
    req=request(data_label=DataLabel(classification=DataClass.LIMITED))
    out=b.publish_consultation_result(ConsultationResult(req,{"load":.9},1.0))
    assert out["classification"] == "LIMITED" and out["details_withheld"] is True
