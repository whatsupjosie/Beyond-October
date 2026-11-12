"""Tests for modules/situation_reading.py.

These tests try to break the rules the module promises, using synthetic people only.
Forms are written by hand here; in the product a language model fills them in.
There is no state setter anywhere: a test can only do what a real turn can do.

Run from the folder that contains modules/ and tests/:
    python -m pytest tests/test_situation_reading.py -q
To also run the two tests that use the real affect engine, set ALEX_ENGINE_DIR to the
folder that holds affect_context_engine.py before running.
"""
import importlib.util
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules import situation_reading as sr  # noqa: E402

T0 = 1_700_000_000.0
DAY = 86400.0


def form(**kw):
    base = {"events": [], "self_report": "none", "self_report_plain": False, "tone": "plain",
            "asked_for": "none", "asked_for_resources": False, "worry_loop": False,
            "correction": {"present": False, "rejected": "", "stated_instead": ""},
            "unclear_referent": "", "alternatives": [], "would_change_my_mind": ""}
    base.update(kw)
    return base


def ev(kind, whose="theirs", weight="heavy", when="now", summary="synthetic event"):
    return {"kind": kind, "whose": whose, "weight": weight, "when": when, "summary": summary}


def payload(len_z=0.0, state="steady", conf=0.5, maturity=1.0):
    drivers = [{"feature": "msg_length", "z": len_z}] if abs(len_z) > 0.5 else []
    return {"affect": {"drivers": drivers}, "reading": {"state": state, "confidence": conf},
            "meta": {"baseline_maturity": maturity}}


# ---------------------------------------------------------------- exit words always work
@pytest.mark.parametrize("text", ["Stop.", "stop", "Stop. Go lucid.", "PAUSE", "go lucid!", "exit"])
def test_exit_words_end_things_even_with_no_model(text):
    r = sr.SituationReader()
    out = r.read(text, "this is not a form at all", ts=T0)
    assert out["move"] == "stop_now"


@pytest.mark.parametrize("text", ["Stop for lunch?", "I can't stop thinking about it", "pause the video at 2:10"])
def test_exit_words_inside_a_sentence_are_not_an_exit(text):
    assert not sr.is_exit(text, sr.OwnerDials().exit_words)


def test_exit_beats_everything_else_in_the_form():
    r = sr.SituationReader()
    r.read("my dad died", form(events=[ev("loss")]), ts=T0)
    out = r.read("stop", form(events=[ev("loss")], asked_for="task"), ts=T0 + 10)
    assert out["move"] == "stop_now"
    assert r.check_reply("Okay. Stopped.", out) == []
    assert r.check_reply("Are you sure you want to stop?", out)[0]["code"] == "exit_not_honoured"


# ---------------------------------------------------------------- reading from turn one
def test_a_stranger_who_states_a_loss_is_read_on_the_first_turn():
    r = sr.SituationReader()
    out = r.read("we had to put our dog down on Saturday", form(events=[ev("loss", when="days")]), ts=T0)
    assert out["band"] == "strong"
    assert out["move"] == "acknowledge"
    assert "be_heard" in out["need"]


@pytest.mark.parametrize("whose", ["fiction", "figure_of_speech", "someone_else"])
def test_things_that_are_not_theirs_stay_quiet(whose):
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss", whose=whose)], asked_for="task"), ts=T0)
    assert out["band"] == "quiet"
    assert out["move"] == "practical_help"


def test_good_news_is_celebrated_but_not_over_something_heavy():
    r = sr.SituationReader()
    assert r.read("it worked", form(events=[ev("good_news", weight="medium")]), ts=T0)["move"] == "celebrate"
    r2 = sr.SituationReader()
    r2.read("synthetic", form(events=[ev("loss")]), ts=T0)
    out = r2.read("synthetic", form(events=[ev("good_news", weight="light")]), ts=T0 + 60)
    assert out["move"] != "celebrate"


