/* Reach integration for the preserved 2i v20 editor. No model impersonation. */
'use strict';
const reachFileMode = new URLSearchParams(location.search).get('file');
let WORKSPACE_KEY = 'reach2i_workspace_v1';
let RECOVERY_KEY = 'reach2i_recovery_v1';
const uuid = () => crypto.randomUUID ? crypto.randomUUID() : 'doc_' + Date.now() + '_' + Math.random().toString(36).slice(2);
const requestedIdParam=new URLSearchParams(location.search).get('document');
const requestedDocumentId=/^[A-Za-z0-9_-]{1,100}$/.test(requestedIdParam||'')?requestedIdParam:null;
const priorEditorWriter=typeof history.state?.twoiWriter==='string'?history.state.twoiWriter:null;
const priorOfflineDocumentId=location.protocol==='file:'?history.state?.twoiOfflineDocument:null;
const editorWriter=uuid();
const studioEntry=new URLSearchParams(location.search).has('studio_room');
let studioResume=null;
/* Editor recovery selection — kept pure for regression tests. */
function uniqueEditorRecoveries(records){
  const copies=new Map();
  for(const r of records){
    if(!r?.id||!r.state)continue;
    const key=r.dirty?"dirty:"+r.id+":"+(r.writer||"legacy")+":"+(r.writer?"":(r.ts||0)):"clean:"+r.id;
    const old=copies.get(key);
    if(!old||(r.revision||0)>(old.revision||0)||((r.revision||0)===(old.revision||0)&&(r.ts||0)>(old.ts||0)))copies.set(key,r);
  }
  return [...copies.values()].sort((a,b)=>(b.ts||0)-(a.ts||0));
}
function chooseEditorRecovery({documentId,previousWriter,explicit,records}){
  const candidates=uniqueEditorRecoveries(records).filter(r=>r.id===documentId);
  const own=previousWriter?candidates.find(r=>r.writer===previousWriter&&r.dirty):null;
  if(own)return own;
  const clean=candidates.find(r=>!r.dirty);
  if(explicit)return clean||null;
  const dirty=candidates.filter(r=>r.dirty);
  return dirty.length===1?dirty[0]:clean||null;
}
function parseStudioResume(raw){
  try{
    const x=typeof raw==='string'?JSON.parse(raw):raw;
    if(!x||typeof x.id!=='string'||!/^[A-Za-z0-9_-]{1,100}$/.test(x.id)||typeof x.writer!=='string'||!/^[A-Za-z0-9_-]{1,120}$/.test(x.writer))return null;
    return {id:x.id,writer:x.writer};
  }catch{return null;}
}
/* End editor recovery selection. */
function stored(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; } }
let workspace = stored(WORKSPACE_KEY, { clientId:'writer_' + uuid(), documentId:uuid() });
let documentId = priorOfflineDocumentId || workspace.documentId || uuid();
let revision = 0, mutation = 0, savedMutation = 0, savePromise = null;
let fileSavingId = null;
let serverReady = false, initializing = true, saveConflict = false, recoverySafe = false;
let partnerId = 'alex', conversations = {}, conversationIds = {};
let partnerNames = {alex:'Alex', craig:'Craig', friend:'Friend'};
// The host selects the installed FREE local model. Never hardcode a model tag
// or silently choose a paid API. An explicitly saved user choice is separate.
let MODEL_KEY = null;
let modelConfig = null; // Ownerless settings must not silently select a billable model.
function hostLocalProvider(config) {
  const p = config && typeof config === 'object' ? config : null;
  // The Reach configuration endpoint supplies only locally hosted defaults.
  if (p?.provider === 'ollama' &&
      (!p.base_url || /^http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:\/.*)?$/.test(p.base_url)))
    return Object.assign({}, p);
  if (p?.provider === 'openai_compatible' &&
      /^http:\/\/(?:127\.0\.0\.1|\[::1\])(?::\d+)?\/v1\/?$/.test(p.base_url || ''))
    return Object.assign({}, p);
  return null;
}

