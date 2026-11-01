"""Care routines: library safety, shape estimate, selection rules, self-correction,
and the CareCoordinator / bridge wiring. The pure module needs no feature flag;
the wiring tests switch the optional Alex Little One layer on with monkeypatch."""
from __future__ import annotations

import dataclasses
import json
import random

import pytest

from modules.alex_little_one import care_profile as profile_mod
from modules.alex_little_one.care_routines import (
    Bid, BidLabel, CareRoutineDirector, Family, ROUTINES, RoutineSettings, estimate_bid,
    render_prompt_block, settings_from_profile,
)
from modules.care_eq import CareCoordinator

FORBIDDEN_TERMS = (
    profile_mod._SEXUAL_TERMS | profile_mod._HUMILIATION_TERMS | profile_mod._CONTROL_TERMS
    | profile_mod._PUNISHMENT_TERMS | profile_mod._STOP_REFUSAL_TERMS | profile_mod._DIAPER_BOUNDARY_TERMS
)
ALL_ROUTINES = [r for family in Family for r in ROUTINES[family]]
STRAINED = "waaaaah waaaah waaaaaah"
BRIGHT = "hehehe yay!"
CALM = "mama"


def director(seed: int = 1, clock=None) -> CareRoutineDirector:
    ticks = iter(range(0, 100000, 20))
    return CareRoutineDirector(rng=random.Random(seed), clock=clock or (lambda: float(next(ticks))))


def turn(d: CareRoutineDirector, raw: str, settings: RoutineSettings = RoutineSettings()):
    d.observe(raw)
    return d.choose(settings)


# ---- library ---------------------------------------------------------------

def test_every_family_has_routines_and_ids_are_unique():
    assert all(ROUTINES[family] for family in Family)
    ids = [r.id for r in ALL_ROUTINES]
    assert len(ids) == len(set(ids))


def test_no_routine_contains_forbidden_behaviour():
    for r in ALL_ROUTINES:
        text = " ".join((r.intent, *r.beats, *r.seeds)).lower()
        hits = [t for t in FORBIDDEN_TERMS if t in text]
        assert not hits, (r.id, hits)
        assert r.max_sentences <= 5


def test_care_talk_about_needs_stays_in_its_own_families():
    for r in ALL_ROUTINES:
        text = " ".join((*r.beats, *r.seeds)).lower()
        if r.family is not Family.CHANGE:
            assert not any(w in text for w in ("diaper", "freshie")), r.id
        if r.family is not Family.NEEDS:
            assert not any(w in text for w in ("baba", "bottle")), r.id


def test_change_routines_are_plain_care_words_only():
    import re
    anatomical = re.compile(r"\b(genitals?|private parts?|penis|vagina|crotch|groin|pee|poop|pooped|wet yourself)\b")
    for r in ROUTINES[Family.CHANGE]:
        text = " ".join((r.intent, *r.beats, *r.seeds)).lower()
        assert not anatomical.search(text), r.id
        assert r.needs == "change" and r.stage


def test_change_stage_coverage():
    from modules.alex_little_one.care_routines import CHANGE_STAGES
    for stage in CHANGE_STAGES:
        count = sum(1 for r in ROUTINES[Family.CHANGE] if r.stage == stage)
        assert count >= (1 if stage == "pause" else 2), stage
    assert len(ROUTINES[Family.CHANGE]) >= 35  # a lot of dialogue


def test_stop_routine_is_never_in_the_normal_pool():
    d = director(2)
    turn(d, CALM)
    for _ in range(300):
        assert turn(d, CALM).routine.id != "stop_and_steady"


def test_josies_own_words_are_preserved_exactly():
    seeds = {s for r in ALL_ROUTINES for s in r.seeds}
    assert "Look at that big smile. Look at that smile. What a happy {pet}." in seeds
    assert "Does my {pet} need a freshie?" in seeds
    assert "Is someone ready for their baba?" in seeds
    assert "I'm right here. You're safe. Nothing you need to do." in seeds


