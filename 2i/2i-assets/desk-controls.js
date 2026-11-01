/* Shared controls for the integrated desk and the local phone edition. */
'use strict';
window.reachDeskReady=(window.reachLocalReady||window.reachPhoneReady).then(()=>{
  const make=(tag,id,parent,text='')=>{const node=document.createElement(tag);node.id=id;node.textContent=text;parent.append(node);return node;};
  const button=(id,label,parent,action)=>{const node=make('button',id,parent,label);node.type='button';node.onclick=action;return node;};
  const row=(id,parent)=>{const node=make('div',id,parent);node.className='reader-row';return node;};
  const options=(id,label,parent,values)=>{
    const field=make('label',id+'Label',parent,label);field.htmlFor=id;const select=make('select',id,field);
    for(const [value,text] of values){const option=make('option','',select,text);option.value=value;}return select;
  };
  const host=document.getElementById('reach-phone-inline')||document.body;
  const audio=make('details','reachAudio',host);audio.open=true;
  make('summary','readerHeading',audio,'Audio · Read aloud');
  const content=make('div','readerControls',audio);
  const state=make('div','readerStatus',content,'Ready to read');state.setAttribute('role','status');
  const transport=row('readerTransport',content);
  button('readerRead','Read from start',transport,()=>reader.play({fromStart:true}));
  button('readerPlay','Play',transport,()=>reader.toggle());button('readerStop','Stop',transport,()=>reader.stop());
  const nav=row('readerNavigation',content);
  button('readerPrevious','Previous paragraph',nav,()=>reader.paragraph(-1));button('readerNext','Next paragraph',nav,()=>reader.paragraph(1));
  const seek=row('readerSeek',content);
  button('readerBack','Back 10 words',seek,()=>reader.words(-10));button('readerForward','Forward 10 words',seek,()=>reader.words(10));
  const settings=make('details','readerSettings',content);make('summary','readerSettingsHeading',settings,'Voice, speed & reading options');
  const form=make('div','readerOptions',settings);
  const source=options('readerSource','Read',form,[['manuscript','Manuscript'],['draft','Uncommitted draft'],['partner','Latest partner reply']]);
  const voice=options('readerVoice','Phone / browser voice',form,[['','Default voice']]);
  const rate=options('readerRate','Reading speed',form,[[0.5,'0.5×'],[0.75,'0.75×'],[1,'1×'],[1.25,'1.25×'],[1.5,'1.5×'],[1.75,'1.75×'],[2,'2×'],[2.5,'2.5×']]);rate.value='1';
  const volume=options('readerVolume','Voice volume',form,[[1,'100%'],[0.75,'75%'],[0.5,'50%'],[0.25,'25%'],[0,'Muted']]);
  button('readerCursor','Read from cursor',form,()=>{
    reader.setSource('manuscript');source.value='manuscript';
    const position=coWriting?(committed.slice(0,selectedIdx??0).join('\n').length+(selectedIdx?1:0)):soloTextarea.selectionStart;
    reader.play({position});
  });
  const voiceNote=make('p','readerVoiceNote',form,'Uses your selected phone/browser voice. Live PubPartner voice is not connected here.');
  voiceNote.className='reader-note';
  const excerpt=make('p','readerExcerpt',content);excerpt.className='reader-note';
  const getText=kind=>kind==='draft'?buffer.join('\n'):kind==='partner'?(chatHistory.findLast(r=>r.role==='assistant')?.content||''):(coWriting?committed.join('\n'):soloTextarea.value);
  const reader=new window.ReachReadAloud({
    getText,getKey:kind=>documentId+':'+kind+(kind==='partner'?':'+partnerId:''),
    beforePlay:()=>{playing=false;speechToken++;speaking=false;inReaction=false;clearTimeout(reactionTimer);reactionTimer=null;},
    onChange:renderReader
  });
  window.reachReader=reader;
  function renderReader(s){
    const text=s.total?'Paragraph '+(s.index+1)+' of '+s.total+' · '+s.message:s.message;
    if(state.textContent!==text)state.textContent=text;
    $('readerPlay').textContent=reader.active?'Pause':s.phase==='paused'?'Resume':'Play';
    $('readerPrevious').disabled=!s.total||s.index===0;$('readerNext').disabled=!s.total||s.index>=s.total-1;
    $('readerBack').disabled=!s.total;$('readerForward').disabled=!s.total;
    excerpt.textContent=s.text?s.text.slice(s.offset,s.offset+140):'Paste or write on the page, then press Read.';
    const mini=$('deskMiniPlay');if(mini)mini.textContent=reader.active?'Pause reading':'Play reading';
    const miniState=$('deskMiniState');if(miniState&&miniState.textContent!==text)miniState.textContent=text;
  }
  source.onchange=()=>reader.setSource(source.value);
  for(const input of [voice,rate,volume])input.onchange=()=>reader.configure({rate:Number(rate.value),volume:Number(volume.value),voiceURI:voice.value});
  const voices=()=>{
    let list=[];try{list=reader.synth?.getVoices()||[];}catch(_){}
    const selected=voice.value;voice.replaceChildren();
    const initial=make('option','',voice,'Default phone/browser voice');initial.value='';
    for(const v of list){const option=make('option','',voice,v.name+' · '+v.lang+(v.localService===false?' · online':''));option.value=v.voiceURI;}
    voice.value=[...voice.options].some(o=>o.value===selected)?selected:'';
  };
  reader.synth?.addEventListener?.('voiceschanged',voices);voices();
  const initialStop=stopPlaying;
  stopPlaying=function(){reader.stop();initialStop();};
  startPlaying=()=>reader.play();
  $('playBtn').onclick=()=>reader.toggle();$('stopBtn').onclick=()=>reader.stop();$('skipBtn').onclick=()=>reader.paragraph(1);
  $('speedSlider').oninput=()=>{reader.configure({rate:Number($('speedSlider').value)});rate.value=String(reader.rate);};
  const refresh=refreshArtwork;
  refreshArtwork=function(){refresh();reader.checkForChanges();};
  soloTextarea.addEventListener('input',()=>reader.checkForChanges());draftArea.addEventListener('input',()=>reader.checkForChanges());
  window.addEventListener('pagehide',()=>reader.stop());
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reader.pause();});

  const dialog=photoModal('readerModal','Audio controls');
  const general=photoModal('deskSettings','Settings');
  const size=options('deskTextSize','Phone manuscript text size',general.body,[[18,'Standard'],[20,'Large'],[22,'Extra large']]);
  const setSize=value=>{const chosen=[18,20,22].includes(Number(value))?Number(value):18;size.value=String(chosen);document.documentElement.style.setProperty('--reach-manuscript-size',chosen+'px');};
  setSize(stored('reach2i_text_size',18));size.onchange=()=>{setSize(size.value);try{localStorage.setItem('reach2i_text_size',JSON.stringify(Number(size.value)));}catch(_){}};
  button('deskAudioSettings','Voice and audio settings',general.body,()=>{closeModal('deskSettings');showAudio(true);});
  button('deskModelSettings','PubPartner connection',general.body,()=>{closeModal('deskSettings');openLLMModal();});
  const openSettings=()=>openModal('deskSettings');
  function showAudio(expand=false){
    restoreDesk();audio.open=true;if(expand)settings.open=true;
    if(window.reachPhone.active){audio.scrollIntoView?.({block:'nearest'});$('readerRead').focus();}else openModal('readerModal');
  }
  photoMenu('photoAudioMenu','Audio / read aloud',()=>showAudio());
  photoMenu('photoSettingsMenu','Settings',openSettings);
  photoMenu('photoCollapseMenu','Shrink desk',()=>collapseDesk());
  photoMenu('photoCloseMenu','Close desk view',()=>closeDesk());
  const dock=make('div','reachDeskDock',host);dock.hidden=true;
  make('span','reachDeskDockTitle',dock,'Writer’s Room · closed');
  button('deskReopen','Reopen writing desk',dock,()=>restoreDesk());
  let collapsed=false,closed=false;
  function restoreDesk(){closed=false;collapsed=false;delete document.body.dataset.deskState;dock.hidden=true;updateChrome();}
  function collapseDesk(){closed=false;collapsed=!collapsed;dock.hidden=true;document.body.dataset.deskState=collapsed?'collapsed':'open';updateChrome();}
  async function closeDesk(){
    reader.stop();closeMenu();
    if(!await preserveBeforeSwitch()){
      const notice=$('deskNotice')||make('div','deskNotice',host);
      notice.hidden=false;notice.textContent='Your changes could not be preserved. Export a copy before closing this view.';return;
    }
    for(const modal of document.querySelectorAll('.modal-backdrop.open'))closeModal(modal.id);
    closed=true;document.body.dataset.deskState='closed';dock.hidden=false;dock.scrollIntoView?.({block:'nearest'});$('deskReopen').focus();
  }
  function updateChrome(){
    const control=$('deskShrink');if(control){control.textContent=collapsed?'□':'—';control.setAttribute('aria-label',collapsed?'Restore full desk':'Shrink desk');control.title=collapsed?'Restore':'Shrink';control.setAttribute('aria-expanded',String(!collapsed));}
  }
  function mount(){
    $('sidebarToggle').onclick=openSettings;$('sidebarToggle').setAttribute('aria-label','Settings');
    if(window.reachPhone.active){
      const header=$('phoneHeaderActions');
      for(const [id,glyph,label]of [['menuToggle','☰','General menu'],['sidebarToggle','⚙','Settings']]){const node=$(id);node.textContent=glyph;node.title=label;node.setAttribute('aria-label',label);}
      if(!$('deskShrink'))button('deskShrink','—',header,()=>collapseDesk());
      if(!$('deskClose'))button('deskClose','×',header,()=>closeDesk());
      $('deskClose').title='Close desk view';$('deskClose').setAttribute('aria-label','Close desk view');
      header.replaceChildren($('menuToggle'),$('sidebarToggle'),$('deskShrink'),$('deskClose'));
      $('phoneTabs').after(audio);
      if(!$('deskNotice')){const notice=make('div','deskNotice',$('phoneRoom'));notice.setAttribute('role','alert');notice.hidden=true;}
      if(!$('deskMiniAudio')){const mini=row('deskMiniAudio',$('phoneRoom'));make('div','deskMiniState',mini).setAttribute('role','status');button('deskMiniPlay','Play reading',mini,()=>reader.toggle());button('deskMiniStop','Stop reading',mini,()=>reader.stop());}
      updateChrome();renderReader(reader.state);
    }else{if(collapsed||closed)restoreDesk();dialog.body.append(audio);}
  }
  window.addEventListener('reach:view-changed',mount);mount();
  // Dialogs opened from low on a phone page should appear by the tapped control,
  // not above the visible part of a long inline desk.
  let lastTapTop=null;
  document.addEventListener('pointerdown',event=>{
    const target=event.target.closest?.('button,summary');
    if(target)lastTapTop=target.getBoundingClientRect().top+(window.scrollY||0);
  },true);
  const showModal=openModal;
  openModal=function(id){
    const control=document.activeElement;
    if(document.getElementById('reach-phone-inline')){
      const position=lastTapTop??((control?.getBoundingClientRect?.().top||0)+(window.scrollY||0));
      $(id).style.paddingTop=Math.max(12,position-60)+'px';lastTapTop=null;
    }
    showModal(id);
  };
  reader.sync();
  if(!reader.supported){reader.message='Phone/browser voice is unavailable in this view';reader.notify();}
  window.reachDesk={close:closeDesk,collapse:collapseDesk,restore:restoreDesk,showAudio,openSettings,get closed(){return closed;},get collapsed(){return collapsed;}};
});