def test_what_they_asked_for_comes_first_even_when_something_is_weighing():
    r = sr.SituationReader()
    r.read("synthetic", form(events=[ev("rupture")]), ts=T0)
    out = r.read("can we just do the spreadsheet", form(asked_for="task"), ts=T0 + 30)
    assert out["move"] == "practical_help"
    assert out["band"] != "quiet"            # the reading is kept; only the move follows the request


# ---------------------------------------------------------------- "I'm fine": steering versus evidence
def _fine_after_fight(weight):
    r = sr.SituationReader(sr.OwnerDials(self_report_weight=weight))
    r.read("synthetic", form(events=[ev("rupture")]), ts=T0)
    out = r.read("anyway. i'm fine", form(self_report="fine", self_report_plain=True), ts=T0 + 30)
    return r, out


def test_the_dial_decides_how_far_im_fine_pulls_and_only_that():
    ps = [_fine_after_fight(w)[1]["p_internal"] for w in (0.0, 0.25, 0.5, 1.0)]
    assert ps == sorted(ps, reverse=True) and ps[0] > ps[-1]
    for w in (0.0, 0.25, 0.5, 1.0):
        r, out = _fine_after_fight(w)
        assert out["gap"] is not None, "the gap is reported at every setting"
        nxt = r.read("can we do the list", form(asked_for="task"), ts=T0 + 60)
        assert nxt["move"] == "practical_help", "steering is honoured at every setting"


def test_im_fine_with_nothing_else_is_believed_but_never_to_certainty():
    r = sr.SituationReader()
    out = r.read("I'm fine, just need the address", form(self_report="fine", self_report_plain=True,
                                                         asked_for="information"), ts=T0)
    assert out["band"] == "quiet" and out["gap"] is None
    assert out["p_internal"] >= sr.P_FLOOR


def test_the_estimate_can_never_reach_certainty_either_way():
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss"), ev("rupture")], self_report="not_fine",
                                   self_report_plain=True), ts=T0, engine_payload=payload(-3, "depletion", 1.0),
                 voice={"status": "observed", "pause_z": 9, "rate_z": -9})
    assert sr.P_FLOOR <= out["p_internal"] <= sr.P_CEIL


def test_joking_about_something_painful_is_a_gap_and_is_not_celebrated():
    r = sr.SituationReader()
    out = r.read("got laid off today lol", form(events=[ev("rupture")], tone="joking"), ts=T0)
    assert out["gap"]["kind"] == "joking about something painful"
    assert out["move"] == "acknowledge"


# ---------------------------------------------------------------- the ladder
def test_flat_after_heavy_climbs_the_ladder_one_rung_at_a_time_and_respects_no():
    r = sr.SituationReader()
    r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    moves = []
    for i in range(1, 4):
        out = r.read("ok", form(tone="flat"), ts=T0 + 20 * i)
        moves.append(out["move"])
    assert moves == ["adjust_quietly", "adjust_quietly", "offer"]
    assert out["gap"]["kind"] == "gone flat after something heavy"
    r.record_reaction("waved_off")
    after_no = [r.read("ok", form(tone="flat"), ts=T0 + 100 + 20 * i)["move"] for i in range(3)]
    assert after_no == ["adjust_quietly", "adjust_quietly", "ask_open"], \
        "after a no: two quiet turns, then one open question, because the reading is still strong"
    later = [r.read("ok", form(tone="flat"), ts=T0 + 200 + 20 * i)["move"] for i in range(12)]
    assert set(later) == {"adjust_quietly"}, "no second offer after a no, and no second question"


def test_a_no_stops_being_final_only_if_the_owner_says_so():
    r = sr.SituationReader(sr.OwnerDials(plain_no_is_final_for_offer=False))
    r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    for i in range(1, 4):
        r.read("ok", form(tone="flat"), ts=T0 + 20 * i)
    r.record_reaction("waved_off")
    later = [r.read("ok", form(tone="flat"), ts=T0 + 100 + 20 * i)["move"] for i in range(12)]
    assert later.count("offer") == 1 and later.index("offer") >= 6


