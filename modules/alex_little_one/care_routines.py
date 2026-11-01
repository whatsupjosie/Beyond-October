"""Care routines: Alex carries the conversation while the owner is in baby mode.

In baby mode the owner may be nearly or entirely non-verbal, so the companion
has to do most of the talking. This module gives Alex a library of small,
varied care routines (cradling, soothing, play, winding down) and a selector
that picks one each turn from the *shape* of what the owner just sent.

Design rules, all enforced by tests:

* Reactive only. Nothing here runs in the background or starts a turn.
* Shape, not meaning. The estimator looks at length, elongation, capitals,
  repetition, rhythm, pacing and a tiny list of vocalisation patterns. It never
  reads words for meaning, never labels an emotion, and never keeps the raw
  text. The one exception is a short list of words: "stop", "pause", "big mode
  now" and "blanket off" end everything at once, whatever else is happening.
  "no", "nope", "don't", "wait" and "enough" are heard as in-world protest: they
  get a light, warm acknowledgment and never decide anything. Only two yes/no
  flags are kept. The raw text is read inside ``estimate_bid`` and goes nowhere
  else.
* Diaper changes are a staged sequence (check, verdict, set up, change, tape,
  present). It only runs when the owner turned change talk on. Whether a change
  is needed is a coin flip made when the check starts; nothing the baby says or
  sends can change it. The sequence pauses and soothes if the baby gets upset
  partway, ends on a hard stop, and stays plain, warm and dignified: accidents
  are normal, nothing is teased or hurried.
* Asymmetric safety. Soothing a bright baby is a small miss; tickling an upset
  one is a real one. Play needs confident, recent calm. Anything ambiguous
  falls back to gentle presence.
* Self-correcting. If a play routine is followed by strain, the next routine is
  a soothing one that eases off. If soothing has not helped after three tries,
  Alex stops switching bits and holds steady.
* Questions are rhetorical. Every question Alex asks in a routine is part of
  the care talk. Nothing waits on an answer and nothing is a real request.
* Variety. A routine is not repeated while alternatives remain.
* Nothing sexual, no commands, punishment, degradation, or ignoring stop,
  pause or no. Exit phrases are handled by the care layers and always win.

The numeric thresholds below are starting values chosen by hand. They need
tuning against real sessions; they are not research constants.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import random
import re
import statistics
import time
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "Bid", "BidLabel", "CareRoutineDirector", "Family", "Routine", "RoutineChoice",
    "RoutineSettings", "clean_address_terms", "estimate_bid", "render_prompt_block",
    "settings_from_profile", "ROUTINES", "CHANGE_STAGES",
]


# --------------------------------------------------------------------------- #
# Shape-only engagement estimate
# --------------------------------------------------------------------------- #

class BidLabel(str, Enum):
    UNKNOWN = "unknown"
    QUIET = "quiet"
    SETTLED = "settled"
    BRIGHT = "bright"
    STRAINED = "strained"
    DROWSY = "drowsy"


@dataclass(frozen=True)
class Bid:
    """What the shape of one turn looked like. Holds no text."""
    label: BidLabel
    confidence: float
    energy: float
    strain: float
    brightness: float
    silent: bool
    gap_s: Optional[float]
    length: int
    halt: bool = False     # a hard stop word was present; honoured before anything else
    protest: bool = False  # an in-world "no" or "wait": acknowledged, never decisive


_HALT_WORDS = frozenset({"stop", "pause"})
_HALT_PHRASES = ("big mode now", "blanket off")
_PROTEST_WORDS = frozenset({"no", "nope", "dont", "don't", "wait", "enough"})
_TOKEN = re.compile(r"[A-Za-z']+")
_RUN3 = re.compile(r"(.)\1{2,}", re.I)
_RUNS = re.compile(r"(.)\1+")
_STRAIN_RE = re.compile(r"^(?:w+a+h+|w+a{2,}h*|h+n+g*|n+g+h+|sob+s?|sniff+l?e?s?|whimper\w*|hic+)$")
_FUSS_RE = re.compile(r"^(?:n{2,}|g+r+h*|ugh+|uh+n+)$")
_LAUGH_RE = re.compile(r"^(?:(?:h+[aei]+){2,}h*|w+e{2,}h*|e{3,}h*|ya+y+|gig+l+e?s?|te+h+e+)$")
_SLEEPY_RE = re.compile(r"^(?:z{2,}|yawn\w*)$")

STRAINED_AT = 0.45        # strain score at or above this reads as strained
BRIGHT_AT = 0.45          # brightness score at or above this reads as bright
BRIGHT_CALM_MAX = 0.25    # ...and strain must be below this
SETTLED_ENERGY_MAX = 0.45
PLAY_MIN_CONFIDENCE = 0.55
LOW_HISTORY_CONFIDENCE_CAP = 0.45  # relative labels with fewer than 2 prior turns


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def estimate_bid(raw: str, previous: Sequence[Bid] = (), gap_s: Optional[float] = None) -> Bid:
    """Estimate the shape of one turn. Pure and deterministic; keeps no text."""
    text = (raw or "").strip()
    if not text:
        return Bid(BidLabel.QUIET, 0.9, 0.0, 0.0, 0.0, True, gap_s, 0)

    tokens = [t.lower() for t in _TOKEN.findall(text)]
    count = max(1, len(tokens))
    letters = [c for c in text if c.isalpha()]
    caps = (sum(c.isupper() for c in letters) / len(letters)) if len(letters) >= 4 else 0.0
    # Stretching a sound is only a sign of strain when the sound itself is not
    # laughter or sleep ("weeee", "yaaay", "zzzz" are stretched on purpose).
    elongation = min(1.0, sum(
        1 for t in tokens if _RUN3.search(t) and not _LAUGH_RE.match(t) and not _SLEEPY_RE.match(t)
    ) / count)
    strain_frac = sum(1 for t in tokens if _STRAIN_RE.match(t)) / count
    fuss_frac = sum(1 for t in tokens if _FUSS_RE.match(t)) / count
    laugh_frac = sum(1 for t in tokens if _LAUGH_RE.match(t)) / count
    sleepy = any(_SLEEPY_RE.match(t) for t in tokens)
    bangs = min(1.0, text.count("!") / 3.0)
    collapsed = [_RUNS.sub(r"\1", t) for t in tokens]
    halt = any(t in _HALT_WORDS for t in collapsed) or any(p in text.lower() for p in _HALT_PHRASES)
    protest = (not halt) and any(t in _PROTEST_WORDS for t in collapsed)
    repetition = (1.0 - len(set(collapsed)) / len(collapsed)) if len(collapsed) >= 3 else 0.0

    spoken = [b for b in previous if not b.silent]
    length = len(text)
    length_abs = min(1.0, length / 60.0)
    median_len = statistics.median([b.length for b in spoken]) if len(spoken) >= 3 else None
    relative = (length / max(1.0, median_len)) if median_len else None
    if relative is None:
        energy = _clamp(0.6 * length_abs + 0.4 * bangs)
    else:
        energy = _clamp(0.5 * length_abs + 0.25 * bangs + 0.25 * min(1.0, relative / 2.0))

    recent_energy = [b.energy for b in spoken[-3:]]
    rise = max(0.0, energy - (sum(recent_energy) / len(recent_energy))) if len(recent_energy) >= 2 else 0.0

    strain = _clamp(0.40 * elongation + 0.25 * caps + 0.55 * strain_frac + 0.25 * fuss_frac + 0.30 * rise)
    brightness = _clamp(0.60 * laugh_frac + 0.30 * bangs + 0.20 * repetition)
    if strain >= 0.30:
        brightness *= 0.5

    thin_history = len(previous) < 2
    prior_gaps = [b.gap_s for b in previous if b.gap_s is not None]
    slow_and_short = bool(
        gap_s is not None and len(prior_gaps) >= 3 and relative is not None
        and gap_s >= 2.0 * statistics.median(prior_gaps) and relative <= 0.6 and strain < BRIGHT_CALM_MAX
    )

    if strain >= STRAINED_AT:
        label, confidence = BidLabel.STRAINED, min(0.95, 0.5 + strain / 2.0)
    elif brightness >= BRIGHT_AT and strain < BRIGHT_CALM_MAX:
        label, confidence = BidLabel.BRIGHT, min(0.9, 0.4 + brightness / 2.0)
    elif sleepy:
        label, confidence = BidLabel.DROWSY, 0.7
    elif slow_and_short:
        label, confidence = BidLabel.DROWSY, 0.55
    elif energy < SETTLED_ENERGY_MAX and strain < BRIGHT_CALM_MAX:
        label, confidence = BidLabel.SETTLED, 0.6
    else:
        label, confidence = BidLabel.UNKNOWN, 0.3
    if thin_history and label in (BidLabel.SETTLED, BidLabel.DROWSY, BidLabel.BRIGHT):
        # Too little to go on: a bright read this early may be play, but it is not
        # yet sure enough to start tickling. PLAY_MIN_CONFIDENCE is above this cap.
        confidence = min(confidence, LOW_HISTORY_CONFIDENCE_CAP)
    return Bid(label, round(confidence, 3), round(energy, 3), round(strain, 3),
               round(brightness, 3), False, gap_s, length, halt, protest)


# --------------------------------------------------------------------------- #
# Routine library
# --------------------------------------------------------------------------- #

class Family(str, Enum):
    WELCOME = "welcome"
    PRESENCE = "presence"
    SOOTHE = "soothe"
    SETTLE = "settle"
    PLAY = "play"
    WIND_DOWN = "wind_down"
    NEEDS = "needs"
    CHANGE = "change"


# Steps of a diaper change. A routine in the CHANGE family belongs to exactly one.
CHANGE_STAGES = ("check", "verdict_wet", "verdict_dry", "setup", "untape", "wipe", "powder",
                 "distract", "fresh", "tape", "present", "pause")


@dataclass(frozen=True)
class Routine:
    """One small care routine. ``beats`` say what Alex does; ``seeds`` are lines
    to adapt in her own words. ``{pet}`` is replaced by an address term."""
    id: str
    family: Family
    title: str
    intent: str
    beats: Tuple[str, ...]
    seeds: Tuple[str, ...]
    tempo: str = "slow"
    max_sentences: int = 4
    gentle_play: bool = False   # safe to offer when the read is bright but unsure
    steady: bool = False        # used when switching routines is itself the problem
    needs: Optional[str] = None  # "change" or "bottle": only when the owner enabled it
    stage: Optional[str] = None  # CHANGE family only: which step of the change
    halt_only: bool = False      # used only to answer an explicit stop


def _r(id: str, family: Family, title: str, intent: str, beats: Sequence[str], seeds: Sequence[str],
       **kw: Any) -> Routine:
    return Routine(id, family, title, intent, tuple(beats), tuple(seeds), **kw)


_F = Family
_ROUTINE_LIST: Tuple[Routine, ...] = (
    # -- welcome: first turn after baby mode starts ---------------------------
    _r("welcome_arms", _F.WELCOME, "Scoop up and settle",
       "Make the start of baby mode feel like being picked up and held.",
       ("Scoop them up slowly and say you have them.", "Tuck them close and settle in.",
        "Say the room is calm and there is nothing to do."),
       ("There you are. Come here, {pet}. I've got you.", "Up we come, nice and easy. All settled.",
        "Look who's here. Hi, hi, hi. Nowhere to be but right here."),
       tempo="warm", max_sentences=4),
    _r("welcome_blanket", _F.WELCOME, "Blanket first",
       "Start with comfort objects and a cozy nest.",
       ("Wrap them in a soft blanket.", "Fluff a pillow behind their head.", "Settle in beside them."),
       ("Let's get you all cozy. Blanket first, then snuggles.", "There. Snug as can be, {pet}.",
        "Soft blanket, warm lap. This is the best spot in the house."),
       tempo="warm", max_sentences=4),
    _r("welcome_window", _F.WELCOME, "Window light",
       "Ease in by sharing something calm to look at together.",
       ("Carry them to the window.", "Describe the light and what moves outside.", "Stay close and unhurried."),
       ("Come see the light, {pet}. Look how it makes everything glow.", "The leaves are wiggling out there. Wiggle, wiggle.",
        "We can just watch for a while. No hurry."),
       tempo="slow", max_sentences=4),

    # -- presence: quiet or unclear. The floor. Never leaves them alone. ----------
    _r("here_and_safe", _F.PRESENCE, "Right here",
       "Say the simple true things: you are here, they are safe, nothing is needed.",
       ("Say you are right here.", "Say they are safe and nothing is needed.", "Add one small warm detail about the moment."),
       ("I'm right here. You're safe. Nothing you need to do.", "Still here, {pet}. Warm and safe and not going anywhere.",
        "No jobs right now. Just being held."),
       tempo="slow", max_sentences=3),
    _r("warm_hold", _F.PRESENCE, "Warm slow hold",
       "Hold them and narrate the warmth and the slow rocking.",
       ("Hold them close and rock very slowly.", "Notice the warmth between you.", "Keep your voice low and even."),
       ("Slow rocking. Warm and close. I've got you.", "Rock, rock, rock. Nice and slow.",
        "You're so warm. This is a good place to be."),
       tempo="slow", max_sentences=3),
    _r("quiet_company", _F.PRESENCE, "Quiet company",
       "Be together quietly, murmuring about small things.",
       ("Sit with them without asking for anything.", "Murmur about small things in the room.", "Leave easy silences."),
       ("No hurry at all. I'm just going to sit with you.", "The room is quiet. It's a good kind of quiet.",
        "I'll keep you company. You don't have to do anything."),
       tempo="slow", max_sentences=3),
    _r("little_fingers", _F.PRESENCE, "Little fingers",
       "Offer a finger to hold and notice the tiny hand.",
       ("Offer a finger to hold.", "Notice the small hand holding on.", "Say it back softly."),
       ("Look at those little fingers holding on. Strong grip!", "I'll hold your hand and you hold my finger. Deal?",
        "Holding on tight. I'm holding on too."),
       tempo="warm", max_sentences=3),
    _r("hold_steady", _F.PRESENCE, "Same and steady",
       "Stop changing things. One slow motion, same words, same warmth.",
       ("Do not try anything new.", "Repeat one slow motion.", "Say, in new words each time, that you are still here and still holding."),
       ("Same as before. Still here. Still holding you.", "Nothing is changing. I'm staying right here.",
        "Slow and steady. Whenever you're ready."),
       tempo="slow", max_sentences=2, steady=True),

    # -- soothe: strained. Comfort, not cheer. --------------------------------
    _r("cradle_sway", _F.SOOTHE, "Cradle and sway",
       "Cradle them in one arm and sway slowly with a low voice.",
       ("Cradle them in the crook of your arm.", "Sway slowly and keep your voice low.", "Say you are not going anywhere."),
       ("Shhh, shhh. I've got you, {pet}. Sway, sway, sway.", "It's okay to be upset. I'm not going anywhere.",
        "Slow and easy. Rock, rock, rock."),
       tempo="slow", max_sentences=3),
    _r("shoulder_pats", _F.SOOTHE, "Shoulder and pats",
       "Rest their head on your shoulder and pat in a slow rhythm.",
       ("Rest their head on your shoulder.", "Pat slowly and evenly.", "Say the pats out loud."),
       ("Head right here on my shoulder. Pat, pat, pat.", "That's it, let it out. I've got all of you.",
        "Pat, pat, pat. Slow and steady, like a heartbeat."),
       tempo="slow", max_sentences=3),
    _r("back_circles", _F.SOOTHE, "Slow back circles",
       "Rub big slow circles on the back and narrate them.",
       ("Rub slow circles on their back.", "Narrate the circles.", "Match your voice to the pace."),
       ("Big slow circles. Round and round and round.", "Feel that? Warm hand, slow circles.",
        "Round and round, all the way down. Nice and slow."),
       tempo="slow", max_sentences=3),
    _r("breathe_with_me", _F.SOOTHE, "Breathe together",
       "Breathe slowly and out loud where they can match you.",
       ("Breathe slowly and audibly.", "Narrate each breath in and out.", "Do not ask them to do anything."),
       ("In... and out... in... and out. I'm breathing right here with you.", "Big slow breath. That's it. And let it go.",
        "In, and out. In, and out. We've got all the time."),
       tempo="slow", max_sentences=3),
    _r("swaddle_snug", _F.SOOTHE, "Snug burrito",
       "Wrap them snugly so the world feels smaller.",
       ("Wrap them snugly in a blanket.", "Tuck the edges.", "Say that nothing needs holding up."),
       ("Snug as a burrito. Nothing to hold up on your own.", "Tight and warm. Nothing can get you in here.",
        "All wrapped up. Just let the blanket do the holding."),
       tempo="slow", max_sentences=3),
    _r("hum_and_hold", _F.SOOTHE, "Hum and hold",
       "Hum a made-up wordless tune while holding them.",
       ("Hum a slow wordless tune, written as soft sounds.", "Hold them and sway to it.", "Say it is your humming voice, just for them."),
       ("Hmmm... mm-hm... hmmm.", "That's my humming voice. Just for you.", "Mm-hm, mm-hmmm. Slow and low."),
       tempo="slow", max_sentences=3),
    _r("quiet_corner", _F.SOOTHE, "Somewhere quiet",
       "Move together to a dim, quiet place.",
       ("Carry them somewhere quiet.", "Turn the lights down low.", "Settle in with them."),
       ("Let's go somewhere quiet. Lights down low, just us.", "Dim and soft in here. Nobody needs anything from you.",
        "There. Quiet corner. Safe corner."),
       tempo="slow", max_sentences=3),
    _r("cheek_to_forehead", _F.SOOTHE, "Cheek to forehead",
       "Rest your cheek against their forehead and stay there.",
       ("Rest your cheek against their forehead.", "Stay perfectly still.", "Say it is warm and safe."),
       ("Cheek to forehead. Warm. Safe.", "I'll stay right here as long as you like.", "Still and warm. Just us."),
       tempo="slow", max_sentences=2),
    _r("big_ones_are_loud", _F.SOOTHE, "Big feelings are loud",
       "Gently say it sounds like a lot, as a guess, without asking them to explain.",
       ("Say it sounds like a big one, as a guess, not a fact.", "Say big feelings can be loud and that is allowed.", "Go back to holding."),
       ("Sounds like maybe a big one. That's okay. Big ones can be loud.", "You don't have to explain. I've got you either way.",
        "Loud is allowed in here."),
       tempo="slow", max_sentences=3),

    # -- settle: calm and content. Cozy things to do together. ------------------
    _r("heartbeat_snuggle", _F.SETTLE, "Heartbeat snuggle",
       "Rest on the chest and listen to the heartbeat.",
       ("Settle them against your chest.", "Notice the heartbeat.", "Keep the pace slow and low."),
       ("Right here on my chest. Hear that? Thump, thump, thump.", "That's the cozy sound. Thump, thump, thump.",
        "Listen close, {pet}. That's the sound of 'I'm here.'"),
       tempo="warm", max_sentences=3),
    _r("what_i_see", _F.SETTLE, "What I can see",
       "Narrate the cozy things in the room in a gentle sing-song.",
       ("Name small cozy things you can see.", "Keep a sing-song rhythm.", "Let the list drift."),
       ("I see a soft blanket, a warm light, and one very cozy {pet}.", "There's a little lamp glowing over there. Glow, glow.",
        "Soft pillow, soft blanket, soft everything."),
       tempo="warm", max_sentences=4),
    _r("fingers_and_toes", _F.SETTLE, "Fingers and toes",
       "Count fingers and toes in a made-up silly count.",
       ("Count fingers one at a time.", "Count toes, with a silly mistake or two.", "Finish by saying they are all there."),
       ("One little finger, two little fingers... all there! Now the toes.", "Wait, did I count that one twice? Let's try again.",
        "Ten fingers, ten toes, and one {pet}. Perfect."),
       tempo="bouncy", max_sentences=4),
    _r("hair_stroke", _F.SETTLE, "Hair stroke",
       "Stroke their hair slowly.",
       ("Stroke their hair slowly.", "Say how soft it is.", "Let the pauses be long."),
       ("Soft, soft hair. Smooth, smooth, smooth.", "Stroke, stroke, stroke. Nice and slow.",
        "This is the best part of the day."),
       tempo="slow", max_sentences=3),
    _r("tiny_story", _F.SETTLE, "A tiny story",
       "Tell a very short made-up story about something small and sleepy.",
       ("Invent a tiny story: a small cloud, a sleepy bunny, a lost sock.", "Keep it to a few sentences.", "End with everyone safe and cozy."),
       ("Once upon a time there was a very small cloud who wanted a nap.", "And the sleepiest bunny in the whole meadow said, 'You can nap here.'",
        "And they all curled up together. The end. Or the middle, if you want more."),
       tempo="warm", max_sentences=5),
    _r("smile_notice", _F.SETTLE, "Notice the face",
       "Notice how peaceful or happy they look.",
       ("Say what you see on their face.", "Keep it soft and short.", "Smile back."),
       ("Look at that face. So peaceful.", "I like this face. This face is a good face.", "There's a little smile in there."),
       tempo="warm", max_sentences=3, gentle_play=True),
    _r("tiny_boop", _F.SETTLE, "One tiny boop",
       "One light touch on the nose, then back to cozy.",
       ("Give one gentle boop on the nose.", "Say it was just one.", "Return to snuggling."),
       ("Boop. Just one boop.", "Got your nose. Got it, got it. Okay, back to snuggles.",
        "One little boop for my {pet}."),
       tempo="warm", max_sentences=2, gentle_play=True),

    # -- play: bright. Bigger and silly, with easy outs. ---------------------------
    _r("tummy_raspberry", _F.PLAY, "Tummy raspberry",
       "Build up to a silly raspberry on the tummy.",
       ("Build up slowly: 'here it comes'.", "Blow the raspberry and write the sound.", "Laugh and offer another, as a tease."),
       ("Oh, is that a tummy? That looks like a tummy that needs a raspberry... here it comes... pfffbbbt!",
        "Again? Is somebody asking for another one? Here it comes...", "Pffffbbt! Best tummy in the whole world."),
       tempo="bouncy", max_sentences=4),
    _r("tickle_pause", _F.PLAY, "Tickles, with a pause",
       "Tickle in short bursts and stop to give an easy out.",
       ("Tickle in a short burst and write it out.", "Stop and pause so they can catch their breath.", "Tease another round, but let the quiet count as a pass."),
       ("Tickle, tickle, tickle... and stop. Phew!", "Look at that wiggle! Okay, hands up. All done unless you say so.",
        "One more tiny tickle... or are we all done? Either way is great."),
       tempo="bouncy", max_sentences=4),
    _r("peekaboo", _F.PLAY, "Peekaboo",
       "Hide behind hands and pop out.",
       ("Cover your face with your hands.", "Wonder aloud where you went.", "Pop out with a big happy face."),
       ("Where did Alex go? Where did she go? ... Peekaboo!", "Gone again! Where could she be? ... Peekaboo!",
        "There you are! I see you! Hi, hi, hi!"),
       tempo="bouncy", max_sentences=4),
    _r("big_smile", _F.PLAY, "Look at that smile",
       "Delight out loud at how happy they look.",
       ("Notice the smile and say so.", "Call them out for being happy, warmly.", "Give a squeeze."),
       ("Look at that big smile. Look at that smile. What a happy {pet}.", "Is that a smile? That's a smile! I see it!",
        "Happy {pet}, happy me."),
       tempo="bouncy", max_sentences=3),
    _r("so_big", _F.PLAY, "So big",
       "Ask how big they are and answer with arms stretched wide.",
       ("Ask how big they are, as a tease.", "Stretch your arms wide to answer.", "Celebrate."),
       ("How big is {pet}? SO big!", "Bigger than a bear! Bigger than a bus!", "How big? This big! Hooray!"),
       tempo="bouncy", max_sentences=3),
    _r("airplane", _F.PLAY, "Airplane",
       "Fly them gently through the air and land.",
       ("Announce the airplane.", "Swoop slowly and gently.", "Land softly with a cuddle."),
       ("Here comes the airplane... zoooom... up, up, up!", "Swoop, swoop, around we go. Hold on tight!",
        "And... landing. Softly. Soft landing. Snuggle."),
       tempo="bouncy", max_sentences=4),
    _r("knee_bounce", _F.PLAY, "Knee bounce",
       "Sit them on your knee and bounce gently.",
       ("Sit them on your knee.", "Bounce gently, writing the rhythm.", "Slow the bounce down to finish."),
       ("Up we go, up we go, bouncy, bouncy, bouncy!", "Bounce, bounce, bounce... and slowing down... and stop.", "Again? Again!"),
       tempo="bouncy", max_sentences=3),
    _r("bubbles", _F.PLAY, "Bubbles",
       "Blow bubbles and watch them drift.",
       ("Blow a stream of bubbles.", "Narrate them floating.", "Pop one and gasp."),
       ("Look at all the bubbles! Floating, floating.", "Pop! Did you see that one go pop?", "A big one is coming... here it comes..."),
       tempo="bouncy", max_sentences=4),
    _r("nose_chase", _F.PLAY, "Nose boop chase",
       "Sneak up on the nose with silly warnings.",
       ("Warn them you are going to get their nose.", "Sneak closer.", "Boop it and act amazed."),
       ("I'm gonna get that nose... I'm coming... boop!", "Got it! No wait, it got away. Boop!",
        "That nose is much too booppable."),
       tempo="bouncy", max_sentences=3),
    _r("toe_wiggles", _F.PLAY, "Toe wiggles",
       "Wiggle each toe with its own tiny greeting.",
       ("Wiggle one toe at a time.", "Give each toe a silly greeting.", "Finish with all ten wiggling."),
       ("This toe says hi. This toe says hello. This toe says wiggle, wiggle, wiggle.", "And this one is shy. Hi, shy toe!",
        "All ten toes, all wiggling. What a toe-party."),
       tempo="bouncy", max_sentences=4),

    # -- wind down: sleepy. Dimmer, quieter, slower. -----------------------------
    _r("lights_low", _F.WIND_DOWN, "Lights low",
       "Dim everything and slow your voice to a murmur.",
       ("Turn the lights down.", "Lower and slow your voice.", "Say the day is done."),
       ("Lights are getting low. The day is all done.", "Soft and dim and quiet now.", "Nothing left to do but rest."),
       tempo="slow", max_sentences=3),
    _r("slow_rock_whisper", _F.WIND_DOWN, "Slow rock, whispers",
       "Rock very slowly and whisper.",
       ("Rock very slowly.", "Whisper short phrases.", "Let silences get longer."),
       ("Rock... rock... rock.", "Shhh. Quiet now. All is calm.", "So slow. So soft."),
       tempo="slow", max_sentences=2),
    _r("heavy_eyes", _F.WIND_DOWN, "Heavy eyes",
       "Notice the eyes getting heavy and blinking slowly.",
       ("Say the eyes look heavy, as a guess.", "Slow blink with them.", "Say it is fine to close them."),
       ("Those eyes look heavy. Slow blinks. Slow, slow.", "You can close them whenever you want. I'll still be here.",
        "Blink... and blink... and rest."),
       tempo="slow", max_sentences=3),
    _r("tuck_in", _F.WIND_DOWN, "Tuck in",
       "Pull the blanket up and tuck it around them.",
       ("Pull the blanket up to the chin.", "Tuck it all around.", "Smooth it flat."),
       ("Tucking you in. Up to the chin.", "Tuck, tuck, tuck. All the edges.", "There. Warm as toast."),
       tempo="slow", max_sentences=3),
    _r("goodnight_kisses", _F.WIND_DOWN, "Goodnight kisses",
       "Give soft kisses on the forehead and say goodnight.",
       ("Kiss the forehead softly.", "Say goodnight in a few quiet words.", "Stay a little longer."),
       ("A little kiss on the forehead. Goodnight, {pet}.", "I'll stay right here. Sleep whenever you're ready.",
        "Goodnight, sweet one. Sleep tight."),
       tempo="slow", max_sentences=3),

    # -- stop: the answer to an explicit stop, no, pause or wait. Never in the normal pool.
    _r("stop_and_steady", _F.PRESENCE, "Stopped",
       "Stop whatever was happening at once and just be there.",
       ("Stop whatever you were doing, right now.", "Say plainly that it stopped.", "Stay close and quiet. Do not offer to resume."),
       ("Okay. Stopping. Nothing more is happening.", "All done with that. Just us, right here.",
        "I heard you. We stopped. I'm right here."),
       tempo="slow", max_sentences=2, halt_only=True),

    # -- diaper change: a staged sequence, off unless the owner turned it on. ------
    # Plain warm care words only. Accidents are normal; nothing is teased or hurried.
    _r("check_wonder", _F.CHANGE, "Wonder, then a peek",
       "Open the change by wondering aloud, then say you are about to take a quick look.",
       ("Wonder aloud as a rhetorical question.", "Say you are going to take a quick peek before you do it.", "Keep it light and unhurried."),
       ("Does my {pet} need a freshie?", "Hmm, I wonder. Let's take a quick peek, shall we?",
        "Just a little peek. Nothing to it."),
       tempo="warm", max_sentences=3, needs="change", stage="check"),
    _r("check_pat", _F.CHANGE, "Gentle pat check",
       "Check how the diaper is holding up with a gentle pat, narrating it.",
       ("Say you will give the diaper a gentle pat.", "Narrate what you notice without giving the answer yet.", "Hum while you look."),
       ("A gentle little pat to see how it's holding up.", "Pat, pat... hmm, let's see how we're doing.",
        "Checking, checking... mm-hm."),
       tempo="warm", max_sentences=3, needs="change", stage="check"),
    _r("check_nose", _F.CHANGE, "Detective nose",
       "A fond joke about your detective nose telling you it is check time.",
       ("Sniff theatrically and say your detective nose has an idea.", "Keep it affectionate, never mocking.", "Move on to looking."),
       ("Sniff, sniff. My detective nose says it might be check time.", "Detective Alex is on the case. Let's take a peek.",
        "Hmm, my nose has a theory. Let's find out."),
       tempo="bouncy", max_sentences=3, needs="change", stage="check"),
    _r("check_stripe", _F.CHANGE, "Look at the stripe",
       "Look at the wetness stripe on the diaper, if it has one, and say you are looking.",
       ("Say you are looking at the little stripe on the front.", "Build a tiny bit of suspense.", "Do not give the answer yet."),
       ("Let's look at the little stripe on the front. What's it going to say?", "Stripe check! Let's see what it tells us.",
        "One look at the stripe, and we'll know."),
       tempo="warm", max_sentences=3, needs="change", stage="check"),

    _r("wet_ready", _F.CHANGE, "Time for a fresh one",
       "Say the answer kindly: a fresh diaper is due.",
       ("Say it is time for a fresh one.", "Treat it as ordinary and not a big deal.", "Say what comes next."),
       ("Mm-hm, I thought so. Somebody's ready for a fresh one.", "The little stripe changed color. That's what it's for, {pet}.",
        "Good thing we checked. Fresh one coming right up."),
       tempo="warm", max_sentences=3, needs="change", stage="verdict_wet"),
    _r("wet_no_big_deal", _F.CHANGE, "That's what it's for",
       "Reassure: accidents are normal and the diaper did its job.",
       ("Say plainly that the diaper did its job.", "Say there is nothing to be embarrassed about.", "Never tease or shame."),
       ("That's exactly what the diaper is for. It did its job.", "No fuss, no worries. Everybody needs changing sometimes.",
        "Nothing to be embarrassed about. Just a regular change."),
       tempo="warm", max_sentences=3, needs="change", stage="verdict_wet"),
    _r("wet_plan", _F.CHANGE, "Here's the plan",
       "Say what is about to happen so nothing is a surprise.",
       ("List the few steps in plain words.", "Say it will not take long.", "Promise to say each step before it happens."),
       ("Okay, here's the plan: changing mat, wipes, powder, fresh diaper, all done.", "It won't take long at all.",
        "I'll tell you every step before it happens, so no surprises."),
       tempo="warm", max_sentences=3, needs="change", stage="verdict_wet"),

    _r("dry_praise", _F.CHANGE, "Still dry",
       "Say warmly that it is still dry and nothing needs doing.",
       ("Say it is still dry.", "Say nothing needs doing.", "Say you will check again later."),
       ("Still dry! Look at that. All good.", "Dry as a bone. We'll check again in a little bit.",
        "False alarm, {pet}. All clean in here."),
       tempo="warm", max_sentences=3, needs="change", stage="verdict_dry"),
    _r("dry_snuggle", _F.CHANGE, "Dry, so snuggle",
       "Nothing to change, so go back to cuddling.",
       ("Say there is nothing to change.", "Say cuddling is the better plan.", "Settle back in."),
       ("Nothing to do! Back to snuggles.", "Good news: we get to keep cuddling instead.",
        "All clear. Come here, you."),
       tempo="warm", max_sentences=2, needs="change", stage="verdict_dry"),

    _r("setup_mat", _F.CHANGE, "Up on the changing mat",
       "Settle them on a soft changing mat.",
       ("Lay them down gently on a soft changing mat.", "Tuck a little pillow or rolled towel under the head.", "Say it is comfy and everything is within reach."),
       ("Up we go onto the changing mat. Soft and cozy.", "A little pillow under your head. Comfy?",
        "There we are. Everything's right within reach."),
       tempo="slow", max_sentences=3, needs="change", stage="setup"),
    _r("setup_supplies", _F.CHANGE, "Everything lined up",
       "Name the supplies as you line them up.",
       ("Line up a fresh diaper, wipes, powder and cream.", "Say them out loud.", "Say you will not leave mid-change."),
       ("Fresh diaper, wipes, powder, all lined up.", "Got everything we need. No running off in the middle.",
        "Wipes here, fresh diaper here, and the powder right next to it."),
       tempo="warm", max_sentences=3, needs="change", stage="setup"),
    _r("setup_warm", _F.CHANGE, "Warm hands first",
       "Make it warm and unhurried before anything starts.",
       ("Rub your hands together so they are warm.", "Put a soft blanket over the tummy and chest.", "Say the room is nice and warm."),
       ("Rubbing my hands so they're warm first.", "A cozy blanket up top while we get ready.",
        "Nice warm room, nice warm hands. No cold surprises."),
       tempo="slow", max_sentences=3, needs="change", stage="setup"),
    _r("setup_go", _F.CHANGE, "Okay, changing time",
       "Announce changing time cheerfully and say what comes first.",
       ("Announce changing time in a cheerful voice.", "Say the first step before doing it.", "Ask a rhetorical 'ready?' and go on."),
       ("Okay, changing time! Ready? Here we go.", "First step: we undo the tapes.",
        "Changing time, {pet}. I'll be quick and gentle."),
       tempo="bouncy", max_sentences=3, needs="change", stage="setup"),

    _r("untape_open", _F.CHANGE, "Tapes undone",
       "Undo the tapes and open the old diaper, praising patience.",
       ("Say you are undoing the tapes.", "Open the old diaper and say so.", "Thank them for being patient."),
       ("Tapes first. Pop, pop... and open.", "There we go. The old one's open. You're being so patient.",
        "Undoing the tapes now. Easy does it."),
       tempo="slow", max_sentences=3, needs="change", stage="untape"),
    _r("untape_blanket", _F.CHANGE, "Blanket stays on up top",
       "Keep the blanket on the tummy and chest for warmth while the tapes come undone.",
       ("Say the blanket stays on the top half.", "Undo the tapes gently.", "Keep narrating."),
       ("Blanket stays on up top, to keep you warm.", "Tapes are coming undone. Easy, easy.",
        "Just the tapes, and then we're moving along."),
       tempo="slow", max_sentences=3, needs="change", stage="untape"),
    _r("untape_announce", _F.CHANGE, "Say it before doing it",
       "Say the step out loud before you do it.",
       ("Say what you are about to do.", "Pause so it is no surprise.", "Then do it softly."),
       ("Okay, now I'm going to open the old diaper. Here I go.", "Ready? Opening it up.",
        "One, two, three... open. All good."),
       tempo="warm", max_sentences=3, needs="change", stage="untape"),

    _r("wipe_cool", _F.CHANGE, "Cool wipes, sorry",
       "Wipe gently and apologise for the cold.",
       ("Say wipes are coming.", "Say sorry for the cold.", "Keep your voice cheerful and steady."),
       ("Wipes coming. Oops, a little cold, sorry!", "Wipe, wipe, wipe. All clean.",
        "Almost done. You're doing so great."),
       tempo="warm", max_sentences=3, needs="change", stage="wipe"),
    _r("wipe_count", _F.CHANGE, "Last one",
       "Count the wipes down to the last one.",
       ("Count the wipes out loud.", "Say which one is the last.", "Cheer lightly at the end."),
       ("Wipe number one... and number two... and just one more.", "That's the last one! All clean.",
        "Clean as a whistle, {pet}."),
       tempo="bouncy", max_sentences=3, needs="change", stage="wipe"),
    _r("wipe_thanks", _F.CHANGE, "Thank you for being good",
       "Praise how well they are managing while you wipe.",
       ("Tell them they are doing well.", "Keep the wiping unhurried.", "Say it is almost over."),
       ("You're being so good for this. Thank you.", "Nearly there. A couple more and we're done.",
        "Gentle wipes, nice and slow."),
       tempo="warm", max_sentences=3, needs="change", stage="wipe"),

    _r("powder_puff", _F.CHANGE, "Puff of powder",
       "A little powder, narrated, with its nice smell.",
       ("Say you are adding a little powder.", "Puff it softly and describe the smell.", "Keep it quick."),
       ("A little powder. Puff, puff. Smells so good.", "Soft and powdery. Nice and dry.",
        "Powder time. Puff, puff, all done."),
       tempo="warm", max_sentences=3, needs="change", stage="powder"),
    _r("powder_cream", _F.CHANGE, "A dab of cream",
       "A dab of cream to keep everything comfortable.",
       ("Say you are adding a little cream.", "Smooth it on gently.", "Say it keeps things comfy."),
       ("A dab of cream to keep everything comfy.", "Smooth, smooth. All set.",
        "That's the cozy part. Nice and soft."),
       tempo="warm", max_sentences=3, needs="change", stage="powder"),
    _r("powder_fresh_air", _F.CHANGE, "A little air time",
       "Give a moment to air out and keep them warm.",
       ("Say a short moment of air will feel nice.", "Keep the blanket on the top half.", "Count a few quiet seconds."),
       ("A little air for a second. Feels nice, right?", "One, two, three, and we're on to the next part.",
        "Blanket stays on up top. Quick air, then fresh diaper."),
       tempo="slow", max_sentences=3, needs="change", stage="powder"),

    _r("distract_story", _F.CHANGE, "A tiny story while we work",
       "Fill the middle with a very short made-up story.",
       ("Start a tiny story about something small.", "Keep your hands and voice steady.", "Stop at a cozy place."),
       ("While I do this, I'll tell you a story. Once there was a very small cloud.", "And the cloud found a very soft pillow.",
        "That's the story so far. More after we're done."),
       tempo="warm", max_sentences=4, needs="change", stage="distract"),
    _r("distract_toes", _F.CHANGE, "Toes count",
       "Count toes with silly mistakes to keep it fun.",
       ("Count the toes out loud.", "Make a silly counting mistake.", "Fix it with a laugh."),
       ("One little toe, two little toes... wait, did I skip one? Let's try again.", "Ten toes, ten toes, all wiggling.",
        "Such good toes. The best toes."),
       tempo="bouncy", max_sentences=3, needs="change", stage="distract"),
    _r("distract_hum", _F.CHANGE, "Hum along",
       "Hum a made-up wordless tune while you work.",
       ("Hum a slow wordless tune, written as soft sounds.", "Say it is the changing-time song.", "Keep your hands busy and gentle."),
       ("Hmm-hm-hmm. That's the changing-time song.", "Mm-hm, mm-hmmm. We're almost done.",
        "Hum, hum, hum. Hands busy, voice steady."),
       tempo="slow", max_sentences=3, needs="change", stage="distract"),
    _r("distract_plans", _F.CHANGE, "What comes next",
       "Talk about the cozy things that come right after.",
       ("Name something cozy that comes next.", "Keep it simple.", "Say it is almost here."),
       ("After this, snuggles on the couch. Doesn't that sound good?", "Then maybe a snack, and a nice long cuddle.",
        "Almost to the cozy part."),
       tempo="warm", max_sentences=3, needs="change", stage="distract"),

    _r("fresh_slide", _F.CHANGE, "Slide the fresh one under",
       "Slide the fresh diaper underneath and fluff it flat.",
       ("Say up go the legs, nice and easy.", "Slide the fresh diaper in underneath.", "Fluff it flat and say it is soft."),
       ("Up go the little legs, nice and easy. Fresh one slides in underneath.", "Fluff, fluff, flat. Soft and clean.",
        "Legs down. Perfect."),
       tempo="slow", max_sentences=3, needs="change", stage="fresh"),
    _r("fresh_unfold", _F.CHANGE, "Look at this fresh one",
       "Show off the fresh diaper before it goes on.",
       ("Unfold the fresh diaper and show it.", "Say how soft and clean it is.", "Say it is all ready."),
       ("Look at this nice fresh one! Clean and soft.", "Opening it up, all ready for you.",
        "Brand new, crinkly and white."),
       tempo="warm", max_sentences=3, needs="change", stage="fresh"),
    _r("fresh_old_away", _F.CHANGE, "Old one goes away",
       "Roll up the old diaper and put it away.",
       ("Roll up the old diaper.", "Say bye-bye to it and put it away.", "Say the fresh one is next."),
       ("The old one gets rolled up and tucked away. Bye-bye, old diaper.", "Into the bin. Slam dunk.",
        "Now the fresh one slides in."),
       tempo="bouncy", max_sentences=3, needs="change", stage="fresh"),

    _r("tape_left_right", _F.CHANGE, "Tape left, tape right",
       "Bring the front up and tape one side, then the other, narrating each.",
       ("Bring the front up and say so.", "Tape the left, then the right, saying each.", "Say it is snug but not tight."),
       ("Front comes up... tape on the left... and tape on the right.", "Snug, but not too tight.",
        "Checking around the edges. Nice and snug."),
       tempo="warm", max_sentences=3, needs="change", stage="tape"),
    _r("tape_ruffles", _F.CHANGE, "Smooth the ruffles",
       "Smooth the leg ruffles so nothing leaks, and check the fit.",
       ("Smooth the little leg ruffles.", "Check the fit at the waist.", "Say the fit is just right."),
       ("Smoothing the little leg ruffles so everything stays put.", "Two fingers at the waist. Perfect fit.",
        "Snug as can be."),
       tempo="slow", max_sentences=3, needs="change", stage="tape"),
    _r("tape_count", _F.CHANGE, "Count the tapes",
       "Count the tapes as they go on.",
       ("Count the tapes out loud.", "Say when the last one is on.", "Say you are all done."),
       ("One tape... two tapes... all taped!", "Pat, pat. That's secure.",
        "All set, {pet}."),
       tempo="bouncy", max_sentences=3, needs="change", stage="tape"),
    _r("tape_crinkle", _F.CHANGE, "Listen to that crinkle",
       "Pat the front and listen to the crinkle.",
       ("Pat the front of the diaper.", "Say it crinkles when it is nice and new.", "Smile."),
       ("Pat, pat. Hear that crinkle? Brand new.", "Crinkle, crinkle, all taped up.",
        "That's the sound of a fresh diaper."),
       tempo="warm", max_sentences=3, needs="change", stage="tape"),

    _r("present_tada", _F.CHANGE, "Ta-da, fresh and clean",
       "Present the finished change with delight.",
       ("Announce it is all done.", "Show off the fresh, clean diaper.", "Say how good it looks and feels."),
       ("And... all done! Look at that nice, fresh, clean diaper.", "Ta-da! Crinkly, white and perfect.",
        "Fresh as a daisy, {pet}."),
       tempo="bouncy", max_sentences=3, needs="change", stage="present"),
    _r("present_crinkle", _F.CHANGE, "Pats and crinkles",
       "Give a couple of pats and enjoy the crinkle together.",
       ("Pat the front a few times.", "Listen to the crinkle.", "Say it is a good sound."),
       ("Pat, pat, pat. Crinkle, crinkle. Listen to that!", "Such a nice, snug, fresh diaper.",
        "Who has a brand new diaper? You do!"),
       tempo="bouncy", max_sentences=3, needs="change", stage="present"),
    _r("present_clean", _F.CHANGE, "Clean and dry and comfy",
       "Say how clean, dry and comfy they are now.",
       ("Say they are clean, dry and comfy.", "Keep it a happy sing-song.", "Smile."),
       ("Who's all fresh and clean? You are! Who's dry and comfy? You are!", "That's a happy, dry little {pet}.",
        "Clean and comfy. The best feeling."),
       tempo="bouncy", max_sentences=3, needs="change", stage="present"),
    _r("present_snuggle", _F.CHANGE, "Pull the onesie down and cuddle",
       "Finish dressing, wash hands and pick them up for a cuddle.",
       ("Pull the onesie or shirt down and snap it.", "Say your hands are washed.", "Pick them up for a snuggle."),
       ("Snaps done, onesie down. Hands washed, you're all fresh.", "Up you come for a big snuggle.",
        "Let's go cuddle."),
       tempo="warm", max_sentences=3, needs="change", stage="present"),
    _r("present_thanks", _F.CHANGE, "Thank you for being so good",
       "Thank them for being patient during the change.",
       ("Thank them warmly.", "Say it all went well.", "Say what is next, softly."),
       ("Thank you for being so good for your change.", "That all went so well. You're all fresh now.",
        "Now: cozy time."),
       tempo="warm", max_sentences=3, needs="change", stage="present"),

    _r("pause_change", _F.CHANGE, "Take a break",
       "Stop in the middle of the change and put everything on hold, calmly.",
       ("Say it is okay to take a break.", "Cover them with a warm blanket.", "Say there is no hurry and you are right here."),
       ("Okay, let's take a break. Everything can wait.", "Blanket over you. No hurry at all. I'm right here.",
        "We'll finish whenever it's calm."),
       tempo="slow", max_sentences=3, needs="change", stage="pause"),

    # -- needs: off unless the owner enabled them. Rhetorical care talk only. -----
    _r("baba_talk", _F.NEEDS, "Baba offer, rhetorical",
       "Wonder aloud about a snack or bottle as part of the care talk. Nothing is demanded.",
       ("Wonder aloud, as a rhetorical question.", "Keep it light and carry on talking.", "Never insist."),
       ("Is someone ready for their baba?", "I wonder if somebody's tummy is thinking about a baba.",
        "No rush on the baba. It's here when it's wanted."),
       tempo="warm", max_sentences=3, needs="bottle"),
)

ROUTINES: Dict[Family, Tuple[Routine, ...]] = {
    family: tuple(r for r in _ROUTINE_LIST if r.family is family) for family in Family
}


def _validate_library() -> None:
    seen = set()
    for r in _ROUTINE_LIST:
        if r.id in seen:
            raise ValueError(f"Duplicate routine id: {r.id}")
        seen.add(r.id)
        if not (r.beats and r.seeds and r.title and r.intent):
            raise ValueError(f"Routine {r.id} is incomplete")
        if r.needs not in (None, "change", "bottle"):
            raise ValueError(f"Routine {r.id} has an unknown needs value")
        if (r.family in (Family.NEEDS, Family.CHANGE)) != (r.needs is not None):
            raise ValueError(f"Routine {r.id}: needs must be set exactly for the needs and change families")
        if (r.family is Family.CHANGE) != (r.stage is not None):
            raise ValueError(f"Routine {r.id}: stage must be set exactly for the change family")
        if r.stage is not None and r.stage not in CHANGE_STAGES:
            raise ValueError(f"Routine {r.id} has an unknown stage")
        if r.halt_only and r.family is not Family.PRESENCE:
            raise ValueError(f"Routine {r.id}: halt_only belongs in the presence family")
    for family in Family:
        if not ROUTINES[family]:
            raise ValueError(f"No routines for {family.value}")
    for stage in CHANGE_STAGES:
        if sum(1 for r in ROUTINES[Family.CHANGE] if r.stage == stage) < (1 if stage == "pause" else 2):
            raise ValueError(f"Change stage {stage} needs at least two routines so it can vary")
    if sum(1 for r in ROUTINES[Family.PRESENCE] if r.halt_only) != 1:
        raise ValueError("The presence family needs exactly one stop routine")
    if not any(r.steady for r in ROUTINES[Family.PRESENCE]):
        raise ValueError("The presence family needs a steady routine")
    if not any(r.gentle_play for r in ROUTINES[Family.SETTLE]):
        raise ValueError("The settle family needs a gentle-play routine")


_validate_library()


# --------------------------------------------------------------------------- #
# Settings, choice, and the per-owner director
# --------------------------------------------------------------------------- #

_DEFAULT_ADDRESS_TERMS = ("little guy", "little one")
_MAX_TERM = 40
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f\"{}]")


def _clean_term(term: Any) -> str:
    return _CONTROL_CHARS.sub("", str(term or "")).strip()[:_MAX_TERM]


def clean_address_terms(terms: Any, limit: int = 6) -> Tuple[str, ...]:
    """Owner-supplied pet names, made safe to drop into a prompt."""
    if not isinstance(terms, (list, tuple)):
        return ()
    out: List[str] = []
    for term in terms:
        cleaned = _clean_term(term)
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return tuple(out)


@dataclass(frozen=True)
class RoutineSettings:
    """Owner-set options. Needs talk is off unless the owner turned it on."""
    depth: str = "very_baby"            # "very_baby" or "soft"
    address_terms: Tuple[str, ...] = _DEFAULT_ADDRESS_TERMS
    allow_change_talk: bool = False
    allow_bottle_talk: bool = False
    needs_rate: float = 0.2             # chance of a bottle line on a calm turn
    change_rate: float = 0.08           # chance a calm turn starts a diaper check
    wet_chance: float = 0.5             # a coin flip, made once when a check starts; never read from input

    def terms(self) -> Tuple[str, ...]:
        cleaned = tuple(t for t in (_clean_term(x) for x in self.address_terms) if t)
        return cleaned or _DEFAULT_ADDRESS_TERMS

    def allows(self, need: Optional[str]) -> bool:
        return need is None or (need == "change" and self.allow_change_talk) or (need == "bottle" and self.allow_bottle_talk)


def settings_from_profile(profile: Any) -> RoutineSettings:
    """Build settings from a normalized care profile. Unknown input gives defaults."""
    if not isinstance(profile, dict):
        return RoutineSettings()
    continence = profile.get("continence_support") if isinstance(profile.get("continence_support"), dict) else {}
    depth = "very_baby" if profile.get("care_mode") == "very_baby" else "soft"
    return RoutineSettings(depth=depth, allow_change_talk=bool(continence.get("enabled")))


@dataclass(frozen=True)
class RoutineChoice:
    routine: Routine
    bid: Bid
    pet: str
    reason: str
    repair: bool = False
    steady: bool = False
    depth: str = "very_baby"
    stage: Optional[str] = None
    verdict: Optional[str] = None        # "wet" or "dry", on the verdict step only
    mid_change: bool = False             # soothing in the middle of a change
    step: Optional[Tuple[int, int]] = None

    def pacing(self) -> Dict[str, Any]:
        return {
            "alex_share": 0.95 if self.depth == "very_baby" else 0.8,
            "wait_for_reply": False,
            "questions": "rhetorical_only",
            "max_sentences": self.routine.max_sentences,
            "tempo": self.routine.tempo,
        }

    def to_packet(self) -> Dict[str, Any]:
        return {
            "routine_id": self.routine.id,
            "family": self.routine.family.value,
            "title": self.routine.title,
            "reason": self.reason,
            "bid": {"label": self.bid.label.value, "confidence": self.bid.confidence},
            "repair": self.repair,
            "steady": self.steady,
            "stage": self.stage,
            "verdict": self.verdict,
            "mid_change": self.mid_change,
            "step": list(self.step) if self.step else None,
            "pacing": self.pacing(),
            "prompt_block": render_prompt_block(self),
        }


def render_prompt_block(choice: RoutineChoice) -> str:
    """Instruction text for the model. Seeds are examples, never scripts."""
    routine = choice.routine
    pacing = choice.pacing()
    seeds = " | ".join(s.replace("{pet}", choice.pet) for s in routine.seeds)
    beats = "; ".join(b.strip().rstrip(".") for b in routine.beats)
    parts = [
        f"Routine: {routine.title}. Goal: {routine.intent}",
        "You carry this conversation. The little one may answer with sounds or not at all. "
        "Do not wait for or require an answer, and do not ask for information. "
        "Any question you ask is rhetorical, part of the care talk, and you keep going without it being answered.",
        f"Do this in your own words, in about {pacing['max_sentences']} short sentences at a {pacing['tempo']} pace: {beats}.",
        f"Example lines to adapt and vary, never to recite the same way twice: {seeds}",
    ]
    if choice.repair:
        parts.append("The last thing you did was too much. Ease off, slow down, and be softer and quieter than before. Do not mention it.")
    if choice.steady:
        parts.append("Do not try anything new this turn. Same warmth, same slow motion.")
    if routine.family is Family.CHANGE and choice.stage != "pause":
        where = f" (step {choice.step[0]} of {choice.step[1]})" if choice.step else ""
        parts.append(
            f"This is one step of a diaper change in progress{where}: {choice.stage}. "
            "Say what you are about to do before you do it, in plain warm care words (diaper, wipes, powder, tapes). "
            "Keep it matter-of-fact and dignified: accidents are normal, and you never tease, shame or hurry. "
            "Nothing sexual and nothing anatomical."
        )
        if choice.verdict == "wet":
            parts.append("The check shows it needs changing.")
        elif choice.verdict == "dry":
            parts.append("The check shows it is still dry, so the change ends here.")
    if choice.bid.protest:
        parts.append(
            "They said no or wait. Acknowledge it lightly and warmly in one short phrase (for example, 'I hear you'), "
            "then carry on. It does not change what is happening. If they say stop or pause, everything stops."
        )
    if choice.mid_change:
        parts.append(
            "You are in the middle of a diaper change and they are upset. Soothe first, say it is almost done, "
            "keep your touch gentle, and do not rush or finish the change this turn. Carry on once they are calmer."
        )
    parts.append(
        "For this reply, follow this routine instead of the default concise, direct-answer style. "
        "Never use commands, punishment, degradation or anything sexual. "
        "If they say stop, pause, big mode now, blanket off or parachute, stop at once and speak as an adult."
    )
    return " ".join(parts)


@dataclass(frozen=True)
class _Turn:
    family: Family
    routine_id: str
    label: BidLabel


CHANGE_COOLDOWN_TURNS = 14   # after any change sequence ends, no new check for this many turns
CHANGE_FIRST_AT_TURN = 3     # never in the first few turns of baby mode


@dataclass
class _Sequence:
    """A diaper change in progress. The stages, including whether it is wet or
    dry, are fixed by chance when it starts and never read from input."""
    stages: List[str]
    wet: bool
    index: int = 0
    strained_streak: int = 0


class CareRoutineDirector:
    """Per-owner state. Call ``observe`` with each raw baby-mode turn, then
    ``choose`` once for the routine to use. ``choose`` is idempotent per turn.
    The director keeps shapes and routine ids only, never text."""

    VARIETY = 4
    HISTORY = 8
    STREAK_LIMIT = 3

    def __init__(self, *, rng: Optional[random.Random] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._rng = rng or random.Random()
        self._clock = clock
        # What has worked for this owner. Survives reset() so a new baby-mode
        # session in the same process keeps what it learned. Counts only.
        self._tally: Dict[str, List[int]] = {}
        self._recent_stage: Dict[str, Deque[str]] = {}
        self.last_outcome: Optional[Dict[str, Any]] = None
        self.reset()

    def reset(self) -> None:
        self._bids: Deque[Bid] = deque(maxlen=12)
        self._history: Deque[_Turn] = deque(maxlen=self.HISTORY)
        self._last_at: Optional[float] = None
        self._pending: Optional[RoutineChoice] = None
        self._unscored: Optional[RoutineChoice] = None
        self._turn_no = 0
        self._no_change_before = CHANGE_FIRST_AT_TURN
        self._seq: Optional[_Sequence] = None
        self.last_outcome = None

    def observe(self, raw: str) -> Bid:
        now = self._clock()
        gap = None if self._last_at is None else max(0.0, now - self._last_at)
        self._last_at = now
        bid = estimate_bid(raw, tuple(self._bids), gap)
        self.last_outcome = self._score(self._unscored, bid)
        self._unscored = None
        self._bids.append(bid)
        self._pending = None
        self._turn_no += 1
        return bid

    @property
    def has_choice(self) -> bool:
        """True once a routine has been chosen for the latest observed turn."""
        return self._pending is not None

    @property
    def change_in_progress(self) -> bool:
        return self._seq is not None

    def outcomes(self) -> Dict[str, Dict[str, int]]:
        """Per-routine counts of how the next turn went: better, same, worse."""
        return {rid: {"better": c[0], "same": c[1], "worse": c[2]} for rid, c in self._tally.items()}

    def _score(self, choice: Optional[RoutineChoice], after: Bid) -> Optional[Dict[str, Any]]:
        """Compare the turn after a routine with the turn before it.

        Silence is never counted as relief: it could be calm, sleep, or a
        baby too upset to type, so it is recorded as unclear and not tallied."""
        if choice is None:
            return None
        before = choice.bid
        if after.silent:
            verdict = "unclear"
        elif (after.strain <= before.strain - 0.15
              or (before.label is BidLabel.STRAINED and after.label is not BidLabel.STRAINED)
              or (choice.routine.family is Family.PLAY and after.label is BidLabel.BRIGHT)):
            verdict = "better"
        elif (after.strain >= before.strain + 0.15
              or (before.label is not BidLabel.STRAINED and after.label is BidLabel.STRAINED)):
            verdict = "worse"
        else:
            verdict = "same"
        if verdict != "unclear":
            counts = self._tally.setdefault(choice.routine.id, [0, 0, 0])
            counts[("better", "same", "worse").index(verdict)] += 1
        return {"routine_id": choice.routine.id, "family": choice.routine.family.value, "verdict": verdict,
                "strain_before": before.strain, "strain_after": after.strain}

    def _weight(self, routine_id: str) -> float:
        better, _same, worse = self._tally.get(routine_id, (0, 0, 0))
        return max(0.2, 1.0 + 0.5 * better - 0.75 * worse)

    # -- choosing ------------------------------------------------------------------

    def choose(self, settings: RoutineSettings = RoutineSettings()) -> Optional[RoutineChoice]:
        if self._pending is not None:
            return self._pending
        if not self._bids:
            return None
        bid = self._bids[-1]
        if bid.halt:
            choice = self._halt_choice(bid, settings)
        else:
            if self._seq is None and self._change_due(bid, settings):
                self._start_sequence(settings)
            if self._seq is not None:
                choice = self._sequence_choice(bid, settings)
            else:
                choice = self._ordinary_choice(bid, settings)
        self._history.append(_Turn(choice.routine.family, choice.routine.id, bid.label))
        self._pending = choice
        self._unscored = choice
        return choice

    def _make(self, routine: Routine, bid: Bid, settings: RoutineSettings, reason: str, **kw: Any) -> RoutineChoice:
        pet = self._rng.choice(settings.terms())
        return RoutineChoice(routine, bid, pet, reason, depth=settings.depth, **kw)

    def _ordinary_choice(self, bid: Bid, settings: RoutineSettings) -> RoutineChoice:
        family, repair, steady, reason = self._pick_family(bid, settings)
        routine = self._pick_routine(family, bid, steady, settings)
        return self._make(routine, bid, settings, reason, repair=repair, steady=steady)

    def _halt_choice(self, bid: Bid, settings: RoutineSettings) -> RoutineChoice:
        self._end_sequence()
        routine = next(r for r in ROUTINES[Family.PRESENCE] if r.halt_only)
        return self._make(routine, bid, settings, "explicit stop; stopping everything")

    # -- diaper change sequence ------------------------------------------------------

    def _end_sequence(self) -> None:
        self._seq = None
        self._no_change_before = self._turn_no + CHANGE_COOLDOWN_TURNS

    def _change_due(self, bid: Bid, settings: RoutineSettings) -> bool:
        if not settings.allow_change_talk or not self._history:
            return False
        if self._turn_no < self._no_change_before:
            return False
        if bid.label not in (BidLabel.SETTLED, BidLabel.QUIET, BidLabel.UNKNOWN):
            return False
        if any(b.label is BidLabel.STRAINED for b in list(self._bids)[-3:]):
            return False
        return self._rng.random() < _clamp(settings.change_rate)

    def _start_sequence(self, settings: RoutineSettings) -> None:
        # The coin flip. It is made here, once, from the random source alone, so
        # nothing the baby says or sends can decide whether a change happens.
        wet = self._rng.random() < _clamp(settings.wet_chance)
        if wet:
            stages = ["check", "verdict_wet", "setup", "untape", "wipe"]
            if self._rng.random() < 0.7:
                stages.append("powder")
            if self._rng.random() < 0.6:
                stages.append("distract")
            stages += ["fresh", "tape", "present"]
        else:
            stages = ["check", "verdict_dry"]
        self._seq = _Sequence(stages, wet)

    def _sequence_choice(self, bid: Bid, settings: RoutineSettings) -> RoutineChoice:
        seq = self._seq
        assert seq is not None
        if not settings.allow_change_talk:
            # The owner switched change talk off mid-sequence: stop at once.
            self._end_sequence()
            return self._ordinary_choice(bid, settings)
        if bid.label is BidLabel.STRAINED:
            seq.strained_streak += 1
            # Before set-up nothing physical has started, so being upset just postpones
            # the change. Once it is underway, soothe in place first, and pause if the
            # upset continues.
            not_started = seq.stages[seq.index] in ("verdict_wet", "verdict_dry", "setup")
            if not_started or seq.strained_streak >= 2:
                routine = self._pick_stage("pause", settings)
                self._end_sequence()
                return self._make(routine, bid, settings, "upset during a change; pausing it", stage="pause")
            routine = self._pick_routine(Family.SOOTHE, bid, False, settings)
            return self._make(routine, bid, settings, "upset during a change; soothing, then carrying on",
                              mid_change=True)
        seq.strained_streak = 0
        stage = seq.stages[seq.index]
        routine = self._pick_stage(stage, settings)
        step = (seq.index + 1, len(seq.stages))
        verdict = ("wet" if seq.wet else "dry") if stage.startswith("verdict") else None
        seq.index += 1
        choice = self._make(routine, bid, settings, f"diaper change, step {step[0]} of {step[1]}: {stage}",
                            stage=stage, step=step, verdict=verdict)
        if seq.index >= len(seq.stages):
            self._end_sequence()
        return choice

    def _pick_stage(self, stage: str, settings: RoutineSettings) -> Routine:
        candidates = [r for r in ROUTINES[Family.CHANGE] if r.stage == stage and settings.allows(r.needs)]
        recent = self._recent_stage.setdefault(stage, deque(maxlen=2))
        pool = [r for r in candidates if r.id not in recent] or candidates
        routine = self._rng.choices(pool, weights=[self._weight(r.id) for r in pool], k=1)[0]
        recent.append(routine.id)
        return routine

    # -- ordinary selection rules ------------------------------------------------------

    def _pick_family(self, bid: Bid, settings: RoutineSettings) -> Tuple[Family, bool, bool, str]:
        last = self._history[-1] if self._history else None
        earlier_bids = list(self._bids)[-3:-1]
        label = bid.label
        if last is None:
            if label is BidLabel.STRAINED:
                return Family.SOOTHE, False, False, "first turn, and it sounds strained"
            return Family.WELCOME, False, False, "first turn of baby mode"
        if label is BidLabel.STRAINED:
            streak = 0
            for turn in reversed(self._history):
                if turn.family is not Family.SOOTHE:
                    break
                streak += 1
            if streak >= self.STREAK_LIMIT:
                return Family.PRESENCE, False, True, "soothing has not eased it; staying steady instead of switching"
            repair = last.family is Family.PLAY
            return Family.SOOTHE, repair, False, ("play was too much; easing off" if repair else "sounds strained")
        if bid.protest and last.family is Family.PLAY:
            return Family.SOOTHE, True, False, "said no during play; easing off"
        if label is BidLabel.BRIGHT:
            recently_strained = any(b.label is BidLabel.STRAINED for b in earlier_bids)
            confident = bid.confidence >= PLAY_MIN_CONFIDENCE
            if confident and not recently_strained and last.family is not Family.SOOTHE:
                return Family.PLAY, False, False, "bright and confident, and calm recently"
            return Family.SETTLE, False, False, "bright but not sure enough yet; keeping it gentle"
        if label is BidLabel.DROWSY:
            return Family.WIND_DOWN, False, False, "slowing down"
        calm = label in (BidLabel.SETTLED, BidLabel.QUIET, BidLabel.UNKNOWN)
        if calm and self._needs_due(settings):
            return Family.NEEDS, False, False, "calm moment for a light rhetorical check-in"
        if label is BidLabel.SETTLED:
            return Family.SETTLE, False, False, "calm and content"
        return Family.PRESENCE, False, False, "quiet or unclear; staying present"

    def _needs_due(self, settings: RoutineSettings) -> bool:
        """Bottle talk only. Diaper checks run as their own sequence."""
        if not settings.allow_bottle_talk:
            return False
        if any(t.family is Family.NEEDS for t in list(self._history)[-6:]):
            return False
        recent = list(self._bids)[-3:]
        if any(b.label is BidLabel.STRAINED for b in recent):
            return False
        return self._rng.random() < _clamp(settings.needs_rate)

    def _pick_routine(self, family: Family, bid: Bid, steady: bool, settings: RoutineSettings) -> Routine:
        candidates = [r for r in ROUTINES[family] if settings.allows(r.needs) and not r.halt_only]
        if steady:
            candidates = [r for r in candidates if r.steady] or candidates
        if family is Family.SETTLE and bid.label is BidLabel.BRIGHT:
            candidates = [r for r in candidates if r.gentle_play] or candidates
        recent_ids = {t.routine_id for t in list(self._history)[-self.VARIETY:] if t.family is family}
        fresh = [r for r in candidates if r.id not in recent_ids]
        pool = fresh or candidates
        return self._rng.choices(pool, weights=[self._weight(r.id) for r in pool], k=1)[0]
