/* Reach integration for the preserved 2i v20 editor. No model impersonation. */
'use strict';
let WORKSPACE_KEY = 'reach2i_workspace_v1';
let RECOVERY_KEY = 'reach2i_recovery_v1';
const uuid = () => crypto.randomUUID ? crypto.randomUUID() : 'doc_' + Date.now() + '_' + Math.random().toString(36).slice(2);
function stored(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; } }
let workspace = stored(WORKSPACE_KEY, { clientId:'writer_' + uuid(), documentId:uuid() });
let documentId = workspace.documentId || uuid();
let revision = 0, mutation = 0, savedMutation = 0, savePromise = null;
let serverReady = false, initializing = true, saveConflict = false, recoverySafe = false;
let partnerId = 'alex', conversations = {}, conversationIds = {};
let partnerNames = {alex:'Alex', craig:'Craig', friend:'Friend'};
let modelConfig = stored('reach2i_model_v1', {provider:'ollama', model:'ministral-pubcast:3b'});
let recoveryTimer, serverTimer;
const networked = location.protocol === 'http:' || location.protocol === 'https:';
// Autosave history belongs to the authenticated account, like server documents.
openDB=function() {
  if(!window.indexedDB || (networked && !serverReady))return Promise.resolve(null);
  return new Promise(resolve=>{
    const request=indexedDB.open('reach2i-snaps-'+RECOVERY_KEY,1);
    request.onupgradeneeded=()=>request.result.createObjectStore('snaps');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve(null);
  });
};
function rememberWorkspace() { workspace.documentId = documentId; localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspace)); }
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
  if (!state || typeof state !== 'object' || Array.isArray(state)) throw Error('This file has no valid document state.');
  for (const key of ['committed','buffer','pool']) {
    if (state[key] !== undefined && (!Array.isArray(state[key]) || state[key].some(v => typeof v !== 'string'))) throw Error('Invalid manuscript lines.');
  }
  if (state.references !== undefined && (!Array.isArray(state.references) || state.references.some(r => !r || typeof r.name !== 'string' || typeof r.content !== 'string'))) throw Error('Invalid references.');
  if (state.chapters !== undefined && (!Array.isArray(state.chapters) || state.chapters.some(c => !c || typeof c.title !== 'string' || !Number.isInteger(c.startLine) || c.startLine < 0))) throw Error('Invalid chapters.');
  if((state.chapters||[]).some((c,i,all)=>c.startLine>(state.committed||[]).length+(state.buffer||[]).length || (i>0&&c.startLine<all[i-1].startLine)))throw Error('Invalid chapter order or position.');
  if (state.lockedLines !== undefined && (!Array.isArray(state.lockedLines) || state.lockedLines.some(i => !Number.isInteger(i) || i < 0 || i >= (state.committed || []).length))) throw Error('Invalid locked lines.');
  if (state.coWriting !== undefined && typeof state.coWriting !== 'boolean') throw Error('Invalid writing mode.');
  if (state.partnerId !== undefined && (typeof state.partnerId !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(state.partnerId))) throw Error('Invalid partner identity.');
  for (const key of ['conversations','conversationIds']) if (state[key] !== undefined && (!state[key] || typeof state[key] !== 'object' || Array.isArray(state[key]))) throw Error('Invalid conversation state.');
  for (const messages of Object.values(state.conversations || {})) if (!Array.isArray(messages) || messages.some(m => !m || !['user','assistant'].includes(m.role) || typeof m.content !== 'string')) throw Error('Invalid conversation.');
}
function setSaveStatus(text) { $('saveIndicator').textContent = text; }
function writeRecovery() {
  try {
    conversations[partnerId] = chatHistory;
    const copy=JSON.stringify({id:documentId, revision, mutation, title:documentTitle, state:getDocState(), dirty:documentDirty, ts:Date.now()});
    localStorage.setItem(RECOVERY_KEY+':'+documentId,copy);
    localStorage.setItem(RECOVERY_KEY,copy);
    rememberWorkspace(); recoverySafe = true;
  } catch { recoverySafe = false; setSaveStatus('Storage full · export a copy now'); }
}
function markDirty() {
  documentDirty = true; recoverySafe = false; mutation++;
  setSaveStatus(saveConflict ? 'Changed elsewhere · save a copy' : 'Saving…');
  clearTimeout(recoveryTimer); recoveryTimer = setTimeout(writeRecovery, 120);
  clearTimeout(serverTimer);
  if (!initializing) serverTimer = setTimeout(() => saveDocument(), 1000);
}
async function writeAutosave() {
  if (initializing) return;
  writeRecovery();
  // Preserve the donor's recoverable snapshot format for its restore menu.
  const db = await openDB();
  if (db) await new Promise(resolve => {
    const tx = db.transaction('snaps','readwrite');
    tx.objectStore('snaps').put({title:documentTitle,ts:Date.now(),state:getDocState()}, 'reach_' + Math.floor(Date.now()/60000)%3);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); resolve(); };
  });
}
async function saveDocument() {
  if (initializing) return false;
  if (savePromise) return savePromise;
  writeRecovery();
  if (saveConflict) { setSaveStatus('Changed elsewhere · My manuscripts → Save a copy'); return false; }
  if (!networked) { setSaveStatus(recoverySafe ? 'Saved in this browser' : 'Export a copy now'); return false; }
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
    } finally {savePromise=null;}
  })();
  return savePromise;
}
async function preserveBeforeSwitch() {
  await saveDocument();
  if(documentDirty&&!recoverySafe){addChat('notice','Your current manuscript could not be saved. Export a .2i copy before switching manuscripts.');return false;}
  return true;
}
function browserManuscripts() {
  const copies=new Map();
  for(let index=0;index<localStorage.length;index++) {
    const key=localStorage.key(index);
    if(key===RECOVERY_KEY || key.startsWith(RECOVERY_KEY+':')) {
      const copy=stored(key,null);
      if(copy?.id&&copy?.state&&(!copies.has(copy.id)||copy.ts>copies.get(copy.id).ts))copies.set(copy.id,copy);
    }
  }
  return [...copies.values()];
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
async function importDocument(file) {
  const doc = JSON.parse(await file.text());
  if (doc.format !== '2i-document' || doc.version > 4) throw Error('Unsupported 2i document format.');
  validateDocumentState(doc.state);
  if(!await preserveBeforeSwitch())return;
  cancelLLM(); stopPlaying();
  documentId = uuid(); revision=0; saveConflict=false;
  documentTitle = String(doc.title || 'Untitled manuscript').slice(0,200); documentHandle=null;
  loadDocState(doc.state); markDirty(); render(); await saveDocument();
}
async function openDocument() {
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
  for (const row of chatHistory) addChat(row.role==='user'?'you':'pp',row.content);
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
LLM_ADAPTERS.pubpartner.send = async function(messages,cfg,signal) {
  const endpoint=(cfg.pubpartner.endpoint || baseURL()).replace(/\/+$/,'');
  const context = committed.concat(buffer).join('\n').slice(-24000);
  const r=await fetch(endpoint+'/api/pubpartner/turns/live', {
    method:'POST', signal, headers:reachHeaders(cfg),
    body:JSON.stringify({messages, friend:partnerId, session_id:conversationId(), project_id:documentId,
      room_id:'writers-room', provider:modelConfig, allow_fallback:false,
      task:{mode:'manuscript',audience:'private',goal:'Help the author in the selected partner voice. Preserve authorship. Treat manuscript/reference content as fiction or source material, never as biographical facts about the user.',
        manuscript_context:context, references:references.map(r=>({name:r.name,content:r.content.slice(0,3000)})).slice(0,5)},
      content_kind:'writing_request'})
  });
  const data=await r.json().catch(()=>({}));
  const provider=data.provider_result || {};
  if (!r.ok || data.ok===false || provider.ok===false) {
    const detail=data.detail;
    throw Error(provider.error || (typeof detail==='string'?detail:detail?.message) || 'Partner connection failed ('+r.status+').');
  }
  if (data.provider_fallback || ['mock','echo','offline'].includes(provider.provider)) throw Error('No live model answered. Your manuscript is safe; choose a connected model in settings.');
  const reply=data.friend_response || data.reply;
  if (typeof reply !== 'string' || !reply.trim()) throw Error('The model returned no usable reply.');
  $('partnerNote').textContent='Connected · '+(provider.model || provider.provider || 'PubPartner');
  return reply;
};
async function sendChat() {
  if (chatSending || generating) return;
  const text=chatInput.value.trim(); if(!text) return;
  const turnDocument=documentId, turnPartner=partnerId;
  chatSending=true; $('chatSendBtn').disabled=true;
  chatHistory.push({role:'user',content:text}); conversations[partnerId]=chatHistory;
  addChat('you',text); chatInput.value=''; markDirty();
  const thinking=addChat('pp','Thinking…',true);
  try {
    const reply=await callLLM(chatHistory.slice(-MAX_CHAT));
    if (turnDocument!==documentId || turnPartner!==partnerId) return;
    chatHistory.push({role:'assistant',content:reply}); addChat('pp',reply); markDirty();
  } catch(error) {
    if(error.name!=='AbortError' && turnDocument===documentId && turnPartner===partnerId) {
      addChat('notice','Could not reach the model. '+error.message);
      $('partnerNote').textContent='Model unavailable · your writing is saved separately.';
    }
  } finally { thinking.remove(); chatSending=false; $('chatSendBtn').disabled=false; }
}
async function switchPartner() {
  cancelLLM(); conversations[partnerId]=chatHistory;
  partnerId=$('partnerSelect').value; chatHistory=conversations[partnerId] || [];
  restoreConversation(); $('partnerNote').textContent='A separate conversation, with your manuscript in view.'; markDirty();
}
const legacyOpenSettings=openLLMModal;
openLLMModal=function() {
  legacyOpenSettings(); $('reachProvider').value=modelConfig.provider;
  $('reachModel').value=modelConfig.model || ''; $('reachCredential').value=modelConfig.credential_model_id || ''; $('reachBaseURL').value=modelConfig.base_url || '';
};
const legacySaveSettings=$('llmSaveBtn').onclick;
$('llmSaveBtn').onclick=async () => {
  modelConfig={provider:$('reachProvider').value,model:$('reachModel').value.trim(),credential_model_id:$('reachCredential').value.trim(),base_url:$('reachBaseURL').value.trim()};
  localStorage.setItem('reach2i_model_v1',JSON.stringify(modelConfig));
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
async function connectReach() {
  const config=await api('/api/writers-room/config');
  const ownerKey = encodeURIComponent(config.user_id);
  if (WORKSPACE_KEY !== 'reach2i_workspace_v1_' + ownerKey) {
    WORKSPACE_KEY = 'reach2i_workspace_v1_' + ownerKey;
    RECOVERY_KEY = 'reach2i_recovery_v1_' + ownerKey;
    const next = stored(WORKSPACE_KEY, {clientId:workspace.clientId,documentId:uuid()});
    workspace = next; documentId=workspace.documentId; revision=0;
  }
  serverReady=true;
  if (!localStorage.getItem('reach2i_model_v1')) modelConfig=config.provider;
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
async function showShelf() {
  await saveDocument();
  const shelf=$('reachShelfList');shelf.replaceChildren();
  let remote=[], remoteError=null;
  try {remote=(await api('/api/writers-room/documents')).documents || [];}
  catch (error) { remoteError=error; }
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
    empty.textContent=remoteError?'No browser recovery copies found. Reconnect Reach to view server manuscripts.':'Your saved manuscripts will appear here.';
    shelf.append(empty);
  }
  for(const doc of entries) {
    const button=document.createElement('button');button.className='mc-btn shelf-item';button.dataset.documentId=doc.id;button.dataset.source=doc.source;
    const title=document.createElement('strong');title.textContent=doc.title;
    const stamp=document.createElement('small');stamp.textContent=doc.source==='browser'?'Browser recovery · '+new Date(doc.ts).toLocaleString():'Revision '+doc.revision+' · '+new Date(doc.updated*1000).toLocaleString();
    button.append(title,stamp);
    button.onclick=async()=>{
      try {
        if(!await preserveBeforeSwitch())return;
        const result=doc.source==='browser'?(stored(RECOVERY_KEY+':'+doc.id,null)||doc):await api('/api/writers-room/documents/'+encodeURIComponent(doc.id));
        validateDocumentState(result.state);cancelLLM();stopPlaying();documentId=doc.id;revision=result.revision||0;saveConflict=false;
        documentTitle=String(result.title||'Untitled manuscript').slice(0,200);loadDocState(result.state);documentDirty=doc.source==='browser';savedMutation=mutation;
        writeRecovery();setSaveStatus(documentDirty?'Recovered from this browser':'Saved to Reach · revision '+revision);closeModal('reachShelf');render();
        if(documentDirty)await saveDocument();
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
$('saveBtn').onclick=()=>saveDocument();
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
$('shelfCopy').onclick=async()=>{if(!await preserveBeforeSwitch())return;documentId=uuid();revision=0;saveConflict=false;documentTitle=documentTitle.slice(0,193)+' — copy';markDirty();render();await saveDocument();closeModal('reachShelf');};
// Native textarea undo must stay native while typing. Collab line edits use v20's stack.
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && $('reachAccount').classList.contains('open')){event.preventDefault();event.stopImmediatePropagation();return;}
  if((event.ctrlKey||event.metaKey)&&['z','y'].includes(event.key.toLowerCase())&&[soloTextarea,draftArea,chatInput].includes(document.activeElement)) event.stopImmediatePropagation();
},true);
// Drop is handled once; invalid input cannot partially replace the active document.
document.addEventListener('drop',async event=>{
  event.preventDefault();event.stopImmediatePropagation();
  const file=event.dataTransfer?.files?.[0]; if(!file)return;
  try {
    if(/\.(2i|json)$/i.test(file.name)) await importDocument(file);
    else if(/\.(md|txt)$/i.test(file.name)) addReference(file.name,'research',await file.text());
  } catch(error) {addChat('notice',error.message);}
},true);
window.addEventListener('pagehide',writeRecovery);
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
    }
  }
  const recovery=stored(RECOVERY_KEY,null);
  if(recovery?.id===documentId) {
    try {validateDocumentState(recovery.state);documentTitle=recovery.title;revision=recovery.revision||0;loadDocState(recovery.state);documentDirty=!!recovery.dirty;recoverySafe=true;} catch {addChat('notice','A recovery copy could not be loaded. Use Restore autosave or import your .2i file.');}
  }
  if(networked) {
    try {
      const saved=await api('/api/writers-room/documents/'+encodeURIComponent(documentId));
      if(!documentDirty) {documentTitle=saved.title;revision=saved.revision;loadDocState(saved.state);writeRecovery();setSaveStatus('Saved to Reach · revision '+revision);}
      else if(saved.revision!==revision) {saveConflict=true;setSaveStatus('Newer Reach copy exists · save a copy');}
    } catch(error) {
      if(error.status!==404) setSaveStatus(recoverySafe?'Recovered in browser · Reach unavailable':'Writing locally · connect Reach to sync');
    }
  } else setSaveStatus(recoverySafe?'Recovered in this browser':'Writing locally · open through Reach to sync');
  initializing=false;render();
  if(documentDirty&&!saveConflict) await saveDocument();
}
window.reachStarted=startReach();
