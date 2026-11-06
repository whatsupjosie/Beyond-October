"""Own-copy guests: group schedule/attachments and a genuinely lost chat receipt."""
from contextlib import ExitStack, contextmanager
import json
from playwright.sync_api import expect

from tests.test_guest_identity import CONSENTS
from tests.test_human_profile_onboarding_browser import fresh_host
from tests.test_independent_guest_hosts import setup
from tests.test_independent_guest_browser import seed
from tests.test_production25d_browser import production_browser


def test_independent_guests_group_delivery_and_lost_receipt_retry(tmp_path,production_browser):
    with ExitStack() as stack:
        start=contextmanager(fresh_host.__wrapped__)
        base,host=stack.enter_context(start(tmp_path/'production'))
        owner,headers=setup(host,'director')
        guests=[]
        for index in range(2):
            _,home=stack.enter_context(start(tmp_path/f'home-{index}'))
            human,own_headers=setup(home,f'guest-{index}')
            code=host.post('/api/guests/invites',headers=headers,json={}).json()['invite_code']
            challenge=host.post('/api/guests/challenge',json={'invite_code':code}).json()
            proof=home.post('/api/guests/sign',headers=own_headers,json={'challenge':challenge['challenge'],'consents':CONSENTS})
            entry=host.post('/api/guests/request',json=proof.json()).json()['entry_id']
            pending=next(p for p in host.get('/api/guests/pending',headers=headers).json()['pending'] if p['entry_id']==entry)
            assert host.post('/api/guests/entries/'+entry+'/approve',headers=headers,json={'fingerprint':pending['fingerprint']}).status_code==200
            lease=host.post('/api/guests/status',json={'poll_token':challenge['poll_token']}).json()
            context=production_browser.new_context();stack.callback(context.close)
            seed(context,base,lease['access_token'])
            guests.append((human,context,{'Authorization':'Bearer '+lease['access_token']}))
        one,two=guests
        group=host.post('/api/production/groups',headers=headers,json={'name':'Independent crew','members':[{'user_id':one[0]['user_id'],'department':'Sound'},{'user_id':two[0]['user_id'],'department':'Camera'}]})
        assert group.status_code==201,group.text
        note={'subject':'Revised call','group_id':group.json()['id'],'to':['@department:Sound'],'bcc':[two[0]['user_id']],
              'placements':{one[0]['user_id']:['audio_console']},'kind':'schedule',
              'schedule':{'starts_at':'2026-11-07T14:00:00-08:00','ends_at':'2026-11-07T15:00:00-08:00'}}
        note['preview']=host.post('/api/notes/preview',headers=headers,json=note).json()['preview']
        sent=host.post('/api/notes',headers=headers,data={'note':json.dumps(note)},files={'files':('call.txt',b'Keep these original bytes','text/plain')})
        assert sent.status_code==201,sent.text
        nid=sent.json()['id']
        sound=host.get('/api/notes/'+nid,headers=one[2]).json()
        assert sound['spots']==['mirror','audio_console'] and sound['bcc']==[]
        assert host.get(sound['files'][0]['url'],headers=two[2]).content==b'Keep these original bytes'
        assert host.post('/api/notes/'+nid+'/read',headers=one[2]).status_code==200
        assert host.get('/api/notes/'+nid,headers=two[2]).json()['unread']

        # Drop one actual server receipt while keeping the real socket open.
        # The recipient receives the message; retry must not append it twice.
        one[1].add_init_script('''const NativeSocket=WebSocket;
            window.WebSocket=class extends NativeSocket {constructor(...args){super(...args);
              this.addEventListener('message',event=>{try{const p=JSON.parse(event.data);
                if(window.dropReceipt&&p.type==='chat_receipt'){window.dropReceipt=false;window.droppedReceipt=true;event.stopImmediatePropagation();}
              }catch(_){}});}};''')
        a=one[1].new_page();b=two[1].new_page();errors=[]
        for page in (a,b):page.on('pageerror',lambda error:errors.append(str(error)))
        a.goto(base+'/static/human_contacts.html');b.goto(base+'/static/human_contacts.html')
        a.fill('#person',two[0]['user_id']);a.fill('#hello','Plan the shoot');a.locator('#request button').click()
        a.wait_for_function('document.getElementById("status").textContent.includes("request sent")')
        b.click('#refresh');b.get_by_role('button',name='Accept contact',exact=True).click()
        b.get_by_role('button',name='Open conversation',exact=True).click()
        a.click('#refresh');a.get_by_role('button',name='Open conversation',exact=True).click()
        for page in (a,b):page.wait_for_function('document.getElementById("status").textContent.includes("channel open")')
        a.evaluate('window.dropReceipt=true');a.fill('#text','Exactly once after a lost receipt');a.locator('#send button').click()
        a.wait_for_function('window.droppedReceipt===true')
        b.wait_for_function('document.getElementById("log").textContent.includes("Exactly once after a lost receipt")')
        a.wait_for_function('!document.querySelector("#send button").disabled',timeout=20000)
        assert 'not confirmed' in a.locator('#status').inner_text()
        a.locator('#send button').click();a.wait_for_function('document.getElementById("text").value===""')
        # Reopening reads persisted history, including any accidental duplicate.
        b.evaluate('document.getElementById("status").textContent=""')
        b.get_by_role('button',name='Open conversation',exact=True).click()
        b.wait_for_function('document.getElementById("status").textContent.includes("channel open")')
        expect(b.locator('#log p').filter(has_text='Exactly once after a lost receipt')).to_have_count(1)
        b.get_by_role('button',name='Block contact',exact=True).click()
        a.wait_for_function('document.getElementById("status").textContent.includes("channel closed")')
        assert host.post('/api/chat/dm/request',headers=one[2],json={'to_user':two[0]['user_id']}).status_code==409
        assert errors==[]


