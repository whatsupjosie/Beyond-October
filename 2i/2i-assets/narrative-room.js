/* 2i scene intelligence, author-controlled drafting and advisory review. */
(function installNarrativeRoom(){
  "use strict";
  // Ordinary manuscripts only. File trays retain their existing editing path.
  if(new URLSearchParams(location.search).has("file"))return;
  const C=NarrativeCore;
  let state=C.fresh(),serial=0,audioSerial=0,activeAudio=null;
  let panel=null,form={},sceneSelect=null,report=null,notice=null,archiveView=null;
  const id=()=>crypto.randomUUID?crypto.randomUUID():"scene_"+Date.now()+"_"+Math.random().toString(36).slice(2);
  const current=()=>state.scenes.find(s=>s.id===state.activeSceneId)||null;
  function selectScene(next){C.selectScene(state,next);}
  window.twoiNarrativeHistory={capture:()=>C.captureUndo(state,[...PP_GEN]),restore:(point,displaced,kind)=>{state=C.restoreUndo(state,point,displaced,kind);PP_GEN.clear();for(const text of point.generated||[])ppMarkGenerated(text);}};
  const scope=()=>typeof documentId==="undefined"?"standalone":documentId;
  const partner=()=>typeof partnerId==="undefined"?"pubpartner":partnerId;
  const ownerReady=()=>typeof initializing==="undefined"||!initializing;
  const say=(s)=>{if(notice)notice.textContent=s;const bar=$("narrativeStatus");if(bar)bar.textContent=s;};
  const save=()=>{markDirty();if(typeof writeRecovery==="function")writeRecovery();};
  const meta=()=>({sceneId:state.activeSceneId,documentId:scope(),createdAt:new Date().toISOString(),revision:typeof revision==="undefined"?null:revision});
  // Detect accidental movement of numeric anchors. Not a cryptographic permission
  // check. Authors explicitly re-anchor a scene if an earlier edit moved it.
  function anchor(lines){let a=2166136261,b=0;for(const line of lines){for(let i=0;i<line.length;i++){a=Math.imul(a^line.charCodeAt(i),16777619);b++;}a=Math.imul(a^10,16777619);}return lines.length+":"+b+":"+(a>>>0);}
  function anchorScene(s){s.prefixAnchor=anchor(committed.slice(0,s.start));s.suffixAnchor=s.end===null?null:anchor(committed.slice(s.end));return s;}
  function checkAnchor(s){
    if(s.prefixAnchor!==undefined&&s.prefixAnchor!==anchor(committed.slice(0,s.start)))throw Error("Earlier material changed. Review the scene's start line and save its dossier before continuing.");
    if(s.end!==null&&s.suffixAnchor!==undefined&&s.suffixAnchor!==anchor(committed.slice(s.end)))throw Error("Later material changed. Review the scene's end line and save its dossier before continuing.");
  }
  const originalGet=getDocState,originalLoad=loadDocState,originalToggle=toggleMode,originalApprove=approveBuffer;
  getDocState=function(){return {...originalGet(),narrative:C.clone(state),generatedLineTexts:[...PP_GEN]};};
  loadDocState=function(data){
    const restored=C.restore(data.narrative);
    if(restored.latentByScene!==undefined&&(!Array.isArray(restored.latentByScene)||restored.latentByScene.some(x=>!x||typeof x.id!=="string"||typeof x.text!=="string")))throw Error("Invalid latent scene archive; retain the original document.");
    // Old editors advanced pointer before the current reading line was approved.
    // Its precise review status is unknown; retain it as a recovery candidate.
    const previousLine=(data.pool||[])[(data.pointer||0)-1];
    if(previousLine&&!restored.archive.some(x=>x.kind==="legacy last-read candidate"&&x.text===previousLine))C.archive(restored,"legacy last-read candidate",previousLine,{migration:true});
    const pending=(data.pool||[]).slice(data.pointer||0).join("\n");
    if(pending){C.archive(restored,"legacy queue",pending,{migration:true});restored.latent+=(restored.latent?"\n":"")+pending;}
    serial++;audioSerial++;activeAudio=null;reading=null;playing=false;inReaction=false;cancelSpeech();
    state=restored;
    PP_GEN.clear();for(const text of data.generatedLineTexts||[])if(typeof text==="string")ppMarkGenerated(text);
    PP.intelligence=null;PP.online=false;PP.lastCommit=0;ppRenderCast();ppRenderFlags();ppSetStatus("checking document");
    originalLoad({...data,pool:[],pointer:0,coWriting:!!data.coWriting||!!data.buffer?.length,references:data.references||[]});
    if(panel?.open)fill();
    updateBar();
  };
  function updateBar(){
    const s=current(),n=C.footprint(buffer.join("\n"));
    const el=$("narrativeBudget");if(el)el.textContent=(s?s.title:"No scene selected")+" · "+n.words+"/500 draft words · "+(state.latent?"latent material retained":"no latent material");
  }
  function make(tag,text,parent){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(parent)parent.append(el);return el;}
  function button(text,parent,fn){const e=make("button",text,parent);e.type="button";e.className="mc-btn";e.onclick=fn;return e;}
  function field(label,key,rows=2,kind="textarea"){const labelEl=make("label",label,panelBody);const input=make(kind,undefined,labelEl);input.id="narrative_"+key;if(kind==="textarea")input.rows=rows;else if(kind==="input")input.type=key==="start"||key==="end"?"number":"text";form[key]=input;return input;}
  let panelBody;
  const names={purpose:"Dramatic purpose",cast:"Cast / character identities",motivation:"Character objectives and obstacles",information:"Information distribution (recipient | fact | current state | intended state)",subtext:"Subtext",ambiguity:"Ambiguity / planned reveal",choreography:"Blocking, objects and physical continuity",emotionalProgression:"Emotional progression",dramaticProgression:"Dramatic progression / change",audienceImpact:"Intended audience impact",dependencies:"Dependencies / preceding and later scenes",editorialAttention:"Particular attention / punch-up targets",executionAssessment:"Author's assessment"};
  function makePanel(){
    const style=make("style",`#narrativeDialog{width:min(720px,94vw);max-height:90dvh;overflow:auto;background:#f7efe0;color:#29231b;border:1px solid #8b7250;border-radius:12px;padding:18px;font:14px/1.4 system-ui}#narrativeDialog::backdrop{background:#0008}#narrativeDialog label{display:block;margin:10px 0;color:inherit;font-weight:600}#narrativeDialog input,#narrativeDialog select,#narrativeDialog textarea{display:block;width:100%;box-sizing:border-box;margin:4px 0 0;padding:7px;background:#fffaf0;color:#29231b;border:1px solid #ad9b83;border-radius:5px;font:inherit}#narrativeDialog textarea{resize:vertical}#narrativeDialog .narrative-actions{display:flex;gap:7px;flex-wrap:wrap;margin:9px 0}#narrativeDialog pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:35vh;overflow:auto;font:inherit;background:#fffaf0;padding:10px;border:1px solid #ad9b83}#narrativeDialog .mc-btn{min-height:34px;flex:0 1 auto}#narrativeBudget,#narrativeStatus{font-size:11px;overflow-wrap:anywhere;margin-top:5px}`,document.head);
    panel=make("dialog",undefined,document.body);panel.id="narrativeDialog";panel.setAttribute("aria-label","Narrative intelligence");
    make("h2","Scene intelligence",panel);
    make("p","Define the purpose and intended effect, not a compulsory formula. Dossiers and assessments are separate from the manuscript.",panel);
    const top=make("div",undefined,panel);top.className="narrative-actions";
    button("Close",top,()=>{if(!formChanged()||confirm("Discard unsaved dossier edits?"))panel.close();});
    button("Cancel model request",top,()=>{if(generating){stopPlaying();say("Cancellation requested. No new draft will be applied.");}});
    button("New scene",top,()=>{if(formChanged()&&!confirm("Discard unsaved dossier edits?"))return;if(!ownerReady()||generating||chatSending||buffer.some(x=>x.trim()))return say("Finish the current draft or active request first.");const c=current();if(c&&c.end===null){c.end=committed.length;anchorScene(c);}const start=committed.length;const s=anchorScene(C.scene(id(),"Scene "+(state.scenes.length+1),start,null));state.scenes.push(s);selectScene(s.id);save();fill();updateBar();});
    const selectLabel=make("label","Active scene",panel);sceneSelect=make("select",undefined,selectLabel);sceneSelect.onchange=()=>{if(formChanged()&&!confirm("Discard unsaved dossier edits?")){sceneSelect.value=state.activeSceneId||"";return;}if(!ownerReady()||generating||chatSending||buffer.some(x=>x.trim())){sceneSelect.value=state.activeSceneId||"";return say("Resolve the current draft or request before switching scenes.");}selectScene(sceneSelect.value||null);save();fill();updateBar();};
    panelBody=make("div",undefined,panel);
    field("Scene title","title",1,"input");field("First manuscript line (1-based)","start",1,"input");form.start.min="1";
    field("Last manuscript line (blank = current end)","end",1,"input");form.end.min="0";
    const medium=field("Medium","medium",1,"select");for(const [v,t] of [["prose","Novel / prose"],["screenplay","Screenplay"],["stage","Stage"],["audio","Audio drama"],["other","Other"]]){const o=make("option",t,medium);o.value=v;}
    for(const f of C.fields)field(names[f],f,f==="information"?4:2);
    form.information.placeholder="Audience | the letter exists | unaware | suspects";
    make("p","Knowledge states: knows, suspects, unaware, false belief, uncertain. Intended states may also be withhold, reveal, maintain, misdirect or resolve.",panelBody);
    field("Confirmed author decisions / corrections","decisions",3);
    const actions=make("div",undefined,panel);actions.className="narrative-actions";
    button("Save dossier",actions,apply);
    button("Suggest dossier",actions,()=>run("dossier"));
    button("Review scene",actions,()=>run("review"));
    button("Generate / reconsider next draft",actions,()=>run("draft"));
    button("Archive current draft",actions,archiveDraft);
    button("Show creative archive",actions,()=>{archiveView.hidden=!archiveView.hidden;refreshArchive();});
    notice=make("p","Ready.",panel);notice.setAttribute("role","status");
    report=make("pre","No assessment yet.",panel);report.setAttribute("aria-label","Editorial advisory");
    archiveView=make("pre","",panel);archiveView.hidden=true;archiveView.setAttribute("aria-label","Creative archive (not canon)");
    panel.addEventListener("cancel",e=>{if(formChanged()&&!confirm("Discard unsaved dossier edits?"))e.preventDefault();});
  }
  function refreshArchive(){if(!archiveView||archiveView.hidden)return;archiveView.textContent=state.archive.map(x=>`${x.kind} · ${x.createdAt||"migrated"} · ${x.sceneId||"unassigned"}\n${x.text}`).join("\n\n────────\n\n")||"No archived material.";}
  function fill(){
    if(!panel)return;
    sceneSelect.replaceChildren();const empty=make("option","Choose or define a scene",sceneSelect);empty.value="";
    for(const s of state.scenes){const o=make("option",s.title,sceneSelect);o.value=s.id;}
    sceneSelect.value=state.activeSceneId||"";
    const s=current();
    const defaultStart=chapters.length?Math.min(committed.length,chapters[chapters.length-1].startLine):0;
    form.title.value=s?.title||"Scene "+(state.scenes.length+1);form.start.value=(s?.start??defaultStart)+1;form.end.value=s?.end??"";
    form.medium.value=s?.medium||"prose";for(const f of C.fields)form[f].value=s?.[f]||"";
    form.decisions.value=s?.decisions||"";
    refreshReport();
    refreshArchive();
  }
  function refreshReport(){
    const values=[state.review,state.proposal].filter(x=>x?.sceneId===state.activeSceneId);
    if(!values.length){report.textContent="No assessment for this scene yet.";return;}
    report.textContent=values.map(v=>{
      let matching=false;try{matching=v.source===anchor([stamp(build(v.kind||"review"))]);}catch{}
      return (matching?"Current context":"Older context / draft; reassess before relying on it")+"\n"+v.text;
    }).join("\n\n────────\n\n");
  }
  function openPanel(){if(!ownerReady()){say("Wait for the account to open.");return;}if(!panel)makePanel();fill();panel.showModal();}
  function formChanged(){
    if(!panel?.open)return false;const s=current();
    if(!s)return C.fields.some(f=>form[f].value.trim())||!!form.decisions.value.trim();
    return form.title.value.trim()!==s.title||Number(form.start.value)-1!==s.start||(form.end.value.trim()===""?null:Number(form.end.value))!==s.end||form.medium.value!==(s.medium||"prose")||form.decisions.value!==(s.decisions||"")||C.fields.some(f=>form[f].value!==s[f]);
  }
  function apply(){
    try{
      if(!ownerReady()||generating||chatSending)throw Error("Wait for the active request.");
      const start=Number(form.start.value)-1,end=form.end.value.trim()===""?null:Number(form.end.value);
      if(start<0||start>committed.length||end!==null&&(end>committed.length||end<start))throw Error("Scene range is outside the current manuscript.");
      const old=current();const s=C.scene(old?.id||id(),form.title.value.trim(),start,end,Object.fromEntries(C.fields.map(f=>[f,form[f].value])));
      C.disclosure(s.information);s.medium=form.medium.value;s.decisions=form.decisions.value;
      anchorScene(s);
      if(old){state.scenes=state.scenes.map(x=>x.id===old.id?s:x);}else{state.scenes.push(s);selectScene(s.id);}
      save();fill();updateBar();say("Dossier saved. Existing latent prose remains provisional.");
    }catch(e){say(e.message);}
  }
  function build(kind){
    const s=current();if(!s)throw Error("Save a scene dossier first.");
    checkAnchor(s);
    const history=typeof chatHistory==="undefined"?[]:chatHistory.filter(x=>!x.delivery).slice(-20).map(x=>({role:x.role,content:x.content}));
    const feedback=state.archive.filter(x=>x.sceneId===s.id&&["rejected presented draft","committed presented draft","author revised presented draft"].includes(x.kind)).slice(-6).map(x=>({kind:x.kind,text:x.text}));
    const ctx=C.context({lines:committed.slice(),chapters,active:s,buffer:buffer.slice(),decisions:[{confirmed:s.decisions||""},{recentDiscussion:history},{recentReviewOutcomes:feedback}],latent:kind==="draft"?state.latent:"",medium:s.medium||"prose"});
    ctx.references=references.map(r=>({name:r.name,type:r.type,content:r.content}));
    return ctx;
  }
  const stamp=ctx=>JSON.stringify([scope(),partner(),ctx,C.clone(state.scenes),state.activeSceneId]);
  function archiveDraft(){
    if(!ownerReady()||!coWriting||generating||chatSending||editingIdx!==null)return say("Finish the active request or edit and enter Collab mode first.");
    if(!buffer.length&&!state.presentedOriginal)return say("There is no presented draft to archive.");
    if(!confirm("Archive this entire uncommitted draft? It will remain recoverable, but will leave the active manuscript draft."))return;
    snapshot();C.archive(state,"rejected presented draft",buffer.join("\n"),meta());if(state.presentedOriginal&&state.presentedOriginal!==buffer.join("\n"))C.archive(state,"original rejected AI draft",state.presentedOriginal,meta());state.presentedOriginal="";state.presentedBasis=null;state.presentedSceneId=null;buffer=[];reading=null;stopPlaying();save();render();updateBar();refreshArchive();say("Draft archived. Reconsider any remaining latent material before presenting it.");
  }
  async function run(kind){
    if(!ownerReady()||generating||chatSending||editingIdx!==null){say("Finish the active request or inline edit first.");return false;}
    if(formChanged()){say("Save the changed scene dossier before requesting model work.");return false;}
    if(kind==="draft"&&!coWriting){say("Enter Collab mode to generate manuscript prose.");return false;}
    if(kind==="draft"&&(buffer.length||reading||state.presentedOriginal)){say("Review, commit or archive the existing presented draft before requesting more.");return false;}
    if(playing)stopPlaying();
    let ctx,prompts,source,token,origin;
    try{
      ctx=build(kind);if(kind==="draft"&&!ctx.endsAtManuscriptEnd)throw Error("This editor can only append at the manuscript end. Use editorial review for earlier scenes.");
      prompts=C.prompt(ctx,kind);source=stamp(ctx);origin=scope();
      if(!llmOk())throw Error("Configure a model first.");
    }catch(e){say(e.message);if(!current()&&!panel?.open)openPanel();return false;}
    token=++serial;generating=true;$("genBtn").disabled=true;
    document.dispatchEvent(new Event("foresight:work-change"));say(kind==="draft"?"Rereading and reconsidering…":"Reading for editorial assessment…");render();
    let raw="";
    try{
      raw=await callLLM(prompts,{narrativeKind:kind});
      if(origin!==scope())throw Error("The document changed during the request; no result was applied.");
      let fresh=false;try{fresh=token===serial&&source===stamp(build(kind));}catch{}
      if(!fresh){C.archive(state,"stale "+kind,raw,meta());save();say("The manuscript, partner, or dossier changed. The stale response was archived, not presented.");return false;}
      if(kind!=="draft"){
        const value={sceneId:state.activeSceneId,text:raw,source:anchor([source]),kind,createdAt:new Date().toISOString()};
        const key=kind==="review"?"review":"proposal";const previous=state[key];if(previous)C.archive(state,"superseded "+key,previous.text,{...meta(),sceneId:previous.sceneId});
        state[key]=value;
        if(report)report.textContent=raw;save();say("Advisory ready. No manuscript text was changed.");return true;
      }
      let d;try{d=C.parseDraft(raw);}catch(e){C.archive(state,"unparsed model response",raw,meta());save();throw e;}
      // No model code can write to committed. ONLY the author's explicit
      // Commit draft action can move this text across the editorial boundary.
      snapshot();
      C.archive(state,"superseded latent draft",state.latent,meta());
      state.latent=d.latent;
      if(d.notes){if(state.review)C.archive(state,"superseded review",state.review.text,{...meta(),sceneId:state.review.sceneId});state.review={sceneId:state.activeSceneId,text:d.notes,source:anchor([source]),kind:"draft",createdAt:new Date().toISOString()};}
      state.presentedOriginal=d.presented;state.presentedSceneId=state.activeSceneId;state.presentedBasis=anchor([JSON.stringify([ctx.section,ctx.previous,ctx.decisions[0],ctx.scene,ctx.knowledge])]);buffer=d.presented.split("\n");buffer.forEach(ppMarkGenerated);
      save();render();updateBar();refreshArchive();if(report&&d.notes)report.textContent=d.notes;
      say("Draft presented within the two-page approximation. Review before continuing.");if(panel?.open)panel.close();return true;
    }catch(e){say(e.name==="AbortError"?"Request cancelled; manuscript unchanged.":e.message);return false;}
    finally{generating=false;$("genBtn").disabled=false;render();updateBar();document.dispatchEvent(new Event("foresight:work-change"));}
  }
  // A commit must be consciously authorized. Never approve because of a
  // mode switch or elapsed playback time. Preserve the exact presented batch.
  approveBuffer=function(){
    if(!ownerReady()||generating||chatSending||editingIdx!==null)return say("Finish the active request or inline edit before committing.");
    if(playing)stopAudio();
    if(!buffer.length)return;
    if(state.presentedOriginal&&state.presentedSceneId===state.activeSceneId){
      let matches=false;try{const ctx=build("draft");matches=state.presentedBasis===anchor([JSON.stringify([ctx.section,ctx.previous,ctx.decisions[0],ctx.scene,ctx.knowledge])]);}catch{}
      if(!matches&&!confirm("The scene or author decisions changed after this draft was generated. Commit it anyway, or cancel to archive and reconsider?"))return;
      if(state.presentedOriginal!==buffer.join("\n")){C.archive(state,"author revised presented draft",state.presentedOriginal,meta());}
    }
    C.archive(state,"committed presented draft",buffer.join("\n"),meta());originalApprove();state.presentedOriginal="";state.presentedBasis=null;state.presentedSceneId=null;save();updateBar();refreshArchive();
  };
  $("approveBtn").onclick=approveBuffer;
  toggleMode=function(){
    if(generating||chatSending||editingIdx!==null)return say("Finish the active request or inline edit before switching modes.");
    if(coWriting&&buffer.length)return say("Commit or archive the presented draft explicitly before switching modes.");
    snapshot();originalToggle();updateBar();
  };
  $("modeBadge").onclick=toggleMode;
  // Playback reads the displayed text only; no timer or skip action can
  // invoke inference or approve prose.
  function stopAudio(){audioSerial++;activeAudio=null;cancelSpeech();playing=false;inReaction=false;render();}
  stopPlaying=function(){if(generating){serial++;cancelLLM();}stopAudio();};
  function nextAudio(){
    const a=activeAudio;if(!a||!playing)return;
    if(a.source!==buffer.join("\n")||a.index>=a.lines.length){stopAudio();return;}
    const t=++audioSerial;const line=a.lines[a.index++];
    if(!line.trim()){nextAudio();return;}
    speechRead(line,()=>{if(t===audioSerial&&a===activeAudio)nextAudio();});
  }
  startPlaying=function(){if(playing||generating||chatSending||!buffer.some(x=>x.trim()))return;activeAudio={source:buffer.join("\n"),lines:buffer.filter(x=>x.trim()),index:0};playing=true;render();nextAudio();};
  generateMore=()=>run("draft");
  tick=()=>run("draft");
  $("genBtn").onclick=()=>run("draft");$("playBtn").onclick=()=>playing?stopPlaying():startPlaying();
  $("stopBtn").onclick=stopPlaying;$("skipBtn").onclick=()=>{if(!playing||!activeAudio)return;cancelSpeech();audioSerial++;nextAudio();};
  const controls=$("mcSection").querySelector(".section-body");
  button("Scene intelligence",controls,openPanel).id="narrativeOpen";
  button("Revision history",controls,()=>{if(typeof showRevisionHistory==="function")showRevisionHistory();else say("Connect Reach to view server revisions.");}).id="narrativeHistory";
  button("Archive draft",controls,archiveDraft).id="narrativeArchiveDraft";
  const budget=make("p","",controls);budget.id="narrativeBudget";
  const status=make("p","",controls);status.id="narrativeStatus";status.setAttribute("role","status");
  draftArea.addEventListener("input",()=>{if(playing)stopAudio();updateBar();});
  document.addEventListener("foresight:work-change",updateBar);
  updateBar();
})();
