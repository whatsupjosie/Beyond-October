/* Shared file working copies. Tray geometry belongs to Counter; bytes belong here. */
(function(root){
'use strict';
const DB='pubcast-foresight-files-v1', STORE='files';
let database, ownerPromise, ownerCredential;
function newId(){
  if(root.crypto?.randomUUID)return root.crypto.randomUUID();
  if(!root.crypto?.getRandomValues)throw Error('Secure random IDs unavailable');
  const bytes=root.crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function credential(){return sessionStorage.getItem('pubcast_token')||localStorage.getItem('pubpartner.auth.token.v1')||''}
async function ownerScope(){
  const token=credential();
  if(ownerPromise && token!==ownerCredential)throw Error('Reach account changed. Reload before accessing working copies.');
  if(!ownerPromise){
    ownerCredential=token;
    ownerPromise=(async()=>{
      const response=await fetch('/api/writers-room/config',{headers:headers()});
      if(!response.ok)throw Error('Sign in to Reach before accessing working copies.');
      const config=await response.json();
      if(typeof config.user_id!=='string'||!config.user_id.trim())throw Error('Reach did not confirm the working-copy owner.');
      return encodeURIComponent(config.user_id);
    })();
    ownerPromise.catch(()=>{ownerPromise=null});
  }
  return ownerPromise;
}
async function db(){
  const owner=await ownerScope();
  if(!database) database=new Promise((resolve,reject)=>{
    const r=indexedDB.open(DB+':'+owner,1);
    r.onupgradeneeded=()=>r.result.createObjectStore(STORE,{keyPath:'id'});
    r.onsuccess=()=>{r.result.onversionchange=()=>{r.result.close();database=null};resolve(r.result)};
    r.onerror=()=>{database=null;reject(r.error)};
    r.onblocked=()=>{database=null;reject(Error('Close other PubCast tabs to upgrade file storage'))};
  });
  return database;
}
// Exit journal. A checked save reads the revision and writes only in the read's callback, which never runs
// once a page is being torn down, so unsaved text at reload, close or tab kill was lost. On page hide/unload
// the unsaved snapshot is written here synchronously instead, then applied on the next open through the
// normal checked save. It is a separate database so the file shelf (list()) never shows it as a file, and
// it never overwrites the real record, so a closing stale window cannot clobber a newer save.
const EXIT_DB='pubcast-foresight-exit-v1', EXIT_STORE='exit';
let exitDatabase, exitConnection=null;
async function exitDb(){
  const owner=await ownerScope();
  if(!exitDatabase) exitDatabase=new Promise((resolve,reject)=>{
    const r=indexedDB.open(EXIT_DB+':'+owner,1);
    r.onupgradeneeded=()=>r.result.createObjectStore(EXIT_STORE,{keyPath:'id'});
    r.onsuccess=()=>{r.result.onversionchange=()=>{r.result.close();exitDatabase=null;exitConnection=null};exitConnection=r.result;resolve(r.result)};
    r.onerror=()=>{exitDatabase=null;reject(r.error)};
    r.onblocked=()=>{exitDatabase=null;reject(Error('Close other PubCast tabs to upgrade file storage'))};
  });
  return exitDatabase;
}
async function exitEntry(id,remove){
  const d=await exitDb();
  return new Promise((resolve,reject)=>{
    const tx=d.transaction(EXIT_STORE,remove?'readwrite':'readonly'),store=tx.objectStore(EXIT_STORE);let result;
    if(remove)store.delete(id);else{const r=store.get(id);r.onsuccess=()=>{result=r.result}}
    tx.oncomplete=()=>resolve(result);tx.onabort=tx.onerror=()=>reject(tx.error||Error('Exit journal failed'));
  });
}
// No await anywhere: the put is queued in the same task as pagehide, before the page goes away.
function writeExitEntryNow(entry){
  if(!exitConnection)return false;
  const tx=exitConnection.transaction(EXIT_STORE,'readwrite');tx.objectStore(EXIT_STORE).put(entry);tx.commit?.();
  return true;
}
async function record(id,value,expected){
  const d=await db();
  return new Promise((resolve,reject)=>{
    const tx=d.transaction(STORE,value?'readwrite':'readonly'),store=tx.objectStore(STORE);
    let result,error;
    if(value&&expected!==undefined){
      const read=store.get(id);
      read.onsuccess=()=>{
        if((read.result?.revision||0)!==expected){error=Error('This working copy changed in another window. Export your edits before reopening it.');tx.abort();return;}
        result={...value,revision:expected+1};store.put(result);
      };
    }else{const r=value?store.put(value):store.get(id);r.onsuccess=()=>{result=value||r.result};}
    tx.oncomplete=()=>resolve(result);
    tx.onabort=tx.onerror=()=>reject(error||tx.error||Error('File storage failed'));
  });
}

function node(tag,attrs={},text){
  const n=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs)) {if(k==='style')n.style.cssText=v;else n.setAttribute(k,v)}
  if(text!==undefined)n.textContent=text;
  return n;
}
function download(name,blob){
  const a=node('a',{download:name,href:URL.createObjectURL(blob)});document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),30000);
}
function headers(){
  const token=sessionStorage.getItem('pubcast_token')||localStorage.getItem('pubpartner.auth.token.v1');
  return token?{Authorization:'Bearer '+token}:{};
}
async function api(path,body){
  const r=await fetch('/api/foresight/files/'+path,{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok){let d;try{d=await r.json()}catch{}throw Error(typeof d?.detail==='string'?d.detail:'File service returned HTTP '+r.status)}
  return r;
}
async function workspace(path,body){
  const r=await fetch('/api/foresight/workspace/'+path,{method:body?'POST':'GET',headers:{...headers(),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
  if(!r.ok){let d;try{d=await r.json()}catch{}throw Error(typeof d?.detail==='string'?d.detail:'Local workspace returned HTTP '+r.status)}
  return r.json();
}
async function base64(blob){
  return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(r.error);r.readAsDataURL(blob)});
}
const ext=name=>(String(name).match(/\.([^.]+)$/)||[])[1]?.toLowerCase()||'';
// Rich .2i v5 archives are binary, unlike manuscript v4 JSON. Never hand them
// to the text conversion path or silently flatten their formatted DOCX bytes.
async function isRich2i(blob){
  if(!blob||blob.size<4)return false;
  const prefix=new Uint8Array(await blob.slice(0,4).arrayBuffer());
  return prefix[0]===0x50&&prefix[1]===0x4b&&prefix[2]===0x03&&prefix[3]===0x04;
}
function decodedBlob(b64,type){
  const raw=atob(b64);
  const bytes=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
  return new Blob([bytes],{type});
}
async function decodeText(blob){
  if(blob.size>5*1024*1024)throw Error('Text exceeds the 5 MB editor limit. Original remains available.');
  const bytes=new Uint8Array(await blob.arrayBuffer());let encoding='utf-8';
  if(bytes[0]===255&&bytes[1]===254)encoding='utf-16le';
  if(bytes[0]===254&&bytes[1]===255)encoding='utf-16be';
  const text=new TextDecoder(encoding,{fatal:true}).decode(bytes);
  if(text.includes('\0'))throw Error('This appears to be a binary file; no text conversion was applied.');
  return text;
}
const sessions=new WeakMap();
async function mount(c,host,file,options={}){
  const body=host.body;body.replaceChildren();
  const wrap=node('div',{'class':'ff-workspace',style:'display:flex;flex-direction:column;height:100%;min-height:0;padding:12px;box-sizing:border-box;color:#efdfc2;gap:8px'});
  const bar=node('div',{style:'display:flex;flex-wrap:wrap;gap:6px'}),status=node('div',{role:'status',style:'font-size:12px;white-space:pre-wrap'}),area=node('div',{style:'flex:1;min-height:0;overflow:auto'});
  wrap.append(bar,status,area);body.append(wrap);
  let alive=true, value, editor, image, canvas, url, handle, timer, saving=Promise.resolve(), serial=0, diagnosticVersion=-1, changed=false, processing=Promise.resolve();
  let richMode=false,richSource=null,richEditor=null,richOpening=false,richMetadataDirty=false,opening=true;
  let localSaveError=false,writing=0,imageWrites=0,queuedPlain=null,exitWritten=false,exitListeners=null;
  function richMetadataChanged(){if(richMode){richMetadataDirty=true;serial++;}}
  const say=s=>{if(alive)status.textContent=s};
  function button(label,fn){const b=node('button',{type:'button',class:'fp-btn'},label);b.onclick=()=>Promise.resolve().then(fn).catch(e=>say(e.message));bar.append(b);return b}
  function snapshot(){if(richMode)return {...value,updated:Date.now()};return {...value,draft:editor?(options.getText?.()??editor.value):value.draft,title:options.getTitle?.()||value.title,twoiState:options.getState?{...value.twoiState,...structuredClone(options.getState())}:value.twoiState,updated:Date.now()}}
  function persistRaw(){
    if(!value)return Promise.reject(Error('File has not finished opening'));
    clearTimeout(timer);
    if(richMode&&!richEditor&&!changed&&!richMetadataDirty)return Promise.resolve(value);
    if(richMode&&richEditor){
      saving=saving.catch(()=>{}).then(async()=>{
        if(!changed&&!richMetadataDirty)return value;
        const version=serial,capture=changed;
        let docx=null;
        if(capture){
          const raw=await richEditor.saveBytes();
          docx=new Blob([raw],{type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
          if(docx.size>24*1024*1024)throw Error("Working DOCX exceeds the 24 MiB archive limit. Download your edited DOCX before closing.");
        }
        const v=docx?{...snapshot(),richDraft:docx,richDraftDocumentId:richSource.document_id,richDraftSourceHash:richSource.original_sha256}:snapshot();
        const saved=await record(v.id,v,value.revision||0);
        if(docx){value.richDraft=docx;value.richDraftDocumentId=v.richDraftDocumentId;value.richDraftSourceHash=v.richDraftSourceHash;}
        value.revision=saved.revision;
        if(serial===version){changed=false;richMetadataDirty=false;say("Formatted working copy saved in this browser · source archive unchanged");}
        return v;
      });
      return saving;
    }
    // Coalesce plain saves. A save that is queued but has not started yet takes its snapshot when it
    // starts, so it already contains every edit made before this call; join it rather than queue another
    // record write. Edits made after it starts are covered by a later run.
    if(queuedPlain)return queuedPlain;
    const run=saving.catch(()=>{}).then(()=>{
      queuedPlain=null;
      const v=snapshot(),version=serial;
      return record(v.id,v,value.revision||0).then(saved=>{value.revision=saved.revision;if(serial===version){changed=false;richMetadataDirty=false;if(exitWritten){exitWritten=false;exitEntry(v.id,true).catch(e=>console.error('Exit journal cleanup failed',e))}if(diagnosticVersion!==version)say(richMode?'Rich working copy saved in this browser · source archive unchanged':handle?'Saved to chosen file and PubCast · source snapshot retained':'Working copy saved in PubCast · source snapshot retained')}return v});
    });
    queuedPlain=run;saving=run;
    return run;
  }
  function persist(){
    if(opening||richOpening)return Promise.reject(Error('Wait for this file to finish opening.'));
    writing++;
    return Promise.resolve().then(persistRaw).then(result=>{localSaveError=false;return result;},error=>{localSaveError=true;throw error;}).finally(()=>{writing--;});
  }
  function dirty(){serial++;changed=true;say('Unsaved changes');host.changed();clearTimeout(timer);timer=setTimeout(()=>persist().catch(e=>{say('Save failed: '+e.message);options.onSaveError?.(e.message)}),richMode?1500:350)}
  function checkedRichDraft(){
    if(!value.richDraft)return null;
    if(!richSource||value.richDraftDocumentId!==richSource.document_id||!richSource.original_sha256||value.richDraftSourceHash!==richSource.original_sha256)throw Error("Recovered DOCX identity does not match the preserved source. Download original and recovery separately; no replacement was made.");
    return value.richDraft;
  }
  async function currentRichDocx(){
    if(richEditor&&changed)return new Blob([await richEditor.saveBytes()],{type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
    return checkedRichDraft()||decodedBlob(richSource.working_docx_b64,"application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  }
  async function richArchiveOutput(){
    if(!richSource)throw Error("Rich archive has not been verified.");
    if(!changed&&!value.richDraft)return value.original;
    const working=await currentRichDocx(),data=await base64(working);
    return packVerifiedRich({document_id:richSource.document_id,original_name:richSource.original_name,original_mime:richSource.original_mime,original_data_b64:richSource.original_data_b64,working_docx_b64:data,metadata:richSource.metadata||{}});
  }
  async function packVerifiedRich(payload){
    const packed=await (await api("native-rich/create",payload)).json();
    if(packed.kind!=="rich-v5"||typeof packed.data_b64!=="string")throw Error("Rich archive packaging failed; the original remains unchanged.");
    const archive=decodedBlob(packed.data_b64,"application/zip");
    if(archive.size!==packed.size||!root.crypto?.subtle)throw Error("Could not verify exported archive size or integrity.");
    const hash=Array.from(new Uint8Array(await root.crypto.subtle.digest("SHA-256",await archive.arrayBuffer())),b=>b.toString(16).padStart(2,"0")).join("");
    if(hash!==packed.sha256)throw Error("Exported rich archive failed integrity verification.");
    return archive;
  }
  async function output(format){
    await processing;
    if(richMode)return richArchiveOutput();
    if(!format&&editor&&ext(value.name)==='2i')format='2i';
    if(editor){
      if(format==='2i')return new Blob([JSON.stringify({format:'2i-document',version:4,title:options.getTitle?.()||value.title||value.name,state:{...value.twoiState,...options.getState?.()}},null,2)],{type:'application/json'});
      if(format==='docx')return (await api('export',{text:options.getText?.()??editor.value,format})).blob();
      return new Blob([options.getText?.()??editor.value],{type:'text/plain;charset=utf-8'});
    }
    return value.working||value.original;
  }
  function outputName(format){
    const name=value.name;
    if(richMode)return /\.2i$/i.test(name)?name:name.replace(/\.[^.]*$/,'')+'.2i';
    if(format==='docx')return name.replace(/\.[^.]*$/,'')+'.docx';
    if(editor&&value.converted)return name.replace(/\.[^.]*$/,'')+'.txt';
    if(value.working)return name.replace(/\.[^.]*$/,'')+'.png';
    return name;
  }
  async function saveAs(){
    // Obtain the native handle during the user gesture; generating a document can be asynchronous.
    const name=outputName();let picked;
    if(root.showSaveFilePicker) {try{picked=await root.showSaveFilePicker({suggestedName:name})}catch(e){if(e.name==='AbortError')return;throw e}}
    const target=ext(picked?.name||name);
    if(richMode&&target!=='2i')throw Error('Choose a .2i archive destination. Use Download working DOCX for Word format.');
    const format=editor&&['docx','2i'].includes(target)?target:undefined;
    if(editor&&['pdf','png','jpg','jpeg','xlsx','pptx','doc','odt','zip'].includes(target))throw Error('Use a text, DOCX or 2i destination for this editable copy; this format cannot be written.');
    if(canvas&&target!=='png')throw Error('Edited images must be saved as PNG; choose a .png destination.');
    const blob=await output(format);
    if(picked){const stream=await picked.createWritable();try{await stream.write(blob);await stream.close()}catch(e){await stream.abort().catch(()=>{});throw e}handle=picked;delete value.workspace;value.handle=handle;value.savedFormat=format;value.name=picked.name;c.data.name=value.name;host.setTitle(value.name);richMetadataChanged();say('Saved file: '+picked.name)}
    else {download(name,blob);say('Copy downloaded · destination follows your browser settings')}

    await persist();
  }
  async function saveToWorkspace(){
    const chosen=prompt('Save in your local PubCast workspace. Use folders such as Scripts/example.py.',value.workspace?.path||outputName());
    if(chosen===null)return false;
    const path=chosen.trim();if(!path)throw Error('Enter a filename');
    const target=ext(path),format=editor&&['docx','2i'].includes(target)?target:undefined;
    if(richMode&&target!=='2i')throw Error('Choose a .2i archive filename. Use Download working DOCX for Word format.');
    if(editor&&['pdf','png','jpg','jpeg','xlsx','pptx','doc','odt','zip'].includes(target))throw Error('Choose a text, DOCX or 2i filename for this text copy.');
    if(value.working&&target!=='png')throw Error('Edited images are saved as PNG.');
    const saved=await workspace('file',{path,data:await base64(await output(format)),expected_revision:value.workspace?.path===path?value.workspace.revision:null});
    value.workspace={path:saved.path,revision:saved.revision,format};handle=undefined;delete value.handle;richMetadataChanged();await persist();say('Saved local file: '+saved.path);return true;
  }
  async function save(){
    if(opening||richOpening)throw Error('Wait for this file to finish opening.');
    await processing;
    if(richMode)return persist(); // Explicit export writes files; ordinary Save retains the working copy locally.
    if(value.workspace){const saved=await workspace('file',{path:value.workspace.path,data:await base64(await output(value.workspace.format)),expected_revision:value.workspace.revision});value.workspace.revision=saved.revision;await persist();say('Saved local file: '+saved.path);return true;}
    if(handle){if(handle.queryPermission&&await handle.queryPermission({mode:'readwrite'})!=='granted'&&await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('File permission was not granted. Use Save As to choose a destination.');const blob=await output(value.savedFormat);const stream=await handle.createWritable();try{await stream.write(blob);await stream.close()}catch(e){await stream.abort().catch(()=>{});throw e}}
    return persist();
  }
  function fileActivity(){const dirty=!!(changed||richMetadataDirty),busy=opening||richOpening||writing>0||imageWrites>0;return {dirty,busy,recovery:!!value&&!dirty&&!busy&&!localSaveError};}
  async function prepareClose(){
    if(!alive||opening||richOpening)return false;
    const version=serial;
    await save();
    const status=fileActivity();
    return alive&&serial===version&&!status.dirty&&!status.busy&&status.recovery;
  }
  const session={save,prepareClose,activity:fileActivity,export:async()=>{const data=await output();return {name:outputName(),data,type:data.type}},
    pending:()=>{const s=fileActivity();return s.dirty||s.busy||!s.recovery;},dispose:()=>{alive=false;clearTimeout(timer);exitListeners?.();if(value)persist().catch(console.error).finally(()=>richEditor?.destroy());else richEditor?.destroy();if(url)URL.revokeObjectURL(url);if(image)image.src='';const media=area.querySelector('video,audio');if(media){media.pause();media.removeAttribute('src');media.load()}},
    flush:persist,saveAs:saveToWorkspace};
  sessions.set(c,session);
  try{
    c.data.fileId=c.data.fileId||newId();host.changed();
    value=await record(c.data.fileId);
    if(!value&&file){value={id:c.data.fileId,name:file.name,mime:file.type,original:file,updated:Date.now()};await record(value.id,value)}
    if(!alive)return session;
    if(!value){say('No saved file bytes found. Choose the file again using Import.');return session}
    handle=value.handle;
    options.onReady?.(value);
    button('Local account…',async()=>{if(!await prepareClose())throw Error('The file changed or has unfinished work. Save it before switching accounts.');const top=window.top;top.location.assign('/login?next='+encodeURIComponent(top.location.pathname+top.location.search))});
    const saveControl=button('Save',()=>session.save());button('Save As…',saveToWorkspace);button('Save to device…',saveAs);
    button('Download original',()=>download(value.original.name||value.name,value.original));
    button('Rename working copy',async()=>{const n=prompt('Working copy filename',value.name);if(n?.trim()){const name=n.trim().replace(/[\\/]/g,'_').slice(0,255);if(richMode&&ext(name)!=='2i')throw Error('A rich archive must keep its .2i extension.');value.name=name;c.data.name=value.name;host.setTitle(value.name);richMetadataChanged();await persist();host.changed()}});
    const extension=ext(value.name), mime=value.mime||'';
    if(extension==='2i'&&await isRich2i(value.original)){
      richMode=true;saveControl.textContent='Save working copy locally';
      // Authenticated reader verifies strict membership, digest, version and bounds.
      // A bad or future archive remains downloadable, never partially imported.
      say('Verifying rich 2i document…');
      const rich=await (await api('native-rich/read',{data_b64:await base64(value.original)})).json();
      if(rich.kind!=='rich-v5')throw Error('Unsupported rich document version');
      richSource=rich;
      if(!alive)return session;
      options.onPreview?.(true);
      area.style.display='block';
      area.replaceChildren();
      area.append(node('h2',{},typeof rich.metadata?.title==='string'?rich.metadata.title:rich.original_name));
      area.append(node('p',{},'The source and formatted working DOCX are separately recoverable. Open the optional local rich editor if installed. Never silently convert this archive to plain text.'));
      area.append(node('p',{},'Document ID: '+rich.document_id));
      button('Download preserved source',()=>download(rich.original_name,decodedBlob(rich.original_data_b64,rich.original_mime)));
      button('Download working DOCX',async()=>download(rich.original_name.replace(/\.[^.]+$/,'')+'-working.docx',await currentRichDocx()));
      button('Download verified rich 2i',async()=>download(outputName(),await richArchiveOutput()));
      if(value.richDraft){button('Download local recovery DOCX',()=>download('recovered-working.docx',value.richDraft));button('Download original working revision',()=>download('source-working.docx',decodedBlob(rich.working_docx_b64,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')));}
      const open=button('Open local rich editor',async()=>{
        if(richOpening||richEditor)return;
        if(!rich.original_sha256)throw Error('Verified source identity is unavailable. Use the download controls; the source is unchanged.');
        richOpening=true;open.disabled=true;
        try{
          const working=await currentRichDocx();
          if(value.richDraft&&!confirm('Open the saved local DOCX recovery for this source archive? The original remains separately downloadable.'))return;
          const {mountRichEditor}=await import('/2i-assets/rich-editor.js');
          if(!alive)return;
          const editArea=node('div',{style:'height:100%;min-height:420px'});
          area.append(editArea);
          let candidate;
          try{candidate=await mountRichEditor({container:editArea,bytes:new Uint8Array(await working.arrayBuffer()),onChange:()=>{if(alive)dirty();},onSave:()=>persist(),onError:e=>say(String(e?.message||e))});}
          catch(e){editArea.remove();throw e;}
          if(!alive){candidate.destroy();return;}
          richEditor=candidate;for(const n of [...area.children])if(n!==editArea)n.remove();
          say('Formatted editor open · local working copy autosaves · export a verified rich 2i archive or edited DOCX explicitly');
        }catch(error){say('Local rich editing unavailable: '+error.message+' · original and working download controls remain available.');}
        finally{richOpening=false;open.disabled=!!richEditor;}
      });
      if(value.richDraft){try{checkedRichDraft();say('A local saved DOCX recovery is available. The source archive is retained.');}catch(error){say(error.message);}}
      else say('Rich 2i archive verified · source and formatted working revision preserved · read-only until the local rich editor is opened');
      return session;
    }
    if(mime.startsWith('image/')||/^(png|jpe?g|gif|webp|bmp|svg|avif)$/.test(extension)){
      options.onImage?.();
      image=new Image();url=URL.createObjectURL(value.working||value.original);
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('This image cannot be decoded by your browser'));image.src=url});
      if(!alive)return session;
      canvas=node('canvas',{'aria-label':'Image editor',style:'max-width:100%;height:auto'});canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
      if(canvas.width*canvas.height>40000000)throw Error('Image exceeds the 40-megapixel editing limit');
      canvas.getContext('2d').drawImage(image,0,0);area.append(canvas);

      async function commit(){
        const version=++serial;changed=true;
        const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('Could not encode image')),'image/png'));
        if(version!==serial)return;
        value.working=blob;await persist();
      }
      function imageAction(fn){imageWrites++;processing=processing.catch(()=>{}).then(async()=>{if(fn()!==false)await commit()}).finally(()=>{imageWrites--;});return processing}
      function rotate(){return imageAction(()=>{const copy=node('canvas');copy.width=canvas.width;copy.height=canvas.height;copy.getContext('2d').drawImage(canvas,0,0);canvas.width=copy.height;canvas.height=copy.width;const ctx=canvas.getContext('2d');ctx.translate(canvas.width,0);ctx.rotate(Math.PI/2);ctx.drawImage(copy,0,0)})}
      button('Rotate 90°',rotate);
      button('Crop…',()=>imageAction(()=>{
        const raw=prompt('Crop rectangle in pixels: left, top, width, height',`0, 0, ${canvas.width}, ${canvas.height}`);if(raw===null)return false;
        const v=raw.split(',').map(x=>Number(x.trim()));
        if(v.length!==4||!v.every(Number.isInteger)||v[0]<0||v[1]<0||v[2]<1||v[3]<1||v[0]+v[2]>canvas.width||v[1]+v[3]>canvas.height)throw Error('Crop must be a rectangle inside the image');
        const pixels=canvas.getContext('2d').getImageData(...v);canvas.width=v[2];canvas.height=v[3];canvas.getContext('2d').putImageData(pixels,0,0);
      }));
      const oldSave=session.save;session.save=async()=>{await processing;return oldSave()};session.flush=session.save;
      const oldExport=session.export;session.export=async()=>{await processing;return oldExport()};
      say('Image ready · edits save as a PNG working copy · original retained');
    }else if(mime.startsWith('video/')||mime.startsWith('audio/')||/^(mp4|webm|mov|m4v|ogv|mp3|wav|m4a|ogg|flac)$/.test(extension)){
      const media=node(mime.startsWith('audio/')||/^(mp3|wav|m4a|ogg|flac)$/.test(extension)?'audio':'video',{controls:'',style:'max-width:100%;max-height:100%'});
      url=URL.createObjectURL(value.original);media.src=url;media.onerror=()=>say('Your browser cannot decode this media format. Original retained.');area.append(media);say('Media ready · original saved for reopening');
    }else{
      if(value.draft===undefined&&extension==='2i'){if(value.original.size>5*1024*1024)throw Error('2i document exceeds the 5 MB editor limit');const d=JSON.parse(await value.original.text());if(d.format!=='2i-document'||d.version>4||!d.state||!Array.isArray(d.state.committed)||!d.state.committed.every(line=>typeof line==='string'))throw Error('Invalid 2i document');value.title=typeof d.title==='string'?d.title:value.name;value.twoiState=d.state;value.draft=d.state.committed.join('\n');}
      if(value.draft===undefined&&/^(docx|odt|pptx|xlsx|pdf)$/.test(extension)){
        say('Converting a working copy…');
        const result=await (await api('convert',{name:value.name,data:await base64(value.original)})).json();
        value.draft=result.text;value.warning=result.warning;value.converted=true;await record(value.id,value);
      }
      if(value.draft===undefined)value.draft=await decodeText(value.original);
      // Apply an exit journal left by a page that closed with unsaved text (see writeExitEntryNow).
      let exitNote='',exitConflict=null;
      try{
        const pending=await exitEntry(value.id);
        if(pending){
          const same=pending.draft===value.draft&&JSON.stringify(pending.twoiState??null)===JSON.stringify(value.twoiState??null);
          if(same)await exitEntry(value.id,true);
          else if(pending.baseRevision===(value.revision||0)){
            const next={...value,draft:pending.draft,title:pending.title||value.title,twoiState:pending.twoiState===undefined?value.twoiState:pending.twoiState,updated:Date.now()};
            const saved=await record(value.id,next,value.revision||0);
            value=saved;await exitEntry(value.id,true);
            exitNote='Recovered unsaved edits from when this file was last closed · saved';
          }else exitConflict=pending;
        }
      }catch(e){console.error('Exit journal unavailable',e);exitNote='Close protection unavailable in this browser: '+(e?.message||e);}
      if(value.warning)wrap.insertBefore(node('div',{role:'note',style:'font-size:12px;line-height:1.4'},value.warning),area);
      if(!alive)return session;
      editor=options.editor||node('textarea',{'aria-label':'File editor',spellcheck:'false',style:'box-sizing:border-box;width:100%;height:100%;min-height:180px;resize:none;background:#171511;color:#f3e5ca;border:1px solid #887455;padding:12px;font:14px/1.5 monospace;tab-size:4'});
      editor.value=value.draft;options.load?.(value);editor.addEventListener('input',dirty);editor.addEventListener('foresight-native-change',dirty);if(!options.editor)area.append(editor);else area.style.display='none';
      const exitSave=()=>{
        if(!alive||opening||richMode||!value||!(changed||writing>0))return;
        try{const v=snapshot();if(writeExitEntryNow({id:value.id,baseRevision:value.revision||0,draft:v.draft,title:v.title,twoiState:v.twoiState,saved:Date.now()}))exitWritten=true;}
        catch(e){console.error('Exit journal write failed',e)}
      };
      const onHidden=()=>{if(document.hidden)exitSave()};
      addEventListener('pagehide',exitSave);document.addEventListener('visibilitychange',onHidden);
      exitListeners=()=>{removeEventListener('pagehide',exitSave);document.removeEventListener('visibilitychange',onHidden)};
      if(exitConflict){
        const kept=exitConflict;
        wrap.insertBefore(node('div',{role:'alert',style:'font-size:12px;line-height:1.4'},'Unsaved edits from a window that closed were kept separately, because this file was saved elsewhere after they were made. They have not been applied.'),area);
        button('Download unsaved edits',()=>download('unsaved-edits-'+value.name.replace(/\.[^.]*$/,'')+'.txt',new Blob([kept.draft],{type:'text/plain;charset=utf-8'})));
        button('Discard unsaved edits',async()=>{if(!confirm('Discard the unsaved edits from the closed window? Download them first if you need them.'))return;await exitEntry(value.id,true);say('Unsaved edits from the closed window discarded')});
      }
      button('Export DOCX',async()=>{download(outputName('docx'),await output('docx'));say('DOCX text copy downloaded; original unchanged')});
      if(extension==='docx')button('Download rich 2i copy of original DOCX',async()=>{
        if(!confirm('Create a separate formatted .2i archive from the ORIGINAL DOCX? This does not include edits to this plain-text copy. Your text copy and original remain unchanged.'))return;
        const source=value.original,name=source?.name||value.name;
        if(!source||source.size>24*1024*1024||ext(name)!=='docx')throw Error('A valid original DOCX within the archive limit is required.');
        const encoded=await base64(source);
        const blob=await packVerifiedRich({document_id:newId(),original_name:name,original_mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',original_data_b64:encoded,working_docx_b64:encoded,metadata:{title:name.replace(/\.docx$/i,'')}});
        download(name.replace(/\.docx$/i,'')+'.2i',blob);say('Separate rich 2i archive created from original formatted bytes. Open it to use the optional rich editor; text copy unchanged.');
      });
      if(/\.py$/i.test(value.name)){button('Check Python',async()=>{const version=serial,text=options.getText?.()??editor.value;const r=await workspace('check-python',{name:value.name,text});if(serial===version&&(options.getText?.()??editor.value)===text){diagnosticVersion=version;say(r.message)}});button('Run Python',async()=>{await persist();if(parent===window)window.open('/static/foresight_shell.html?script='+encodeURIComponent(value.id),'_blank','noopener');else parent.postMessage({type:'foresight:run-python',fileId:value.id,name:value.name},location.origin)})}
      if(options.getState)button('Export 2i manuscript',async()=>download(value.name.replace(/\.[^.]*$/,'')+'.2i',await output('2i')));
      if(extension==='pdf')button('View original PDF',()=>{options.onPreview?.(true);area.style.display='block';if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(value.original);const f=node('iframe',{src:url,title:value.name,style:'width:100%;height:100%;border:0'});area.replaceChildren(f);button('Return to editor',()=>{if(options.editor){area.replaceChildren();area.style.display='none';options.onPreview?.(false)}else area.replaceChildren(editor)})});
      say(exitNote||value.warning||'2i text editor ready · working copy auto-saves · text exports use UTF-8');
    }
  }catch(e){options.onError?.();if(value&&ext(value.name)==='pdf')button('View original PDF',()=>{if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(value.original);area.replaceChildren(node('iframe',{src:url,title:value.name,style:'width:100%;height:100%;border:0'}))});say('Could not open working copy: '+e.message+'\nThe original has not been altered.');if(value&&!bar.querySelector('button'))button('Download original',()=>download(value.original.name||value.name,value.original))}
  finally{opening=false;}
  return session;
}
async function list(){const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction(STORE,'readonly'),r=t.objectStore(STORE).getAll();t.oncomplete=()=>resolve(r.result.map(({id,name,updated,original})=>({id,name,updated,size:original?.size||0})));t.onerror=()=>reject(t.error)})}
root.ForesightFiles={newId,ownerScope,encode:base64,workspace,list,mount,get:c=>sessions.get(c),record,decodeText,download};
})(window);
