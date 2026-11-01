/* PubCast 2.5D integrated local production desk.
 * Genuine 2.5D layer composition, independent camera viewports, real canvas MediaRecorder,
 * optional mic capture, transactional local session persistence, no forged backend/Blackbox status.
 */
(function(){
"use strict";
const Core=window.PubCast25D, Render=window.PubCast25DRenderer, Store=window.PubCast25DStore;
if(!Core||!Render||!Store){document.body.textContent="Studio dependencies could not load";return;}
const $=id=>document.getElementById(id);
const el={genre:$("genre"),description:$("description"),state:$("state"),alert:$("alert"),events:$("events"),
program:$("program"),preview:$("preview"),programShot:$("programShot"),previewShot:$("previewShot"),
camera:$("cameras"),performer:$("performer"),recBadge:$("recBadge"),audioBadge:$("audioBadge"),
record:$("record"),recordStop:$("recordStop"),start:$("start"),stop:$("stop"),mic:$("mic"),
micLevel:$("micLevel"),micMute:$("micMute"),micMeter:$("micMeter"),timecode:$("timecode"),
playback:$("playback"),sessionList:$("sessionList"),manifest:$("manifest"),download:$("download"),
assetInfo:$("assetInfo"),avatarStatus:$("avatarStatus"),switcherLink:$("switcherLink"),liveMedia:$("liveMedia")};
const world=document.createElement("canvas");world.width=Core.W;world.height=Core.H;
const lastFrame=document.createElement("canvas");lastFrame.width=Core.W;lastFrame.height=Core.H;
const state={pkg:null,performers:[],assets:{},avatarBridge:null,avatarError:"",
programId:null,previewId:null,
session:null,media:null,mediaError:null,recorder:null,videoStream:null,micStream:null,audioContext:null,micSource:null,
micGain:null,micAnalyser:null,audioDest:null,recordingPromise:null,recordingComplete:null,recordedChunks:[],
recordingStartedAt:0,recordingId:null,recovery:null,
recordingMime:"",microphoneMuted:false,microphoneLevel:1,selected:null,playbackUrl:null,downloadUrl:null,
lastTick:0,blackout:false,panicActive:false,lowerThird:false,lowerText:"BELLA FAUX PAS",scores:[0,0],transition:null,
storageReady:false,assetUrls:{},assetByPackage:{},avatarChecks:0,
sharedSwitcher:null,remoteProgram:null,remotePreview:null,programMixSource:null,mediaPublisher:null,
avatarGeneration:0,avatarLoadingGeneration:-1,loadedActorIds:new Set(),
previewBars:false,lastPanicSeq:0,lastBlackoutSeq:0,lastBarsSeq:0,cuePollBusy:false};
const pr=el.program.getContext("2d"), pv=el.preview.getContext("2d"), prior=lastFrame.getContext("2d");
function status(message,error){
 el.state.textContent=message;el.state.classList.toggle("error",!!error);
}
function error(message){
 el.alert.textContent=message;status("ATTENTION",true);log("ERROR "+message);
}
function log(message){
 const time=new Date().toLocaleTimeString([], {hour12:false});
 const line=document.createElement("div");line.textContent=time+"  "+message;
 el.events.appendChild(line);el.events.scrollTop=el.events.scrollHeight;
 while(el.events.childNodes.length>85)el.events.removeChild(el.events.firstChild);
}
function emit(type,payload){
 if(!state.session)return;
 const e=Core.event(state.session,type,payload||{},Date.now());
 return e;
}
async function safe(fn){
 try{await fn()}catch(e){error(String(e?.message||e));console.error("PubCast 2.5D",e);}
}
function setControls(){
 const active=!!state.session,rec=!!state.recorder,stopping=!!state.recordingPromise;
 el.start.disabled=active;el.genre.disabled=active;el.stop.disabled=!active||stopping;
 el.record.disabled=!active||rec||stopping||!state.storageReady;
 el.recordStop.disabled=!rec||stopping;
 el.record.disabled=el.record.disabled||!!state.recovery;
 $("recoveryPanel").hidden=!state.recovery;
 el.recBadge.textContent=rec?"● REC "+state.recordingMime:"REC OFF";
 el.recBadge.style.color=rec?"#ff7070":"";
 el.audioBadge.textContent=state.micStream?"MIC "+(state.microphoneMuted?"MUTED":"ACTIVE"):"MIC OFF";
 el.micMute.disabled=!state.micStream;
 el.micLevel.disabled=!state.micStream;
 if(active&&state.panicActive)status("PANIC: BLACKOUT",true);
 else if(!active&&el.state.textContent!=="ATTENTION")status("STANDBY");
 else if(active&&el.state.textContent!=="ATTENTION")status(state.blackout?"BLACKOUT":rec?"RECORDING":"ON AIR");
}
function buildCameras(){
 el.camera.replaceChildren();
 for(const shot of state.pkg.cameras){
  const btn=document.createElement("button");
  btn.type="button";btn.textContent=shot.label;btn.dataset.shot=shot.id;
  btn.addEventListener("click",()=>safe(()=>choosePreview(shot.id)));
  el.camera.appendChild(btn);
 }
 refreshCameraUI();
}
function refreshCameraUI(){
 if(!state.pkg)return;
 for(const btn of el.camera.children){
  const s=btn.dataset.shot;
  btn.classList.toggle("selected",s===state.previewId);
  btn.textContent=state.pkg.cameras.find(x=>x.id===s).label+
    (s===state.programId?" [PGM]":"")+(s===state.previewId?" [PVW]":"");
 }
 const camera=id=>state.pkg.cameras.find(x=>x.id===id);
 el.programShot.textContent="PGM: "+(camera(state.programId)?.label||"—");
 el.previewShot.textContent="PVW: "+(camera(state.previewId)?.label||"—");
}
function loadGenre(id){
 if(state.session)throw Error("Finish the current production before changing the set");
 const pkg=Core.PACKAGES[id];if(!pkg)throw Error("Unknown package "+id);
 Core.validate(pkg);
 // All GLB actor instances belong to ONE current production package.
 // Clear before replacing; unique IDs prevent an old async loader from
 // overwriting a new package's actor with the same performer number.
 state.avatarGeneration++;
 if(state.avatarBridge?.clear)for(const id of state.loadedActorIds)state.avatarBridge.clear(id);
 state.loadedActorIds.clear();
 state.pkg=pkg;
 state.performers=pkg.performers.map(p=>({id:"p25d-"+pkg.id+"-"+p.id,slot:p.slot,position:p.position.slice(),
 avatar:p.avatar,moving:false,vx:0,vy:0,motionUntil:0}));
 state.programId=pkg.cameras[0].id;state.previewId=pkg.cameras[1].id;
 state.assets=state.assetByPackage[id]||(state.assetByPackage[id]={});
 state.blackout=false;state.panicActive=false;state.lowerThird=false;state.lowerText=pkg.graphics;
 state.scores=[0,0];state.transition=null;
 el.description.textContent=pkg.title+" · "+pkg.subtitle+" — "+pkg.cameras.length+" preset shots";
 el.genre.value=id;el.performer.replaceChildren();
 for(const p of state.performers){
  const o=document.createElement("option");o.value=p.id;o.textContent=p.slot+" ("+p.id+")";el.performer.appendChild(o);
 }
 buildCameras();setControls();log("SET "+pkg.title+" / "+pkg.cameras.length+" camera configurations");
 loadActors();
}
async function choosePreview(id){
 Core.shot(state.pkg,id);
 if(state.sharedSwitcher?.connected()){
   await state.sharedSwitcher.choosePreview(id);
 } else {
   state.previewId=id;refreshCameraUI();
 }
 emit("camera.preview",{id,shared:!!state.sharedSwitcher?.connected()});log("PREVIEW "+id);
}
function makeTransition(duration=600,elapsedMs=0){
 prior.clearRect(0,0,Core.W,Core.H);
 prior.drawImage(el.program,0,0,Core.W,Core.H);
 state.transition={started:performance.now()-Math.max(0,elapsedMs),duration};
}
async function cut(dissolve){
 if(!state.pkg||!state.session)throw Error("Start production before switching Program");
 const old=state.programId, wanted=state.previewId;
 if(state.sharedSwitcher?.connected()){
   // The same canonical switcher operates the studio; never take locally on HTTP failure.
   if(dissolve)makeTransition();
   try { await state.sharedSwitcher.take(!!dissolve); }
   catch(e) {state.transition=null;throw e;}
 } else {
   if(dissolve)makeTransition();else state.transition=null;
   state.programId=wanted;state.previewId=old;
   refreshCameraUI();
 }
 emit(dissolve?"camera.dissolve":"camera.cut",{from:old,to:state.programId,durationMs:dissolve?600:0,shared:!!state.sharedSwitcher?.connected()});
 log((dissolve?"DISSOLVE ":"CUT ")+old+" → "+state.programId);
}
function sharedSwitcherState(next) {
 if(!state.session)return;
 const previous=state.programId;
 const transition=next.transition||{};
 if(next.program&&next.program!==previous&&transition.type==="dissolve"){
   const elapsed=Number.isFinite(Number(transition.started_at))
     ? Date.now()-Number(transition.started_at)*1000 : Number.POSITIVE_INFINITY;
   const duration=Math.min(4000,Math.max(0,Number(transition.duration_ms)||0));
   if(duration&&elapsed>=-100&&elapsed<duration){
     // A second director can trigger a real remote dissolve. Respect the
     // server timestamp so late polling does not replay a finished transition.
     makeTransition(duration,elapsed);
   }
 }
 state.remoteProgram=next.remoteProgram;
 state.remotePreview=next.remotePreview;
 if(next.program)state.programId=next.program;
 if(next.preview)state.previewId=next.preview;
 refreshCameraUI();
 if(next.remoteProgram) {
   log("SHARED PROGRAM SOURCE OUTSIDE 2.5D PACKAGE: "+next.remoteProgram);
 } else {
   emit("camera.shared_state",{program:state.programId,preview:state.previewId,transition:next.transition});
 }
}
function sharedSwitcherWarning(reason) {
 if(!state.session)return;
 el.switcherLink.textContent="VIDEO SYNC LOST";
 el.switcherLink.style.color="#ff8b8b";
 error(reason);
}
function cue(type,payload){
 emit("cue."+type,payload||{});log("CUE "+type+(payload?.performer?" "+payload.performer:""));
}
function drawPreviewBars(c){
 const colors=["#ddd","#f0db34","#16dade","#31da4e","#d146e3","#e24f42","#225bec","#161616"];
 for(let i=0;i<colors.length;i++){c.fillStyle=colors[i];c.fillRect(i*Core.W/colors.length,0,Core.W/colors.length,Core.H*.72);}
 c.fillStyle="#121212";c.fillRect(0,Core.H*.72,Core.W,Core.H*.28);
 c.fillStyle="#ffffff";c.font="bold 26px system-ui";c.textAlign="center";
 c.fillText("PUBCAST PREVIEW TEST PATTERN — NOT A CAMERA",Core.W/2,Core.H*.84);
}
async function syncServerVideoCues(){
 if(!state.session||state.cuePollBusy)return;
 state.cuePollBusy=true;
 try{
   const response=await fetch("/api/state/production",{cache:"no-store"});
   if(!response.ok)return;
   const remote=await response.json();
   if(!remote||typeof remote!=="object")return;
   const panicSeq=Number(remote.panic_seq)||0;
   if(panicSeq>state.lastPanicSeq&&panicSeq>Date.parse(state.session.startedAt)/1000){
     state.lastPanicSeq=panicSeq;state.blackout=true;state.panicActive=true;
     cue("remote_panic",{panicSeq});
     status("PANIC: BLACKOUT");
     if(state.recorder)await stopRecording();
   }
   const blackSeq=Number(remote.blackout_seq)||0;
   if(blackSeq&&blackSeq!==state.lastBlackoutSeq){
     state.lastBlackoutSeq=blackSeq;
     if(blackSeq>state.lastPanicSeq){
       state.blackout=remote.blackout===true;
       if(!state.blackout)state.panicActive=false;
       cue("remote_blackout",{enabled:state.blackout});
     }
   }
   const barsSeq=Number(remote.preview_bars_seq)||0;
   if(barsSeq&&barsSeq!==state.lastBarsSeq){
     state.lastBarsSeq=barsSeq;state.previewBars=remote.preview_bars===true;
     cue("preview_bars",{enabled:state.previewBars});
   }
   setControls();
 }catch(e){if(state.sharedSwitcher?.connected())log("VIDEO CUE POLL ERROR "+e.message);}
 finally{state.cuePollBusy=false;}
}
function move(delta){
 const p=state.performers.find(p=>p.id===el.performer.value);if(!p)return;
 const old=p.position[0];p.position[0]=Math.min(.9,Math.max(.1,Math.round((old+delta)*100)/100));
 p.vx=delta;p.vy=0;p.moving=true;p.motionUntil=performance.now()+450;
 cue("blocking",{performer:p.id,from:old,to:p.position[0],y:p.position[1]});
}
function animate(){
 const p=state.performers.find(p=>p.id===el.performer.value);
 if(!p)return;
 const patterns="wave|gesture|talk|cheer|nod|react|point|look|greet";
 if(!state.avatarBridge?.playClip?.(p.id,patterns))return error("No matching real gesture animation in "+p.id+"'s loaded GLB");
 cue("animation",{performer:p.id,clipPattern:patterns});
}
function reset(){
 for(let i=0;i<state.performers.length;i++){
  const p=state.performers[i];p.position=state.pkg.performers[i].position.slice();
  p.moving=false;p.vx=0;p.vy=0;
 }
 cue("blocking.reset",{});log("Stage blocking reset");
}
async function startProduction(){
 if(state.session)throw Error("A production is already running");
 const sess=Core.makeSession(state.pkg,Date.now());state.session=sess;
 emit("production.start",{package:state.pkg.id,program:state.programId});
 try{if(state.storageReady)await Store.save(sess)}catch(e){state.session=null;throw Error("Cannot persist session start: "+e.message);}
 log("PRODUCTION START "+sess.id);setControls();
 state.remoteProgram=null;state.remotePreview=null;
 const Shared=window.PubCast25DSharedSwitcher;
 if(Shared){
   const bridge=Shared.create({onState:sharedSwitcherState,onError:sharedSwitcherWarning});
   const result=await bridge.attach(state.pkg);
   state.sharedSwitcher=bridge;
   el.switcherLink.textContent=result.shared?"VIDEO: SHARED SWITCHER":"VIDEO: LOCAL ONLY";
   el.switcherLink.style.color=result.shared?"#79e9b0":"#efd18b";
   log(result.shared?"SHARED SWITCHER ATTACHED: "+result.sourceCount+" stage cameras":"LOCAL VIDEO MODE: "+result.reason);
   if(result.shared&&window.PubCast25DFramePublisher){
     state.mediaPublisher=window.PubCast25DFramePublisher.create({
       session:sess.id,sourceId:id=>Shared.sourceId(state.pkg.id,id),
       onState:feed=>{
         el.liveMedia.textContent=feed.live?"REMOTE FRAMES: CONFIRMED ("+feed.frames+")":"REMOTE FRAMES: OFF";
         el.liveMedia.style.color=feed.live?"#79e9b0":"";
       },
       onError:(reason,count)=>{
         if(count===1||count===3||count%10===0){
           el.liveMedia.textContent="REMOTE FRAMES: ERROR";
           el.liveMedia.style.color="#ff8b8b";log(reason);
         }
       }
     });
   }
 }else{
   el.switcherLink.textContent="VIDEO: LOCAL ONLY";
   log("Shared switcher adapter unavailable; local-only production");
 }
}
async function stopProduction(){
 if(!state.session)return;
 if(state.recorder)await stopRecording();
 if(state.recovery)throw Error("Save the unsaved take before ending this production. A recovery copy can also be downloaded below.");
 const sess=state.session;
 emit("production.stop",{});
 Core.finish(sess,Date.now());
 if(state.storageReady)await Store.save(sess);
 if(state.mediaPublisher){
   try{await state.mediaPublisher.stop()}catch(e){log("LIVE MEDIA RELEASE WARNING "+e.message)}
   state.mediaPublisher=null;
 }
 state.sharedSwitcher?.detach();state.sharedSwitcher=null;
 state.remoteProgram=null;state.remotePreview=null;
 el.switcherLink.textContent="VIDEO: LOCAL ONLY";
 el.liveMedia.textContent="REMOTE FRAMES: OFF";el.liveMedia.style.color="";
 state.session=null;log("PRODUCTION END "+sess.id);setControls();await refreshSessions();
}
function recordedMime(){
 if(typeof MediaRecorder==="undefined")throw Error("MediaRecorder is unavailable in this browser");
 const types=["video/webm;codecs=vp9,opus","video/webm;codecs=vp8,opus","video/webm;codecs=vp9","video/webm;codecs=vp8","video/webm","video/mp4"];
 return types.find(x=>MediaRecorder.isTypeSupported?.(x))||"";
}
function cleanupMedia(){
 for(const track of state.videoStream?.getTracks()||[])track.stop();
 for(const track of state.micStream?.getTracks()||[])track.stop();
 try{state.micSource?.disconnect()}catch(_){}
 try{state.micGain?.disconnect()}catch(_){}
 try{state.programMixSource?.disconnect()}catch(_){}
 if(state.audioContext&&state.audioContext.state!=="closed")state.audioContext.close().catch(console.warn);
 state.videoStream=null;state.micStream=null;state.audioContext=null;
 state.micSource=null;state.micGain=null;state.micAnalyser=null;state.audioDest=null;state.programMixSource=null;
}
async function startRecording(){
 if(!state.session)throw Error("Start a production before recording");
 if(state.recorder||state.recordingPromise)throw Error("Already recording");
 if(state.recovery)throw Error("Save or download the unsaved take before recording again");
 if(!state.storageReady)throw Error("Local persistent session storage is unavailable");
 if(typeof el.program.captureStream!=="function")throw Error("Canvas.captureStream is unsupported");
 const mime=recordedMime();
 state.recordedChunks=[];state.mediaError=null;
 try{
   // Captures exactly the program canvas presented to the operator.
   state.videoStream=el.program.captureStream(30);
   if(!state.videoStream.getVideoTracks().length)throw Error("No video track from program canvas");
   const combined=new MediaStream([...state.videoStream.getVideoTracks()]);
   const programAudio=window.PubcastProgramAudio;
   // A single recording track combines the established program mixer and an
   // optional microphone. Never create a competing dialogue/music/SFX bus graph.
   if(programAudio?.captureOutputStream || el.mic.checked){
     const AC=window.AudioContext||window.webkitAudioContext;
     if(!AC)throw Error("Web Audio mix-to-record unavailable");
     state.audioContext=new AC();await state.audioContext.resume();
     state.audioDest=state.audioContext.createMediaStreamDestination();
     if(programAudio?.captureOutputStream){
       const liveMix=programAudio.captureOutputStream();
       await programAudio.context?.resume?.();
       if(!liveMix.getAudioTracks().length)throw Error("Shared program mixer has no capture track");
       state.programMixSource=state.audioContext.createMediaStreamSource(liveMix);
       state.programMixSource.connect(state.audioDest);
     }
     if(el.mic.checked){
       if(!navigator.mediaDevices?.getUserMedia)throw Error("Microphone capture unavailable; deselect mic to record without microphone");
       state.micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
       state.micSource=state.audioContext.createMediaStreamSource(state.micStream);
       state.micGain=state.audioContext.createGain();state.micGain.gain.value=state.microphoneMuted?0:state.microphoneLevel;
       state.micAnalyser=state.audioContext.createAnalyser();state.micAnalyser.fftSize=256;
       state.micSource.connect(state.micGain);state.micGain.connect(state.micAnalyser);
       state.micAnalyser.connect(state.audioDest); // recording, never local speaker loopback
     }
     for(const track of state.audioDest.stream.getAudioTracks())combined.addTrack(track);
   }
   const rec=new MediaRecorder(combined,mime?{mimeType:mime,videoBitsPerSecond:3000000}:{videoBitsPerSecond:3000000});
   state.recordingMime=rec.mimeType||mime||"browser default";
   rec.ondataavailable=e=>{if(e.data?.size)state.recordedChunks.push(e.data)};
   rec.onerror=e=>{state.mediaError=e.error||Error("MediaRecorder error")};
   state.recordingStartedAt=Date.now();
   state.recordingId=state.session.id+"-take-"+state.recordingStartedAt;
   rec.start(1000);state.recorder=rec;
   emit("recording.start",{mime:state.recordingMime,microphone:!!state.micStream,
     sharedProgramMix:!!state.programMixSource,canvas:[Core.W,Core.H]});
   log("REC START "+state.recordingMime+" / microphone "+(state.micStream?"ON":"OFF"));setControls();
 }catch(e){cleanupMedia();state.recorder=null;setControls();throw e;}
}
async function stopRecording(){
 if(!state.recorder)return;
 if(state.recordingPromise)return state.recordingPromise;
 const rec=state.recorder;
 state.recordingPromise=new Promise((resolve,reject)=>{
   rec.onstop=async ()=>{
     try{
       const captureError=state.mediaError;
       const blob=new Blob(state.recordedChunks,{type:rec.mimeType||"video/webm"});
       if(blob.size===0)throw Error("Recorder generated no video data");
       emit("recording.stop",{bytes:blob.size,mime:blob.type});
       const sess=state.session;
       if(!sess)throw Error("Session disappeared before recording completed");
       // Preserve every take independently; a second Record must never replace
       // the first take's bytes, including sessions from the old single-take store.
       if(!sess.recordings)sess.recordings=sess.media?[Object.assign({id:sess.id},sess.media)]:[];
       sess.media={id:state.recordingId,mime:blob.type,bytes:blob.size,
         startedAt:new Date(state.recordingStartedAt).toISOString(),
         offsetMs:state.recordingStartedAt-Date.parse(sess.startedAt),
         durationMs:Date.now()-state.recordingStartedAt,incomplete:!!captureError};
       sess.recordings.push(sess.media);
       state.recovery={session:sess,blob,take:sess.media};
       await Store.save(sess,blob);
       state.recovery=null;
       log((captureError?"PARTIAL TAKE SAVED ":"REC SAVED ")+blob.size+" bytes; "+sess.events.length+" session events");
       await refreshSessions();
       if(captureError)throw Error("Recording interrupted; available partial media was saved: "+captureError.message);
       resolve(blob);
     }catch(e){state.mediaError=e;log("REC FAILED "+e.message+(state.recovery?"; unsaved media remains available for recovery":""));reject(e)}
     finally{
       cleanupMedia();state.recordedChunks=[];state.recorder=null;state.recordingPromise=null;setControls();
     }
   };
   try{if(rec.state==="inactive")rec.onstop();else rec.stop();}catch(e){state.recordingPromise=null;cleanupMedia();state.recorder=null;reject(e);}
 });
 return state.recordingPromise;
}
async function refreshSessions(){
 if(!state.storageReady)return;
 const sessions=await Store.list();el.sessionList.replaceChildren();
 if(!sessions.length){el.sessionList.textContent="No saved sessions yet.";return;}
 for(const session of sessions){
  const takes=session.recordings?.length?session.recordings:[session.media||null];
  for(const [index,take] of takes.entries()){
   const btn=document.createElement("button");
   btn.textContent=(session.endedAt?"✓ ":"● ")+session.packageId+" · "+session.startedAt.slice(0,19).replace("T"," ")+" · "+(take?.incomplete?"INCOMPLETE ":"")+"Take "+(index+1)+" · "+(take?.bytes||0)+" bytes";
   btn.addEventListener("click",()=>safe(()=>selectSession(session.id,take?.id)));
   el.sessionList.appendChild(btn);
  }
 }
}
async function selectSession(id,takeId){
 const item=await Store.read(id,takeId);if(!item.session)throw Error("Session not found");
 item.takeId=takeId||item.session.media?.id||id;
 if(state.playbackUrl){URL.revokeObjectURL(state.playbackUrl);state.playbackUrl=null;}
 state.selected=item;
 if(item.blob){state.playbackUrl=URL.createObjectURL(item.blob);el.playback.src=state.playbackUrl;}
 else {el.playback.removeAttribute("src");el.playback.load();}
 el.download.disabled=!item.blob;el.manifest.disabled=false;
 log("SESSION OPEN "+id+" / "+item.session.events.length+" events "+(item.blob?"MEDIA":"NO MEDIA"));
}
function downloadBlob(blob,name){
 const url=URL.createObjectURL(blob);const a=document.createElement("a");
 a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),15000);
}
function chooseImage(input,key){
 const file=input.files?.[0];if(!file)return;
 if(file.size>24*1024*1024)throw Error("Asset too large; supply an image smaller than 24 MB");
 if(!file.type.startsWith("image/"))throw Error("Only image assets are supported");
 const url=URL.createObjectURL(file),image=new Image();
 image.onload=()=>{const prev=state.assetUrls[state.pkg.id+key];if(prev)URL.revokeObjectURL(prev);
  state.assetUrls[state.pkg.id+key]=url;state.assets[key]=image;
  el.assetInfo.textContent=state.pkg.title+" · "+key+" replaced with "+file.name+" ("+image.naturalWidth+"×"+image.naturalHeight+")";
  emit("set.asset",{layer:key,name:file.name,width:image.naturalWidth,height:image.naturalHeight});
  log("ART "+key+" "+file.name);
 };
 image.onerror=()=>{URL.revokeObjectURL(url);error("Could not decode image "+file.name)};
 image.src=url;
}
async function loadActors(){
 if(!state.pkg)return;
 const bridge=window.PubCastGLB;
 if(!bridge){el.avatarStatus.textContent="3D GLB engine unavailable; stage rendering continues without substitute actors.";return;}
 state.avatarBridge=bridge;state.avatarError="";
 const generation=state.avatarGeneration;
 if(state.avatarLoadingGeneration===generation)return; // avoid double simultaneous loads
 state.avatarLoadingGeneration=generation;
 const previous=state.avatarLoadTask;
 const work=async()=>{
 if(previous)await previous.catch(()=>{});
 if(generation!==state.avatarGeneration)return;
 const failures=[],loaded=[];
 for(const p of state.performers.slice()){
  if(generation!==state.avatarGeneration)break;
  if(bridge.has(p.id)){loaded.push(p.id);state.loadedActorIds.add(p.id);continue;}
  try{
    const file=p.avatar==="female"?"MakeHuman_Female.glb":"MakeHuman_Male.glb";
    const info=await bridge.load(p.id,"./world/test_avatars/"+file,p.slot);
    if(generation!==state.avatarGeneration){bridge.clear(p.id);break;}
    state.loadedActorIds.add(p.id);
    loaded.push(p.id+" ("+info.clips.length+" animations)");
  }catch(e){if(generation===state.avatarGeneration)failures.push(p.id+": "+e.message);}
 }
 if(generation!==state.avatarGeneration)return;
 el.avatarStatus.textContent="3D GLB actors: "+loaded.join(", ")+(failures.length?" | LOAD FAILED: "+failures.join("; "):"");
 if(failures.length)log("3D ASSET FAILURE "+failures.join("; "));
 else log("3D ACTORS loaded "+loaded.length);
 };
 // Stable performer IDs can be reused when the same genre is reloaded.
 // Finish stale loaders before starting replacements, so their cleanup cannot
 // clear the new generation's live actor.
 state.avatarLoadTask=work();
 return state.avatarLoadTask;
}
function frame(now){
 window.requestAnimationFrame(frame);
 if(document.hidden||now-state.lastTick<32)return;
 const dt=state.lastTick?Math.min(.1,(now-state.lastTick)/1000):0;state.lastTick=now;
 for(const p of state.performers)if(p.moving&&now>=p.motionUntil){p.moving=false;p.vx=0;p.vy=0;}
 const pkg=state.pkg;if(!pkg)return;
 if(state.avatarError){el.avatarStatus.textContent=state.avatarError;state.avatarError="";}
 try{
  Render.renderCamera(pr,pkg,Core.shot(pkg,state.programId),state,world,dt);
  const previewState=Object.assign({},state,{blackout:false,lowerThird:false});
  Render.renderCamera(pv,pkg,Core.shot(pkg,state.previewId),previewState,world,0);
  if(state.previewBars)drawPreviewBars(pv);
  if(state.remoteProgram){
    pr.fillStyle="#000";pr.fillRect(0,0,Core.W,Core.H);
    pr.fillStyle="#ff8b8b";pr.font="bold 28px system-ui";pr.textAlign="center";
    pr.fillText("EXTERNAL PROGRAM SOURCE — NO LOCAL VIDEO FEED",Core.W/2,Core.H/2);
  }
  if(state.remotePreview){
    pv.fillStyle="#000";pv.fillRect(0,0,Core.W,Core.H);
    pv.fillStyle="#ff8b8b";pv.font="bold 28px system-ui";pv.textAlign="center";
    pv.fillText("EXTERNAL PREVIEW SOURCE — NO LOCAL VIDEO FEED",Core.W/2,Core.H/2);
  }
  if(state.mediaPublisher&&state.sharedSwitcher?.connected()){
   if(!state.remoteProgram)state.mediaPublisher.publish(state.programId,el.program).catch(e=>log("PROGRAM PUBLISH ERROR "+e.message));
   if(!state.remotePreview&&state.previewId!==state.programId)
     state.mediaPublisher.publish(state.previewId,el.preview).catch(e=>log("PREVIEW PUBLISH ERROR "+e.message));
  }
  if(state.transition){
   const f=1-(now-state.transition.started)/state.transition.duration;
   if(f>0){pr.globalAlpha=Math.min(1,Math.max(0,f));pr.drawImage(lastFrame,0,0);pr.globalAlpha=1;}
   else state.transition=null;
  }
 }catch(e){state.avatarError=e.message;log("RENDER ERROR "+e.message);}
 if(state.session){
  const elapsed=Math.max(0,Date.now()-Date.parse(state.session.startedAt));
  const seconds=Math.floor(elapsed/1000);
  el.timecode.textContent=String(Math.floor(seconds/3600)).padStart(2,"0")+":"+
   String(Math.floor(seconds/60)%60).padStart(2,"0")+":"+
   String(seconds%60).padStart(2,"0");
 }
 if(state.micAnalyser){
  const data=new Uint8Array(state.micAnalyser.frequencyBinCount);state.micAnalyser.getByteTimeDomainData(data);
  let power=0;for(const v of data){const n=(v-128)/128;power+=n*n;}
  const rms=Math.sqrt(power/data.length);
  el.micMeter.value=Math.min(1,rms*4);
 }
}
function initializeControls(){
 for(const [id,pkg] of Object.entries(Core.PACKAGES)){
  const option=document.createElement("option");option.value=id;option.textContent=pkg.title;el.genre.appendChild(option);
 }
 el.genre.addEventListener("change",()=>safe(()=>loadGenre(el.genre.value)));
 el.start.addEventListener("click",()=>safe(startProduction));
 el.stop.addEventListener("click",()=>safe(stopProduction));
 el.record.addEventListener("click",()=>safe(startRecording));
 el.recordStop.addEventListener("click",()=>safe(stopRecording));
 $("cut").addEventListener("click",()=>safe(()=>cut(false)));
 $("fade").addEventListener("click",()=>safe(()=>cut(true)));
 $("moveLeft").addEventListener("click",()=>safe(()=>move(-.07)));
 $("moveRight").addEventListener("click",()=>safe(()=>move(.07)));
 $("gesture").addEventListener("click",()=>safe(animate));
 $("reset").addEventListener("click",()=>safe(reset));
 $("lower").addEventListener("click",()=>safe(()=>{state.lowerThird=!state.lowerThird;cue("lower_third",{enabled:state.lowerThird,text:state.lowerText})}));
 $("black").addEventListener("click",()=>safe(async()=>{
   const enabled=!state.blackout;
   if(state.sharedSwitcher?.connected()){
     const response=await fetch("/api/production/video-cue",{
       method:"POST",headers:{"Content-Type":"application/json"},
       body:JSON.stringify({cue:"blackout",enabled})
     });
     if(!response.ok)throw Error("Shared blackout command HTTP "+response.status);
     const result=await response.json();
     if(!result?.ok)throw Error("Shared blackout was not confirmed");
     state.lastBlackoutSeq=Number(result.blackout_seq)||state.lastBlackoutSeq;
   }
   state.blackout=enabled;if(!enabled)state.panicActive=false;
   setControls();cue("blackout",{enabled,shared:!!state.sharedSwitcher?.connected()});
 }));
 $("scoreLeft").addEventListener("click",()=>safe(()=>{state.scores[0]++;cue("score",{contestant:0,value:state.scores[0]})}));
 $("scoreRight").addEventListener("click",()=>safe(()=>{state.scores[1]++;cue("score",{contestant:1,value:state.scores[1]})}));
 $("backFile").addEventListener("change",e=>safe(()=>chooseImage(e.target,"back")));
 $("frontFile").addEventListener("change",e=>safe(()=>chooseImage(e.target,"front")));
 $("midFile").addEventListener("change",e=>safe(()=>chooseImage(e.target,"mid")));
 $("clearAssets").addEventListener("click",()=>safe(()=>{
  for(const key of ["back","mid","front"]){const k=state.pkg.id+key;if(state.assetUrls[k]){URL.revokeObjectURL(state.assetUrls[k]);delete state.assetUrls[k];}delete state.assets[key];}
  el.assetInfo.textContent="Procedural fallback layers restored";emit("set.asset.reset",{});log("Placeholder scenery restored");
 }));
 el.micLevel.addEventListener("input",()=>{state.microphoneLevel=Number(el.micLevel.value)/100;if(state.micGain&&!state.microphoneMuted)state.micGain.gain.value=state.microphoneLevel;});
 el.micMute.addEventListener("click",()=>{state.microphoneMuted=!state.microphoneMuted;if(state.micGain)state.micGain.gain.value=state.microphoneMuted?0:state.microphoneLevel;setControls();emit("audio.mic_mute",{muted:state.microphoneMuted})});
 el.download.addEventListener("click",()=>safe(()=>{if(state.selected?.blob)downloadBlob(state.selected.blob,state.selected.takeId+"."+(/mp4/.test(state.selected.blob.type)?"mp4":"webm"))}));
 $("recoveryDownload").addEventListener("click",()=>safe(()=>{
   if(state.recovery)downloadBlob(state.recovery.blob,state.recovery.take.id+"."+(/mp4/.test(state.recovery.blob.type)?"mp4":"webm"));
 }));
 $("recoverySave").addEventListener("click",()=>safe(async()=>{
   const recovery=state.recovery;if(!recovery)return;
   await Store.save(recovery.session,recovery.blob);state.recovery=null;
   el.alert.textContent="";status("ON AIR");setControls();await refreshSessions();log("RECOVERY SAVED "+recovery.take.id);
 }));
 el.manifest.addEventListener("click",()=>safe(()=>{if(state.selected?.session)downloadBlob(new Blob([JSON.stringify(state.selected.session,null,2)],{type:"application/json"}),state.selected.session.id+".json")}));
 window.addEventListener("pagehide",()=>{
   state.mediaPublisher?.stop().catch(()=>{});
   state.sharedSwitcher?.detach();
   state.avatarGeneration++;
   for(const id of state.loadedActorIds)state.avatarBridge?.clear?.(id);
   state.loadedActorIds.clear();
   if(state.recorder&&state.recorder.state==="recording"){try{state.recorder.requestData()}catch(_){}}
 });
 window.addEventListener("beforeunload",e=>{if(state.recorder||state.recovery){e.preventDefault();e.returnValue="";}});
 document.addEventListener("pubcast-glb-ready",()=>loadActors());
}
async function init(){
 initializeControls();
 try{const db=await Store.open();db.close();state.storageReady=true;}catch(e){error("Persistent recording storage unavailable: "+e.message);}
 loadGenre("news");setControls();await refreshSessions();
 window.requestAnimationFrame(frame);
 const cuePoll=setInterval(()=>syncServerVideoCues().catch(e=>log("CUE ERROR "+e.message)),500);
 window.addEventListener("pagehide",()=>clearInterval(cuePoll));
 window.PubCast25DStudio={state:()=>({package:state.pkg?.id,program:state.programId,preview:state.previewId,recording:!!state.recorder,session:state.session?.id||null,storage:state.storageReady}),
 loadGenre,choosePreview,cut,startProduction,stopProduction,startRecording,stopRecording};
 document.documentElement.dataset.production25d="ready";
}
init().catch(e=>error("Studio initialization failed: "+e.message));
})();
