from pathlib import Path

from modules.ai_runtime import load_ai_runtime_config
from modules.ai_runtime_slots import build_model_slot_status, load_model_slot_status


def test_requested_alex_jeremy_model_slots_are_declared():
    status = load_model_slot_status(Path(__file__).resolve().parents[1])
    slots = status["slots"]
    assert slots["alex"]["profile"] == "ministral_3b_local"
    assert slots["alex"]["requested_model"] == "ministral 3b"
    assert slots["jeremy"]["profile"] == "gemma3_1b_q4_local"
    assert slots["jeremy"]["requested_model"] == "gemma3 1b q4 interactive"
    assert slots["background_math"]["profile"] == "gemma4_compute_q5_e2b_local"
    assert slots["background_math"]["requested_model"] == "gemma4 e2b q5 background"


def test_model_slot_status_reports_disabled_without_failing():
    config = load_ai_runtime_config(Path(__file__).resolve().parents[1])
    status = build_model_slot_status(config)
    assert status["slots"]["alex"]["available"] is True
    assert status["slots"]["jeremy"]["available"] is True
    assert status["slots"]["background_math"]["available"] is True