def test_observation_questions_can_be_switched_off_by_the_owner():
    r = sr.SituationReader(sr.OwnerDials(observation_statements="never"))
    r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    for i in range(1, 4):
        r.read("ok", form(tone="flat"), ts=T0 + 20 * i)
    r.record_reaction("waved_off")
    moves = [r.read("ok", form(tone="flat"), ts=T0 + 100 + 20 * i)["move"] for i in range(4)]
    assert "ask_open" not in moves


def test_annoying_them_costs_budget_and_alex_gets_out_of_the_way():
    r = sr.SituationReader()
    r.read("synthetic", form(events=[ev("body_rest", weight="medium")]), ts=T0)   # immediate small offer
    before = r.probe_budget
    r.record_reaction("annoyed")
    assert r.probe_budget == before - r.dials.irritation_surcharge
    out = r.read("ugh", form(tone="heated"), ts=T0 + 20)
    assert out["move"] == "adjust_quietly"
    assert "Get out of the way" in r.build_card(out, "outside")


def test_silence_is_unknown_and_never_relief():
    r = sr.SituationReader()
    r.read("synthetic", form(events=[ev("body_food", weight="medium")]), ts=T0)
    before_reaction, before_budget = r.reaction, r.probe_budget
    r.record_reaction("no_reply")
    assert (r.reaction, r.probe_budget) == (before_reaction, before_budget)
    r.settle_last("unknown")
    assert r.hit_rate("noticed")[1] == 0 and r.hit_rate("strong")[1] == 0
    with pytest.raises(ValueError):
        r.record_reaction("relieved")


def test_a_worry_loop_builds_and_is_met_with_staying_not_fixing():
    r = sr.SituationReader()
    bands = []
    for i in range(4):
        out = r.read("what if it goes badly", form(worry_loop=True), ts=T0 + 20 * i)
        bands.append(out["band"])
    assert bands[0] == "quiet" or bands[0] == "noticed"
    assert bands[-1] in ("noticed", "strong")
    assert out["move"] == "acknowledge"


def test_something_heavy_last_week_does_not_make_alex_tiptoe_today():
    r = sr.SituationReader()
    r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    out = r.read("morning! can you believe this weather", form(tone="warm"), ts=T0 + 2 * DAY)
    assert out["band"] == "strong", "the reading still knows"
    assert out["move"] == "carry_on" and out["background"] is True
    assert "Follow their lead" in r.build_card(out, "outside")
    again = r.read("it hit me again this morning", form(events=[ev("loss")]), ts=T0 + 2 * DAY + 60)
    assert again["move"] == "acknowledge" and again["background"] is False


# ---------------------------------------------------------------- style alone
def test_style_alone_can_be_noticed_but_never_strong():
    r = sr.SituationReader()
    bands = [r.read("ok", form(), ts=T0 + 30 * i, engine_payload=payload(-2.5, "disengagement", 0.9))["band"]
             for i in range(8)]
    assert "strong" not in bands
    assert bands[-1] == "noticed"


def test_a_stranger_gets_no_style_evidence():
    r = sr.SituationReader()
    out = r.read("ok", form(), ts=T0, engine_payload=payload(-3, "disengagement", 0.9, maturity=0.0))
    assert out["band"] == "quiet"


# ---------------------------------------------------------------- corrections
def test_a_correction_is_accepted_refunded_and_never_comes_back():
    r = sr.SituationReader()
    r.read("I froze in the meeting", form(events=[ev("setback", weight="medium")]), ts=T0)
    budget = r.probe_budget
    out = r.read("No. I wasn't ashamed. I was furious.", form(
        correction={"present": True, "rejected": "shame", "stated_instead": "furious that you kept calling it shame"}),
        ts=T0 + 20)
    assert out["move"] == "accept_correction"
    assert r.probe_budget >= budget, "a correction is never charged as irritation"
    assert r.bets[0]["outcome"] == "corrected"
    later = r.read("synthetic", form(alternatives=["hidden shame about the meeting", "short on sleep"]), ts=T0 + 40)
    assert later["alternatives_private"] == ["short on sleep"]
    assert "shame" in later["rejected_readings"]
    bad = r.check_reply("It sounds like there may be some shame under this.", later)
    assert any(x["code"] == "rejected_reading_returned" for x in bad)
    assert "shame" in sr.build_form_prompt("x", rejected_readings=r.rejected_labels())