def test_address_term_fills_her_phrase_exactly():
    from modules.alex_little_one.care_routines import RoutineChoice
    big_smile = next(r for r in ROUTINES[Family.PLAY] if r.id == "big_smile")
    choice = RoutineChoice(big_smile, estimate_bid(BRIGHT), "little guy", "test")
    block = render_prompt_block(choice)
    assert "Look at that big smile. Look at that smile. What a happy little guy." in block
    assert "{pet}" not in block


# ---- shape estimate --------------------------------------------------------

@pytest.mark.parametrize("raw,label", [
    (STRAINED, BidLabel.STRAINED),
    ("WAAAAH!!", BidLabel.STRAINED),
    ("nnnn nnn", BidLabel.STRAINED),
    (BRIGHT, BidLabel.BRIGHT),
    ("zzz", BidLabel.DROWSY),
    ("", BidLabel.QUIET),
    ("   ", BidLabel.QUIET),
    (CALM, BidLabel.SETTLED),
    # Stretched sounds on their own could be cooing or wailing. The honest label
    # is "unknown", which gets gentle presence rather than play or hard soothing.
    ("goooo gooo baaa", BidLabel.UNKNOWN),
    ("mmmm", BidLabel.UNKNOWN),
])
def test_estimate_labels(raw, label):
    assert estimate_bid(raw).label is label


@pytest.mark.parametrize("raw,label", [
    ("weeeee!!", BidLabel.BRIGHT),
    ("yaaaay!", BidLabel.BRIGHT),
    ("zzzzz", BidLabel.DROWSY),
])
def test_stretched_laughter_and_sleep_are_not_strain(raw, label):
    bid = estimate_bid(raw)
    assert bid.strain == 0.0 or bid.strain < 0.25
    assert bid.label is label


def test_sleep_after_a_hold_is_not_scored_as_worse():
    d = director()
    turn(d, CALM)
    turn(d, "")
    d.observe("zzz")
    assert d.last_outcome["verdict"] != "worse"


def test_prompt_block_has_clean_punctuation():
    for r in ALL_ROUTINES:
        d = director()
        d.observe(CALM)
        from modules.alex_little_one.care_routines import RoutineChoice
        block = render_prompt_block(RoutineChoice(r, estimate_bid(CALM), "little one", "t"))
        assert ".;" not in block and ".." not in block.replace("...", ""), r.id


@pytest.mark.parametrize("raw", ["goooo gooo baaa", "mmmm"])
def test_ambiguous_stretched_sounds_get_gentle_presence(raw):
    d = director()
    turn(d, CALM)
    assert turn(d, raw).routine.family is Family.PRESENCE


def test_silence_is_quiet_not_relief():
    bid = estimate_bid("")
    assert bid.silent and bid.label is BidLabel.QUIET


def test_bid_holds_no_text():
    secret = "the launch code is swordfish"
    bid = estimate_bid(secret)
    assert all(not isinstance(v, str) or v in {e.value for e in BidLabel} or isinstance(v, BidLabel)
               for v in dataclasses.asdict(bid).values())
    assert "swordfish" not in repr(bid)


def test_adult_words_are_not_read_for_meaning():
    # The estimator looks at shape. These carry no strain shape, whatever they mean.
    assert estimate_bid("i'm fine").label is not BidLabel.STRAINED
    assert estimate_bid("everything is terrible").label is not BidLabel.STRAINED


def test_estimate_is_deterministic():
    assert estimate_bid(STRAINED, gap_s=4.0) == estimate_bid(STRAINED, gap_s=4.0)


# ---- selection rules -------------------------------------------------------

def test_first_turn_is_welcome_unless_strained():
    assert turn(director(), CALM).routine.family is Family.WELCOME
    assert turn(director(), STRAINED).routine.family is Family.SOOTHE


@pytest.mark.parametrize("seed", range(25))
def test_strained_never_gets_play(seed):
    d = director(seed)
    turn(d, CALM)
    for _ in range(6):
        assert turn(d, STRAINED).routine.family in (Family.SOOTHE, Family.PRESENCE)


def test_bright_after_calm_gets_play():
    d = director()
    turn(d, CALM)
    turn(d, CALM)
    assert turn(d, BRIGHT).routine.family is Family.PLAY


