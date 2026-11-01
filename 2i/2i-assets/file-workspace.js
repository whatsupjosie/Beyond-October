/* File adapter for the actual v22 2i editor. Loaded after its native scripts. */
(async function(){
'use strict';
const qs=new URLSearchParams(location.search);
const id=qs.get('file');
const sessionNonce=qs.get('foresightSession');
if(window.reachStarted){
  try{await window.reachStarted;}
  catch(error){$('saveBtn').disabled=true;$('saveIndicator').textContent='2i could not establish its account: '+error.message;return;}
}
// Normal 2i is already managed by Reach. The historical native adapter below
// must not overwrite Reach's saveDocument/newDocument/openDocument functions or
// silently restore the global twoi-native-last copy over the active manuscript.
// Legacy recovery bytes stay untouched and can be recovered deliberately.
if (!id && window.reachStarted) {
  await window.reachStarted;
  $('saveBtn').disabled = false;
  // Window focus only changes optional presentation. Save, recovery, approved
  // model turns and manuscript indexing remain live until they finish safely.
  let optionalActivity = 'full';
  const activityStatus = () => ({version:1,ready:true,mode:optionalActivity,
    capabilities:['status','save','export','activity','prepare-close'],
    dirty:!!documentDirty,conflict:!!saveConflict,
    saving:!!savePromise, protected:!!chatSending || !!generating || !!PP?.inflight,
    recovery:!!recoverySafe});
  async function handleHost(command,payload) {
    if(command==='status') return activityStatus();
    if(command==='activity') {
      const mode = payload?.mode;
      if(!['full','reduced','pause-optional'].includes(mode)) throw Error('Unsupported 2i activity policy');
      optionalActivity=mode;
      document.documentElement.dataset.foresightActivity=mode;
      document.dispatchEvent(new Event('foresight:activity-change'));
      return activityStatus();
    }
    if(command==='save') return (await saveDocument())===true;
    if(command==='prepare-close') {
      if(chatSending || generating || PP?.inflight) return {canClose:false,reason:'2i has an active conversation, generation, or manuscript-indexing operation.',status:activityStatus()};
      const saved=await saveDocument();
      const status=activityStatus();
      const canClose=saved===true && !status.dirty && !status.saving && !status.protected && !status.conflict;
      return {canClose,reason:canClose?'':'2i changed or started work during saving. Finish its work and try again.',status};
    }
    if(command==='export') return {name:safeName()+'.2i',type:'application/json',
      data:new Blob([JSON.stringify(docPayload(),null,2)],{type:'application/json'})};
    throw Error('Unknown 2i host command');
  }
  function publishActivityStatus(){
    if(parent!==window)parent.postMessage({type:'foresight:app-status',version:1,sessionNonce,...activityStatus()},location.origin);
  }
  document.addEventListener('foresight:work-change',publishActivityStatus);
  addEventListener('message',async e=>{
    if(e.origin!==location.origin||e.source!==parent||
       e.data?.type!=='foresight:file-command'||e.data.fileId!=null ||
       e.data.sessionNonce!==sessionNonce||typeof e.data.requestId!=='string') return;
    const {requestId,command,payload}=e.data;
    try {
      const result=await handleHost(command,payload);
      parent.postMessage({type:'foresight:file-result',requestId,result,sessionNonce},location.origin);
      publishActivityStatus();
    } catch(error){
      parent.postMessage({type:'foresight:file-result',requestId,error:String(error?.message||error),sessionNonce},location.origin);
    }
  });
  if(parent!==window) parent.postMessage({type:'foresight:file-ready',version:1,sessionNonce,capabilities:activityStatus().capabilities},location.origin);
  return;
}

// Never rebind the canonical Reach manuscript handlers in normal 2i mode.
// An integration missing its Reach runtime must fail visibly, not silently
// restore a shared legacy recovery copy over a different manuscript.
if(!id){
  const error='2i cannot start: the authenticated Reach manuscript runtime is unavailable.';
  $('saveBtn').disabled=true;
  $('saveIndicator').textContent=error;
  throw Error(error);
}
// Retain the host session when file selection navigates within this iframe.
// Losing it would cause valid close/save confirmations to be rejected.
function filePage(fileId){
  const url=new URL('/writers-room',location.origin);
  url.searchParams.set('file',fileId);
  if(sessionNonce)url.searchParams.set('foresightSession',sessionNonce);
  return url.pathname+url.search;
}
// File-mode drafts have their own stable IDs; the normal 2i manuscript is untouched.
const toolbar=document.createElement('section');toolbar.setAttribute('aria-label','2i file controls');
const shell=document.querySelector('.app-shell');document.body.insertBefore(toolbar,shell);
toolbar.style.height='auto';
const toolbarSize=new ResizeObserver(()=>{if(shell.style.display!=='none')shell.style.height='calc(100vh - '+toolbar.getBoundingClientRect().height+'px)'});toolbarSize.observe(toolbar);
addEventListener('pagehide',()=>toolbarSize.disconnect());
const c={data:{fileId:id},state:{}};
const host={body:toolbar,changed(){},setTitle(title){documentTitle=title;render();parent.postMessage({type:'foresight:file-renamed',fileId:id,name:title},location.origin)}};

let session;
const originalMarkDirty=markDirty;
markDirty=function(){originalMarkDirty();if(session){soloTextarea.dispatchEvent(new Event('foresight-native-change'));session.flush().catch(e=>{$('saveIndicator').textContent='Save failed: '+e.message})}};
try{
  session=await ForesightFiles.mount(c,host,null,{
    editor:soloTextarea,
    getState:()=>getDocState(),
    getTitle:()=>documentTitle,
    getText:()=>coWriting?committed.join('\n'):soloTextarea.value,
    onReady(v){documentTitle=v.name;if(/\.(py|js|ts|jsx|tsx|xml|html|css|json|yaml|yml|toml|ini|sh|ps1|sql|c|cpp|h|rs)$/i.test(v.name)){soloTextarea.style.fontFamily='monospace';soloTextarea.spellcheck=false;}render()},
    onImage(){shell.style.display='none';toolbar.style.height='100vh'},
    onPreview(active){shell.style.display=active?'none':'';toolbar.style.height=active?'100vh':'auto';},
    onError(){shell.style.display='none';toolbar.style.height='100vh'},
    load(v){
      documentTitle=v.title||v.name;
      const state=v.twoiState||{committed:v.draft.split('\n'),buffer:[],pool:[],pointer:0,chapters:[{title:'Document',subtitle:'',startLine:0}],lockedLines:[],coWriting:false,references:[]};
      loadDocState(state);soloTextarea.value=committed.join('\n');documentDirty=false;render();
    }
  });
  window.foresightFileSession=session;
  saveDocument=()=>session.save();saveDocumentAs=()=>session.saveAs();
  async function openFile(file){
    await session.save();
    const next=crypto.randomUUID();
    await ForesightFiles.record(next,{id:next,name:file.name,mime:file.type,original:file,updated:Date.now()});
    parent.postMessage({type:'foresight:file-selected',previousFileId:id,fileId:next,name:file.name},location.origin);
    location.assign(filePage(next));
  }
  openDocument=async()=>{const input=document.createElement('input');input.type='file';input.onchange=()=>{if(input.files[0])openFile(input.files[0]).catch(e=>alert(e.message))};input.click()};
  newDocument=async()=>openFile(new File([''],'Untitled.txt',{type:'text/plain'}));
  document.addEventListener('drop',event=>{event.preventDefault();event.stopImmediatePropagation();const file=event.dataTransfer?.files?.[0];if(file)openFile(file).catch(e=>alert(e.message))},true);

  $('saveBtn').onclick=()=>saveDocument().catch(e=>{$('saveIndicator').textContent=e.message});
  $('saveBtn').disabled=false;
  // Notify only our same-origin parent, never an arbitrary page.
  parent.postMessage({type:'foresight:file-ready',fileId:id},location.origin);
  let optionalActivity='full';
  const activityStatus=()=>({version:1,ready:true,mode:optionalActivity,
    capabilities:['status','save','export','activity','prepare-close'],
    dirty:session.pending(),protected:!!chatSending || !!generating || !!PP?.inflight,recovery:true});
  addEventListener('message',async e=>{
    if(e.origin!==location.origin||e.source!==parent||e.data?.type!=='foresight:file-command'||
       e.data.fileId!==id||e.data.sessionNonce!==sessionNonce||typeof e.data.requestId!=='string')return;
    const {requestId,command,payload}=e.data;
    try{
      let result;
      if(command==='save'){await session.save();result=true;}
      else if(command==='export')result=await session.export();
      else if(command==='status')result=activityStatus();
      else if(command==='activity'){
        if(!['full','reduced','pause-optional'].includes(payload?.mode))throw Error('Unsupported 2i activity policy');
        optionalActivity=payload.mode;document.documentElement.dataset.foresightActivity=optionalActivity;
        document.dispatchEvent(new Event('foresight:activity-change'));result=activityStatus();
      }else if(command==='prepare-close'){
        if(chatSending || generating || PP?.inflight)result={canClose:false,reason:'2i has active work.',status:activityStatus()};
        else {await session.save();const status=activityStatus();result={canClose:!status.dirty && !status.protected,
          reason:status.dirty||status.protected?'Document changed or started work during saving.':'',status};}
      }else throw Error('Unknown 2i host command');
      parent.postMessage({type:'foresight:file-result',requestId,result,sessionNonce},location.origin);
    }catch(error){parent.postMessage({type:'foresight:file-result',requestId,error:String(error?.message||error),sessionNonce},location.origin)}
  });
  if(parent!==window)parent.postMessage({type:'foresight:file-ready',fileId:id,version:1,sessionNonce,capabilities:activityStatus().capabilities},location.origin);
  addEventListener('pagehide',()=>session.flush().catch(console.error));
  document.addEventListener('visibilitychange',()=>{if(document.hidden)session.flush().catch(console.error)});
  addEventListener('beforeunload',event=>{if(session.pending()){event.preventDefault();event.returnValue=''}});
}catch(error){toolbar.textContent='Could not open file in 2i: '+error.message}
})();
