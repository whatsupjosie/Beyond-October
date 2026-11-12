"""Actual group note resolution, membership fences and independent delivery state."""
from tests.test_production_notes import env


def create(env):
    c,auth,people,_=env
    members=[{'user_id':people['pete']['user_id'],'department':'Sound'},
             {'user_id':people['repete']['user_id'],'department':'Camera'}]
    result=c.post('/api/production/groups',headers=auth('josie','owner'),json={'name':'Episode','members':members})
    assert result.status_code==201,result.text
    return result.json()


def test_group_departments_individual_spots_schedule_and_bcc_privacy(env):
    c,auth,p,_=env; group=create(env); owner=auth('josie','owner')
    payload={'subject':'Rehearsal moved','group_id':group['id'],'to':['@department:Sound'],
             'bcc':[p['repete']['user_id']], 'placements':{p['pete']['user_id']:['audio_console']},
             'kind':'schedule','schedule':{'starts_at':'2026-11-06T14:00:00-08:00','ends_at':'2026-11-06T15:00:00-08:00','location':'Studio'}}
    preview=c.post('/api/notes/preview',headers=owner,json=payload)
    assert preview.status_code==200,preview.text
    assert len(preview.json()['recipients'])==2
    payload['preview']=preview.json()['preview']
    sent=c.post('/api/notes',headers=owner,json=payload)
    assert sent.status_code==201,sent.text
    nid=sent.json()['id']
    sound=c.get('/api/notes/'+nid,headers=auth('pete','guest')).json()
    camera=c.get('/api/notes/'+nid,headers=auth('repete','guest')).json()
    assert sound['spots']==['mirror','audio_console'] and camera['spots']==['mirror']
    assert sound['bcc']==[] and camera['you_were_bcc']
    assert sound['production']['kind']=='schedule' and sound['production']['schedule']['location']=='Studio'
    assert c.get('/api/notes/'+nid,headers=auth('oldtimer','guest')).status_code==404
    c.post('/api/notes/'+nid+'/read',headers=auth('pete','guest'))
    assert c.get('/api/notes/'+nid,headers=auth('repete','guest')).json()['unread']


def test_membership_preview_revision_and_authorization(env):
    c,auth,p,_=env; group=create(env); owner=auth('josie','owner'); guest=auth('pete','guest')
    assert c.get('/api/production/groups',headers=auth('oldtimer','guest')).json()['groups']==[]
    assert c.post('/api/production/groups',headers=guest,json={'name':'Other'}).status_code==403
    assert c.patch('/api/production/groups/'+group['id'],headers=guest,json={'name':'Taken','members':[],'revision':0}).status_code==403
    payload={'subject':'Group note','group_id':group['id'],'to':['@production']}
    assert c.post('/api/notes',headers=owner,json=payload).status_code==409
    payload['preview']=c.post('/api/notes/preview',headers=owner,json=payload).json()['preview']
    changed=c.patch('/api/production/groups/'+group['id'],headers=owner,json={'name':'New crew','members':[{'user_id':p['pete']['user_id']}],'revision':0})
    assert changed.status_code==200,changed.text
    assert c.post('/api/notes',headers=owner,json=payload).status_code==409
    assert c.patch('/api/production/groups/'+group['id'],headers=owner,json={'name':'Stale','members':[],'revision':0}).status_code==409
    assert c.get('/api/production/groups',headers=auth('repete','guest')).json()['groups']==[]
    assert c.post('/api/notes/preview',headers=owner,json={'to':['@production']}).status_code==400
    assert c.post('/api/notes/preview',headers=owner,json={**payload,'to':[p['oldtimer']['user_id']]}).status_code==400
    assert c.post('/api/notes/preview',headers=owner,json={**payload,'kind':'schedule','schedule':{'starts_at':'2026-11-06T14:00','ends_at':'2026-11-06T15:00'}}).status_code==400