def test_bright_right_after_soothing_stays_gentle():
    d = director()
    turn(d, CALM)
    turn(d, STRAINED)
    choice = turn(d, BRIGHT)
    assert choice.routine.family is Family.SETTLE
    assert choice.routine.gentle_play


def test_bright_too_early_stays_gentle_not_play():
    d = director()
    turn(d, CALM)                       # one prior turn: not enough history yet
    choice = turn(d, BRIGHT)
    assert choice.bid.label is BidLabel.BRIGHT
    assert choice.bid.confidence < 0.55
    assert choice.routine.family is Family.SETTLE and choice.routine.gentle_play


def test_play_followed_by_strain_repairs():
    d = director()
    turn(d, CALM)
    turn(d, CALM)
    assert turn(d, BRIGHT).routine.family is Family.PLAY
    choice = turn(d, STRAINED)
    assert choice.routine.family is Family.SOOTHE
    assert choice.repair
    assert "Ease off" in render_prompt_block(choice)


def test_repeated_strain_stops_switching_and_holds_steady():
    d = director()
    turn(d, CALM)
    picks = [turn(d, STRAINED) for _ in range(5)]
    assert [c.routine.family for c in picks[:3]] == [Family.SOOTHE] * 3
    steady = picks[3]
    assert steady.steady and steady.routine.id == "hold_steady"
    assert "Do not try anything new" in render_prompt_block(steady)


def test_calm_after_soothing_comes_down_to_settle_or_presence():
    d = director()
    turn(d, STRAINED)
    assert turn(d, CALM).routine.family in (Family.SETTLE, Family.PRESENCE)


def test_drowsy_winds_down():
    d = director()
    turn(d, CALM)
    assert turn(d, "zzz").routine.family is Family.WIND_DOWN


def test_quiet_gets_presence_not_silence():
    d = director()
    turn(d, CALM)
    assert turn(d, "").routine.family is Family.PRESENCE


def test_no_immediate_repeats_within_a_family():
    d = director(3)
    turn(d, CALM)
    seen = []
    for _ in range(20):
        c = turn(d, CALM)
        if c.routine.family is Family.SETTLE:
            seen.append(c.routine.id)
    window = 4
    for i in range(len(seen)):
        assert seen[i] not in seen[max(0, i - window):i]


def test_choose_is_idempotent_within_a_turn():
    d = director()
    d.observe(CALM)
    assert d.choose() is d.choose()
    d.observe(CALM)
    assert d.choose() is not None


def test_same_seed_same_choices():
    def run(seed):
        d = director(seed)
        return [turn(d, raw).routine.id for raw in (CALM, STRAINED, STRAINED, CALM, BRIGHT, "", "zzz")]
    assert run(7) == run(7)


def test_choose_without_observation_is_none():
    assert director().choose() is None


# ---- optional talk is opt-in ---------------------------------------------------

def test_nothing_optional_happens_by_default():
    d = director(5)
    turn(d, CALM)
    for _ in range(300):
        assert turn(d, CALM).routine.family not in (Family.NEEDS, Family.CHANGE)
    assert not d.change_in_progress


def test_bottle_talk_appears_only_when_enabled_and_spaced_out():
    d = director(5)
    settings = RoutineSettings(allow_bottle_talk=True, needs_rate=1.0)
    turn(d, CALM, settings)
    picks = [turn(d, CALM, settings) for _ in range(30)]
    needs = [i for i, c in enumerate(picks) if c.routine.family is Family.NEEDS]
    assert needs, "bottle talk never appeared"
    assert {picks[i].routine.id for i in needs} == {"baba_talk"}
    assert all(b - a >= 6 for a, b in zip(needs, needs[1:]))


def test_bottle_talk_never_follows_strain():
    d = director(5)
    settings = RoutineSettings(allow_bottle_talk=True, needs_rate=1.0)
    turn(d, CALM, settings)
    turn(d, STRAINED, settings)
    assert turn(d, CALM, settings).routine.family is not Family.NEEDS


# ---- diaper change sequence -------------------------------------------------------

ON = RoutineSettings(allow_change_talk=True, change_rate=1.0)


