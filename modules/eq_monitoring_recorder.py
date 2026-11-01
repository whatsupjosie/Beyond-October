from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

class EQMonitoringRecorder:
    """Append-only development evidence recorder.

    Observation, affect interpretation, interventions and outcomes are stored in
    separate JSONL streams. Missing telemetry stays missing; this class never
    derives typing speed from inter-message latency.
    """
    STREAMS=("transcript","telemetry","affect_trace","affect_dynamics","intervention_trace","provider_pipeline","outcomes","reviews")
    def __init__(self, data_dir:Path|str, *, enabled:bool=True, build_id:Optional[str]=None):
        self.root=Path(data_dir)/"blackbox"/"dev"/"EQ"; self.root.mkdir(parents=True,exist_ok=True)
        self.enabled=enabled; self.build_id=build_id or os.getenv("PUBCAST_BUILD_ID") or "unknown"
        self._lock=RLock(); self._sessions:dict[str,Path]={}

    @staticmethod
    def _hash(record:dict)->str:
        clean={k:v for k,v in record.items() if k!="integrity_sha256"}
        raw=json.dumps(clean,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()
        return hashlib.sha256(raw).hexdigest()

    def _session_dir(self, session_id:str)->Path:
        safe="".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)[:120] or "default"
        if safe not in self._sessions:
            d=self.root/"sessions"/safe; d.mkdir(parents=True,exist_ok=True); self._sessions[safe]=d
            manifest=d/"manifest.json"
            if not manifest.exists():
                manifest.write_text(json.dumps({"session_id":safe,"created_at":time.time(),"build_id":self.build_id,"schema":"pubcast.eq.dev.v1"},indent=2),encoding="utf-8")
        return self._sessions[safe]

    def _append(self, session_id:str, stream:str, record:dict)->dict:
        if not self.enabled: return record
        if stream not in self.STREAMS: raise ValueError(stream)
        r={"event_id":record.get("event_id") or uuid.uuid4().hex,"recorded_at":time.time(),"build_id":self.build_id,**record}
        r["integrity_sha256"]=self._hash(r)
        line=json.dumps(r,ensure_ascii=False,separators=(",",":"),default=str)+"\n"
        with self._lock:
            p=self._session_dir(session_id)/(stream+".jsonl")
            with p.open("a",encoding="utf-8",newline="\n") as f:
                f.write(line); f.flush(); os.fsync(f.fileno())
        return r

    def record_message(self,payload:Dict[str,Any],*,role:Optional[str]=None,provider:Optional[str]=None,model:Optional[str]=None)->dict:
        sid=str(payload.get("session_id") or payload.get("room") or "default")
        return self._append(sid,"transcript",{"message_id":payload.get("message_id"),"turn_id":payload.get("turn_id"),
            "timestamp":payload.get("t") or payload.get("timestamp") or time.time(),"room":payload.get("room"),
            "role":role or payload.get("role") or ("assistant" if str(payload.get("user_id") or "").startswith("bot:") else "user"),"sender_id":payload.get("user_id") or payload.get("sender_id"),
            "sender_name":payload.get("user"),"text":payload.get("text",""),"provider":provider,"model":model})

    def record_telemetry(self,session_id:str,telemetry:Dict[str,Any])->dict:
        # Missing fields remain absent/None. In particular, no typing-rate inference.
        return self._append(session_id,"telemetry",dict(telemetry))

    def record_affect(self,session_id:str,*,user_id:str,message_id:Optional[str],text:str,
                      baseline_before:Dict[str,Any],evaluation:Dict[str,Any],baseline_after:Dict[str,Any])->dict:
        return self._append(session_id,"affect_trace",{"user_id":user_id,"message_id":message_id,
            "text_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),"baseline_before":baseline_before,
            "evaluation":evaluation,"baseline_after":baseline_after})

    def record_affect_dynamics(self,session_id:str,*,user_id:str,message_id:Optional[str],dynamics:Dict[str,Any])->dict:
        return self._append(session_id,"affect_dynamics",{"user_id":user_id,"message_id":message_id,"dynamics":dynamics})

    def record_intervention(self,session_id:str,data:Dict[str,Any])->dict: return self._append(session_id,"intervention_trace",data)
    def record_provider(self,session_id:str,data:Dict[str,Any])->dict: return self._append(session_id,"provider_pipeline",data)
    def record_outcome(self,session_id:str,data:Dict[str,Any])->dict: return self._append(session_id,"outcomes",data)
    def record_review(self,session_id:str,data:Dict[str,Any])->dict: return self._append(session_id,"reviews",data)
