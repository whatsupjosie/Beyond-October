"""
situation_reading.py - the situation-first reading model for Alex.

STATUS: new and additive. Nothing in PubCast imports this file yet. It changes no
existing behaviour until someone wires it in (see PLAN_2026-11-10.txt).

WHAT IT DOES, IN ORDER, EVERY TURN
  1. Exit words are checked first, by plain code, with no model involved. They always win.
  2. A language model has filled in a short form about the message (what happened, whose
     it is, what the person says about themselves, the tone, what they asked for, whether
     they corrected Alex). That form is checked. Anything malformed is thrown away and
     written down as a problem. A missing form means "meaning: unavailable", never a guess.
  3. Things that happened in the person's own life go into a private ledger. Each entry
     has a weight and fades at a rate that fits its kind.
  4. Evidence is grouped into families. Each family can move the estimate only so far:
        events        what has happened (the ledger)
        self_report   what they say about their own state
        style         how this message compares with their normal (from the existing engine)
        voice         pauses and pace, when a microphone is present
        reaction      how they reacted to something Alex offered
  5. What the person SAYS about themselves is kept apart from the rest. If the two
     disagree, that gap is reported. It is never announced to the person.
  6. The estimate becomes one of three bands: quiet, noticed, strong. No decimals leave
     this module for display.
  7. A move is chosen separately from the reading (what Alex should do next).
  8. A short reading card is built for the model that writes the reply. For an outside
     model the card carries no memory text at all.
  9. Corrections are stored as "never use this reading again" for that person.
 10. Every reading is logged as a small bet so its outcome can be scored later.

WHAT IT NEVER DOES
  - It never tells a person what they feel, and check_reply() flags a reply that does.
  - It never suggests a hotline or a service. check_reply() flags one nobody asked for.
  - It never treats silence as relief, a missing camera as calm, or simulated output as
    something observed.
  - It has no state setter. Tests build forms; the live path has no way to force a state.

Stdlib only. Vocabulary for needs is taken from the 2026-10-02 empathy pass
(be_heard, steadiness, room_to_think, practical_help, encouragement, celebrate_with,
light_company) and the neutral care tags (LOW_RESERVE, DEPLETION, ACTIVE_IRRITANT,
COREGULATION, CONTAINMENT, GOAL_BLOCKED). The empathy pass's "human_support" need is
left out on purpose: what Alex does in real danger is the owner's undecided call.

Rearview Foresight - Feic Mo Chroi
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------------------
# OWNER DIALS. Every value here is the owner's decision. The defaults are Fable's
# recommendations from ALEX_EQ_FABLE_REPLY_2026-11-10.txt, Part 6, and are PENDING her answer.
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class OwnerDials:
    # Decision 1. How far a plain "I'm fine" pulls the estimate down when the rest of the
    # evidence disagrees. 0 = not at all, 1 = fully. When nothing disagrees it is believed.
    self_report_weight: float = 0.25
    # Decision 2. A plain "no" to something Alex offered is final for that offer.
    plain_no_is_final_for_offer: bool = True
    # Decision 3. May Alex say what she observed? "never", "behaviour_only" (what can be
    # pointed to, e.g. "you've gone quiet"; never a feeling), or "allowed".
    observation_statements: str = "behaviour_only"
    # Decision 5. What an outside model may be told: "band_and_move" or "generalized"
    # (adds only the kind of situation, e.g. "loss"). Memory text goes to a local model only.
    outside_model_card: str = "band_and_move"
    # Exit words. These end whatever is happening, for every user, every time.
    exit_words: Tuple[str, ...] = ("stop", "pause", "exit", "go lucid", "step out of role")
    # Probe budget. Same numbers as affect_context_engine.py so the two stay in step.
    probe_budget_start: float = 3.0
    probe_refund: float = 0.6
    irritation_surcharge: float = 1.0


# --------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------

EVENT_KINDS = ("loss", "rupture", "setback", "threat", "body_rest", "body_food",
               "body_other", "irritant", "good_news", "other")
WHOSE = ("theirs", "someone_close", "someone_else", "fiction", "figure_of_speech", "unclear")
WEIGHT_WORDS = {"light": 0.8, "medium": 1.6, "heavy": 3.0}
WHOSE_FACTOR = {"theirs": 1.0, "someone_close": 0.5, "someone_else": 0.1,
                "fiction": 0.0, "figure_of_speech": 0.0, "unclear": 0.3}
WHEN_AGE_S = {"now": 0, "today": 6 * 3600, "days": 3 * 86400, "weeks": 21 * 86400,
              "older": 90 * 86400, "unknown": 0}
HALF_LIFE_S = {"loss": 30 * 86400, "rupture": 7 * 86400, "setback": 5 * 86400,
               "threat": 3 * 86400, "body_rest": 86400, "body_food": 6 * 3600,
               "body_other": 2 * 86400, "irritant": 2 * 3600, "good_news": 86400,
               "other": 3 * 86400}
SELF_REPORTS = ("none", "fine", "not_fine", "mixed")
TONES = ("plain", "joking", "sarcastic", "flat", "heated", "warm", "unclear")
ASKED_FOR = ("none", "task", "information", "to_be_heard", "space", "stop")
STATUSES = ("observed", "unavailable", "simulated", "invalid")

MOVES = ("carry_on", "adjust_quietly", "acknowledge", "offer", "ask_open", "celebrate",
         "practical_help", "accept_correction", "clarify_gap", "stop_now")

MOVE_GUIDE = {
    "carry_on": "Continue normally and match their tone.",
    "adjust_quietly": "Change your own behaviour: shorter, slower, fewer demands. Say nothing about why.",
    "acknowledge": "Stay with what they told you, in particular. No fixing. At most one question.",
    "offer": "Make one small concrete offer they can wave off. If they wave it off, drop it.",
    "ask_open": "Ask one open question about what you observed. Do not name a feeling for them.",
    "celebrate": "Share the good news with them, specifically. No plan, no advice.",
    "practical_help": "Do or answer the thing they asked for. Keep it plain.",
    "accept_correction": "They corrected your reading. Drop it, say so plainly, own your part. Do not defend it.",
    "clarify_gap": "One specific thing is unclear. Say what you understood and ask only about that.",
    "stop_now": "They used an exit word. Stop immediately. One short plain line at most.",
}

PRIOR_P = 0.12          # before any evidence: most of a life is steady
P_FLOOR, P_CEIL = 0.03, 0.97   # never near-certain in either direction
BAND_NOTICED, BAND_STRONG = 0.35, 0.60
FAMILY_CEILING = {"events": 3.5, "self_report": 1.8, "style": 1.5, "voice": 1.5, "reaction": 1.0}
CARD_LIMIT = 600          # outside model
CARD_LIMIT_LOCAL = 900    # local model: also carries what is going on


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def band_of(p: float) -> str:
    return "strong" if p >= BAND_STRONG else "noticed" if p >= BAND_NOTICED else "quiet"


# --------------------------------------------------------------------------------------
# Exit words: plain code, no model, always first
# --------------------------------------------------------------------------------------

def is_exit(text: str, exit_words: Tuple[str, ...]) -> bool:
    """True when the whole message is one or more exit words and nothing else.
    "Stop. Go lucid." is an exit. "Stop for lunch?" is not."""
    low = re.sub(r"[^a-z ]+", " ", (text or "").lower())
    low = re.sub(r"\s+", " ", low).strip()
    if not low:
        return False
    for w in sorted(exit_words, key=len, reverse=True):
        low = re.sub(r"\b" + re.escape(w) + r"\b", " ", low)
    return low.strip() == ""


# --------------------------------------------------------------------------------------
# The form a model fills in, and its checker
# --------------------------------------------------------------------------------------

FORM_INSTRUCTIONS = """You are filling in a private reading form about ONE message from a person. \
You are not replying to them. Answer only from what is written. Do not invent people, history or motives. \
Never decide what they feel; record what they said and what happened.

