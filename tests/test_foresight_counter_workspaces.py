"""Browser regressions for mixed-size workspaces and crowded admission.

Real counter, geometry, physics and browser mouse events; graphics output is
stubbed so these tests make no GPU rendering claim. Local request interception
keeps this independent of Reach and of a listening network socket.
Run: python -m pytest -q tests/test_foresight_counter_workspaces.py
Requires Playwright and its Chromium browser.
"""

from pathlib import Path
from urllib.parse import urlparse, unquote
import mimetypes
import os

import pytest

ROOT = Path(__file__).resolve().parents[1]
playwright = pytest.importorskip("playwright.sync_api")

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;overflow:hidden;background:#21160f}
canvas{position:fixed;inset:0;width:100vw;height:100vh;touch-action:none}
</style></head><body><canvas id="gl"></canvas>
<script src="/static/foresight_shapes.js"></script>
<script src="/static/foresight_chain.js"></script>
<script src="/static/foresight_gl.js"></script>
<script src="/static/foresight_counter.js"></script>
<script>
window.defs = {
 keyboard:{title:'Keyboard',family:'octagon',w:800,h:210,minW:480,minH:150},
 timeline:{title:'Audio timeline',family:'hexagon',w:430,h:340,minW:300,minH:240},
 reference:{title:'Reference article',family:'pentagon',w:300,h:190,minW:240,minH:150},
 archive:{title:'Sound library',family:'heptagon',w:290,h:180,minW:230,minH:140},
 bpm:{title:'BPM',family:'hexagon',w:130,h:90,minW:100,minH:70},
 large:{title:'Large program',family:'octagon',w:680,h:420,minW:440,minH:280}
};
window.provider = {
 describe:type => defs[type],
 catalog:()=>[{title:'New chat',run:()=>{window.ran=true}}, {type:'reference',title:'Reference article'}],
 mount(c,host){
   const button=document.createElement('button'); button.textContent=c.def.title;
   host.body.dataset.contentType=c.type;
   button.style.cssText='margin:18px;position:relative;z-index:1';
   c.state.clicks=c.state.clicks||0;
   button.onclick=()=>{c.state.clicks++;host.changed()};
   host.body.appendChild(button);
   if(c.type==='reference'){
     const article=document.createElement('article'); article.style.cssText='height:100%;overflow:auto';
     for(let i=0;i<30;i++){const p=document.createElement('p');p.textContent='Reference paragraph '+i;article.appendChild(p)}
     host.body.appendChild(article);
   }
 }
};
// These interaction tests isolate DOM layout and physics from GPU timing.
// Rendering is validated separately; this replacement is not evidence of GPU output.
const gl={setTheme(){},draw(){},gl:{finish(){}},quality:'full'};
window.counter=ForesightCounter.create({canvas:document.getElementById('gl'),gl,provider,storageKey:'workspace-test'});
window.time=10000;
counter.debug.setClock(time);
window.advance=(n=320)=>{for(let i=0;i<n;i++){time+=17;counter.debug.setClock(time);counter.debug.step()}counter.debug.draw()};
window.openTray=(type,options={})=>{const t=counter.open(type,null,options);advance();return t&&t.id};
window.geometry=()=>counter.trays.filter(t=>!t.hidden).map(t=>({id:t.id,x:t.cx,y:t.cy,w:t.reqW,h:t.reqH,scale:t.scale}));
</script></body></html>"""


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        if os.environ.get("FORESIGHT_SINGLE_PROCESS") == "1":
            args += ["--single-process", "--no-zygote"]
        b = p.chromium.launch(args=args, executable_path=os.environ.get("FORESIGHT_TEST_CHROMIUM") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})

    def serve(route):
        path = unquote(urlparse(route.request.url).path)
        if path == "/workspace-test":
            route.fulfill(status=200, content_type="text/html", body=PAGE)
            return
        if path == "/portal-audit":
            route.fulfill(
                status=200,
                content_type="text/html",
                body="""<!doctype html><button onclick="parent.postMessage({type:'foresight:open-conversation',conversationId:'audit-conversation'},'*')">Request conversation</button>""",
            )
            return
        f = (ROOT / path.lstrip("/")).resolve()
        if f.is_relative_to(ROOT) and f.is_file():
            route.fulfill(
                status=200,
                content_type=mimetypes.guess_type(f.name)[0]
                or "application/octet-stream",
                body=f.read_bytes(),
            )
        else:
            route.fulfill(
                status=404, body="Not available in this isolated counter test"
            )

    ctx.route("**/*", serve)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://127.0.0.1/workspace-test")
    pg.wait_for_function("window.counter")
    yield pg
    assert not errors, errors
    ctx.close()


def test_five_different_working_sizes_survive_focus_and_restore(page):
    page.evaluate("""() => [
      openTray('keyboard',{id:'keyboard',x:850,y:810}),
      openTray('timeline',{id:'timeline',x:460,y:370}),
      openTray('reference',{id:'reference',x:1050,y:230}),
      openTray('archive',{id:'archive',x:1220,y:510}),
      openTray('bpm',{id:'bpm',x:1440,y:190})
    ]""")
    state = page.evaluate("geometry()")
    assert len(state) == 5, page.evaluate(
        "counter.trays.map(t=>counter.debug.info(t.id))"
    )
    areas = {t["id"]: t["w"] * t["h"] * t["scale"] ** 2 for t in state}
    assert (
        max(areas, key=areas.get) == "keyboard" and min(areas, key=areas.get) == "bpm"
    )
    assert page.evaluate("counter.debug.pressure().overlap") <= 4.6
    # Focus changes the active controls without requesting a new layout.
    before = page.evaluate("geometry()")
    for kind in ["keyboard", "timeline", "reference", "archive", "bpm"]:
        page.locator(f'[data-content-type="{kind}"] > button').click()
        assert page.evaluate("counter.selected.id") == kind
        page.evaluate("advance(30)")
    page.evaluate("counter.saveNow()")
    assert page.evaluate("geometry()") == before
    assert page.evaluate("counter.trays.map(t=>t.stack[0].state.clicks)") == [1] * 5
    snap = page.evaluate("counter.serialize()")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("window.counter")
    assert page.evaluate("s=>counter.restore(s)", snap)
    assert page.evaluate("geometry()") == before
    assert page.evaluate("counter.trays.map(t=>t.stack[0].state.clicks)") == [1] * 5


def test_opening_requests_room_before_parking(page):
    page.evaluate("openTray('large',{id:'first'})")
    before = page.evaluate("geometry()")
    page.evaluate("openTray('large',{id:'second'})")
    state = page.evaluate("counter.trays.map(t=>counter.debug.info(t.id))")
    assert len([t for t in state if not t["hidden"]]) == 2, state
    assert page.evaluate("counter.debug.pressure().overlap") <= 4.6
    assert page.evaluate("geometry()") != before


def test_locked_tray_unchanged_during_admission(page):
    page.evaluate(
        "openTray('large',{id:'first'});counter.lock(counter.find('first'),true)"
    )
    before = page.evaluate("JSON.stringify(counter.find('first').q)")
    page.evaluate("openTray('large',{id:'second'})")
    assert page.evaluate("JSON.stringify(counter.find('first').q)") == before
    assert page.evaluate("counter.debug.pressure().overlap") <= 4.6


def test_run_only_picker_action_remains_available(page):
    page.evaluate("counter.openPicker(null)")
    page.get_by_role("button", name="New chat", exact=True).click()
    assert page.evaluate("window.ran === true")


def test_save_during_admission_restores_a_readable_parked_tray(page):
    page.evaluate(
        "openTray('large',{id:'first'});counter.open('large',null,{id:'second'});advance(45)"
    )
    assert page.evaluate("!!counter.find('second').admitting")
    snap = page.evaluate("counter.serialize()")
    second = next(t for t in snap["trays"] if t["id"] == "second")
    assert second["parked"] and not second["closed"]
    assert second["w"] == 680 and second["h"] == 420 and second["scale"] >= 0.7
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("window.counter")
    page.evaluate("s=>counter.restore(s)", snap)
    assert page.evaluate(
        "counter.find('second').hidden && counter.find('second').parked"
    )


def test_lock_cancels_an_in_progress_expansion(page):
    page.evaluate(
        "openTray('keyboard',{id:'first'});counter.importInto(counter.find('first'),'large');counter.lock(counter.find('first'),true)"
    )
    assert page.evaluate("counter.find('first').locked && !counter.find('first').grow")
    before = page.evaluate("JSON.stringify(counter.find('first').q)")
    page.evaluate("advance(100)")
    assert page.evaluate("JSON.stringify(counter.find('first').q)") == before


def test_pending_open_cannot_be_locked_into_a_permanently_tiny_frame(page):
    page.evaluate(
        "openTray('large',{id:'first'});counter.open('large',null,{id:'second'});advance(45);counter.lock(counter.find('second'),true)"
    )
    assert page.evaluate(
        "!counter.find('second').locked && !!counter.find('second').admitting"
    )
    page.evaluate("advance(320)")
    assert page.evaluate(
        "!counter.find('second').admitting && !counter.find('second').hidden"
    )
    page.evaluate("counter.lock(counter.find('second'),true)")
    assert page.evaluate("counter.find('second').locked")


@pytest.mark.parametrize("action,flag", [("close", "closed"), ("park", "parked")])
def test_interrupting_admission_keeps_the_requested_lifecycle(page, action, flag):
    page.evaluate(
        "openTray('large',{id:'first'});counter.open('large',null,{id:'second'});advance(45)"
    )
    assert page.evaluate("!!counter.find('second').admitting")
    page.evaluate(f"counter.{action}(counter.find('second'));advance(80)")
    info = page.evaluate("counter.debug.info('second')")
    assert info[flag] and info["hidden"], info
    assert page.evaluate(
        "!counter.find('second').admitting && !counter.find('second').grow"
    )
    snap = page.evaluate("counter.serialize()")
    stored = next(t for t in snap["trays"] if t["id"] == "second")
    assert stored[flag] and (stored["closed"] != stored["parked"]), stored


def test_rapid_open_requests_finish_without_overlaps_or_lost_contents(page):
    page.evaluate(
        "['keyboard','timeline','reference','archive','bpm'].forEach(id=>counter.open(id,null,{id}))"
    )
    # Drive the same time/physics progression as the animation loop, checking
    # intermediate states rather than only its final settled arrangement.
    result = page.evaluate("""()=>{
      let worst=0,unreadable=[];
      for(let i=0;i<1800;i++){
        advance(1);worst=Math.max(worst,counter.debug.pressure().overlap);
        for(const t of counter.trays)if(!t.hidden&&!t.admitting&&!t.grow&&t.scale<0.69)unreadable.push(t.id);
        if(!counter.debug.anim()&&!counter.debug.queue()&&!counter.trays.some(t=>t.admitting||t.grow)&&i>100)break;
      }
      return {worst,unreadable,ids:counter.trays.map(t=>t.id),queue:counter.debug.queue()};
    }""")
    assert sorted(result["ids"]) == sorted(
        ["keyboard", "timeline", "reference", "archive", "bpm"]
    ), result
    assert result["queue"] == 0 and not result["unreadable"], result
    assert result["worst"] <= 4.6, result


def test_new_open_request_waits_for_the_current_admission(page):
    page.evaluate(
        "openTray('large',{id:'first'});counter.open('large',null,{id:'second'});advance(45)"
    )
    assert page.evaluate("!!counter.find('second').admitting && !counter.debug.anim()")
    page.evaluate("counter.open('bpm',null,{id:'third'})")
    assert page.evaluate("!counter.find('third') && counter.debug.queue()===1")
    page.evaluate("advance(800)")
    assert page.evaluate("!!counter.find('third') && counter.debug.queue()===0")


def test_slow_rendering_cannot_block_later_open_requests_indefinitely(page):
    page.evaluate("openTray('large',{id:'first'});counter.open('large',null,{id:'second'});advance(45)")
    assert page.evaluate("!!counter.find('second').admitting")
    page.evaluate("""() => {
      counter.open('bpm',null,{id:'third'});
      time+=5000;counter.debug.setClock(time);
      counter.debug.step();counter.debug.step();
    }""")
    assert page.evaluate("!!counter.find('third') && counter.debug.queue()===0")
    assert page.evaluate("counter.find('second').stack[0].type") == "large"


def test_focus_autosaves_without_an_explicit_save_call(page):
    page.evaluate("openTray('keyboard',{id:'keyboard'});openTray('bpm',{id:'bpm'})")
    page.wait_for_timeout(450)
    page.locator('[data-content-type="keyboard"] > button').click()
    page.wait_for_timeout(450)
    assert (
        page.evaluate("JSON.parse(localStorage.getItem('workspace-test')).selected")
        == "keyboard"
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("window.counter")
    assert page.evaluate("counter.restore()")
    assert page.evaluate("counter.selected.id") == "keyboard"
    assert page.evaluate("counter.find('keyboard').stack[0].state.clicks") == 1


def test_external_navigation_cannot_issue_host_conversation_commands(page):
    page.add_script_tag(url="http://127.0.0.1/static/foresight_programs.js")
    page.evaluate("""()=>{
      window.opened=[];
      window.programs=ForesightPrograms.create({toast:()=>{}});
      programs.bind({trays:[],open:(type,data)=>opened.push({type,data})});
      programs.programs.find(p=>p.id==='world_chat').url='/portal-audit';
      const body=document.createElement('div');document.body.appendChild(body);
      window.portal={type:'world_chat',data:{},state:{},body};
      programs.provider.mount(portal,{body,setTitle(){},changed(){}});
      portal.frame.dataset.audit='portal';
      portal.frame.style.cssText='position:fixed;left:0;top:0;width:320px;height:200px;z-index:100';
    }""")
    child = page.frame_locator('iframe[data-audit="portal"]')
    child.get_by_role("button", name="Request conversation").click()
    page.wait_for_function("opened.length===1")
    with page.expect_event(
        "framenavigated",
        predicate=lambda f: f.url.startswith("http://127.0.0.1:81/"),
    ):
        page.evaluate("portal.frame.src='http://127.0.0.1:81/portal-audit'")
    child.get_by_role("button", name="Request conversation").click()
    page.wait_for_timeout(100)
    assert page.evaluate("opened.length") == 1


def test_rejected_resize_rolls_back_geometry_and_pressure_history(page):
    page.evaluate(
        "openTray('large',{id:'fixed'});counter.lock(counter.find('fixed'),true);openTray('bpm',{id:'small'})"
    )
    page.evaluate("""()=>{
      const t=counter.find('small');t.chain.P[0][0]+=3;t.chain.dent=3;t.chain.calm=7;
      ForesightChain.restore(ForesightChain.snapshot(counter.trays));
      window.physical=()=>counter.trays.map(t=>({x:t.cx,y:t.cy,w:t.reqW,h:t.reqH,a:t.a,b:t.b,r:t.r,scale:t.scale,
        P:t.chain.P,R:t.chain.R,dent:t.chain.dent,calm:t.chain.calm,crowd:t.chain.crowd,vx:t.chain.vx,vy:t.chain.vy,fx:t.chain.fx,fy:t.chain.fy}));
    }""")
    before = page.evaluate("physical()")
    assert not page.evaluate(
        "counter.debug.trySize('small',1200,800,counter.find('fixed').cx,counter.find('fixed').cy)"
    )
    assert page.evaluate("physical()") == before


def test_admission_does_not_shrink_a_remote_indicator(page):
    page.evaluate(
        "openTray('large',{id:'first'});openTray('bpm',{id:'remote',x:1430,y:190})"
    )
    before = page.evaluate("counter.find('remote').scale")
    smallest = page.evaluate("""()=>{
      counter.open('large',null,{id:'second'});let smallest=counter.find('remote').scale;
      for(let i=0;i<320;i++){advance(1);smallest=Math.min(smallest,counter.find('remote').scale)}
      return smallest;
    }""")
    assert smallest == before
    assert page.evaluate("counter.find('remote').scale") == before
    assert not page.evaluate("!!counter.find('remote').squeezeReq")


@pytest.mark.parametrize("viewport", [(1366, 768), (1280, 800)])
def test_five_compact_working_trays_at_laptop_sizes(page, viewport):
    page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    page.evaluate("""()=>{
      openTray('keyboard',{id:'keyboard',w:600,h:190});
      openTray('timeline',{id:'timeline',w:340,h:260});
      openTray('reference',{id:'reference',w:240,h:150});
      openTray('archive',{id:'archive',w:240,h:150});
      openTray('bpm',{id:'bpm',w:100,h:70});
    }""")
    assert len(page.evaluate("geometry()")) == 5, page.evaluate(
        "counter.trays.map(t=>counter.debug.info(t.id))"
    )
    assert page.evaluate("counter.debug.pressure().overlap") <= 4.6
    for kind in ["keyboard", "timeline", "reference", "archive", "bpm"]:
        page.locator(f'[data-content-type="{kind}"] > button').click()
        page.evaluate("advance(20)")
    assert page.evaluate("counter.trays.map(t=>t.stack[0].state.clicks)") == [1] * 5


def test_compressed_growth_can_reach_a_different_aspect_than_the_content_minimum(page):
    page.evaluate("openTray('bpm',{id:'small'})")
    assert page.evaluate("counter.debug.trySize('small',80,30,900,500)")
    size = page.evaluate(
        "(()=>{const t=counter.find('small');return [t.reqW*t.scale,t.reqH*t.scale]})()"
    )
    assert size == pytest.approx([80, 30])


def test_immediate_reload_flushes_pending_layout_and_content_state(page):
    page.evaluate("openTray('keyboard',{id:'keyboard'});openTray('bpm',{id:'bpm'})")
    page.wait_for_timeout(450)
    page.locator('[data-content-type="keyboard"] > button').click()
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("window.counter")
    assert page.evaluate("counter.restore()")
    assert page.evaluate("counter.selected.id") == "keyboard"
    assert page.evaluate("counter.find('keyboard').stack[0].state.clicks") == 1


def test_mouse_focus_does_not_rapidly_inflate_a_compressed_tray(page):
    page.evaluate("""()=>{
      openTray('keyboard',{id:'keyboard'});openTray('bpm',{id:'bpm'});
      const t=counter.find('keyboard');ForesightChain.rescale(t,ForesightShapes,0.7);t.chain.calm=0;
      counter.debug.draw();
    }""")
    page.locator('[data-content-type="keyboard"] > button').click()
    assert page.evaluate("counter.selected.id") == "keyboard"
    page.evaluate("advance(1)")
    assert page.evaluate("counter.find('keyboard').scale") == 0.7
