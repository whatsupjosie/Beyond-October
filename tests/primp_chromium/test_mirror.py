"""Rendered user workflows, using real files, WebGL, IndexedDB and the actual host."""
import base64
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageChops
import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]


def image(page):
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    encoded = page.locator('#viewport canvas').evaluate('c=>c.toDataURL("image/png").split(",")[1]')
    return base64.b64decode(encoded)


def difference(a, b):
    return ImageChops.difference(Image.open(io.BytesIO(a)).convert('RGB'), Image.open(io.BytesIO(b)).convert('RGB'))


def same(a, b):
    return difference(a, b).getbbox() is None


def neutral_quantization_only(a, b):
    # Linear factors baked to 8-bit sRGB can move a code value at rare pixels.
    # Exact layer undo is independently covered; this is original-vs-baked only.
    diff = difference(a, b)
    if any(high > 1 for low, high in diff.getextrema()):
        return False
    raw = diff.tobytes()
    changed = sum(1 for i in range(0, len(raw), 3) if raw[i] or raw[i+1] or raw[i+2])
    return changed <= diff.width * diff.height * .001


def choose(page, name='sheila'):
    page.locator(f'[data-base={name}]').click()
    expect(page.locator('#status')).to_contain_text('Avatar ready')
    expect(page.locator('#surface option')).to_have_count(1)


def stroke(page):
    box = page.locator('#viewport canvas').bounding_box()
    x, y = box['x']+box['width']/2, box['y']+box['height']/2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x+8, y, steps=5)
    page.mouse.up()
    image(page)


def download(page, button, destination):
    with page.expect_download() as caught:
        page.locator(button).click()
    caught.value.save_as(destination)
    return Path(destination)


@pytest.mark.parametrize('name', ['manny', 'sheila'])
def test_prepared_avatar_renders_frames_rotates_and_lights(mirror, tmp_path, name):
    page = mirror
    empty = image(page)
    choose(page, name)
    whole = image(page)
    assert not same(empty, whole)
    page.locator('#face').click()
    close = image(page)
    assert not same(whole, close)
    page.locator('#light').select_option('warm')
    warm = image(page)
    assert not same(close, warm)
    page.locator('[data-tool=orbit]').click()
    box = page.locator('#viewport canvas').bounding_box()
    x, y = box['x']+box['width']/2, box['y']+box['height']/2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x+80, y, steps=12)
    page.mouse.up()
    assert not same(warm, image(page))
    page.screenshot(path=str(tmp_path/f'{name}-rendered.png'), full_page=True)


def test_paint_undo_compare_save_reopen_export_and_recovery(mirror, tmp_path):
    page = mirror
    choose(page)
    page.locator('#detail').select_option('2048')
    before = image(page)
    page.get_by_role('button', name='Ink', exact=True).click()
    stroke(page)
    expect(page.locator('#undo')).to_be_enabled()
    painted = image(page)
    assert not same(before, painted)
    page.locator('#undo').click()
    assert neutral_quantization_only(before, image(page))
    page.locator('#redo').click()
    assert same(painted, image(page))
    page.locator('#compare').click()
    assert same(before, image(page))
    page.locator('#compare').click()
    assert same(painted, image(page))
    project = download(page, '#save', tmp_path/'painted.primp')
    saved = json.loads(project.read_text())
    assert saved['version'] == 2 and saved['targets'][0]['size'] == 2048
    assert base64.b64decode(saved['source']) == (ROOT/'static/primp/avatars/sheila.glb').read_bytes()
    layer = saved['targets'][0]['layers'][5]['png']
    pixels = Image.open(io.BytesIO(base64.b64decode(layer.split(',')[1])))
    assert pixels.size == (2048, 2048) and pixels.getbbox()
    expect(page.locator('#status')).to_contain_text('Unsaved-work protection stays on')
    page.locator('#clear').click()
    assert neutral_quantization_only(before, image(page))
    page.locator('#project-file').set_input_files(project)
    expect(page.locator('#status')).to_contain_text('Editable look reopened')
    assert same(painted, image(page))
    exported = download(page, '#export', tmp_path/'painted.glb')
    assert exported.read_bytes()[:4] == b'glTF'
    page.locator('#avatar-file').set_input_files(exported)
    expect(page.locator('#status')).to_contain_text('Avatar ready')
    assert same(painted, image(page))
    page.locator('#project-file').set_input_files(project)
    expect(page.locator('#storage-status')).to_have_text('Local recovery saved on this device.', timeout=15000)
    page.reload()
    expect(page.locator('#recover')).to_be_visible()
    page.locator('#recover').click()
    expect(page.locator('#status')).to_contain_text('Editable look reopened')
    assert same(painted, image(page))
    snapshot = download(page, '#snapshot', tmp_path/'mirror.png')
    assert same(painted, snapshot.read_bytes())
    page.screenshot(path=str(tmp_path/'painted-recovered.png'), full_page=True)