def run_change(seed: int, settings: RoutineSettings = ON, raws=None, max_turns: int = 40):
    """Drive calm turns until a whole change has run. Returns the choices that were part of it."""
    d = director(seed)
    turn(d, CALM, settings)
    picks, started = [], False
    for i in range(max_turns):
        raw = (raws[i % len(raws)] if raws else CALM)
        c = turn(d, raw, settings)
        if c.routine.family is Family.CHANGE:
            started = True
            picks.append(c)
        elif started:
            break
    return d, picks


def test_change_never_starts_before_the_first_few_turns():
    d = director(1)
    first = [turn(d, CALM, ON) for _ in range(3)]
    assert all(c.routine.family is not Family.CHANGE for c in first[:2])


@pytest.mark.parametrize("seed", range(12))
def test_a_change_runs_in_order_and_ends(seed):
    d, picks = run_change(seed)
    stages = [c.stage for c in picks]
    assert stages[0] == "check"
    if stages[1] == "verdict_dry":
        assert stages == ["check", "verdict_dry"]
        return
    assert stages[1] == "verdict_wet"
    required = ["setup", "untape", "wipe", "fresh", "tape", "present"]
    positions = [stages.index(s) for s in required]
    assert positions == sorted(positions)
    assert stages[-1] == "present"
    assert set(stages) <= {"check", "verdict_wet", "setup", "untape", "wipe", "powder", "distract", "fresh", "tape", "present"}
    assert [c.step[0] for c in picks] == list(range(1, len(picks) + 1))
    assert all(c.step[1] == len(picks) for c in picks)
    assert not d.change_in_progress


def test_wet_verdict_is_a_coin_flip_that_no_input_can_move():
    """Whether a change is needed comes from chance alone: about half, whatever is sent."""
    inputs = {
        "calm": [CALM], "no": ["no no no", "nope"], "yes": ["yes yes", "yes please"],
        "quiet": [""], "bright": [BRIGHT, CALM], "mixed": ["no", "yes", "", CALM, "wait"],
    }
    for name, raws in inputs.items():
        wet = dry = 0
        for seed in range(400):
            _d, picks = run_change(seed, raws=raws)
            verdicts = [c.verdict for c in picks if c.verdict]
            assert len(verdicts) == 1, (name, seed, [c.stage for c in picks])
            wet += verdicts[0] == "wet"
            dry += verdicts[0] == "dry"
        assert wet + dry == 400
        assert 0.42 <= wet / 400 <= 0.58, (name, wet)


def test_default_wet_chance_is_even():
    assert RoutineSettings().wet_chance == 0.5


def test_answering_the_rhetorical_question_with_no_does_not_cancel_the_check():
    for seed in range(20):
        _d, picks = run_change(seed, raws=["no"])
        assert [c.stage for c in picks][:2] in (["check", "verdict_wet"], ["check", "verdict_dry"])


def test_upset_mid_change_soothes_then_carries_on():
    d, picks = run_change(3, settings=RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0),
                          max_turns=5)  # check, verdict, set-up, untape: now underway
    assert d.change_in_progress
    before = [c.stage for c in picks]
    soothe = turn(d, STRAINED, ON)
    assert soothe.routine.family is Family.SOOTHE and soothe.mid_change
    assert "middle of a diaper change" in render_prompt_block(soothe)
    assert d.change_in_progress
    resumed = turn(d, CALM, ON)
    assert resumed.routine.family is Family.CHANGE
    assert resumed.stage not in before[-1:]  # moved on; did not repeat the step it was on


def test_two_upset_turns_pause_the_change_and_it_stays_paused():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    d, _ = run_change(4, settings=wet, max_turns=5)  # underway
    first = turn(d, STRAINED, wet)
    assert first.mid_change and d.change_in_progress
    paused = turn(d, STRAINED, wet)
    assert paused.stage == "pause" and paused.routine.id == "pause_change"
    assert not d.change_in_progress
    for _ in range(10):  # cooldown: no new check right away
        assert turn(d, CALM, wet).routine.family is not Family.CHANGE


def test_upset_before_set_up_pauses_at_once():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    d, picks = run_change(5, settings=wet, max_turns=2)  # welcome, one calm turn, then the check
    assert [c.stage for c in picks] == ["check"]
    assert turn(d, STRAINED, wet).stage == "pause"


