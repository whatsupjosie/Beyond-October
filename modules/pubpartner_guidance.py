"""User guidance memory for PubPartner.

This is the product feature that remembers the annoying rules the user should
not have to repeat: style corrections, workflow preferences, exact-text rules,
provider complaints, and friend-specific instructions.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_slug(value: str, fallback: str = "anon") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._-")
    return (cleaned or fallback)[:120]


def _now() -> float:
    return time.time()


class PubPartnerGuidanceStore:
    """Append-only JSONL guidance store with compact retrieval."""

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "pubpartner" / "guidance"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        return self.root / f"{_safe_slug(user_id)}.jsonl"

    def add(
        self,
        *,
        user_id: str,
        text: str,
        friend_id: str = "*",
        project_id: str = "*",
        kind: str = "preference",
        priority: int = 5,
        applies_to: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("guidance text is required")
        row = {
            "id": f"gdn_{int(_now() * 1000)}_{uuid.uuid4().hex[:8]}",
            "user_id": user_id or "anon",
            "friend_id": friend_id or "*",
            "project_id": project_id or "*",
            "kind": str(kind or "preference")[:60],
            "text": text.strip()[:1000],
            "priority": max(1, min(10, int(priority))),
            "applies_to": [str(v)[:80] for v in (applies_to or [])][:12],
            "metadata": dict(metadata or {}),
            "created_at": _now(),
            "active": True,
        }
        with self._path(row["user_id"]).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return {"ok": True, "guidance": row}

    def list(self, *, user_id: str, friend_id: str = "*", project_id: str = "*", limit: int = 100) -> Dict[str, Any]:
        rows = self._read(user_id)
        filtered = [r for r in rows if self._matches(r, friend_id=friend_id, project_id=project_id)]
        filtered.sort(key=lambda r: (int(r.get("priority", 0)), float(r.get("created_at", 0))), reverse=True)
        return {"ok": True, "guidance": filtered[: max(1, min(500, int(limit)))]}

    def compact(self, *, user_id: str, friend_id: str, project_id: str, task: Optional[Dict[str, Any]] = None, limit: int = 8) -> List[Dict[str, Any]]:
        rows = self.list(user_id=user_id, friend_id=friend_id, project_id=project_id, limit=200)["guidance"]
        task_text = " ".join(str(v).lower() for v in (task or {}).values())
        scored: List[tuple[int, float, Dict[str, Any]]] = []
        for row in rows:
            score = int(row.get("priority", 5)) * 10
            applies = [str(v).lower() for v in row.get("applies_to") or []]
            if applies and any(a in task_text for a in applies):
                score += 20
            if row.get("friend_id") == friend_id:
                score += 5
            if row.get("project_id") == project_id:
                score += 5
            scored.append((score, float(row.get("created_at", 0)), row))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        out: List[Dict[str, Any]] = []
        for _, _, row in scored[: max(0, min(24, int(limit)))]:
            out.append({
                "id": row.get("id"),
                "k": row.get("kind"),
                "prio": row.get("priority"),
                "txt": str(row.get("text") or "")[:220],
            })
        return out

    def _read(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._path(user_id or "anon")
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("active", True):
                rows.append(row)
        return rows

    def _matches(self, row: Dict[str, Any], *, friend_id: str, project_id: str) -> bool:
        row_friend = str(row.get("friend_id") or "*")
        row_project = str(row.get("project_id") or "*")
        return row_friend in {"*", friend_id, ""} and row_project in {"*", project_id, ""}
