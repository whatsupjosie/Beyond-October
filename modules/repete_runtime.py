"""RePete: deterministic offline character dialogue (data-driven, not an LLM)."""
from __future__ import annotations
from typing import Mapping, Sequence
from . import offline_brain


def respond(message: str, history: Sequence[Mapping[str, str]] = ()) -> str:
    return offline_brain.respond("repeat", message, history)