def test_stop_and_pause_end_everything_at_once():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    for word in ("stop", "STOP!", "pause", "please stop", "big mode now", "blanket off"):
        d, _ = run_change(6, settings=wet, max_turns=3)
        assert d.change_in_progress
        choice = turn(d, word, wet)
        assert choice.routine.id == "stop_and_steady", word
        assert not d.change_in_progress
        for _ in range(10):
            assert turn(d, CALM, wet).routine.family is not Family.CHANGE


def test_stop_works_outside_a_change_too():
    d = director()
    turn(d, CALM)
    assert turn(d, "stop").routine.id == "stop_and_steady"


def test_a_plain_no_is_acknowledged_but_decides_nothing():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    d, _ = run_change(7, settings=wet, max_turns=3)
    choice = turn(d, "no no no", wet)
    assert choice.bid.protest and not choice.bid.halt
    assert choice.routine.family is Family.CHANGE and d.change_in_progress
    assert "Acknowledge it lightly" in render_prompt_block(choice)


def test_no_during_play_eases_off():
    d = director()
    turn(d, CALM)
    turn(d, CALM)
    assert turn(d, BRIGHT).routine.family is Family.PLAY
    choice = turn(d, "no no")
    assert choice.routine.family is Family.SOOTHE and choice.repair


def test_turning_change_talk_off_stops_a_change_in_progress():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    d, _ = run_change(8, settings=wet, max_turns=3)
    assert d.change_in_progress
    off = RoutineSettings(allow_change_talk=False)
    assert turn(d, CALM, off).routine.family is not Family.CHANGE
    assert not d.change_in_progress


def test_no_change_without_the_owner_switch():
    d = director(9)
    turn(d, CALM, RoutineSettings(change_rate=1.0))
    for _ in range(200):
        assert turn(d, CALM, RoutineSettings(change_rate=1.0)).routine.family is not Family.CHANGE


def test_change_never_starts_while_upset_or_playing():
    for seed in range(20):
        d = director(seed)
        turn(d, CALM, ON)                                   # welcome
        turn(d, CALM, ON)                                   # too early to start
        assert turn(d, BRIGHT, ON).routine.family is not Family.CHANGE
        assert turn(d, STRAINED, ON).routine.family is not Family.CHANGE
        assert not d.change_in_progress


def test_a_change_already_underway_carries_on_through_a_giggle():
    wet = RoutineSettings(allow_change_talk=True, change_rate=1.0, wet_chance=1.0)
    d, _ = run_change(10, settings=wet, max_turns=3)
    assert d.change_in_progress
    assert turn(d, BRIGHT, wet).routine.family is Family.CHANGE


def test_change_prompt_says_the_step_and_keeps_it_plain_and_dignified():
    _d, picks = run_change(2)
    block = render_prompt_block(picks[1])
    assert "diaper change in progress" in block and "never tease, shame or hurry" in block
    assert "Nothing sexual and nothing anatomical" in block
    verdict_block = render_prompt_block(next(c for c in picks if c.verdict))
    assert ("needs changing" in verdict_block) or ("still dry" in verdict_block)


def test_variety_across_changes():
    d = director(11)
    turn(d, CALM, ON)
    seen = {}
    for _ in range(400):
        c = turn(d, CALM, ON)
        if c.stage:
            seen.setdefault(c.stage, []).append(c.routine.id)
    for stage in ("check", "setup", "wipe", "tape", "present"):
        ids = seen[stage]
        assert len(set(ids)) >= 2
        assert all(a != b for a, b in zip(ids, ids[1:]))  # same step never twice in a row


def test_settings_from_profile():
    assert settings_from_profile(None) == RoutineSettings()
    on = settings_from_profile({"care_mode": "very_baby", "continence_support": {"enabled": True}})
    assert on.allow_change_talk and not on.allow_bottle_talk and on.depth == "very_baby"
    off = settings_from_profile({"care_mode": "soft", "continence_support": {"enabled": False}})
    assert not off.allow_change_talk and off.depth == "soft"


