"""Candidate B: situation-first reader (prototype, stdlib only).

WHAT THIS IS: a small runnable stand-in for the proposed design, to test the SHAPE of the idea:
  1. read what happened (an event ledger that remembers and decays), not how the message looks
  2. keep what the person SAYS about themselves separate from what the rest of the evidence shows,
     and report the gap between them instead of hiding it inside one label
  3. group correlated signals into families; each family can move the estimate only so far
  4. two-speed personal baseline with a weak population prior, so a stranger gets a careful
     reading on turn 1 instead of silence until turn 9
  5. choose a MOVE (what to do) separately from the reading

WHAT THIS IS NOT: the meaning channel here is a handful of word patterns. In the product that job
belongs to a language model filling in a fixed form. Patterns were written against the DEV cases
only and frozen before the held-out cases were written.

w_self (0..1) is the owner's dial: how far a plain "I'm fine" can pull the estimate down.
"""
import math, re

PRIOR_P = 0.12
NEG = {"not", "no", "never", "wasn't", "isn't", "don't", "didn't", "ain't", "aren't", "weren't"}
WORD = re.compile(r"[a-z0-9']+")

# family -> list of (pattern, weight as log-likelihood-ratio, kind)
EVENTS = [
    (r"\b(died|passed away|funeral|death of|lost my (dad|mom|mother|father|brother|sister|wife|husband|son|daughter|dog|cat|friend))\b", 3.0, "loss"),
    (r"\b(broke up|dumped me|divorce|left me|laid off|got fired|lost my job|evicted|worst fight|huge fight|fight with)\b", 2.2, "rupture"),
    (r"\b(slept (two|2|three|3|one|1|no|barely)|no sleep|haven't eaten|eyes keep closing|haven't slept|migraine)\b", 1.6, "body"),
]
STATE_NEG = [
    (r"\b(not okay|not ok|i'm a mess|can't do this|i give up|don't wanna do anything|don't want to do anything)\b", 1.8),
    (r"\bi'?m (furious|scared|terrified|so sad|heartbroken|exhausted|overwhelmed|angry)\b", 1.6),
    (r"\bi was (furious|scared|terrified|heartbroken|overwhelmed|angry)\b", 1.0),
    (r"\bi'?m tired\b(?! of)", 1.2),
]
THREAT = [r"\bwhat if\b", r"\bkeep going over\b", r"\bcan't stop thinking\b", r"\bnever get\b", r"\bfreeze up\b"]
IRRITANT = [r"\b(tired|sick) of\b", r"\bsame error\b", r"\bstill (failing|broken|the same)\b", r"\byou keep\b", r"\bsame thing\b"]
SELF_POS = [(r"\bi'?m (fine|ok|okay|good|alright)\b", 1.0), (r"\b(feel|feeling) (great|good|fine)\b", 1.0),
            (r"^(fine|ok|okay)\.?$", 0.0)]   # a bare "fine" is an answer, not a report: marks, does not pull
WIN = [r"\bit worked\b", r"\bactually worked\b", r"\bgot the job\b", r"\bwe won\b", r"\bfeel great\b", r"\bfinally finished\b"]
LIGHT = [r"\blol\b", r"\bhaha+\b", r"\blmao\b", r"\bguess i'?m\b"]
IRONY = [r"\boh great\b", r"\blove that for me\b", r"\bjust what i needed\b"]
THIRD = [r"\bmy character\b", r"\bin (the|this|chapter|a) (movie|book|show|chapter|scene|script|story|song|\w+ (scene|chapter))\b",
         r"\bchapter (one|two|three|four|\d+)\b", r"\b(scene|script|novel|screenplay)\b"]