def test_ten_pointer_edits_and_keyboard_undo(mirror):
    page = mirror
    choose(page)
    before = image(page)
    for i in range(10):
        page.get_by_role('button', name='Ink' if i%2 else 'Berry', exact=True).click()
        stroke(page)
    expect(page.locator('#history-info')).to_contain_text('10 undo / 0 redo')
    final = image(page)
    page.locator('#viewport canvas').focus()
    for _ in range(10):
        page.keyboard.press('Control+z')
    expect(page.locator('#history-info')).to_contain_text('0 undo / 10 redo')
    assert neutral_quantization_only(before, image(page))
    for _ in range(10):
        page.keyboard.press('Control+y')
    assert same(final, image(page))


def test_graphics_loss_preserves_work_and_restores_render(mirror, tmp_path):
    page = mirror
    choose(page)
    stroke(page)
    painted = image(page)
    assert page.locator('#viewport canvas').evaluate("c=>{window.testLoss=c.getContext('webgl2').getExtension('WEBGL_lose_context');if(!window.testLoss)return false;window.testLoss.loseContext();return true;}")
    expect(page.locator('#status')).to_contain_text('Graphics context lost')
    expect(page.locator('#export')).to_be_disabled()
    expect(page.locator('#save')).to_be_enabled()
    saved = download(page, '#save', tmp_path/'lost-context.primp')
    assert json.loads(saved.read_text())['targets'][0]['layers'][5]['png']
    page.evaluate('window.testLoss.restoreContext()')
    expect(page.locator('#status')).to_have_text('Graphics restored.', timeout=15000)
    assert same(painted, image(page))


def test_mobile_touch_paint_and_layout(browser, live_host, tmp_path):
    with browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True, device_scale_factor=1) as context:
        context.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(live_host['account']['access_token'])+');window.showSaveFilePicker=undefined;')
        page = context.new_page()
        page.goto(live_host['url']+'/static/primp.html')
        choose(page)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        before = image(page)
        box = page.locator('#viewport canvas').bounding_box()
        page.touchscreen.tap(box['x']+box['width']/2, box['y']+box['height']/2)
        expect(page.locator('#undo')).to_be_enabled()
        assert not same(before, image(page))
        page.locator('#undo').click()
        assert neutral_quantization_only(before, image(page))
        page.screenshot(path=str(tmp_path/'mobile-touch.png'), full_page=True)


def test_invalid_import_keeps_painted_look(mirror, tmp_path):
    page = mirror
    choose(page)
    stroke(page)
    painted = image(page)
    bad = tmp_path/'broken.glb'
    bad.write_bytes(b'glTFnotavalidfile')
    page.locator('#avatar-file').set_input_files(bad)
    expect(page.locator('#status')).to_have_attribute('data-error', 'true')
    assert same(painted, image(page))
    expect(page.locator('#undo')).to_be_enabled()


def test_accessibility_and_keyboard_controls(mirror):
    page = mirror
    choose(page)
    axe = os.environ.get('AXE_CORE_PATH')
    assert axe and Path(axe).is_file(), 'Install axe-core and set AXE_CORE_PATH'
    page.add_script_tag(path=axe)
    result = page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))}")
    assert not result, json.dumps(result, indent=2)
    page.locator('[data-tool=orbit]').focus()
    page.keyboard.press('Enter')
    expect(page.locator('[data-tool=orbit]')).to_have_attribute('aria-pressed','true')
    page.locator('#compare').focus()
    page.keyboard.press('Space')
    expect(page.locator('#compare')).to_have_attribute('aria-pressed','true')
    page.keyboard.press('Space')
    expect(page.locator('#compare')).to_have_attribute('aria-pressed','false')


def test_real_rigged_face_paint_and_layers(mirror, tmp_path):
    page = mirror
    page.locator('#avatar-file').set_input_files(ROOT/'tests/fixtures/avatars/mh_female.glb')
    expect(page.locator('#status')).to_contain_text('Avatar ready')
    page.locator('#face').click()
    before = image(page)
    page.get_by_role('button', name='Ink', exact=True).click()
    stroke(page)
    expect(page.locator('#undo')).to_be_enabled()
    painted = image(page)
    assert not same(before, painted)
    page.locator('#visible').uncheck()
    assert same(before, image(page))
    page.locator('#visible').check()
    assert same(painted, image(page))
    page.locator('#layer-opacity').focus()
    page.keyboard.press('Home')
    assert same(before, image(page))
    page.keyboard.press('End')
    assert same(painted, image(page))
    page.locator('#layer').select_option('0')
    page.get_by_role('button', name='Terracotta', exact=True).click()
    page.locator('[data-tool=powder]').click()
    stroke(page)
    assert not same(painted, image(page))
    page.screenshot(path=str(tmp_path/'rigged-face-painted.png'), full_page=True)


