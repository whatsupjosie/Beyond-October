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
  // Claude's original /typewriter-console remains the source of the key mapping,
  // key animations, keyboard support and sound. The 2i editor owns the words.
  const figure=el("figure",null,$("notebookFrame"));figure.id="twoiDeskScene";
  const typewriter=el("iframe",null,figure);
  typewriter.id="twoiTypewriterConsole";
  typewriter.title="Interactive blue and brass typewriter";
  typewriter.src="/typewriter-console?embedded=2i";
  typewriter.loading="lazy";
  el("figcaption",config.seated?"Type on the machine or in the manuscript":"Typewriter view · keys edit this manuscript",figure);

  function currentText(){
    return coWriting ? (buffer.join("\n")||committed.join("\n")) : soloTextarea.value;
  }
  function syncPaper(){
    if(typewriter.dataset.ready!=="true" || !typewriter.contentWindow)return;
    typewriter.contentWindow.postMessage({
      type:"pubcast:2i-manuscript",
      // Only a decorative excerpt goes into the frame. Saving uses the actual editor.
      text:currentText().slice(-2000)
    },location.origin);
  }
  typewriter.addEventListener("load",()=>{typewriter.dataset.ready="false";});
  window.addEventListener("message",event=>{
    // Do not accept commands from another frame, domain, or an inactive view.
    if(event.source!==typewriter.contentWindow || event.origin!==location.origin)return;
    const data=event.data;
    if(data?.type==="pubcast:2i-ready"){
      typewriter.dataset.ready="true";syncPaper();return;
    }
    if(data?.type!=="pubcast:2i-key" || document.body.dataset.twoiDesk!=="typewriter")return;
    if(initializing || generating || chatSending || editingIdx!==null){
      addChat("notice","Finish the active edit or request before using the typewriter keys.");
      return;
    }
    const target=coWriting?draftArea:soloTextarea;
    if(!window.TwoiTypewriterInput){
      addChat("notice","Typewriter input is unavailable; write in the manuscript instead.");
      return;
    }
    window.TwoiTypewriterInput.apply(target,data.key);
    // Existing input handlers enforce locked lines and synchronize Save Now.
    syncPaper();
  });
  document.addEventListener("foresight:work-change",syncPaper);
  for(const input of [soloTextarea,draftArea])input.addEventListener("input",syncPaper);
  const oldRender=render;
  render=function(){oldRender();syncPaper();};
  const syncPresentation=()=>{
    const active=document.body.dataset.twoiDesk==="typewriter";
    figure.hidden=!active;
    if(active)syncPaper();
  };
  document.addEventListener("twoi:presentation-change",syncPresentation);
  syncPresentation();
})();
