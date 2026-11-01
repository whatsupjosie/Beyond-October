"""Actual 2i v22, provider, IndexedDB and browser file operations.

Local routing supplies repository bytes; browser rendering is real. No claim of
GPU Counter physics or physical audio. Format API calls use the real converters.
"""

import base64
import io
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="Optional browser verification requires Playwright"
).sync_playwright
from docx import Document
from PIL import Image
from modules.foresight_file_formats import convert
from modules.foresight_workspace import create_workspace_router
from modules.writers_room import create_writers_room_router
from modules.auth_routes import router as auth_router
from modules import userdb
from modules.auth import create_access_token
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
HTML = """<html><head><style>#host>iframe{width:100%;height:100%;border:0}</style></head><body><div id="host" style="width:1100px;height:850px"></div>
<script src="/static/foresight_files.js"></script><script src="/static/foresight_programs.js"></script>
<script>
window.app=ForesightPrograms.create({});window.p=app.provider;
window.openFile=(name,text,mime='text/plain')=>{
 const r=p.fromFile(new File([text],name,{type:mime}));localStorage.setItem('file-data',JSON.stringify(r.data));localStorage.setItem('file-type',r.type);return mount(r.data,r.type);
};
window.mount=(data,type='file')=>{window.c={type,data,state:{},body:document.getElementById('host')};window.host={body:c.body,changed(){},setTitle(){}};return p.mount(c,host)};
window.restore=()=>mount(JSON.parse(localStorage.getItem('file-data')),localStorage.getItem('file-type')||'file');
</script></body></html>"""


@pytest.fixture
def page(tmp_path, monkeypatch):
    # A real user database in this test's own folder, with a real owner made by first-run setup, so the
    # session check and the owner-scoped working copies run their real code.
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    userdb._sync_init_db()
    assert userdb._sync_create_owner_via_setup("offline-writer", "offline-writer-password-1234")
    with sync_playwright() as p:
        engine = os.environ.get("FORESIGHT_TEST_BROWSER", "chromium")
        browser = (
            p.firefox.launch(timeout=20000)
            if engine == "firefox"
            else p.chromium.launch(
                args=["--single-process", "--no-zygote", "--use-angle=swiftshader"],
                executable_path=os.environ.get("FORESIGHT_TEST_CHROMIUM") or None
            )
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000}, accept_downloads=True
        )

        external = []
        api_app = FastAPI()
        api_app.include_router(create_workspace_router(tmp_path))
        # The real routes the file provider and 2i now call before they open a file: the signed-in owner
        # (/api/writers-room/config scopes working copies) and the session check (/api/auth/*).
        api_app.include_router(create_writers_room_router(tmp_path))
        api_app.include_router(auth_router)
        api_client = TestClient(api_app)
        test_token = create_access_token({"sub": "offline-writer", "role": "owner"})
        context.add_init_script(
            "sessionStorage.setItem('pubcast_token',"
            + __import__("json").dumps(test_token)
            + ");window.showSaveFilePicker=undefined;"
        )

        def route(r):
            address = urlparse(r.request.url)
            if address.netloc != "localhost":
                external.append(r.request.url)
                r.abort()
                return
            path = address.path
            if path.startswith(("/api/foresight/workspace/", "/api/writers-room/", "/api/auth/")):
                response = api_client.request(
                    r.request.method,
                    path + ("?" + address.query if address.query else ""),
                    content=r.request.post_data,
                    headers={
                        k: v
                        for k, v in r.request.headers.items()
                        if k.lower() in {"authorization", "content-type"}
                    },
                )
                r.fulfill(
                    status=response.status_code,
                    body=response.content,
                    content_type=response.headers.get(
                        "content-type", "application/json"
                    ),
                )
                return
            if path == "/test":
                r.fulfill(body=HTML, content_type="text/html")
                return
            if path == "/api/foresight/files/convert":
                b = r.request.post_data_json
                try:
                    r.fulfill(json=convert(b["name"], base64.b64decode(b["data"])))
                except ValueError as e:
                    r.fulfill(status=422, json={"detail": str(e)})
                return
            if path == "/writers-room":
                file = ROOT / "2i/writers-room-v22.html"
            elif path.startswith("/static/"):
                file = ROOT / path.lstrip("/")
            elif path.startswith("/2i-assets/"):
                file = ROOT / "2i" / path.lstrip("/")
            else:
                r.fulfill(status=404, body="Not found")
                return
            if file.is_file():
                r.fulfill(
                    body=file.read_bytes(),
                    content_type=mimetypes.guess_type(file.name)[0]
                    or "application/octet-stream",
                )
            else:
                r.fulfill(status=404, body="Not found")

        context.route("**/*", route)
        page = context.new_page()
        page.goto("http://localhost/test")
        page.workspace_root = tmp_path
        yield page
        browser.close()
        api_client.close()
        assert not external, "File work attempted external network access: " + repr(
            external
        )


