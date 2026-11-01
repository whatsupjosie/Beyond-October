from __future__ import annotations

import pytest

from modules.pubpartner_rephrase import (
    AlexRephrasingEngine,
    check_fidelity,
    protect_for_model,
    resolve_mode,
    restore_from_model,
)

VOICE = "You are Alex. Warm, direct, ellipses, endearments in normal mode."
RAW = "Certainly, the deadline is March 14 and the fee is $65. Hope this helps!"


def engine(reply):
    calls = []

    def gen(system, user):
        calls.append((system, user))
        return reply(len(calls)) if callable(reply) else reply

    return AlexRephrasingEngine(gen), calls


def test_no_generator_matches_parent_behavior():
    result = AlexRephrasingEngine().restore(RAW, voice_prompt=VOICE)
    assert result.friend_response == "the deadline is March 14 and the fee is $65."
    assert result.provider_neutralization["alex_rephrase"]["skipped_reason"] == "no_generator_configured"


def test_faithful_rewrite_is_accepted_and_receipted():
    eng, calls = engine("Josie... the deadline is March 14, and the fee is $65, sweetheart.")
    result = eng.restore(RAW, voice_prompt=VOICE)
    assert result.friend_response.startswith("Josie...")
    assert result.change_level == "voice_rewrite" and "alex_voice_rewrite" in result.applied
    assert "REWRITE MODE" in calls[0][0] and VOICE in calls[0][0]
    assert calls[0][1] == "the deadline is March 14 and the fee is $65."  # model saw neutral text, not provider voice


def test_invented_number_is_rejected_then_falls_back_to_neutral():
    eng, calls = engine("Josie... the deadline is March 15, and the fee is $65.")
    result = eng.restore(RAW, voice_prompt=VOICE)
    assert result.friend_response == "the deadline is March 14 and the fee is $65."
    assert len(calls) == 2 and "numbers_changed" in calls[1][1]
    receipt = result.provider_neutralization["alex_rephrase"]
    assert receipt["fallback_to_neutral"] and not receipt["accepted"]


def test_retry_can_succeed():
    eng, _ = engine(lambda n: "the deadline is March 15 and the fee is $65." if n == 1 else "Josie... the deadline is March 14, fee $65.")
    result = eng.restore(RAW, voice_prompt=VOICE)
    assert result.change_level == "voice_rewrite"
    assert result.provider_neutralization["alex_rephrase"]["attempts"] == 2


def test_code_fence_never_reaches_model_and_comes_back_exact():
    raw = "Run this:\n```\nrm -rf build/\n```\nThen restart."
    seen = {}

    def gen(system, user):
        seen["user"] = user
        return "Josie... run this:\n" + user.split("\n")[1] + "\nthen restart it."

    result = AlexRephrasingEngine(gen).restore(raw, voice_prompt=VOICE)
    assert "rm -rf" not in seen["user"]
    assert "```\nrm -rf build/\n```" in result.friend_response


def test_exact_source_material_is_not_rewritten():
    eng, calls = engine("anything")
    result = eng.restore("Quote: I'm not here to be strictly placated to.", voice_prompt=VOICE)
    assert not calls and "I'm not here to be strictly placated to." in result.friend_response
    assert result.provider_neutralization["alex_rephrase"]["skipped_reason"] == "exact_source_material_not_rewritten"
    eng2, calls2 = engine("anything")
    eng2.restore("hello there friend", voice_prompt=VOICE, source_policy={"immutable": True})
    assert not calls2


def test_generator_error_never_breaks_the_turn():
    def boom(system, user):
        raise RuntimeError("model down")

    result = AlexRephrasingEngine(boom).restore(RAW, voice_prompt=VOICE)
    assert result.friend_response == "the deadline is March 14 and the fee is $65."
    assert result.provider_neutralization["alex_rephrase"]["fallback_to_neutral"]


def test_missing_voice_prompt_skips_rather_than_guesses():
    eng, calls = engine("x")
    result = eng.restore(RAW)
    assert not calls and result.provider_neutralization["alex_rephrase"]["skipped_reason"] == "no_voice_prompt_supplied"


def test_prompt_can_come_from_alex_packet():
    eng, calls = engine("Josie... the deadline is March 14 and the fee is $65.")
    eng.restore(RAW, alex_packet={"prompt_text": "PACKET VOICE"})
    assert "PACKET VOICE" in calls[0][0]


def test_professional_mode_rejects_endearments_and_ellipses():
    src = "the filing is due Friday."
    assert "endearment_in_formal_mode" in check_fidelity(src, "Sweetheart, the filing is due Friday.", mode="professional")
    assert "ellipsis_in_formal_mode" in check_fidelity(src, "The filing is due... Friday.", mode="professional")
    assert check_fidelity(src, "The filing is due Friday, Josie.", mode="professional") == []


def test_private_modes_need_explicit_private_session_and_never_broadcast():
    assert resolve_mode("baby", explicit_private=False, private_session=True, broadcast=False)[0] == "normal"
    assert resolve_mode("madeline", explicit_private=True, private_session=False, broadcast=False)[0] == "normal"
    assert resolve_mode("nanny", explicit_private=True, private_session=True, broadcast=True)[0] == "normal"
    assert resolve_mode("baby", explicit_private=True, private_session=True, broadcast=False)[0] == "baby"
    assert resolve_mode("bogus", explicit_private=False, private_session=True, broadcast=False)[0] == "normal"


def test_baby_talk_outside_baby_mode_rejected():
    assert "baby_talk_outside_baby_mode" in check_fidelity("it is done.", "it is wittle done.", mode="normal")


def test_invented_name_link_autobiography_and_length_rejected():
    src = "send the file to the clerk."
    assert any(f.startswith("new_names") for f in check_fidelity(src, "Josie... send the file to the clerk, Marcus.", mode="normal"))
    assert "links_or_paths_changed" in check_fidelity(src, "send the file to the clerk at https://x.example/a.", mode="normal")
    assert "invented_autobiography" in check_fidelity(src, "When I was a kid I sent files to the clerk.", mode="normal")
    assert "false_reassurance" in check_fidelity(src, "send it, everything will be fine.", mode="normal")
    long_src = " ".join(["word"] * 40)
    assert "too_long" in check_fidelity(long_src, " ".join(["word"] * 80), mode="normal")
    assert "dropped_content" in check_fidelity(long_src, " ".join(["word"] * 10), mode="normal")


def test_quoted_text_must_survive():
    src = 'she wrote "I want the whole thing as written" in the note.'
    assert "quoted_text_altered" in check_fidelity(src, "she wrote that she wants the whole thing in the note.", mode="normal")


def test_protect_roundtrip():
    text = "a\n```x = 1```\nb\n```y = 2```"
    masked, blocks = protect_for_model(text)
    assert "x = 1" not in masked and restore_from_model(masked, blocks) == text


@pytest.mark.asyncio
async def test_async_wrapper():
    eng, _ = engine("Josie... the deadline is March 14 and the fee is $65.")
    result = await eng.arestore(RAW, voice_prompt=VOICE)
    assert result.change_level == "voice_rewrite"
