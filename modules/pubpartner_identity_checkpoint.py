"""Experimental PubPartner pre-response identity checkpoint.

The full checkpoint runs before response 1 and every third response thereafter
(1, 4, 7, ...). Ordinary turns still carry the active FCP1 identity packet.
The one-second minimum starts AFTER the model-facing packet has been assembled,
so the time cannot accidentally overlap unrelated packet construction.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Mapping

INTERVAL = 3
MINIMUM_SECONDS = 1.0


def scheduled(response_number: int) -> bool:
    if response_number < 1:
        raise ValueError("response_number must be positive")
    return (response_number - 1) % INTERVAL == 0


def validate_identity_packet(turn: Mapping[str, Any]) -> dict:
    """Fail closed instead of dispatching a response with no character identity."""
    fcp = turn.get("fcp1")
    if not isinstance(fcp, dict):
        raise ValueError("Missing FCP1 identity packet")
    friend = fcp.get("f")
    if not isinstance(friend, dict) or not str(friend.get("id") or friend.get("friend_id") or "").strip():
        raise ValueError("Missing friend identity in FCP1 packet")
    # A complete packet must contain the identity, user, policy, memory and
    # guidance compartments even when a new character has zero memories.
    for key in ("u", "m", "guide", "safe", "history", "source_policy"):
        if key not in fcp:
            raise ValueError(f"Missing FCP1 identity-review compartment: {key}")
    prompt = turn.get("llm_prompt_text")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Missing model-facing identity context")
    if not prompt.startswith("@FCP1") or "\nf=" not in prompt or "\nu=" not in prompt:
        raise ValueError("Model-facing prompt omitted the FCP1 identity or user")
    if fcp["m"] and "\nm=" not in prompt:
        raise ValueError("Retrieved memories missing from model-facing prompt")
    if fcp["guide"] and "\nguide=" not in prompt:
        raise ValueError("Behavioral guidance missing from model-facing prompt")
    return {
        "friend_id": str(friend.get("id") or friend.get("friend_id")),
        "memory_count": int(turn.get("memory_count") or 0),
        "guidance_count": int(turn.get("guidance_count") or 0),
    }


async def checkpoint(turn: Mapping[str, Any], response_number: int, *,
                     clock=time.monotonic, sleep=asyncio.sleep,
                     minimum_seconds: float = MINIMUM_SECONDS) -> dict:
    """Validate the prepared identity and enforce the full interval if scheduled."""
    start = clock()
    details = validate_identity_packet(turn)
    full = scheduled(response_number)
    if full:
        await sleep(max(0.0, minimum_seconds - (clock() - start)))
    elapsed = clock() - start
    if full and elapsed < minimum_seconds:
        await sleep(minimum_seconds - elapsed)
        elapsed = clock() - start
    return {
        "response_number": response_number,
        "full_refresh": full,
        "minimum_seconds": minimum_seconds if full else 0.0,
        "elapsed_ms": round(elapsed * 1000, 2),
        **details,
    }