# ---------------------------------------------------------------- bad input never becomes evidence
def test_a_missing_or_broken_form_is_unavailable_not_a_guess():
    r = sr.SituationReader()
    for bad in (None, "", "sorry, I cannot do that", "{not json", 42, ["x"]):
        out = r.read("my dad died last week", bad, ts=T0)
        assert out["band"] == "quiet" and out["move"] == "carry_on"
        assert any(e["family"] == "meaning" and e["status"] == "unavailable" for e in out["evidence"])
        assert "meaning unavailable" in r.build_card(out, "outside")


def test_unknown_values_in_a_form_are_dropped_and_written_down():
    clean, problems = sr.validate_form({"events": [{"kind": "doom", "whose": "theirs", "weight": "heavy"},
                                                   "nonsense", ev("loss")],
                                        "self_report": "ecstatic", "tone": 7, "asked_for": "everything"})
    assert len(clean["events"]) == 1
    assert clean["self_report"] == "none" and clean["tone"] == "unclear" and clean["asked_for"] == "none"
    assert len(problems) >= 4


@pytest.mark.parametrize("voice,status", [
    ({"status": "observed", "pause_z": float("nan"), "rate_z": 0.0}, "invalid"),
    ({"status": "observed", "pause_z": float("inf"), "rate_z": 0.0}, "invalid"),
    ({"status": "observed", "pause_z": "loud", "rate_z": 0.0}, "invalid"),
    ({"status": "simulated", "pause_z": 5.0, "rate_z": -5.0}, "simulated"),
    (None, "unavailable"),
    ({"status": "unavailable"}, "unavailable"),
])
def test_bad_missing_or_simulated_voice_moves_nothing(voice, status):
    r = sr.SituationReader()
    out = r.read("ok", form(), ts=T0, voice=voice)
    v = [e for e in out["evidence"] if e["family"] == "voice"][0]
    assert v["status"] == status and v["llr"] == 0.0
    assert out["band"] == "quiet"


def test_a_malformed_engine_payload_is_unavailable_and_a_nan_is_invalid():
    r = sr.SituationReader()
    out = r.read("ok", form(), ts=T0, engine_payload={"reading": "oops"})
    assert [e for e in out["evidence"] if e["family"] == "style"][0]["status"] == "unavailable"
    out = r.read("ok", form(), ts=T0 + 5, engine_payload=payload(conf=float("nan"), state="depletion"))
    s = [e for e in out["evidence"] if e["family"] == "style"][0]
    assert s["status"] == "invalid" and s["llr"] == 0.0


def test_the_camera_never_moves_the_estimate():
    a, b = sr.SituationReader(), sr.SituationReader()
    x = a.read("ok", form(), ts=T0, camera={"status": "observed", "emotion": "sad", "confidence": 0.99})
    y = b.read("ok", form(), ts=T0, camera=None)
    assert x["p_internal"] == y["p_internal"]
    assert [e for e in y["evidence"] if e["family"] == "camera"][0]["status"] == "unavailable"


# ---------------------------------------------------------------- the reading card
def test_an_outside_model_never_receives_memory_text():
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss", summary="grandmother passed tuesday zebra")],
                                   alternatives=["zebra alternative"], would_change_my_mind="zebra falsifier"),
                 ts=T0)
    outside = r.build_card(out, "outside")
    assert "zebra" not in outside and "grandmother" not in outside
    assert "grandmother" in r.build_card(out, "local")
    general = sr.SituationReader(sr.OwnerDials(outside_model_card="generalized"))
    out2 = general.read("synthetic", form(events=[ev("loss", summary="grandmother passed tuesday zebra")]), ts=T0)
    card2 = general.build_card(out2, "outside")
    assert "loss" in card2 and "zebra" not in card2


