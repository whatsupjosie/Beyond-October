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
  // Runtime-only consent. Imported/forked history never starts a recorder.
  // All retained events live in the existing private narrative archive.
  let capture=null,sessionNotice="";
  const sessionActive=()=>!!capture&&capture.document===scope();
  function recordSession(event,details={},text=""){
    if(!sessionActive())return false;
    try{
      const row={...meta(),...C.sessionEvent(capture,event,details,text)},size=JSON.stringify(row).length*3;
      const reserve=2048;
      if(event!=="end"&&event!=="coverage-limit"&&(capture.events>=498||capture.bytes+size>capture.budget-reserve)){
        const gap=C.sessionEvent(capture,"coverage-limit",{reason:"budget"});state.archive.push({...meta(),...gap});capture.sequence++;capture.events++;
        const ended=C.sessionEvent(capture,"end",{reason:"budget"});state.archive.push({...meta(),...ended});capture=null;
        sessionNotice="Session capture stopped at its storage limit; later actions are not recorded. Existing manuscript and evidence retained.";
        say(sessionNotice);updateSessionControl();return false;
      }
      state.archive.push(row);capture.sequence++;capture.events++;capture.bytes+=size;
      return true;
    }catch(error){
      try{const gap=C.sessionEvent(capture,"coverage-limit",{reason:"error"});state.archive.push({...meta(),...gap});}catch{}
      capture=null;sessionNotice="Session capture stopped after an error; coverage is incomplete. Manuscript editing remains available.";say(sessionNotice);updateSessionControl();return false;
    }
  }
  function observeEdit(data){
    if(!sessionActive())return false;
    try{const details=C.observedEdit(capture,data);return details?recordSession("edit",details):false;}
    catch{recordSession("coverage-limit",{reason:"error"});if(sessionActive())stopCapture("error");else save();return false;}
  }
  function stopCapture(reason="explicit"){
    if(!sessionActive())return false;
    const recorded=recordSession("end",{reason});capture=null;
    if(recorded)sessionNotice=reason==="error"?"Creative session ended after an error; coverage is incomplete. Recorded material remains in the private manuscript archive.":"Creative session ended. Recorded material remains in the private manuscript archive.";
    say(sessionNotice);updateSessionControl();save();return recorded;
  }
  function startCapture(mode){
    if(!ownerReady()||generating||chatSending||editingIdx!==null||sessionActive()||!C.captureModes.includes(mode))throw Error("Finish active work or the current session before starting another.");
    const estimate=JSON.stringify(getDocState()).length*3,budget=Math.min(96000,Math.max(0,1600000-estimate));
    if(budget<8192)throw Error("This manuscript has insufficient estimated sync capacity for additional recording. Export a native copy or work in a smaller manuscript.");
    capture={id:id(),mode,document:scope(),sequence:0,events:0,bytes:0,budget};
    if(!recordSession("start")||!sessionActive()){save();throw Error("Capture could not start; "+sessionNotice);}
    sessionNotice="Creative capture active: "+mode+". It is limited to supported actions, not continuous surveillance.";updateSessionControl();save();
  }
  function updateSessionControl(){
    const button=$("narrativeSession");if(button)button.textContent=sessionActive()?"Creative session · "+capture.mode:"Creative session · off";
  }
  function openSession(){
    if(!ownerReady()||generating||chatSending||editingIdx!==null)return say("Finish active work before changing session capture.");
    const old=$("twoiSessionDialog");if(old)old.remove();
    const d=make("dialog",undefined,document.body);d.id="twoiSessionDialog";d.setAttribute("aria-label","Private creative session");
    Object.assign(d.style,{width:"min(620px,94vw)",maxHeight:"85dvh",overflow:"auto",padding:"16px",background:"#fffaf0",color:"#29231b",borderRadius:"10px"});
    const source=scope();
    make("h2","Private creative session",d);
    make("p","Opt in for this document and live editor only. Existing draft recovery and normal revision saving continue regardless. Capture is saved with the private native manuscript, including normal Reach sync if connected; it is not sent to a model or public disclosure. No automatic restart after reload, import or fork.",d);
    make("p",sessionNotice||"Capture is currently off.",d);
    const info=make("p","",d);info.setAttribute("role","status");
    const verify=()=>{if(source!==scope()||generating||chatSending||editingIdx!==null)throw Error("The document or active work changed. Reopen this dialog.");};
    function attempt(fn){try{verify();fn();d.close();}catch(e){info.textContent=e.message;}}
    if(sessionActive()){
      make("p",capture.mode+" · "+capture.events+" events · approximately "+Math.ceil(capture.bytes/1024)+" KiB of "+Math.floor(capture.budget/1024)+" KiB budget",d);
      const note=make("textarea",undefined,d);note.rows=3;note.maxLength=8000;note.placeholder="Optional private milestone or creative decision";
      button("Record milestone",d,()=>attempt(()=>{if(!note.value.trim())throw Error("Enter a milestone.");const recorded=recordSession("milestone",{},note.value);save();if(!recorded)throw Error(sessionNotice||"Milestone was not recorded.");}));
      button("End session",d,()=>attempt(()=>{if(!stopCapture("explicit"))throw Error(sessionNotice||"Session end was not recorded.");}));
    }else{
      const select=make("select",undefined,make("label","Capture depth",d));for(const [mode,label] of [["essential","Essential — approvals, rejections, decisions"],["significant","Significant — plus presented candidates, advisories, large edits and paste/drop metadata"],["comprehensive","Comprehensive — plus exact deltas at supported writing inputs"]]){const o=make("option",label,select);o.value=mode;}
      select.value="essential";
      make("p","Comprehensive recording can retain removed or pasted private text. All modes are bounded (up to 500 events / 96 KB estimated per session); unsupported actions and interrupted sessions may leave gaps. No keys, credentials, microphone, or unrelated activity are captured.",d);
      button("Start private capture",d,()=>attempt(()=>{if(!confirm("Start "+select.value+" private capture? Recorded content remains with this manuscript and its normal recovery/sync copies."))throw Error("Capture not started.");startCapture(select.value);}));
    }
    button("Close",d,()=>d.close());d.addEventListener("close",()=>d.remove(),{once:true});d.showModal();
  }
  window.twoiCreativeSession={observeEdit,record:recordSession,stopForSwitch:()=>stopCapture("switch"),active:sessionActive};
  // Detect accidental movement of numeric anchors. Not a cryptographic permission
  // check. Authors explicitly re-anchor a scene if an earlier edit moved it.
  function anchor(lines){let a=2166136261,b=0;for(const line of lines){for(let i=0;i<line.length;i++){a=Math.imul(a^line.charCodeAt(i),16777619);b++;}a=Math.imul(a^10,16777619);}return lines.length+":"+b+":"+(a>>>0);}
  function anchorScene(s){s.prefixAnchor=anchor(committed.slice(0,s.start));s.suffixAnchor=s.end===null?null:anchor(committed.slice(s.end));return s;}
  function outcomeBasis(s){return anchor([JSON.stringify([s.start,s.end??committed.length,committed.slice(s.start,s.end??committed.length),s.confirmedOutcomes||""])]);}
  function verifiedOutcomes(s){return !!s.outcomeBasis&&s.outcomeBasis===outcomeBasis(s);}
  function reviewBasis(ctx){return anchor([JSON.stringify([scope(),partner(),ctx.section,ctx.previous,ctx.scene,ctx.knowledge,ctx.continuity,ctx.references,ctx.documentFormat,ctx.decisions[0]])]);}
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
    capture=null;sessionNotice="";state=restored;updateSessionControl();
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
    const style=make("style",`#narrativeDialog{width:min(720px,94vw);max-height:90dvh;overflow:auto;background:#f7efe0;color:#29231b;border:1px solid #8b7250;border-radius:12px;padding:18px;font:14px/1.4 system-ui}#narrativeDialog::backdrop{background:#0008}#narrativeDialog label{display:block;margin:10px 0;color:inherit;font-weight:600}#narrativeDialog input,#narrativeDialog select,#narrativeDialog textarea{display:block;width:100%;box-sizing:border-box;margin:4px 0 0;padding:7px;background:#fffaf0;color:#29231b;border:1px solid #ad9b83;border-radius:5px;font:inherit}#narrativeDialog textarea{resize:vertical}#narrativeDialog .narrative-actions{display:flex;gap:7px;flex-wrap:wrap;margin:9px 0}#narrativeDialog pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:35vh;overflow:auto;font:inherit;background:#fffaf0;padding:10px;border:1px solid #ad9b83}#narrativeDialog .mc-btn{min-height:34px;flex:0 1 auto}`,document.head);
    panel=make("dialog",undefined,document.body);panel.id="narrativeDialog";panel.setAttribute("aria-label","Narrative intelligence");
    make("h2","Scene intelligence",panel);
    make("p","Define the purpose and intended effect, not a compulsory formula. Dossiers and assessments are separate from the manuscript.",panel);
    const top=make("div",undefined,panel);top.className="narrative-actions";
    button("Close",top,()=>{if(!formChanged()||confirm("Discard unsaved dossier edits?"))panel.close();});
    button("Cancel model request",top,()=>{if(generating){stopPlaying();say("Cancellation requested. No new draft will be applied.");}});
    button("New scene",top,()=>{if(formChanged()&&!confirm("Discard unsaved dossier edits?"))return;if(!ownerReady()||generating||chatSending||buffer.length||state.presentedOriginal)return say("Finish the current draft or active request first.");snapshot();const c=current();if(c&&c.end===null){const wasVerified=verifiedOutcomes(c);c.end=committed.length;anchorScene(c);if(wasVerified)c.outcomeBasis=outcomeBasis(c);}const start=committed.length;const s=anchorScene(C.scene(id(),"Scene "+(state.scenes.length+1),start,null));state.scenes.push(s);selectScene(s.id);save();fill();updateBar();});
    const selectLabel=make("label","Active scene",panel);sceneSelect=make("select",undefined,selectLabel);sceneSelect.onchange=()=>{if(formChanged()&&!confirm("Discard unsaved dossier edits?")){sceneSelect.value=state.activeSceneId||"";return;}if(!ownerReady()||generating||chatSending||buffer.length||state.presentedOriginal){sceneSelect.value=state.activeSceneId||"";return say("Resolve the current draft or request before switching scenes.");}snapshot();selectScene(sceneSelect.value||null);save();fill();updateBar();};
    panelBody=make("div",undefined,panel);
    field("Scene title","title",1,"input");field("First manuscript line (1-based)","start",1,"input");form.start.min="1";
    field("Last manuscript line (blank = current end)","end",1,"input");form.end.min="0";
    const medium=field("Medium","medium",1,"select");for(const [v,t] of [["prose","Novel / prose"],["screenplay","Screenplay"],["stage","Stage"],["audio","Audio drama"],["other","Other"]]){const o=make("option",t,medium);o.value=v;}
    for(const f of C.fields)field(names[f],f,f==="information"?4:2);
    form.information.placeholder="Audience | the letter exists | unaware | suspects";
    make("p","Knowledge states: knows, suspects, unaware, false belief, uncertain. Intended states may also be withhold, reveal, maintain, misdirect or resolve.",panelBody);
    field("Confirmed author decisions / corrections","decisions",3);
    field("Confirmed scene outcomes (recipient | fact | actual state)","confirmedOutcomes",3);
    form.confirmedOutcomes.placeholder="Audience | the letter exists | knows";
    make("p","Only record an outcome here after the author confirms it actually happened. Future reveals belong in Information distribution.",panelBody);
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
    form.decisions.value=s?.decisions||"";form.confirmedOutcomes.value=s?.confirmedOutcomes||"";
    if(s?.confirmedOutcomes&&!verifiedOutcomes(s))say("Confirmed outcomes are from older or unverified text. Review and explicitly reconfirm them before treating them as established.");
    refreshReport();
    refreshArchive();
  }
  function refreshReport(){
    const values=(state.advisories||[]).filter(x=>x.sceneId===state.activeSceneId);
    if(!values.length){report.textContent="No assessment for this scene yet.";return;}
    report.textContent=values.map(v=>{
      let matching=false;try{matching=v.source===anchor([stamp(build(v.kind||"review"))]);}catch{}
      return (matching?"Current context":"Older context / draft; reassess before relying on it")+"\n"+v.text;
    }).join("\n\n────────\n\n");
  }
  function openPanel(){if(!ownerReady()){say("Wait for the account to open.");return;}if(!panel)makePanel();fill();panel.showModal();}
  // Read-only navigation deliberately does not select or modify the active
  // AI scene, nor does it invoke inference or change the creative archive.
  window.twoiSceneNavigation=()=>state.scenes.map(s=>{
    let reason="";
    if(!Number.isInteger(s.start)||s.start<0||s.start>=committed.length||(s.end!==null&&(!Number.isInteger(s.end)||s.end<=s.start||s.end>committed.length)))reason="No valid committed scene range.";
    else if(s.prefixAnchor===undefined||(s.end!==null&&s.suffixAnchor===undefined))reason="Scene anchors have not been confirmed; review the dossier.";
    else try{checkAnchor(s);}catch(error){reason=error.message;}
    return {id:s.id,title:s.title,start:s.start,end:s.end,reason};
  });
  function formChanged(){
    if(!panel?.open)return false;const s=current();
    if(!s)return C.fields.some(f=>form[f].value.trim())||!!form.decisions.value.trim()||!!form.confirmedOutcomes.value.trim();
    return form.title.value.trim()!==s.title||Number(form.start.value)-1!==s.start||(form.end.value.trim()===""?null:Number(form.end.value))!==s.end||form.medium.value!==(s.medium||"prose")||form.decisions.value!==(s.decisions||"")||form.confirmedOutcomes.value!==(s.confirmedOutcomes||"")||C.fields.some(f=>form[f].value!==s[f]);
  }
  function apply(){
    try{
      if(!ownerReady()||generating||chatSending)throw Error("Wait for the active request.");
      const start=Number(form.start.value)-1,end=form.end.value.trim()===""?null:Number(form.end.value);
      if(start<0||start>committed.length||end!==null&&(end>committed.length||end<start))throw Error("Scene range is outside the current manuscript.");
      const old=current();const s=C.scene(old?.id||id(),form.title.value.trim(),start,end,Object.fromEntries(C.fields.map(f=>[f,form[f].value])));
      C.disclosure(s.information);C.outcomes(form.confirmedOutcomes.value);s.medium=form.medium.value;s.decisions=form.decisions.value;s.confirmedOutcomes=form.confirmedOutcomes.value;
      anchorScene(s);
      if(s.confirmedOutcomes.trim()){
        if(old?.confirmedOutcomes===s.confirmedOutcomes&&!verifiedOutcomes(old)&&!confirm("The source text or prior confirmation changed. Have you reread this scene and confirmed these outcomes still hold?"))s.outcomeBasis=old.outcomeBasis||null;
        else s.outcomeBasis=outcomeBasis(s);
      }
      snapshot();if(old){state.scenes=state.scenes.map(x=>x.id===old.id?s:x);}else{state.scenes.push(s);selectScene(s.id);}
      save();fill();updateBar();say("Dossier saved. Existing latent prose remains provisional.");
    }catch(e){say(e.message);}
  }
  function build(kind){
    const s=current();if(!s)throw Error("Save a scene dossier first.");
    checkAnchor(s);
    const history=typeof chatHistory==="undefined"?[]:chatHistory.filter(x=>!x.delivery).slice(-20).map(x=>({role:x.role,content:x.content}));
    const feedback=state.archive.filter(x=>x.sceneId===s.id&&["rejected presented draft","original rejected AI draft","committed presented draft","author revised presented draft"].includes(x.kind)).slice(-6).map(x=>({kind:x.kind,text:x.text}));
    const ctx=C.context({lines:committed.slice(),chapters,active:s,buffer:buffer.slice(),decisions:[{confirmed:s.decisions||""},{recentDiscussion:history},{recentReviewOutcomes:feedback}],latent:kind==="draft"?state.latent:"",medium:s.medium||"prose"});
    if(typeof getFormatContext==='function')ctx.documentFormat=getFormatContext();
    ctx.continuity=C.continuity(state.scenes,s,committed.length,verifiedOutcomes);
    if(s.confirmedOutcomes&&!verifiedOutcomes(s)){ctx.scene.confirmedOutcomesHistorical=ctx.scene.confirmedOutcomes;ctx.scene.confirmedOutcomes="";}
    ctx.references=references.map(r=>({name:r.name,type:r.type,content:r.content}));
    return ctx;
  }
  const stamp=ctx=>JSON.stringify([scope(),partner(),ctx,C.clone(state.scenes),state.activeSceneId]);
  function archiveDraft(){
    if(!ownerReady()||!coWriting||generating||chatSending||editingIdx!==null)return say("Finish the active request or edit and enter Collab mode first.");
    if(!buffer.length&&!state.presentedOriginal)return say("There is no presented draft to archive.");
    if(!confirm("Archive this entire uncommitted draft? It will remain recoverable, but will leave the active manuscript draft."))return;
    snapshot();const rejectionIndex=state.archive.length;C.archive(state,"rejected presented draft",buffer.join("\n"),meta());if(state.presentedOriginal&&state.presentedOriginal!==buffer.join("\n"))C.archive(state,"original rejected AI draft",state.presentedOriginal,meta());recordSession("rejection",state.archive.length>rejectionIndex?{archiveIndex:rejectionIndex}:{});state.presentedOriginal="";state.presentedBasis=null;state.presentedSceneId=null;buffer=[];reading=null;stopPlaying();save();render();updateBar();refreshArchive();say("Draft archived. Reconsider any remaining latent material before presenting it.");
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
        C.putAdvisory(state,value);
        if(sessionActive()&&capture.mode!=="essential")recordSession("advisory",{requestKind:kind});
        if(report)refreshReport();save();say("Advisory ready. No manuscript text was changed.");return true;
      }
      let d;try{d=C.parseDraft(raw);}catch(e){C.archive(state,"unparsed model response",raw,meta());save();throw e;}
      // No model code can write to committed. ONLY the author's explicit
      // Commit draft action can move this text across the editorial boundary.
      snapshot();
      C.archive(state,"superseded latent draft",state.latent,meta());
      state.latent=d.latent;
      if(d.notes)C.putAdvisory(state,{sceneId:state.activeSceneId,text:d.notes,source:anchor([source]),kind:"draft",createdAt:new Date().toISOString()});
      state.presentedOriginal=d.presented;state.presentedSceneId=state.activeSceneId;state.presentedBasis=reviewBasis(ctx);buffer=d.presented.split("\n");buffer.forEach(ppMarkGenerated);
      if(sessionActive()&&capture.mode!=="essential")recordSession("candidate",{requestKind:"draft"});
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
      let matches=false;try{const ctx=build("draft");matches=state.presentedBasis===reviewBasis(ctx);}catch{}
      if(!matches&&!confirm("The scene or author decisions changed after this draft was generated. Commit it anyway, or cancel to archive and reconsider?"))return;
    }
    const firstLine=committed.length,batch=buffer.slice(),accepted=batch.join("\n"),candidate=state.presentedSceneId===state.activeSceneId?state.presentedOriginal:null,context=meta();
    let failure=null;
    try{originalApprove();}catch(error){failure=error;}
    const applied=committed.length===firstLine+batch.length&&batch.every((line,index)=>committed[firstLine+index]===line)&&buffer.length===0;
    if(!applied){say(failure?"Approval did not finish: "+failure.message:"Approval could not be confirmed. Draft records were not marked committed.");return;}
    C.recordDraftApproval(state,{candidate,accepted,firstLine,lineCount:batch.length,meta:context});
    recordSession("approval",{archiveIndex:state.archive.length-1});
    state.presentedOriginal="";state.presentedBasis=null;state.presentedSceneId=null;save();updateBar();refreshArchive();
    if(failure)say("Text committed; a post-commit action failed: "+failure.message);
  };
  $("approveBtn").onclick=approveBuffer;
  toggleMode=function(){
    if(generating||chatSending||editingIdx!==null)return say("Finish the active request or inline edit before switching modes.");
    if(coWriting&&(buffer.length||state.presentedOriginal))return say("Commit or archive the presented draft explicitly before switching modes.");
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
  function openTestimony(){
    if(!ownerReady()||generating||chatSending||editingIdx!==null)return say("Finish active work before making an author statement.");
    const old=$("twoiTestimonyDialog");if(old)old.remove();
    const d=make("dialog",undefined,document.body);d.id="twoiTestimonyDialog";d.setAttribute("aria-label","Author statements and disputes");
    Object.assign(d.style,{width:"min(660px,94vw)",maxHeight:"85dvh",overflow:"auto",padding:"16px",background:"#fffaf0",color:"#29231b",borderRadius:"10px"});
    const source=scope(),basis=JSON.stringify(state.archive);
    make("h2","Author statements and disputes",d);
    make("p","Your statement is testimony, not a replacement for the recorded source. Add a correction or dispute without erasing either record. Private text is not included in the aggregate disclosure.",d);
    const label=make("label","Source record",d),select=make("select",undefined,label);
    const candidates=state.archive.map((r,i)=>({r,i})).filter(x=>x.r.kind!=="author testimony");
    for(const {r,i} of candidates){const o=make("option","Record "+(i+1)+" · "+r.kind+" · "+r.text.slice(0,70),select);o.value=String(i);}
    const quote=make("pre","",d);Object.assign(quote.style,{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:"20dvh",overflow:"auto"});
    const history=make("div",undefined,d);
    const category=make("select",undefined,make("label","Statement type",d));for(const k of C.statementKinds){const o=make("option",k,category);o.value=k;}
    const prior=make("select",undefined,make("label","Earlier statement to supersede (optional)",d));
    const note=make("textarea",undefined,make("label","Your statement",d));note.rows=5;note.maxLength=8000;note.style.width="100%";
    const info=make("p","",d);info.setAttribute("role","status");
    function refresh(){
      const i=Number(select.value),row=state.archive[i];quote.textContent=row?.text??"No source record available.";
      prior.replaceChildren();const none=make("option","No earlier statement",prior);none.value="";
      history.replaceChildren();
      for(let j=0;j<state.archive.length;j++){const claim=C.authorStatement(state.archive,j);if(!claim||claim.targetRecordIndex!==i)continue;
        const p=make("p","Statement "+(j+1)+" · "+claim.category+(claim.supersedes===null?"":" · supersedes "+(claim.supersedes+1))+": "+state.archive[j].text,history);p.style.whiteSpace="pre-wrap";p.style.overflowWrap="anywhere";
        const o=make("option","Statement "+(j+1)+" · "+claim.category,prior);o.value=String(j);
      }
      prior.value="";
    }
    select.onchange=refresh;
    const saveButton=button("Append private statement",d,()=>{
      try{if(source!==scope()||basis!==JSON.stringify(state.archive)||generating||chatSending||editingIdx!==null)throw Error("The document or archive changed; reopen statements.");
        if(!candidates.length)throw Error("There is no source record to annotate.");
        const index=C.appendAuthorStatement(state,{target:Number(select.value),category:category.value,text:note.value,supersedes:prior.value===""?null:Number(prior.value),meta:meta()});
        recordSession("statement",{archiveIndex:index});save();d.close();say("Author statement appended. Existing evidence remains unchanged.");
      }catch(error){info.textContent=error.message;}
    });saveButton.disabled=!candidates.length;
    button("Close",d,()=>d.close());d.addEventListener("close",()=>d.remove(),{once:true});refresh();d.showModal();
  }
  function openContributionReport(){
    if(!ownerReady()||generating||chatSending||editingIdx!==null){say("Finish the active request or inline edit before reviewing contribution records.");return;}
    const old=$("twoiContributionDialog");if(old)old.remove();
    const d=make("dialog",undefined,document.body);d.id="twoiContributionDialog";d.setAttribute("aria-label","Contribution records");
    Object.assign(d.style,{width:"min(640px,94vw)",maxHeight:"85dvh",overflow:"auto",padding:"16px",background:"#fffaf0",color:"#29231b",border:"1px solid #8b7250",borderRadius:"10px"});
    const source=scope(),report=C.contributionReport(state);
    make("h2","Creative contribution records",d);
    make("p","The AI provides testimony. The software provides evidence. Neither delivers the verdict.",d);
    make("p","This is an aggregate of existing document records, not an independent witness or a determination of authorship.",d);
    const counts=make("ul",undefined,d);
    for(const [kind,count] of Object.entries(report.recordCounts))if(count)make("li",count+" · "+kind,counts);
    make("li",report.otherArchiveRecords+" · other archive record(s)",counts);
    make("li",report.currentAdvisoryRecords+" · current advisory record(s)",counts);
    const a=report.approvalObservations;
    make("p","Recorded approvals: "+a.recorded+" · exact match "+a.exactCandidateMatches+" · changed "+a.changedCandidates+" · no linked candidate "+a.unlinkedApprovals+". These describe text correspondence, not who wrote it.",d);
    make("p",report.sessionSummary.starts+" recorded session starts · "+report.sessionSummary.ends+" ends · "+report.sessionSummary.coverageLimits+" coverage limits. Capture is incomplete by design.",d);
    make("p",report.authorStatements.recorded+" author statement(s), including "+report.authorStatements.disputes+" dispute(s). Self-reported; not independently verified.",d);
    make("p",report.hasPresentedModelCandidate?"A model candidate is currently recorded as presented.":"No currently presented model candidate is recorded.",d);
    const limitations=make("ul",undefined,d);for(const line of report.limitations)make("li",line,limitations);
    const ensureCurrent=()=>{if(source!==scope()||generating||chatSending||editingIdx!==null)throw Error("The manuscript or active request changed. Reopen contribution records.");};
    const info=make("p","",d);info.setAttribute("role","status");
    function download(privateText){try{ensureCurrent();if(privateText&&!confirm("Export a PRIVATE copy containing creative drafts, rejected alternatives and advisory text? Keep it separate from any public disclosure."))return;const evidence=C.contributionReport(state,{includePrivateText:privateText});downloadFile(privateText?"2i-private-creative-archive.json":"2i-contribution-summary.json",JSON.stringify(evidence,null,2),"application/json");info.textContent="Download requested. No certification issued; no upload performed.";}catch(error){info.textContent=error.message;}}
    button("Author statements and disputes",d,()=>{ensureCurrent();d.close();openTestimony();});
    button("Export aggregate only",d,()=>download(false));
    button("Export private archive (contains text)",d,()=>download(true));
    button("Close",d,()=>d.close());
    d.addEventListener("close",()=>d.remove(),{once:true});d.showModal();
  }
  const controls=$("mcSection").querySelector(".section-body");
  // These two lines sit in the Manuscript Control panel from the start, so their style must exist from the start.
  // It used to be added only when the Scene intelligence dialog first opened; until then they showed as large
  // unstyled body text and spilled over the panel below. They match the panel's other small labels (.mc-row).
  make("style","#narrativeBudget,#narrativeStatus{margin:0;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:10px;line-height:1.7;color:var(--parchment-soft);overflow-wrap:anywhere}",document.head).id="narrativeControlStyle";
  button("Scene intelligence",controls,openPanel).id="narrativeOpen";
  button("Contribution records",controls,openContributionReport).id="narrativeContribution";
  button("Creative session · off",controls,openSession).id="narrativeSession";
  button("Revision history",controls,()=>{if(typeof showRevisionHistory==="function")showRevisionHistory();else say("Connect Reach to view server revisions.");}).id="narrativeHistory";
  button("Archive draft",controls,archiveDraft).id="narrativeArchiveDraft";
  const budget=make("p","",controls);budget.id="narrativeBudget";
  const status=make("p","",controls);status.id="narrativeStatus";status.setAttribute("role","status");
  draftArea.addEventListener("input",()=>{if(playing)stopAudio();updateBar();});
  document.addEventListener("foresight:work-change",updateBar);
  updateBar();
})();
