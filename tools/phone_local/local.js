// Restore useful local actions while explicitly leaving model services offline.
window.reachLocalReady=Promise.all([window.reachStarted,window.reachPhoneReady]).then(()=>{
  window.reachPhone.setView(true,false);
  const info=photoModal('phoneLocalInfo','Writing on your phone');
  const note=document.createElement('p');note.className='partner-note';
  note.textContent='This writing desk works here without a computer. Alex and the other PubPartners are not connected to a live model in this edition. Export a .2i copy to carry your manuscript into Reach later.';
  info.body.append(note);
  const storageNote=document.createElement('p');storageNote.className='partner-note';
  storageNote.textContent=reachPhoneStore.persistent?'Save keeps a copy in this browser. Export a backup before clearing browser data.':'This view cannot keep work after it closes. Export or copy your writing before leaving.';info.body.append(storageNote);
  openLLMModal=()=>openModal('phoneLocalInfo');
  $('sidebarToggle').onclick=openLLMModal;$('llmPill').onclick=openLLMModal;
  const status=setSaveStatus;
  setSaveStatus=function(text){
    if(text==='Saved in this browser'&&!reachPhoneStore.persistent)text='Kept in this open view only · export to keep';
    if(text==='Writing locally · open through Reach to sync')text='Ready to write here · live partner disconnected';
    status(text);
  };
  const localNotice=()=>{
    $('partnerNote').textContent='Model unavailable · live partners are not connected in this edition';
    $('photoConnection').textContent='Offline';
    $('chatInput').placeholder='Live partner not connected';
  };
  sendChat=async()=>{
    localNotice();
    addChat('notice','Your live partner is not connected in this phone edition. Your unsent message stays in the input field.');
  };
  $('chatSendBtn').onclick=sendChat;
  const switchLocal=switchPartner;
  switchPartner=async()=>{await switchLocal();localNotice();};$('partnerSelect').onchange=switchPartner;
  const originalShelf=showShelf;
  showShelf=async()=>{try{await originalShelf();}catch(error){setSaveStatus('Could not open saved manuscripts · export your current work');}};
  $('phoneShelf').onclick=showShelf;$('photoShelfMenu').onclick=()=>{closeMenu();showShelf();};
  const exporting=photoModal('phoneLocalExport','Keep a copy');
  const exportHint=document.createElement('p');exportHint.className='partner-note';exportHint.textContent='Download this copy, or select the text below and copy it.';exporting.body.append(exportHint);
  const output=document.createElement('textarea');output.id='phoneLocalExportText';output.readOnly=true;output.setAttribute('aria-label','Exported manuscript');output.rows=8;exporting.body.append(output);
  const select=document.createElement('button');select.className='mc-btn';select.textContent='Select all';select.onclick=()=>{output.focus();output.select();};exporting.actions.append(select);
  const download=document.createElement('button');download.className='mc-btn';download.textContent='Download';exporting.actions.append(download);
  downloadFile=function(name,text,type){
    output.value=text;$('phoneLocalExportTitle').textContent=name;
    download.onclick=()=>{
      const url=URL.createObjectURL(new Blob([text],{type})),anchor=document.createElement('a');
      anchor.href=url;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      exportHint.textContent='Download requested. If nothing opens, use Select all and copy the text.';
    };
    openModal('phoneLocalExport');
  };
  const goal=photoModal('phoneLocalGoal','Word goal');
  const input=document.createElement('input');input.type='number';input.min='0';input.max='10000000';input.id='phoneLocalGoalInput';input.setAttribute('aria-label','Word goal');goal.body.append(input);
  const goalSave=document.createElement('button');goalSave.className='mc-btn';goalSave.textContent='Set goal';goal.actions.append(goalSave);
  goalSave.onclick=()=>{
    const value=Number(input.value);if(!Number.isInteger(value)||value<0||value>10000000){input.setCustomValidity('Choose a whole number from 0 to 10,000,000.');input.reportValidity();return;}
    input.setCustomValidity('');photoGoal=value;
    try{reachPhoneStore.setItem('reach2i_word_goal',JSON.stringify(value));}catch(_){}
    refreshArtwork();closeModal('phoneLocalGoal');
  };
  $('photoWordGoal').onclick=()=>{input.value=String(photoGoal);openModal('phoneLocalGoal');};
  // A single selected line has a direct native edit field in the donor editor;
  // no keyboard, hover or a second runtime is needed for free writing.
  localNotice();
  setSaveStatus(reachPhoneStore.persistent?'Ready · Save keeps a copy in this browser':'Try writing here · export before closing');
  $('phoneEdition').textContent='LOCAL WRITING';
  const query=new URL(location.href).searchParams;
  if(query.get('view')!=='desktop')window.reachPhone.setView(true,false);
});
