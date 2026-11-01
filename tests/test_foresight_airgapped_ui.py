"""Exercise the REAL Counter menu/controller scripts without network navigation.

This is an environment-limited browser regression. Navigation to HTTP and file
URLs is prohibited by the runner; graphics is deliberately stubbed. It checks
real DOM menus, click handling, tray lifecycle and in-memory serialization,
NOT GPU quality, authenticated HTTP, embedded iframe execution, or persistence
across an actual browser restart. Those require separate target-device gates.
"""
from pathlib import Path
import os
import re
import shutil

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
COUNTER_HTML = (STATIC / "foresight_counter.html").read_text(encoding="utf-8")
SCRIPTS = re.findall(r"<script(?:\s+[^>]*)?>(.*?)</script>", COUNTER_HTML, flags=re.S)
APP_SCRIPT = next(script for script in reversed(SCRIPTS) if "async function boot()" in script)
DOM = re.sub(r"<script(?:\s+[^>]*)?>.*?</script>", "", COUNTER_HTML, flags=re.S)


def serve_counter(page):
    """Open the Counter page on a real http origin. page.set_content() gives it an opaque origin, where sessionStorage is
    refused and a relative fetch cannot be parsed, so the Counter's boot (which asks /api/writers-room/config who owns the
    workspace) stopped before it started the frame loop: no frames, so no tray ever opened. Only the owner lookup is
    answered; every other call gets a 404, as it would with no host behind the page."""
    def handle(route):
        url = route.request.url
        if url.endswith("/api/writers-room/config"):
            route.fulfill(status=200, content_type="application/json", body='{"user_id":"airgapped-test"}')
        elif url == "http://counter.test/":
            route.fulfill(status=200, content_type="text/html", body=DOM)
        else:
            route.fulfill(status=404, body="")
    page.route("http://counter.test/**", handle)
    page.goto("http://counter.test/")


@pytest.fixture
def counter_page():
    with playwright.sync_playwright() as p:
        executable = (os.environ.get("FORESIGHT_TEST_CHROMIUM")
                      or shutil.which("chromium") or shutil.which("chromium-browser")
                      or shutil.which("google-chrome"))
        try:
            browser = p.chromium.launch(
                **({"executable_path": executable} if executable else {}),
                args=["--disable-dev-shm-usage", "--use-angle=swiftshader"],
            )
        except playwright.Error as error:
            pytest.skip(f"Optional development browser unavailable: {error}")
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        serve_counter(page)
        page.evaluate("""() => {
          const storage = new Map();
          Object.defineProperty(window, 'localStorage', {configurable:true, value: {
            getItem: k=>storage.has(k)?storage.get(k):null,
            setItem: (k,v)=>storage.set(k,String(v)),
            removeItem: k=>storage.delete(k), clear:()=>storage.clear()
          }});
          window.ReachAuth={requireSession:async()=>({role:'owner'})};
        }""")
        for name in ["foresight.config.js", "foresight_shapes.js", "foresight_gl.js", "foresight_chain.js"]:
            page.add_script_tag(path=str(STATIC / name))
        # Replace only the renderer; the real Counter, physics, menus and provider
        # remain unmodified and interact with actual browser DOM.
        page.evaluate("""() => {
          const mat=ForesightGL.MAT;
          window.ForesightGL=class {
            static MAT=mat;
            constructor(){this.gl={finish(){}};this.quality='full';}
            loadStone(){}setTheme(){}setLight2(){}draw(){}
          };
        }""")
        for name in ["foresight_counter.js", "foresight_files.js", "foresight_programs.js"]:
            page.add_script_tag(path=str(STATIC / name))
        page.add_script_tag(content=APP_SCRIPT)
        page.wait_for_function("window.__counter && window.__programs")
        yield page
        assert not errors, errors
        browser.close()


def open_menu(page, name):
    page.get_by_role("button", name=name, exact=True).click()


def test_default_counter_menu_can_open_lock_close_and_reopen(counter_page):
    page = counter_page
    assert page.evaluate("__counter.trays.length") == 0
    open_menu(page, "File")
    page.get_by_role("menuitem", name="New blank tray").click()
    page.wait_for_function("__counter.trays.length===1 && !__counter.trays[0].hidden")
    assert page.evaluate("__counter.trays[0].stack[0].type") == "blank"
    open_menu(page, "View")
    page.get_by_role("menuitem", name="Lock this tray").click()
    assert page.evaluate("__counter.trays[0].locked")
    open_menu(page, "View")
    page.get_by_role("menuitem", name="Unlock this tray").click()
    assert not page.evaluate("__counter.trays[0].locked")
    open_menu(page, "File")
    page.get_by_role("menuitem", name="Close this tray into the fan").click()
    page.wait_for_function("__counter.trays[0].closed", timeout=5000)
    assert page.evaluate("__counter.trays[0].stack[0].type") == "blank"
    open_menu(page, "Window")
    item = page.get_by_role("menuitem", name=re.compile("in the fan"))
    assert item.count() == 1
    item.click()
    page.wait_for_function("!__counter.trays[0].closed && !__counter.trays[0].hidden", timeout=5000)


