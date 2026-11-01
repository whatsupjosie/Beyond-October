/* PubCast simple shoot assembler.
 * Original UI built around broadly familiar NLE concepts: bin, viewer,
 * track sync and selects. No branded Resolve assets or copyrighted UI.
 * Does not render, transform or overwrite source media.
 */
(function(){
"use strict";
const Core=window.PubCastEditorSync, Store=window.PubCastEditorSyncStore, Interchange=window.PubCastEditorInterchange;
const $=id=>document.getElementById(id);
if(!Core||!Store||!$("station-editor"))return;
const ui={
 title:$("ed-project-title"),projects:$("ed-projects"),newProject:$("ed-new-project"),
 save:$("ed-save"),export:$("ed-export"),edlExport:$("ed-edl-export"),
 frameRate:$("ed-frame-rate"),sourceExport:$("ed-original"),
 import:$("ed-import"),cache:$("ed-cache"),
 sidecar:$("ed-sidecar"),bin:$("ed-bin"),video:$("ed-view"),audio:$("ed-audio"),
 playhead:$("ed-playhead"),markIn:$("ed-mark-in"),markOut:$("ed-mark-out"),add:$("ed-add-subclip"),
 io:$("ed-io"),timeline:$("ed-timeline"),status:$("ed-status"),selected:$("ed-selected-track"),
 offset:$("ed-offset"),apply:$("ed-apply-offset"),reset:$("ed-reset-offset"),
 marker:$("ed-marker-number"),markClacker:$("ed-mark-clacker"),health:$("ed-sync-health"),
 menu:$("ed-sync-menu"),advance:$("ed-advance-30"),delay:$("ed-delay-30"),
 resetMenu:$("ed-reset-menu"),closeMenu:$("ed-close-sync"),
 prev:$("ed-prev"),back:$("ed-back"),stop:$("ed-stop"),play:$("ed-play"),
 forward:$("ed-forward"),next:$("ed-next"),split:$("ed-split"),lift:$("ed-lift"),
 ripple:$("ed-ripple"),closeGaps:$("ed-close-gaps"),addGap:$("ed-add-gap"),
 activeClip:$("ed-active-clip")
};
let project=null,currentTrackId=null,activeClipId=null,playheadUs=0,markInUs=null,markOutUs=null,selectionToken=0;
let saveQueue=Promise.resolve(),lastSaved=-1,projectEpoch=0;
const fileByTrack=new Map(),objectURLByTrack=new Map();
const fail=err=>{const msg=String(err?.message||err);ui.status.textContent=msg;ui.status.style.color="#ff8585";console.error("PubCast assembly",err)};
const say=s=>{ui.status.textContent=s;ui.status.style.color="#91dfaf"};
const safe=fn=>Promise.resolve().then(fn).catch(fail);
const ensure=()=>{if(!project)throw Error("Create or open a shoot first");return project};
const selected=()=>{ensure();const t=project.tracks.find(x=>x.id===currentTrackId);if(!t)throw Error("Choose a camera or audio track");return t};
const timeText=us=>{const ms=Math.round(Math.max(0,us)/1000),h=Math.floor(ms/3600000),m=Math.floor(ms%3600000/60000),s=Math.floor(ms%60000/1000);
 return [h,m,s].map(n=>String(n).padStart(2,"0")).join(":")+"."+String(ms%1000).padStart(3,"0")};
const clone=x=>JSON.parse(JSON.stringify(x));
const filenameSafe=s=>String(s).replace(/[^a-zA-Z0-9._-]+/g,"-").slice(0,90)||"pubcast-shoot";
function downloadBlob(blob,name){
 const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;
 document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function chosenFPS(){if(!Interchange)throw Error("Interchange adapter unavailable");return Interchange.validFrameRate(Number(ui.frameRate.value))}
function stopPreview(){
 selectionToken++;for(const media of [ui.video,ui.audio]){media.pause();media.removeAttribute("src");media.load();media.hidden=true;}
}
function releaseURLs(){stopPreview();for(const url of objectURLByTrack.values())URL.revokeObjectURL(url);
 objectURLByTrack.clear();fileByTrack.clear()}
async function save(){
 ensure();Core.validateProject(project);
 const saved=clone(project),epoch=projectEpoch,rev=saved.revision;
 saveQueue=saveQueue.catch(()=>{}).then(async()=>{
   if(epoch!==projectEpoch||rev<lastSaved)return;
   await Store.saveProject(saved);
   if(epoch===projectEpoch){lastSaved=rev;say("Saved project revision "+rev)}
 });
 await saveQueue;
}
function updated(){renderBin();renderSelected();renderTimeline();return save()}
function currentMedia(){const t=selected();return t.kind==="audio"?ui.audio:ui.video}
function shootPosition(){
 const t=selected(),media=currentMedia(),sourceUs=Math.round((Number(media.currentTime)||0)*1000000);
 return Math.max(0,Core.editTimeUs(project,t.id,sourceUs));
}
function updatePlayhead(){
 if(!project||!currentTrackId)return;
 try{playheadUs=shootPosition();ui.playhead.textContent="Shoot time: "+timeText(playheadUs)}
 catch(e){ui.health.textContent=String(e.message)}
}
async function resolveMedia(t){
 if(fileByTrack.has(t.id))return fileByTrack.get(t.id);
 if(t.mediaRef?.startsWith("local:"))return (await Store.readMedia(t.mediaRef.slice(6)))?.blob||null;
 if(t.mediaRef?.startsWith("studio:")){
   if(!window.PubCast25DStore)throw Error("Stage recording store unavailable");
   return (await window.PubCast25DStore.read(t.mediaRef.slice(7)))?.blob||null;
 }
 return null;
}
async function selectTrack(id,preserveShootPosition=false){
 ensure();
 if(!preserveShootPosition&&currentTrackId&&currentTrackId!==id)updatePlayhead();
 const t=project.tracks.find(x=>x.id===id);if(!t)throw Error("Track not found");
 currentTrackId=t.id;stopPreview();const token=selectionToken;
 renderBin();renderSelected();
 const blob=await resolveMedia(t);
 if(token!==selectionToken)return;
 if(!blob){say("Proxy not loaded. Relink "+t.label+" using Import; your edits are safe.");return}
 let url=objectURLByTrack.get(t.id);
 if(!url){url=URL.createObjectURL(blob);objectURLByTrack.set(t.id,url)}
 const media=t.kind==="audio"?ui.audio:ui.video;media.hidden=false;media.src=url;
 const desired=Core.sourceTimeUs(project,t.id,playheadUs);
 media.addEventListener("loadedmetadata",()=>{
   if(token!==selectionToken)return;
   const sec=Math.max(0,desired/1000000);
   try{
     if(Number.isFinite(media.duration)&&media.duration>0&&media.duration<=24*3600){
       const durationUs=Math.round(media.duration*1000000);
       if(t.durationUs!==durationUs){t.durationUs=durationUs;project.revision++;project.updatedAt=new Date().toISOString();save().catch(fail)}
     }
     const quality=t.quality||{role:"unverified",verified:false,bytePreserved:false};
     if(media.videoWidth>0&&media.videoHeight>0&&
       (quality.width!==media.videoWidth||quality.height!==media.videoHeight)){
       t.quality={...quality,width:media.videoWidth,height:media.videoHeight};
       project.revision++;project.updatedAt=new Date().toISOString();save().catch(fail);
     }
     media.currentTime=Number.isFinite(media.duration)&&media.duration>0?
       Math.min(sec,Math.max(0,media.duration-.001)):sec;
   }catch(e){fail(e)}
 },{once:true});
 media.load();say("Viewing "+t.label+" — source is unchanged");
}
function renderBin(){
 ui.bin.replaceChildren();
 if(!project){ui.bin.textContent="No shoot open";return}
 if(!project.tracks.length){ui.bin.textContent="Add camera/audio proxy files, then mark clacker sync points";return}
 for(const t of project.tracks){
   const row=document.createElement("div");row.style.cssText="display:flex;gap:6px;align-items:center;padding:6px;border-bottom:1px solid #8885";
   if(t.id===currentTrackId)row.style.background="rgba(140,150,255,.16)";
   const choose=document.createElement("button");choose.type="button";choose.style.flex="1";choose.textContent=(t.kind==="audio"?"♫ ":"▣ ")+t.label;
   choose.addEventListener("click",()=>safe(()=>selectTrack(t.id)));
   choose.addEventListener("contextmenu",e=>{
   e.preventDefault();ui.menu.hidden=false;
   safe(()=>selectTrack(t.id));
 });
   const offset=document.createElement("span");offset.className="muted small";offset.textContent=(t.manualOffsetUs>=0?"+":"")+Core.formatSeconds(t.manualOffsetUs)+"s";
   const adjust=document.createElement("button");adjust.type="button";adjust.textContent="Sync / Offset";
   adjust.addEventListener("click",()=>{
   ui.menu.hidden=false;safe(async()=>{await selectTrack(t.id);ui.offset.focus()});
 });
   row.append(choose,offset,adjust);ui.bin.append(row);
 }
}
function renderSelected(){
 if(!project||!currentTrackId){ui.selected.textContent="Select a track";ui.offset.value="0.000000";ui.health.textContent="Unanchored";return}
 const t=selected(),a=Core.alignment(project,t);
 ui.selected.textContent=t.label;ui.offset.value=Core.formatSeconds(t.manualOffsetUs);
 ui.health.textContent=a.origin==="clacker"
   ?("Clacker "+a.markers+" marker(s); drift "+a.driftPpm.toFixed(1)+" ppm; residual "+a.residualUs+" µs")
   :a.origin==="wallclock"?"Wall-clock estimate; set clacker markers for precision"
   :"UNANCHORED — mark clacker before trusting sync";
}
function renderTimeline(){
 ui.timeline.replaceChildren();if(!project)return;
 const entries=Core.timelineEntries(project);
 if(!entries.length){ui.timeline.textContent="No selected shots yet";return}
 for(const e of entries){
   const row=document.createElement("div");row.style.cssText="display:flex;gap:6px;padding:6px;align-items:center;border-bottom:1px solid #8885";
   if(activeClipId===e.id)row.style.background="rgba(170,180,255,.17)";
   const track=project.tracks.find(t=>t.id===e.trackId);
   const label=document.createElement("span");label.style.flex="1";
   label.textContent=(e.kind==="gap"?"[BLANK] "+timeText(e.durationUs):(track?.label||e.trackId)+" · "+timeText(e.inUs)+" – "+timeText(e.outUs))
      +"  · assembly "+timeText(e.timelineInUs);
   const choose=document.createElement("button");choose.type="button";choose.textContent="Select";
   choose.addEventListener("click",()=>safe(async()=>{
     activeClipId=e.id;
     if(e.kind!=="gap"){playheadUs=e.inUs;await selectTrack(e.trackId,true)}
     renderTimeline();ui.activeClip.textContent=e.kind==="gap"?"Selected blank":("Selected "+(track?.label||e.trackId));
   }));
   const up=document.createElement("button");up.type="button";up.textContent="↑";up.title="Earlier in rough cut";
   up.addEventListener("click",()=>safe(async()=>{Core.moveSelection(project,e.id,-1);await updated()}));
   const down=document.createElement("button");down.type="button";down.textContent="↓";down.title="Later in rough cut";
   down.addEventListener("click",()=>safe(async()=>{Core.moveSelection(project,e.id,1);await updated()}));
   row.append(label,choose,up,down);ui.timeline.append(row);
 }
}
function renderIO(){ui.io.textContent="In: "+(markInUs==null?"—":timeText(markInUs))+"  Out: "+(markOutUs==null?"—":timeText(markOutUs))}
function activeEntry(){ensure();const item=Core.timelineEntries(project).find(x=>x.id===activeClipId);
 if(!item)throw Error("Select a rough-cut clip first");return item;}
function seekPlayhead(secondsDelta){
 const media=currentMedia();if(!media.currentSrc)throw Error("Load a camera/audio proxy first");
 const sourceTime=Math.max(0,media.currentTime+secondsDelta);
 media.currentTime=Number.isFinite(media.duration)&&media.duration>0?Math.min(media.duration,sourceTime):sourceTime;
 updatePlayhead();
}
function navigateShot(direction){
 const entries=Core.timelineEntries(ensure()).filter(x=>x.kind!=="gap");
 if(!entries.length)throw Error("Rough cut is empty");
 const index=entries.findIndex(x=>x.id===activeClipId),next=entries[Math.max(0,Math.min(entries.length-1,index+direction))];
 if(!next)throw Error("No adjacent shot");
 activeClipId=next.id;playheadUs=next.inUs;
 ui.activeClip.textContent="Selected "+(project.tracks.find(t=>t.id===next.trackId)?.label||next.trackId);
 return selectTrack(next.trackId,true).then(renderTimeline);
}
function splitCurrent(){
 const e=activeEntry();if(e.kind==="gap")throw Error("Choose a shot, not blank space");
 if(e.trackId!==currentTrackId)throw Error("Preview the selected shot before splitting");
 const time=shootPosition();
 const assemblyUs=e.timelineInUs+(time-e.inUs);
 Core.splitAt(project,e.id,assemblyUs);
 activeClipId=e.id;return updated();
}
function deleteCurrent(ripple){
 const e=activeEntry();Core.deleteSelection(project,e.id,ripple);
 activeClipId=null;ui.activeClip.textContent=ripple?"Ripple delete applied":"Lifted shot, retaining blank space";return updated();
}
async function openProject(id){
 if(project&&project.revision!==lastSaved)await save();
 const result=await Store.readProject(id);if(!result)throw Error("Shoot project missing");
 Core.validateProject(result);releaseURLs();project=result;projectEpoch++;lastSaved=result.revision;
 currentTrackId=null;activeClipId=null;markInUs=null;markOutUs=null;playheadUs=0;ui.title.value=result.title;ui.frameRate.value=String(result.frameRate||24);
 renderBin();renderTimeline();renderSelected();renderIO();say("Opened "+result.title+"; relink un-cached files as needed");
}
async function refreshProjects(){
 const projects=await Store.listProjects();ui.projects.replaceChildren();
 const placeholder=document.createElement("option");placeholder.value="";placeholder.textContent="Saved shoots…";ui.projects.append(placeholder);
 for(const item of projects){const option=document.createElement("option");option.value=item.id;option.textContent=item.title+" · "+new Date(item.updatedAt).toLocaleDateString();ui.projects.append(option)}
}
async function createShoot(){
 if(project&&project.revision!==lastSaved)await save();
 releaseURLs();project=Core.createProject(ui.title.value||"Untitled shoot",Date.now(),"edit-"+Date.now()+"-"+Math.random().toString(36).slice(2,8));
 projectEpoch++;lastSaved=-1;currentTrackId=null;activeClipId=null;playheadUs=0;markInUs=null;markOutUs=null;
 project.frameRate=chosenFPS();
 ui.title.value=project.title;renderBin();renderSelected();renderTimeline();renderIO();
 await save();await refreshProjects();
}
async function importFiles(){
 ensure();const files=[...ui.import.files];if(!files.length)return;
 let imported=0;
 for(const file of files){
   if(!file.type.startsWith("video/")&&!file.type.startsWith("audio/"))throw Error(file.name+" is not an audio/video proxy");
   const existing=project.tracks.find(t=>t.label===file.name);
   if(existing){
     fileByTrack.set(existing.id,file);
     if(ui.cache.checked){await Store.saveMedia(existing.id,file,file.name);existing.mediaRef="local:"+existing.id}
     imported++;continue;
   }
   const track=Core.addTrack(project,{id:"track-"+Date.now().toString(36)+"-"+(project.tracks.length+1),
     kind:file.type.startsWith("audio/")?"audio":"camera",label:file.name,
     mediaRef:"temporary:"+file.name,durationUs:null});
   fileByTrack.set(track.id,file);
   if(ui.cache.checked){await Store.saveMedia(track.id,file,file.name);track.mediaRef="local:"+track.id}
   imported++;
 }
 ui.import.value="";await updated();say(imported+" proxy file(s) imported/relinked; set clacker markers to establish sync");
 if(!currentTrackId&&project.tracks.length)await selectTrack(project.tracks[0].id);
}
async function importSidecar(){
 ensure();const f=ui.sidecar.files[0];if(!f)return;
 const data=JSON.parse(await f.text());
 if(data.schema!=="pubcast.clacker"||data.version!==1||!Array.isArray(data.markers)||data.markers.length>50000)
   throw Error("Unsupported clacker sidecar format");
 const staged=clone(project);
 for(const marker of data.markers){
   if(!marker||typeof marker.trackId!=="string"||!Number.isSafeInteger(marker.sequence)||!Number.isSafeInteger(marker.sourceUs))
     throw Error("Invalid clacker marker");
   Core.addClackerMark(staged,marker.trackId,marker.sequence,marker.sourceUs);
 }
 Core.validateProject(staged);project=staged;ui.sidecar.value="";await updated();say(data.markers.length+" clacker markers imported and saved");
}
function applyOffset(seconds){const t=selected();Core.setOffsetSeconds(project,t.id,seconds);return updated()}
async function noteClacker(){
 const t=selected(),sequence=Number(ui.marker.value);
 if(!Number.isSafeInteger(sequence)||sequence<0)throw Error("Invalid 15-second clacker number");
 const media=currentMedia();
 if(!media.currentSrc||media.readyState<1||!Number.isFinite(media.currentTime))
   throw Error("Open and seek an actual proxy before setting a clacker anchor");
 const sourceUs=Math.round(media.currentTime*1000000),staged=clone(project);
 Core.addClackerMark(staged,t.id,sequence,sourceUs);
 Core.alignment(staged,staged.tracks.find(x=>x.id===t.id)); // Validate drift before changing project.
 project=staged;await updated();say("Clacker #"+sequence+" marked at "+timeText(sourceUs));
}
function exportPlan(){
 ensure();if(!Interchange)throw Error("Professional interchange adapter unavailable");
 const frameRate=chosenFPS(),audit=Interchange.audit(project,Core);
 const obj={...Interchange.packageManifest(project,Core,{frameRate}),project:clone(project)};
 downloadBlob(new Blob([JSON.stringify(obj,null,2)],{type:"application/json"}),
   filenameSafe(project.title)+".pubcast-handoff.json");
 say("Handoff saved. "+audit.problems.length+" source problems, "+audit.warnings.length+
   " checks pending. Transfer originals separately; no media is embedded in this manifest.");
}
function exportEDL(){
 ensure();if(!Interchange)throw Error("CMX3600 interchange adapter unavailable");
 const edl=Interchange.toEDL(project,Core,chosenFPS());
 downloadBlob(new Blob([edl.edl],{type:"text/plain;charset=utf-8"}),
   filenameSafe(project.title)+".edl");
 say("Simple CMX3600 cuts EDL at "+edl.rate+" fps saved. "+
   "Keep the JSON handoff for microsecond clacker offsets, drift and audio.");
}
async function exportSource(){
 const t=selected(),blob=await resolveMedia(t);
 if(!blob||!blob.size)throw Error("The selected media isn't available here. Relink the source first.");
 const name=String(t.label).replace(/[\\/:*?"<>|]/g,"_").slice(0,180)||"original-media";
 downloadBlob(blob,name);
 say("Saved "+name+" as stored bytes—no transcode or upscale. Source quality is not certified.");
}
function changePlayhead(us){playheadUs=Math.max(0,us);if(currentTrackId)selectTrack(currentTrackId,true).catch(fail);ui.playhead.textContent="Shoot time: "+timeText(playheadUs)}
ui.newProject.addEventListener("click",()=>safe(createShoot));
ui.save.addEventListener("click",()=>safe(async()=>{await save();await refreshProjects()}));
ui.projects.addEventListener("change",()=>{if(ui.projects.value)safe(()=>openProject(ui.projects.value))});
ui.import.addEventListener("change",()=>safe(importFiles));
ui.sidecar.addEventListener("change",()=>safe(importSidecar));
ui.apply.addEventListener("click",()=>safe(()=>applyOffset(ui.offset.value)));
ui.reset.addEventListener("click",()=>safe(()=>applyOffset("0")));
ui.advance.addEventListener("click",()=>safe(()=>{const t=selected();Core.adjustOffsetSeconds(project,t.id,"0.030");return updated()}));
ui.delay.addEventListener("click",()=>safe(()=>{const t=selected();Core.adjustOffsetSeconds(project,t.id,"-0.030");return updated()}));
ui.resetMenu.addEventListener("click",()=>safe(()=>applyOffset("0")));
ui.closeMenu.addEventListener("click",()=>{ui.menu.hidden=true});
ui.markClacker.addEventListener("click",()=>safe(noteClacker));
ui.markIn.addEventListener("click",()=>safe(()=>{markInUs=shootPosition();renderIO()}));
ui.markOut.addEventListener("click",()=>safe(()=>{markOutUs=shootPosition();renderIO()}));
ui.add.addEventListener("click",()=>safe(async()=>{
 const t=selected();if(markInUs==null||markOutUs==null)throw Error("Mark an In and Out first");
 Core.addSelection(project,{id:"select-"+(project.selections.length+1)+"-"+Date.now(),trackId:t.id,inUs:markInUs,outUs:markOutUs});
 await updated();say("Selected coverage added — original take untouched");
}));
ui.export.addEventListener("click",()=>safe(exportPlan));
ui.edlExport.addEventListener("click",()=>safe(exportEDL));
ui.sourceExport.addEventListener("click",()=>safe(exportSource));
ui.frameRate.addEventListener("change",()=>safe(async()=>{
 ensure();project.frameRate=chosenFPS();project.revision++;project.updatedAt=new Date().toISOString();
 await save();
}));
ui.play.addEventListener("click",()=>safe(async()=>{
 const media=currentMedia();if(!media.currentSrc)throw Error("No proxy to play");
 if(media.paused){await media.play();ui.play.textContent="⏸"}else{media.pause();ui.play.textContent="▶"}
}));
ui.stop.addEventListener("click",()=>safe(()=>{const media=currentMedia();media.pause();
 const shot=project?.selections.find(e=>e.id===activeClipId);
 if(shot&&shot.kind!=="gap"&&shot.trackId===currentTrackId){
   const us=Core.sourceTimeUs(project,shot.trackId,shot.inUs);
   media.currentTime=Math.max(0,us/1000000);
 }
 ui.play.textContent="▶";
}));
ui.back.addEventListener("click",()=>safe(()=>seekPlayhead(-1/chosenFPS())));
ui.forward.addEventListener("click",()=>safe(()=>seekPlayhead(1/chosenFPS())));
ui.prev.addEventListener("click",()=>safe(()=>navigateShot(-1)));
ui.next.addEventListener("click",()=>safe(()=>navigateShot(1)));
ui.split.addEventListener("click",()=>safe(splitCurrent));
ui.lift.addEventListener("click",()=>safe(()=>deleteCurrent(false)));
ui.ripple.addEventListener("click",()=>safe(()=>deleteCurrent(true)));
ui.closeGaps.addEventListener("click",()=>safe(async()=>{const count=Core.closeGaps(ensure());
 await updated();say(count+" blank spaces removed; sources unchanged")}));
ui.addGap.addEventListener("click",()=>safe(async()=>{Core.gap(ensure(),1000000);
 await updated();say("One-second blank inserted in rough cut")}));
for(const media of [ui.video,ui.audio])media.addEventListener("pause",()=>ui.play.textContent="▶");
for(const media of [ui.video,ui.audio]){
 media.addEventListener("timeupdate",updatePlayhead);
 media.addEventListener("seeked",updatePlayhead);
}
document.addEventListener("keydown",e=>{
 if(!$("station-editor")||$("station-editor").classList.contains("hidden"))return;
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 if(["INPUT","TEXTAREA","SELECT"].includes(e.target?.tagName)||e.target?.isContentEditable)return;
 if(e.key.toLowerCase()==="i"){e.preventDefault();ui.markIn.click()}
 if(e.key.toLowerCase()==="o"){e.preventDefault();ui.markOut.click()}
 if(e.code==="Space"||e.key.toLowerCase()==="l"){e.preventDefault();ui.play.click()}
 if(e.key.toLowerCase()==="k"){e.preventDefault();ui.stop.click()}
 if(e.code==="ArrowLeft"){e.preventDefault();ui.back.click()}
 if(e.code==="ArrowRight"){e.preventDefault();ui.forward.click()}
});
window.addEventListener("pagehide",releaseURLs);
refreshProjects().then(()=>{renderBin();renderTimeline()}).catch(fail);
window.PubCastShootAssembly={openProject,refreshProjects,exportPlan};
})();