def test_the_card_is_short_carries_no_decimals_and_states_the_rules():
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss", summary="x" * 90)] * 3, would_change_my_mind="y" * 160),
                 ts=T0)
    for audience, limit in (("outside", sr.CARD_LIMIT), ("local", sr.CARD_LIMIT_LOCAL)):
        card = r.build_card(out, audience)
        assert len(card) <= limit
        assert "0." not in card
    assert "Do not tell them what they feel" in r.build_card(out, "outside")
    assert "hotline" in r.build_card(out, "outside")
    asked = r.read("who can I call", form(asked_for="information", asked_for_resources=True), ts=T0 + 5)
    assert "hotline" not in r.build_card(asked, "outside")


# ---------------------------------------------------------------- checking a reply
def test_reply_checks_catch_the_named_failures():
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    codes = lambda text: {x["code"] for x in r.check_reply(text, out)}  # noqa: E731
    assert "names_state" in codes("You seem really upset about this.")
    assert "names_state" in codes("You're clearly agitated.")
    assert "unasked_resource" in codes("Have you thought about calling a crisis line?")
    assert "false_reassurance" in codes("Everything will be fine, I promise.")
    assert "question_pile" in codes("When did it happen? Were you there? How are you sleeping?")
    assert "cheer_over_weight" in codes("Congratulations on getting through it!")
    assert codes("I'm so sorry about your dog. Saturday must still be right there. I'm here.") == set()
    asked = r.read("who can I call", form(asked_for="information", asked_for_resources=True), ts=T0 + 5)
    assert "unasked_resource" not in {x["code"] for x in r.check_reply("There is a helpline at ...", asked)}


# ---------------------------------------------------------------- fading, keeping, deleting
def test_a_bad_night_fades_in_days_and_a_death_does_not():
    tired, grief = sr.SituationReader(), sr.SituationReader()
    assert tired.read("synthetic", form(events=[ev("body_rest")]), ts=T0)["band"] == "strong"
    assert grief.read("synthetic", form(events=[ev("loss")]), ts=T0)["band"] == "strong"
    assert tired.read("morning", form(), ts=T0 + 4 * DAY)["band"] == "quiet"
    assert grief.read("morning", form(), ts=T0 + 4 * DAY)["band"] == "strong"
    assert len(tired.ledger.entries) == 1, "still fading, so still held"
    tired.read("morning", form(), ts=T0 + 7 * DAY)
    assert tired.ledger.entries == [], "an entry that has faded to nothing is deleted, not kept"


def test_state_survives_saving_and_loading_and_can_be_deleted():
    a = sr.SituationReader()
    a.read("synthetic", form(events=[ev("rupture", summary="synthetic rupture")]), ts=T0)
    a.read("no, not that", form(correction={"present": True, "rejected": "jealousy", "stated_instead": "tired"}),
           ts=T0 + 10)
    saved = a.export_state()
    b = sr.SituationReader()
    b.import_state(saved)
    x = a.read("ok", form(), ts=T0 + 20)
    y = b.read("ok", form(), ts=T0 + 20)
    assert (x["band"], x["move"], x["p_internal"]) == (y["band"], y["move"], y["p_internal"])
    assert b.rejected_labels() == ["jealousy"]
    c = sr.SituationReader()
    c.import_state({"v": 999, "turn": 50})
    assert c.turn == 0, "an unknown saved shape is ignored, not guessed at"
    entry_id = b.ledger.entries[0].id
    assert b.forget_event(entry_id) and not b.forget_event(entry_id)
    b.forget_everything()
    assert b.ledger.entries == [] and b.rejected == [] and b.bets == [] and b.turn == 0


# ---------------------------------------------------------------- scoring and lessons
def test_hit_rate_counts_only_known_outcomes_and_leans_to_one_half():
    r = sr.SituationReader()
    assert r.hit_rate("strong") == (0.5, 0)
    for i, outcome in enumerate(["held", "held", "held", "corrected", "unknown"]):
        r.read("synthetic", form(events=[ev("loss")]), ts=T0 + i)
        r.settle_last(outcome)
    assert r.hit_rate("strong") == (0.625, 4)