let recoveryTimer, serverTimer;
const networked = location.protocol === 'http:' || location.protocol === 'https:';
// Autosave history belongs to the authenticated account, like server documents.
openDB=function() {
  if(reachFileMode || !window.indexedDB || (networked && !serverReady))return Promise.resolve(null);
  return new Promise(resolve=>{
    const request=indexedDB.open('reach2i-snaps-'+RECOVERY_KEY,1);
    request.onupgradeneeded=()=>request.result.createObjectStore('snaps');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve(null);
  });
};
function pinEditorDocument() {
  if(reachFileMode)return;
  try{
    if(!networked){
      history.replaceState({...history.state,twoiWriter:editorWriter,twoiOfflineDocument:documentId},'');
      return;
    }
    const url=new URL(location.href);url.searchParams.set('document',documentId);
    history.replaceState({...history.state,twoiWriter:editorWriter},'',url);
  }catch(error){console.warn('Could not pin the editor URL:',error.message);}
}
function rememberWorkspace() {
  workspace.documentId=documentId;
  try{localStorage.setItem(WORKSPACE_KEY,JSON.stringify(workspace));}catch{}
  pinEditorDocument();
}
function recoveryWriterKey(id,writer=editorWriter){return RECOVERY_KEY+':writer:'+writer+':'+id;}
function rememberStudioResume(){
  if(!serverReady||initializing||reachFileMode)return false;
  try{sessionStorage.setItem(RECOVERY_KEY+':studio-handoff',JSON.stringify({id:documentId,writer:editorWriter}));return true;}catch{return false;}
}
// Manuscripts and account state always belong to the local Reach host.
// A separately configured AI endpoint must never redirect document writes.
function baseURL() { return (networked ? location.origin : 'http://localhost:8000').replace(/\/+$/, ''); }
function reachHeaders(cfg=llmCfg) {
  const headers = {'Content-Type':'application/json'};
  const token = cfg.pubpartner.token?.trim() || sessionStorage.getItem('pubcast_token') || localStorage.getItem('pubpartner.auth.token.v1');
  if (token) headers.Authorization = 'Bearer ' + token;
  else headers['X-Client-Id'] = workspace.clientId;
  return headers;
}
async function api(path, options={}) {
  const r = await fetch(baseURL() + path, {signal:AbortSignal.timeout?.(8000), ...options, headers:{...reachHeaders(), ...(options.headers || {})}});
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = body.detail;
    const error = new Error(r.status === 401 ? 'Sign in to Reach or add your auth token in model settings.' :
      (typeof detail === 'string' ? detail : detail?.message) || 'Reach returned ' + r.status);
    error.status = r.status; throw error;
  }
  return body;
}
function validateDocumentState(state) {
  if(state?.formatting!==undefined){if(typeof TwoiFormatCore==='undefined')throw Error('Formatting runtime unavailable; retain the original.');TwoiFormatCore.restore(state.formatting,state.committed||[]);}
  if (!state || typeof state !== 'object' || Array.isArray(state)) throw Error('This file has no valid document state.');
  for (const key of ['committed','buffer','pool']) {
    if (state[key] !== undefined && (!Array.isArray(state[key]) || state[key].some(v => typeof v !== 'string'))) throw Error('Invalid manuscript lines.');
  }
  if (state.references !== undefined && (!Array.isArray(state.references) || state.references.some(r => !r || typeof r.name !== 'string' || typeof r.content !== 'string'))) throw Error('Invalid references.');
  if (state.chapters !== undefined && (!Array.isArray(state.chapters) || state.chapters.some(c => !c || typeof c.title !== 'string' || !Number.isInteger(c.startLine) || c.startLine < 0))) throw Error('Invalid chapters.');
  if((state.chapters||[]).some((c,i,all)=>c.startLine>(state.committed||[]).length+(state.buffer||[]).length || (i>0&&c.startLine<all[i-1].startLine)))throw Error('Invalid chapter order or position.');
  if (state.lockedLines !== undefined && (!Array.isArray(state.lockedLines) || state.lockedLines.some(i => !Number.isInteger(i) || i < 0 || i >= (state.committed || []).length))) throw Error('Invalid locked lines.');
  if (state.coWriting !== undefined && typeof state.coWriting !== 'boolean') throw Error('Invalid writing mode.');
  if(state.generatedLineTexts!==undefined&&(!Array.isArray(state.generatedLineTexts)||state.generatedLineTexts.some(x=>typeof x!=='string')))throw Error('Invalid generated-line provenance.');
  if(state.pointer!==undefined&&(!Number.isInteger(state.pointer)||state.pointer<0||state.pointer>(state.pool||[]).length))throw Error('Invalid generation queue position.');
  // Validate the added narrative record before changing document identity or
  // rendering the recovered copy. Invalid data must not replace active work.
  if(state.narrative!==undefined){
    if(typeof NarrativeCore==='undefined')throw Error('Narrative intelligence runtime missing; keep the original document.');
    const narrative=NarrativeCore.restore(state.narrative);
    if(narrative.archive.some(x=>!x||typeof x.kind!=='string'||typeof x.text!=='string'))throw Error('Invalid creative archive.');
    const ids=new Set(narrative.scenes.map(x=>x.id));
    if(narrative.latentByScene!==undefined){
      if(!Array.isArray(narrative.latentByScene)||narrative.latentByScene.some(x=>!x||!ids.has(x.id)||typeof x.text!=='string')||new Set(narrative.latentByScene.map(x=>x.id)).size!==narrative.latentByScene.length)throw Error('Invalid scene-specific latent archive.');
    }
    for(const key of ['review','proposal']){
      const item=narrative[key];if(item!==null&&item!==undefined&&(!item||typeof item.text!=='string'||!ids.has(item.sceneId)))throw Error('Invalid narrative advisory.');
    }
  }
  if (state.partnerId !== undefined && (typeof state.partnerId !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(state.partnerId))) throw Error('Invalid partner identity.');
  for (const key of ['conversations','conversationIds']) if (state[key] !== undefined && (!state[key] || typeof state[key] !== 'object' || Array.isArray(state[key]))) throw Error('Invalid conversation state.');
  for (const messages of Object.values(state.conversations || {})) if (!Array.isArray(messages) || messages.some(m => !m || !['user','assistant'].includes(m.role) || typeof m.content !== 'string')) throw Error('Invalid conversation.');
}
function setSaveStatus(text) { $('saveIndicator').textContent = text; }
function writeRecovery() {
  if(reachFileMode || (networked&&!serverReady))return;
  try{
    conversations[partnerId]=chatHistory;
    const copy={id:documentId,revision,mutation,title:documentTitle,state:getDocState(),dirty:documentDirty,ts:Date.now(),writer:editorWriter};
    const content=JSON.stringify(copy), key=RECOVERY_KEY+':'+documentId, own=recoveryWriterKey(documentId);
    if(documentDirty){
      // Independent tabs must never overwrite one another's unsaved recovery.
      localStorage.setItem(own,content);
    }else{
      const old=stored(key,null);
      if(!old?.dirty&&(!old||(old.revision||0)<=revision))localStorage.setItem(key,content);
      // Preserve legacy dirty copies. Remove only this runtime's buffer once
      // the server or the clean canonical recovery actually retains the work.
      if((networked&&revision>0)||(!old?.dirty&&stored(key,null)?.revision===revision))localStorage.removeItem(own);
    }
    rememberWorkspace();recoverySafe=true;
  }catch{recoverySafe=false;pinEditorDocument();setSaveStatus('Browser recovery unavailable · export a copy if needed');}
}
function markDirty() {
  documentDirty = true; recoverySafe = false; mutation++;
  setSaveStatus(saveConflict ? 'Changed elsewhere · save a copy' : 'Saving…');
  clearTimeout(recoveryTimer); recoveryTimer = setTimeout(writeRecovery, 120);
  clearTimeout(serverTimer);
  if (!initializing) serverTimer = setTimeout(() => saveDocument(), 1000);
  document.dispatchEvent(new Event('foresight:work-change'));
}
async function writeAutosave() {
  if (initializing) return;
  writeRecovery();
  // Preserve the donor's recoverable snapshot format for its restore menu.
  const db = await openDB();
  if (db) await new Promise(resolve => {
    const tx = db.transaction('snaps','readwrite');
    // Per-document snapshots prevent two manuscripts sharing one three-slot
    // rotation. Historical reach_0..2 snapshots are deliberately not deleted.
    tx.objectStore('snaps').put({id:documentId,title:documentTitle,ts:Date.now(),state:getDocState(),writer:editorWriter}, 'reach_' + documentId + '_' + editorWriter + '_' + (Math.floor(Date.now()/60000)%3));
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); resolve(); };
  });
}
async function saveDocument() {
  if (initializing) return false;
  if (savePromise) return savePromise;
  writeRecovery();
  if (saveConflict) { setSaveStatus('Changed elsewhere · My manuscripts → Save a copy'); return false; }
  // No host (opened from disk): automatic saves keep the browser recovery copy only and say where the file stands.
  // Writing the manuscript file is an explicit act: see saveToFile().
  if (!networked) {
    if (fileSavingId !== documentId && documentDirty) showUnsavedFileStatus();
    return false;
  }
  if(revision>0&&!documentDirty)return true;
  const savingId=documentId;
  savePromise=(async()=>{
    try {
      // A caller changing manuscripts awaits every edit made during the write.
      do {
        writeRecovery();
        const savingMutation=mutation;
        const payload={...docPayload(),expected_revision:revision};
        const result=await api('/api/writers-room/documents/'+encodeURIComponent(savingId),{method:'PUT',body:JSON.stringify(payload)});
        if(savingId!==documentId)return false;
        revision=result.revision;savedMutation=savingMutation;serverReady=true;
        documentDirty=mutation!==savingMutation;
        setSaveStatus(documentDirty?'Saving latest changes…':'Saved to Reach · revision '+revision);
        writeRecovery();
      } while(documentDirty);
      return true;
    } catch(error) {
      if(error.status===409){saveConflict=true;setSaveStatus('Changed elsewhere · save a copy');}
      else setSaveStatus((recoverySafe?'Saved in browser · ':'Save failed · ')+(error.status?error.message:'Reach unavailable'));
      return false;
    } finally {savePromise=null;document.dispatchEvent(new Event('foresight:work-change'))}
  })();
  return savePromise;
}
function showUnsavedFileStatus() {
  setSaveStatus(!recoverySafe ? 'Export a copy now' : documentHandle
    ? 'Kept in this browser · Save to update ' + documentHandle.name
    : 'Kept in this browser · Save to write a file');
}

