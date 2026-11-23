"""Evidence-linked, user-controlled PubPartner calibration interviews.

This store records feedback and its provenance. It does not infer emotion or
rewrite a personality automatically. The partner/EQ pipeline consumes approved
feedback in a separately reviewed integration.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

MODES = {"user", "system"}
MAX_MAIN = 5
TARGET_MAIN = 3
MAX_FOLLOW_UPS_PER_MAIN = 1


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "anon")).strip("._-")
    return (cleaned or "anon")[:96]


class CalibrationError(ValueError):
    pass


class CalibrationStore:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "pubpartner" / "calibration"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str, interview_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", interview_id):
            raise CalibrationError("invalid interview id")
        return self.root / _slug(user_id) / (interview_id + ".json")

    def _write(self, path: Path, document: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("x", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()

    def start(self, *, user_id: str, partner_id: str, mode: str) -> Dict[str, Any]:
        if mode not in MODES:
            raise CalibrationError("mode must be user or system")
        if not str(partner_id).strip():
            raise CalibrationError("partner_id is required")
        interview_id = uuid.uuid4().hex
        document = {
            "id": interview_id,
            "user_id": str(user_id),
            "partner_id": str(partner_id)[:120],
            "mode": mode,
            "state": "formal",
            "target_main_questions": TARGET_MAIN,
            "max_main_questions": MAX_MAIN,
            "main_questions_asked": 0,
            "questions": [],
            "continuation": [],
            "created_at": time.time(),
        }
        self._write(self._path(user_id, interview_id), document)
        return document

    def get(self, *, user_id: str, interview_id: str) -> Dict[str, Any]:
        path = self._path(user_id, interview_id)
        if not path.exists():
            raise FileNotFoundError("calibration interview not found")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("user_id") != str(user_id):
            raise FileNotFoundError("calibration interview not found")
        return data

    def record(self, *, user_id: str, interview_id: str, action: str,
               text: str = "", question_id: str = "", evidence: Dict[str, Any] | None = None,
               modality: str = "text") -> Dict[str, Any]:
        document = self.get(user_id=user_id, interview_id=interview_id)
        if modality not in {"text", "voice"}:
            raise CalibrationError("modality must be text or voice")
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise CalibrationError("text must contain 1 to 16000 characters")
        if evidence is None:
            evidence = {}
        if not isinstance(evidence, dict):
            raise CalibrationError("evidence must be an object")
        # Reference only: no invented audio or archive claims, no embedded recording.
        allowed_evidence = {k: str(evidence[k])[:200] for k in
                            ("session_id", "turn_id", "source_id", "audio_ref")
                            if k in evidence and evidence[k] is not None}
        stamp = {"text": text, "modality": modality, "evidence": allowed_evidence, "at": time.time()}
        if action == "main_question":
            if document["state"] != "formal":
                raise CalibrationError("formal interview has ended")
            if len(document["questions"]) >= MAX_MAIN:
                raise CalibrationError("five main questions maximum")
            stamp.update({"id": uuid.uuid4().hex, "answer": None, "follow_up": None,
                          "follow_up_answer": None})
            document["questions"].append(stamp)
            document["main_questions_asked"] = len(document["questions"])
        elif action in {"answer", "follow_up", "follow_up_answer"}:
            if document["state"] != "formal":
                raise CalibrationError("formal interview has ended")
            question = next((q for q in document["questions"] if q["id"] == question_id), None)
            if question is None:
                raise CalibrationError("unknown main question")
            if action == "answer":
                if question["answer"] is not None:
                    raise CalibrationError("question already answered")
                question["answer"] = stamp
            elif action == "follow_up":
                if question["answer"] is None or question["follow_up"] is not None:
                    raise CalibrationError("follow-up requires answer and is limited to one")
                question["follow_up"] = stamp
            else:
                if question["follow_up"] is None or question["follow_up_answer"] is not None:
                    raise CalibrationError("follow-up answer requires an unanswered follow-up")
                question["follow_up_answer"] = stamp
        elif action in {"continuation", "clarification"}:
            # After formal close, clarification never increments the main-question count.
            if document["state"] != "open":
                raise CalibrationError("continuation is available after formal close")
            stamp["kind"] = action
            document["continuation"].append(stamp)
        else:
            raise CalibrationError("unsupported calibration action")
        self._write(self._path(user_id, interview_id), document)
        return document

    def finish_formal(self, *, user_id: str, interview_id: str) -> Dict[str, Any]:
        document = self.get(user_id=user_id, interview_id=interview_id)
        if document["state"] == "formal":
            document["state"] = "open"
            document["formal_closed_at"] = time.time()
            self._write(self._path(user_id, interview_id), document)
        return document

    def close(self, *, user_id: str, interview_id: str) -> Dict[str, Any]:
        document = self.get(user_id=user_id, interview_id=interview_id)
        document["state"] = "closed"
        document["closed_at"] = time.time()
        self._write(self._path(user_id, interview_id), document)
        return document

    def list_interviews(self, *, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        folder = self.root / _slug(user_id)
        rows = []
        if folder.exists():
            for path in folder.glob("*.json"):
                try:
                    rows.append(self.get(user_id=user_id, interview_id=path.stem))
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    continue
        return sorted(rows, key=lambda d: d["created_at"], reverse=True)[:max(1, min(100, limit))]

    def save_audio(self, *, user_id: str, interview_id: str,
                   data: bytes, content_type: str) -> Dict[str, Any]:
        """Save an explicitly recorded sample. No automatic audio collection."""
        interview = self.get(user_id=user_id, interview_id=interview_id)
        if interview.get("state") == "closed":
            raise CalibrationError("cannot add audio to a closed interview")
        mime = content_type.split(";", 1)[0].strip().lower()
        allowed = {"audio/webm": "webm", "audio/ogg": "ogg",
                   "audio/mp4": "m4a", "audio/wav": "wav",
                   "audio/x-wav": "wav"}
        if mime not in allowed:
            raise CalibrationError("unsupported audio format")
        if not data or len(data) > 4 * 1024 * 1024:
            raise CalibrationError("audio sample must be between 1 byte and 4 MB")
        audio_id = uuid.uuid4().hex
        directory = self.root / _slug(user_id) / "audio" / interview_id
        directory.mkdir(parents=True, exist_ok=True)
        if len(list(directory.glob("*"))) >= 50:
            raise CalibrationError("audio sample limit reached for this interview")
        path = directory / (audio_id + "." + allowed[mime])
        with path.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        return {"ok": True, "audio_ref": audio_id, "bytes": len(data),
                "content_type": mime, "interview_id": interview_id}

    def audio_path(self, *, user_id: str, interview_id: str,
                   audio_ref: str) -> Path:
        self.get(user_id=user_id, interview_id=interview_id)
        if not re.fullmatch(r"[a-f0-9]{32}", audio_ref):
            raise CalibrationError("invalid audio reference")
        directory = self.root / _slug(user_id) / "audio" / interview_id
        files = [p for p in directory.glob(audio_ref + ".*") if p.suffix in {".webm", ".ogg", ".m4a", ".wav"}] if directory.exists() else []
        if len(files) != 1:
            raise FileNotFoundError("audio not found")
        return files[0]
