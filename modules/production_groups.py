"""Production membership in the existing notes database; no parallel delivery store."""
import hashlib
import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool


def fail(status, message):
    raise HTTPException(status, message)


class ProductionGroups:
    def __init__(self, connection):
        self.connection = connection
        with connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS production_groups(id TEXT PRIMARY KEY,name TEXT NOT NULL,owner_id TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS production_members(group_id TEXT NOT NULL REFERENCES production_groups(id),user_id TEXT NOT NULL,department TEXT NOT NULL DEFAULT '',role TEXT NOT NULL,PRIMARY KEY(group_id,user_id));
            ''')

    def get(self, gid, actor, host=False, db=None):
        if db is None:
            with self.connection() as connection:
                return self.get(gid, actor, host, connection)
        row = db.execute('SELECT * FROM production_groups WHERE id=?', (gid,)).fetchone()
        if not row:
            fail(404, 'Production group not found')
        members = [dict(r) for r in db.execute('SELECT user_id,department,role FROM production_members WHERE group_id=? ORDER BY user_id', (gid,))]
        if not host and actor not in {m['user_id'] for m in members}:
            fail(404, 'Production group not found')
        return dict(row, members=members)

    def list(self, actor, host=False):
        with self.connection() as db:
            ids = db.execute('SELECT id FROM production_groups ORDER BY name,id').fetchall()
            return [self.get(r[0], actor, host, db) for r in ids if host or db.execute('SELECT 1 FROM production_members WHERE group_id=? AND user_id=?', (r[0], actor)).fetchone()]

    def save(self, actor, host, body, known, gid=None):
        if not isinstance(body, dict) or set(body)-{'name','members','revision'}:
            fail(400, 'Choose a group name, members and revision')
        name = body.get('name')
        if not isinstance(name, str) or not name.strip() or len(name)>80:
            fail(400, 'Group names must contain one to eighty characters')
        members = body.get('members', [])
        if not isinstance(members,list) or len(members)>200:
            fail(400, 'A production may have up to two hundred members')
        clean = {}
        for member in members:
            if not isinstance(member,dict) or set(member)-{'user_id','department','role'}:
                fail(400,'Invalid production member')
            uid, department, role = member.get('user_id'), member.get('department',''), member.get('role','member')
            if not isinstance(uid,str) or uid not in known or uid in clean or not isinstance(role,str) or role not in {'producer','member'} or not isinstance(department,str) or len(department)>60:
                fail(400,'Choose known, distinct people, a department and producer/member role')
            clean[uid] = (department.strip(),role)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if gid:
                previous=self.get(gid,actor,host,db)
                if not host and not any(m['user_id']==actor and m['role']=='producer' for m in previous['members']):
                    fail(403,'Only the host or a production producer may edit membership')
                if type(body.get('revision')) is not int or body['revision']!=previous['revision']:
                    fail(409,'Production membership changed; reload before saving')
                owner=previous['owner_id']
                db.execute('UPDATE production_groups SET name=?,revision=revision+1 WHERE id=?',(name.strip(),gid))
            else:
                if not host:
                    fail(403,'The host creates production groups')
                gid='g_'+secrets.token_hex(10); owner=actor
                db.execute('INSERT INTO production_groups(id,name,owner_id) VALUES(?,?,?)',(gid,name.strip(),owner))
            clean[owner] = (clean.get(owner,('', 'producer'))[0], 'producer')
            db.execute('DELETE FROM production_members WHERE group_id=?',(gid,))
            db.executemany('INSERT INTO production_members VALUES(?,?,?,?)',[(gid,uid,*values) for uid,values in clean.items()])
            return self.get(gid,actor,True,db)

    def guard(self, db, snapshot, actor, host):
        group=self.get(snapshot['id'],actor,host,db)
        if group['revision']!=snapshot['revision']:
            fail(409,'Production membership changed; preview recipients again')


def schedule(value):
    if value is None:
        return None
    if not isinstance(value,dict) or set(value)-{'starts_at','ends_at','location'}:
        fail(400,'A schedule needs start/end times and an optional location')
    result={}
    parsed=[]
    for key in ['starts_at','ends_at']:
        text=value.get(key)
        if not isinstance(text,str) or len(text)>50:
            fail(400,'Use complete start and end times with a time zone')
        try:
            dt=datetime.fromisoformat(text.replace('Z','+00:00'))
            if dt.utcoffset() is None:
                raise ValueError()
        except ValueError:
            fail(400,'Schedule times must include a time zone')
        parsed.append(dt); result[key]=dt.isoformat()
    if parsed[1]<=parsed[0]:
        fail(400,'Schedule end must follow its start')
    location=value.get('location','')
    if not isinstance(location,str) or len(location)>200:
        fail(400,'Keep the schedule location under two hundred characters')
    result['location']=location.strip()
    return result


def resolve(groups, profile, body, everyone, spots):
    actor=profile['user_id']; host=profile.get('role')=='owner'
    known={p['user_id'] for p in everyone}
    gid=body.get('group_id')
    if gid is not None and (not isinstance(gid,str) or len(gid)>80):
        fail(400,'Choose a production group ID')
    group=groups.get(gid,actor,host) if gid else None
    members=group['members'] if group else []
    permitted={m['user_id'] for m in members} if group else known
    placed={}
    for kind in ['to','cc','bcc']:
        selected=body.get(kind) or []
        if not isinstance(selected,list) or len(selected)>200 or not all(isinstance(x,str) for x in selected):
            fail(400,'Recipients must be lists of people or departments')
        for selector in selected:
            if selector=='@production' or selector.startswith('@department:'):
                if not group:
                    fail(400,'Choose a production group before addressing the production or a department')
                department=selector.removeprefix('@department:')
                targets=[m['user_id'] for m in members if selector=='@production' or m['department']==department]
                if selector!='@production' and not targets:
                    fail(400,'No recipients in that department')
            else:
                targets=[selector]
            for uid in targets:
                if uid not in known or uid not in permitted:
                    fail(400,'A selected person is not in this production')
                placed.setdefault(uid,kind)
    if not placed or len(placed)>200:
        fail(400,'Choose between one and two hundred recipients')
    common=spots.clean(body.get('spots'))
    overrides=body.get('placements',{})
    if not isinstance(overrides,dict) or set(overrides)-set(placed):
        fail(400,'Per-person placements must name selected recipients only')
    positions={uid:spots.clean(overrides.get(uid,common)) for uid in placed}
    kind=body.get('kind','note')
    if not isinstance(kind,str) or kind not in {'note','schedule'}:
        fail(400,'Choose a note or schedule update')
    timing=schedule(body.get('schedule'))
    if (kind=='schedule') != (timing is not None):
        fail(400,'Schedule updates require start and end times')
    metadata={'group_id':gid,'group_name':group['name'] if group else '', 'kind':kind,'schedule':timing}
    snapshot={'id':gid,'revision':group['revision']} if group else None
    fingerprint=hashlib.sha256(json.dumps([actor,snapshot,placed,positions,metadata],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(recipients=placed,positions=positions,metadata=metadata,snapshot=snapshot,preview=fingerprint)


def create_group_router(groups, me, read_json, list_people):
    router=APIRouter()
    @router.get('/api/production/groups')
    async def listing(profile=Depends(me)):
        return {'groups':await run_in_threadpool(groups.list,profile['user_id'],profile.get('role')=='owner'),'can_create':profile.get('role')=='owner'}
    @router.post('/api/production/groups',status_code=201)
    async def create(request:Request,profile=Depends(me)):
        known={p['user_id'] for p in await list_people()}
        return await run_in_threadpool(groups.save,profile['user_id'],profile.get('role')=='owner',await read_json(request),known)
    @router.patch('/api/production/groups/{gid}')
    async def update(gid:str,request:Request,profile=Depends(me)):
        known={p['user_id'] for p in await list_people()}
        return await run_in_threadpool(groups.save,profile['user_id'],profile.get('role')=='owner',await read_json(request),known,gid)
    return router
