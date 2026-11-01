from __future__ import annotations
import os, json, secrets
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .identity import load_or_create_identity
from .memory import MemoryGate
from .engine import SyncEngine
from .store import SyncStore
from .protocol import Entity, SyncEnvelope, VectorClock
MANUSCRIPT_TYPE='manuscript'
# Authored content, in the order a writer thinks about it. Anything outside
# this set is provenance and is resolved as a last-writer-wins register by the
# engine rather than treated as an authored revision.
MANUSCRIPT_AUTHORED_FIELDS=('content','character_names','plot_elements','style_notes','user_id')
@dataclass
class Config:
    values:dict[str,str]
    def __init__(self, values=None): self.values=dict(values or {})
    def get(self,key,default=None): return self.values.get(key, os.getenv(key,default))
class State:
    def __init__(self,cfg:Config):
        self.cfg=cfg; data=Path(cfg.get('PP_DATA_DIR','./data')); data.mkdir(parents=True,exist_ok=True)
        role=cfg.get('PP_ROLE','resident'); node_id=cfg.get('PP_NODE_ID')
        self.identity=load_or_create_identity(data/'identity.json',role,node_id)
        self.store=SyncStore(data/'sync.db'); self.engine=SyncEngine(self.identity.node_id,self.store)
        self.memory=MemoryGate(data/'memory.db')
    def close(self): self.store.close(); self.memory.db.close()
