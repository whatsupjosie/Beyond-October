from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

@dataclass(frozen=True)
class VectorClock:
    values: Dict[str, int] = field(default_factory=dict)
    def normalized(self):
        return VectorClock({k:int(v) for k,v in self.values.items() if int(v)>0})
    def increment(self,node_id):
        v=dict(self.values); v[node_id]=v.get(node_id,0)+1; return VectorClock(v)
    def merge(self,other):
        keys=set(self.values)|set(other.values)
        return VectorClock({k:max(self.values.get(k,0),other.values.get(k,0)) for k in keys})
    def dominates(self,other):
        keys=set(self.values)|set(other.values)
        ge=all(self.values.get(k,0)>=other.values.get(k,0) for k in keys)
        gt=any(self.values.get(k,0)>other.values.get(k,0) for k in keys)
        return ge and (gt or self.normalized().values==other.normalized().values)
    def strictly_dominates(self, other):
        keys=set(self.values)|set(other.values)
        ge=all(self.values.get(k,0)>=other.values.get(k,0) for k in keys)
        gt=any(self.values.get(k,0)>other.values.get(k,0) for k in keys)
        return ge and gt

    def concurrent_with(self,other):
        return not self.dominates(other) and not other.dominates(self)
    def to_dict(self): return dict(self.normalized().values)
    @classmethod
    def from_dict(cls,value):
        return cls({str(k):int(v) for k,v in (value or {}).items() if int(v)>0}).normalized()

@dataclass(frozen=True)
class Entity:
    entity_type:str
    entity_id:str
    fields:Dict[str,Any]
    version:VectorClock
    deleted:bool=False
    def to_dict(self):
        return {"entity_type":self.entity_type,"entity_id":self.entity_id,"fields":self.fields,
                "version":self.version.to_dict(),"deleted":self.deleted}
    @classmethod
    def from_dict(cls,value):
        return cls(str(value["entity_type"]),str(value["entity_id"]),dict(value.get("fields") or {}),
                   VectorClock.from_dict(value.get("version")),bool(value.get("deleted",False)))

@dataclass(frozen=True)
class Change:
    change_id:str
    node_id:str
    entity_type:str
    entity_id:str
    fields:Dict[str,Any]
    version:VectorClock
    base_version:VectorClock
    deleted:bool=False
    def to_dict(self):
        return {"change_id":self.change_id,"node_id":self.node_id,"entity_type":self.entity_type,
                "entity_id":self.entity_id,"fields":self.fields,"version":self.version.to_dict(),
                "base_version":self.base_version.to_dict(),"deleted":self.deleted}
    @classmethod
    def from_dict(cls,value):
        return cls(str(value["change_id"]),str(value["node_id"]),str(value["entity_type"]),str(value["entity_id"]),
                   dict(value.get("fields") or {}),VectorClock.from_dict(value.get("version")),
                   VectorClock.from_dict(value.get("base_version")),bool(value.get("deleted",False)))

@dataclass(frozen=True)
class Conflict:
    entity_type:str
    entity_id:str
    local:Entity
    remote:Entity
    reason:str="concurrent_field_conflict"
    def to_dict(self):
        return {"entity_type":self.entity_type,"entity_id":self.entity_id,"reason":self.reason,
                "local":self.local.to_dict(),"remote":self.remote.to_dict()}

@dataclass(frozen=True)
class SyncCursor:
    version:VectorClock
    def to_dict(self): return {"version":self.version.to_dict()}
    @classmethod
    def from_dict(cls,value): return cls(VectorClock.from_dict((value or {}).get("version")))

@dataclass(frozen=True)
class SyncEnvelope:
    protocol:str
    sender_node:str
    changes:tuple[Change,...]
    cursor:SyncCursor
    capabilities:tuple[str,...]=()
    conflicts:tuple[Conflict,...]=()
    def to_dict(self):
        return {"protocol":self.protocol,"sender_node":self.sender_node,
                "changes":[c.to_dict() for c in self.changes],"cursor":self.cursor.to_dict(),
                "capabilities":list(self.capabilities),"conflicts":[c.to_dict() for c in self.conflicts]}
    @classmethod
    def from_dict(cls,value):
        return cls(str(value["protocol"]),str(value["sender_node"]),
                   tuple(Change.from_dict(x) for x in value.get("changes",[])),
                   SyncCursor.from_dict(value.get("cursor")),
                   tuple(str(x) for x in value.get("capabilities",[])),())