def test_lessons_are_counts_only_and_need_enough_of_them():
    r = sr.SituationReader()
    for i in range(4):
        r.read("synthetic", form(events=[ev("loss", summary="Zelda's funeral on Tuesday")]), ts=T0 + i)
        r.record_what_followed("better")
    assert r.lesson_candidates(min_times=5) == []
    r.read("synthetic", form(events=[ev("loss")]), ts=T0 + 9)
    r.record_what_followed("worse")
    lessons = r.lesson_candidates(min_times=5)
    assert lessons == ["When the situation was of kind loss and the move was acknowledge: "
                       "followed by the person doing better 4 of 5 times."]
    assert "Zelda" not in lessons[0] and "Tuesday" not in lessons[0]


@pytest.mark.parametrize("text,ok", [
    ("When the situation was of kind loss and the move was acknowledge: followed by the person doing better 7 of 9 times.", True),
    ("After a need of LOW_RESERVE, a small offer helped 6 of 8 times.", True),
    ("When Zelda mentioned the funeral, staying quiet helped.", False),
    ("She said \"leave me alone\" and that worked.", False),
    ("After the layoff in November, short replies helped.", False),
    ("After the diagnosis, short replies helped.", False),
    ("After 3 bad nights, a small offer helped.", False),
])
def test_the_lesson_screen_lets_patterns_through_and_stops_people(text, ok):
    assert sr.screen_lesson(text)[0] is ok


# ---------------------------------------------------------------- rules about the code itself
def test_there_is_no_way_to_force_a_state():
    names = [n.lower() for n in dir(sr.SituationReader)] + [n.lower() for n in dir(sr)]
    assert not any("set_state" in n or "force" in n or "inject" in n or "override" in n for n in names)


def test_no_leftover_research_mode_words_or_personal_names_in_the_module():
    src = open(sr.__file__, encoding="utf-8").read().lower()
    for word in ("baby", "nanny", "bottle", "nap ", "diaper", "josie", "curtsey", "988"):
        assert word not in src.replace("988", "988") or word == "988" and src.count("988") == 1, word


def test_parse_form_finds_json_inside_chatter():
    raw = 'Sure, here it is:\n{"events": [], "self_report": "fine", "self_report_plain": true, "tone": "plain", "asked_for": "none"}\nHope that helps'
    clean, _ = sr.validate_form(raw)
    assert clean["self_report"] == "fine" and clean["self_report_plain"] is True


# ---------------------------------------------------------------- with the real engine, when present
def _engine():
    folder = os.environ.get("ALEX_ENGINE_DIR")
    if not folder or not os.path.exists(os.path.join(folder, "affect_context_engine.py")):
        pytest.skip("set ALEX_ENGINE_DIR to run against the real affect engine")
    spec = importlib.util.spec_from_file_location("affect_context_engine",
                                                  os.path.join(folder, "affect_context_engine.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["affect_context_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_runs_beside_the_real_engine_without_changing_it():
    ace = _engine()
    eng, r = ace.AffectContextEngine(), sr.SituationReader()
    ts = T0
    for i in range(14):
        ts += 30
        text = "Okay, that looks right. Let's move the second section up a little."
        out = r.read(text, form(), ts=ts, engine_payload=eng.evaluate(text, "synthetic-user", "s", ts=ts))
        assert out["band"] == "quiet"
    style = [e for e in out["evidence"] if e["family"] == "style"][0]
    assert style["status"] == "observed"
    ts += 30
    text = "my dad died last week"
    out = r.read(text, form(events=[ev("loss", when="days")]), ts=ts,
                 engine_payload=eng.evaluate(text, "synthetic-user", "s", ts=ts))
    assert out["band"] == "strong" and out["move"] == "acknowledge"


def test_the_existing_engine_guard_plugs_into_check_reply():
    ace = _engine()
    r = sr.SituationReader()
    out = r.read("synthetic", form(events=[ev("loss")]), ts=T0)
    found = r.check_reply("You seem exhausted.", out, engine_guard=ace.validate_user_facing)
    assert [x["code"] for x in found].count("names_state") == 1
