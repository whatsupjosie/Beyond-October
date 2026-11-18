/* Native 2i studio presentation and shared production notes. */
(function installStudioDesk(){
  function presentationMode(config,fileMode){return fileMode?"standard":config.seated?"typewriter":config.room?"notebook":"standard";}
  /* Josie: "In any open 2i window she can switch between the notebook, the typewriter and the single-page notebook
     from the menu." A studio seat decides which look 2i OPENS in; it no longer decides which looks may be chosen. */
  function canPresent(mode){return mode==="standard"||mode==="notebook"||mode==="typewriter";}
  if(reachFileMode){document.body.dataset.twoiDesk="standard";return;}
  const q=new URLSearchParams(location.search),config=TwoiStudioBridge.presentation(q.get("studio_room"),q.get("studio_view"),q.get("desk"));
  document.body.dataset.twoiDesk=presentationMode(config,false);
  window.twoiCanPresent=mode=>canPresent(mode,config.seated);
  window.twoiSetPresentation=mode=>{
    if(!window.twoiCanPresent(mode))throw Error("This presentation requires a designated writing station.");
    document.body.dataset.twoiDesk=mode;
    document.dispatchEvent(new CustomEvent("twoi:presentation-change",{detail:{mode}}));
  };
  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;if(parent)parent.append(n);return n;};
  const controls=el("div",null,$("mcSection").querySelector(".section-body"));controls.id="twoiStudioControls";
  const button=(label,action)=>{const b=el("button",label,controls);b.type="button";b.className="mc-btn";b.onclick=action;return b;};
  let loading=null,opening=false;
  async function ensureNotes(){
    if(!window.PubCastNotes){
      if(!loading)loading=new Promise((resolve,reject)=>{const script=el('script',null,document.head);script.src='/static/production_notes.js';script.onload=resolve;script.onerror=()=>{script.remove();loading=null;reject(Error('Production notes could not load.'));};});
      await loading;
      if(config.room)window.PubCastNotes.onView(config.room+'/'+q.get('studio_view'));
    }
    return window.PubCastNotes;
  }
  async function notes(action){
    if(initializing||!networked||!serverReady){addChat("notice","Connect and sign in to Bella Faux Pas before opening production notes.");return;}
    if(opening)return;opening=true;
    try{
      const service=await ensureNotes();
      // Reuse the actual room menu, not a parallel message composer.
      await service.open();
      if(action==="compose")await service.compose({});
      if(action==="place")await service.place();
    }catch(error){addChat("notice",error.message);}
    finally{opening=false;}
  }
  const inbox=button("Studio notes",()=>notes("inbox"));inbox.id="twoiNotesInbox";
  button("Write a note",()=>notes("compose")).id="twoiWriteNote";
  button("Place sticky note",()=>notes("place")).id="twoiPlaceNote";
  document.addEventListener("pubcast:notes-unread",e=>{const n=e.detail?.count;inbox.textContent=Number.isInteger(n)&&n>0?"Studio notes ("+n+" unread)":"Studio notes";});
  // Start the shared inbox poll only after the authenticated native editor is ready.
  window.reachStarted?.then(()=>{if(networked&&serverReady)ensureNotes().catch(()=>{});}).catch(()=>{});
  if(config.returnPath)button(config.seated?"Stand up · return to room":"Return to studio",async()=>{
    try{
      if(initializing){addChat("notice","Wait for the manuscript to open before leaving.");return;}
      if(!await preserveBeforeSwitch())return;
      if(!rememberStudioResume()){
        addChat("notice","Unable to retain this tab's manuscript handoff. Save or export your work before leaving.");
        return;
      }
      location.assign(config.returnPath);
    }catch(error){addChat("notice",error.message);}
  });
  // Reuse Claude's touchable-key console as an optional, isolated instrument.
  // The typewriter can be opened from any 2i presentation, without a second
  // manuscript buffer or changes to the existing notebook/solo editor.
  let keysLayer=null,keysFrame=null,keysFailed=false;
  const keysButton=button("Touchable typewriter",()=>openKeys());
  keysButton.id="twoiTouchableTypewriter";
  if(location.protocol==="file:"||typeof TwoiTypewriterKeys==='undefined'){
    keysButton.disabled=true;
    keysButton.title="Interactive keys require the hosted PubCast typewriter console";
  }
  function closeKeys(){
    if(keysLayer)keysLayer.style.display="none";
    keysButton.focus({preventScroll:true});
  }
  function openKeys(){
    if(keysButton.disabled||document.body.dataset.twoiDesk!=="typewriter")return;
    if(!keysLayer){
      keysLayer=el("div",null,document.body);
      keysLayer.id="twoiLiveKeys";keysLayer.setAttribute("role","dialog");
      keysLayer.setAttribute("aria-label","Touchable typewriter keys");
      keysLayer.setAttribute("aria-modal","false");
      keysLayer.style.cssText="position:fixed;inset:2dvh 2vw;z-index:25000;background:#17110b;border:2px solid #c6a360;box-shadow:0 0 0 500vmax #0009;display:none;flex-direction:column;padding:8px;gap:8px";
      const close=el("button","Close typewriter",keysLayer);close.type="button";close.className="mc-btn";close.onclick=closeKeys;
      keysFrame=el("iframe",null,keysLayer);
      keysFrame.id="twoiLiveKeysFrame";keysFrame.title="Interactive blue and gold typewriter";
      keysFrame.style.cssText="flex:1;min-height:0;width:100%;border:0;background:#1b140f";
      keysFrame.src="/typewriter-console?embed=2i";
    }
    keysLayer.style.display="flex";
  }
  window.addEventListener("message",event=>{
    if(!keysFrame||event.source!==keysFrame.contentWindow||event.origin!==location.origin
       ||keysLayer.style.display!=="flex"||document.body.dataset.twoiDesk!=="typewriter"
       ||event.data?.type!=="pubcast:2i-key")return;
    if(initializing||generating||chatSending||editingIdx!==null)return;
    // Shift/blank keys are controls, not failed typing attempts.
    if(!TwoiTypewriterKeys.command(event.data.key))return;
    const target=coWriting?draftArea:soloTextarea;
    let written=false;
    try{written=TwoiTypewriterKeys.write(document,target,event.data.key);}catch(error){
      if(!keysFailed){addChat("notice","Typewriter input failed: "+error.message);keysFailed=true;}
    }
    if(!written&&!keysFailed){
      addChat("notice","Touchable keys could not edit this manuscript. Use its text field instead.");
      keysFailed=true;
    }
    if(written)keysFrame.contentWindow.postMessage({type:"pubcast:2i-paper",text:target.value.slice(-500)},event.origin);
  });
  function syncKeysButton(){
    const active=document.body.dataset.twoiDesk==="typewriter";
    keysButton.hidden=!active;
    keysButton.style.display=active?"":"none";
    if(!active&&keysLayer)keysLayer.style.display="none";
  }
  document.addEventListener("twoi:presentation-change",syncKeysButton);
  syncKeysButton();
  if(!config.seated)return;
  const figure=el("figure",null,$("notebookFrame"));figure.id="twoiDeskScene";
  const img=el("img",null,figure);img.src="/static/world/rooms/dressing_typewriter_sitting.png";img.alt="First-person view of the blue and gold typewriter at the desk";
  const preview=el("div","",figure);preview.id="twoiPaperPreview";preview.setAttribute("aria-hidden","true");
  el("figcaption",config.room==="writers_room"?"Seated typewriter · shared artwork pending room-specific view":"Seated at the dressing-room typewriter",figure);
  function syncPaper(){
    const text=coWriting?buffer.join("\n")||committed.join("\n"):soloTextarea.value;
    preview.textContent=text.slice(-500).split("\n").slice(-4).join("\n");
  }
  document.addEventListener("foresight:work-change",syncPaper);
  for(const input of [soloTextarea,draftArea])input.addEventListener("input",syncPaper);
  const oldRender=render;render=function(){oldRender();syncPaper();};syncPaper();
  const options=el("div",null,controls);options.id="twoiAudioOptions";
  const key="twoi.typewriter.audio.v1";/* Josie: "audio effects must be optional". Off until she turns them on; her choice is kept. */let preferences={click:false,bell:false};
  try{const old=JSON.parse(localStorage.getItem(key)||"null");if(old){if(typeof old.click==="boolean")preferences.click=old.click;if(typeof old.bell==="boolean")preferences.bell=old.bell;}}catch{}
  function toggle(name,label){
    const l=el("label",null,options),i=el("input",null,l);i.type="checkbox";i.checked=preferences[name];l.append(document.createTextNode(" "+label));i.onchange=()=>{preferences[name]=i.checked;try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}};
  }
  toggle("click","Key clicks");toggle("bell","Line-end bell");
  const syncPresentation=()=>{const active=document.body.dataset.twoiDesk==="typewriter";figure.hidden=!active;options.style.display=active?"":"none";if(active)syncPaper();};
  document.addEventListener("twoi:presentation-change",syncPresentation);syncPresentation();
  let ctx=null,lastClick=0;
  function sound(kind){
    if(document.body.dataset.twoiDesk!=="typewriter"||!preferences[kind])return;
    // Private UI effects only; not production/broadcast audio.
    try{
      const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
      if(!ctx)ctx=new AC();if(ctx.state==="suspended")ctx.resume().catch(()=>{});
      const t=ctx.currentTime;if(kind==="click"&&t-lastClick<0.022&&lastClick!==0)return;if(kind==="click")lastClick=t;
      const o=ctx.createOscillator(),g=ctx.createGain();o.type=kind==="bell"?"sine":"triangle";o.frequency.setValueAtTime(kind==="bell"?1450:940,t);
      if(kind==="click")o.frequency.exponentialRampToValueAtTime(190,t+0.027);
      g.gain.setValueAtTime(kind==="bell"?0.075:0.045,t);g.gain.exponentialRampToValueAtTime(0.001,t+(kind==="bell"?0.22:0.042));o.connect(g);g.connect(ctx.destination);o.start(t);o.stop(t+(kind==="bell"?0.23:0.05));o.onended=()=>{o.disconnect();g.disconnect();};
    }catch{}
  }
  const before=new WeakMap();
  function isWriting(node){return node===soloTextarea||node===draftArea||node?.matches?.(".m-line-edit textarea");}
  document.addEventListener("beforeinput",e=>{if(e.isTrusted&&isWriting(e.target)&&!e.isComposing)before.set(e.target,e.target.value);},true);
  document.addEventListener("input",e=>{
    if(!e.isTrusted||!isWriting(e.target)||e.isComposing||!before.has(e.target))return;
    const old=before.get(e.target);before.delete(e.target);
    const c=TwoiStudioBridge.cue(old,e.target.value,e.target.selectionStart,e.inputType,e.data);
    if(c.click)sound("click");if(c.bell)sound("bell");
  });
  window.addEventListener("pagehide",()=>{if(ctx){ctx.close().catch(()=>{});ctx=null;}});
})();