def editor(page):
    return page.frame_locator("#host iframe").locator("#soloTextarea")


def test_native_2i_edit_save_export_and_reopen(page):
    page.evaluate("openFile('script.py', 'print(\"original\")\\n')")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('.ff-workspace [role=status]')?.textContent.includes('ready')"
    )
    assert text.input_value() == 'print("original")\n'
    text.fill('print("edited")\n# retained\n')
    page.evaluate("p.save(c)")
    result = page.evaluate(
        "async()=>{const f=await p.exportContent(c);return {name:f.name,text:await f.data.text()}}"
    )
    assert result == {"name": "script.py", "text": 'print("edited")\n# retained\n'}
    page.reload()
    page.evaluate("restore()")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('#soloTextarea')?.value.includes('edited')"
    )
    assert text.input_value() == result["text"]
    original = page.evaluate(
        "async()=>{const v=await ForesightFiles.record(c.data.fileId);return await v.original.text()}"
    )
    assert original == 'print("original")\n'


def test_docx_opens_in_native_2i_as_explicit_text_copy(page):
    d = Document()
    d.add_paragraph("Curtsey document")
    b = io.BytesIO()
    d.save(b)
    page.evaluate(
        "b=>{const bytes=Uint8Array.from(atob(b),c=>c.charCodeAt(0));return openFile('work.docx',bytes,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}",
        base64.b64encode(b.getvalue()).decode(),
    )
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('#soloTextarea')?.value==='Curtsey document'"
    )
    assert (
        "not preserved"
        in page.frame_locator("#host iframe").locator("[role=status]").inner_text()
    )
    editor(page).fill("Edited document")
    page.evaluate("p.save(c)")
    result = page.evaluate(
        "async()=>{const f=await p.exportContent(c);return {name:f.name,text:await f.data.text()}}"
    )
    assert result == {"name": "work.txt", "text": "Edited document"}
    assert page.evaluate(
        "async()=>{const v=await ForesightFiles.record(c.data.fileId);return v.original.size}"
    ) == len(b.getvalue())


def test_image_rotate_crop_download_and_restore(page):
    out = io.BytesIO()
    Image.new("RGB", (80, 40), "red").save(out, format="PNG")
    page.evaluate(
        "b=>openFile('picture.png',Uint8Array.from(atob(b),c=>c.charCodeAt(0)),'image/png')",
        base64.b64encode(out.getvalue()).decode(),
    )
    frame = page.frame_locator("#host iframe")
    canvas = frame.locator('canvas[aria-label="Image editor"]')
    canvas.wait_for()
    frame.get_by_role("button", name="Rotate 90°", exact=True).click()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('canvas[aria-label=\"Image editor\"]')?.width===40"
    )
    page.once("dialog", lambda dialog: dialog.accept("0, 0, 20, 30"))
    frame.get_by_role("button", name="Crop…", exact=True).click()
    page.evaluate("p.save(c)")
    result = page.evaluate(
        "async()=>{const f=await p.exportContent(c);const a=new Uint8Array(await f.data.arrayBuffer());return Array.from(a)}"
    )
    image = Image.open(io.BytesIO(bytes(result)))
    assert image.size == (20, 30)
    page.reload()
    page.evaluate("restore()")
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('canvas[aria-label=\"Image editor\"]')?.width===20"
    )


def test_unknown_binary_preserves_original_without_false_text(page):
    page.evaluate(
        "openFile('unknown.bin',new Uint8Array([0,1,2,255]),'application/octet-stream')"
    )
    frame = page.frame_locator("#host iframe")
    frame.get_by_role("button", name="Download original", exact=True).wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('Could not open')"
    )
    assert not editor(page).input_value()
    with page.expect_download() as dl:
        frame.get_by_role("button", name="Download original", exact=True).click()
    assert Path(dl.value.path()).read_bytes() == bytes([0, 1, 2, 255])


