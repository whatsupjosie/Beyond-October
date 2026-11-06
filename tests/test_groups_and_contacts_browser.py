"""Real UI: production membership, departmental schedule placement, contact consent and blocking."""
import httpx

from tests.test_production_notes_browser import reach
from tests.test_production25d_browser import production_browser


def login(context, base, user, password, destination):
    page=context.new_page();page.goto(base+'/login?next='+destination)
    page.fill('#loginUser',user);page.fill('#loginPass',password);page.click('#loginBtn')
    page.wait_for_url('**'+destination)
    return page


def test_groups_ui_department_schedule_and_personal_mirror(reach,production_browser):
    base,user,password=reach
    context=production_browser.new_context(viewport={'width':1440,'height':1000})
    errors=[]
    try:
        page=login(context,base,user,password,'/static/production_groups.html')
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.wait_for_selector('.member')
        with httpx.Client(base_url=base,trust_env=False,timeout=20) as api:
            token=api.post('/api/auth/login',json={'username':user,'password':password}).json()['access_token']
            owner={'Authorization':'Bearer '+token}
            people={p['username']:p for p in api.get('/api/production/people',headers=owner).json()['people']}
            page.fill('#name','Browser production')
            for username,department in [('pete-notes','Sound'),('repete-notes','Camera')]:
                row=page.locator('.member[data-user="'+people[username]['user_id']+'"]')
                row.locator('.included').check();row.locator('.department').fill(department)
            page.click('#save');page.wait_for_function('document.getElementById("status").textContent.startsWith("Production saved")')
            gid=page.locator('#groups').input_value()
            page.goto(base+'/walk?view=control_room/main')
            page.wait_for_function('document.documentElement.dataset.ready === "1"')
            page.wait_for_function('window.PubCastNotes?.state.enabled')
            page.evaluate('PubCastNotes.compose({})');page.wait_for_selector('#pnGroup')
            page.select_option('#pnGroup',gid)
            page.locator('.pn-pick[data-kind="to"][data-id="@department:Sound"]').click()
            page.locator('.pn-subject').fill('Schedule for sound only')
            page.select_option('#pnKind','schedule')
            page.fill('#pnStart','2026-11-07T14:00');page.fill('#pnEnd','2026-11-07T15:00');page.fill('#pnLocation','Audio desk')
            page.get_by_role('button',name='Preview recipients',exact=True).click()
            page.wait_for_selector('.pn-review select')
            page.get_by_label('Locations for Pete',exact=True).select_option('audio_console')
            page.get_by_role('button',name='Preview recipients',exact=True).click()
            page.wait_for_function('document.querySelector(".pn-msg").textContent.includes("Recipients reviewed")')
            page.get_by_role('button',name='Stick it',exact=True).click()
            page.wait_for_selector('.pn-menu')
            pete_token=api.post('/api/auth/login',json={'username':'pete-notes','password':password}).json()['access_token']
            pete={'Authorization':'Bearer '+pete_token}
            inbox=api.get('/api/notes',headers=pete).json()['notes'];note=next(n for n in inbox if n['subject']=='Schedule for sound only')
            assert note['spots']==['mirror','audio_console'] and note['production']['schedule']['location']=='Audio desk'
            other_token=api.post('/api/auth/login',json={'username':'repete-notes','password':password}).json()['access_token']
            assert api.get('/api/notes/'+note['id'],headers={'Authorization':'Bearer '+other_token}).status_code==404
            assert not errors
    finally:
        context.close()


def test_contacts_accept_chat_block_and_unblock(reach,production_browser):
    base,_,password=reach
    one=production_browser.new_context();two=production_browser.new_context()
    try:
        a=login(one,base,'pete-notes',password,'/static/human_contacts.html')
        b=login(two,base,'repete-notes',password,'/static/human_contacts.html')
        a.fill('#person','repete-notes');a.fill('#hello','Make an episode together');a.locator('#request button').click()
        a.wait_for_function('document.getElementById("status").textContent.includes("request sent")')
        b.click('#refresh');b.get_by_role('button',name='Accept contact',exact=True).click()
        b.get_by_role('button',name='Open conversation',exact=True).click()
        a.click('#refresh');a.get_by_role('button',name='Open conversation',exact=True).click()
        a.wait_for_function('document.getElementById("status").textContent.includes("channel open")')
        b.wait_for_function('document.getElementById("status").textContent.includes("channel open")')
        a.fill('#text','Private rehearsal message');a.locator('#send button').click()
        b.wait_for_function('document.getElementById("log").textContent.includes("Private rehearsal message")')
        a.wait_for_function('document.getElementById("text").value===""')
        b.get_by_role('button',name='Block contact',exact=True).click()
        b.wait_for_selector('#blocked article')
        a.wait_for_function('document.getElementById("status").textContent.includes("channel closed")')
        a.locator('#request button').click();a.wait_for_function('document.getElementById("status").textContent.includes("blocked")')
        b.get_by_role('button',name='Unblock',exact=True).click();b.wait_for_function('document.getElementById("blocked").children.length===0')
    finally:
        one.close();two.close()
