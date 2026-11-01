"""Data-driven offline dialogue engine for PubCast characters.

Not an LLM. A character's offline voice lives in data/characters/<id>.json:
ordered intents, each with regex patterns and several authored responses. The
engine picks the first matching intent and rotates through its responses so
asking the same thing twice does not repeat the same line. Selection is
deterministic (same message and history give the same reply), which keeps it
testable. It never invents facts: unmatched questions get the character's
honest fallback line.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "characters"
_RECENT_WINDOW = 24
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}


class CharacterDataError(ValueError):
    pass


def _validate(char_id: str, data: Mapping[str, Any]) -> Dict[str, Any]:
    intents = data.get("intents")
    if not isinstance(intents, list) or not intents:
        raise CharacterDataError(f"{char_id}: 'intents' must be a non-empty list")
    seen = set()
    compiled = []
    for i, intent in enumerate(intents):
        iid = intent.get("id")
        if not iid or iid in seen:
            raise CharacterDataError(f"{char_id}: intent #{i} missing or duplicate id {iid!r}")
        seen.add(iid)
        pats = intent.get("patterns")
        resp = intent.get("responses")
        if not pats or not all(isinstance(p, str) for p in pats):
            raise CharacterDataError(f"{char_id}.{iid}: patterns required")
        if not resp or not all(isinstance(r, str) and r.strip() for r in resp):
            raise CharacterDataError(f"{char_id}.{iid}: responses required")
        try:
            rx = [re.compile(p, re.IGNORECASE) for p in pats]
        except re.error as exc:
            raise CharacterDataError(f"{char_id}.{iid}: bad pattern: {exc}") from exc
        compiled.append({"id": iid, "rx": rx, "responses": list(resp), "ordered": bool(intent.get("ordered"))})
    fb = data.get("fallback")
    if not fb or not all(isinstance(r, str) and r.strip() for r in fb):
        raise CharacterDataError(f"{char_id}: 'fallback' list required")
    return {"intents": compiled, "fallback": list(fb), "meta": {k: v for k, v in data.items() if k not in ("intents", "fallback")}}


def load(char_id: str) -> Dict[str, Any]:
    path = DATA_DIR / f"{char_id}.json"
    mtime = path.stat().st_mtime
    hit = _cache.get(char_id)
    if hit and hit[0] == mtime:
        return hit[1]
    brain = _validate(char_id, json.loads(path.read_text(encoding="utf-8")))
    _cache[char_id] = (mtime, brain)
    return brain


def _choose(options: Sequence[str], seed: str, recent_text: str, ordered: bool = False) -> str:
    fresh = [o for o in options if o not in recent_text]
    pool = fresh or list(options)
    if ordered:
        return pool[0]
    h = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:4], "big")
    return pool[h % len(pool)]


def match_intent(char_id: str, message: str) -> Optional[str]:
    text = message.strip()
    try:
        brain = load(char_id)
    except FileNotFoundError:
        return None  # use the character module's already-authored fallback
    for intent in brain["intents"]:
        if any(rx.search(text) for rx in intent["rx"]):
            return intent["id"]
    return None


def respond(char_id: str, message: str, history: Sequence[Mapping[str, str]] = ()) -> str:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("A non-empty message is required")
    brain = load(char_id)
    recent = "\n".join(str(h.get("text", "")) for h in list(history)[-_RECENT_WINDOW:])
    seed = f"{message.strip().casefold()}|{len(history)}"
    for intent in brain["intents"]:
        if any(rx.search(message) for rx in intent["rx"]):
            return _choose(intent["responses"], seed, recent, intent["ordered"])
    return _choose(brain["fallback"], seed, recent)