def test_save_as_download_is_edited_file_and_2i_export_keeps_state(page):
    page.evaluate("openFile('notes.md', '# Original\\n')")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('ready')"
    )
    text.fill("# Edited\nParagraph")
    frame = page.frame_locator("#host iframe")
    page.evaluate(
        "document.querySelector('#host iframe').contentWindow.showSaveFilePicker=undefined"
    )
    with page.expect_download() as result:
        frame.get_by_role("button", name="Save to device…", exact=True).click()
    assert Path(result.value.path()).read_text() == "# Edited\nParagraph"
    assert result.value.suggested_filename == "notes.md"
    with page.expect_download() as result:
        frame.get_by_role("button", name="Export 2i manuscript", exact=True).click()
    import json

    saved = json.loads(Path(result.value.path()).read_text())
    assert saved["format"] == "2i-document"
    assert saved["state"]["committed"] == ["# Edited", "Paragraph"]


def test_tray_metadata_and_browser_shortcut_import_roundtrip(page):
    result = page.evaluate(
        "async()=>{const c={type:'browser',data:{address:'https://example.org/article'},state:{}};const f=await p.exportContent(c);return await p.resolveFile(new File([f.data],f.name,{type:f.type}))}"
    )
    assert result == {
        "type": "browser",
        "data": {"address": "https://example.org/article"},
    }
    result = page.evaluate(
        "async()=>{const c={type:'chat',title:'Chat',data:{conversationId:'saved-conversation'},state:{}};const f=await p.exportContent(c);return await p.resolveFile(new File([f.data],f.name,{type:f.type}))}"
    )
    assert result == {"type": "chat", "data": {"conversationId": "saved-conversation"}}


def test_native_text_undo_and_clipboard_paste(page):
    page.evaluate("openFile('code.py','start')")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('ready')"
    )
    text.click()
    text.press("End")
    page.keyboard.insert_text(" typed")
    text.press("Control+z")
    assert text.input_value() == "start"
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("navigator.clipboard.writeText(' pasted')")
    text.press("End")
    text.press("Control+v")
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('#soloTextarea')?.value==='start pasted'"
    )
    page.evaluate("p.save(c)")
    assert (
        page.evaluate(
            "async()=>{const f=await p.exportContent(c);return f.data.text()}"
        )
        == "start pasted"
    )


def test_saved_working_copy_rejects_stale_writer(page):
    result = page.evaluate(
        "async()=>{await ForesightFiles.record('conflict',{id:'conflict',draft:'first'});await ForesightFiles.record('conflict',{id:'conflict',draft:'new'},0);let error;try{await ForesightFiles.record('conflict',{id:'conflict',draft:'stale'},0)}catch(e){error=e.message}return {draft:(await ForesightFiles.record('conflict')).draft,error}}"
    )
    assert result["draft"] == "new"
    assert "another window" in result["error"]


def test_cancelled_crop_does_not_create_an_edited_copy(page):
    out = io.BytesIO()
    Image.new("RGB", (20, 10), "blue").save(out, format="JPEG")
    page.evaluate(
        "b=>openFile('original.jpg',Uint8Array.from(atob(b),c=>c.charCodeAt(0)),'image/jpeg')",
        base64.b64encode(out.getvalue()).decode(),
    )
    frame = page.frame_locator("#host iframe")
    frame.locator('canvas[aria-label="Image editor"]').wait_for()
    page.once("dialog", lambda d: d.dismiss())
    frame.get_by_role("button", name="Crop…", exact=True).click()
    page.evaluate("p.save(c)")
    result = page.evaluate(
        "async()=>{const f=await p.exportContent(c);return {name:f.name,size:f.data.size}}"
    )
    assert result == {"name": "original.jpg", "size": len(out.getvalue())}


def test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker(page):
    page.evaluate("openFile('offline.md','# Original')")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('ready')"
    )
    text.fill("# Offline saved file\nSecond line")
    page.once("dialog", lambda d: d.accept("Documents/offline.md"))
    page.frame_locator("#host iframe").get_by_role(
        "button", name="Save As…", exact=True
    ).click()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('Saved local file')"
    )
    disk = list(page.workspace_root.rglob("offline.md"))[0]
    assert disk.read_text() == "# Offline saved file\nSecond line"
    text.fill("# Second edit")
    page.evaluate("p.save(c)")
    assert disk.read_text() == "# Second edit"
    page.reload()
    page.evaluate("restore()")
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('#soloTextarea')?.value==='# Second edit'"
    )
    assert disk.read_text() == "# Second edit"


