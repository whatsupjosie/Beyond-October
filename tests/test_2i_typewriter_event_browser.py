"""Claude's touch-key events must edit 2i's authoritative textarea, not a demo buffer.

Standalone synthetic host: uses the ACTUAL production 2i input bridge,
studio-desk and typewriter-demo scripts through intercepted localhost routes.
No real server, account or network required. Requires Chromium/Playwright.
"""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]

PARENT = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<section id="mcSection"><div class="section-body"></div></section>
<textarea id="soloTextarea">Original</textarea><textarea id="draftArea"></textarea>
<script>
const reachFileMode=false;
const $=id=>document.getElementById(id);
const soloTextarea=$('soloTextarea'),draftArea=$('draftArea');
let coWriting=false,initializing=false,generating=false,chatSending=false,editingIdx=null;
window.receivedInputs=0;window.writerNotes=[];
function addChat(role,message){writerNotes.push({role,message});}
soloTextarea.addEventListener('input',()=>receivedInputs++);
draftArea.addEventListener('input',()=>receivedInputs++);
</script>
<script src="/static/2i_studio_bridge.js"></script>
<script src="/2i/2i-assets/typewriter-key-bridge.js"></script>
<script src="/2i/2i-assets/studio-desk.js"></script>
</body></html>"""

CHILD = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<div id="painted" style="width:900px;height:600px;position:relative"></div>
<script src="/static/typewriter_console_demo.js"></script>
<script>
document.dispatchEvent(new CustomEvent('pubcast:console-ready', {
 detail:{frame:document.getElementById('painted'),manifest:{paper:{x:0.2,y:0.05,w:0.6,h:0.32}}}
}));
</script>
</body></html>"""


@pytest.fixture()
def app():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1024, "height": 768})
        errors = []

        def serve(route):
            request = urlsplit(route.request.url)
            if request.hostname != "localhost":
                return route.abort()
            if request.path == "/test-parent":
                return route.fulfill(status=200, body=PARENT, content_type="text/html")
            if request.path == "/typewriter-console":
                return route.fulfill(status=200, body=CHILD, content_type="text/html")
            sources = {
                "/static/2i_studio_bridge.js":"static/2i_studio_bridge.js",
                "/static/typewriter_console_demo.js":"static/typewriter_console_demo.js",
                "/2i/2i-assets/typewriter-key-bridge.js":"2i/2i-assets/typewriter-key-bridge.js",
                "/2i/2i-assets/studio-desk.js":"2i/2i-assets/studio-desk.js",
            }
            if request.path in sources:
                file = ROOT / sources[request.path]
                return route.fulfill(status=200, body=file.read_bytes(), content_type="text/javascript")
            return route.fulfill(status=404, body="Not found")

        context.route("**/*", serve)
        page = context.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto("http://localhost/test-parent")
        page.evaluate("twoiSetPresentation('typewriter')")
        page.evaluate("soloTextarea.focus(); soloTextarea.setSelectionRange(soloTextarea.value.length,soloTextarea.value.length)")
        page.locator("#twoiTouchableTypewriter").click()
        child = page.frame_locator("#twoiLiveKeysFrame")
        child.locator("#painted").wait_for()
        yield page, child
        assert errors == [], errors
        browser.close()


def _key(child, char, text=""):
    child.locator("#painted").evaluate(
        "(el,key) => el.dispatchEvent(new CustomEvent('pubcast:key', {detail:key}))",
        {"char":char,"text":text,"source":"pointer"},
    )


def test_touch_keyboard_edits_real_manuscript_and_preserves_native_undo(app):
    page,child = app
    _key(child,"A","X")
    page.wait_for_function("soloTextarea.value==='OriginalX'")
    assert page.evaluate("receivedInputs") == 1
    _key(child,"SHIFT","")
    assert page.input_value("#soloTextarea") == "OriginalX"
    assert page.evaluate("writerNotes.length") == 0
    _key(child,"BACKSPACE","")
    page.wait_for_function("soloTextarea.value==='Original'")
    _key(child,"RETURN","\n")
    page.wait_for_function("soloTextarea.value==='Original\\n'")
    assert page.evaluate("receivedInputs") == 3
    page.locator("#soloTextarea").focus()
    page.keyboard.press("Control+z")
    assert page.input_value("#soloTextarea") == "Original"


def test_closing_keyboard_and_spoofed_messages_cannot_edit_document(app):
    page,child = app
    page.locator("#twoiLiveKeys button").click()
    _key(child,"A","X")
    page.wait_for_timeout(60)
    assert page.input_value("#soloTextarea") == "Original"
    page.evaluate("window.postMessage({type:'pubcast:2i-key',key:{char:'A',text:'X'}},location.origin)")
    page.wait_for_timeout(60)
    assert page.input_value("#soloTextarea") == "Original"


def test_collab_routes_to_draft_not_approved_manuscript(app):
    page,child = app
    page.evaluate("coWriting=true; draftArea.focus()")
    _key(child,"A","Draft")
    page.wait_for_function("draftArea.value==='Draft'")
    assert page.input_value("#soloTextarea") == "Original"