async function saveToFile() {
  if (initializing || fileSavingId !== null) return false;
  const savingId = documentId;
  const savingMutation = mutation;
  fileSavingId = savingId;
  try {
    writeRecovery();
    const result = await writeOfflineManuscript({
      handle: documentHandle,
      filename: safeName() + '.2i',
      payload: JSON.stringify(docPayload(), null, 2),
      isCurrent: () => documentId === savingId
    });
    if (documentId !== savingId) return false;
    if (!result) {
      setSaveStatus(recoverySafe ? 'Not saved to a file · kept in this browser' : 'Not saved · export a copy now');
      return false;
    }
    documentHandle = result.handle;
    documentDirty = mutation !== savingMutation;
    writeRecovery();
    if (documentDirty) showUnsavedFileStatus();
    else setSaveStatus(result.handle ? 'Saved to ' + result.handle.name : 'Copy downloaded · ' + result.filename);
    document.dispatchEvent(new Event('foresight:work-change'));
    return !documentDirty;
  } catch (error) {
    if (documentId === savingId) {
      writeRecovery();
      const reason = error instanceof ManuscriptFileConflict ? 'File changed' : 'File save failed';
      setSaveStatus(reason + ' · ' + (recoverySafe ? 'kept in this browser · ' : '') + 'Save a copy');
      addChat('notice', error.message);
    }
    return false;
  } finally {
    fileSavingId = null;
  }
}
// What the Save button, File › Save and Ctrl+S do: the host when there is one, the file when there is not.
function saveNow() { return networked ? saveDocument() : saveToFile(); }
async function preserveBeforeSwitch() {
  if (chatSending || generating || editingIdx!==null) {
    addChat('notice', 'An inline edit, message or generation is still active. Finish or cancel it before changing manuscripts.');
    return false;
  }
  const sourceId=documentId;window.twoiCreativeSession?.stopForSwitch();await saveDocument();
  if(sourceId!==documentId||generating||chatSending){addChat('notice','The current manuscript or request changed. Retry the switch.');return false;}
  if(documentDirty&&!recoverySafe){addChat('notice','Your current manuscript could not be saved. Export a .2i copy before switching manuscripts.');return false;}
  return true;
}
function browserManuscripts() {
  const records=[];
  try{
    for(let index=0;index<localStorage.length;index++){
      const key=localStorage.key(index);
      if(key===RECOVERY_KEY||key?.startsWith(RECOVERY_KEY+':')){
        const r=stored(key,null);if(r?.id&&r.state)records.push({...r,recoveryKey:key});
      }
    }
  }catch{}
  return uniqueEditorRecoveries(records);
}
function downloadFile(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = document.createElement('a'); a.href=url; a.download=name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function keepChapterPositions(previous,next) {
  let first=0,last=0;
  while(first<previous.length&&first<next.length&&previous[first]===next[first])first++;
  while(last<previous.length-first&&last<next.length-first&&previous[previous.length-last-1]===next[next.length-last-1])last++;
  const oldEnd=previous.length-last,delta=next.length-previous.length;
  const offsets=[0];for(let i=0;i<previous.length;i++)if(previous[i]==='\n')offsets.push(i+1);
  chapters.forEach((chapter,index)=>{
    if(index===0){chapter.startLine=0;return;}
    const anchor=offsets[chapter.startLine]??previous.length;
    const moved=anchor<first?anchor:anchor>=oldEnd?anchor+delta:first;
    chapter.startLine=next.slice(0,Math.max(0,moved)).split('\n').length-1;
  });
}
async function saveDocumentAs() {
  writeRecovery();
  downloadFile(safeName()+'.2i', JSON.stringify(docPayload(),null,2), 'application/json');
  setSaveStatus('Copy exported · ' + (revision ? 'Reach revision '+revision : 'browser recovery kept'));
}
async function exportManuscript() {
  let text = '# ' + documentTitle + '\n\n';
  committed.forEach((line,i) => {
    for (const chapter of chapters.filter(c => c.startLine === i)) text += '\n## '+chapter.title+(chapter.subtitle?'\n*'+chapter.subtitle+'*':'')+'\n\n';
    text += line+'\n';
  });
  if (buffer.length) text += '\n---\n*Uncommitted draft*\n\n'+buffer.join('\n')+'\n';
  downloadFile(safeName()+'.md', text, 'text/markdown');
}
async function importDocument(file, fileHandle = null) {
  const doc = JSON.parse(await file.text());
  if (doc.format !== '2i-document' || doc.version > 4) throw Error('Unsupported 2i document format.');
  validateDocumentState(doc.state);
  if(!await preserveBeforeSwitch())return;
  cancelLLM(); stopPlaying();
  documentId = uuid(); revision=0; saveConflict=false;
  documentTitle = String(doc.title || 'Untitled manuscript').slice(0,200); documentHandle=fileHandle;
  loadDocState({...doc.state,conversationIds:{}});
  if (fileHandle) {
    documentDirty = false;
    writeRecovery();
    setSaveStatus('Opened ' + fileHandle.name);
    document.dispatchEvent(new Event('foresight:work-change'));
  } else {
    markDirty(); render(); await saveDocument();
  }
  return true;
}
async function openDocument() {
  // No host, and the browser has a file picker: keep the chosen file's handle so Save writes back to that file.
  if (!networked && typeof window.showOpenFilePicker === 'function') {
    try {
      const [handle] = await window.showOpenFilePicker({types:[{description:'2i Document',accept:{'application/json':['.2i','.json']}}]});
      await importDocument(await readManuscriptFile(handle), handle);
    } catch (error) { if (error.name !== 'AbortError') addChat('notice', error.message); }
    return;
  }
  const input = document.createElement('input'); input.type='file'; input.accept='.2i,.json';
  input.onchange = async () => { if (input.files[0]) try { await importDocument(input.files[0]); } catch(error) { addChat('notice',error.message); } };
  input.click();
}
async function newDocument() {
  if(!await preserveBeforeSwitch())return;
  cancelLLM(); stopPlaying(); documentId=uuid(); revision=0; saveConflict=false;
  documentTitle='Untitled manuscript'; documentHandle=null;
  loadDocState({committed:[],buffer:[],pool:[],pointer:0,chapters:[{title:'Chapter One',subtitle:'',startLine:0}],lockedLines:[],coWriting:false,references:[],partnerId});
  markDirty(); render(); await saveDocument();
}
function restoreConversation() {
  if (!$('partnerSelect').querySelector('option[value="'+partnerId+'"]')) {
    const option=document.createElement('option'); option.value=partnerId; option.textContent=partnerNames[partnerId] || partnerId; $('partnerSelect').appendChild(option);
  }
  $('partnerSelect').value=partnerId;
  chatLog.replaceChildren();
  for (const row of chatHistory) {
    if (row.delivery === 'pending') row.delivery = 'unknown';
    addChat(row.role==='user'?'you':'pp',row.content);
    if (row.delivery === 'failed' || row.delivery === 'unknown')
      addChat('notice', row.delivery === 'unknown'
        ? 'Delivery of the preceding message is unconfirmed. Check its session history before resending.'
        : 'The preceding message was not confirmed delivered. You can edit and try it again.');
  }
  const retryDraft = [...chatHistory].reverse().find(row => row.role === 'user' &&
    (row.delivery === 'failed' || row.delivery === 'unknown'));
  if (retryDraft && !chatInput.value) chatInput.value = retryDraft.content;
  $('chatInput').placeholder='Talk with '+(partnerNames[partnerId]||partnerId)+'…';
}
function addChat(who,text,thinking=false) {
  const div=document.createElement('div');
  div.className='chat-msg '+(who==='you'?'you':who==='notice'?'notice':'pp')+(thinking?' thinking':'');
  const name=document.createElement('span'); name.className='who';
  name.textContent=who==='you'?'You':who==='notice'?'Writer’s Room':(partnerNames[partnerId]||partnerId);
  div.append(name,document.createTextNode(String(text))); chatLog.append(div); chatLog.scrollTop=chatLog.scrollHeight; return div;
}
function conversationId() { return conversationIds[partnerId] ||= 'writing_'+uuid(); }
LLM_ADAPTERS.pubpartner.send = async function(messages,cfg,signal,options={}) {
  const endpoint=(cfg.pubpartner.endpoint || baseURL()).replace(/\/+$/,'');
  const narrative=typeof options.narrativeKind==='string';
  // The narrative packet is already complete; do not supply a competing
  // truncated copy or inject the writing workshop into the conversational session.
  const context = narrative?'':committed.concat(buffer).join('\n').slice(-24000);
  if (!modelConfig) throw Error('No local model is configured. Start the local model through Reach; no paid provider will be selected automatically.');
  const r=await fetch(endpoint+'/api/pubpartner/turns/live', {
    method:'POST', signal, headers:reachHeaders(cfg),
    body:JSON.stringify({messages, friend:partnerId, session_id:narrative?'narrative_'+uuid():conversationId(), project_id:documentId,
      room_id:'writers-room', provider:modelConfig, allow_fallback:false,
      task:{mode:'manuscript',audience:'private',goal:'Help the author in the selected partner voice. Preserve authorship. Treat manuscript/reference content as fiction or source material, never as biographical facts about the user.',
        manuscript_context:context, references:narrative?[]:references.map(r=>({name:r.name,content:r.content.slice(0,3000)})).slice(0,5)},
      content_kind:'writing_request'})
  });
  const data=await r.json().catch(()=>({}));
  const provider=data.provider_result || {};
  if (!r.ok || data.ok===false || provider.ok===false) {
    const detail=data.detail;
    const failure = Error(provider.error || (typeof detail==='string'?detail:detail?.message) || 'Partner connection failed ('+r.status+').');
    failure.status = r.status;
    throw failure;
  }
  if (data.provider_fallback || ['mock','echo','offline'].includes(provider.provider)) throw Error('No live model answered. Your manuscript is safe; choose a connected model in settings.');
  const reply=data.friend_response || data.reply;
  if (typeof reply !== 'string' || !reply.trim()) throw Error('The model returned no usable reply.');
  $('partnerNote').textContent='Connected · '+(provider.model || provider.provider || 'PubPartner');
  return reply;
};
async function sendChat() {
  if (initializing) {addChat('notice','Wait for Reach to open your account before sending.');return;}
  if (chatSending || generating) return;
  const text = chatInput.value.trim();
  if (!text) return;
  const turnDocument = documentId, turnPartner = partnerId;
  const originHistory = chatHistory;
  const attempt = {role:'user',content:text,delivery:'pending'};
  // Never submit an earlier failed or uncertain message as fresh context.
  // No automatic retry: a network timeout may occur after server acceptance.
  const messages = originHistory.filter(row => row.delivery == null &&
    (row.role === 'user' || row.role === 'assistant')).slice(-(MAX_CHAT-1));
  messages.push({role:'user',content:text});
  chatSending = true;
  if(typeof document!=='undefined')document.dispatchEvent(new Event('foresight:work-change'));
  $('chatSendBtn').disabled = true;
  originHistory.push(attempt);
  conversations[turnPartner] = originHistory;
  addChat('you',text);
  markDirty(); // durable provisional state before invoking the network
  const thinking = addChat('pp','Thinking…',true);
  try {
    // Retain the pending turn before sending. File trays use their own working
    // copy store; ordinary manuscripts use their owner-scoped recovery record.
    if(reachFileMode){
      if(!window.foresightFileSession)throw Object.assign(Error('File recovery is not ready. Your message has not been sent.'),{status:400});
      try{await window.foresightFileSession.flush();}
      catch(error){throw Object.assign(Error('Cannot retain the message: '+error.message),{status:400});}
    }else{
      writeRecovery();
      if(!recoverySafe)throw Object.assign(Error('Browser recovery is unavailable. Export your work before sending.'),{status:400});
    }
    const reply = await callLLM(messages);
    // The document-switch and partner-switch handlers block while chatSending.
    // Keep the guard in case another program navigated the page independently.
    if (turnDocument !== documentId || turnPartner !== partnerId) {
      attempt.delivery = 'unknown';
      addChat('notice','A reply completed after the conversation changed. Reopen its original session to reconcile it.');
      return;
    }
    delete attempt.delivery;
    originHistory.push({role:'assistant',content:reply});
    if (chatInput.value.trim() === text) chatInput.value = '';
    addChat('pp',reply);
    markDirty();
  } catch(error) {
    // Errors can occur after the host received the request, so do not
    // promise that a blind retry is idempotent. Preserve the draft and mark
    // the attempt, excluding it from subsequent model context.
    attempt.delivery = error?.status === 503 || error?.status === 400 ? 'failed' : 'unknown';
    if (turnDocument === documentId && turnPartner === partnerId) {
      addChat('notice', 'The reply was not confirmed: ' + (error?.message || error) +
        (attempt.delivery === 'unknown' ? ' It may have reached PubPartner; check the session before resending.' : ''));
      $('partnerNote').textContent='Model unavailable · your manuscript and unsent text are preserved.';
      markDirty();
    }
  } finally {
    thinking.remove();
    chatSending = false;
    if(typeof document!=='undefined')document.dispatchEvent(new Event('foresight:work-change'));
    $('chatSendBtn').disabled = false;
  }
}
async function switchPartner() {
  if (chatSending || generating) {
    $('partnerSelect').value = partnerId;
    addChat('notice','Finish or cancel the pending reply or generation before switching partners.');
    return;
  }
  cancelLLM(); conversations[partnerId]=chatHistory;
  partnerId=$('partnerSelect').value; chatHistory=conversations[partnerId] || [];
  restoreConversation(); $('partnerNote').textContent='A separate conversation, with your manuscript in view.'; markDirty();
}
const legacyOpenSettings=openLLMModal;
openLLMModal=function() {
  legacyOpenSettings(); $('reachProvider').value=modelConfig?.provider || 'ollama';
  $('reachModel').value=modelConfig?.model || ''; $('reachCredential').value=modelConfig?.credential_model_id || ''; $('reachBaseURL').value=modelConfig?.base_url || '';
};
const legacySaveSettings=$('llmSaveBtn').onclick;
$('llmSaveBtn').onclick=async () => {
  if(!MODEL_KEY){$('partnerNote').textContent='Sign in before saving model settings.';return;}
  modelConfig={provider:$('reachProvider').value,model:$('reachModel').value.trim(),credential_model_id:$('reachCredential').value.trim(),base_url:$('reachBaseURL').value.trim()};
  localStorage.setItem(MODEL_KEY,JSON.stringify(modelConfig));
  legacySaveSettings();
  $('partnerNote').textContent='Settings saved. Send a message to connect.';
  try { await connectReach(); } catch {};
};
$('llmTestBtn').onclick=async () => {
  const button=$('llmTestBtn'); button.disabled=true; $('llmTestResult').textContent='Checking connection…';
  try {
    const config={provider:$('reachProvider').value,model:$('reachModel').value.trim(),credential_model_id:$('reachCredential').value.trim(),base_url:$('reachBaseURL').value.trim()};
    const endpoint=$('llmPPEndpoint').value.replace(/\/+$/,'');
    const headers=reachHeaders({pubpartner:{token:$('llmPPToken').value}});
    const r=await fetch(endpoint+'/api/pubpartner/providers/status?'+new URLSearchParams({provider:config.provider,model:config.model,credential_model_id:config.credential_model_id,base_url:config.base_url}),{headers});
    const result=await r.json();
    $('llmTestResult').textContent=r.ok&&result.available?'Service configured. A real reply will confirm generation.':'Model unavailable: '+(result.reason||result.error||result.detail||r.status);
  } catch(error) { $('llmTestResult').textContent='Cannot connect: '+error.message; }
  finally { button.disabled=false; }
};
function configureOwnerModels(ownerKey,provider){
  MODEL_KEY='reach2i_model_v1_'+ownerKey;
  LLM_KEY='pubcast2i_llm_v2_'+ownerKey;
  llmCfg=loadLLM();
  modelConfig=stored(MODEL_KEY,null)||hostLocalProvider(provider);
}
async function connectReach() {
  const config=await api('/api/writers-room/config');
  if(typeof config.user_id!=='string'||!config.user_id.trim())throw Error('Reach did not confirm the manuscript owner.');
  const ownerKey = encodeURIComponent(config.user_id);
  configureOwnerModels(ownerKey,config.provider);
  if (WORKSPACE_KEY !== 'reach2i_workspace_v1_' + ownerKey) {
    WORKSPACE_KEY = 'reach2i_workspace_v1_' + ownerKey;
    RECOVERY_KEY = 'reach2i_recovery_v1_' + ownerKey;
    const next = stored(WORKSPACE_KEY, {clientId:workspace.clientId,documentId:uuid()});
    workspace = next; documentId=reachFileMode ? 'file_'+reachFileMode : (requestedDocumentId||workspace.documentId||uuid()); revision=0;
  }
  // Read only this authenticated owner's per-tab handoff. Explicit version URLs win.
  if(studioEntry&&!requestedDocumentId&&!reachFileMode){
    try{studioResume=parseStudioResume(sessionStorage.getItem(RECOVERY_KEY+':studio-handoff'));}catch{}
    if(studioResume)documentId=studioResume.id;
  }
  serverReady=true;
  if (!modelConfig) $('partnerNote').textContent='No local model configured · paid models will not be selected automatically.';
  // Character profiles are optional; their outage must not block manuscript storage.
  try {
    const profiles=await api('/api/pubpartner/profiles/friend');
    for (const profile of profiles.profiles || []) if(profile.id && profile.display_name) partnerNames[profile.id]=profile.display_name;
  } catch(error) {
    console.warn('Reach character profiles unavailable; manuscript storage remains connected:', error.message);
  }
  $('partnerSelect').replaceChildren(...Object.entries(partnerNames).map(([id,name])=>{const o=document.createElement('option');o.value=id;o.textContent=name;return o;}));
  $('partnerSelect').value=partnerId;
  restoreConversation();
}

async function showRevisionHistory() {
  if (reachFileMode || !networked) {addChat('notice','Server revision history requires a connected native manuscript.');return;}
  if (initializing || generating || chatSending) {addChat('notice','Finish the active request before opening revision history.');return;}
  const sourceId=documentId;
  const entry=await saveDocument();
  if(sourceId!==documentId||initializing||generating||chatSending||editingIdx!==null)return;
  const comparisonBasis={lines:committed.slice(),revision:entry===true&&!documentDirty?revision:null};
  const old=document.getElementById('reachRevisionHistory');if(old)old.remove();
  const d=document.createElement('dialog');d.id='reachRevisionHistory';
  d.setAttribute('aria-label','Manuscript revision history');
  Object.assign(d.style,{width:'min(680px,94vw)',maxHeight:'85dvh',overflow:'auto',background:'#f7efe0',color:'#29231b',border:'1px solid #8b7250',borderRadius:'12px',padding:'16px'});
  document.body.append(d);
  const add=(tag,text,parent=d)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;parent.append(e);return e;};
  const action=(text,parent,fn)=>{const b=add('button',text,parent);b.type='button';b.className='mc-btn';b.style.margin='4px';b.onclick=fn;return b;};
  add('h2','Saved revisions');
  add('p','Older revisions are read-only here. Export a copy or recover one as a separate manuscript; the current manuscript is never replaced.');
  if(entry!==true)add('p','Current changes may not have reached the server. Only confirmed server revisions are listed.');
  const status=add('p','Loading…');status.setAttribute('role','status');
  const comparison=add('section',undefined);comparison.hidden=true;
  comparison.setAttribute('aria-label','Read-only revision comparison');
  const list=add('div',undefined);const nav=add('div',undefined);
  function renderComparison(saved,number){
    const result=TwoiFormatCore.compareLines(saved.committed||[],comparisonBasis.lines);
    comparison.replaceChildren();comparison.hidden=false;
    add('h3','Revision '+number+' → '+(comparisonBasis.revision===null?'local snapshot at opening':'saved revision '+comparisonBasis.revision),comparison);
    add('p','Committed text only. Formatting, titles, notes, draft, and attribution records are not compared. No changes are applied.',comparison);
    add('p',result.method==='coarse-region'?'Large changed region shown as a whole; counts include any unchanged paragraphs inside that region.':result.removedCount+' earlier paragraph(s) removed or replaced · '+result.addedCount+' later paragraph(s) added or replaced.',comparison);
    if(!result.blocks.length)add('p','Committed text is identical.',comparison);
    let displayed=0,chars=0,clipped=false;
    outer:for(const b of result.blocks){
      const section=add('div',undefined,comparison);section.style.borderTop='1px solid #ad9b83';section.style.padding='6px 0';
      add('strong','Earlier position '+(b.oldStart+1)+' · later position '+(b.newStart+1),section);
      for(const [label,lines,start] of [['− Earlier',b.removed,b.oldStart],['+ Later',b.added,b.newStart]]){
        for(let i=0;i<lines.length;i++){
          if(displayed>=200||chars>=50000){clipped=true;break outer;}
          const remaining=Math.max(0,50000-chars),line=lines[i],part=line.slice(0,remaining);if(part.length<line.length)clipped=true;
          const row=add('p',label+' '+(start+i+1)+': '+(part||'(blank paragraph)')+(part.length<line.length?' [truncated]':''),section);
          Object.assign(row.style,{whiteSpace:'pre-wrap',overflowWrap:'anywhere',margin:'4px 0',padding:'4px',background:label.startsWith('−')?'#fce7e4':'#e4f1e7',color:'#28231d'});
          displayed++;chars+=part.length;
        }
      }
    }
    if(clipped)add('p','Screen preview limited to 200 paragraphs / 50,000 characters. Export the full comparison only if you want a private copy.',comparison);
    action('Export full private text comparison',comparison,()=>{
      if(!d.open||documentId!==sourceId)return;
      if(!confirm('Export a private file containing manuscript text from both compared revisions?'))return;
      downloadFile('revision-'+number+'-comparison.json',JSON.stringify({format:'2i-committed-comparison',version:1,baseline:number,targetRevision:comparisonBasis.revision,targetDescription:'snapshot at history opening',...result},null,2),'application/json');
    });
    action('Close comparison',comparison,()=>{comparison.hidden=true;comparison.replaceChildren();});
    comparison.scrollIntoView({block:'start'});
  }
  action('Close',nav,()=>d.close());
  const more=action('Older revisions',nav,()=>load());more.disabled=true;
  let before=null,busy=false;
  async function load(){
    if(busy)return;busy=true;more.disabled=true;
    try{
      const params=before===null?'':'?before='+encodeURIComponent(before);
      const result=await api('/api/writers-room/documents/'+encodeURIComponent(sourceId)+'/revisions'+params);
      if(!d.open)return;
      if(!result.revisions.length&&list.childElementCount===0)status.textContent='No confirmed server revisions yet.';
      else status.textContent='Saved snapshots only · '+(result.next_before?'more available':'end of history');
      for(const row of result.revisions){
        const box=add('div',undefined,list);box.style.borderTop='1px solid #ad9b83';box.style.padding='8px 0';
        add('strong','Revision '+row.revision+' · '+row.title,box);
        add('p',new Date(row.updated*1000).toLocaleString(),box);
        async function retrieve(mode){
          if(busy)return;busy=true;more.disabled=true;
          try{
            const snapshot=await api('/api/writers-room/documents/'+encodeURIComponent(sourceId)+'/revisions/'+row.revision);
            const copy={format:snapshot.format,version:snapshot.version,title:snapshot.title,state:snapshot.state};
            validateDocumentState(copy.state);
            if(!d.open||documentId!==sourceId)return;
            if(mode==='compare'){renderComparison(copy.state,row.revision);status.textContent='Comparison is read-only.';}
            else if(mode==='export'){
              downloadFile('revision-'+row.revision+'.2i',JSON.stringify(copy,null,2),'application/json');
              status.textContent='Revision exported without changing the current manuscript.';
            }else{
              if(sourceId!==documentId)throw Error('The active manuscript changed. Open revision history again.');
              if(!confirm('Open this revision as a separate recovered manuscript? Your current manuscript will be preserved.'))return;
              await forkSavedVersion(sourceId,row.revision,String(copy.title).slice(0,170)+' — recovered r'+row.revision);
              if(documentId!==sourceId)d.close();
              else status.textContent='Recovery was not applied. The current manuscript remains active.';
            }
          }catch(error){status.textContent=error.message;}
          finally{busy=false;more.disabled=before===null;}
        }
        action('Compare with opened snapshot',box,()=>retrieve('compare'));
        action('Export .2i',box,()=>retrieve('export'));
        action('Open as recovered copy',box,()=>retrieve('recover'));
      }
      before=result.next_before??null;
    }catch(error){status.textContent='Revision history unavailable: '+error.message;}
    finally{busy=false;more.disabled=before===null;}
  }
  d.addEventListener('close',()=>d.remove(),{once:true});d.showModal();await load();
}