def test_address_terms_are_cleaned():
    s = RoutineSettings(address_terms=('bad"{x}\nterm', "", "y" * 200))
    terms = s.terms()
    assert all('"' not in t and "{" not in t and "\n" not in t and 0 < len(t) <= 40 for t in terms)
    assert RoutineSettings(address_terms=("", "  ")).terms() == ("little guy", "little one")


# ---- prompt block and pacing ---------------------------------------------------

def test_prompt_block_makes_alex_carry_the_conversation():
    d = director()
    d.observe(CALM)
    choice = d.choose()
    block = render_prompt_block(choice)
    assert "You carry this conversation" in block
    assert "rhetorical" in block
    assert "Do not wait for or require an answer" in block
    for phrase in ("big mode now", "blanket off", "parachute"):
        assert phrase in block
    assert "{pet}" not in block
    pacing = choice.to_packet()["pacing"]
    assert pacing["wait_for_reply"] is False and pacing["questions"] == "rhetorical_only"
    assert pacing["alex_share"] == 0.95


def test_soft_depth_shares_more_of_the_talking():
    d = director()
    d.observe(CALM)
    assert d.choose(RoutineSettings(depth="soft")).to_packet()["pacing"]["alex_share"] == 0.8


# ---- feedback loop ------------------------------------------------------------

def test_outcome_better_when_strain_eases():
    d = director()
    turn(d, STRAINED)
    d.observe(CALM)
    assert d.last_outcome["verdict"] == "better"
    assert sum(c["better"] for c in d.outcomes().values()) == 1


def test_outcome_worse_when_calm_turns_strained():
    d = director()
    turn(d, CALM)
    turn(d, CALM)
    d.observe(STRAINED)
    assert d.last_outcome["verdict"] == "worse"


def test_silence_is_unclear_and_not_tallied():
    d = director()
    turn(d, STRAINED)
    d.observe("")
    assert d.last_outcome["verdict"] == "unclear"
    assert d.outcomes() == {}


def test_play_that_stays_bright_counts_as_better():
    d = director()
    turn(d, CALM)
    turn(d, CALM)
    assert turn(d, BRIGHT).routine.family is Family.PLAY
    d.observe(BRIGHT)
    assert d.last_outcome["verdict"] == "better"


def test_what_works_is_favoured_and_what_hurts_is_not():
    d = director()
    d._tally["cradle_sway"] = [4, 0, 0]
    d._tally["shoulder_pats"] = [0, 0, 5]
    assert d._weight("cradle_sway") > d._weight("back_circles") > d._weight("shoulder_pats")
    assert d._weight("shoulder_pats") >= 0.2


def test_learning_survives_reset_within_the_process():
    d = director()
    turn(d, STRAINED)
    d.observe(CALM)
    tally = d.outcomes()
    d.reset()
    assert d.outcomes() == tally
    assert d.last_outcome is None


# ---- wiring: CareCoordinator ----------------------------------------------------

@pytest.fixture
def routines_on(monkeypatch):
    monkeypatch.setenv("ENABLE_ALEX_LITTLE_ONE", "true")


def test_coordinator_routines_are_off_without_the_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_ALEX_LITTLE_ONE", raising=False)
    care = CareCoordinator(tmp_path)
    care.activate("u")
    care.receive("u", STRAINED)
    assert care.routine_for("u") is None
    assert all(e["kind"] != "routine" for e in care.export("u")["events"])