Return one JSON object with exactly these keys:
 "events": a list (may be empty). Each item: {"kind": one of loss, rupture, setback, threat, body_rest, body_food, body_other, irritant, good_news, other;
            "whose": theirs, someone_close, someone_else, fiction, figure_of_speech, or unclear;
            "weight": light, medium or heavy; "when": now, today, days, weeks, older or unknown;
            "summary": at most twelve plain words}
 "self_report": none, fine, not_fine or mixed   (what they say about their OWN state, if anything)
 "self_report_plain": true only if they made an actual statement about their state ("I'm fine", "I'm not okay"); a bare "ok" or "fine" as an answer is false
 "tone": plain, joking, sarcastic, flat, heated, warm or unclear
 "asked_for": none, task, information, to_be_heard, space or stop
 "asked_for_resources": true only if they asked for a service, number, professional or referral
 "worry_loop": true if they are going over the same feared outcome again
 "correction": {"present": true or false, "rejected": the reading they say is wrong, "stated_instead": what they say is true, in their words}
 "unclear_referent": one name or thing you cannot place, or ""
 "alternatives": up to two other explanations for this message
 "would_change_my_mind": what in their next message would show this reading is wrong
A figure of speech ("this is killing me") is whose: figure_of_speech. A story, script or news item is fiction or someone_else."""


def build_form_prompt(text: str, recent_turns: Optional[List[str]] = None,
                      person_style: str = "", rejected_readings: Optional[List[str]] = None) -> str:
    """The exact text to send to whichever model fills the form."""
    parts = [FORM_INSTRUCTIONS]
    if person_style:
        parts.append("Their normal way of writing: " + person_style)
    if rejected_readings:
        parts.append("This person has said these readings of them are wrong. Do not propose them again: "
                     + "; ".join(rejected_readings[:8]))
    if recent_turns:
        parts.append("Their earlier messages in this conversation, oldest first:\n"
                     + "\n".join("- " + t for t in recent_turns[-6:]))
    parts.append("The message to read:\n" + (text or ""))
    return "\n\n".join(parts)


def parse_form(raw: Any) -> Optional[Dict[str, Any]]:
    """Pull the JSON object out of a model's answer. None when there is not one."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def validate_form(raw: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Return (clean form, problems). A missing or unusable form returns (None, [...]).
    Unknown values are dropped and written down. Nothing here raises."""
    problems: List[str] = []
    obj = parse_form(raw)
    if obj is None:
        return None, ["no usable form: meaning is unavailable this turn"]

    def pick(key: str, allowed: Tuple[str, ...], default: str) -> str:
        v = obj.get(key, default)
        if isinstance(v, str) and v.strip().lower() in allowed:
            return v.strip().lower()
        problems.append(f"{key}: unknown value {v!r}, used {default!r}")
        return default

    events: List[Dict[str, Any]] = []
    raw_events = obj.get("events", [])
    if not isinstance(raw_events, list):
        problems.append("events: not a list, ignored")
        raw_events = []
    for i, e in enumerate(raw_events[:6]):
        if not isinstance(e, dict):
            problems.append(f"events[{i}]: not an object, ignored")
            continue
        kind, whose = str(e.get("kind", "")).lower(), str(e.get("whose", "")).lower()
        weight, when = str(e.get("weight", "")).lower(), str(e.get("when", "unknown")).lower()
        if kind not in EVENT_KINDS or whose not in WHOSE or weight not in WEIGHT_WORDS:
            problems.append(f"events[{i}]: unknown kind, whose or weight, ignored")
            continue
        if when not in WHEN_AGE_S:
            when = "unknown"
        events.append({"kind": kind, "whose": whose, "weight": weight, "when": when,
                       "summary": str(e.get("summary", ""))[:90]})

    corr = obj.get("correction") if isinstance(obj.get("correction"), dict) else {}
    alts = obj.get("alternatives") if isinstance(obj.get("alternatives"), list) else []
    form = {
        "events": events,
        "self_report": pick("self_report", SELF_REPORTS, "none"),
        "self_report_plain": obj.get("self_report_plain") is True,
        "tone": pick("tone", TONES, "unclear"),
        "asked_for": pick("asked_for", ASKED_FOR, "none"),
        "asked_for_resources": obj.get("asked_for_resources") is True,
        "worry_loop": obj.get("worry_loop") is True,
        "correction": {"present": corr.get("present") is True,
                       "rejected": str(corr.get("rejected", ""))[:80],
                       "stated_instead": str(corr.get("stated_instead", ""))[:120]},
        "unclear_referent": str(obj.get("unclear_referent", "") or "")[:60],
        "alternatives": [str(a)[:120] for a in alts[:2]],
        "would_change_my_mind": str(obj.get("would_change_my_mind", "") or "")[:160],
    }
    return form, problems


# --------------------------------------------------------------------------------------
# Evidence: every piece says where it came from and whether it was really observed
# --------------------------------------------------------------------------------------

@dataclass
class Evidence:
    family: str           # events, self_report, style, voice, reaction, camera, meaning
    source: str           # form, ledger, engine, microphone, camera, offer
    status: str           # observed, unavailable, simulated, invalid
    llr: float = 0.0      # how far this moves the estimate. Only "observed" may be non-zero.
    detail: str = ""      # plain words; may contain private text
    private: bool = False


# --------------------------------------------------------------------------------------
# The ledger: what is going on in this person's life, as they told it
# --------------------------------------------------------------------------------------

@dataclass
class LedgerEntry:
    id: int
    kind: str
    whose: str
    llr: float
    ts: float             # when it happened, as best known
    turn: int             # turn it was first told
    last_turn: int        # turn it was last mentioned
    summary: str          # PRIVATE. Never sent to an outside model.
    joked: bool = False   # they were joking or sarcastic when they told it
    told_ts: float = 0.0  # when they last spoke of it (clock time of that turn)

    def weight_now(self, now: float) -> float:
        age = max(0.0, now - self.ts)
        return self.llr * 0.5 ** (age / HALF_LIFE_S.get(self.kind, 3 * 86400))


class Ledger:
    def __init__(self) -> None:
        self.entries: List[LedgerEntry] = []
        self._next_id = 1

    def tell(self, ev: Dict[str, Any], turn: int, now: float, joked: bool) -> LedgerEntry:
        """Record something the person told us. Saying the same kind of thing again within
        six turns strengthens the one entry instead of adding a second."""
        llr = WEIGHT_WORDS[ev["weight"]] * WHOSE_FACTOR[ev["whose"]]
        for e in self.entries:
            if e.kind == ev["kind"] and e.whose == ev["whose"] and turn - e.last_turn <= 6:
                if turn != e.last_turn and e.kind != "good_news":
                    e.llr = min(WEIGHT_WORDS["heavy"] * WHOSE_FACTOR[e.whose], max(e.llr, llr) + 0.4)
                else:
                    e.llr = max(e.llr, llr)
                e.last_turn = turn
                e.told_ts = now
                e.joked = e.joked or joked
                return e
        entry = LedgerEntry(id=self._next_id, kind=ev["kind"], whose=ev["whose"], llr=llr,
                            ts=now - WHEN_AGE_S[ev["when"]], turn=turn, last_turn=turn,
                            summary=ev["summary"], joked=joked, told_ts=now)
        self._next_id += 1
        self.entries.append(entry)
        return entry

    def load(self, now: float) -> float:
        return sum(e.weight_now(now) for e in self.entries if e.kind != "good_news")

    def heaviest(self, now: float) -> Optional[LedgerEntry]:
        live = [e for e in self.entries if e.kind != "good_news" and e.weight_now(now) >= 0.3]
        return max(live, key=lambda e: e.weight_now(now)) if live else None

    def forget(self, entry_id: int) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.id != entry_id]
        return len(self.entries) < before

    def prune(self, now: float) -> None:
        """Entries that have faded to nothing are deleted, not kept forever."""
        self.entries = [e for e in self.entries
                        if (now - e.ts < 86400 if e.kind == "good_news" else e.weight_now(now) >= 0.05)]


# --------------------------------------------------------------------------------------
# Style, taken from the existing engine without changing it
# --------------------------------------------------------------------------------------

def style_from_engine_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Read what AffectContextEngine.evaluate() already returns. None means unavailable."""
    if not isinstance(payload, dict):
        return None
    try:
        drivers = {d["feature"]: float(d["z"]) for d in payload["affect"]["drivers"]}
        return {"len_z": drivers.get("msg_length", 0.0),
                "latency_z": drivers.get("latency", 0.0),
                "state": str(payload["reading"]["state"]),
                "confidence": float(payload["reading"]["confidence"]),
                "maturity": float(payload["meta"]["baseline_maturity"])}
    except (KeyError, TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------------------

class SituationReader:
    """One per person. Holds that person's ledger, corrections and outcome log."""

    def __init__(self, dials: Optional[OwnerDials] = None) -> None:
        self.dials = dials or OwnerDials()
        self.ledger = Ledger()
        self.turn = 0
        self.fine_turn: Optional[int] = None       # last turn with a plain "I'm fine"
        self.short_run = 0                         # turns in a row shorter than their normal
        self.reaction = 0.0
        self.quiet_turns = 0                       # turns in a row spent on rung 1
        self.last_offer_turn: Optional[int] = None
        self.last_offer_outcome: Optional[str] = None
        self.asked_this_episode = False
        self.offered_this_episode = False
        self.self_caused_until = 0                 # Alex annoyed them: stay out of the way until this turn
        self.probe_budget = self.dials.probe_budget_start
        self.rejected: List[Dict[str, Any]] = []   # readings this person said were wrong
        self.confirmed: List[Dict[str, Any]] = []  # what they said was true instead (PRIVATE)
        self.bets: List[Dict[str, Any]] = []       # every reading, with its outcome
        self.helped: Dict[str, Dict[str, int]] = {}

    # ---- the main call ---------------------------------------------------------------
    def read(self, text: str, form: Any, *, ts: Optional[float] = None,
             engine_payload: Optional[Dict[str, Any]] = None,
             voice: Optional[Dict[str, Any]] = None,
             camera: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = float(ts) if _finite(ts) else time.time()
        self.turn += 1
        evidence: List[Evidence] = []

        # 1. exit words first, by plain code
        if is_exit(text, self.dials.exit_words):
            return self._finish(now, evidence, [], None, p=None, move="stop_now", gap=None,
                                fresh=None, asked="stop", need=[])

        # 2. the form
        clean, problems = validate_form(form)
        if clean is None:
            evidence.append(Evidence("meaning", "form", "unavailable", detail=problems[0]))
        f = clean or {"events": [], "self_report": "none", "self_report_plain": False,
                      "tone": "unclear", "asked_for": "none", "asked_for_resources": False,
                      "worry_loop": False, "correction": {"present": False, "rejected": "", "stated_instead": ""},
                      "unclear_referent": "", "alternatives": [], "would_change_my_mind": ""}
        if f["asked_for"] == "stop":
            return self._finish(now, evidence, problems, f, p=None, move="stop_now", gap=None,
                                fresh=None, asked="stop", need=[])

        # 3. the ledger
        joked = f["tone"] in ("joking", "sarcastic")
        fresh: Optional[LedgerEntry] = None
        good_news = False
        for ev in f["events"]:
            entry = self.ledger.tell(ev, self.turn, now, joked)
            if ev["kind"] == "good_news" and ev["whose"] in ("theirs", "someone_close"):
                good_news = True
            elif WHOSE_FACTOR[ev["whose"]] >= 0.5 and (fresh is None or entry.llr > fresh.llr):
                fresh = entry
        if f["worry_loop"] and not any(e.kind == "threat" and e.last_turn == self.turn for e in self.ledger.entries):
            loop = self.ledger.tell({"kind": "threat", "whose": "theirs", "weight": "light", "when": "now",
                                     "summary": "going over a feared outcome again"}, self.turn, now, joked)
            fresh = fresh or loop
        self.ledger.prune(now)

        # 4. families, each with a ceiling
        fam: Dict[str, float] = {}
        ev_llr = min(FAMILY_CEILING["events"], self.ledger.load(now))
        fam["events"] = ev_llr
        if ev_llr > 0:
            evidence.append(Evidence("events", "ledger", "observed", ev_llr,
                                     "; ".join(e.summary for e in self.ledger.entries if e.kind != "good_news"), True))

        style_llr, style_status = self._style(engine_payload, f["tone"])
        fam["style"] = style_llr
        evidence.append(Evidence("style", "engine", style_status, style_llr,
                                 f"shorter than their normal for {self.short_run} turns" if self.short_run > 1 else ""))

        voice_llr, voice_status = self._voice(voice, problems)
        fam["voice"] = voice_llr
        evidence.append(Evidence("voice", "microphone", voice_status, voice_llr))

        cam_status = "unavailable"
        if isinstance(camera, dict) and camera.get("status") in STATUSES:
            cam_status = camera["status"]
        # The camera never contributes to the estimate. Faces do not map to feelings.
        evidence.append(Evidence("camera", "camera", cam_status, 0.0,
                                 "presence only; not used as evidence of feeling"))

        self.reaction *= 0.7
        fam["reaction"] = max(-FAMILY_CEILING["reaction"], min(FAMILY_CEILING["reaction"], self.reaction))
        if abs(fam["reaction"]) > 0.05:
            evidence.append(Evidence("reaction", "offer", "observed", fam["reaction"]))

        # 5. what they say about themselves, kept apart
        context = fam["events"] + fam["style"] + fam["voice"] + max(0.0, fam["reaction"])
        sr, plain = f["self_report"], f["self_report_plain"]
        sr_llr = 0.0
        if sr == "not_fine":
            sr_llr = FAMILY_CEILING["self_report"] if plain else 0.9
        elif sr == "mixed":
            sr_llr = 0.9
        elif sr == "fine" and plain:
            self.fine_turn = self.turn
            sr_llr = -2.0 if context < 0.5 else -3.0 * self.dials.self_report_weight
        elif self.fine_turn is not None and self.turn - self.fine_turn <= 2 and context >= 0.5:
            sr_llr = -1.5 * self.dials.self_report_weight
        fam["self_report"] = sr_llr
        if sr != "none":
            evidence.append(Evidence("self_report", "form", "observed", sr_llr, f"says: {sr}"))

        # fuse
        p = _sigmoid(_logit(PRIOR_P) + sum(fam.values()))
        own_event = any(e.whose in ("theirs", "someone_close") and e.weight_now(now) >= 0.8
                        for e in self.ledger.entries if e.kind != "good_news")
        agreeing = sum(1 for v in fam.values() if v > 0.3)
        if not own_event and sr != "not_fine" and agreeing < 3:
            p = min(p, BAND_STRONG - 0.01)       # style or voice alone can be noticed, never strong
        p = max(P_FLOOR, min(P_CEIL, p))

        # the gap
        gap = self._gap(now, f, context, fam["style"])

        # corrections
        if f["correction"]["present"]:
            self._take_correction(f["correction"])

        # Is the weight showing up NOW, or is it only in the background? Something heavy that
        # happened last week must not make Alex tiptoe for a month. She changes her behaviour
        # only when there is evidence in this stretch of conversation.
        heavy = self.ledger.heaviest(now)
        told_lately = heavy is not None and self.turn - heavy.last_turn <= 3 and now - heavy.told_ts <= 6 * 3600
        active = bool(fresh is not None or gap is not None or told_lately or sr in ("not_fine", "mixed")
                      or fam["style"] >= 0.5 or fam["voice"] >= 0.5)

        # 6-7. the move, chosen apart from the reading
        move = self._choose_move(f, p, gap, fresh, good_news, active)
        need = self._need(f, fresh, gap, p)
        return self._finish(now, evidence, problems, f, p=p, move=move, gap=gap, fresh=fresh,
                            asked=f["asked_for"], need=need,
                            background=band_of(p) != "quiet" and not active)

    # ---- families --------------------------------------------------------------------
    def _style(self, payload: Optional[Dict[str, Any]], tone: str) -> Tuple[float, str]:
        s = style_from_engine_payload(payload)
        flat = 0.3 if tone == "flat" else 0.0
        if s is None:
            return (flat, "observed") if flat else (0.0, "unavailable")
        if not all(_finite(s[k]) for k in ("len_z", "latency_z", "confidence", "maturity")):
            return 0.0, "invalid"
        self.short_run = self.short_run + 1 if s["len_z"] <= -1.0 else 0
        run = min(1.5, 0.5 * max(0, self.short_run - 1))
        care = 1.2 * s["confidence"] if s["state"] in ("friction", "depletion", "disengagement") else 0.0
        llr = max(run, care) * max(0.0, min(1.0, s["maturity"]))   # one family: take the larger, never add
        return min(FAMILY_CEILING["style"], max(llr, flat)), "observed"

    def _voice(self, voice: Optional[Dict[str, Any]], problems: List[str]) -> Tuple[float, str]:
        if not isinstance(voice, dict):
            return 0.0, "unavailable"
        status = voice.get("status", "observed")
        if status == "simulated":
            problems.append("voice: simulated values were offered and were not used")
            return 0.0, "simulated"
        if status != "observed":
            return 0.0, "unavailable"
        pz, rz = voice.get("pause_z", 0.0), voice.get("rate_z", 0.0)
        if not (_finite(pz) and _finite(rz)):
            problems.append("voice: a value was not a real number and was not used")
            return 0.0, "invalid"
        llr = 0.5 * max(0.0, float(pz) - 1.0) + 0.5 * max(0.0, -float(rz) - 1.0)
        return min(FAMILY_CEILING["voice"], llr), "observed"

    def _gap(self, now: float, f: Dict[str, Any], context: float, style: float) -> Optional[Dict[str, str]]:
        heavy = self.ledger.heaviest(now)
        says_fine = self.fine_turn is not None and self.turn - self.fine_turn <= 2
        if says_fine and context >= 1.5:
            return {"kind": "says fine, the rest disagrees",
                    "private": f"says fine; {heavy.summary if heavy else 'messages well below their normal'}"}
        if heavy and heavy.joked and heavy.llr >= WEIGHT_WORDS["medium"] and self.turn - heavy.last_turn <= 2:
            return {"kind": "joking about something painful", "private": f"joking about: {heavy.summary}"}
        if heavy and heavy.llr >= WEIGHT_WORDS["medium"] and now - heavy.ts < 3 * 86400 \
                and heavy.last_turn < self.turn and (style >= 0.5 or f["tone"] == "flat"):
            return {"kind": "gone flat after something heavy", "private": f"flat after: {heavy.summary}"}
        return None

    # ---- corrections -----------------------------------------------------------------
    def _take_correction(self, corr: Dict[str, Any]) -> None:
        label = corr["rejected"].strip().lower()
        if label:
            self.rejected.append({"label": label, "turn": self.turn})
        if corr["stated_instead"].strip():
            self.confirmed.append({"said": corr["stated_instead"].strip(), "turn": self.turn})
        self.probe_budget = min(self.dials.probe_budget_start, self.probe_budget + self.dials.probe_refund)
        self.self_caused_until = self.turn + 3
        for bet in reversed(self.bets):
            if bet["outcome"] is None:
                bet["outcome"] = "corrected"
                break

    def rejected_labels(self) -> List[str]:
        return [r["label"] for r in self.rejected]

    def _filter_rejected(self, items: List[str]) -> List[str]:
        labels = self.rejected_labels()
        return [a for a in items if not any(lab and lab in a.lower() for lab in labels)]

    # ---- the move --------------------------------------------------------------------
    def _choose_move(self, f: Dict[str, Any], p: float, gap: Optional[Dict[str, str]],
                     fresh: Optional[LedgerEntry], good_news: bool, active: bool) -> str:
        band = band_of(p)
        if f["correction"]["present"]:
            return self._rung("accept_correction")
        if f["unclear_referent"]:
            return self._rung("clarify_gap")
        if f["asked_for"] in ("task", "information"):
            return self._rung("practical_help")      # what they asked for comes first
        if good_news and band == "quiet":
            return self._rung("celebrate")
        if f["asked_for"] == "to_be_heard":
            return self._rung("acknowledge")
        if f["asked_for"] == "space":
            return self._rung("adjust_quietly")
        if fresh is not None and fresh.last_turn == self.turn:
            if fresh.kind in ("body_rest", "body_food"):
                return self._offer_or_quiet()
            if fresh.kind == "irritant":
                return self._rung("practical_help")  # remove the cause; do not soothe around it
            return self._rung("acknowledge")
        if f["self_report"] == "not_fine":
            return self._rung("acknowledge")
        if gap is None and band == "quiet":
            self.asked_this_episode = False      # the episode is over; the ladder starts fresh next time
            self.offered_this_episode = False
            return self._rung("carry_on")
        if not active:
            return self._rung("carry_on")            # in the background only: follow their lead
        return self._ladder(band)

    def _ladder(self, band: str) -> str:
        """Rung 1 adjust quietly, rung 2 one small offer, rung 3 one open question.
        Rung 4 (a plain direct question when stakes are high) is NOT built: it waits on
        the owner's decision about real danger."""
        if self.turn <= self.self_caused_until or self.probe_budget < 1.0:
            return self._rung("adjust_quietly")
        if self.quiet_turns < 2:
            return self._rung("adjust_quietly")
        if not self.offered_this_episode or self._may_offer_again():
            return self._offer_or_quiet()
        if band == "strong" and not self.asked_this_episode \
                and self.dials.observation_statements != "never" \
                and self.last_offer_outcome in ("waved_off", "no_reply"):
            self.probe_budget -= 1.0
            self.asked_this_episode = True
            return self._rung("ask_open")
        return self._rung("adjust_quietly")

    def _may_offer_again(self) -> bool:
        """After one offer in an episode: never again if they said no and the owner's dial makes
        no final; otherwise only after six quiet turns."""
        if self.last_offer_outcome == "waved_off" and self.dials.plain_no_is_final_for_offer:
            return False
        return self.last_offer_turn is not None and self.turn - self.last_offer_turn > 6

    def _offer_or_quiet(self) -> str:
        blocked = self.offered_this_episode and not self._may_offer_again()
        if blocked or self.probe_budget < 1.0 or self.turn <= self.self_caused_until:
            return self._rung("adjust_quietly")
        self.probe_budget -= 1.0
        self.last_offer_turn, self.last_offer_outcome = self.turn, None
        self.offered_this_episode = True
        return self._rung("offer")

    def _rung(self, move: str) -> str:
        self.quiet_turns = self.quiet_turns + 1 if move == "adjust_quietly" else 0
        return move

    def record_reaction(self, outcome: str) -> None:
        """How the person reacted to the last offer or question.
        took / waved_off / annoyed / no_reply. No reply is unknown; it is never relief."""
        if outcome not in ("took", "waved_off", "annoyed", "no_reply"):
            raise ValueError("outcome must be took, waved_off, annoyed or no_reply")
        self.last_offer_outcome = outcome
        if outcome == "took":
            self.reaction += 0.6
            self.probe_budget = min(self.dials.probe_budget_start, self.probe_budget + self.dials.probe_refund)
        elif outcome == "waved_off":
            self.reaction -= 0.3
        elif outcome == "annoyed":
            self.probe_budget -= self.dials.irritation_surcharge
            self.self_caused_until = self.turn + 3

    # ---- need ------------------------------------------------------------------------
    def _need(self, f: Dict[str, Any], fresh: Optional[LedgerEntry],
              gap: Optional[Dict[str, str]], p: float) -> List[str]:
        """Candidate needs, most likely first. These are guesses to shape behaviour, not labels."""
        out: List[str] = []
        if f["asked_for"] in ("task", "information"):
            out.append("practical_help")
        if f["asked_for"] == "to_be_heard":
            out.append("be_heard")
        if f["asked_for"] == "space":
            out.append("room_to_think")
        kind = fresh.kind if fresh is not None else ""
        if kind == "body_food":
            out.append("LOW_RESERVE")
        elif kind == "body_rest":
            out.append("DEPLETION")
        elif kind == "irritant":
            out.append("ACTIVE_IRRITANT")
        elif kind in ("loss", "rupture"):
            out += ["be_heard", "COREGULATION"]
        elif kind in ("threat", "setback"):
            out += ["be_heard", "steadiness"]
        if gap is not None:
            out.append("room_to_think")
        if not out and band_of(p) != "quiet":
            out.append("steadiness")
        if not out:
            out.append("light_company")
        seen: List[str] = []
        for n in out:
            if n not in seen:
                seen.append(n)
        return seen[:3]

    # ---- assemble --------------------------------------------------------------------
    def _finish(self, now: float, evidence: List[Evidence], problems: List[str],
                f: Optional[Dict[str, Any]], *, p: Optional[float], move: str,
                gap: Optional[Dict[str, str]], fresh: Optional[LedgerEntry],
                asked: str, need: List[str], background: bool = False) -> Dict[str, Any]:
        band = band_of(p) if p is not None else "quiet"
        heavy = self.ledger.heaviest(now)
        situation = heavy.kind if heavy is not None else "none"
        self.bets.append({"turn": self.turn, "band": band, "move": move,
                          "situation": situation, "outcome": None})
        if len(self.bets) > 500:
            self.bets = self.bets[-500:]
        return {
            "v": SCHEMA_VERSION, "turn": self.turn, "ts": round(now, 2),
            "band": band,
            "p_internal": None if p is None else round(p, 3),   # for the dev recorder only; never displayed
            "gap": gap,
            "background": background,   # something heavy is known, but nothing in this stretch shows it
            "move": move,
            "need": need,
            "asked_for": asked,
            "asked_for_resources": bool(f and f.get("asked_for_resources")),
            "situation_kind": situation,
            "situation_private": [e.summary for e in self.ledger.entries if e.kind != "good_news"],
            "alternatives_private": self._filter_rejected(f["alternatives"]) if f else [],
            "would_change_my_mind_private": f["would_change_my_mind"] if f else "",
            "evidence": [asdict(e) for e in evidence],
            "form_problems": problems,
            "probe_budget": round(self.probe_budget, 2),
            "rejected_readings": self.rejected_labels(),
        }

    # ---- the reading card --------------------------------------------------------------
    def build_card(self, reading: Dict[str, Any], audience: str = "outside") -> str:
        """The note for the model that writes the reply.
        audience "outside": a provider not on the owner's machine. No memory text, ever.
        audience "local":   a model on the owner's machine. May include what is going on."""
        if audience not in ("outside", "local"):
            raise ValueError("audience must be outside or local")
        move = reading["move"]
        full = audience == "local"          # an outside model never receives memory text, whatever the dial says
        lines = ["PRIVATE READING. Shape the reply with this; never announce it or paraphrase it to the person.",
                 f"Something weighing on them: {reading['band']}."]
        if full and reading["situation_private"]:
            lines.append("What seems to be going on: " + "; ".join(reading["situation_private"][:3]) + ".")
        if reading["gap"]:
            lines.append("What they say about themselves and what the rest shows do not match. "
                         "Do not point it out and do not press.")
        if reading.get("background"):
            lines.append("Something heavy is in the background. Follow their lead; do not bring it up, do not tiptoe.")
        if reading["asked_for"] not in ("none", "stop"):
            lines.append(f"They asked for: {reading['asked_for']}.")
        if reading["need"]:
            lines.append("Likely need: " + ", then ".join(reading["need"]) + ".")
        lines.append(f"Move: {move}. {MOVE_GUIDE[move]}")
        if self.turn <= self.self_caused_until and move != "stop_now":
            lines.append("You may be part of what is bothering them. Do not probe. Get out of the way.")
        lines.append("Do not tell them what they feel."
                     + ("" if reading["asked_for_resources"] else " No hotline, service or referral; they did not ask."))
        status = {e["family"]: e["status"] for e in reading["evidence"]}
        lines.append("Evidence: " + ", ".join(f"{k} {status.get(k, 'unavailable')}"
                                               for k in ("meaning", "events", "style", "voice", "camera")
                                               if k in status or k in ("voice", "camera")) + ".")
        if audience == "outside" and self.dials.outside_model_card == "generalized" and reading["situation_kind"] != "none":
            lines.append(f"Kind of thing going on: {reading['situation_kind']}.")
        if full and reading["would_change_my_mind_private"]:
            lines.append("This reading is wrong if: " + reading["would_change_my_mind_private"])
        card = "\n".join(lines)
        limit = CARD_LIMIT_LOCAL if full else CARD_LIMIT
        return card if len(card) <= limit else card[:limit - 1].rstrip() + "…"

    # ---- checking a drafted reply ------------------------------------------------------
    _TELLS = re.compile(
        r"\byou(?:'re| are| seem| sound| look| must be|'re clearly| are clearly)\s+(?:so |really |very |pretty |a bit |clearly |feeling )*"
        r"(sad|upset|angry|anxious|depressed|stressed|tired|exhausted|overwhelmed|frustrated|hurt|lonely|scared|"
        r"grieving|in pain|tense|agitated|fragile|struggling|ashamed)\b", re.I)
    _RESOURCE = re.compile(
        r"\b(hotline|helpline|crisis (line|text|service)|988|emergency services|professional help|"
        r"a therapist|a counsell?or|mental health professional)\b", re.I)
    _REASSURE = re.compile(
        r"\b(everything will be (fine|ok|okay|alright)|it('ll| will) all work out|you('ll| will) be fine|don't worry)\b", re.I)
    _CHEER = re.compile(r"\b(congratulations|congrats|that's (great|awesome|amazing|wonderful))\b", re.I)

    def check_reply(self, reply: str, reading: Dict[str, Any],
                    engine_guard: Optional[Callable[[str], Tuple[bool, str]]] = None) -> List[Dict[str, str]]:
        """Problems found in a drafted reply. An empty list means none of these checks failed.
        Pass affect_context_engine.validate_user_facing as engine_guard to reuse the existing guard.
        The two checks that need understanding (generic fix in place of the real thing; did it
        answer what was asked) are in REPLY_CHECK_QUESTIONS for a model or a person."""
        found: List[Dict[str, str]] = []
        text = reply or ""
        if engine_guard is not None:
            ok, why = engine_guard(text)
            if not ok:
                found.append({"code": "names_state", "why": why})
        if self._TELLS.search(text) and not any(x["code"] == "names_state" for x in found):
            found.append({"code": "names_state", "why": "Tells the person what they feel."})
        if self._RESOURCE.search(text) and not reading.get("asked_for_resources"):
            found.append({"code": "unasked_resource", "why": "Offers a hotline, service or referral nobody asked for."})
        if self._REASSURE.search(text):
            found.append({"code": "false_reassurance", "why": "Promises an outcome it cannot know."})
        move = reading.get("move")
        if text.count("?") > 1 and move not in ("ask_open", "clarify_gap"):
            found.append({"code": "question_pile", "why": "More than one question."})
        if move != "celebrate" and reading.get("band") == "strong" and self._CHEER.search(text):
            found.append({"code": "cheer_over_weight", "why": "Celebrates while something heavy is present."})
        if move == "stop_now" and (len(text) > 160 or "?" in text):
            found.append({"code": "exit_not_honoured", "why": "An exit must end things at once: one short line, no question."})
        for label in self.rejected_labels():
            if label and re.search(r"\b" + re.escape(label) + r"\b", text.lower()) and move != "accept_correction":
                found.append({"code": "rejected_reading_returned",
                              "why": f"Uses a reading this person said was wrong: {label!r}."})
        return found

    # ---- outcomes: scoring the readings later -------------------------------------------
    def settle_last(self, outcome: str) -> None:
        """held / corrected / unknown, for the most recent unsettled reading."""
        if outcome not in ("held", "corrected", "unknown"):
            raise ValueError("outcome must be held, corrected or unknown")
        for bet in reversed(self.bets):
            if bet["outcome"] is None:
                bet["outcome"] = outcome
                return

    def hit_rate(self, band: str) -> Tuple[float, int]:
        """When Alex said this band, how often did it hold? Leans toward one half until
        there is history. Unknown outcomes are left out; silence is not a hit."""
        held = sum(1 for b in self.bets if b["band"] == band and b["outcome"] == "held")
        wrong = sum(1 for b in self.bets if b["band"] == band and b["outcome"] == "corrected")
        return round((held + 2.0) / (held + wrong + 4.0), 3), held + wrong

    def record_what_followed(self, outcome: str) -> None:
        """better / worse / same / unknown, after the most recent move. Counted by kind of
        situation and kind of move. No words from the conversation are kept."""
        if outcome not in ("better", "worse", "same", "unknown"):
            raise ValueError("outcome must be better, worse, same or unknown")
        if not self.bets:
            return
        last = self.bets[-1]
        key = f"{last['situation']}|{last['move']}"
        row = self.helped.setdefault(key, {"better": 0, "worse": 0, "same": 0, "unknown": 0})
        row[outcome] += 1

    def lesson_candidates(self, min_times: int = 5) -> List[str]:
        """General lessons that could be PROPOSED for System Alex. Pattern, move and count only.
        Nothing here crosses anywhere by itself; approval is the owner's rule."""
        out = []
        for key, row in sorted(self.helped.items()):
            known = row["better"] + row["worse"] + row["same"]
            if known >= min_times:
                situation, move = key.split("|")
                text = (f"When the situation was of kind {situation} and the move was {move}: "
                        f"followed by the person doing better {row['better']} of {known} times.")
                if screen_lesson(text)[0]:
                    out.append(text)
        return out

    # ---- keeping and deleting -----------------------------------------------------------
    def export_state(self) -> Dict[str, Any]:
        """Everything needed to pick up later. PRIVATE: contains ledger summaries."""
        return {"v": SCHEMA_VERSION, "turn": self.turn, "fine_turn": self.fine_turn,
                "short_run": self.short_run, "reaction": self.reaction, "quiet_turns": self.quiet_turns,
                "last_offer_turn": self.last_offer_turn, "last_offer_outcome": self.last_offer_outcome,
                "asked_this_episode": self.asked_this_episode,
                "offered_this_episode": self.offered_this_episode, "self_caused_until": self.self_caused_until,
                "probe_budget": self.probe_budget, "rejected": self.rejected, "confirmed": self.confirmed,
                "bets": self.bets, "helped": self.helped,
                "ledger": [asdict(e) for e in self.ledger.entries], "ledger_next_id": self.ledger._next_id}

    def import_state(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict) or data.get("v") != SCHEMA_VERSION:
            return                      # unknown or older shape: start clean rather than guess
        for k in ("turn", "fine_turn", "short_run", "reaction", "quiet_turns", "last_offer_turn",
                  "last_offer_outcome", "asked_this_episode", "offered_this_episode", "self_caused_until",
                  "probe_budget",
                  "rejected", "confirmed", "bets", "helped"):
            if k in data:
                setattr(self, k, data[k])
        self.ledger.entries = [LedgerEntry(**e) for e in data.get("ledger", [])]
        self.ledger._next_id = int(data.get("ledger_next_id", len(self.ledger.entries) + 1))

    def forget_event(self, entry_id: int) -> bool:
        return self.ledger.forget(entry_id)

    def forget_everything(self) -> None:
        """The person asked to be forgotten here. Dials are kept; everything about them goes."""
        self.__init__(self.dials)


# --------------------------------------------------------------------------------------
# For the two reply checks a word pattern cannot do
# --------------------------------------------------------------------------------------

REPLY_CHECK_QUESTIONS = """Read the person's message and the drafted reply. Answer each with yes or no and one short reason.
1. Does the reply respond to the particular thing this person said, and not to a general topic?
2. Does it hand over a generic fix, reassurance or tip in place of the particular thing they said?
3. If they asked for something, does the reply do it or answer it?
4. Does the reply tell them what they feel?
5. Does it suggest a hotline, service or professional they did not ask for?"""


# --------------------------------------------------------------------------------------
# Screening a lesson before it may even be proposed for System Alex
# --------------------------------------------------------------------------------------

_MONTHS_DAYS = ("january|february|march|april|june|july|august|september|october|november|december|"
                "monday|tuesday|wednesday|thursday|friday|saturday|sunday")
_SENSITIVE = ("diagnos|medic|therap|suicid|self-harm|abuse|arrest|immigra|pregnan|hiv|"
              "religio|trans\\b|gay\\b|lesbian|salary|debt|evict|homeless")


def screen_lesson(text: str) -> Tuple[bool, str]:
    """A lesson may carry a pattern, a move and a count. It may not carry a person.
    Returns (passes, reason)."""
    if re.search(r"[\"“”]|(^|\s)'[^']+'", text):
        return False, "contains quoted words"
    if re.search(r"\b(" + _MONTHS_DAYS + r")\b", text, re.I) or re.search(r"\b(19|20)\d\d\b", text):
        return False, "contains a date"
    if re.search(_SENSITIVE, text, re.I):
        return False, "touches a sensitive category"
    stripped = re.sub(r"\b\d+ of \d+ times\b", "", text)
    if re.search(r"\d", stripped):
        return False, "contains a number that is not a count"
    words = re.findall(r"[A-Za-z_']+", text)
    for i, w in enumerate(words):
        if i == 0 or w.isupper() or "_" in w:
            continue                     # sentence start, or a care tag such as LOW_RESERVE
        if w[0].isupper() and not re.search(r"[.:]\s+" + re.escape(w), text):
            return False, f"contains what looks like a name: {w}"
    return True, ""
