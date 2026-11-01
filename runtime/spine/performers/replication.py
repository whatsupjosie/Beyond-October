from __future__ import annotations

from typing import Any, Dict, Iterable

from .performer_state import PerformerState


def build_replication_snapshot(performers: Iterable[PerformerState], *, dirty_only: bool = False, mark_clean: bool = False) -> Dict[str, Any]:
    items = []
    for performer in performers:
        if dirty_only and not performer.dirty:
            continue
        items.append(performer.to_dict())
        if mark_clean:
            performer.mark_clean()
    return {"performers": items, "count": len(items)}