/* PubCast 2.5D integrated local production desk.
 * Genuine 2.5D layer composition, independent camera viewports, real canvas MediaRecorder,
 * optional mic capture, transactional local session persistence, no forged backend/Blackbox status.
 */
(function(){
"use strict";
const Core=window.PubCast25D, Render=window.PubCast25DRenderer, Store=window.PubCast25DStore, Capture=window.PubCast25DCapture;
if(!Core||!Render||!Store||!Capture){document.body.textContent="Studio dependencies could not load";return;}
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
micGain:null,micAnalyser:null,audioDest:null,recordingPromise:null,recordingComplete:null,recordingStarting:null,
recordingStartedAt:0,recordingId:null,recovery:null,
recordingMime:"",microphoneMuted:false,microphoneLevel:1,selected:null,playbackUrl:null,downloadUrl:null,
lastTick:0,blackout:false,panicActive:false,lowerThird:false,lowerText:"BELLA FAUX PAS",scores:[0,0],transition:null,
storageReady:false,assetUrls:{},assetByPackage:{},avatarChecks:0,
sharedSwitcher:null,remoteProgram:null,remotePreview:null,programMixSource:null,mediaPublisher:null,
avatarGeneration:0,avatarLoadingGeneration:-1,loadedActorIds:new Set(),
previewBars:false,lastPanicSeq:0,lastBlackoutSeq:0,lastBarsSeq:0,cuePollBusy:false};
let selectedServer=null,selectionVersion=0;
const archive=window.PubCast25DArchive?.create({store:Store,onState:report=>{
 $("archiveStatus").textContent=report.message;
 $("archivePause").disabled=!(archive.status().busy||report.state==="downloading");
 $("archiveSave").disabled=!state.selected?.blob||!!selectedServer||!!state.recorder||archive.status().busy;
}});
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
 try{await fn()}catch(e){if(e?.name==="AbortError")return;error(String(e?.message||e));console.error("PubCast 2.5D",e);}
}
function setControls(){
 const active=!!state.session,rec=!!state.recorder,stopping=!!state.recordingPromise,starting=!!state.recordingStarting;
 el.start.disabled=active;el.genre.disabled=active;el.stop.disabled=!active||stopping;
 el.record.disabled=!active||rec||stopping||starting||!state.storageReady;
 el.recordStop.disabled=(!rec&&!starting)||stopping;
 el.recordStop.textContent=starting?"CANCEL RECORDING START":"STOP RECORDING";
 el.record.disabled=el.record.disabled||!!state.recovery;
 $("recoveryPanel").hidden=!state.recovery;
 $("archiveSave").disabled=!state.selected?.take||!state.selected?.blob||rec||starting||stopping||!!selectedServer||!archive||archive.status().busy;
 $("archiveRefresh").disabled=rec||starting||stopping;
 $("archiveBundle").disabled=rec||starting||stopping||!selectedServer;
 el.recBadge.textContent=rec?"● REC "+state.recordingMime:starting?"PREPARING RECORDING":"REC OFF";
 el.recBadge.style.color=rec?"#ff7070":"";
 const microphoneLive=state.micStream?.getAudioTracks().some(t=>t.readyState==='live');
 el.audioBadge.textContent=microphoneLive?"MIC "+(state.microphoneMuted?"MUTED":"ACTIVE"):"MIC OFF";
 el.micMute.disabled=!microphoneLive;
 el.micLevel.disabled=!microphoneLive;
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
     if(state.recorder||state.recordingStarting)await stopRecording({immediate:true});
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
 await window.PubCastAudioDesk?.close();
 if(!state.session)return;
 if(state.recorder||state.recordingStarting)await stopRecording();
 if(state.recovery)throw Error("Save the unsaved take before ending this production. A recovery copy can also be downloaded below.");
 state.clacker?.close();state.clacker=null;
 const sess=state.session;
 emit("production.stop",{});
 Core.finish(sess,Date.now());
 if(state.storageReady)await Store.save(sess);
 try{await window.PubCastCameraPool?.endProduction?.();}catch(e){log("POOL CLOSE WARNING "+e.message);}
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
function cleanupMedia(media=state){
 media.micHandle?.stop();media.micHandle=null;
 for(const track of media.capturedAudioStream?.getTracks()||[])track.stop();
 for(const track of media.videoStream?.getTracks()||[])track.stop();
 for(const track of media.micStream?.getTracks()||[])track.stop();
 for(const track of media.audioDest?.stream?.getTracks()||[])track.stop();
 try{media.micSource?.disconnect()}catch(_){}
 try{media.micGain?.disconnect()}catch(_){}
 try{media.programMixSource?.disconnect()}catch(_){}
 if(media.audioContext&&media.audioContext!==window.PubcastProgramAudio?.context&&media.audioContext.state!=="closed")media.audioContext.close().catch(console.warn);
 media.videoStream=null;media.micStream=null;media.audioContext=null;
 media.micSource=null;media.micGain=null;media.micAnalyser=null;media.audioDest=null;media.programMixSource=null;
}
const captureOwner=Capture.id();
function captureLease(id,owner,onFailure=()=>{}){
 let busy=false,closed=false;
 const timer=setInterval(async()=>{
  if(busy)return;busy=true;
  try{await Store.renewCapture(id,owner);}catch(e){if(!closed)onFailure(e);}finally{busy=false;}
 },2000);
 return ()=>{closed=true;clearInterval(timer);};
}
async function startRecording(){
 if(!state.session)throw Error("Start a production before recording");
 if(state.recorder||state.recordingPromise||state.recordingStarting)throw Error("Already recording or preparing recording");
 if(archive?.status().busy)throw Error("Pause the server save before starting another take");
 if(archive?.status().viewBusy){archive.cancelView();$("archiveStatus").textContent="Server transfer paused for recording. Retry after the take.";}
 if(state.recovery)throw Error("Save or download the unsaved take before recording again");
 if(!state.storageReady)throw Error("Local persistent session storage is unavailable");
 if(!globalThis.crypto?.subtle)throw Error("Recording integrity checks require HTTPS or localhost");
 if(typeof el.program.captureStream!=="function")throw Error("Canvas.captureStream is unsupported");
 const mime=recordedMime(),sess=state.session,media={},op={cancelled:false,media};
 state.recordingStarting=op;state.mediaError=null;state.recordingHasData=false;state.recordingStopImmediate=false;setControls();
 const check=()=>{if(op.cancelled||state.recordingStarting!==op||state.session!==sess)throw new DOMException("Recording start canceled","AbortError");};
 let capture=null,adopted=false,stopLease=()=>{};
 try{
   media.videoStream=el.program.captureStream(30);
   if(!media.videoStream.getVideoTracks().length)throw Error("No video track from program canvas");
   const combined=new MediaStream([...media.videoStream.getVideoTracks()]);
   const programAudio=window.PubcastProgramAudio;
   if(programAudio?.captureOutputStream || el.mic.checked){
     const AC=window.AudioContext||window.webkitAudioContext;
     if(!AC)throw Error("Web Audio mix-to-record unavailable");
     if(!programAudio?.attachInput)throw Error('Shared program audio input mixer unavailable');
     media.audioContext=programAudio.ensureContext();await media.audioContext.resume();check();
     if(programAudio?.captureOutputStream){
       const liveMix=programAudio.captureOutputStream();
       await programAudio.context?.resume?.();check();
       if(!liveMix.getAudioTracks().length)throw Error("Shared program mixer has no capture track");
       media.programMixSource=liveMix;
       media.capturedAudioStream=liveMix.clone();
     }
     if(el.mic.checked){
       if(!navigator.mediaDevices?.getUserMedia)throw Error("Microphone capture unavailable; deselect mic to record without microphone");
       media.micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});check();
       media.micHandle=programAudio.attachInput('local-microphone',media.micStream,{label:'Local microphone',
         onStop:()=>media.micStream?.getTracks().forEach(t=>t.stop())});
       programAudio.configureInput(media.micHandle.id,{muted:state.microphoneMuted,volume:state.microphoneLevel});
       media.micGain=media.micHandle.gain;media.micAnalyser=media.micHandle.analyser;
     }
     for(const track of media.capturedAudioStream.getAudioTracks())combined.addTrack(track);
   }
   check();
   if(state.clacker?.failed){state.clacker.close();state.clacker=null;}
   if(!state.clacker){
     const reference=await window.PubCast25DClacker.create(programAudio.context,sess,e=>{
       state.mediaError=e;error(e.message);stopRecording({immediate:true}).catch(()=>{});
     });
     try{check();}catch(e){reference.close();throw e;}
     state.clacker=reference;
   }
   const rec=new MediaRecorder(combined,mime?{mimeType:mime,videoBitsPerSecond:3000000}:{videoBitsPerSecond:3000000});
   let startedAt=Date.now();const id=sess.id+"-take-"+startedAt+"-"+Capture.id().slice(0,8);
   capture={id,owner:captureOwner,session:structuredClone(sess),mime:rec.mimeType||mime||"video/webm",syncReferenceId:state.clacker.input.syncReferenceId,
     sourceId:"p25d_"+sess.packageId+"_"+state.programId,startedAt:new Date(startedAt).toISOString(),
     offsetMs:startedAt-Date.parse(sess.startedAt)};
   await Store.beginCapture(capture);check();
   media.sourceRecordings=new window.PubCast25DSourceRecordings({mixer:programAudio,session:sess,
     parentTakeId:id,owner:captureOwner,references:[state.clacker.input],onFailure:e=>{
       if(op.cancelled||(state.recordingId!==id&&state.recordingStarting!==op))return;
       state.mediaError=state.mediaError||e;
       $("captureStatus").textContent="Recording interrupted: "+e.message+". Available chunks are retained.";
       if(state.recorder)stopRecording({immediate:true}).catch(e=>error(e.message));
     }});
   await media.sourceRecordings.start();check();
   if(state.mediaError)throw state.mediaError;
   Object.assign(state,media);adopted=true;
   state.recordingSourceId=capture.sourceId;state.recordingMime=capture.mime;
   state.recordingStartedAt=startedAt;state.recordingId=id;
   let resolve,reject,finishing=false;
   const completion=new Promise((a,b)=>{resolve=a;reject=b;});completion.catch(()=>{});
   state.recordingComplete=completion;
   const fail=e=>{
     state.mediaError=state.mediaError||e;
     $("captureStatus").textContent="Recording interrupted: "+e.message+". Available chunks are retained.";
     stopRecording({immediate:true}).catch(e=>error(e.message));
   };
   const writer=Capture.create({store:Store,id,owner:captureOwner,session:sess,timing:capture,onFailure:fail,
     onProgress:p=>{if(!state.mediaError)$("captureStatus").textContent="Saved locally: "+p.bytes+" bytes in "+p.chunks+" checkpoints · checkpoint at "+(p.durationMs/1000).toFixed(1)+" seconds";}});
   stopLease=captureLease(id,captureOwner,e=>{if(!finishing)fail(e);});
   state.captureWriter=writer;
   rec.ondataavailable=e=>{if(e.data?.size){state.recordingHasData=true;writer.push(e.data,Date.now()-startedAt);}};
   rec.onerror=e=>fail(e.error||Error("MediaRecorder error"));
   rec.onstop=()=>{
    if(finishing)return;finishing=true;
    state.recordingPromise=completion;setControls();
    finishRecording(rec,writer,capture,sess).then(resolve,reject).finally(()=>stopLease());
   };
   state.recorder=rec;state.recordingStarting=null;
   // The durable reservation can take time: timestamp capture at actual start.
   startedAt=Date.now();capture.startedAt=new Date(startedAt).toISOString();capture.offsetMs=startedAt-Date.parse(sess.startedAt);
   state.recordingStartedAt=startedAt;
   rec.start(1000);
   emit("recording.start",{mime:state.recordingMime,microphone:!!state.micStream,
     sharedProgramMix:!!state.programMixSource,canvas:[Core.W,Core.H],journal:id});
   $("captureStatus").textContent="Recording started; waiting for the first local checkpoint.";
   log("REC START "+state.recordingMime+" / microphone "+(state.micStream?"ON":"OFF"));setControls();
 }catch(e){
   stopLease();
   await media.sourceRecordings?.stop().catch(()=>{});
   if(adopted){cleanupMedia();state.recorder=null;state.recordingComplete=null;state.captureWriter=null;}
   if(capture)await Store.releaseCapture(capture.id,captureOwner).catch(()=>{});
   if(!adopted&&(op.cancelled||state.recordingStarting!==op||state.session!==sess))
     throw new DOMException("Recording start canceled","AbortError");
   throw e;
 }finally{
   if(!adopted)cleanupMedia(media);
   if(state.recordingStarting===op)state.recordingStarting=null;
   setControls();
 }
}
async function finishRecording(rec,writer,capture,sess){
 try{
   const pending=await writer.settle();let captureError=state.mediaError||pending.error;
   try{await state.sourceRecordings?.stop();}catch(e){captureError=captureError||e;}
   const record=await Store.readCapture(capture.id);
   const blob=await Capture.assemble(record,pending.pending);
   emit("recording.stop",{bytes:blob.size,mime:blob.type,incomplete:!!captureError});
   if(!sess.recordings)sess.recordings=sess.media?[Object.assign({id:sess.id},sess.media)]:[];
   sess.media={id:capture.id,mime:blob.type,bytes:blob.size,sourceId:capture.sourceId,syncReferenceId:capture.syncReferenceId,
     startedAt:capture.startedAt,offsetMs:capture.offsetMs,durationMs:Date.now()-Date.parse(capture.startedAt),
     incomplete:!!captureError,journal:{chunks:record.chunks.length,bytes:record.capture.bytes}};
   sess.recordings.push(sess.media);
   state.recovery={session:sess,blob,take:sess.media,capture:{id:capture.id,owner:captureOwner}};
   await Store.save(sess,blob,state.recovery.capture);
   state.recovery=null;
   $("captureStatus").textContent=(captureError?"Incomplete take saved locally: ":"Take saved locally: ")+blob.size+" bytes.";
   log((captureError?"PARTIAL TAKE SAVED ":"REC SAVED ")+blob.size+" bytes; "+sess.events.length+" session events");
   await refreshSessions();
   if(captureError)throw Error("Recording interrupted; available partial media was saved: "+captureError.message);
   return blob;
 }catch(e){
   state.mediaError=e;
   await Store.releaseCapture(capture.id,captureOwner).catch(()=>{});
   log("REC FAILED "+e.message+(state.recovery?"; unsaved media remains available for recovery":"; committed journal chunks are retained"));
   throw e;
 }finally{
   state.sourceRecordings=null;
   cleanupMedia();state.recorder=null;state.recordingPromise=null;state.recordingComplete=null;state.captureWriter=null;setControls();
 }
}
// Ordinary Stop gives a short take up to three seconds to produce media.
// PANIC can interrupt that wait and never waits for encoder progress.
function waitForFirstData(rec,ms){
 return new Promise(resolve=>{
  const started=Date.now();
  const look=()=>{
   if(state.recordingHasData||state.recordingStopImmediate||rec.state!=="recording"||Date.now()-started>=ms)return resolve();
   try{rec.requestData();}catch(_){}
   setTimeout(look,100);
  };
  look();
 });
}
async function stopRecording(options){
 if(options?.immediate===true)state.recordingStopImmediate=true;
 if(state.recordingStarting){
   const op=state.recordingStarting;op.cancelled=true;state.recordingStarting=null;
   cleanupMedia(op.media);$("captureStatus").textContent="Recording start canceled.";setControls();return;
 }
 if(state.recordingPromise)return state.recordingPromise;
 if(!state.recorder)return;
 const rec=state.recorder,completion=state.recordingComplete;
 state.recordingPromise=completion;setControls();
 try{
  if(!state.recordingStopImmediate&&rec.state==="recording")await waitForFirstData(rec,3000);
  if(rec.state==="inactive")rec.onstop();else rec.stop();
 }catch(e){state.mediaError=e;rec.onstop();}
 return completion;
}
async function recoverCapture(id){
 if(state.recorder||state.recordingStarting||state.recordingPromise||state.session||state.recovery)
   throw Error("Finish the current production and save its take before recovering another recording");
 const capture=await Store.claimCapture(id,captureOwner);
 const stopLease=captureLease(id,captureOwner);
 try{
   const record=await Store.readCapture(id),blob=await Capture.assemble(record);
   const sess=record.capture.session;
   if(capture.kind==='audio-source'){
     const source={id,parentTakeId:capture.parentTakeId,sourceId:capture.sourceId,label:capture.label,kind:capture.sourceKind||'voice',syncReferenceId:capture.syncReferenceId||null,
       mime:blob.type,bytes:blob.size,startedAt:capture.startedAt,offsetMs:capture.offsetMs,
       durationMs:capture.durationMs,preFader:true,incomplete:true,recovered:true};
     await Store.saveSource(sess,source,blob,{id,owner:captureOwner});
     await refreshSessions();return;
   }
   const saved=await Store.read(sess.id);
   sess.sourceTracks=saved.session?.sourceTracks||sess.sourceTracks||[];
   if(!sess.recordings)sess.recordings=sess.media?[Object.assign({id:sess.id},sess.media)]:[];
   sess.media={id,mime:blob.type,bytes:blob.size,sourceId:capture.sourceId,syncReferenceId:capture.syncReferenceId||null,startedAt:capture.startedAt,
     offsetMs:capture.offsetMs,durationMs:record.capture.durationMs,incomplete:true,recovered:true,
     journal:{chunks:record.chunks.length,bytes:blob.size,lastCheckpointAt:record.capture.lastCheckpointAt}};
   sess.recordings.push(sess.media);
   if(!sess.endedAt){Core.event(sess,"recording.recovered",{take:id,committedBytes:blob.size},Date.now());Core.finish(sess,Date.now());}
   await Store.save(sess,blob,{id,owner:captureOwner});
   $("captureStatus").textContent="Recovered incomplete take: "+blob.size+" bytes. Material after the last checkpoint may be missing.";
   log("INTERRUPTED TAKE RECOVERED "+id);await refreshSessions();await selectSession(sess.id,id);
 }finally{stopLease();await Store.releaseCapture(id,captureOwner).catch(()=>{});}
}
async function refreshCaptureRecovery(){
 if(!state.storageReady)return;
 const rows=await Store.listCaptures(),list=$("captureRecoveryList");list.replaceChildren();
 const visible=rows.filter(r=>r.id!==state.recordingId||(!state.recorder&&!state.recordingStarting));
 if(!visible.length){list.textContent="No interrupted recordings found.";return;}
 for(const row of visible){
   const button=document.createElement("button");button.type="button";button.style.cssText="width:100%;min-height:44px;text-align:left;margin:4px 0";
   button.dataset.captureId=row.id;
   const active=row.leaseUntil>Date.now();
   button.textContent=(active?"Active in another tab / checking connection: ":"Recover incomplete take: ")+row.startedAt+" · "+row.bytes+" bytes saved";
   button.disabled=active||!row.bytes||!!state.session;
   button.onclick=()=>safe(()=>recoverCapture(row.id));list.appendChild(button);
 }
}
async function refreshSessions(){
 if(!state.storageReady)return;
 await refreshCaptureRecovery();
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
  for(const source of session.sourceTracks||[]){
   const btn=document.createElement('button');
   btn.textContent=(source.kind==='sync-reference'?'SYNC: ':'VOICE: ')+source.label+' · '+(source.incomplete?'INCOMPLETE · ':'')+source.bytes+' bytes';
   btn.onclick=()=>safe(()=>selectSession(session.id,source.id));el.sessionList.appendChild(btn);
  }
 }
}
async function selectSession(id,takeId){
 const selection=++selectionVersion;
 if(archive?.status().viewBusy){$("archiveStatus").textContent="Server transfer paused; local take selected.";$("archivePause").disabled=!archive.status().busy;}
 archive?.cancelView();
 const item=await Store.read(id,takeId);if(!item.session)throw Error("Session not found");
 if(selection!==selectionVersion)return;
 item.takeId=takeId||item.session.media?.id||id;
 const take=item.session.sourceTracks?.find(t=>t.id===item.takeId)||item.session.recordings?.find(t=>t.id===item.takeId)||item.session.media;
 item.take=take?{...take,id:item.takeId}:null;
 selectedServer=null;$("archiveBundle").disabled=true;
 if(state.playbackUrl){URL.revokeObjectURL(state.playbackUrl);state.playbackUrl=null;}
 state.selected=item;
 if(item.blob){state.playbackUrl=URL.createObjectURL(item.blob);el.playback.src=state.playbackUrl;}
 else {el.playback.removeAttribute("src");el.playback.load();}
 el.download.disabled=!item.blob;el.manifest.disabled=false;
 $("archiveSave").disabled=!item.blob||!archive||!!state.recorder||archive.status().busy;
 log("SESSION OPEN "+id+" / "+item.session.events.length+" events "+(item.blob?"MEDIA":"NO MEDIA"));
}
async function refreshServerTakes(){
 if(state.recorder||state.recordingStarting)throw Error("Finish recording before transferring server takes");
 if(!archive)throw Error("Server save component unavailable");
 const takes=await archive.list(),list=$("archiveList");list.replaceChildren();
 if(!takes.length)list.textContent="No server takes for this account.";
 for(const take of takes){
  const button=document.createElement("button");button.type="button";button.style.cssText="width:100%;min-height:44px;text-align:left;margin:4px 0;overflow-wrap:anywhere";
  button.textContent=take.take_id+" · "+take.state+" · "+take.received_bytes+" / "+take.expected_bytes+" bytes"+(Number.isFinite(take.capture_started_at)?" · captured "+new Date(take.capture_started_at*1000).toLocaleString():" · capture time unknown")+(take.capture_incomplete?" · INCOMPLETE CAPTURE":"");
  button.disabled=take.state!=="complete";
  button.onclick=()=>safe(async()=>{
   if(state.recorder||state.recordingStarting)throw Error("Finish recording before opening server media");
   selectedServer=take;$("archiveBundle").disabled=true;
   selectionVersion++;
   state.selected=null;el.download.disabled=true;el.manifest.disabled=true;$("archiveSave").disabled=true;
   if(state.playbackUrl){URL.revokeObjectURL(state.playbackUrl);state.playbackUrl=null;}
   el.playback.removeAttribute("src");el.playback.load();
   $("archiveStatus").textContent="Loading validated server take…";
   const item=await archive.download(take.id);
   if(selectedServer!==take)return;
   if(item.sha256!==take.sha256||item.blob.size!==take.received_bytes)throw Error("Server media response does not match its saved manifest");
   if(state.playbackUrl)URL.revokeObjectURL(state.playbackUrl);
   state.selected={blob:item.blob,takeId:take.take_id};
   el.download.disabled=false;
   state.playbackUrl=URL.createObjectURL(item.blob);el.playback.src=state.playbackUrl;
   $("archiveBundle").disabled=false;$("archiveStatus").textContent="Opened server take: "+item.blob.size+" verified source bytes.";
  });list.appendChild(button);
  if(take.state==="uploading"){
   const end=document.createElement("button");end.type="button";end.textContent="End unfinished upload (keep its bytes)";
   end.onclick=()=>safe(async()=>{await archive.abandon(take.id);await refreshServerTakes();});list.appendChild(end);
  }
 }
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
  state.actorFrameStamp=now;
  Render.renderCamera(pr,pkg,Core.shot(pkg,state.programId),state,world,dt);
  const previewState=Object.assign({},state,{blackout:false,lowerThird:false,reuseActorFrame:true});
  const pooledPreview=window.PubCastCameraPool?.previewFor?.("p25d_"+pkg.id+"_"+state.previewId);
  if(pooledPreview)pv.drawImage(pooledPreview,0,0,Core.W,Core.H);
  else Render.renderCamera(pv,pkg,Core.shot(pkg,state.previewId),previewState,world,0);
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
  if(state.transition){
   const f=1-(now-state.transition.started)/state.transition.duration;
   if(f>0){pr.globalAlpha=Math.min(1,Math.max(0,f));pr.drawImage(lastFrame,0,0);pr.globalAlpha=1;}
   else state.transition=null;
  }
  if(state.clacker?.paint(el.program,!state.blackout&&!state.remoteProgram))
    state.videoStream?.getVideoTracks()[0]?.requestFrame?.();
  state.clacker?.paint(el.preview,!state.remotePreview);
  if(state.mediaPublisher&&state.sharedSwitcher?.connected()){
   const assigned=window.PubCastCameraPool?.assignedSources?.()||[];
   // Program is always source-local, including while an old preview assignment
   // is still present in a delayed pool-state response after a CUT.
   if(!state.remoteProgram)state.mediaPublisher.publish(state.programId,el.program).catch(e=>log("PROGRAM PUBLISH ERROR "+e.message));
   if(!state.remotePreview&&state.previewId!==state.programId&&!assigned.includes("p25d_"+pkg.id+"_"+state.previewId))
     state.mediaPublisher.publish(state.previewId,el.preview).catch(e=>log("PREVIEW PUBLISH ERROR "+e.message));
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
 $("archiveSave").onclick=()=>safe(async()=>{
  if(state.recorder||state.recordingStarting)throw Error("Finish recording before transferring a saved take");
  const selected=state.selected;if(!selected?.blob||!selected.take)throw Error("Select a saved local take first");
  try{
   await archive.save({...selected,sourceId:selected.blob.type.startsWith('audio/')?
     'p25d_voice_'+selected.take.sourceId.replace(/[^A-Za-z0-9_]/g,'_'):
     selected.take.sourceId||"p25d_"+selected.session.packageId+"_"+Core.PACKAGES[selected.session.packageId].cameras[0].id});
   await refreshServerTakes();
  }finally{$("archivePause").disabled=true;$("archiveSave").disabled=!state.selected?.blob||!!selectedServer||!!state.recorder;}
 });
 $("archivePause").onclick=()=>archive.cancel();
 $("archiveRefresh").onclick=()=>safe(refreshServerTakes);
 $("archiveBundle").onclick=()=>safe(async()=>{
  if(!selectedServer)return;
  const take=selectedServer;
  const blob=await archive.bundle(take.id);
  downloadBlob(blob,take.take_id+"-source.zip");
 });
 window.addEventListener("pagehide",()=>archive?.close());
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
 el.micLevel.addEventListener("input",()=>{state.microphoneLevel=Number(el.micLevel.value)/100;if(state.micHandle)window.PubcastProgramAudio.configureInput(state.micHandle.id,{volume:state.microphoneLevel});});
 el.micMute.addEventListener("click",()=>{state.microphoneMuted=!state.microphoneMuted;if(state.micHandle)window.PubcastProgramAudio.configureInput(state.micHandle.id,{muted:state.microphoneMuted});setControls();emit("audio.mic_mute",{muted:state.microphoneMuted})});
 el.download.addEventListener("click",()=>safe(()=>{if(state.selected?.blob)downloadBlob(state.selected.blob,state.selected.takeId+"."+(/mp4/.test(state.selected.blob.type)?"mp4":"webm"))}));
 $("recoveryDownload").addEventListener("click",()=>safe(()=>{
   if(state.recovery)downloadBlob(state.recovery.blob,state.recovery.take.id+"."+(/mp4/.test(state.recovery.blob.type)?"mp4":"webm"));
 }));
 $("recoverySave").addEventListener("click",()=>safe(async()=>{
   const recovery=state.recovery;if(!recovery)return;
   await Store.save(recovery.session,recovery.blob,recovery.capture);state.recovery=null;
   el.alert.textContent="";status("ON AIR");setControls();await refreshSessions();log("RECOVERY SAVED "+recovery.take.id);
 }));
 el.manifest.addEventListener("click",()=>safe(()=>{if(state.selected?.session)downloadBlob(new Blob([JSON.stringify(state.selected.session,null,2)],{type:"application/json"}),state.selected.session.id+".json")}));
 window.addEventListener("pagehide",()=>{
   state.mediaPublisher?.stop().catch(()=>{});
   state.sharedSwitcher?.detach();
   state.avatarGeneration++;
   for(const id of state.loadedActorIds)state.avatarBridge?.clear?.(id);
   state.loadedActorIds.clear();
   if(state.recordingStarting){state.recordingStarting.cancelled=true;cleanupMedia(state.recordingStarting.media);}
   // Do not rely on unload callbacks: only committed checkpoints survive a crash.
   if(state.recorder&&state.recorder.state==="recording"){try{state.recorder.requestData()}catch(_){}}
 });
 window.addEventListener("beforeunload",e=>{if(state.recorder||state.recordingStarting||state.recovery){e.preventDefault();e.returnValue="";}});
 document.addEventListener("pubcast-glb-ready",()=>loadActors());
}
async function init(){
 initializeControls();
 window.PubcastProgramAudio?.onInput((type,input)=>{emit('audio.input.'+type,{id:input.id,label:input.label,
   volume:input.volume,muted:input.muted,solo:input.solo,eq:input.eq,connectedAt:input.connectedAt});setControls();});
 try{const db=await Store.open();db.close();state.storageReady=true;}catch(e){error("Persistent recording storage unavailable: "+e.message);}
 loadGenre("news");setControls();await refreshSessions();
 window.requestAnimationFrame(frame);
 const cuePoll=setInterval(()=>syncServerVideoCues().catch(e=>log("CUE ERROR "+e.message)),500);
 const recoveryPoll=setInterval(()=>refreshCaptureRecovery().catch(()=>{}),3000);
 window.addEventListener("pagehide",()=>{clearInterval(cuePoll);clearInterval(recoveryPoll);state.clacker?.close();});
 window.PubCast25DStudio={state:()=>({package:state.pkg?.id,program:state.programId,preview:state.previewId,recording:!!state.recorder,recordingStarting:!!state.recordingStarting,journal:state.captureWriter?.status()||null,session:state.session?.id||null,storage:state.storageReady}),
 loadGenre,choosePreview,cut,startProduction,stopProduction,startRecording,stopRecording,recoverCapture,
 poolSnapshot:()=>{
  if(Object.values(state.assets).some(Boolean))throw Error("Shared camera previews currently require the bundled set assets");
  for(const p of state.performers){
   const expected=new URL("./world/test_avatars/MakeHuman_"+(p.avatar==="female"?"Female":"Male")+".glb",location.href).href;
   if(state.avatarBridge?.info?.(p.id)?.sourceUrl!==expected)throw Error("Shared camera previews currently require the bundled performers to finish loading");
  }
  return {package:state.pkg.id,performers:state.performers.map(p=>({id:p.id,slot:p.slot,avatar:p.avatar,
   position:p.position.slice(),vx:p.vx||0,vy:p.vy||0,moving:!!p.moving})),lowerThird:state.lowerThird,
   lowerText:state.lowerText,scores:state.scores.slice(),blackout:state.blackout};
 }};
 document.documentElement.dataset.production25d="ready";
 window.dispatchEvent(new Event("production25d-ready"));
}
init().catch(e=>error("Studio initialization failed: "+e.message));
})();