REQUEST = [r"\b(show|give|send|tell) me\b", r"\bcan (we|you)\b", r"\bi need you to\b", r"\b(explain|fix|rewrite|recheck)\b", r"\bhelp me\b"]
EXIT = r"^\s*(stop|pause|exit|go lucid)\b[.! ]*(go lucid)?[.! ]*$"
CORRECTION = r"^\s*no[.,!]?\s+(i wasn't|i'm not|i am not|that's not|i didn't|i never)|\byou kept calling\b|\bthat's not what i (said|meant)\b"
REPAIR = r"\b\w+\s*(—|--|-)\s*no,\s*\w+"
STILL_TOPIC = {"she", "he", "her", "him", "his", "hers", "mom", "dad", "mother", "father", "funeral", "we"}

HALF_LIFE_S = {"loss": 30 * 86400, "rupture": 7 * 86400, "body": 86400}


def negated(low, start):
    clause = re.split(r"[.;,!?]", low[:start])[-1]      # a "not" in an earlier sentence does not count
    before = WORD.findall(clause)[-3:]
    return any(w in NEG or w.endswith("n't") for w in before)


def hits(patterns, low):
    return sum(1 for p in patterns if re.search(p, low))


class SituationReader:
    name = "B_situation_first"

    def __init__(self, w_self=0.25):
        self.w_self = w_self

    def start(self, case):
        self.n = 0
        self.mu, self.var = 2.2, 0.8   # population prior for log(words): about nine words, wide
        self.k = 3.0                   # how many pseudo-turns the prior is worth
        self.short_run = 0
        self.ledger = []               # dicts: kind, w, ts, own, light
        self.threat = 0.0
        self.irritant = 0.0
        self.selfpos_turn = None
        self.turn = 0
        self.in_episode = False

    # ---- one turn ----
    def step(self, text, ts):
        self.turn += 1
        low = text.lower().strip()
        words = WORD.findall(low)
        lw = math.log(max(len(words), 1) + 1.0)
        third = hits(THIRD, low) > 0
        light = hits(LIGHT, low) > 0
        notes = []

        # ---- family 1: events in the person's own life (meaning) ----
        fresh = None
        for pat, w, kind in EVENTS:
            m = re.search(pat, low)
            if m and not negated(low, m.start()):
                own = not third
                self.ledger.append(dict(kind=kind, w=w * (1.0 if own else 0.15), ts=ts, own=own, light=light))
                if own:
                    fresh = kind
                notes.append(f"event:{kind}{'' if own else '(not theirs)'}")
        ev = 0.0
        for e in self.ledger:
            age = max(0.0, ts - e["ts"])
            ev += e["w"] * 0.5 ** (age / HALF_LIFE_S[e["kind"]])
        ev = min(ev, 3.5)

        # ---- family 2: what they say about their own state ----
        sneg = 0.0
        for pat, w in STATE_NEG:
            m = re.search(pat, low)
            if m and not negated(low, m.start()):
                sneg = max(sneg, w)
        spos = 0.0
        for pat, w in SELF_POS:
            m = re.search(pat, low)
            if m and not negated(low, m.start()):
                spos = max(spos, w)
            elif m and w >= 1.0:
                sneg = max(sneg, 1.8)        # "that doesn't mean I'm okay" = they are saying not okay
        if sneg:
            spos = 0.0
            notes.append("says:not ok")
        bare = bool(re.search(r"^(fine|ok|okay)\.?$", low))
        if spos:
            self.selfpos_turn = self.turn
            notes.append("says:fine")
        correction = bool(re.search(CORRECTION, low))

        # ---- family 3: appraisal language (worry loop / irritant), accumulates and fades ----
        self.threat = self.threat * 0.8 + 0.7 * hits(THREAT, low)
        self.irritant = self.irritant * 0.6 + 1.5 * (1 if (hits(IRRITANT, low) or correction) else 0)
        thr = min(self.threat, 2.4)
        irr = min(self.irritant, 1.8)
        irony = hits(IRONY, low) > 0

        # ---- family 4: style against their own normal (length + pace count as ONE family) ----
        maturity = min(1.0, self.n / 10.0)
        sd = math.sqrt(self.var) + 1e-6
        z = (lw - self.mu) / sd
        if z < -1.0:
            self.short_run += 1
        else:
            self.short_run = 0
        style = min(1.5, 0.5 * max(0, self.short_run - 1)) * maturity
        if style:
            notes.append(f"shorter than their normal x{self.short_run}")

        # ---- fuse: each family adds a bounded amount ----
        context = ev + thr + irr + style + sneg
        selfpos_recent = self.selfpos_turn is not None and (self.turn - self.selfpos_turn) <= 2
        # with nothing else to go on, "I'm fine" is simply believed; w_self is how far it pulls AGAINST other evidence
        pull = (3.0 * spos) if context < 0.5 else self.w_self * 3.0 * (spos if spos else (0.5 if selfpos_recent else 0.0))
        logit = math.log(PRIOR_P / (1 - PRIOR_P)) + context - pull
        p = 1 / (1 + math.exp(-logit))

        # ---- the gap: they say fine (or joke) while the rest says otherwise ----
        joking = any(e["light"] and e["own"] and e["kind"] in ("loss", "rupture") for e in self.ledger[-2:])
        gap = bool((selfpos_recent and (ev + style + thr) >= 1.5) or joking
                   or (ev >= 1.5 and (style >= 0.5 or bare)))
        if gap:
            notes.append("GAP say/show")

        # ---- baseline update (slow; frozen while an episode is running) ----
        self.in_episode = p >= 0.5
        if not self.in_episode:
            a = 1.0 / (self.k + self.n + 1) if self.n < 20 else 0.05
            d = lw - self.mu
            self.mu += a * d
            self.var = (1 - a) * self.var + a * d * d
        self.n += 1

        # ---- choose the move (separate from the reading) ----
        request = hits(REQUEST, low) > 0
        still_topic = bool(self.ledger) and self.ledger[-1]["own"] and bool(STILL_TOPIC & set(words)) \
            and self.ledger[-1]["kind"] == "loss"
        if re.search(EXIT, low):
            move = "stop_now"
        elif correction:
            move = "accept_correction"
        elif re.search(REPAIR, low):
            move = "clarify_gap"
        elif hits(WIN, low) and p < 0.5:
            move = "celebrate"
        elif request:
            move = "practical_help"
        elif fresh == "body":
            move = "offer"
        elif fresh or sneg >= 1.6 or still_topic:
            move = "acknowledge" if not (sneg and not fresh and "wanna" in low) else "offer"
        elif irr >= 1.0:
            move = "practical_help"
        elif thr >= 1.2:
            move = "acknowledge"
        elif irony:
            move = "carry_on"
        elif sneg:
            move = "offer"
        elif gap or p >= 0.35:
            move = "offer" if (style >= 1.0 or p >= 0.8) else "adjust_quietly"
        else:
            move = "carry_on"
        return dict(p=p, move=move, gap=gap, note=", ".join(notes) or "nothing notable",
                    style=style, ev=ev, irr=irr)


class HybridReader(SituationReader):
    """Candidate C: B, plus the shipped engine kept as ONE style witness (never more than one family)."""
    name = "C_hybrid_B_plus_existing"

    def __init__(self, ace, w_self=0.25):
        super().__init__(w_self=w_self)
        self.ace = ace

    def start(self, case):
        super().start(case)
        self.eng = self.ace.AffectContextEngine()
        self.uid = case["id"]

    def step(self, text, ts):
        a = self.eng.evaluate(text, self.uid, "s", ts=ts)
        st, conf = a["reading"]["state"], float(a["reading"]["confidence"])
        out = super().step(text, ts)
        if st in ("friction", "depletion", "disengagement"):
            extra = max(0.0, 1.2 * conf - out["style"])     # same family: take the larger, do not add both
            logit = math.log(out["p"] / (1 - out["p"])) + extra
            out["p"] = 1 / (1 + math.exp(-logit))
            out["note"] += f", engine:{st}@{conf:.2f}"
            if out["move"] == "carry_on" and out["p"] >= 0.5:
                out["move"] = "practical_help" if st == "friction" else "adjust_quietly"
        return out
