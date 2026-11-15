/* Native 2i studio presentation and shared production notes. */
(function installStudioDesk(){
  if(reachFileMode)return;
  const q=new URLSearchParams(location.search),config=TwoiStudioBridge.presentation(q.get("studio_room"),q.get("studio_view"),q.get("desk"));
  document.body.dataset.twoiDesk=config.seated?"typewriter":"notebook";
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
  const key="twoi.typewriter.audio.v1";let preferences={click:true,bell:true};
  try{const old=JSON.parse(localStorage.getItem(key)||"null");if(old){if(typeof old.click==="boolean")preferences.click=old.click;if(typeof old.bell==="boolean")preferences.bell=old.bell;}}catch{}
  function toggle(name,label){
    const l=el("label",null,options),i=el("input",null,l);i.type="checkbox";i.checked=preferences[name];l.append(document.createTextNode(" "+label));i.onchange=()=>{preferences[name]=i.checked;try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}};
  }
  toggle("click","Key clicks");toggle("bell","Line-end bell");
  let ctx=null,lastClick=0;
  function sound(kind){
    if(!preferences[kind])return;
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
