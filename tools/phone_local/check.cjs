// No browser rendering. Execute the real packaged scripts with all networking denied.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('jsdom');
const base=require('node:path').resolve(process.argv[2]||'dist');
const inline=process.argv[3];
function load(file,{blocked=false,copy={},audio=false}={}){
  const markup=fs.readFileSync(file,'utf8'),errors=[],network=[];
  const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(markup,{url:'https://phone-preview.test/desk',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const w=dom.window;Object.defineProperty(w,'innerWidth',{value:390,configurable:true});Object.defineProperty(w,'innerHeight',{value:844,configurable:true});
  for(const [key,value]of Object.entries(copy))w.localStorage.setItem(key,value);
  if(blocked){Object.defineProperty(w,'localStorage',{get(){throw Error('Storage unavailable in this view');}});Object.defineProperty(w,'sessionStorage',{get(){throw Error('Storage unavailable in this view');}});}
  w.fetch=(...args)=>{network.push(args);throw Error('Forbidden network attempt');};w.confirm=()=>true;w.prompt=()=>null;
  w.requestAnimationFrame=()=>0;w.cancelAnimationFrame=()=>{};
  if(audio){
    w.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
    w.speechSynthesis={calls:[],current:null,addEventListener(){},getVoices:()=>[{name:'Test phone voice',voiceURI:'test-phone',lang:'en-US',localService:true}],resume(){},
      cancel(){const old=this.current;this.current=null;old?.onerror?.({error:'canceled'});},
      speak(u){this.calls.push(u);this.current=u;u.onstart?.();}};
  }
  const context=dom.getInternalVMContext();
  for(const m of markup.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(m[1],context);
  assert.equal(w.document.querySelectorAll('[onclick]').length,0);
  return {w,errors,network,run:s=>vm.runInContext(s,context),click:id=>w.document.getElementById(id).click()};
}
const pause=()=>new Promise(r=>setTimeout(r,20));
(async()=>{
  for(const file of [base+'/Reach_Phone_Standalone.html',inline].filter(Boolean)){
    let h=load(file);await h.w.reachLocalReady;await h.w.reachDeskReady;
    assert.equal(h.w.reachPhone.active,true);assert.equal(h.w.document.getElementById('reachAccount').classList.contains('open'),false);
    h.run("soloTextarea.value='A page written on my phone.\\n\\n  Exact spaces.  ';soloTextarea.dispatchEvent(new Event('input'));");
    h.click('saveBtn');await pause();assert.match(h.w.document.getElementById('saveIndicator').textContent,/Saved in this browser/);
    const copy=Object.fromEntries(Object.keys(h.w.localStorage).map(k=>[k,h.w.localStorage.getItem(k)]));h.w.close();h=load(file,{copy});await h.w.reachLocalReady;await h.w.reachDeskReady;
    assert.equal(h.w.document.getElementById('soloTextarea').value,'A page written on my phone.\n\n  Exact spaces.  ');
    h.click('phoneTab_partner');h.w.document.getElementById('chatInput').value='Is Alex connected?';h.click('chatSendBtn');await pause();
    assert.equal(h.run('chatHistory.length'),0);assert.equal(h.w.document.getElementById('chatInput').value,'Is Alex connected?');
    assert.match(h.w.document.getElementById('chatLog').textContent,/not connected/);
    h.click('sidebarToggle');assert(h.w.document.getElementById('deskSettings').classList.contains('open'));h.click('deskModelSettings');assert(h.w.document.getElementById('phoneLocalInfo').classList.contains('open'));h.run("closeModal('phoneLocalInfo')");
    h.click('phoneTab_archive');h.run("addReference('Phone note','notes','Words to keep.');");h.click('photoRefNotes');
    assert.match(h.w.document.getElementById('refListContainer').textContent,/Phone note/);
    h.w.document.querySelector('#refListContainer button[title=View]').click();assert.equal(h.w.reachPhone.panel,'write');h.run('closeRefViewer()');
    h.click('phoneShelf');await pause();assert(h.w.document.querySelector('#reachShelfList [data-source=browser]'));h.run("closeModal('reachShelf')");
    h.click('exportBtn');await pause();assert.match(h.w.document.getElementById('phoneLocalExportText').value,/Exact spaces/);h.run("closeModal('phoneLocalExport')");
    h.click('hmSaveAs');await pause();const doc=JSON.parse(h.w.document.getElementById('phoneLocalExportText').value);assert.equal(doc.format,'2i-document');assert.equal(doc.state.committed[2],'  Exact spaces.  ');
    assert.equal(h.network.length,0);assert.deepEqual(h.errors,[]);h.w.close();
    console.log('PASS: '+file.split('/').pop()+' boots without requests, saves/restores exact text, opens archive/shelf/settings, exports real content, and never impersonates a live partner');
    h=load(file,{blocked:true});await h.w.reachLocalReady;await h.w.reachDeskReady;h.run("soloTextarea.value='Temporary words';soloTextarea.dispatchEvent(new Event('input'));");h.click('saveBtn');await pause();
    assert.match(h.w.document.getElementById('saveIndicator').textContent,/open view only/);
    h.click('phoneShelf');await pause();assert(h.w.document.querySelector('#reachShelfList button'));h.run("closeModal('reachShelf')");
    h.click('hmSaveAs');await pause();assert.equal(JSON.parse(h.w.document.getElementById('phoneLocalExportText').value).state.committed[0],'Temporary words');
    assert.equal(h.network.length,0);assert.deepEqual(h.errors,[]);h.w.close();
    console.log('PASS: unavailable browser storage is labeled temporary; shelf and copy/export remain usable');
    h=load(file,{audio:true});await h.w.reachDeskReady;
    h.run("soloTextarea.value='First paragraph with one two three four five six seven eight nine ten eleven twelve thirteen.\\n\\nSecond paragraph.';soloTextarea.dispatchEvent(new Event('input'));");
    h.run('writeRecovery()');const beforeReading=h.run('JSON.stringify(getDocState())');
    for(const id of ['readerRead','readerPlay','readerStop','readerPrevious','readerNext','readerBack','readerForward','deskShrink','deskClose']){
      const node=h.w.document.getElementById(id);assert(node);assert.equal(typeof node.onclick,'function');assert(Number.parseFloat(h.w.getComputedStyle(node).minHeight)>=48,id);
    }
    h.click('readerRead');assert(h.w.speechSynthesis.current.text.startsWith('First paragraph'));assert.equal(h.w.document.getElementById('readerPlay').textContent,'Pause');
    h.click('readerPlay');assert.equal(h.w.reachReader.phase,'paused');h.click('readerPlay');assert.equal(h.w.reachReader.phase,'reading');
    h.click('readerNext');assert.equal(h.w.speechSynthesis.current.text,'Second paragraph.');h.click('readerPrevious');assert(h.w.speechSynthesis.current.text.startsWith('First paragraph'));
    h.click('readerForward');assert(h.w.reachReader.offset>0);h.click('readerBack');assert.equal(h.w.reachReader.offset,0);
    const speed=h.w.document.getElementById('readerRate');speed.value='1.5';speed.dispatchEvent(new h.w.Event('change'));assert.equal(h.w.speechSynthesis.current.rate,1.5);
    h.click('readerStop');assert.equal(h.w.reachReader.phase,'idle');assert.equal(h.run('JSON.stringify(getDocState())'),beforeReading);
    h.click('sidebarToggle');assert(h.w.document.getElementById('deskSettings').classList.contains('open'));
    const size=h.w.document.getElementById('deskTextSize');size.value='22';size.dispatchEvent(new h.w.Event('change'));assert.equal(h.w.document.documentElement.style.getPropertyValue('--reach-manuscript-size'),'22px');h.click('deskSettingsClose');
    h.click('deskShrink');assert.equal(h.w.reachDesk.collapsed,true);assert.equal(h.w.document.body.dataset.deskState,'collapsed');assert.equal(h.w.document.getElementById('deskShrink').textContent,'□');
    h.click('deskMiniPlay');assert.equal(h.w.reachReader.phase,'reading');h.click('deskMiniStop');assert.equal(h.w.reachReader.phase,'idle');h.click('deskShrink');assert.equal(h.w.reachDesk.collapsed,false);
    h.click('readerRead');h.click('deskClose');await pause();assert.equal(h.w.reachDesk.closed,true);assert.equal(h.w.reachReader.phase,'idle');assert.equal(h.w.document.getElementById('reachDeskDock').hidden,false);
    h.click('deskReopen');assert.equal(h.w.reachDesk.closed,false);assert.equal(h.run('JSON.stringify(getDocState())'),beforeReading);
    h.click('deskShrink');h.w.reachPhone.setView(false);assert.equal(h.w.reachDesk.collapsed,false);assert.equal(h.w.document.body.dataset.deskState,undefined);
    h.w.reachPhone.setView(true);assert(h.w.document.getElementById('phoneRoom').contains(h.w.document.getElementById('reachAudio')));
    assert.equal(h.network.length,0);assert.deepEqual(h.errors,[]);h.w.close();
    console.log('PASS: visible audio buttons control the selected text; settings/shrink/restore/close/reopen preserve the manuscript');
    h=load(file);await h.w.reachDeskReady;
    h.run("soloTextarea.value='Test text';soloTextarea.dispatchEvent(new Event('input'));");h.click('readerRead');assert.match(h.w.document.getElementById('readerStatus').textContent,/unavailable/);
    h.click('phoneTab_archive');h.run("addReference('One note','notes','Note text');addReference('One map','research','Map text');");h.click('photoRefNotes');assert.equal(h.w.document.querySelectorAll('#refListContainer .ref-item').length,1);
    h.w.document.querySelector('#refListContainer button[title=View]').click();h.w.document.querySelector('[data-close-reference]').click();assert(!h.w.document.getElementById('refViewer').classList.contains('open'));
    h.click('phoneTab_archive');h.w.document.querySelector('#refListContainer button[title=Delete]').click();h.click('refDeleteConfirm');assert.equal(h.run('references.length'),1);
    h.click('addRefBtn');h.w.document.querySelector('[data-close-modal=addRefModalBackdrop]').click();assert.equal(h.w.document.querySelector('.app-shell').inert,false);
    assert.equal(h.network.length,0);assert.deepEqual(h.errors,[]);h.w.close();
    console.log('PASS: missing audio is reported; filters, reference Back/Delete and dialog Close work with inline handlers disabled');
  }
})().catch(e=>{console.error(e);process.exit(1);});
