"""Sir Purfluous: deterministic offline character dialogue.

Not an LLM. The bot works without any provider or API key. A speaking model,
when connected, makes him richer; it is never required for him to function.

Every substantive line is existing authored material: the waiting-room state
lines, idle banter, monologues and borrowed lines in his character profile,
and the director notes of the standalone Purfluous bot. This module only
routes a message to the right authored line. It never claims to know the
admission verdict, never claims power over security, and never invents a
source for a fact it does not have.
"""
from __future__ import annotations

import hashlib
import re
from typing import Mapping, Sequence

from . import offline_brain
from .sir_purfluous_waiting_room import load_profile

_OFFLINE_NOTE = ("My full powers wait on the speaking model, Sancho. Offline I keep to the door, "
                 "the craft, and my own history.")


def _pick(options: Sequence[str], message: str) -> str:
    """Deterministic choice: same message, same line; different messages vary."""
    opts = [o for o in options if isinstance(o, str) and o.strip()]
    if not opts:
        return ""
    digest = hashlib.sha256(message.casefold().encode("utf-8")).digest()
    return opts[digest[0] % len(opts)]


def _state(profile: Mapping, name: str, message: str) -> str:
    return _pick((profile.get("state_lines") or {}).get(name) or [], message)


def _idle(profile: Mapping, message: str) -> str:
    lines = [i.get("line") for i in profile.get("idle_banter") or [] if isinstance(i, dict)]
    return _pick(lines, message)


def _monologue(tone: str | None, message: str) -> str:
    from .sir_purfluous_character_profile import MONOLOGUE_POOL
    pool = [m.text for m in MONOLOGUE_POOL if tone is None or m.tone == tone]
    return _pick(pool, message)


def _borrowed(trigger: str, message: str) -> str:
    from .sir_purfluous_character_profile import BORROWED_LINES
    hits = [b for b in BORROWED_LINES if b["trigger"] == trigger]
    if not hits:
        return ""
    b = hits[int(hashlib.sha256(message.encode()).digest()[0]) % len(hits)]
    return f"Borrowed from {b['source']}, and better than I could manage: “{b['line']}”"


def respond(message: str, history: Sequence[Mapping[str, str]] = ()) -> str:
    """Answer in character from authored material; never fabricate operations."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Sir Purfluous needs a non-empty message")
    text = message.strip().casefold()
    profile = load_profile()
    words = set(re.findall(r"[a-z']+", text))

    # Security and admission are never his to grant. Check these first.
    if re.search(r"\b(bypass|override|skip|let me in|get me in|unlock|disable|turn off)\b.*\b(security|door|consent|check|admission|lock)\b"
                 r"|\b(security|consent|admission)\b.*\b(bypass|override|skip|disable)\b|\bopen the door\b", text):
        return ("I am the host at the door, Sancho, not the lock upon it. I cannot waive consent, "
                "skip a check, or open what the studio has not opened. What I can do is make the waiting worth something.")
    if re.search(r"\b(approved|admitted|admission|denied|my status|am i in|how long|still waiting|when will)\b", text):
        return ("I am the host, not the ledger, Sancho; I cannot see the verdict from here, so I will not guess it. "
                "Watch the door's own notice for the answer. " + _state(profile, "pending", message))
    social = offline_brain.match_intent("sir_purfluous", message)
    if social:
        return offline_brain.respond("sir_purfluous", message, history)
    if re.search(r"\b(consent|waiver|sign|signature|terms|agree)\b", text):
        return _state(profile, "consent", message)
    if re.search(r"\b(avatar|identity|my name|what name|display name|nickname|persona)\b", text):
        return _state(profile, "identity", message)
    if re.search(r"\b(proving ground|body|walk|motion|calibrat)", text):
        return _state(profile, "proving_ground", message)

    if re.search(r"\b(who are you|your name|who is this|what are you|introduce yourself)\b", text):
        return ("Sir Purfluous, Sancho: self-appointed knight of cinema, host of this threshold, "
                "and the only man here who knighted himself and kept the receipt. " + _OFFLINE_NOTE)
    if re.search(r"\bjeremy\b|\bsystem guidance\b", text):
        return ("Guidance of that sort speaks through the studio's own notices, Sancho, not through me. "
                "I keep the door and the company.")
    if re.search(r"\b(pete|alex bourgeois|floor director)\b", text):
        return ("Pete runs the floor now, and runs it well. I will admit nothing about having trained her "
                "without a witness and a glass of something.")
    if re.search(r"\b(repete|re-pete|apprentice)\b", text):
        return "RePete is Pete's apprentice, clumsy with people and sharp with machines. A fine combination in this trade."

    # Feelings and borrowed lines.
    if re.search(r"\b(scared|afraid|nervous|anxious|worried|hopeless|lost)\b", text):
        return _borrowed("vulnerable_moment", message)
    if re.search(r"\b(encourage|motivat|pep talk|inspire|cheer me)", text):
        return _borrowed("pep_talk", message)
    if re.search(r"\b(coach|teach me|advice|how do i act|acting|actor|audition)\b", text):
        return _monologue("serious", message)
    if re.search(r"\b(story|tale|tell me|monologue|anecdote|famous|brando|taylor)\b", text):
        return _monologue("funny", message)

    if re.search(r"\b(thanks|thank you|cheers)\b", text):
        return "Gratitude accepted, Sancho, and entered in the ledger of small mercies."
    if re.search(r"\b(bye|goodbye|farewell|see you|good night)\b", text):
        return "Exit, pursued by applause. Go well, Sancho."
    if re.search(r"\b(hello|hey|hi|morning|evening|welcome|greetings)\b", text) or len(words) <= 1:
        return _state(profile, "arrival", message)

    # Honest limit: no invented sources, no pretending to understand.
    return ("That, Sancho, is a larger question than I can answer without the speaking model, and I will not "
            "invent an answer to flatter the lighting. " + _idle(profile, message))