def create_app(config:Config|None=None):
    cfg=config or Config(); state=State(cfg); app=FastAPI(title='pubpartner-federation')
    app.state.pp=state
    # CORS: this service has no browser UI of its own, so Foresight (served
    # from PubCast on a different port/origin) polls it directly via fetch().
    # Ports match the local dev defaults documented in the Foresight handoff;
    # extend this list if you run PubCast or Foresight from a different port.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            'http://localhost:8000', 'http://127.0.0.1:8000',
            'http://localhost:3000', 'http://127.0.0.1:3000',
        ],
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type', 'Authorization'],
    )
    def auth(authorization: str|None):
        expected=cfg.get('PP_API_KEY')
        if not expected: return
        # Constant-time: a plain != leaks the shared secret one byte at a time
        # to anyone who can measure response latency across enough attempts.
        #
        # Compare as bytes, not str. compare_digest on str operands raises
        # TypeError the moment either side contains a non-ASCII character, so
        # a header of 'Bearer héllo' turned a 401 into an unhandled 500 —
        # trading a timing leak for a trivially reachable crash on a public
        # endpoint. Latin-1 round-trips every byte an HTTP header can carry.
        presented=(authorization or '').encode('latin-1', 'replace')
        if not secrets.compare_digest(presented, f'Bearer {expected}'.encode('latin-1', 'replace')):
            raise HTTPException(401,'invalid bearer token')

    def peer_auth(inbound: str|None)->dict[str,str]:
        """Credential presented TO a peer during sync.

        Forwarding the caller's own Authorization header assumed every node in
        the federation shares one secret and handed this node's inbound
        credential to a third party. PP_PEER_API_KEY lets a deployment give the
        peer its own credential; the previous behaviour remains the default so
        existing single-secret setups keep working.
        """
        peer_key=cfg.get('PP_PEER_API_KEY')
        if peer_key: return {'Authorization':f'Bearer {peer_key}'}
        return {'Authorization':inbound} if inbound else {}
    @app.get('/health')
    def health():
        return {'status':'healthy','service':'pubpartner-federation','role':state.identity.role,'node_id':state.identity.node_id,'protocol':state.engine.PROTOCOL,'auth_configured':bool(cfg.get('PP_API_KEY'))}
    @app.post('/api/manuscript/commit')
    def manuscript_commit(body:dict[str,Any], authorization: str|None=Header(default=None)):
        auth(authorization)
        for key in ('project_id','chapter_id','content'):
            if not isinstance(body.get(key),str) or not body[key].strip(): raise HTTPException(400,f'{key} must be a non-empty string')
        mid=f"{body['project_id']}:{body['chapter_id']}"
        submitted={'content':body['content'],'character_names':body.get('character_names',[]),'plot_elements':body.get('plot_elements',[]),'style_notes':body.get('style_notes',[]),'user_id':body.get('user_id','josie')}
        current=state.store.get(MANUSCRIPT_TYPE,mid)
        # What the client last saw. Optional for backward compatibility, but a
        # client that omits it cannot be protected from the failure below.
        raw_base=body.get('base_version')
        base_version=VectorClock.from_dict(raw_base) if isinstance(raw_base,dict) else None
        # 2i submits the complete manuscript on every commit, because an editor
        # holds the whole document. Recording all of it as changed told the
        # federation engine that untouched fields had been authored at their
        # existing values, so a peer's genuine edit to one field collided with
        # this node's stale resubmission of that same field. Commit the actual
        # delta instead: the wire contract with 2i is unchanged, and the
        # field-level merge engine finally sees real field-level patches.
        stale_fields=[]
        if current is None or current.deleted:
            patch=dict(submitted)
        else:
            # Computing the delta against CURRENT state is not sufficient on its
            # own. An editor holds a whole document; if a peer changed a field
            # the editor has not reloaded, the editor's copy of that field still
            # differs from current state and is indistinguishable from a
            # deliberate revert. That silently destroyed the peer's edit on every
            # replica, with no conflict recorded.
            #
            # base_version is what the client last saw. A field whose version has
            # moved past that base changed underneath the client, so the client's
            # value is stale, not authored. Refuse it and record the collision
            # instead of overwriting.
            patch={}
            for key,value in submitted.items():
                if current.fields.get(key)==value: continue
                if base_version is not None and state.store.field_version(
                        MANUSCRIPT_TYPE,mid,key).strictly_dominates(base_version):
                    stale_fields.append(key); continue
                patch[key]=value
        if stale_fields:
            attempted=Entity(MANUSCRIPT_TYPE,mid,dict(submitted),base_version or VectorClock(),False)
            state.store.add_conflict(current,attempted,'stale_client_fields:'+','.join(sorted(stale_fields)))
        if not patch:
            return {'status':'stale' if stale_fields else 'unchanged','manuscript_id':mid,'project_id':body['project_id'],'chapter_id':body['chapter_id'],'change_id':None,'node_id':state.identity.node_id,'version':current.version.to_dict(),'stale_fields':sorted(stale_fields)}
        patch['message_id']=body.get('message_id'); patch['timestamp']=body.get('timestamp')
        change=state.engine.upsert(MANUSCRIPT_TYPE,mid,patch)
        return {'status':'committed','manuscript_id':mid,'project_id':body['project_id'],'chapter_id':body['chapter_id'],'change_id':change.change_id,'node_id':state.identity.node_id,'changed_fields':sorted(k for k in patch if k in MANUSCRIPT_AUTHORED_FIELDS),'stale_fields':sorted(stale_fields),'version':change.version.to_dict()}
    @app.get('/api/manuscript/{project_id}/{chapter_id}')
    def manuscript_get(project_id:str,chapter_id:str,authorization: str|None=Header(default=None)):
        auth(authorization); e=state.store.get(MANUSCRIPT_TYPE,f'{project_id}:{chapter_id}')
        if e is None or e.deleted: raise HTTPException(404,'manuscript not found')
        return e.to_dict()
    @app.get('/api/sync/conflicts')
    def sync_conflicts(authorization: str|None=Header(default=None)):
        """Recorded conflicts were durable but unreadable over HTTP.

        A conflict nobody can see is indistinguishable from a conflict that was
        silently discarded, which defeats the point of recording it.
        """
        auth(authorization); rows=state.store.conflicts()
        items=[{'conflict_id':r['conflict_id'],'entity_type':r['entity_type'],'entity_id':r['entity_id'],'reason':r['reason'],'created_at':r['created_at'],'local':json.loads(r['local_payload']),'remote':json.loads(r['remote_payload'])} for r in rows]
        return {'count':len(items),'node_id':state.identity.node_id,'conflicts':items}

    @app.post('/api/memory/candidates')
    def capture(body:dict[str,Any], authorization: str|None=Header(default=None)):
        auth(authorization); text=body.get('text')
        if not isinstance(text,str) or not text.strip(): raise HTTPException(400,'text must be a non-empty string')
        return {'candidate_id':state.memory.capture(text,body.get('metadata'))}
    @app.get('/api/memory/candidates')
    def candidates(authorization: str|None=Header(default=None)):
        auth(authorization); return state.memory.list()
    @app.post('/api/memory/candidates/{candidate_id}/promote')
    def promote(candidate_id:str,authorization: str|None=Header(default=None)):
        auth(authorization); item=state.memory.promote(candidate_id)
        if item is None: raise HTTPException(404,'candidate not found')
        return item
    @app.post('/api/sync')
    def sync(body:dict[str,Any]|None=None, authorization: str|None=Header(default=None)):
        auth(authorization); body=body or {}; env=SyncEnvelope.from_dict(body.get('envelope') or {})
        results=state.engine.receive(env)
        return {'node_id':state.identity.node_id,'protocol':state.engine.PROTOCOL,'results':[{'applied':r.applied,'duplicate':r.duplicate,'ignored':r.ignored,'conflict':r.conflict.to_dict() if r.conflict else None} for r in results], 'envelope':state.engine.envelope().to_dict()}
    @app.post('/api/sync/pull')
    def sync_pull(body:dict[str,Any]|None=None, authorization: str|None=Header(default=None)):
        auth(authorization); body=body or {}; known=body.get('known_cursor')
        from .protocol import VectorClock
        clock=VectorClock.from_dict((known or {}).get('version') if known else {})
        return state.engine.envelope(clock).to_dict()
    @app.post('/api/sync/trigger')
    def sync_trigger(body:dict[str,Any], authorization: str|None=Header(default=None)):
        auth(authorization); peer=body.get('peer_url') or cfg.get('PP_PEER_URL')
        if not peer: raise HTTPException(400,'peer_url is required')
        known=body.get('known_cursor') or {}
        try:
            headers=peer_auth(authorization)
            # Advertise what this node has actually seen so the peer sends the
            # tail rather than its whole change log on every trigger.
            known=known or {'version':state.engine.clock.to_dict()}
            r=httpx.post(peer.rstrip('/')+'/api/sync/pull',json={'known_cursor':known},headers=headers,timeout=15)
            r.raise_for_status(); remote=r.json()
            applied=state.engine.receive(SyncEnvelope.from_dict(remote))
            outbound=state.engine.envelope(VectorClock.from_dict(remote.get('cursor',{}).get('version',{})))
            rr=httpx.post(peer.rstrip('/')+'/api/sync',json={'envelope':outbound.to_dict()},headers=headers,timeout=15)
            rr.raise_for_status()
            return {'status':'synced','peer_url':peer,'received':len(applied),'peer_response':rr.json()}
        except httpx.HTTPError as exc: raise HTTPException(502,f'peer sync failed: {exc}')
    return app
if __name__=='__main__':
    import uvicorn
    cfg=Config(); uvicorn.run(create_app(cfg),host=cfg.get('PP_HOST','127.0.0.1'),port=int(cfg.get('PP_PORT','8000')))
