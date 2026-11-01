// Hermetic DOM/state tests, not a browser rendering or live model test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM, VirtualConsole} = require('jsdom');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root,'2i/index.html'),'utf8');
// Separate script evaluations preserve real classic-script declaration order.
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).concat(['button-bindings.js','reach.js','artwork.js','phone.js','reader.js','desk-controls.js'].map(file=>fs.readFileSync(path.join(root,'2i/2i-assets',file),'utf8')));
const hotspotMap=JSON.parse(fs.readFileSync(path.join(root,'2i/2i-assets/hotspots.json'),'utf8'));
const documents = new Map();
let requests=[], failProvider=false;
const clickedHotspots=new Set();
const pause=()=>new Promise(resolve=>setTimeout(resolve,30));
function harness(storage={},settings={}) {
  const errors=[];
  const vc=new VirtualConsole(); vc.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(html,{url:settings.url||'http://reach.test/writers-room',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const w=dom.window, context=dom.getInternalVMContext();
  if(settings.width)Object.defineProperty(w,'innerWidth',{value:settings.width,configurable:true});
  if(settings.height)Object.defineProperty(w,'innerHeight',{value:settings.height,configurable:true});
  for(const file of ['reach.css','artwork.css','phone.css','reader.css']) {const style=w.document.createElement('style');style.textContent=fs.readFileSync(path.join(root,'2i/2i-assets',file),'utf8');w.document.head.append(style);}
  w.document.addEventListener('click',event=>{const target=event.target.closest('[data-hotspot]');if(target)clickedHotspots.add(target.id);},true);
  for(const [key,value] of Object.entries(storage))w.localStorage.setItem(key,value);
  w.requestAnimationFrame=()=>0; w.cancelAnimationFrame=()=>{}; w.confirm=()=>true;w.prompt=()=> '24000';
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({}, {get:(_,key)=>key==='createLinearGradient'||key==='createRadialGradient'?()=>({addColorStop(){}}):()=>{}});
  const downloads=[];w.Blob=Blob;
  w.URL.createObjectURL=blob=>{downloads.push(blob);return 'blob:test';}; w.URL.revokeObjectURL=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){};
  w.fetch=async(url,options={})=>{
    const p=new URL(url,'http://reach.test').pathname, body=options.body?JSON.parse(options.body):null;
    let value={},status=200;
    if(p==='/2i-assets/hotspots.json')value=hotspotMap;
    else if(p==='/api/auth/status')value={auth_enforced:false,setup_required:false};
    else if(p==='/api/writers-room/config')value={user_id:'test-author',provider:{provider:'ollama',model:'test-only'}};
    else if(p==='/api/pubpartner/profiles/friend')value={profiles:[{id:'alex',display_name:'Alex'},{id:'craig',display_name:'Craig'}]};
    else if(p==='/api/pubpartner/providers/status')value={available:true,provider:'ollama'};
    else if(p==='/api/pubpartner/turns/live'){
      requests.push(body);
      if(failProvider){status=503;value={ok:false,provider_result:{ok:false,error:'synthetic unavailable provider'}};}
      else value={ok:true,reply:'Synthetic test reply',provider_result:{ok:true,provider:'ollama',model:'test-only'}};
    } else if(p.startsWith('/api/writers-room/documents/')) {
      if(settings.failDocuments)throw Error('Synthetic disconnected document service');
      if(settings.holdNextPut&&options.method==='PUT'){settings.holdNextPut=false;await new Promise(resolve=>settings.releasePut=resolve);}
      const id=p.split('/').pop(), old=documents.get(id);
      if(options.method==='PUT') {
        if((old?.revision||0)!==body.expected_revision){status=409;value={detail:{message:'Revision conflict'}};}
        else {value={...body,id,revision:(old?.revision||0)+1,updated:Date.now()/1000};documents.set(id,value);}
      } else if(old)value=old;else{status=404;value={detail:'document not found'};}
    } else if(p==='/api/writers-room/documents'){
      if(settings.failDocuments)throw Error('Synthetic disconnected document service');
      value={documents:[...documents.values()]};
    }
    else throw Error('Unhandled fake API path: '+p);
    return {ok:status<400,status,json:async()=>value};
  };
  for(const script of scripts)vm.runInContext(script,context);
  // Production bindings must work with inline HTML event handlers disabled.
  return {dom,w,errors,downloads,run:script=>vm.runInContext(script,context),storage:()=>Object.fromEntries(Object.keys(w.localStorage).map(k=>[k,w.localStorage.getItem(k)]))};
}
const deadline=setTimeout(()=>{console.error('FAIL: editor test did not finish');process.exit(1);},30000);
(async()=>{
  let h=harness(); await pause();
  await h.w.reachArtworkReady;
  assert.equal(h.w.document.querySelector('.app-shell').dataset.artworkReady,'true');
  for(const control of hotspotMap.controls){
    const button=h.w.document.getElementById(control.id);
    assert.equal(typeof button.onclick,'function',control.id);
    assert.equal(button.style.left,control.bounds[0]+'px');
    assert(button.getAttribute('aria-label'));
  }
  const {createHash}=require('node:crypto');
  assert.equal(createHash('sha256').update(fs.readFileSync(path.join(root,'2i/2i-assets/writers-room-art.webp'))).digest('hex'),hotspotMap.image.sha256);
  const x=h.w.document.getElementById('saveBtn').style.left;
  Object.defineProperty(h.w,'innerWidth',{value:672,configurable:true});Object.defineProperty(h.w,'innerHeight',{value:448,configurable:true});
  h.w.dispatchEvent(new h.w.Event('resize'));
  assert.equal(h.w.document.querySelector('.app-shell').style.getPropertyValue('--art-scale'),'0.5');
  assert.equal(h.w.document.getElementById('saveBtn').style.left,x);
  console.log('PASS: original image hash, labeled button map and shared scaling');
  h.run(String.raw`soloTextarea.value='A lantern glowed.\n\n  Keep these spaces.  '; soloTextarea.dispatchEvent(new Event('input'));`);
  await h.run('saveDocument()');
  assert.equal(h.run('documentDirty'),false);
  assert.match(h.w.document.getElementById('wordCount').textContent,/6 words/);
  const id=h.run('documentId');
  assert.equal(documents.get(id).state.committed[2],'  Keep these spaces.  ');
  h.run(`documentTitle='The Lantern'; addReference('Harbor map','research','An invented shore.'); markDirty();`);
  await h.run('saveDocument()');
  const saved=h.storage();h.dom.window.close();
  h=harness(saved);await pause();
  assert.equal(h.w.document.getElementById('soloTextarea').value,'A lantern glowed.\n\n  Keep these spaces.  ');
  assert.equal(h.w.document.getElementById('paperTitle').textContent,'The Lantern');
  assert.equal(h.run('references[0].content'),'An invented shore.');
  console.log('PASS: words, title and references survive save and reload');

  h.run(`$('chatInput').value='The harbor is Lumen.';`);await h.run('sendChat()');
  h.run(`$('partnerSelect').value='craig';`);await h.run('switchPartner()');
  assert.equal(h.run('chatHistory.length'),0);
  h.run(`$('chatInput').value='Craig, help me with this scene.';`);await h.run('sendChat()');
  assert.equal(requests.at(-1).friend,'craig');
  assert.equal(requests.at(-1).messages.length,1);
  assert(!JSON.stringify(requests.at(-1).messages).includes('The harbor is Lumen.'));
  assert.equal(requests.at(-1).allow_fallback,false);
  assert(requests.at(-1).task.manuscript_context.includes('Keep these spaces.'));
  h.run(`$('partnerSelect').value='alex';`);await h.run('switchPartner()');
  assert.equal(h.run('chatHistory[0].content'),'The harbor is Lumen.');
  h.run(`$('chatInput').value='Keep that name.';`);await h.run('sendChat()');
  assert.equal(requests.at(-1).messages.length,3);
  console.log('PASS: partner changes isolate conversations; full history reaches the adapter');

  failProvider=true;
  const count=h.run('chatHistory.length');
  h.run(`$('chatInput').value='Try again.';`);await h.run('sendChat()');
  assert.equal(h.run('chatHistory.length'),count+1);
  assert.match(h.w.document.getElementById('chatLog').textContent,/reply was not confirmed: synthetic unavailable provider/);
  assert.equal(h.w.document.getElementById('chatSendBtn').disabled,false);
  console.log('PASS: unavailable model displays an error without inventing an assistant turn');

  h.run('lockAll()');
  assert.equal(h.run('coWriting'),true);
  h.run('toggleMode()');assert.equal(h.run('coWriting'),true);
  h.run(`$('frFind').value='lantern';$('frReplace').value='candle';$('frReplaceAllBtn').click();`);
  assert.equal(h.run('committed[0]'),'A lantern glowed.');
  assert.match(h.w.document.getElementById('frResult').textContent,/0 replacements/);
  console.log('PASS: locked manuscript text resists free editing and replace-all');

  const lockedWords=h.run('JSON.stringify(committed)');
  h.w.document.getElementById('photoInsert').click();
  assert.equal(h.run('JSON.stringify(committed)'),lockedWords);
  assert.equal(h.run('buffer.at(-1)'),'Synthetic test reply');
  assert.equal(h.w.document.getElementById('photoInsert').disabled,true);
  h.w.document.getElementById('photoCommitMenu').click();
  assert.equal(h.run('committed.at(-1)'),'Synthetic test reply');
  h.w.document.getElementById('photoCharacters').click();
  assert(h.w.document.getElementById('photoCollection').classList.contains('open'));
  assert.equal(h.w.document.getElementById('photoCollectionTitle').textContent,'Characters');
  h.run(`addReference('Meet at the dock','idea','A scene premise.');`);
  assert.match(h.w.document.getElementById('photoIdeas').textContent,/Meet at the dock/);
  h.w.document.getElementById('newChapterBtn').click();
  h.w.document.getElementById('photoSceneTitleInput').value='Chapter Two';
  h.w.document.getElementById('photoSceneSave').click();
  assert.equal(h.w.document.getElementById('photoSceneCount').textContent,'SCENE 2 OF 2');
  h.w.document.getElementById('photoPrevious').click();
  assert.equal(h.w.document.getElementById('photoSceneCount').textContent,'SCENE 1 OF 2');
  assert.equal(h.run('committed[0]'),'A lantern glowed.');
  console.log('PASS: image hotspots insert to draft, commit, open collections and navigate scenes');

  const before=h.run('JSON.stringify(getDocState())');
  await assert.rejects(h.run(`importDocument({text:async()=>JSON.stringify({format:'2i-document',version:4,title:'Bad import',state:{committed:'broken'}})})`));
  assert.equal(h.run('JSON.stringify(getDocState())'),before);
  console.log('PASS: malformed import leaves the manuscript intact');

  h.run(`addReference('Literal markup','<img src=x onerror=alert(1)>','<b>A fictional reference</b>');`);
  assert.equal(h.w.document.querySelector('#refListContainer img'),null);
  assert.match(h.w.document.getElementById('refListContainer').textContent,/<img src=x/);
  console.log('PASS: imported reference metadata stays inert text');

  await h.run('saveDocument()');
  const current=documents.get(h.run('documentId'));current.revision++;
  h.run(`documentTitle='A simultaneous edit';markDirty();`);await h.run('saveDocument()');
  assert.equal(h.run('saveConflict'),true);
  assert.notEqual(documents.get(h.run('documentId')).title,'A simultaneous edit');
  assert.match(h.w.document.getElementById('saveIndicator').textContent,/Changed elsewhere/);
  assert.equal(h.errors.filter(e=>!e.includes('indexedDB')).length,0,h.errors.join('\n'));
  h.dom.window.close();
  console.log('PASS: stale revision protects the server copy');

  failProvider=false;h=harness();await h.w.reachStarted;await h.w.reachArtworkReady;
  const click=id=>h.w.document.getElementById(id).click();
  click('photoManuscript');assert.equal(h.w.document.activeElement.id,'soloTextarea');
  click('modeBadge');assert.equal(h.run('coWriting'),true);click('modeBadge');assert.equal(h.run('coWriting'),false);
  click('menuToggle');assert(h.w.document.getElementById('hamburgerMenu').classList.contains('open'));
  click('sidebarToggle');assert(h.w.document.getElementById('deskSettings').classList.contains('open'));click('deskModelSettings');assert(h.w.document.getElementById('llmModalBackdrop').classList.contains('open'));
  assert.equal(h.w.document.querySelector('.app-shell').inert,true);
  assert.equal(h.w.getComputedStyle(h.w.document.getElementById('reachModel')).backgroundColor,'rgb(25, 20, 14)');
  click('llmTestBtn');await pause();assert.match(h.w.document.getElementById('llmTestResult').textContent,/Service configured/);
  click('llmSaveBtn');await pause();assert(!h.w.document.getElementById('llmModalBackdrop').classList.contains('open'));
  assert.equal(h.w.document.querySelector('.app-shell').inert,false);
  click('sidebarToggle');h.w.document.dispatchEvent(new h.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.equal(h.w.document.querySelector('.app-shell').inert,false);
  h.run(`soloTextarea.value='Scene one.\\n';soloTextarea.dispatchEvent(new Event('input'));addReference('Chapter sketch','chapter','A chapter.');addReference('Harbor map','research','A shore.');addReference('Quill notes','notes','A quill.');addReference('Mara','character','A mariner.');addReference('The islands','worldbuilding','An invented world.');`);
  for(const [id,title] of [['photoCharacters','Characters'],['photoWorldbuilding','Worldbuilding'],['photoNotes','Notes']]) {
    click(id);assert.equal(h.w.document.getElementById('photoCollectionTitle').textContent,title);click('photoCollectionClose');
  }
  for(const [id,name] of [['photoRefChapter','Chapter sketch'],['photoRefResearch','Harbor map'],['photoRefNotes','Quill notes']]) {
    click(id);const rows=h.w.document.querySelectorAll('#refListContainer .ref-item');assert.equal(rows.length,1);assert(rows[0].textContent.includes(name));
  }
  click('photoRefAll');assert.equal(h.w.document.querySelectorAll('#refListContainer .ref-item').length,5);
  h.w.document.getElementById('refSearchInput').value='quill';click('photoSearch');
  assert.equal(h.w.document.querySelectorAll('#refListContainer .ref-item').length,1);
  assert.match(h.w.document.getElementById('refListContainer').textContent,/Quill notes/);
  h.w.document.getElementById('refSearchInput').value='';click('photoSearch');
  click('addRefBtn');h.w.document.getElementById('refNameInput').value='Added through the picture';h.w.document.getElementById('refContentInput').value='Preserved reference';click('addRefSaveBtn');
  assert(h.run(`references.some(r=>r.name==='Added through the picture')`));
  click('photoAddIdea');assert.equal(h.w.document.getElementById('refTypeInput').value,'idea');
  h.w.document.getElementById('refNameInput').value='The return';h.w.document.getElementById('refContentInput').value='Return to the harbor.';click('addRefSaveBtn');
  h.w.document.querySelector('#photoIdeas button').click();assert.equal(h.w.document.getElementById('refViewerTitle').textContent,'The return');
  click('photoManuscript');assert(!h.w.document.getElementById('refViewer').classList.contains('open'));
  click('photoAllIdeas');assert.equal(h.w.document.getElementById('photoCollectionTitle').textContent,'Scene ideas');click('photoCollectionClose');
  click('newChapterBtn');h.w.document.getElementById('photoSceneTitleInput').value='Second scene';click('photoSceneSave');
  h.run(`soloTextarea.value+='Second scene words.';soloTextarea.dispatchEvent(new Event('input'));`);
  click('photoPrevious');assert.equal(h.run('photoScene'),0);
  click('photoNext');assert.equal(h.run('photoScene'),1);
  click('photoOutline');assert.equal(h.w.document.querySelectorAll('#photoCollectionBody button').length,2);
  h.w.document.querySelector('#photoCollectionBody button').click();assert.equal(h.run('photoScene'),0);
  h.run(`soloTextarea.value=soloTextarea.value.replace('Scene one.','First line.\\nExtra line.');soloTextarea.dispatchEvent(new Event('input'));`);
  assert.equal(h.run('chapters[1].startLine'),2);
  click('photoNext');assert.equal(h.w.document.getElementById('soloTextarea').selectionStart,h.run(`soloTextarea.value.indexOf('Second scene words.')`));
  click('lockSceneBtn');assert(h.run('lockedLines.has(2)'));assert(!h.run('lockedLines.has(0)'));
  click('lockSceneBtn');assert.equal(h.run('lockedLines.size'),0);
  click('photoLockMode');assert(h.w.document.getElementById('photoLockOptions').classList.contains('open'));
  h.w.document.querySelector('#photoLockOptionsBody button').click();assert.equal(h.run('coWriting'),false);
  h.w.document.getElementById('chatInput').value='Suggest a line.';click('chatSendBtn');await pause();assert.equal(h.run('chatHistory.length'),2);
  click('photoDismiss');assert.equal(h.w.document.getElementById('photoInsert').disabled,true);
  h.w.document.getElementById('chatInput').value='One more.';click('chatSendBtn');await pause();click('photoInsert');assert.equal(h.run('buffer.at(-1)'),'Synthetic test reply');
  click('saveBtn');await h.run('saveDocument()');assert.equal(h.run('documentDirty'),false);
  click('exportBtn');assert.match(await h.downloads.at(-1).text(),/Second scene words/);
  click('hmSaveAs');const exported=JSON.parse(await h.downloads.at(-1).text());assert.equal(exported.format,'2i-document');assert.equal(exported.state.buffer.at(-1),'Synthetic test reply');
  const priorLeft=h.w.document.getElementById('saveBtn').style.left;
  click('photoHotspotMenu');assert(h.w.document.querySelector('.app-shell').classList.contains('show-hotspots'));
  assert.equal(h.w.document.getElementById('saveBtn').style.left,priorLeft);
  click('photoFullSizeMenu');assert.equal(h.w.getComputedStyle(h.w.document.querySelector('.app-shell')).transform,'none');click('photoFullSizeMenu');
  for(const control of hotspotMap.controls) {
    const computed=h.w.getComputedStyle(h.w.document.getElementById(control.id));
    assert.notEqual(computed.display,'none',control.id);assert.equal(computed.position,'absolute',control.id);
    assert(clickedHotspots.has(control.id),'Control was not clicked: '+control.id);
  }
  assert.equal(h.errors.length,0,h.errors.join('\n'));h.w.close();
  console.log('PASS: all '+hotspotMap.controls.length+' pictured controls clicked, with navigation, settings, search, archive, locks, chat, draft, save and exports checked');
  console.log('PASS: chapter destinations follow edits made before them; clickable-area display preserves coordinates');

  const timing={holdNextPut:true};h=harness({},timing);await h.w.reachStarted;await h.w.reachArtworkReady;
  h.run(`soloTextarea.value='Before edit';soloTextarea.dispatchEvent(new Event('input'));`);
  const originalId=h.run('documentId'),firstSave=h.run('saveDocument()');await pause();assert.equal(typeof timing.releasePut,'function');
  h.run(`soloTextarea.value='Latest edit made during saving';soloTextarea.dispatchEvent(new Event('input'));`);
  const switchDocument=h.run('newDocument()');timing.releasePut();await firstSave;await switchDocument;
  assert.equal(documents.get(originalId).state.committed[0],'Latest edit made during saving');
  assert.notEqual(h.run('documentId'),originalId);
  console.log('PASS: switching manuscripts waits for edits made while a save was in progress');
  timing.failDocuments=true;
  h.run(`soloTextarea.value='Offline manuscript A';soloTextarea.dispatchEvent(new Event('input'));`);await h.run('saveDocument()');
  const offlineA=h.run('documentId');await h.run('newDocument()');
  h.run(`soloTextarea.value='Offline manuscript B';soloTextarea.dispatchEvent(new Event('input'));`);await h.run('saveDocument()');
  const offlineB=h.run('documentId');await h.run('showShelf()');
  const recovery=h.w.document.querySelector('#reachShelfList button[data-document-id="'+offlineA+'"][data-source="browser"]');assert(recovery);recovery.click();await pause();
  assert.equal(h.run('documentId'),offlineA);assert.equal(h.w.document.getElementById('soloTextarea').value,'Offline manuscript A');
  assert.equal(h.run(`stored(RECOVERY_KEY+':'+${JSON.stringify(offlineB)},null).state.committed[0]`),'Offline manuscript B');
  const recoveryStorage=h.storage();h.w.close();h=harness(recoveryStorage,timing);await h.w.reachStarted;await h.w.reachArtworkReady;
  assert.equal(h.w.document.getElementById('soloTextarea').value,'Offline manuscript A');assert.equal(h.errors.length,0,h.errors.join('\n'));h.w.close();
  console.log('PASS: offline manuscript copies remain separately recoverable through switching and reload');

  h=harness({}, {url:'http://reach.test/writers-room?view=phone',width:390,height:844});
  await h.w.reachStarted;await h.w.reachPhoneReady;
  const phone=h.w.reachPhone,phoneClick=id=>h.w.document.getElementById(id).click();
  assert.equal(phone.active,true);assert.equal(phone.panel,'write');
  assert.equal(h.w.document.getElementById('phonePanel_partner').hidden,true);
  const phoneEditor=h.w.document.getElementById('soloTextarea');
  h.run(`soloTextarea.value='Written on a phone.\\n  Keep my spaces.  ';soloTextarea.dispatchEvent(new Event('input'));`);
  const phoneId=h.run('documentId');
  for(const control of hotspotMap.controls){
    const node=h.w.document.getElementById(control.id),style=h.w.getComputedStyle(node);
    assert(h.w.document.getElementById('phoneRoom').contains(node),control.id);
    assert.equal(h.w.document.querySelectorAll('#'+control.id).length,1,control.id);
    assert.equal(typeof node.onclick,'function',control.id);
    assert.equal(style.position,'static',control.id);
    assert(Number.parseFloat(style.minHeight)>=48,control.id+' must be touch-sized');
    assert(node.textContent.trim(),control.id+' needs a visible phone caption');
  }
  assert.equal(h.w.getComputedStyle(phoneEditor).fontSize,'var(--reach-manuscript-size,18px)');
  assert.equal(h.w.document.documentElement.style.getPropertyValue('--reach-manuscript-size'),'18px');
  phoneClick('saveBtn');await h.run('saveDocument()');assert.equal(documents.get(phoneId).state.committed[1],'  Keep my spaces.  ');
  phoneClick('phoneTab_partner');assert.equal(phone.panel,'partner');
  h.w.document.getElementById('chatInput').value='A fictional scene suggestion, please.';phoneClick('chatSendBtn');await pause();
  assert.equal(h.run('chatHistory.at(-1).content'),'Synthetic test reply');
  phoneClick('photoInsert');assert.equal(phone.panel,'write');assert.equal(h.w.document.activeElement.id,'draftArea');
  assert.equal(h.run('buffer.at(-1)'),'Synthetic test reply');phoneClick('phoneCommit');assert.equal(h.run('committed.at(-1)'),'Synthetic test reply');
  console.log('PASS: phone view reuses all 26 controls with readable captions, 48px minimum heights, writing, save and partner-to-draft actions');

  phoneClick('phoneTab_archive');assert.equal(phone.panel,'archive');
  h.run(`addReference('Phone research','research','Saved from my phone.');`);
  h.w.document.getElementById('refSearchInput').value='phone';phoneClick('photoSearch');
  assert.match(h.w.document.getElementById('refListContainer').textContent,/Phone research/);
  h.w.document.querySelector('#refListContainer .ref-action-btn[title="View"]').click();
  assert.equal(phone.panel,'write');assert.equal(h.w.document.getElementById('refViewerBody').textContent,'Saved from my phone.');h.run('closeRefViewer()');
  phoneClick('sidebarToggle');assert(h.w.document.getElementById('deskSettings').classList.contains('open'));phoneClick('deskModelSettings');assert(h.w.document.getElementById('llmModalBackdrop').classList.contains('open'));
  assert.equal(h.w.document.querySelector('.app-shell').inert,true);h.run("closeModal('llmModalBackdrop')");assert.equal(h.w.document.querySelector('.app-shell').inert,false);
  const wordsBeforeSwitch=h.run('JSON.stringify(getDocState())');phoneClick('phoneDesktop');
  assert.equal(phone.active,false);assert.equal(h.w.document.getElementById('soloTextarea'),phoneEditor);
  assert.equal(h.run('JSON.stringify(getDocState())'),wordsBeforeSwitch);assert.equal(h.run('documentId'),phoneId);
  for(const control of hotspotMap.controls){const node=h.w.document.getElementById(control.id);assert.equal(node.style.left,control.bounds[0]+'px');assert.equal(h.w.getComputedStyle(node).position,'absolute');}
  phoneClick('photoPhoneMenu');assert.equal(phone.active,true);assert.equal(h.w.document.getElementById('soloTextarea'),phoneEditor);
  assert.equal(h.run('JSON.stringify(getDocState())'),wordsBeforeSwitch);
  phoneClick('exportBtn');assert.match(await h.downloads.at(-1).text(),/Written on a phone/);
  phoneClick('phoneShelf');await pause();assert(h.w.document.getElementById('reachShelf').classList.contains('open'));h.run("closeModal('reachShelf')");
  console.log('PASS: phone archive, settings, exports and shelf work; desktop/phone switches preserve the exact editor, unsaved state and original coordinates');

  const tab=h.w.document.getElementById('phoneTab_write');tab.dispatchEvent(new h.w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
  assert.equal(phone.panel,'partner');assert.equal(h.w.document.activeElement.id,'phoneTab_partner');
  for(const [width,height] of [[320,568],[360,800],[390,844],[430,932],[844,390],[390,390]]){
    Object.defineProperty(h.w,'innerWidth',{value:width,configurable:true});Object.defineProperty(h.w,'innerHeight',{value:height,configurable:true});
    h.w.dispatchEvent(new h.w.Event('resize'));
    assert.equal(h.w.document.documentElement.style.getPropertyValue('--phone-height'),height+'px');assert.equal(phone.active,true);
    assert.equal(h.w.getComputedStyle(h.w.document.querySelector('.app-shell')).transform,'none');
  }
  assert.equal(h.errors.length,0,h.errors.join('\n'));h.w.close();
  h=harness({}, {width:390,height:844});await h.w.reachStarted;await h.w.reachPhoneReady;assert.equal(h.w.reachPhone.active,true);h.w.close();
  h=harness({}, {url:'http://reach.test/writers-room?view=desktop',width:390,height:844});await h.w.reachStarted;await h.w.reachPhoneReady;assert.equal(h.w.reachPhone.active,false);h.w.close();
  console.log('PASS: phone tabs support keyboard navigation, viewport changes retain the view, small screens select phone mode, and explicit desktop mode is honored');
  clearTimeout(deadline);
})().catch(error=>{console.error(error);process.exit(1);});