from tests.test_production_notes_browser import reach
from tests.test_groups_and_contacts_browser import login


def test_recipient_changes_discard_obsolete_per_person_placements(reach,production_browser):
    import httpx
    base,user,password=reach
    context=production_browser.new_context(viewport={'width':1440,'height':1000})
    try:
        page=login(context,base,user,password,'/walk?view=control_room/main')
        with httpx.Client(base_url=base,trust_env=False) as api:
            token=api.post('/api/auth/login',json={'username':user,'password':password}).json()['access_token']
            headers={'Authorization':'Bearer '+token}
            people={p['username']:p for p in api.get('/api/production/people',headers=headers).json()['people']}
            group=api.post('/api/production/groups',headers=headers,json={'name':'Placement change','members':[{'user_id':people['pete-notes']['user_id'],'department':'Sound'},{'user_id':people['repete-notes']['user_id'],'department':'Camera'}]}).json()
        page.wait_for_function('window.PubCastNotes?.state.enabled')
        page.evaluate('PubCastNotes.compose({})');page.wait_for_selector('#pnGroup')
        page.select_option('#pnGroup',group['id'])
        sound=page.locator('.pn-pick[data-kind="to"][data-id="@department:Sound"]')
        camera=page.locator('.pn-pick[data-kind="to"][data-id="@department:Camera"]')
        sound.click();page.get_by_role('button',name='Preview recipients',exact=True).click()
        page.wait_for_selector('.pn-review select')
        page.get_by_label('Locations for Pete',exact=True).select_option('audio_console')
        sound.click();camera.click()
        with page.expect_response(lambda response:response.url.endswith('/api/notes/preview')) as preview:
            page.get_by_role('button',name='Preview recipients',exact=True).click()
        assert preview.value.status==200,preview.value.text()
        page.wait_for_function('document.querySelector(".pn-msg").textContent.includes("Recipients reviewed")',timeout=10000)
        expect(page.get_by_label('Locations for RePete',exact=True)).to_be_visible()
        expect(page.get_by_label('Locations for Pete',exact=True)).to_have_count(0)
    finally:
        context.close()