def test_real_counter_integrates_2i_hosting_and_restorable_layout(counter_page):
    page = counter_page
    # The actual program provider creates the iframe and retains content identity.
    page.evaluate("__programs.open('twoi')")
    page.wait_for_function("__counter.trays.some(t=>t.stack[0].type==='twoi') && !__counter.trays[0].hidden", timeout=5000)
    # the Counter adds a per-session nonce to the tray's address (?foresightSession=...), so match the path, not the whole address (it is also absolute once the page has an origin)
    page.locator('iframe[src*="/writers-room"]').wait_for(state="attached")
    assert page.locator('iframe[src*="/writers-room"]').count() == 1
    page.evaluate("__counter.saveNow()")
    saved = page.evaluate("__counter.serialize()")
    assert len(saved["trays"]) == 1
    assert saved["trays"][0]["contents"][0]["type"] == "twoi"
    assert page.evaluate("localStorage.getItem('foresight.counter.v3:airgapped-test')")
    # Reconstruct a fresh counter, not a merge into an already populated one.
    restored = page.evaluate("""snap => {
      __counter.destroy();
      const gl=new ForesightGL(document.getElementById('gl'));
      const fresh=ForesightCounter.create({canvas:document.getElementById('gl'),gl,
        provider:__programs.provider,storageKey:null,top:70});
      window.__restoredCounter=fresh;
      return fresh.restore(snap) && fresh.trays.length===1 &&
        fresh.trays[0].stack[0].type==='twoi';
    }""", saved)
    assert restored
    # We cannot navigate to /writers-room under this runner policy; iframe
    # creation and route correctness are verified separately by HTTP tests.


@pytest.fixture
def compatibility_page():
    """Actual application and its built-in Canvas 2D fallback, no GL test double."""
    with playwright.sync_playwright() as p:
        executable = (os.environ.get("FORESIGHT_TEST_CHROMIUM")
                      or shutil.which("chromium") or shutil.which("chromium-browser")
                      or shutil.which("google-chrome"))
        try:
            browser = p.chromium.launch(
                **({"executable_path": executable} if executable else {}),
                args=["--disable-dev-shm-usage", "--use-angle=swiftshader"],
            )
        except playwright.Error as error:
            pytest.skip(f"Optional development browser unavailable: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        serve_counter(page)
        page.evaluate("""() => {
          const storage=new Map();
          Object.defineProperty(window,'localStorage',{configurable:true,value:{
            getItem:k=>storage.has(k)?storage.get(k):null,
            setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)
          }});
          window.ReachAuth={requireSession:async()=>({role:'owner'})};
          // Force missing WebGL to test the product's real Canvas 2D failover,
          // not just whatever graphics drivers the CI machine happens to have.
          const real=HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext=function(mode,...args){
            if(mode==='webgl2'||mode==='webgl')return null;
            return real.call(this,mode,...args);
          };
        }""")
        for name in ["foresight.config.js", "foresight_shapes.js", "foresight_gl.js",
                     "foresight_canvas2d.js", "foresight_chain.js", "foresight_counter.js",
                     "foresight_files.js", "foresight_programs.js"]:
            page.add_script_tag(path=str(STATIC / name))
        page.add_script_tag(content=APP_SCRIPT)
        page.wait_for_function("window.__counter && !!window.ForesightCanvas2D")
        yield page
        assert not errors, errors
        browser.close()


def test_real_canvas2d_fallback_keeps_counter_usable(compatibility_page):
    page=compatibility_page
    assert page.get_by_role("status",name="Graphics compatibility mode").is_visible()
    open_menu(page,"File")
    page.get_by_role("menuitem",name="New blank tray").click()
    page.wait_for_function("__counter.trays.length===1 && !__counter.trays[0].hidden")
    assert page.evaluate("document.getElementById('gl').width > 0")
    assert page.evaluate("__counter.trays[0].stack[0].type") == "blank"
    # Changing lighting continues working under the alternate renderer.
    open_menu(page,"View")
    page.get_by_role("menuitem",name="Lantern light").click()
    assert page.evaluate("typeof __counter.debug.draw === 'function'")


def test_real_canvas2d_can_render_five_mixed_tray_shapes(compatibility_page):
    page=compatibility_page
    page.evaluate("""() => {
      for(const id of ['twoi','pubpartner_status','world_chat','recordings','doctor'])
        __programs.open(id);
    }""")
    # Crowded admission is a queued physics operation, not a synchronous call.
    # This is a generous CI bound; target-device animation performance is a
    # separate measured acceptance gate, never silently relaxed in physics tests.
    page.wait_for_function("__counter.trays.length===5",timeout=30000)
    page.evaluate("__counter.settle(120)")
    assert page.evaluate("__counter.trays.length") == 5
    assert page.evaluate("__counter.trays.every(t=>t.stack.length===1)")
    assert page.evaluate("document.querySelectorAll('.fc-plaque').length") == 5
