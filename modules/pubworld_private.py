"""Private delivery to walker sockets (/pubworld/ws/{client_id} in main.py).

The walker's socket is not in the Hub, so ``Hub.send_private_event`` cannot reach it. This registry holds the walker
sockets whose owner has been *verified* (a valid token, never a bare client id) under that person's id, and sends an
event to exactly the people named. Host control uses it for the possession notice, drive commands and timeouts.

A person is matched case-insensitively, as the Hub does. A socket that never proved who it is is never registered, so
an unverified client can neither receive another person's notice nor be mistaken for them.
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

logger = logging.getLogger("pubcast.pubworld_private")


def _finite(v: Any, lo: float, hi: float) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi else None


class PubWorldPrivate:
    def __init__(self) -> None:
        self._by_user: Dict[str, Set[Any]] = {}
        self._presence: Dict[str, Dict[str, Any]] = {}
        self.on_room_change: Optional[Callable[[str, str, str], None]] = None      # (person, room they left, room they entered)
        self.pending_for: Optional[Callable[[str], List[Dict[str, Any]]]] = None   # what a newly connected page of this person must be told (host holds)

    def register(self, user_id: str, ws: Any) -> None:
        if isinstance(user_id, str) and user_id.strip():
            self._by_user.setdefault(user_id.casefold(), set()).add(ws)

    def unregister(self, ws: Any) -> None:
        for key in list(self._by_user):
            self._by_user[key].discard(ws)
            if not self._by_user[key]:
                del self._by_user[key]
                self._presence.pop(key, None)                  # the last socket of a person is gone: they are no longer on the roster

    # ---- who is where: only what a verified walker says about itself, cleaned, and the round trip the host measures itself ----
    def update_presence(self, user_id: str, data: Dict[str, Any], now: Optional[float] = None) -> None:
        key = str(user_id).casefold()
        if key not in self._by_user:
            return                                             # an unverified socket never appears on the roster
        pos = data.get("pos")
        pos = [_finite(pos[0], -1e5, 1e5), _finite(pos[1], -1e5, 1e5)] if isinstance(pos, list) and len(pos) == 2 else None
        if pos is not None and None in pos:
            pos = None
        old = self._presence.get(key) or {}
        rec = {"user_id": str(user_id), "room": str(data.get("room") or "")[:80], "view": str(data.get("view") or "")[:80],
               "pos": pos, "char": str(data.get("char") or "")[:48], "fps": _finite(data.get("fps"), 0, 1000),
               "meshes": _finite(data.get("meshes"), 0, 1e4), "bones": _finite(data.get("bones"), 0, 1e4), "tris": _finite(data.get("tris"), 0, 1e8),
               "rtt_ms": old.get("rtt_ms"), "seen": time.time() if now is None else now}
        self._presence[key] = rec
        if old and old.get("room") != rec["room"] and self.on_room_change:
            try:
                self.on_room_change(str(user_id), old.get("room", ""), rec["room"])
            except Exception:                                  # a listener must never break the socket
                logger.exception("room change listener failed")

    def set_rtt(self, user_id: str, ms: float) -> None:
        rec = self._presence.get(str(user_id).casefold())
        if rec is not None and _finite(ms, 0, 1e6) is not None:
            rec["rtt_ms"] = round(float(ms), 1)

    def roster(self, max_age: float = 15.0, now: Optional[float] = None) -> List[Dict[str, Any]]:
        t = time.time() if now is None else now
        return [dict(r, age=round(t - r["seen"], 1)) for k, r in sorted(self._presence.items()) if k in self._by_user and t - r["seen"] <= max_age]

    def connected(self, user_id: str) -> int:
        return len(self._by_user.get(str(user_id).casefold(), ()))

    async def send(self, user_ids: Iterable[str], event: Dict[str, Any]) -> int:
        """Send `event` to every verified socket of the named people. Returns how many sockets it was written to."""
        wire = json.dumps(event)
        delivered = 0
        for uid in {u.casefold() for u in user_ids if isinstance(u, str) and u}:
            for ws in list(self._by_user.get(uid, ())):
                try:
                    await ws.send_text(wire)
                    delivered += 1
                except Exception:
                    logger.warning("private walker delivery failed; dropping that socket")
                    self.unregister(ws)
        return delivered


__all__ = ["PubWorldPrivate"]