def test_browser_and_host_restart_recover_identical_paint(playwright, browser_type_launch_args, live_host, tmp_path):
    profile = tmp_path/'browser-profile'

    def reopen():
        context = playwright.chromium.launch_persistent_context(str(profile), viewport={'width':1280,'height':900}, **browser_type_launch_args)
        context.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(live_host['account']['access_token'])+');window.showSaveFilePicker=undefined;')
        page = context.pages[0]
        page.goto(live_host['url']+'/static/primp.html')
        return context, page

    context, page = reopen()
    try:
        choose(page)
        stroke(page)
        painted = image(page)
        expect(page.locator('#storage-status')).to_have_text('Local recovery saved on this device.', timeout=15000)
    finally:
        context.close()
    live_host['restart']()
    context, page = reopen()
    try:
        expect(page.locator('#recover')).to_be_visible()
        page.locator('#recover').click()
        expect(page.locator('#status')).to_contain_text('Editable look reopened')
        assert same(painted, image(page))
    finally:
        context.close()


def test_repeated_edits_keep_history_bounded(mirror):
    page = mirror
    choose(page)
    for i in range(60):
        page.get_by_role('button', name='Ink' if i%2 else 'Berry', exact=True).click()
        stroke(page)
    text = page.locator('#history-info').inner_text()
    assert text.startswith('10 undo / 0 redo')
    assert float(text.split('·')[1].strip().split()[0]) <= 64
    for _ in range(10):
        page.locator('#undo').click()
    expect(page.locator('#history-info')).to_contain_text('0 undo / 10 redo')
    assert page.locator('#viewport canvas').evaluate("c=>!c.getContext('webgl2').isContextLost()")


def test_real_browser_writer_with_opfs_handle(mirror):
    # Real browser file writer; supplied handle does not test the OS picker.
    result = mirror.evaluate("""async()=>{
      const {saveLookFile}=await import('/static/primp/files.mjs');
      const directory=await navigator.storage.getDirectory();
      const handle=await directory.getFileHandle('primp-writer.primp',{create:true});
      const result=await saveLookFile(()=>new Blob(['exact editable bytes']),'check.primp',{
        picker:async()=>handle,download:()=>{throw Error('Unexpected fallback');}
      });
      return {confirmed:result.confirmed,text:await (await handle.getFile()).text()};
    }""")
    assert result == {'confirmed':True,'text':'exact editable bytes'}


def test_invalid_identity_cannot_overwrite_recovery(mirror):
    page = mirror
    choose(page)
    stroke(page)
    expect(page.locator('#storage-status')).to_have_text('Local recovery saved on this device.', timeout=15000)
    read = """async()=>{
      const {readRecoveryRecord}=await import('/static/primp/recovery.mjs');
      const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('primp-mirror:account:primp-browser',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
      try{return (await readRecoveryRecord(db)).revision;}finally{db.close();}
    }"""
    revision = page.evaluate(read)
    page.evaluate("sessionStorage.setItem('pubcast_token','invalid-or-expired')")
    page.get_by_role('button', name='Ink', exact=True).click()
    stroke(page)
    expect(page.locator('#storage-status')).to_contain_text('Sign in to PubCast', timeout=15000)
    assert page.evaluate(read) == revision
    expect(page.locator('#save')).to_be_enabled()


def test_foundation_browser_harness(page, live_host):
    # Only test resources are supplied here; production modules use the real host.
    page.route('**/qa/browser.html', lambda r:r.fulfill(path=str(ROOT/'tests/primp/browser.html'),content_type='text/html'))
    page.route('**/qa/browser.mjs', lambda r:r.fulfill(path=str(ROOT/'tests/primp/browser.mjs'),content_type='text/javascript'))
    page.route('**/fixtures/mh_female.glb', lambda r:r.fulfill(path=str(ROOT/'tests/fixtures/avatars/mh_female.glb'),content_type='model/gltf-binary'))
    page.goto(live_host['url']+'/qa/browser.html')
    page.locator('#run').click()
    expect(page.locator('#results')).to_contain_text('RESULT: 23 passed; 0 failed.', timeout=60000)
