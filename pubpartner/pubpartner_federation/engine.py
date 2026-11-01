from __future__ import annotations
import hashlib,json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any,Dict,Optional
from .protocol import Change,Conflict,Entity,SyncCursor,SyncEnvelope,VectorClock
from .store import SyncStore

@dataclass(frozen=True)
class ApplyResult:
    applied:bool
    duplicate:bool=False
    conflict:Optional[Conflict]=None
    ignored:bool=False

class SyncEngine:
    """Offline-first bidirectional sync with patch changes and vector clocks."""
    PROTOCOL="pubpartner-sync/0.1"
    # Fields that carry per-commit provenance rather than authored content.
    # They change on every write by definition, so treating them as
    # conflict-bearing made every genuinely concurrent edit collide on
    # bookkeeping even when the authored fields merged cleanly. They are
    # resolved as last-writer-wins registers instead, using a total order both
    # replicas compute identically.
    DEFAULT_LWW_FIELDS={"manuscript":frozenset({"message_id","timestamp"})}

    def __init__(self,node_id:str,store:SyncStore,lww_fields:Optional[Dict[str,frozenset]]=None):
        if not node_id.strip(): raise ValueError("node_id must not be empty")
        self.node_id=node_id; self.store=store
        self.lww_fields=dict(self.DEFAULT_LWW_FIELDS if lww_fields is None else lww_fields)
        # Recovered from disk, not reset. See SyncStore.load_clock.
        self.clock=store.load_clock()

    @contextmanager
    def _transaction(self):
        with self.store.lock:
            previous_clock = self.clock
            try:
                with self.store.transaction():
                    yield
            except BaseException:
                self.clock = previous_clock
                raise

    def _advance(self,clock:VectorClock)->None:
        self.clock=clock; self.store.save_clock(clock)

    def _lww(self,entity_type:str)->frozenset:
        return self.lww_fields.get(entity_type,frozenset())

    def upsert(self,entity_type:str,entity_id:str,fields:Dict[str,Any])->Change:
        with self._transaction():
            current=self.store.get(entity_type,entity_id)
            base=current.version if current else VectorClock()
            self._advance(self.clock.merge(base).increment(self.node_id))
            merged=dict(current.fields) if current and not current.deleted else {}
            merged.update(fields)
            entity=Entity(entity_type,entity_id,merged,self.clock,False)
            self.store.put(entity, changed_fields=fields.keys())
            change=self._change(entity,base,fields,False)
            self.store.record_change(change)
            self.store.mark_change(change.change_id)
            return change
    def delete(self,entity_type:str,entity_id:str)->Change:
        with self._transaction():
            current=self.store.get(entity_type,entity_id)
            base=current.version if current else VectorClock()
            self._advance(self.clock.merge(base).increment(self.node_id))
            entity=Entity(entity_type,entity_id,{},self.clock,True)
            self.store.put(entity)
            change=self._change(entity,base,{},True)
            self.store.record_change(change)
            self.store.mark_change(change.change_id)
            return change
    def apply(self,change:Change)->ApplyResult:
        with self._transaction():
            if self.store.has_change(change.change_id): return ApplyResult(False,duplicate=True)
            remote=change
            local=self.store.get(change.entity_type,change.entity_id)
            self._advance(self.clock.merge(change.version))
    
            if local is None:
                entity=remote_to_entity(remote)
                # Record field versions on creation too. Omitting them left
                # every field of a remotely-created entity at version {}, which
                # can never strictly dominate a later remote patch's base — so a
                # second node's concurrent creation of the same entity id
                # overwrote the first author's content with no conflict
                # recorded. That is silent data loss under section 21.
                self.store.put(entity, changed_fields=remote.fields.keys())
                self.store.record_change(change); self.store.mark_change(change.change_id)
                return ApplyResult(True)
    
            if local.version.dominates(remote.version):
                self.store.record_change(change); self.store.mark_change(change.change_id); return ApplyResult(False,ignored=True)
    
            if remote.version.dominates(local.version):
                # A change carries a PATCH, not a whole entity. Replacing the
                # stored fields with remote_to_entity(remote) therefore deleted
                # every field the patch did not mention. This was harmless only
                # while every commit submitted the complete manuscript; once
                # commits became real deltas, a peer editing one field wiped the
                # other six on every replica that received it. Merge instead.
                if remote.deleted:
                    self.store.put(Entity(local.entity_type,local.entity_id,{},remote.version,True))
                else:
                    merged={} if local.deleted else dict(local.fields)
                    merged.update(remote.fields)
                    self.store.put(Entity(local.entity_type,local.entity_id,merged,remote.version,False),
                                   changed_fields=remote.fields.keys())
                self.store.record_change(change); self.store.mark_change(change.change_id)
                return ApplyResult(True)
    
            # Concurrent: compare only fields actually changed by the remote patch.
            if remote.deleted:
                reason="concurrent_delete_update"
                self.store.add_conflict(local,remote_to_entity(remote),reason)
                self.store.record_change(change); self.store.mark_change(change.change_id)
                return ApplyResult(False,conflict=Conflict(local.entity_type,local.entity_id,local,remote_to_entity(remote),reason))
    
            if local.deleted:
                reason="concurrent_update_delete"
                self.store.add_conflict(local,remote_to_entity(remote),reason)
                self.store.record_change(change); self.store.mark_change(change.change_id)
                return ApplyResult(False,conflict=Conflict(local.entity_type,local.entity_id,local,remote_to_entity(remote),reason))
    
            lww=self._lww(local.entity_type)
            conflicts=[]
            for key,remote_value in remote.fields.items():
                if key in lww: continue
                local_field_version=self.store.field_version(local.entity_type,local.entity_id,key)
                if local_field_version.strictly_dominates(remote.base_version):
                    if local.fields.get(key) != remote_value:
                        conflicts.append(key)
    
            if conflicts:
                reason="concurrent_fields:"+",".join(sorted(conflicts))
                self.store.add_conflict(local,remote_to_entity(remote),reason)
                self.store.record_change(change); self.store.mark_change(change.change_id)
                return ApplyResult(False,conflict=Conflict(local.entity_type,local.entity_id,local,remote_to_entity(remote),reason))
    
            merged=dict(local.fields)
            applied_fields=[]
            for key,value in remote.fields.items():
                local_field_version=self.store.field_version(local.entity_type,local.entity_id,key)
                if key in lww:
                    # Both replicas compare the same pair of clocks with the
                    # same total order, so both pick the same winner.
                    if _register_order(remote.version) > _register_order(local_field_version):
                        merged[key]=value
                        applied_fields.append(key)
                    continue
                if not local_field_version.strictly_dominates(remote.base_version):
                    merged[key]=value
                    applied_fields.append(key)
            merged_entity=Entity(local.entity_type,local.entity_id,merged,
                                 local.version.merge(remote.version),False)
            self.store.put(merged_entity, changed_fields=applied_fields)
            self.store.record_change(change); self.store.mark_change(change.change_id)
            return ApplyResult(True)
    def envelope(self,known:Optional[VectorClock]=None)->SyncEnvelope:
        known=known or VectorClock()
        return SyncEnvelope(self.PROTOCOL,self.node_id,tuple(self.store.export_changes(known)),
                            SyncCursor(self.clock),
                            ("entity-sync","vector-clocks","patch-changes","idempotency",
                             "conflict-recording","tombstones"),())

    def receive(self,envelope:SyncEnvelope)->list[ApplyResult]:
        if envelope.protocol!=self.PROTOCOL: raise ValueError(f"unsupported sync protocol: {envelope.protocol!r}")
        with self._transaction():
            return [self.apply(c) for c in envelope.changes]

    def _change(self,entity,base,patch,deleted):
        material={"entity_type":entity.entity_type,"entity_id":entity.entity_id,
                  "fields":patch,"version":entity.version.to_dict(),"base_version":base.to_dict(),"deleted":deleted}
        digest=hashlib.sha256(json.dumps(material,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return Change(digest,self.node_id,entity.entity_type,entity.entity_id,dict(patch),entity.version,base,deleted)

def _register_order(clock:VectorClock)->tuple[int,str]:
    """Total order over vector clocks, used only to settle LWW registers."""
    values=clock.to_dict()
    return (sum(values.values()), json.dumps(values,sort_keys=True,separators=(",",":")))


def remote_to_entity(change:Change)->Entity:
    return Entity(change.entity_type,change.entity_id,dict(change.fields),change.version,change.deleted)
