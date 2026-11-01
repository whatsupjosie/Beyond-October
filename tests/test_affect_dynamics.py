from modules.affect_dynamics import AffectDynamics, AffectDynamicsProfile, AffectEvidence


class Clock:
    def __init__(self): self.t = 100.0
    def __call__(self): return self.t
    def advance(self, seconds): self.t += seconds


def ev(i, **kw):
    base = dict(event_id=f"e{i}", timestamp=100+i, confidence=.9,
                baseline_quality=.9, state="steady", arousal=0., valence=0.,
                load=0., tension=.1, dramatic_intensity=.1, stakes=.1,
                novelty=.1, revision=False)
    base.update(kw)
    return AffectEvidence(**base)


def test_time_never_manufactures_grounding():
    c=Clock(); d=AffectDynamics(clock=c)
    d.observe(ev(1, confidence=.25, baseline_quality=.3, novelty=.9, stakes=.9))
    before=d.output(); c.advance(120); after=d.tick()
    assert after.grounding == before.grounding
    assert after.uncertainty == before.uncertainty


def test_consequential_change_orients_and_braces_without_teleporting_display():
    c=Clock(); d=AffectDynamics(clock=c)
    d.observe(ev(1)); c.advance(5); d.tick()
    out=d.observe(ev(2, arousal=2.4, valence=-2.2, load=2.0,
                     tension=.9, dramatic_intensity=.95, stakes=.95, novelty=.95))
    assert out.orienting > 0
    assert out.bracing > 0
    assert out.display["intensity"] < .5
    assert out.director_signals["active_trajectory"] is True


def test_retargeting_starts_from_current_display_not_new_target():
    c=Clock(); d=AffectDynamics(clock=c)
    d.observe(ev(1, dramatic_intensity=.9, tension=.8, stakes=.8))
    c.advance(8); a=d.tick().display["intensity"]
    d.observe(ev(2, dramatic_intensity=.05, tension=.1, stakes=.1,
                 valence=1.8, arousal=-1.0))
    b=d.output().display["intensity"]
    assert b == a
    c.advance(2); cval=d.tick().display["intensity"]
    assert 0 <= cval <= 1


def test_profile_changes_expression_without_changing_evidence():
    c1=Clock(); c2=Clock()
    closed=AffectDynamics(AffectDynamicsProfile(emotional_openness=.15, suppression_tendency=.85), clock=c1)
    open_=AffectDynamics(AffectDynamicsProfile(emotional_openness=.95, suppression_tendency=.05), clock=c2)
    e=ev(1, dramatic_intensity=.9, tension=.8, stakes=.7, arousal=1.8)
    closed.observe(e); open_.observe(e); c1.advance(20); c2.advance(20)
    assert open_.tick().display["intensity"] > closed.tick().display["intensity"]


def test_output_is_advisory_not_camera_or_conversation_authority():
    c=Clock(); d=AffectDynamics(clock=c); out=d.observe(ev(1)).to_dict()
    assert "camera_id" not in out and "take" not in out
    assert "action" not in out["conversation_signals"]
    assert "performance_potential" in out["director_signals"]


def test_low_trust_novelty_cannot_create_maximum_bracing():
    c=Clock(); d=AffectDynamics(clock=c)
    d.observe(ev(1, confidence=.1, baseline_quality=.1, novelty=1, stakes=1,
                 arousal=2.5, valence=-2.5, load=2.5))
    assert d.output().bracing < .35


def test_eq_recorder_has_separate_dynamics_stream(tmp_path):
    import json
    from modules.eq_monitoring_recorder import EQMonitoringRecorder
    rec = EQMonitoringRecorder(tmp_path, build_id="affect-dynamics-test")
    rec.record_affect_dynamics("room", user_id="u", message_id="m", dynamics={"schema": "pubcast.affect.dynamics.v1", "bracing": .2})
    path = tmp_path / "blackbox/dev/EQ/sessions/room/affect_dynamics.jsonl"
    row = json.loads(path.read_text())
    assert row["dynamics"]["schema"] == "pubcast.affect.dynamics.v1"
    assert row["dynamics"]["bracing"] == .2