def test_coordinator_gives_a_routine_each_turn_and_never_stores_text(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.activate("u")
    assert care.routine_for("u") is None  # nothing observed yet
    private = "zxqv-private-sentinel"
    masked = care.receive("u", private)
    assert "meaning unknown" in masked
    packet = care.routine_for("u")
    assert packet["routine_id"] and packet["prompt_block"]
    assert care.routine_for("u") == packet  # idempotent within the turn
    care.receive("u", STRAINED)
    assert care.routine_for("u")["family"] == "soothe"
    blob = json.dumps(care.export("u")) + "".join(p.read_text() for p in (tmp_path / "care_eq_private").glob("*.json"))
    assert private not in blob and STRAINED not in blob
    kinds = [e["kind"] for e in care.export("u")["events"]]
    assert "routine" in kinds and "routine_outcome" in kinds


def test_coordinator_exit_phrase_stops_routines_and_forgets_shapes(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.activate("u")
    care.receive("u", STRAINED)
    assert care.routine_for("u")
    assert care.receive("u", "parachute") == "[SAFEWORD: PARACHUTE]"
    assert care.routine_for("u") is None
    care.activate("u")
    assert care.routine_for("u") is None  # fresh session: no stale turn


def test_coordinator_routine_for_requires_baby_mode(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    assert care.routine_for("nobody") is None
    care.activate("u")
    care.receive("u", CALM)
    care.deactivate("u")
    assert care.routine_for("u") is None


def test_coordinator_other_owners_are_isolated(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.activate("a")
    care.receive("a", STRAINED)
    assert care.routine_for("b") is None


# ---- wiring: bridge -------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_adds_routine_and_drops_misleading_signals(tmp_path, routines_on):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    care = CareCoordinator(tmp_path)
    bridge.care_eq = care
    care.activate("u")
    try:
        packet = await bridge.process_user_turn(user_id="u", session_id="s", text=STRAINED)
        assert packet["care_routine"]["family"] == "soothe"
        assert packet["alex_signals_suppressed"] == "care_mode_masked_input"
        for key in ("response_guidelines", "tone_guidance", "system_alex_guidance", "emotional_coordination"):
            assert key not in packet
        saved = "".join(p.read_text() for p in tmp_path.rglob("*.json") if "care_eq_private" not in str(p))
        assert "care_routine" not in saved and "prompt_block" not in saved
    finally:
        bridge.shutdown()


@pytest.mark.asyncio
async def test_bridge_unchanged_when_not_in_baby_mode(tmp_path, routines_on):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    bridge.care_eq = CareCoordinator(tmp_path)
    try:
        packet = await bridge.process_user_turn(user_id="u", session_id="s", text="hello there")
        assert "care_routine" not in packet and "alex_signals_suppressed" not in packet
        assert packet.get("response_guidelines") is not None
    finally:
        bridge.shutdown()


@pytest.mark.asyncio
async def test_bridge_without_the_flag_keeps_old_behaviour(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_ALEX_LITTLE_ONE", raising=False)
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    care = CareCoordinator(tmp_path)
    bridge.care_eq = care
    care.activate("u")
    try:
        packet = await bridge.process_user_turn(user_id="u", session_id="s", text="classified adult paragraph xyz")
        assert "care_routine" not in packet
        assert care.is_active("u")
    finally:
        bridge.shutdown()


def test_prompt_renders_the_routine():
    from modules import smollm_prompt
    with open(smollm_prompt.__file__, encoding="utf-8") as handle:
        source = handle.read()
    assert 'alex.get("care_routine")' in source and "prompt_block" in source


# ---- owner setting: change talk is opt-in and private -------------------------------

def test_clean_address_terms():
    from modules.alex_little_one.care_routines import clean_address_terms
    assert clean_address_terms(None) == () and clean_address_terms("nope") == ()
    out = clean_address_terms(['sweet "pea"', "{x}", "", "sweet pea", "a" * 100] + [f"t{i}" for i in range(10)])
    assert len(out) == 6 and all(len(t) <= 40 and '"' not in t and "{" not in t for t in out)
    assert out.count("sweet pea") == 1


def test_routine_settings_default_off_and_persist(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    assert care.routine_settings("u") == {"change_talk": False, "bottle_talk": False,
                                          "address_terms": [], "routines_enabled": True}
    saved = care.set_routine_settings("u", change_talk=True, address_terms=["sweet pea", "", "{bad}"])
    assert saved["change_talk"] is True and saved["bottle_talk"] is False
    assert saved["address_terms"] == ["sweet pea", "bad"]
    reloaded = CareCoordinator(tmp_path)
    assert reloaded.routine_settings("u")["change_talk"] is True
    assert reloaded.routine_settings("other")["change_talk"] is False  # per owner
    assert reloaded.set_routine_settings("u", change_talk=False)["change_talk"] is False
    assert CareCoordinator(tmp_path).routine_settings("u")["change_talk"] is False


def test_routine_settings_are_in_the_private_store_only(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.set_routine_settings("u", change_talk=True)
    files = list((tmp_path / "care_eq_private").glob("*.json"))
    assert files and all("routine_settings" in f.read_text() for f in files)
    assert not any("routine_settings" in f.read_text() for f in tmp_path.rglob("*.json") if "care_eq_private" not in str(f))
    kinds = [e["kind"] for e in care.export("u")["events"]]
    assert "routine_settings" in kinds


def test_old_care_files_without_settings_still_load(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.activate("u")
    for f in (tmp_path / "care_eq_private").glob("*.json"):
        data = json.loads(f.read_text())
        data.pop("routine_settings", None)
        f.write_text(json.dumps(data))
    assert CareCoordinator(tmp_path).routine_settings("u")["change_talk"] is False


def _drive(care: CareCoordinator, turns: int, raw: str = CALM):
    stages = []
    for _ in range(turns):
        care.receive("u", raw)
        packet = care.routine_for("u")
        stages.append((packet["family"], packet["stage"]))
    return stages


def test_change_talk_runs_only_after_the_owner_turns_it_on(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care._directors["u"] = CareRoutineDirector(rng=random.Random(4))
    care.activate("u")
    assert all(f != "change" for f, _ in _drive(care, 120))
    care.set_routine_settings("u", change_talk=True)
    stages = _drive(care, 250)
    assert any(f == "change" for f, _ in stages)
    assert {s for f, s in stages if f == "change"} >= {"check", "present"}


def test_turning_change_talk_off_mid_change_stops_it(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care._directors["u"] = CareRoutineDirector(rng=random.Random(4))
    care.activate("u")
    care.set_routine_settings("u", change_talk=True)
    for _ in range(300):
        care.receive("u", CALM)
        if care.routine_for("u")["stage"] == "setup":
            break
    else:
        pytest.fail("no change reached set-up")
    care.set_routine_settings("u", change_talk=False)
    care.receive("u", CALM)
    assert care.routine_for("u")["family"] != "change"


def test_owner_pet_names_reach_the_prompt(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care.activate("u")
    care.set_routine_settings("u", address_terms=["sweet pea"])
    blocks = []
    for _ in range(40):
        care.receive("u", CALM)
        blocks.append(care.routine_for("u")["prompt_block"])
    assert any("sweet pea" in b for b in blocks)
    assert not any("little guy" in b for b in blocks)


def test_change_events_are_logged_without_text(tmp_path, routines_on):
    care = CareCoordinator(tmp_path)
    care._directors["u"] = CareRoutineDirector(rng=random.Random(4))
    care.activate("u")
    care.set_routine_settings("u", change_talk=True)
    _drive(care, 120, raw="zxqv-private-sentinel")
    events = care.export("u")["events"]
    routine_events = [e for e in events if e["kind"] == "routine"]
    assert any(e["observed"].get("stage") for e in routine_events)
    assert "zxqv-private-sentinel" not in json.dumps(events)


def test_settings_routes_are_owner_scoped(tmp_path, routines_on):
    import asyncio
    from fastapi import HTTPException
    from modules import alex_routes
    care = CareCoordinator(tmp_path)
    alex_routes.set_care_eq(care)
    owner = {"user_id": "u", "role": "owner", "authenticated": True}
    guest = {"user_id": "g", "role": "guest", "authenticated": True}
    anon = {"user_id": "u", "role": "owner", "authenticated": False}
    try:
        got = asyncio.run(alex_routes.get_care_routines(identity=owner))
        assert got["change_talk"] is False and got["routines_enabled"] is True
        body = alex_routes.CareRoutineSettingsRequest(change_talk=True, address_terms=["sweet pea"])
        out = asyncio.run(alex_routes.set_care_routines(body, identity=owner))
        assert out["change_talk"] is True and out["address_terms"] == ["sweet pea"]
        with pytest.raises(HTTPException) as exc:
            asyncio.run(alex_routes.set_care_routines(body, identity=guest))
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            asyncio.run(alex_routes.set_care_routines(body, identity=anon))
        assert exc.value.status_code == 401
        assert care.routine_settings("g")["change_talk"] is False
    finally:
        alex_routes.set_care_eq(None)
