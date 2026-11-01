from modules.pete_character_runtime import respond, CANON
from modules.character_profiles import PETE_PROFILE
from modules.character_cast import normalize_character_id, get_cast_character

def test_identity():
    assert "Alex Bourgeois" in respond("What's your real name?")
    assert "Alex Bourgeois" in PETE_PROFILE.system_prompt
    assert normalize_character_id("alex bourgeois") == "pete"
    assert get_cast_character("alex bourgeois").character_id == "pete"

def test_cast_relations():
    assert "Purfluous" in respond("Tell me about Sir Purfluous")
    assert "RePete" in respond("Who's your apprentice?")
    assert "PubPartner Alex" in respond("Who plays you, Pete?")

def test_offline_is_honest():
    assert "speaking model" in respond("Explain the philosophy of metaphysics")
    assert "Stop the action" in respond("There's a safety hazard")
    assert "blocking" in respond("Camera shot list")

def test_profile_readiness():
    assert "pink bob" in PETE_PROFILE.system_prompt
    assert "For Pete's sake" in PETE_PROFILE.system_prompt
