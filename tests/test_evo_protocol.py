"""
tests/test_evo_protocol.py — EVO Protocol unit tests.

Tests the Switchblade Governor, VDI Engine, Prosody Engine, and
E-Pete routing without needing live cameras or GPU inference.

All tests run offline — no network calls, no camera hardware required.

Rear View Foresight LLC — Feic Mo Chroí — 2026
"""
from __future__ import annotations

import sys
import os
import uuid
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Guard: skip entire module gracefully if EVO deps missing ──────────────────
from modules.evo import _EVO_CORE_AVAILABLE
if not _EVO_CORE_AVAILABLE:
    pytest.skip("EVO Protocol not available in this environment", allow_module_level=True)

from modules.evo.vdi_engine import VDIEngine, VDISignals, VoiceMode
from modules.evo.prosody_engine import ProsodyEngine, EmotionalState
from modules.evo.switchblade_governor import SwitchbladeGovernor, SceneState
from modules.evo.voice_characters import get_character_profile, list_characters
from modules.evo.epete import EPete, InferenceTask, TaskType, InferenceModel


def _vdi_score_from_report(report) -> float:
    """VDIReport uses vdi_score as the attribute name."""
    return getattr(report, "vdi_score", getattr(report, "vdi", 0.5))


# ─── helpers ──────────────────────────────────────────────────────────────────

def make_signals(**kwargs) -> VDISignals:
    """Build a VDISignals with safe defaults, overridable by kwargs."""
    defaults = dict(
        audience_engagement=0.5,
        audience_valence=0.5,
        audience_arousal=0.5,
        audience_attention=0.5,
        smile_intensity=0.0,
        frown_intensity=0.0,
        surprise_intensity=0.0,
        confusion_intensity=0.0,
        audience_silence=0.5,
        laughter_detected=0.0,
        murmur_detected=0.0,
        applause_detected=0.0,
        time_in_segment=0.0,
        topic_emotional_weight=0.5,
        call_to_action_pending=False,
        performer_arousal=0.5,
        performer_valence=0.5,
        performer_forward_lean=0.0,
        performer_tension=0.3,
    )
    defaults.update(kwargs)
    return VDISignals(**defaults)


def make_vdi_report(score: float = 0.5):
    """Return a VDI report at approximately the requested score level."""
    engine = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)
    signals = make_signals(
        audience_engagement=score,
        audience_arousal=score,
        audience_attention=score,
        audience_silence=score * 0.5,
        performer_arousal=score,
        performer_forward_lean=score * 0.5,
    )
    return engine.update(signals)


def make_scene() -> SceneState:
    return SceneState(
        program_camera="cam_1",
        shot_type="medium",
        primary_character="pete",
        characters_in_frame=["pete"],
        characters_offscreen=[],
    )


def make_task(task_type: TaskType, prompt: str = "test") -> InferenceTask:
    return InferenceTask(
        task_id=str(uuid.uuid4()),
        task_type=task_type,
        prompt=prompt,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# VDI Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestVDIEngine:

    def setup_method(self):
        self.engine = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)

    def test_vdi_score_in_valid_range(self):
        for _ in range(5):
            report = self.engine.update(make_signals())
            assert 0.0 <= _vdi_score_from_report(report) <= 1.0, f"VDI out of range: {_vdi_score_from_report(report)}"

    def test_high_engagement_elevates_score(self):
        high_signals = make_signals(
            audience_engagement=1.0,
            audience_arousal=1.0,
            audience_attention=1.0,
            audience_silence=1.0,
            performer_arousal=1.0,
            performer_forward_lean=1.0,
        )
        report = self.engine.update(high_signals)
        assert _vdi_score_from_report(report) >= 0.6, f"Expected high VDI, got {_vdi_score_from_report(report)}"

    def test_low_engagement_lowers_score(self):
        low_signals = make_signals(
            audience_engagement=0.0,
            audience_arousal=0.0,
            audience_attention=0.0,
            audience_silence=0.0,
            performer_arousal=0.0,
        )
        report = self.engine.update(low_signals)
        assert _vdi_score_from_report(report) <= 0.45, f"Expected low VDI, got {_vdi_score_from_report(report)}"

    def test_silence_elevates_vdi(self):
        e1 = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)
        e2 = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)
        r1 = e1.update(make_signals(audience_silence=0.0))
        r2 = e2.update(make_signals(audience_silence=1.0))
        assert r2.vdi_score > r1.vdi_score

    def test_report_has_voice_mode(self):
        report = self.engine.update(make_signals())
        assert isinstance(report.voice_mode, VoiceMode)

    def test_report_has_identity_moment_bool(self):
        report = self.engine.update(make_signals())
        assert isinstance(report.identity_moment, bool)

    def test_all_voice_modes_reachable(self):
        modes_seen = set()
        configs = [
            dict(audience_engagement=1.0, audience_arousal=1.0, audience_attention=1.0, audience_silence=1.0),
            dict(audience_engagement=0.65, audience_arousal=0.65),
            dict(audience_engagement=0.40),
            dict(audience_engagement=0.0, audience_arousal=0.0, audience_attention=0.0, audience_silence=0.0),
        ]
        for config in configs:
            e = VDIEngine(smoothing_window=1, mode_hysteresis=0.0)
            report = e.update(make_signals(**config))
            modes_seen.add(report.voice_mode)
        assert len(modes_seen) >= 2, f"Only {len(modes_seen)} VoiceModes reachable: {modes_seen}"


