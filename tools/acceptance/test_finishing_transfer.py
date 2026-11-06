"""Real stage pixels -> server ZIP -> fresh data root/browser -> rough-cut export.

This checks the current encoded-media path, not scene replay or Resolve itself.
"""
import hashlib
import io
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect

from tests.test_production25d_browser import production_browser
from tests.test_studio25d_archive_browser import archive_host,signed_page,record_take
from modules.recording import create_recording_service
from modules.cameras import create_default_cameras


def editor(browser,host):
    context=browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce',accept_downloads=True)
    context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(host.token)+');')
    page=context.new_page();page.goto(host.base+'/control')
    page.wait_for_function('!!window.PubCastShootAssembly')
    page.locator('.nav-btn[data-room="control"]').click();page.locator('[data-station="editor"]').click()
    page.wait_for_selector('#ed-new-project:visible')
    return context,page


def grab(page,selector,target):
    with page.expect_download() as pending:page.click(selector)
    pending.value.save_as(target)
    return target


def seek(page,t):
    page.evaluate('t=>{document.getElementById("ed-view").currentTime=t}',t)
    page.wait_for_function('t=>Math.abs(document.getElementById("ed-view").currentTime-t)<.000001',arg=t)


def test_capture_export_fresh_import_and_exact_offset_interchange(archive_host,production_browser,tmp_path):
    host=archive_host;ctx,stage=signed_page(production_browser,host)
    try:
        proof=record_take(stage)
        original=grab(stage,'#download',tmp_path/'recorded.webm')
        assert hashlib.sha256(original.read_bytes()).hexdigest()==proof['sha256']
        stage.click('#archiveSave');stage.wait_for_function("archiveStatus.textContent.startsWith('Saved on server:')",timeout=30000)
        saved=next(t for t in host.api.get('/api/studio25d/recordings',headers=host.headers).json()['takes'] if t['take_id']==proof['id'])
        response=host.api.post('/api/studio25d/recordings/'+saved['id']+'/bundle',headers=host.headers)
        assert response.status_code==200
        bundle_path=tmp_path/'source.zip';bundle_path.write_bytes(response.content)
        with ZipFile(io.BytesIO(response.content)) as bundle:
            media=[n for n in bundle.namelist() if n.startswith('media/')]
            assert len(media)==1
            assert hashlib.sha256(bundle.read(media[0])).hexdigest()==proof['sha256']
            package_names=bundle.namelist()
        fresh=create_recording_service(tmp_path/'independent-data',create_default_cameras())
        imported=fresh.import_session(bundle_path)
        source=imported.artifacts[0].file_path
        assert source.is_relative_to(fresh.recordings_dir) and hashlib.sha256(source.read_bytes()).hexdigest()==proof['sha256']
        info=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)],capture_output=True,text=True,check=True).stdout)
        video=next(s for s in info['streams'] if s['codec_type']=='video');assert [video['width'],video['height']]==[1280,720]
        report={'source_sha256':proof['sha256'],'original_preserved':True,'fresh_data_import':True,'encoded_dimensions':[video['width'],video['height']],
                'bundle_entries':package_names,'scene_master_gate':'FAIL_MISSING_SOURCE_SCENE_AND_PERFORMANCE_DEPENDENCIES',
                'native_4k_gate':'FAIL_NO_SOURCE_REPLAY_RENDER_PATH','resolve_import':'BLOCKED_APPLICATION_UNAVAILABLE','frame_rates':{}}
        ec,page=editor(production_browser,host)
        try:
            assert page.evaluate('async()=>(await PubCastEditorSyncStore.listProjects()).length')==0
            page.fill('#ed-project-title','Fresh finishing check');page.click('#ed-new-project')
            page.wait_for_function('document.getElementById("ed-status").textContent.startsWith("Saved project")')
            page.check('#ed-cache');page.set_input_files('#ed-import',str(source))
            page.wait_for_function('document.getElementById("ed-view").readyState>=1')
            seek(page,0);page.fill('#ed-marker-number','0');page.click('#ed-mark-clacker')
            page.fill('#ed-offset','0.030');page.click('#ed-apply-offset')
            seek(page,1.03);page.click('#ed-mark-in');seek(page,1.83);page.click('#ed-mark-out');page.click('#ed-add-subclip')
            for fps in (24,25,30):
                page.select_option('#ed-frame-rate',str(fps))
                handoff=json.loads(grab(page,'#ed-export',tmp_path/f'handoff-{fps}.json').read_text())
                shot=handoff['editorial']['shots'][0]
                assert shot['manualOffsetUs']==30000 and shot['sourceInUs']==1030000 and shot['sourceOutUs']==1830000,shot
                text=grab(page,'#ed-edl-export',tmp_path/f'cut-{fps}.edl').read_text()
                event=next(line for line in text.splitlines() if line.startswith('001 '))
                report['frame_rates'][str(fps)]={'event':event,'source_in_us':shot['sourceInUs'],'source_out_us':shot['sourceOutUs'],'sidecar_preserves_subframe':True,'actual_finisher_conform':'NOT_RUN'}
            unchanged=grab(page,'#ed-original',tmp_path/'unchanged-export.webm')
            assert hashlib.sha256(unchanged.read_bytes()).hexdigest()==proof['sha256']
            stored=page.evaluate('async()=>(await PubCastEditorSyncStore.listProjects())[0]')
            page.reload();page.wait_for_function('!!window.PubCastShootAssembly')
            page.locator('.nav-btn[data-room="control"]').click();page.locator('[data-station="editor"]').click()
            page.select_option('#ed-projects',stored['id'])
            page.wait_for_function('document.getElementById("ed-status").textContent.startsWith("Opened ")')
            assert page.evaluate('async id=>(await PubCastEditorSyncStore.readProject(id)).tracks[0].manualOffsetUs',stored['id'])==30000
            report['rough_cut_reload']=True
        finally:ec.close()
        (tmp_path/'readiness.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:ctx.close()


def test_relinked_source_replaces_preview_and_export_together(archive_host,production_browser,tmp_path):
    host=archive_host;ec,page=editor(production_browser,host)
    try:
        clips=[]
        for color,size,duration in [('red','320x180',3),('blue','640x360',1)]:
            path=tmp_path/(color+'.webm')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s={size}:r=30:d={duration}','-c:v','libvpx-vp9','-b:v','200k','-an',str(path)],check=True,timeout=30)
            clips.append(path)
        page.fill('#ed-project-title','Relink check');page.click('#ed-new-project')
        page.wait_for_function('document.getElementById("ed-status").textContent.startsWith("Saved project")')
        page.check('#ed-cache')
        def pick(path):page.set_input_files('#ed-import',{'name':'same-name.webm','mimeType':'video/webm','buffer':path.read_bytes()})
        pick(clips[0]);page.wait_for_function('document.getElementById("ed-view").videoWidth===320')
        pick(clips[1])
        expect(page.locator('#ed-view')).to_have_js_property('videoWidth',640)
        assert page.evaluate('document.getElementById("ed-view").duration')<1.5
        exported=grab(page,'#ed-original',tmp_path/'relinked.webm')
        assert exported.read_bytes()==clips[1].read_bytes()
    finally:ec.close()
