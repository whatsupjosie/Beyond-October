import pytest
from modules.limited_exposure import (
    DataClass, ExposurePurpose, LimitedCategory, label_for_audience,
)
from modules.security_authority import (
    ClassifiedAccessDenied, OwnerAcknowledgement, OwnerAcknowledgementRequired,
    PrincipalRole, ProtectedResource, SecurityGate, SecurityOperation,
    SecurityPrincipal, delegated_host,
)


def resource():
    label = label_for_audience(
        participant_ids={"alice", "bob"}, restricted=True,
        subject_id="alice", origin_event_id="evt-1",
    )
    return ProtectedResource("r1", "instance-a", "owner-1", label)


def test_private_conversation_is_limited_by_construction():
    label = label_for_audience(participant_ids={"alice", "bob"}, restricted=True)
    assert label.classification is DataClass.LIMITED
    assert label.policy.allowed_consumers == frozenset({"alice", "bob"})


def test_public_conversation_not_forced_limited():
    assert not label_for_audience(participant_ids={"alice"}, restricted=False).limited


def test_owner_requires_warning_ack_before_payload_release():
    events=[]
    gate=SecurityGate(events.append)
    owner=SecurityPrincipal("owner-1", PrincipalRole.OWNER, "instance-a")
    with pytest.raises(OwnerAcknowledgementRequired):
        gate.release("secret", principal=owner, resource=resource(),
                     operation=SecurityOperation.READ, purpose=ExposurePurpose.CONTEXT_RETRIEVAL)
    assert events[-1]["outcome"] == "WARNING_REQUIRED"
    assert "secret" not in str(events[-1])


def test_owner_can_retrieve_after_matching_ack_and_classification_remains():
    events=[]; gate=SecurityGate(events.append); r=resource()
    owner=SecurityPrincipal("owner-1", PrincipalRole.OWNER, "instance-a")
    ack=OwnerAcknowledgement("owner-1", "r1", SecurityOperation.READ, True)
    assert gate.release("secret", principal=owner, resource=r,
                        operation=SecurityOperation.READ,
                        purpose=ExposurePurpose.CONTEXT_RETRIEVAL,
                        acknowledgement=ack) == "secret"
    assert r.label.classification is DataClass.LIMITED
    assert events[-1]["outcome"] == "ALLOW"


def test_owner_of_different_instance_has_no_override():
    gate=SecurityGate()
    other=SecurityPrincipal("owner-2", PrincipalRole.OWNER, "instance-b")
    ack=OwnerAcknowledgement("owner-2", "r1", SecurityOperation.READ, True)
    with pytest.raises(ClassifiedAccessDenied):
        gate.release("secret", principal=other, resource=resource(),
                     operation=SecurityOperation.READ,
                     purpose=ExposurePurpose.CONTEXT_RETRIEVAL,
                     acknowledgement=ack)


def test_host_has_no_inherent_owner_override():
    events=[]; gate=SecurityGate(events.append)
    host=delegated_host(principal_id="host-1", instance_id="instance-a", operations=frozenset())
    with pytest.raises(ClassifiedAccessDenied):
        gate.release("secret", principal=host, resource=resource(),
                     operation=SecurityOperation.READ,
                     purpose=ExposurePurpose.DIRECT_CONVERSATION)
    assert events[-1]["reason"] == "host_operation_not_delegated"


def test_host_delegation_is_not_enough_without_resource_authorization():
    gate=SecurityGate()
    host=delegated_host(principal_id="host-1", instance_id="instance-a",
                        operations=frozenset({SecurityOperation.READ}))
    with pytest.raises(ClassifiedAccessDenied):
        gate.release("secret", principal=host, resource=resource(),
                     operation=SecurityOperation.READ,
                     purpose=ExposurePurpose.DIRECT_CONVERSATION)


def test_authorized_participant_can_read_private_conversation():
    gate=SecurityGate()
    alice=SecurityPrincipal("alice", PrincipalRole.PARTICIPANT, "instance-a")
    assert gate.release("hello", principal=alice, resource=resource(),
                        operation=SecurityOperation.READ,
                        purpose=ExposurePurpose.DIRECT_CONVERSATION) == "hello"


def test_uninvolved_participant_cannot_read_private_conversation():
    gate=SecurityGate()
    eve=SecurityPrincipal("eve", PrincipalRole.PARTICIPANT, "instance-a")
    with pytest.raises(ClassifiedAccessDenied):
        gate.release("hello", principal=eve, resource=resource(),
                     operation=SecurityOperation.READ,
                     purpose=ExposurePurpose.DIRECT_CONVERSATION)


def test_ack_is_bound_to_resource_and_operation():
    gate=SecurityGate(); owner=SecurityPrincipal("owner-1", PrincipalRole.OWNER, "instance-a")
    wrong=OwnerAcknowledgement("owner-1", "other", SecurityOperation.READ, True)
    with pytest.raises(OwnerAcknowledgementRequired):
        gate.release("secret", principal=owner, resource=resource(),
                     operation=SecurityOperation.READ,
                     purpose=ExposurePurpose.CONTEXT_RETRIEVAL,
                     acknowledgement=wrong)


def test_standard_data_does_not_generate_classified_security_noise():
    from modules.limited_exposure import DataLabel
    events=[]; gate=SecurityGate(events.append)
    r=ProtectedResource("ordinary", "instance-a", "owner-1", DataLabel())
    p=SecurityPrincipal("someone", PrincipalRole.PARTICIPANT, "instance-a")
    assert gate.release("ordinary", principal=p, resource=r,
                        operation=SecurityOperation.READ,
                        purpose=ExposurePurpose.DIRECT_CONVERSATION) == "ordinary"
    assert events == []