def test_python_syntax_check_in_native_editor_without_external_services(page):
    page.evaluate("openFile('test.py','if broken\\n pass')")
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('ready')"
    )
    frame = page.frame_locator("#host iframe")
    frame.get_by_role("button", name="Check Python", exact=True).click()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('line 1')"
    )
    text.fill("print(42)")
    frame.get_by_role("button", name="Check Python", exact=True).click()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('not executed')"
    )
    page.wait_for_timeout(600)  # The pending autosave must not erase the syntax result.
    assert "not executed" in frame.get_by_role("status").inner_text()


def test_normal_2i_manuscript_saves_to_reach_and_each_save_is_a_new_revision(page):
    """Signed in to Reach, 2i keeps a normal manuscript on the host (/api/writers-room/documents), owner-scoped,
    one revision per save. (Before the real config route was served here, this test expected the offline
    local-folder fallback, which only applies when Reach does not answer.)"""
    import json, sqlite3
    page.goto("http://localhost/writers-room")
    text = page.locator("#soloTextarea")
    text.wait_for()
    page.wait_for_function("document.querySelector('#saveBtn').disabled===false")
    text.fill("Local manuscript\nSecond paragraph")
    page.locator("#saveBtn").click()
    page.wait_for_function("document.querySelector('#saveIndicator').textContent.includes('Saved to Reach · revision 1')")

    def stored():
        with sqlite3.connect(page.workspace_root / "writers_room" / "documents.sqlite3") as db:
            rows = db.execute("SELECT owner, revision, payload FROM documents").fetchall()
        assert len(rows) == 1
        owner, revision, payload = rows[0]
        return owner, revision, json.loads(payload)["state"]["committed"]

    assert stored() == ("offline-writer", 1, ["Local manuscript", "Second paragraph"])
    text.fill("Updated manuscript")
    page.locator("#saveBtn").click()
    page.wait_for_function("document.querySelector('#saveIndicator').textContent.includes('Saved to Reach · revision 2')")
    assert stored() == ("offline-writer", 2, ["Updated manuscript"])
    # and it comes back on reopen
    page.reload()
    page.locator("#soloTextarea").wait_for()
    page.wait_for_function("document.querySelector('#soloTextarea').value.includes('Updated manuscript')", timeout=15000)


def test_local_audio_decodes_plays_and_reopens_offline(page):
    import wave

    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 8000)
    raw = out.getvalue()
    page.evaluate(
        "b=>openFile('local.wav',Uint8Array.from(atob(b),c=>c.charCodeAt(0)),'audio/wav')",
        base64.b64encode(raw).decode(),
    )
    page.wait_for_function("document.querySelector('#host video')?.readyState>=1")
    page.evaluate(
        "()=>{const v=document.querySelector('#host video');v.muted=true;return v.play()}"
    )
    page.wait_for_function("document.querySelector('#host video')?.currentTime>0")
    page.evaluate("document.querySelector('#host video').pause()")
    page.reload()
    page.evaluate("restore()")
    page.wait_for_function("document.querySelector('#host video')?.readyState>=1")
    assert page.evaluate(
        "async()=>{const file=await ForesightFiles.record(c.data.fileId);return file.original.size}"
    ) == len(raw)


def test_2i_open_edit_export_preserves_title_and_unknown_metadata(page):
    import json

    original = {
        "format": "2i-document",
        "version": 4,
        "title": "Author title",
        "state": {
            "committed": ["Original text"],
            "buffer": [],
            "pool": [],
            "pointer": 0,
            "chapters": [],
            "lockedLines": [],
            "coWriting": False,
            "references": [],
            "extensionMetadata": {"keep": "verbatim"},
        },
    }
    page.evaluate(
        "text=>openFile('different-filename.2i',text,'application/json')",
        json.dumps(original),
    )
    text = editor(page)
    text.wait_for()
    page.wait_for_function(
        "document.querySelector('#host iframe')?.contentWindow.document.querySelector('[role=status]')?.textContent.includes('ready')"
    )
    text.fill("Edited text")
    page.evaluate("p.save(c)")
    result = page.evaluate(
        "async()=>{const f=await p.exportContent(c);return JSON.parse(await f.data.text())}"
    )
    assert result["title"] == "Author title"
    assert result["state"]["committed"] == ["Edited text"]
    assert result["state"]["extensionMetadata"] == {"keep": "verbatim"}
