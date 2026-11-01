/* Phone edition: the same editor and saved document, arranged for touch.
 * Existing elements are moved, never cloned. Returning to the picture restores
 * their original parents and coordinates without reloading or losing a draft.
 */
'use strict';
(() => {
  let room, activePanel='write', enabled=false;
  const homes=new Map(), captions=new Map();
  const dynamicCaptions=new Set(['modeBadge','lockSceneBtn','photoLockMode','chatSendBtn']);
  const el=(tag,id,parent,text='')=>{
    const node=document.createElement(tag);node.id=id;node.textContent=text;parent.append(node);return node;
  };
  const row=(id,parent)=>{const node=el('div',id,parent);node.className='phone-row';return node;};
  function move(id,parent,label) {
    const node=$(id);if(!node)throw Error('Missing phone control: '+id);
    if(!homes.has(node)){
      const marker=document.createComment('Desktop position: '+id);node.before(marker);homes.set(node,marker);
    }
    if(label!==undefined&&!dynamicCaptions.has(id)) {captions.set(node,node.innerHTML);node.textContent=label;}
    parent.append(node);return node;
  }
  function button(id,label,parent,action) {
    const node=el('button',id,parent,label);node.type='button';node.onclick=action;return node;
  }
  function selectPanel(name,focus=false) {
    if(!enabled||!['write','partner','archive'].includes(name))return;
    activePanel=name;
    for(const key of ['write','partner','archive']){
      const current=key===name,tab=$('phoneTab_'+key),panel=$('phonePanel_'+key);
      panel.hidden=!current;tab.setAttribute('aria-selected',String(current));tab.tabIndex=current?0:-1;
    }
    if(focus)$('phoneTab_'+name).focus();
    $('phoneViews').scrollTop=0;
  }
  function resizePhone() {
    document.documentElement.style.setProperty('--phone-height',(window.visualViewport?.height||innerHeight)+'px');
  }
  function buildPhone() {
    room=el('div','phoneRoom',photoRoot);
    const header=el('header','phoneHeader',room);
    const brand=el('div','phoneBrand',header);el('small','phoneBrandSmall',brand,'PUBCAST REACH');el('div','phoneBrandTitle',brand,'Writer’s Room');
    const headerActions=row('phoneHeaderActions',header);
    move('sidebarToggle',headerActions,'Settings');move('menuToggle',headerActions,'Menu');
    const tabs=el('nav','phoneTabs',room);tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Your writing room');
    for(const [name,label] of [['write','Write'],['partner','Partner'],['archive','Archive']]){
      const tab=button('phoneTab_'+name,label,tabs,()=>selectPanel(name));tab.setAttribute('role','tab');tab.setAttribute('aria-controls','phonePanel_'+name);
      tab.addEventListener('keydown',event=>{
        const keys=['write','partner','archive'],index=keys.indexOf(name);
        const next=event.key==='ArrowRight'?keys[(index+1)%3]:event.key==='ArrowLeft'?keys[(index+2)%3]:event.key==='Home'?keys[0]:event.key==='End'?keys[2]:null;
        if(next){event.preventDefault();selectPanel(next,true);}
      });
    }
    const views=el('main','phoneViews',room),panels={};
    for(const name of ['write','partner','archive']){
      const panel=el('section','phonePanel_'+name,views);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','phoneTab_'+name);panels[name]=panel;
    }
    const writeTools=row('phoneWriteTools',panels.write);
    move('modeBadge',writeTools);move('photoOutline',writeTools,'Outline');move('newChapterBtn',writeTools,'New scene');move('photoLockMode',writeTools);
    const notebook=el('article','phoneNotebook',panels.write);
    move('photoTitle',notebook);move('pageSheets',notebook);
    const scenes=row('phoneSceneNav',panels.write);
    move('photoPrevious',scenes,'← Previous');move('photoSceneCount',scenes);move('photoNext',scenes,'Next →');
    const writeActions=row('phoneWriteActions',panels.write);
    move('photoManuscript',writeActions,'Focus page');move('lockSceneBtn',writeActions);
    button('phoneCommit','Commit draft',writeActions,()=>{approveBuffer();selectPanel('write');});
    move('photoProgress',panels.write);

    move('worldRoomSection',panels.partner); // Same shared room in phone view; manuscript stays independent.
    el('h2','phonePartnerHeading',panels.partner,'Your PubPartner');
    const partner=row('phonePartnerChoice',panels.partner);
    move('partnerSelect',partner);move('photoConnection',partner);
    move('chatLog',panels.partner);
    const compose=row('phoneCompose',panels.partner);
    move('chatInput',compose);move('chatSendBtn',compose,'Send');
    el('h3','phoneSuggestionHeading',panels.partner,'A suggestion to consider');
    move('photoSuggestionText',panels.partner);
    const suggestion=row('phoneSuggestionActions',panels.partner);
    move('photoInsert',suggestion,'Insert into draft');move('photoDismiss',suggestion,'Dismiss');
    el('h3','phoneIdeasHeading',panels.partner,'Scene ideas');move('photoIdeas',panels.partner);
    const ideas=row('phoneIdeaActions',panels.partner);move('photoAddIdea',ideas,'+ Add idea');move('photoAllIdeas',ideas,'All ideas');

    el('h2','phoneArchiveHeading',panels.archive,'Reference archive');
    const collections=row('phoneCollections',panels.archive);
    for(const [id,label] of [['photoCharacters','Characters'],['photoWorldbuilding','Worldbuilding'],['photoNotes','Notes']])move(id,collections,label);
    const search=row('phoneSearchRow',panels.archive);move('refSearchInput',search);move('photoSearch',search,'Search');
    const filters=row('phoneRefFilters',panels.archive);
    for(const [id,label] of [['photoRefAll','All'],['photoRefChapter','Chapters'],['photoRefResearch','Research'],['photoRefNotes','Notes']])move(id,filters,label);
    move('refListContainer',panels.archive);move('addRefBtn',panels.archive,'+ Add reference');

    const footer=el('footer','phoneFooter',room);move('saveIndicator',footer);
    const footerActions=row('phoneFooterActions',footer);move('saveBtn',footerActions,'Save');
    button('phoneShelf','My manuscripts',footerActions,showShelf);move('exportBtn',footerActions,'Export');
    const desk=row('phoneDeskChoice',footer);button('phoneDesktop','Whole desk picture',desk,()=>setView(false));
    el('span','phoneEdition',desk,'PHONE EDITION');
  }
  function syncPhone() {
    if(!enabled)return;
    $('phoneCommit').disabled=!buffer.length;
    room.dataset.writingMode=coWriting?'review':'write';
  }
  function setView(phone,remember=true) {
    closeMenu();
    if(phone===enabled)return;
    enabled=phone;
    if(phone){
      document.body.classList.remove('art-full-size');document.body.dataset.reachView='phone';buildPhone();selectPanel(activePanel);resizePhone();syncPhone();
    } else {
      for(const [node,marker] of homes){marker.replaceWith(node);if(captions.has(node))node.innerHTML=captions.get(node);}
      homes.clear();captions.clear();room.remove();room=null;delete document.body.dataset.reachView;
    }
    $('photoPhoneMenu').textContent=enabled?'Whole desk picture':'Phone view';
    if(remember){
      const value=phone?'phone':'desktop';
      try{sessionStorage.setItem('reach2i_view',value);}catch(_){/* UI still works if storage is blocked. */}
      const url=new URL(location.href);url.searchParams.set('view',value);history.replaceState(null,'',url);
    }
    refreshArtwork();
    window.dispatchEvent(new Event('reach:view-changed'));
  }
  window.reachPhoneReady=window.reachArtworkReady.then(()=>{
    photoMenu('photoPhoneMenu','Phone view',()=>setView(!enabled));
    const beforeRefresh=refreshArtwork;refreshArtwork=function(){beforeRefresh();syncPhone();};
    const beforeViewRef=viewRef;viewRef=function(...args){if(enabled)selectPanel('write');beforeViewRef(...args);};
    $('photoInsert').addEventListener('click',()=>{if(enabled&&buffer.length){selectPanel('write');draftArea.focus();}});
    // The drawing-size switch is a desktop action, including when invoked from
    // the phone menu. It must not leave the phone UI in a half-transformed state.
    const desktopSize=$('photoFullSizeMenu').onclick;
    $('photoFullSizeMenu').onclick=()=>{if(enabled)setView(false);desktopSize();};
    window.addEventListener('resize',resizePhone);window.visualViewport?.addEventListener('resize',resizePhone);
    let saved;try{saved=sessionStorage.getItem('reach2i_view');}catch(_){}
    const requested=new URL(location.href).searchParams.get('view')||saved;
    setView(requested==='phone'||(!requested&&innerWidth<=600),false);
    window.reachPhone={setView,selectPanel,get active(){return enabled;},get panel(){return activePanel;}};
  });
})();
