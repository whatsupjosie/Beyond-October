"""2i manuscript intelligence: durable chapters, observations, editorial signals and PubPartner generation."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from modules.route_security import current_identity
from modules.local_model_config import default_provider

MAX_CHAPTERS=500
MAX_LINES=30000

def make_router(data_dir: Path):
    router=APIRouter(prefix="/api/pubpartner/manuscript", tags=["manuscript-intelligence"])
    path=Path(data_dir)/"writers_room"/"intelligence.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    def connect():
        db=sqlite3.connect(path, timeout=20)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db
    with connect() as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS chapters(owner TEXT, project TEXT, idx INTEGER, title TEXT, content TEXT, digest TEXT, updated REAL, PRIMARY KEY(owner,project,idx));
        CREATE TABLE IF NOT EXISTS signals(owner TEXT, project TEXT, id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ai_text TEXT, human_text TEXT, chapter_idx INTEGER, created REAL);
        CREATE TABLE IF NOT EXISTS flags(owner TEXT, project TEXT, id TEXT, message TEXT, severity TEXT, resolved INTEGER DEFAULT 0, PRIMARY KEY(owner,project,id));""")
    def owner(identity):
        user = str(identity['user_id'])
        if user == 'anon': raise HTTPException(401, 'A writer identity is required')
        return user
    def ident(v):
        if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',v): raise HTTPException(422,'invalid project id')
        return v
    async def body_json(request):
        try: data=await request.json()
        except Exception: raise HTTPException(400,'invalid JSON')
        if not isinstance(data,dict): raise HTTPException(422,'expected JSON object')
        return data
    def load(db,o,p):
        return db.execute('SELECT * FROM chapters WHERE owner=? AND project=? ORDER BY idx',(o,p)).fetchall()
    def entities(chapters):
        # Explicit mentions only: a capitalized word alone is not sufficient evidence of a character.
        people=set(); places=set()
        for row in chapters:
            s=row['content']
            for m in re.finditer(r'\b(?:named|called)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',s): people.add(m.group(1))
            for m in re.finditer(r'\b(?:city of|town of|village of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',s): places.add(m.group(1))
        def item(s): return {'name':s,'aliases':[],'provenance':{'authority':'inferred','confidence':0.45}}
        return {'character':[item(x) for x in sorted(people)],'location':[item(x) for x in sorted(places)]}
    @router.post('/commit')
    async def commit(request:Request,identity=Depends(current_identity)):
        b=await body_json(request); p=ident(b.get('project_id')); raw=b.get('chapters')
        if not isinstance(raw,list) or len(raw)>MAX_CHAPTERS: raise HTTPException(422,'invalid chapter list')
        incoming=[]; total=0
        for i,ch in enumerate(raw):
            if not isinstance(ch,dict) or not isinstance(ch.get('lines'),list): raise HTTPException(422,'invalid chapter')
            lines=ch['lines']; total+=len(lines)
            if total>MAX_LINES or any(not isinstance(s,str) or len(s)>10000 for s in lines): raise HTTPException(413,'manuscript too large')
            title=str(ch.get('title') or f'Chapter {i+1}')[:250]
            content='\n'.join(lines)
            digest=hashlib.sha256(content.encode('utf-8')).hexdigest()
            incoming.append((i,title,content,digest))
        indexed=[]; o=owner(identity)
        with connect() as db:
            existing={r['idx']:r for r in load(db,o,p)}
            for i,title,content,digest in incoming:
                if i not in existing or existing[i]['digest']!=digest or existing[i]['title']!=title or b.get('force_reindex'):
                    db.execute('INSERT OR REPLACE INTO chapters VALUES(?,?,?,?,?,?,?)',(o,p,i,title,content,digest,time.time()))
                    indexed.append(i)
            for i in existing.keys()-{x[0] for x in incoming}: db.execute('DELETE FROM chapters WHERE owner=? AND project=? AND idx=?',(o,p,i))
            db.commit()
        return {'ok':True,'chapters_indexed':indexed,'errors':[]}
    @router.get('/{project}/health')
    async def health(project:str,identity=Depends(current_identity)):
        p=ident(project); o=owner(identity)
        with connect() as db:
            chapters=load(db,o,p); es=entities(chapters)
        return {'ok':True,'stats':{'entities':sum(len(v) for v in es.values()),'chapters':len(chapters)}}
    @router.get('/{project}/intelligence')
    async def intelligence(project:str,identity=Depends(current_identity)):
        p=ident(project); o=owner(identity)
        with connect() as db:
            chapters=load(db,o,p); flags=[{'flag_id':r['id'],'message':r['message'],'severity':r['severity']} for r in db.execute('SELECT * FROM flags WHERE owner=? AND project=? AND resolved=0',(o,p))]
        return {'ok':True,'entities':entities(chapters),'flags':flags,'chapters':[{'index':r['idx'],'title':r['title'],'hash':r['digest']} for r in chapters]}
    @router.post('/{project}/flags/{flag}/resolve')
    async def resolve(project:str,flag:str,identity=Depends(current_identity)):
        p=ident(project); o=owner(identity)
        with connect() as db:
            cur=db.execute('UPDATE flags SET resolved=1 WHERE owner=? AND project=? AND id=?',(o,p,flag)); db.commit()
        if not cur.rowcount: raise HTTPException(404,'flag not found')
        return {'ok':True}
    @router.post('/voice-signal')
    async def voice_signal(request:Request,identity=Depends(current_identity)):
        b=await body_json(request); p=ident(b.get('project_id')); kind=b.get('type')
        if kind not in ('accepted','rejected','rewritten'): raise HTTPException(422,'invalid signal type')
        ai=b.get('ai_text'); human=b.get('human_text')
        if not isinstance(ai,str) or not ai.strip() or len(ai)>20000 or (human is not None and (not isinstance(human,str) or len(human)>20000)): raise HTTPException(422,'invalid signal text')
        with connect() as db:
            db.execute('INSERT INTO signals(owner,project,kind,ai_text,human_text,chapter_idx,created) VALUES(?,?,?,?,?,?,?)',(owner(identity),p,kind,ai,human,b.get('chapter_index') if isinstance(b.get('chapter_index'),int) else None,time.time())); db.commit()
        return {'ok':True}
    @router.post('/generate')
    async def generate(request:Request,identity=Depends(current_identity)):
        b=await body_json(request); p=ident(b.get('project_id')); context=b.get('context_lines',[])
        if not isinstance(context,list) or len(context)>50 or any(not isinstance(x,str) or len(x)>10000 for x in context): raise HTTPException(422,'invalid context')
        spine=getattr(request.app.state,'pubpartner_spine',None)
        if spine is None: raise HTTPException(503,'PubPartner inference not running')
        instruction=b.get('instruction', 'Continue the manuscript in the established voice.')
        if not isinstance(instruction,str) or not instruction.strip() or len(instruction)>2000:
            raise HTTPException(422,'instruction must be 1–2000 characters')
        message='Continue this manuscript. Return only new prose, no preamble.\nInstruction: '+instruction+'\nRecent manuscript:\n'+'\n'.join(context)
        result=await spine.run_turn(user_id=owner(identity),session_id='manuscript-'+p,project_id=p,room_id='2i',message=message,friend=None,user_primer=None,provider=default_provider(),task={'mode':'manuscript_continuation','goal':'write_only_requested_new_prose'},output={'fmt':'plain','len':'as_requested'},safety=None,content_kind='manuscript',language='en-US',history=None,max_memories=6,prompt_mode='full',allow_fallback=False)
        provider=result.get('provider_result') or {}
        if not provider.get('ok'): raise HTTPException(503, provider.get('error') or 'PubPartner model unavailable')
        answer=str(result.get('friend_response') or '').strip()
        if not answer: raise HTTPException(503,'PubPartner returned empty text')
        return {'ok':True,'lines':answer.splitlines()}
    return router