async function showShelf() {
  if (networked) await saveDocument();
  else writeRecovery();
  const shelf=$('reachShelfList');shelf.replaceChildren();
  let remote=[], remoteError=null;
  if (networked) {
    try {remote=(await api('/api/writers-room/documents')).documents || [];}
    catch (error) { remoteError=error; }
  }
  const local=browserManuscripts();
  const entries=remote.map(doc=>({...doc,source:'server'}));
  for(const doc of local) if(doc.dirty||!remote.some(r=>r.id===doc.id))entries.unshift({...doc,source:'browser'});
  // A disconnected Reach server must not masquerade as an empty manuscript shelf.
  if (remoteError) {
    const warning=document.createElement('p');
    warning.className='reach-shelf-warning';
    warning.setAttribute('role','status');
    warning.textContent='Reach manuscripts unavailable ('+remoteError.message+'). Browser recovery copies are shown below; do not assume your server manuscripts are missing.';
    shelf.append(warning);
  }
  if(!entries.length) {
    const empty=document.createElement('p');
    empty.textContent=!networked?'No browser recovery copies found.':remoteError?'No browser recovery copies found. Reconnect Reach to view server manuscripts.':'Your saved manuscripts will appear here.';
    shelf.append(empty);
  }
  for(const doc of entries) {
    const button=document.createElement('button');button.className='mc-btn shelf-item';button.dataset.documentId=doc.id;button.dataset.source=doc.source;
    const title=document.createElement('strong');title.textContent=doc.title;
    const stamp=document.createElement('small');stamp.textContent=doc.source==='browser'?(doc.dirty?'Unsaved browser recovery':'Browser copy')+' · '+new Date(doc.ts).toLocaleString():'Revision '+doc.revision+' · '+new Date(doc.updated*1000).toLocaleString();
    button.append(title,stamp);
    if(typeof decorateVersionShelf==='function')decorateVersionShelf(button,doc);
    button.onclick=async()=>{
      try {
        if(!await preserveBeforeSwitch())return;
        if(doc.source==='browser'){
          const candidate=stored(doc.recoveryKey,null)||doc;
          validateDocumentState(candidate.state);
          if(!confirm('Recover this browser copy as an independent manuscript? The original version and other editors will remain untouched.'))return;
          if(await importDocument(new Blob([JSON.stringify({format:'2i-document',version:4,title:String(candidate.title||'Untitled').slice(0,175)+' — browser recovery',state:candidate.state})],{type:'application/json'})))closeModal('reachShelf');
          return;
        }
        const previous=documentId,before=mutation;
        const result=await api('/api/writers-room/documents/'+encodeURIComponent(doc.id));
        validateDocumentState(result.state);
        if(documentId!==previous||mutation!==before||generating||chatSending)throw Error('Editor changed while opening this manuscript. Try again.');
        cancelLLM();stopPlaying();documentId=doc.id;revision=result.revision||0;saveConflict=false;
        documentTitle=String(result.title||'Untitled manuscript').slice(0,200);loadDocState(result.state);documentDirty=false;savedMutation=mutation;
        writeRecovery();setSaveStatus('Saved to Reach · revision '+revision);closeModal('reachShelf');render();
        document.dispatchEvent(new Event('foresight:work-change'));
      } catch(error) {addChat('notice',error.message);}
    };
    shelf.append(button);
  }
  openModal('reachShelf');
}
// Install visible actions after the original v20 handlers have been created.
$('mainArea').appendChild($('chatSection'));
$('chatSendBtn').onclick=sendChat;
$('partnerSelect').onchange=switchPartner;
$('saveBtn').onclick=()=>saveNow();
$('llmPill').onclick=openLLMModal;
$('shelfBtn').onclick=showShelf;
const shelf=document.createElement('div'); shelf.className='modal-backdrop'; shelf.id='reachShelf';
shelf.innerHTML='<div class="modal" role="dialog" aria-label="My manuscripts"><div class="modal-title">My manuscripts</div><div class="shelf-list" id="reachShelfList"></div><div class="modal-actions"><button class="mc-btn" id="shelfClose">Close</button><button class="mc-btn" id="shelfImport">Import .2i</button><button class="mc-btn" id="shelfCopy">Save a copy</button><button class="mc-btn primary" id="shelfNew">New manuscript</button></div></div>';
document.body.append(shelf);
const account=document.createElement('div'); account.className='modal-backdrop'; account.id='reachAccount';
account.innerHTML='<form class="modal" id="reachAccountForm" aria-label="Reach account"><div class="modal-title" id="accountTitle">Welcome to Reach</div><p class="partner-note">Your account keeps your manuscripts and conversations together on this computer.</p><div class="modal-body"><label for="accountName">Username</label><input id="accountName" autocomplete="username" required minlength="3"><label for="accountPassword">Password</label><input id="accountPassword" type="password" autocomplete="current-password" required><div id="accountConfirmGroup"><label for="accountConfirm">Confirm password</label><input id="accountConfirm" type="password" autocomplete="new-password"></div></div><p id="accountError" class="partner-note" role="alert"></p><div class="modal-actions"><button type="submit" class="mc-btn primary" id="accountSubmit">Sign in</button></div></form>';
document.body.append(account);
async function showAccount(setup) {
  $('accountTitle').textContent=setup?'Make Reach your own':'Welcome back';
  $('accountSubmit').textContent=setup?'Create local account':'Sign in';
  $('accountConfirmGroup').hidden=!setup;
  $('accountPassword').autocomplete=setup?'new-password':'current-password';
  $('reachAccountForm').onsubmit=async event=>{
    event.preventDefault(); $('accountSubmit').disabled=true; $('accountError').textContent='';
    try {
      const body={username:$('accountName').value.trim(),password:$('accountPassword').value};
      if(setup)body.confirm_password=$('accountConfirm').value;
      const result=await api('/api/auth/'+(setup?'setup':'login'),{method:'POST',body:JSON.stringify(body)});
      sessionStorage.setItem('pubcast_token',result.access_token);
      llmCfg.pubpartner.token=''; saveLLM(llmCfg); location.reload();
    } catch(error) { $('accountError').textContent=error.message; }
    finally { $('accountSubmit').disabled=false; }
  };
  openModal('reachAccount');
}
$('shelfClose').onclick=()=>closeModal('reachShelf');
$('shelfImport').onclick=()=>{closeModal('reachShelf');openDocument();};
$('shelfNew').onclick=()=>{closeModal('reachShelf');newDocument();};
$('shelfCopy').onclick=async()=>{
  if(typeof createVersionFromCurrent==='function'&&networked&&!saveConflict){
    try{if(await createVersionFromCurrent())closeModal('reachShelf');}catch(error){addChat('notice',error.message);}return;
  }
  // Conflict or offline recovery is an independent copy, not a confirmed
  // server lineage. Keep the local text and isolate live conversation sessions.
  if(!await preserveBeforeSwitch())return;documentId=uuid();revision=0;saveConflict=false;
  conversationIds={};documentTitle=documentTitle.slice(0,193)+' — copy';markDirty();render();await saveDocument();closeModal('reachShelf');
};
// Native textarea undo must stay native while typing. Collab line edits use v20's stack.
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && $('reachAccount').classList.contains('open')){event.preventDefault();event.stopImmediatePropagation();return;}
  if((event.ctrlKey||event.metaKey)&&['z','y'].includes(event.key.toLowerCase())&&[soloTextarea,draftArea,chatInput].includes(document.activeElement)) event.stopImmediatePropagation();
},true);
// Drop is handled once; invalid input cannot partially replace the active document.
document.addEventListener('drop',async event=>{
  if(reachFileMode)return; // The file adapter owns file navigation and import.
  event.preventDefault();event.stopImmediatePropagation();
  const file=event.dataTransfer?.files?.[0]; if(!file)return;
  try {
    if(/\.(2i|json)$/i.test(file.name)) await importDocument(file);
    else if(/\.(md|txt)$/i.test(file.name)) addReference(file.name,'research',await file.text());
  } catch(error) {addChat('notice',error.message);}
},true);
window.addEventListener('pagehide',writeRecovery);
window.addEventListener('beforeunload',event=>{
  if (fileSavingId !== null || chatSending || generating || (documentDirty && !recoverySafe)) {
    event.preventDefault();
    event.returnValue = '';
  }
});
document.addEventListener('visibilitychange',()=>{if(document.hidden){writeRecovery();saveDocument();}});
// Associate the donor's visual labels with their controls for keyboard/screen-reader use.
document.querySelectorAll('.modal label').forEach(label=>{const next=label.nextElementSibling;if(next?.id&&!label.htmlFor)label.htmlFor=next.id;});
async function startReach() {
  init();
  if(networked) {
    try {
      const auth=await api('/api/auth/status');
      if(auth.auth_enforced && (auth.setup_required || !reachHeaders().Authorization)) {
        await showAccount(auth.setup_required); return;
      }
      await connectReach();
    } catch(error) {
      if(error.status===401) { await showAccount(false);return; }
      setSaveStatus('Reach identity unavailable · reload to open your workspace');
      throw error;
    }
  }
  if(reachFileMode){initializing=false;return;}
  const candidates=browserManuscripts();
  const recovery=chooseEditorRecovery({documentId,previousWriter:studioResume?.writer||priorEditorWriter,explicit:!!(requestedDocumentId||studioResume),records:candidates});
  if(candidates.some(r=>r.id===documentId&&r.dirty&&r!==recovery&&r.recoveryKey!==recovery?.recoveryKey))
    addChat('notice','Other unsaved browser copies exist. They remain available separately in My manuscripts; no other editor\'s draft was silently adopted.');
  if(recovery?.id===documentId) {
    try {validateDocumentState(recovery.state);documentTitle=recovery.title;revision=recovery.revision||0;loadDocState(recovery.state);documentDirty=!!recovery.dirty;recoverySafe=true;} catch {addChat('notice','A recovery copy could not be loaded. Use Restore autosave or import your .2i file.');}
  }
  if(networked) {
    try {
      const saved=await api('/api/writers-room/documents/'+encodeURIComponent(documentId));
      if(!documentDirty) {validateDocumentState(saved.state);documentTitle=saved.title;revision=saved.revision;loadDocState(saved.state);writeRecovery();setSaveStatus('Saved to Reach · revision '+revision);}
      else if(saved.revision!==revision) {saveConflict=true;setSaveStatus('Newer Reach copy exists · save a copy');}
    } catch(error) {
      if((requestedDocumentId||studioResume)&&!recoverySafe){
        setSaveStatus('Requested version unavailable · open My manuscripts');
        addChat('notice','The requested manuscript was not loaded. This is a separate empty recovery workspace, not the requested version.');
        // Never turn an unknown or inaccessible explicit version ID into
        // a silent new manuscript using that same identity.
        documentId=uuid();revision=0;saveConflict=false;documentTitle='Untitled recovery workspace';
        loadDocState({committed:[],buffer:[],pool:[],pointer:0,chapters:[{title:'Chapter One',subtitle:'',startLine:0}],lockedLines:[],coWriting:false,references:[],partnerId});
        documentDirty=false;
      }else if(error.status!==404)setSaveStatus(recoverySafe?'Recovered in browser · Reach unavailable':'Writing locally · connect Reach to sync');
    }
  } else setSaveStatus(recoverySafe?'Recovered in this browser':'Writing locally · open through Reach to sync');
  initializing=false;if(documentDirty)writeRecovery();else pinEditorDocument();render();
  if(documentDirty&&!saveConflict) await saveDocument();
}
window.reachStarted=startReach();
