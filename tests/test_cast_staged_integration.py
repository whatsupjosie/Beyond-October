from modules.character_cast import normalize_character_id, get_cast_character, list_cast_avatar_presets
from modules.character_profiles import get_character_profile
from modules.evo.voice_characters import get_character_profile as get_voice_profile
from modules.avatar import list_presets


def test_cast_alias_normalization():
    assert normalize_character_id("re_pete") == "repete"
    assert normalize_character_id("repeat") == "repete"
    assert normalize_character_id("sir_purfluous") == "purfluous"


def test_character_profile_aliases_resolve():
    assert get_character_profile("repete").display_name == "RePete"
    assert get_character_profile("purfluous").display_name == "Sir Purfluous"


def test_voice_profiles_cover_cast_aliases():
    assert get_voice_profile("repete").character_id == "re_pete"
    assert get_voice_profile("sir_purfluous").character_id == "sir_purfluous"
    assert get_voice_profile("purfluous").character_id == "sir_purfluous"


def test_avatar_presets_include_staged_cast_glbs():
    preset_ids = {p.preset_id for p in list_presets()}
    assert {"PETE", "REPETE", "PURFLUOUS"}.issubset(preset_ids)
    cast_presets = {p["preset_id"]: p for p in list_cast_avatar_presets()}
    assert cast_presets["PETE"]["glb_url"].endswith("pete_avatar_pubcast_v56.glb")
    assert cast_presets["REPETE"]["glb_url"].endswith("repete_v1.glb")
    assert cast_presets["PURFLUOUS"]["glb_url"].endswith("sir_purfluous_v1.glb")


def test_cast_character_specs_are_staged_not_final():
    for cid in ["pete", "repete", "purfluous"]:
        spec = get_cast_character(cid)
        assert spec.avatar_ready is True
        assert spec.ai_ready is True
        assert spec.final_lock is False
        assert spec.provisional is True
