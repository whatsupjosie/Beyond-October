/* Stable version identity, independent main/working/review status. */
function versionCore(){
  const palette=["#3376bd","#8256bb","#bc7150","#24948c","#c94f86","#697a36","#a05a37","#5361c2","#9a6baf","#377e57","#a66315","#566879"];
  function color(ordinal){return palette[(Math.max(1,Number(ordinal)||1)-1)%palette.length];}
  function describe(v,{here=false,dirty=false,localRevision=null,stale=false}={}){
    if(!v)return{color:"#777",label:"Unconfirmed version",marks:[...(here?["OPEN HERE"]:[]),"Local / unconfirmed"]};
    const marks=[];if(here)marks.push("OPEN HERE");if(v.id===v.main_id)marks.push("MAIN");if(v.id===v.working_id)marks.push("WORKING");
    if(v.departed)marks.push("DEPARTED");
    if(stale)marks.push("STATUS UNCONFIRMED");
    else if(dirty||localRevision!==null&&localRevision!==v.revision||v.review_status!=="reviewed")marks.push("NEEDS REVIEW");
    else marks.push("REVIEWED");
    return{color:color(v.ordinal),label:"V"+v.ordinal,marks};
  }
  return {color,describe};
}
const VersionIdentityCore=versionCore();
if(typeof module!=="undefined"&&module.exports)module.exports=VersionIdentityCore;
if(typeof document!=="undefined")(function installVersionIdentity(){
  if(reachFileMode)return;
  const C=VersionIdentityCore, state={id:null,version:null,rows:[],stale:true,busy:false,request:0};
  const el=(tag,text,parent)=>{const o=document.createElement(tag);if(text!==undefined)o.textContent=text;if(parent)parent.append(o);return o;};
  const button=(text,parent,fn)=>{const b=el("button",text,parent);b.type="button";b.className="mc-btn";b.onclick=fn;return b;};
  const css=el("style",`#twoiVersionBar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;flex-shrink:0;padding:4px 9px;border-left:7px solid #777;background:#24262d;color:#f9f7f2;font:12px/1.3 system-ui}#twoiVersionBar .mc-btn{margin-left:auto;flex:0 0 auto} .twoi-version-mark{display:inline-block;padding:2px 5px;border-radius:3px;margin:1px 3px 1px 0;border:1px solid currentColor;font:600 10px/1.3 system-ui} .twoi-review-green{color:#14643d;background:#e5f5e9}.twoi-review-amber{color:#794500;background:#fff0c9}.twoi-version-departed{border-style:dashed;opacity:.85} #twoiVersionDialog{width:min(690px,94vw);max-height:88dvh;overflow:auto;background:#f7efe0;color:#29231b;border:1px solid #8b7250;border-radius:12px;padding:16px;font:14px/1.4 system-ui}#twoiVersionDialog::backdrop{background:#0008}#twoiVersionDialog .mc-btn{margin:3px;min-height:32px;flex:0 1 auto}#twoiVersionDialog input{max-width:100%;padding:6px}`,document.head);
  const bar=el("div",undefined);bar.id="twoiVersionBar";bar.setAttribute("aria-label","Current manuscript version");
  document.querySelector(".top-bar").after(bar);
  const info=el("span","Local / unconfirmed",bar), marks=el("span",undefined,bar);
  const manage=button("Versions",bar,()=>openVersions());manage.id="twoiVersionManage";
  function markPills(host,values){
    host.replaceChildren();
    values.forEach(m=>{const a=el("span",m,host);a.className="twoi-version-mark"+(m==="REVIEWED"?" twoi-review-green":m==="NEEDS REVIEW"?" twoi-review-amber":m==="DEPARTED"?" twoi-version-departed":"");});
  }
  function paint(){
    const v=state.id===documentId?state.version:null;
    const d=C.describe(v,{here:true,dirty:documentDirty,localRevision:revision,stale:state.stale});
    bar.style.borderLeftColor=d.color;bar.style.borderLeftStyle=v?.departed?"dashed":"solid";info.textContent=d.label+" · "+documentTitle;markPills(marks,d.marks);
    document.title=(v?d.label+" · "+d.marks.filter(m=>m==="MAIN"||m==="WORKING"||m==="DEPARTED"||m==="STATUS UNCONFIRMED").join(" / ")+" · ":"")+documentTitle+" — 2i";
  }
  let timer=null;
  async function refresh(){
    if(initializing||!networked||!serverReady){paint();return;}
    const wanted=documentId, token=++state.request;
    if(state.id!==wanted){state.id=wanted;state.version=null;state.rows=[];state.stale=true;paint();}
    try{
      const x=await api("/api/writers-room/documents/"+encodeURIComponent(wanted)+"/versions");
      if(token!==state.request||documentId!==wanted)return;
      state.id=wanted;state.version=x.current;state.rows=x.versions;state.stale=false;
    }catch{if(token===state.request&&documentId===wanted)state.stale=true;}
    paint();
  }
  const schedule=()=>{paint();clearTimeout(timer);timer=setTimeout(refresh,300);};
  document.addEventListener("foresight:work-change",schedule);
  addEventListener("focus",refresh);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden&&!generating&&!chatSending)refresh();},15000);
  window.reachStarted?.then(refresh).catch(()=>paint());
  window.decorateVersionShelf=function(b,v){
    if(!v.ordinal)return;
    const d=C.describe(v,{here:v.id===documentId,dirty:v.id===documentId&&documentDirty});
    b.style.borderLeft="7px solid "+d.color;
    if(v.departed)b.style.borderLeftStyle="dashed";
    el("small",d.label+" · "+d.marks.join(" · "),b);
  };
  window.forkSavedVersion=async function(source,number,title){
    if(!await preserveBeforeSwitch())return false;
    if(source!==documentId)throw Error("Active manuscript changed; reopen the version manager.");
    const before=mutation;const result=await api("/api/writers-room/documents/"+encodeURIComponent(source)+"/fork",{method:"POST",body:JSON.stringify({source_revision:number,title})});
    validateDocumentState(result.state);
    if(source!==documentId||before!==mutation||generating||chatSending){throw Error("The fork was saved, but the active editor changed. Open it from My manuscripts; the current work was not replaced.");}
    cancelLLM();stopPlaying();documentId=result.id;revision=result.revision;saveConflict=false;documentTitle=result.title;documentHandle=null;
    loadDocState(result.state);documentDirty=false;savedMutation=mutation;writeRecovery();setSaveStatus("Saved to Reach · revision "+revision);render();
    await refresh();return true;
  };
  window.createVersionFromCurrent=async function(){
    if(!await saveDocument())throw Error("Save the current manuscript successfully before creating a confirmed branch.");
    const name=prompt("Name the new version",documentTitle.slice(0,180)+" — alternate");
    if(name===null||!name.trim())return false;
    return window.forkSavedVersion(documentId,revision,name.trim().slice(0,200));
  };
  async function openVersions(){
    if(initializing||generating||chatSending)return;
    const existing=document.getElementById("twoiVersionDialog");if(existing)existing.remove();
    const d=el("dialog",undefined,document.body);d.id="twoiVersionDialog";d.setAttribute("aria-label","Story version manager");
    el("h2","Story versions",d);
    el("p","Color identifies the branch. MAIN and WORKING are independent project designations. OPEN HERE identifies this editor. Review is tied to the saved revision.",d);
    const status=el("p","Loading…",d);status.setAttribute("role","status");
    const rows=el("div",undefined,d),controls=el("div",undefined,d);
    button("Close",controls,()=>d.close());
    button("Fork current saved version",controls,async()=>{try{if(await window.createVersionFromCurrent())d.close();}catch(e){status.textContent=e.message;}});
    button("Refresh",controls,populate);
    d.addEventListener("close",()=>d.remove(),{once:true});d.showModal();await populate();
    async function populate(){
      await refresh();if(!d.open)return;
      rows.replaceChildren();
      if(state.stale||!state.version){status.textContent="Version information is not confirmed. Save and reconnect to manage lineage.";return;}
      status.textContent="Confirmed family · "+state.rows.length+" version(s)";
      for(const v of state.rows){
        const desc=C.describe(v,{here:v.id===documentId,dirty:v.id===documentId&&documentDirty,localRevision:v.id===documentId?revision:null});
        const box=el("div",undefined,rows);Object.assign(box.style,{borderLeft:"7px "+(v.departed?"dashed":"solid")+" "+desc.color,padding:"8px",margin:"8px 0",background:"#fffaf0"});
        el("strong",desc.label+" · "+v.title+" · r"+v.revision,box);
        if(v.parent_id){const parent=state.rows.find(x=>x.id===v.parent_id);el("p","Departed from "+(parent?"V"+parent.ordinal:v.parent_id)+" revision "+v.parent_revision,box);}
        const badges=el("div",undefined,box);markPills(badges,desc.marks);
        async function act(action){
          if(documentDirty||generating||chatSending){status.textContent="Save current work and finish active requests first.";return;}
          if(action==="reviewed"&&!confirm("Mark saved revision "+v.revision+" as reviewed?"))return;
          if((action==="main"||action==="working"||action==="depart")&&!confirm("Apply "+action+" to "+desc.label+"? Manuscript text will not change."))return;
          try{await api("/api/writers-room/documents/"+encodeURIComponent(v.id)+"/version-action",{method:"POST",body:JSON.stringify({action,expected_epoch:v.epoch,expected_revision:v.revision})});await populate();}
          catch(e){status.textContent=e.message;}
        }
        if(v.id!==documentId){
          button("Open in new tab",box,()=>{
            const url=new URL(location.href);url.searchParams.delete("file");url.searchParams.delete("foresightSession");url.searchParams.set("document",v.id);
            const link=el("a",undefined,document.body);link.href=url.href;link.target="_blank";link.rel="noopener";link.click();link.remove();
          });
        }
        if(v.id!==documentId)button("Open here",box,async()=>{
          try{
            if(!await preserveBeforeSwitch())return;
            const prior=documentId,before=mutation;
            const result=await api("/api/writers-room/documents/"+encodeURIComponent(v.id));
            validateDocumentState(result.state);
            if(documentId!==prior||mutation!==before||generating||chatSending)throw Error("Editor changed; retry opening this version.");
            cancelLLM();stopPlaying();documentId=v.id;revision=result.revision;saveConflict=false;documentTitle=result.title;documentHandle=null;loadDocState(result.state);documentDirty=false;savedMutation=mutation;writeRecovery();setSaveStatus("Saved to Reach · revision "+revision);render();await refresh();d.close();
          }catch(e){status.textContent=e.message;}
        });
        if(!v.departed){
          if(v.id!==v.main_id)button("Set main",box,()=>act("main"));
          if(v.id!==v.working_id)button("Set working",box,()=>act("working"));
          if(v.id!==v.main_id&&v.id!==v.working_id)button("Mark departed",box,()=>act("depart"));
        }else button("Reactivate",box,()=>act("reactivate"));
        if(v.review_status!=="reviewed")button("Mark reviewed",box,()=>act("reviewed"));else button("Needs review",box,()=>act("needs_review"));
      }
    }
  }
  paint();
})();
