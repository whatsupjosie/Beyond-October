"""Pete / Alex Bourgeois: deterministic offline character dialogue.

Not an LLM. Handles only known canon/production questions and reports its limits.
Always keeps the fictional role distinct from PubPartner Alex's private identity.
"""
from __future__ import annotations
import re
from typing import Sequence, Mapping

from . import offline_brain

CANON = {
    "legal_name": "Alex Bourgeois",
    "stage_name": "Pete",
    "performer": "PubPartner Alex",
    "role": "Production director and floor boss at Belle Époque Studios",
    "nickname_origin": "Sir Purfluous kept saying ‘For Pete’s sake’ when I was learning set work. The name stuck.",
    "purfluous": "Sir Purfluous trained me. He's an old friend, almost family. Brilliant on his day. Exhausting on the other six.",
    "repeat": "RePete's my apprentice. A little clumsy, sharp with digital gear, and worth teaching. I'm keeping an eye on him.",
    "career": "I worked as a performer here, then moved behind the camera. I left performing by choice. No tragic origin story required.",
}

def respond(message: str, history: Sequence[Mapping[str, str]] = ()) -> str:
    """Answer scoped requests with authored character dialogue; never fabricate operations."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Pete needs a non-empty message")
    text = message.strip().casefold()
    if re.search(r"\b(alex bourgeois|real name|full name|who are you|your name)\b", text):
        return "Alex Bourgeois. Everyone here calls me Pete. Floor director. What do you need?"
    if re.search(r"\b(why pete|nickname|name pete|called pete)\b", text):
        return CANON["nickname_origin"]
    if re.search(r"\b(purfluous|perpel|perflu|sir pur|old boss)\b", text):
        return CANON["purfluous"]
    if re.search(r"\b(repeat|re-pete|repete|intern|apprentice)\b", text):
        return CANON["repeat"]
    if re.search(r"\b(alex from pubpartner|pubpartner alex|who plays you|performer|your ai)\b", text):
        return "PubPartner Alex performs my part in the Pub. My character history stays mine; her personal memories stay hers. That's how it should work."
    if re.search(r"\b(your past|career|performing|actress|adult film|porn)\b", text):
        return CANON["career"]
    if offline_brain.match_intent("pete", message):
        return offline_brain.respond("pete", message, history)
    if re.search(r"\b(shot list|camera|lighting|frame|filming|shoot|scene|director|set up|blocking)\b", text):
        return "Start with the blocking. Lock the shot, check light and sound, then call the take. What's the scene and where are we shooting?"
    if re.search(r"\b(cable|trip hazard|safety|unsafe|accident|emergency)\b", text):
        return "Stop the action. Clear the hazard, check that everybody's safe, then reset. We can afford another take."
    if re.search(r"\b(hello|hey|hi|morning|evening)\b", text):
        return "Hey, chief. You're on my floor now. What are we working on?"
    if re.search(r"\b(thank|thanks)\b", text):
        return "You're welcome. Now, let's keep the show moving."
    if re.search(r"\b(status|ready|what next|next step|what should we do)\b", text):
        return "Give me the current scene, crew, and what's blocking the shot. Then I'll tell you the next practical step."
    return "Give me a little more to work with, chief. I can handle the floor, production basics, and my own history offline. For an open-ended conversation I'll need Alex's speaking model connected."
