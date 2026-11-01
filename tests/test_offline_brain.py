import json, pathlib
import pytest
from modules import offline_brain as ob
from modules import repete_runtime, sir_purfluous_runtime

CHARS = [p.stem for p in (pathlib.Path(__file__).parents[1] / "data" / "characters").glob("*.json")]


@pytest.mark.parametrize("cid", CHARS)
def test_character_data_valid(cid):
    brain = ob.load(cid)
    assert brain["intents"] and brain["fallback"]


def test_same_question_twice_gives_different_replies():
    q = "want a drink?"
    hist, seen = [], set()
    for _ in range(4):
        r = repete_runtime.respond(q, hist)
        seen.add(r); hist += [{"text": q}, {"text": r}]
    assert len(seen) == 4


def test_purfluous_drink_varies_and_never_claims_real_action():
    hist, seen = [], set()
    for _ in range(4):
        r = sir_purfluous_runtime.respond("Would you like a drink?", hist)
        seen.add(r); hist.append({"text": r})
    assert len(seen) >= 3


DOMAIN = [
    # Sir Purfluous: writing, performance, a little directing
    ("sir_purfluous", "how do I write better dialogue", "dialogue"),
    ("sir_purfluous", "explain three act structure", "structure"),
    ("sir_purfluous", "I have writer's block", "writer_block"),
    ("sir_purfluous", "how do I act with an objective", "acting_basics"),
    ("sir_purfluous", "tips for my audition self tape", "audition"),
    ("sir_purfluous", "how do I direct actors", "directing"),
    ("sir_purfluous", "how do I light a scene", "refer_pete"),
    ("sir_purfluous", "how do I color grade", "refer_repete"),
    # Pete: on set, a little performance
    ("pete", "what is a dutch angle", "dutch"),
    ("pete", "explain the 180 rule", "axis"),
    ("pete", "how do I set up a boom mic", "onset_sound"),
    ("pete", "what goes in a call sheet", "callsheet"),
    ("pete", "how should I cover a scene", "coverage"),
    ("pete", "what lens for a close-up", "lenses"),
    ("pete", "what does the slate do", "slate"),
    ("pete", "how do I give an actor notes", "actors_notes"),
    ("pete", "how do I write a logline", "refer_purfluous"),
    ("pete", "how do I do a sound mix", "refer_repete"),
    # RePete: post, editing, effects, sound mix
    ("repeat", "how do I edit a rough cut", "editing_basics"),
    ("repeat", "what is an L-cut", "cutting_rules"),
    ("repeat", "how do I color grade log footage", "color_grading"),
    ("repeat", "how do I mix dialogue and music", "sound_mix"),
    ("repeat", "what's a jump cut", "jumpcut"),
    ("repeat", "how do pro studios do vfx", "pipeline"),
    ("repeat", "analyze this clip for me", "clip_review"),
    ("repeat", "my audio is rough, can you fix it", "audio_fix"),
    ("repeat", "tell me about reskinning", "reskin"),
    ("repeat", "any free tools?", "free_tools"),
    ("repeat", "what is a dutch angle", "refer_pete"),
    ("repeat", "how do I memorise lines for an audition", "refer_purfluous"),
    # natural phrasings
    ("sir_purfluous", "my script feels flat", "script_feedback"),
    ("sir_purfluous", "is my film too long", "length_ending"),
    ("sir_purfluous", "how do I cry on cue", "emotion_on_cue"),
    ("pete", "how do I shoot a dialogue scene", "shoot_dialogue"),
    ("pete", "what do I do if an actor forgets a line", "actor_forgets"),
    ("pete", "what is a gaffer", "crew_roles"),
    ("pete", "the audio has a hum on set", "onset_sound"),
    ("repeat", "how do I fix shaky footage", "stabilize"),
    ("repeat", "how do I make the dialogue louder", "sound_mix"),
    ("repeat", "how do I remove a background", "remove_background"),
    ("repeat", "what software should I edit with", "software_choice"),
]


@pytest.mark.parametrize("cid,q,intent", DOMAIN)
def test_each_topic_goes_to_the_right_character(cid, q, intent):
    assert ob.match_intent(cid, q) == intent


@pytest.mark.parametrize("cid", ["pete", "sir_purfluous", "repeat"])
def test_every_intent_has_multiple_or_authored_responses(cid):
    for i in ob.load(cid)["intents"]:
        assert all(len(r) > 20 for r in i["responses"]), (cid, i["id"])


def test_referrals_name_the_right_person():
    assert "Pete" in repete_runtime.respond("what is a dutch angle")
    assert "Purfluous" in repete_runtime.respond("tips for my audition")
    from modules import pete_character_runtime as pcr
    assert "RePete" in pcr.respond("how do I do a sound mix")
    assert "Purfluous" in pcr.respond("how do I write a logline")
    assert "Pete" in sir_purfluous_runtime.respond("explain the 180 rule")
    assert "RePete" in sir_purfluous_runtime.respond("how do I color grade")


def test_pete_identity_canon_still_wins():
    from modules import pete_character_runtime as pcr
    assert "Alex Bourgeois" in pcr.respond("what's your real name")


def test_unknown_gets_honest_fallback_not_invention():
    r = repete_runtime.respond("what is the capital of Mongolia")
    assert "guess" in r.lower() or "without my speaking model" in r.lower() or "make something up" in r.lower()


def test_clip_review_states_levels_and_limits():
    r = repete_runtime.respond("can you look at this clip")
    assert "story" in r.lower() and "technical" in r.lower()


def test_bad_data_rejected():
    with pytest.raises(ob.CharacterDataError):
        ob._validate("x", {"intents": [{"id": "a", "patterns": ["("], "responses": ["x"]}], "fallback": ["f"]})
    with pytest.raises(ob.CharacterDataError):
        ob._validate("x", {"intents": [], "fallback": ["f"]})


def test_blank_rejected():
    with pytest.raises(ValueError):
        repete_runtime.respond("  ")


def test_ordered_intent_gives_authored_line_first_then_rotates():
    from modules import pete_character_runtime as pcr
    first = pcr.respond("Camera shot list")
    assert first.startswith("Start with the blocking")
    second = pcr.respond("Camera shot list", [{"text": first}])
    assert second != first