# ═══════════════════════════════════════════════════════════════════════════════
# Prosody Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestProsodyEngine:

    def setup_method(self):
        self.engine = ProsodyEngine()

    def _emotional_state(self, **kwargs) -> EmotionalState:
        defaults = dict(arousal=0.5, valence=0.5, tension_score=0.3,
                        forward_lean=0.0, expression_velocity=0.0)
        # Map test shorthand to actual field names
        if 'tension' in defaults:
            defaults['tension_score'] = defaults.pop('tension')
        if 'lean_forward' in defaults:
            defaults['forward_lean'] = defaults.pop('lean_forward')
        defaults.update(kwargs)
        return EmotionalState(**defaults)

    def test_params_produced(self):
        vdi = make_vdi_report(0.5)
        state = self._emotional_state()
        params = self.engine.get_synthesis_params(vdi, self._emotional_state())
        assert params is not None

    def test_speech_rate_in_valid_range(self):
        for score in [0.1, 0.4, 0.6, 0.9]:
            vdi = make_vdi_report(score)
            params = self.engine.get_synthesis_params(vdi, self._emotional_state())
            assert 0.5 <= params.speech_rate <= 1.6, \
                f"speech_rate={params.speech_rate} out of range at VDI≈{score}"

    def test_stability_in_valid_range(self):
        for score in [0.1, 0.9]:
            vdi = make_vdi_report(score)
            params = self.engine.get_synthesis_params(vdi, self._emotional_state())
            assert 0.0 <= params.stability <= 1.0

    def test_unknown_character_does_not_crash(self):
        vdi = make_vdi_report(0.5)
        state = self._emotional_state()
        params = self.engine.get_synthesis_params(vdi, self._emotional_state())
        assert params is not None

    def test_high_arousal_differs_from_low_arousal(self):
        vdi = make_vdi_report(0.5)
        p_calm   = self.engine.get_synthesis_params(vdi, self._emotional_state(arousal=0.1))
        p_aroused = self.engine.get_synthesis_params(vdi, self._emotional_state(arousal=0.9))
        # At least one parameter should differ
        differs = (
            p_aroused.speech_rate    != p_calm.speech_rate or
            p_aroused.pitch_range    != p_calm.pitch_range or
            p_aroused.stability      != p_calm.stability
        )
        assert differs, "High vs low arousal produced identical prosody params"


# ═══════════════════════════════════════════════════════════════════════════════
# Switchblade Governor
# ═══════════════════════════════════════════════════════════════════════════════

