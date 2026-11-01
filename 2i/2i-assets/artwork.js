/* The original picture stays byte-for-byte intact. Coordinates are image pixels. */
'use strict';
let photoScene = 0, photoDocument = documentId;
const dismissedSuggestions = new Map();
const photoRoot = document.querySelector('.app-shell');
function photoElement(tag, id, parent=photoRoot, text='') {
  const el=document.createElement(tag); el.id=id; el.textContent=text; parent.append(el); return el;
}
const photoTitle=photoElement('div','photoTitle'); photoTitle.className='photo-title';
photoElement('div','photoChapterName',photoTitle);
photoElement('button','photoManuscriptTitle',photoTitle).title='Rename this scene';
photoElement('span','photoConnection').title='Model connection';
photoElement('div','photoSuggestionText').setAttribute('aria-label','Latest partner suggestion');
photoElement('div','photoIdeas').setAttribute('aria-label','Scene ideas');
const photoProgress=photoElement('div','photoProgress');
photoProgress.innerHTML='<div class="photo-progress-row"><span>Draft status</span><span id="photoDraftStatus"></span></div><div class="photo-progress-track"><div id="photoProgressFill"></div></div><div class="photo-progress-row"><span id="photoWordCount"></span><button id="photoWordGoal" title="Set a word goal"></button></div>';
photoElement('div','photoFooter').setAttribute('aria-label','Time and word count');
photoElement('div','photoSceneCount').setAttribute('aria-live','polite');
photoElement('div','photoLineNumbers').setAttribute('aria-hidden','true');
photoElement('button','photoLockMode',photoRoot,'Scene lock');
document.querySelector('.ref-search button').id='photoSearch';
for(const [filter,id] of [['all','photoRefAll'],['chapter','photoRefChapter'],['research','photoRefResearch'],['notes','photoRefNotes']])document.querySelector('.ref-tab[data-filter="'+filter+'"]').id=id;
let photoGoal=Number(stored('reach2i_word_goal',0)) || 0;
$('photoWordGoal').onclick=()=>{
  const answer=prompt('Word goal (0 for no goal):',String(photoGoal));
  if(answer===null)return;
  const goal=Number(answer);
  if(!Number.isInteger(goal)||goal<0||goal>10000000){addChat('notice','Choose a whole number from 0 to 10,000,000.');return;}
  photoGoal=goal;localStorage.setItem('reach2i_word_goal',JSON.stringify(goal));refreshArtwork();
};
for(const [value,label] of [['character','Character'],['worldbuilding','Worldbuilding'],['idea','Scene idea']]) {
  if(!$('refTypeInput').querySelector('option[value="'+value+'"]')) {
    const option=document.createElement('option');option.value=value;option.textContent=label;$('refTypeInput').append(option);
  }
}
function photoModal(id,title) {
  const backdrop=photoElement('div',id,document.body);backdrop.className='modal-backdrop';
  const modal=document.createElement('div');modal.className='modal';modal.setAttribute('role','dialog');modal.setAttribute('aria-label',title);backdrop.append(modal);
  const heading=photoElement('div',id+'Title',modal,title);heading.className='modal-title';
  const body=photoElement('div',id+'Body',modal);body.className='shelf-list';
  const actions=photoElement('div',id+'Actions',modal);actions.className='modal-actions';
  const close=photoElement('button',id+'Close',actions,'Close');close.className='mc-btn';close.onclick=()=>closeModal(id);
  backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeModal(id);});
  return {body,actions};
}
const photoCollection=photoModal('photoCollection','Reference archive');
const photoLockOptions=photoModal('photoLockOptions','Writing and locks');
for(const [label,action] of [
  ['Free writing',()=>{if(coWriting)toggleMode();}],['Review draft',()=>{if(!coWriting)toggleMode();}],
  ['Lock or unlock this scene',togglePhotoLock],['Lock all lines',lockAll],
  ['Unlock all lines',()=>{snapshot();lockedLines.clear();markDirty();render();}]
]) {
  const button=document.createElement('button');button.className='mc-btn';button.textContent=label;
  button.onclick=()=>{closeModal('photoLockOptions');action();};photoLockOptions.body.append(button);
}
const photoSceneForm=photoModal('photoSceneForm','Scene');
photoSceneForm.body.innerHTML='<label for="photoSceneTitleInput">Scene title</label><input id="photoSceneTitleInput" maxlength="200"><label for="photoSceneSubtitleInput">Subtitle</label><input id="photoSceneSubtitleInput" maxlength="200">';
const photoSceneSave=photoElement('button','photoSceneSave',photoSceneForm.actions,'Save scene');photoSceneSave.className='mc-btn primary';
function sceneRange() {
  photoScene=Math.max(0,Math.min(photoScene,chapters.length-1));
  return {start:chapters[photoScene]?.startLine || 0, end:chapters[photoScene+1]?.startLine ?? committed.length};
}
function scrollPhotoTextarea(offset) {
  // Measure wrapped text in CSS pixels; a source line is not always one row.
  const css=getComputedStyle(soloTextarea),mirror=document.createElement('div');
  for(const key of ['fontFamily','fontSize','fontWeight','fontStyle','fontVariant','lineHeight','letterSpacing','wordSpacing','textIndent','paddingTop','paddingRight','paddingBottom','paddingLeft','tabSize'])mirror.style[key]=css[key];
  Object.assign(mirror.style,{position:'absolute',left:'-10000px',top:'0',visibility:'hidden',width:(soloTextarea.clientWidth||433)+'px',boxSizing:'border-box',whiteSpace:'pre-wrap',overflowWrap:'break-word'});
  mirror.setAttribute('aria-hidden','true');mirror.textContent=soloTextarea.value.slice(0,offset);
  const marker=document.createElement('span');marker.textContent='\u200b';mirror.append(marker);document.body.append(mirror);
  soloTextarea.scrollTop=marker.offsetTop;mirror.remove();
}
function showPhotoScene(index) {
  photoScene=Math.max(0,Math.min(index,chapters.length-1));closeRefViewer();closeModal('photoCollection');
  const start=sceneRange().start;
  if(coWriting){selectedIdx=start<committed.length?start:null;render();manuscriptLines.scrollTop=manuscriptLines.querySelectorAll('.m-line')[start]?.offsetTop || 0;}
  else {
    const offset=committed.slice(0,start).reduce((n,line)=>n+line.length+1,0);
    soloTextarea.focus();soloTextarea.setSelectionRange(offset,offset);scrollPhotoTextarea(offset);
  }
  refreshArtwork();
}
function editPhotoScene(create=false) {
  const index=photoScene, chapter=chapters[index];
  $('photoSceneFormTitle').textContent=create?'New scene':'Rename scene';
  $('photoSceneTitleInput').value=create?'Chapter '+numberToWord(chapters.length+1):chapter?.title || 'Chapter One';
  $('photoSceneSubtitleInput').value=create?'':chapter?.subtitle || '';
  photoSceneSave.onclick=()=>{
    const title=$('photoSceneTitleInput').value.trim();if(!title)return;
    snapshot();
    const subtitle=$('photoSceneSubtitleInput').value.trim();
    if(create) {
      if(buffer.length)approveBuffer();
      // A blank separator gives the next scene a real insertion point in Write mode.
      if(committed.length && committed.at(-1)!=='')committed.push('');
      const startLine=committed.length?committed.length-1:0;
      if(!chapters.length)chapters=[{title,subtitle,startLine}];
      else chapters.push({title,subtitle,startLine});
      photoScene=chapters.length-1;soloTextarea.value=committed.join('\n');
    } else if(chapter){chapter.title=title;chapter.subtitle=subtitle;}
    markDirty();render();closeModal('photoSceneForm');showPhotoScene(photoScene);
  };
  openModal('photoSceneForm');$('photoSceneTitleInput').focus();
}
$('photoManuscriptTitle').onclick=()=>editPhotoScene();
function showPhotoCollection(kind) {
  const titles={outline:'Outline',character:'Characters',worldbuilding:'Worldbuilding',notes:'Notes',idea:'Scene ideas'};
  $('photoCollectionTitle').textContent=titles[kind] || 'Reference archive';
  photoCollection.body.replaceChildren();
  if(kind==='outline') {
    chapters.forEach((chapter,index)=>{
      const button=document.createElement('button');button.className='mc-btn shelf-item';
      button.textContent=(index+1)+'. '+chapter.title+(chapter.subtitle?' — '+chapter.subtitle:'');
      button.onclick=()=>showPhotoScene(index);photoCollection.body.append(button);
    });
  } else {
    const entries=references.filter(r=>r.type===kind);
    for(const reference of entries) {
      const button=document.createElement('button');button.className='mc-btn shelf-item';button.textContent=reference.name;
      button.onclick=()=>{viewRef(reference.id);closeModal('photoCollection');};photoCollection.body.append(button);
    }
    if(!entries.length){const empty=document.createElement('p');empty.className='partner-note';empty.textContent='A place for your '+titles[kind].toLowerCase()+'.';photoCollection.body.append(empty);}
    const add=document.createElement('button');add.className='mc-btn';add.textContent='+ Add '+(kind==='idea'?'scene idea':kind);
    add.onclick=()=>{closeModal('photoCollection');openPhotoReference(kind);};photoCollection.body.append(add);
  }
  openModal('photoCollection');
}
function openPhotoReference(kind) { $('addRefBtn').onclick();$('refTypeInput').value=kind; }
function latestPhotoSuggestion() {
  const entry=chatHistory.findLast(row=>row.role==='assistant');
  if(!entry)return null;
  const key=documentId+':'+partnerId+':'+(conversationIds[partnerId] || '');
  return dismissedSuggestions.get(key)===entry?null:{entry,key};
}
function insertPhotoSuggestion() {
  const suggestion=latestPhotoSuggestion();if(!suggestion)return;
  if(!coWriting)toggleMode();
  snapshot();buffer.push(...suggestion.entry.content.split('\n'));
  dismissedSuggestions.set(suggestion.key,suggestion.entry);markDirty();render();draftArea.focus();
  setSaveStatus('Suggestion added to draft · Menu → Commit draft when ready');
}
function togglePhotoLock() {
  const range=sceneRange();
  if(range.end<=range.start){addChat('notice','Write a few lines in this scene before locking it.');return;}
  if(!coWriting)toggleMode();snapshot();
  const indexes=Array.from({length:range.end-range.start},(_,i)=>i+range.start);
  const unlock=indexes.every(i=>lockedLines.has(i));
  indexes.forEach(i=>unlock?lockedLines.delete(i):lockedLines.add(i));markDirty();render();
}
function refreshArtwork() {
  if(photoDocument!==documentId){photoScene=0;photoDocument=documentId;}
  const range=sceneRange(),chapter=chapters[photoScene];
  $('photoChapterName').textContent=chapter?.title || 'Your manuscript';
  $('photoManuscriptTitle').textContent=chapter?.subtitle || documentTitle;
  $('photoSceneCount').textContent='SCENE '+(chapters.length?photoScene+1:0)+' OF '+chapters.length;
  const text=coWriting?committed.concat(buffer).join(' '):soloTextarea.value;
  const count=text.trim().split(/\s+/).filter(Boolean).length;
  $('photoWordCount').textContent=count.toLocaleString()+' words';
  $('photoWordGoal').textContent=photoGoal?'/ '+photoGoal.toLocaleString():'Set goal';
  $('photoProgressFill').style.width=photoGoal?Math.min(100,count/photoGoal*100)+'%':'0%';
  const locked=range.end>range.start&&Array.from({length:range.end-range.start},(_,i)=>i+range.start).every(i=>lockedLines.has(i));
  $('photoDraftStatus').textContent=locked?'Scene locked':'Active';
  $('lockSceneBtn').textContent=locked?'Unlock scene':'Lock scene';
  $('lockSceneBtn').setAttribute('aria-label',locked?'Unlock scene':'Lock scene');
  $('photoLockMode').textContent=(coWriting?'Scene lock':'Free writing')+' ▾';
  const suggestion=latestPhotoSuggestion();
  $('photoSuggestionText').textContent=suggestion?suggestion.entry.content:'Ask your partner for an idea. Their latest reply will appear here for you to consider.';
  if($('photoInsert'))$('photoInsert').disabled=!suggestion;
  if($('photoDismiss'))$('photoDismiss').disabled=!suggestion;
  if($('photoPrevious'))$('photoPrevious').disabled=photoScene===0;
  if($('photoNext'))$('photoNext').disabled=photoScene>=chapters.length-1;
  const connection=$('partnerNote').textContent;
  $('photoConnection').textContent=connection.startsWith('Connected')?'Connected':connection.startsWith('Model unavailable')?'Offline':'Connect';
  $('photoConnection').title=connection;
  $('photoConnection').classList.toggle('connected',connection.startsWith('Connected'));
  const ideas=references.filter(r=>r.type==='idea');$('photoIdeas').replaceChildren();
  for(const idea of ideas) {
    const button=document.createElement('button');button.textContent=idea.name;button.onclick=()=>viewRef(idea.id);$('photoIdeas').append(button);
  }
  if(!ideas.length){const empty=document.createElement('p');empty.className='photo-empty';empty.textContent='Catch an idea with the + above.';$('photoIdeas').append(empty);}
  const now=new Date();$('photoFooter').textContent=now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+'   ·   '+now.toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'})+'   ·   '+count.toLocaleString()+' words';
  refreshPhotoNumbers();
}
function refreshPhotoNumbers() {
  const scroll=coWriting?manuscriptLines.scrollTop:soloTextarea.scrollTop;
  const first=Math.floor(scroll/25)+1;
  $('photoLineNumbers').textContent=Array.from({length:15},(_,i)=>first+i).join('\n');
}
const beforeArtworkRender=render;render=function(){beforeArtworkRender();refreshArtwork();};
const beforeArtworkRefs=renderRefs;renderRefs=function(){beforeArtworkRefs();refreshArtwork();};
const beforeArtworkChat=addChat;addChat=function(...args){const result=beforeArtworkChat(...args);refreshArtwork();return result;};
draftArea.addEventListener('input',refreshArtwork);
soloTextarea.addEventListener('scroll',refreshPhotoNumbers);manuscriptLines.addEventListener('scroll',refreshPhotoNumbers);
soloTextarea.addEventListener('click',()=>{
  const line=soloTextarea.value.slice(0,soloTextarea.selectionStart).split('\n').length-1;
  photoScene=Math.max(0,chapters.findLastIndex(chapter=>chapter.startLine<=line));refreshArtwork();
});
new MutationObserver(refreshArtwork).observe($('partnerNote'),{childList:true,subtree:true,characterData:true});
setInterval(refreshArtwork,60000);
function photoMenu(id,label,action) {
  const button=photoElement('button',id,$('hamburgerMenu'),label);button.className='hm-btn';button.onclick=()=>{closeMenu();action();};
}
photoMenu('photoShelfMenu','My manuscripts',showShelf);
photoMenu('photoCommitMenu','Commit draft',approveBuffer);
photoMenu('photoUnlockMenu','Unlock all lines',()=>{snapshot();lockedLines.clear();markDirty();render();});
photoMenu('photoFullSizeMenu','Actual size / fit to window',()=>document.body.classList.toggle('art-full-size'));
photoMenu('photoHotspotMenu','Show clickable areas',()=>{
  const show=photoRoot.classList.toggle('show-hotspots');
  $('photoHotspotMenu').textContent=show?'Hide clickable areas':'Show clickable areas';
});
$('newChapterBtn').onclick=()=>editPhotoScene(true);
$('lockSceneBtn').onclick=togglePhotoLock;
$('sidebarToggle').onclick=openLLMModal;
// The full host keeps partner routing active while its model can be changed below.
$('llmProvider').replaceChildren(Object.assign(document.createElement('option'),{value:'pubpartner',textContent:'Your PubPartner in Reach'}));
llmCfg.provider='pubpartner';
const photoActions={
  manuscript:()=>{closeRefViewer();(coWriting?draftArea:soloTextarea).focus();},
  outline:()=>showPhotoCollection('outline'),characters:()=>showPhotoCollection('character'),
  worldbuilding:()=>showPhotoCollection('worldbuilding'),notes:()=>showPhotoCollection('notes'),
  insert:insertPhotoSuggestion,dismiss:()=>{const s=latestPhotoSuggestion();if(s)dismissedSuggestions.set(s.key,s.entry);refreshArtwork();},
  add_idea:()=>openPhotoReference('idea'),ideas:()=>showPhotoCollection('idea'),
  lock_mode:()=>openModal('photoLockOptions'),
  previous:()=>showPhotoScene(photoScene-1),next:()=>showPhotoScene(photoScene+1)
};
function applyHotspotMap(map) {
  if(map.schema!=='reach.hotspots.v1'||map.image.width!==1344||map.image.height!==896)throw Error('The button map does not match this picture.');
  const ids=new Set();
  for(const item of [...map.controls,...map.live_regions]) {
    const b=item.bounds;
    if(ids.has(item.id)||!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite)||b[0]<0||b[1]<0||b[2]<=0||b[3]<=0||b[0]+b[2]>map.image.width||b[1]+b[3]>map.image.height)throw Error('Invalid image coordinates for '+item.id);
    ids.add(item.id);
    if(item.action&&!photoActions[item.action])throw Error('Unknown button action: '+item.action);
  }
  for(const item of map.controls) {
    const button=$(item.id) || photoElement('button',item.id);
    button.type='button';button.dataset.hotspot=item.id;button.title=item.label;button.setAttribute('aria-label',item.label);
    if(item.action)button.onclick=photoActions[item.action];
  }
  for(const item of [...map.controls,...map.live_regions]) {
    const el=$(item.id);if(!el)throw Error('Missing live region: '+item.id);
    const [left,top,width,height]=item.bounds;Object.assign(el.style,{left:left+'px',top:top+'px',width:width+'px',height:height+'px'});
  }
  const fit=()=>photoRoot.style.setProperty('--art-scale',String(Math.min(innerWidth/map.image.width,innerHeight/map.image.height)));
  fit();window.addEventListener('resize',fit);refreshArtwork();
  photoRoot.dataset.artworkReady='true';
}
window.reachArtworkReady=fetch(new URL('./2i-assets/hotspots.json',location.href)).then(response=>{
  if(!response.ok)throw Error('Could not load the button map.');return response.json();
}).then(applyHotspotMap).catch(error=>{
  const warning=photoElement('div','hotspotError',document.body,error.message+' Open this room using OPEN_REACH_WINDOWS.bat or open_reach.sh.');warning.setAttribute('role','alert');
  throw error;
});
refreshArtwork();
