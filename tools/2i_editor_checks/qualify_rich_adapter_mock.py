from pathlib import Path
from playwright.sync_api import sync_playwright
import json
import os
import shutil

# Real Chromium DOM/input behavior with a mock of the pinned engine contract.
# This does not test DOCX parsing, rendering, or actual formatting fidelity.
source = Path(__file__).resolve().parents[2] / '2i/2i-assets/rich-editor.js'
html = '''<!doctype html><html><body><main id="test"></main><script type="module">
const {mountRichEditor}=await import(window.adapterModuleUrl);
window.checks=[];window.result={};
window.assertCheck=(name,condition)=>{checks.push({name,passed:!!condition});if(!condition)throw Error(name)};
window.state={changes:0,saves:0,errors:0,destroys:0,exec:[],fonts:[],listeners:{},badBytes:false,editable:true};
const host=document.getElementById('test');
const engine={async loadFonts({sources}){state.fonts=sources;return {failures:[]}},createDocxEditor({container,document:bytes}){state.inputBytes=Array.from(bytes);const input=document.createElement('div');input.contentEditable='true';input.textContent='Mock editing surface';container.append(input);return {snapshot:()=>({isLoading:false,isOpening:false,editable:state.editable,parseError:null,page:{current:2,total:4}}),can:cmd=>({ok:cmd.type!=='redo'}),exec:cmd=>{state.exec.push(cmd.type);state.listeners.change?.({revision:1});return {ok:true}},focus:()=>input.focus(),on:(event,cb)=>{state.listeners[event]=cb;return()=>{delete state.listeners[event]}},save:async()=>new Uint8Array(state.badBytes?[1,2,3]:[80,75,3,4,99]).buffer,destroy:()=>state.destroys++}}};
window.mount=async(overrides={})=>mountRichEditor({container:host,bytes:new Uint8Array([80,75,3,4,42]),loadRuntime:async()=>engine,ensureStyle:async()=>{},onChange:()=>state.changes++,onSave:()=>state.saves++,onError:()=>state.errors++,...overrides});
window.setup=async()=>{window.session=await mount();assertCheck('exact input bytes',state.inputBytes.join(',')==='80,75,3,4,42');assertCheck('12 local fonts',state.fonts.length===12&&state.fonts.every(f=>f.url.startsWith('/2i-assets/vendor/docx/fonts/')));assertCheck('page state visible',host.textContent.includes('Page 2 of 4'));assertCheck('mount does not dirty',state.changes===0);};
window.finish=async()=>{assertCheck('bold click dispatches once',state.exec.join(',')==='toggleBold'&&state.changes===1);state.listeners.change({source:'load'});state.listeners.change({source:'refresh'});state.listeners.change({source:'recovery'});assertCheck('replacement events not dirty',state.changes===1);state.listeners.error(Error('engine error'));assertCheck('engine error dispatched',state.errors===1);assertCheck('saved bytes exact',Array.from(await session.saveBytes()).join(',')==='80,75,3,4,99');state.badBytes=true;let bad=false;try{await session.saveBytes()}catch{bad=true}assertCheck('invalid save rejected',bad);session.destroy();session.destroy();assertCheck('destroy idempotent',state.destroys===1&&Object.keys(state.listeners).length===0&&host.children.length===0);let closed=false;try{await session.saveBytes()}catch{closed=true}assertCheck('closed save rejected',closed);let missing=false;try{await mount({loadRuntime:async()=>{throw Error('missing runtime')}})}catch{missing=true}assertCheck('missing engine leaves no surface',missing&&host.children.length===0);let fonts=false;try{await mount({loadRuntime:async()=>({...engine,loadFonts:async()=>({failures:['missing']})})})}catch{fonts=true}assertCheck('missing fonts leaves no surface',fonts&&host.children.length===0);state.editable=false;let readOnly=false;try{await mount()}catch{readOnly=true}assertCheck('read-only engine destroys provisional surface',readOnly&&state.destroys===2&&host.children.length===0);};
window.ready=true;
</script></body></html>'''
with sync_playwright() as p:
    binary = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
    options = {'executable_path':binary} if binary else {}
    browser=p.chromium.launch(args=['--no-sandbox','--disable-dev-shm-usage'],**options)
    result=[]
    for viewport in ({'width':1200,'height':900},{'width':390,'height':844}):
        page=browser.new_page(viewport=viewport)
        requests=[];errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            requests.append(r.request.url)
            r.abort()
        page.route('**/*',route)
        page.evaluate("src=>{window.adapterModuleUrl=URL.createObjectURL(new Blob([src],{type:'text/javascript'}))}",source.read_text())
        page.set_content(html)
        page.wait_for_function('window.ready===true')
        page.evaluate('setup()')
        assert page.get_by_role('button',name='Redo').is_disabled()
        page.get_by_role('button',name='Bold').click()
        page.get_by_role('button',name='Save working copy').click()
        page.wait_for_function('state.saves===1')
        page.locator('[contenteditable=true]').focus()
        page.keyboard.press('Control+s')
        page.wait_for_function('state.saves===2')
        page.evaluate('finish()')
        checks=page.evaluate('checks')
        assert not requests, requests
        assert not errors, errors
        result.append({'viewport':viewport,'checks':checks,'browser_controls':['disabled redo','real button click','save button','Ctrl+S shortcut','no unexpected requests','no page exceptions']})
        page.close()
    browser.close()
print(json.dumps(result,ensure_ascii=False,indent=2))