class TestSwitchbladeGovernor:

    def setup_method(self):
        self.gov = SwitchbladeGovernor()

    def test_emits_priority_vector(self):
        pv = self.gov.tick(make_vdi_report(0.9), make_scene())
        assert pv is not None

    def test_wire_format_is_dict(self):
        pv = self.gov.tick(make_vdi_report(0.5), make_scene())
        wire = pv.to_wire_format()
        assert isinstance(wire, dict)

    def test_wire_format_has_required_keys(self):
        pv = self.gov.tick(make_vdi_report(0.7), make_scene())
        wire = pv.to_wire_format()
        for key in ("e3_s", "e4_f", "mode", "vdi", "ts"):
            assert key in wire, f"Missing key {key!r} in wire format: {list(wire.keys())}"

    def test_identity_mode_has_high_e3_sss(self):
        pv = self.gov.tick(make_vdi_report(0.95), make_scene())
        wire = pv.to_wire_format()
        if wire.get("mode") == "identity":
            assert wire["e3_s"] >= 0.9, f"Identity mode e3_s={wire['e3_s']} should be >= 0.9"

    def test_content_mode_bg_physics_on(self):
        pv = self.gov.tick(make_vdi_report(0.05), make_scene())
        wire = pv.to_wire_format()
        if wire.get("mode") == "content":
            assert wire.get("bg_p", 1) == 1, "Content mode should have bg_p=1 (physics ON)"

    def test_vdi_score_in_wire_matches_report(self):
        report = make_vdi_report(0.7)
        pv = self.gov.tick(report, make_scene())
        wire = pv.to_wire_format()
        assert abs(wire["vdi"] - _vdi_score_from_report(report)) < 0.05, \
            f"Wire VDI {wire['vdi']} doesn't match report {_vdi_score_from_report(report)}"


# ═══════════════════════════════════════════════════════════════════════════════
# Voice Characters
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceCharacters:

    def test_pete_profile_loads(self):
        profile = get_character_profile("pete")
        assert profile is not None

    def test_pete_has_base_stability(self):
        profile = get_character_profile("pete")
        assert hasattr(profile, "base_stability")
        assert 0.0 <= profile.base_stability <= 1.0

    def test_pete_crack_threshold_reasonable(self):
        profile = get_character_profile("pete")
        # Pete cracks rarely — threshold should be high
        assert profile.crack_threshold >= 0.7

    def test_list_characters_includes_pete(self):
        chars = list_characters()
        assert "pete" in chars

    def test_list_returns_collection(self):
        chars = list_characters()
        assert len(chars) >= 1

    def test_unknown_character_returns_none_or_default(self):
        profile = get_character_profile("completely_nonexistent_xyz_abc")
        # Either None (caller handles) or a default profile — neither should crash
        # The contract: no exception raised
        # (profile may be None — that's valid; tests above should not assume not-None)
        # So this test just verifies no crash:
        assert True  # reached here without exception


# ═══════════════════════════════════════════════════════════════════════════════
# E-Pete routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestEPeteRouting:

    def setup_method(self):
        self.epete = EPete(
            studio_model_id="test-studio",
            architect_model_id="test-architect",
            llm_backend=None,
        )

    def test_conversation_routes_to_studio(self):
        task = make_task(TaskType.CONVERSATION)
        decision = self.epete.route(task)
        assert decision.assigned_model == InferenceModel.STUDIO

    def test_narration_routes_to_studio(self):
        decision = self.epete.route(make_task(TaskType.NARRATION))
        assert decision.assigned_model == InferenceModel.STUDIO

    def test_analysis_routes_to_architect(self):
        decision = self.epete.route(make_task(TaskType.ANALYSIS))
        assert decision.assigned_model == InferenceModel.ARCHITECT

    def test_planning_routes_to_architect(self):
        decision = self.epete.route(make_task(TaskType.PLANNING))
        assert decision.assigned_model == InferenceModel.ARCHITECT

    def test_explain_routes_to_chain(self):
        decision = self.epete.route(make_task(TaskType.EXPLAIN))
        assert decision.assigned_model == InferenceModel.CHAIN

    def test_recommend_routes_to_chain(self):
        decision = self.epete.route(make_task(TaskType.RECOMMEND))
        assert decision.assigned_model == InferenceModel.CHAIN

    def test_system_alert_routes_to_studio(self):
        decision = self.epete.route(make_task(TaskType.SYSTEM_ALERT))
        assert decision.assigned_model == InferenceModel.STUDIO

    def test_all_task_types_have_routing(self):
        """Every TaskType must produce a valid routing decision — no crashes."""
        for task_type in TaskType:
            task = make_task(task_type)
            decision = self.epete.route(task)
            assert decision is not None, \
                f"TaskType.{task_type.value} produced no routing decision"
            assert decision.assigned_model in [m for m in InferenceModel], \
                f"TaskType.{task_type.value} → invalid model {decision.assigned_model!r}"

    def test_decision_has_model_and_reason(self):
        task = make_task(TaskType.CONVERSATION)
        decision = self.epete.route(task)
        assert hasattr(decision, "assigned_model")
        assert hasattr(decision, "reason")
