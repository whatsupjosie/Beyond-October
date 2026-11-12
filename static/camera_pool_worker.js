/* Cooperative preview jobs, with consent and resource ownership across awaits. */
(function(){
"use strict";
const $=id=>document.getElementById(id),sid=new URLSearchParams(location.search).get("pool");
const work=new PubCastPoolAsync.Scope(),joins=new PubCastPoolAsync.Scope(),cleanup=new PubCastPoolAsync.Scope();
const views=new Map(),actors=new Map(),lastFrame=new Map(),counts={};
let pid=null,active=false,joining=false,joiningVersion=0,changing=false,disposed=false,state=null,pollJob=null,renderJob=null,assetJob=null;
let guard=new PubCastCameraPoolGuard.Guard(),outgoing=new PubCastCameraPoolGuard.UploadBudget();
let offered=null,lastContact=0,lastTick=performance.now(),lastRaf=0,lastAnimation=performance.now(),tokens=0,total=0,expensiveJobs=0,assetSignature="",fault="";
const world=document.createElement("canvas");world.width=1280;world.height=720;
function limits(){return {max_cameras:Number($("workerCameras").value),max_fps:Number($("workerFps").value),max_upload_kbps:Number($("workerUpload").value),render_ms_per_sec:Number($("workerBudget").value),allow_quality_reduction:$("workerQuality").checked};}
function request(scope,path,method="GET",body,version=scope.version){
 return scope.request("/api/camera-pool/sessions/"+encodeURIComponent(sid)+path,{method,
  headers:body?{"Content-Type":"application/json"}:undefined,body:body?JSON.stringify(body):undefined},r=>r.json(),3500,version);
}
function tasks(){return state?.assignments.filter(t=>t.participant_id===pid)||[];}
function live(ticket){return !disposed&&active&&work.current(ticket);}
function signature(scene){return JSON.stringify(scene.performers.map(p=>[p.id,p.slot,p.avatar]));}
function clearViews(){for(const item of views.values()){item.box.remove();item.canvas.width=0;item.output.width=0;}views.clear();lastFrame.clear();}
function clearActors(){for(const id of actors.values())window.PubCastGLB?.clear(id);actors.clear();assetSignature="";}
function performanceState(){
 const report=guard.report(performance.now(),document.hidden,!!offered?.allow_quality_reduction);
 if(active&&(!state||!state.scene_fresh||performance.now()-lastContact>4000||!tasks().length)){
  report.state="paused";report.work_scale=0;report.reason=!state?fault||"Waiting for session contact":!state.scene_fresh?"Director scene is stale":!tasks().length?"Waiting for a camera assignment":"Session contact expired";
 }
 if(active&&assetJob){report.state="calibrating";report.work_scale=0;report.reason="Preparing assigned camera assets";}
 if(active&&changing){report.state="paused";report.work_scale=0;report.reason="Waiting for confirmation of new limits";}
 report.reason=String(report.reason).slice(0,160);
 return report;
}
function display(){
 if(disposed)return;
 let text=joining?(work.current(joiningVersion)?"Waiting for consent acknowledgement…":"Joining cancelled; awaiting server acknowledgement"):!active?(fault||"Stopped. No camera work is running."):fault||performanceState().reason;
 if(active&&!fault&&performanceState().work_scale)text=`Contributing: ${tasks().length} assigned cameras; ${total} acknowledged frames.`;
 $("poolWorkerStatus").textContent=text;
 $("workerJoin").disabled=joining||active;$("workerLeave").disabled=!joining&&!active;$("workerLimits").disabled=!active;
}
function resetWork(){work.reset();state=null;fault="";tokens=0;lastContact=0;clearViews();clearActors();}
function terminal(error){return [401,403,404,410].includes(error.status);}
function endLocally(error){active=false;changing=false;pid=null;resetWork();$("workerAgree").checked=false;fault="Participation ended: "+error.message;}
async function poll(){
 if(!active||pollJob||changing)return;
 const ticket=work.version,person=pid,job={};pollJob=job;
 try{
  await request(work,`/participants/${person}/heartbeat`,"POST",performanceState(),ticket);
  const next=await request(work,"","GET",undefined,ticket);
  if(!live(ticket)||person!==pid)return;
  const self=next.members.find(m=>m.id===person&&m.active);if(!self)throw Error("Participation ended; join again to offer capacity");
  state=next;offered=self.limits;lastContact=performance.now();fault="";
  const assigned=tasks();
  for(const [source,item] of views)if(!assigned.some(t=>t.source_id===source)){item.box.remove();item.canvas.width=0;item.output.width=0;views.delete(source);}
  if(!assigned.length&&!renderJob&&!assetJob)clearActors();
 }catch(e){if(live(ticket)){if(terminal(e))endLocally(e);else{state=null;fault="Paused: "+e.message;}}}finally{if(pollJob===job)pollJob=null;display();}
}
async function prepare(scene,ticket){
 const job={};assetJob=job;const created=[];const wanted=signature(scene);
 try{
  clearActors();
  if(!window.PubCastGLB)throw Error("3D actor renderer is unavailable");
  for(const p of scene.performers){
   const id="pool-"+ticket+"-"+p.id;
   created.push(id);
   await work.operation(signal=>PubCastGLB.load(id,"./world/test_avatars/MakeHuman_"+(p.avatar==="female"?"Female":"Male")+".glb",p.slot,{signal}),10000,ticket);
   if(!live(ticket)||!tasks().length||!state?.scene||signature(state.scene)!==wanted)throw PubCastPoolAsync.cancelled();
   actors.set(p.id,id);
  }
  if(!live(ticket))throw PubCastPoolAsync.cancelled();
  assetSignature=wanted;guard=new PubCastCameraPoolGuard.Guard();lastRaf=0;tokens=0;fault="";
 }catch(e){for(const id of created)window.PubCastGLB?.clear(id);if(live(ticket)){clearActors();fault="Camera preparation failed: "+e.message;guard.pause(performance.now(),fault);}}
 finally{if(assetJob===job)assetJob=null;display();}
}
function view(source){
 if(views.has(source))return views.get(source);
 const box=document.createElement("section"),label=document.createElement("p"),canvas=document.createElement("canvas"),output=document.createElement("canvas");
 label.textContent=source;canvas.width=1280;canvas.height=720;output.width=640;output.height=360;box.dataset.source=source;box.append(label,canvas);$("workerViews").appendChild(box);
 const item={box,canvas,output,ctx:canvas.getContext("2d"),out:output.getContext("2d")};views.set(source,item);return item;
}
async function tick(){
 const now=performance.now(),report=performanceState(),budget=(offered?.render_ms_per_sec||0)*report.work_scale;
 tokens=Math.min(budget,tokens+(now-lastTick)*budget/1000);lastTick=now;
 if(!active||!state?.scene_fresh||now-lastContact>4000||!tasks().length||renderJob||assetJob)return display();
 if(!report.work_scale)return display();
 const ticket=work.version,scene=state.scene,revision=state.sequence;
 const profile=PubCast25D.PACKAGES[scene.package],prefix="p25d_"+scene.package+"_";
 if(!profile||tasks().some(t=>!profile.cameras.some(c=>prefix+c.id===t.source_id))){guard.held=true;guard.reason="Unsupported camera view; ask the director to release this assignment";return display();}
 if(assetSignature!==signature(scene)){void prepare(scene,ticket);return;}
 if(tokens<1)return;
 const task=tasks().filter(t=>now-(lastFrame.get(t.grant)||0)>=1000/(t.fps*report.work_scale)).sort((a,b)=>(lastFrame.get(a.grant)||0)-(lastFrame.get(b.grant)||0))[0];
 if(!task)return;
 const job={};renderJob=job;lastFrame.set(task.grant,now);
 const started=performance.now();let costCharged=false;
 function charge(){if(costCharged)return 0;costCharged=true;const cost=performance.now()-started;tokens-=cost;expensiveJobs=cost>180?expensiveJobs+1:0;if(expensiveJobs>=3){guard.held=true;guard.reason="Repeated slow camera jobs; apply new limits to retry";}return cost;}
 try{
  const item=view(task.source_id),pkg=PubCast25D.PACKAGES[scene.package],shot=task.source_id.slice(("p25d_"+scene.package+"_").length);
  const dt=Math.min(.1,(now-lastAnimation)/1000);lastAnimation=now;
  const renderState={...scene,performers:scene.performers.map(p=>({...p,id:actors.get(p.id)})),blackout:false,lowerThird:false,assets:{},avatarBridge:PubCastGLB,pixelScale:report.preview_width/640};
  PubCast25DRenderer.renderCamera(item.ctx,pkg,PubCast25D.shot(pkg,shot),renderState,world,dt);
  if(renderState.avatarError)throw Error(renderState.avatarError);
  counts[task.source_id]=(counts[task.source_id]||0)+1;
  if(item.output.width!==report.preview_width){item.output.width=report.preview_width;item.output.height=report.preview_width*9/16;}
  item.out.drawImage(item.canvas,0,0,item.output.width,item.output.height);
  const blob=await work.operation(()=>new Promise((resolve,reject)=>item.output.toBlob(b=>b?resolve(b):reject(Error("Camera encoder returned no data")),"image/jpeg",.68)),2500,ticket);
  const renderMs=charge();
  if(!live(ticket)||performance.now()-lastContact>4000||state?.sequence!==revision||!tasks().some(t=>t.grant===task.grant))return;
  if(!outgoing.reserve(blob.size,offered.max_upload_kbps,performance.now())){guard.pause(performance.now(),"Camera upload budget reached");return;}
  const ack=await work.request("/api/studio25d/media/frames/"+encodeURIComponent(task.source_id),{method:"POST",
   headers:{"Content-Type":"image/jpeg","X-Studio-Session":pid,"X-Camera-Pool":sid,"X-Pool-Participant":pid,"X-Pool-Grant":task.grant,"X-Pool-Scene-Version":String(revision),"X-Render-Ms":renderMs.toFixed(2)},body:blob},r=>r.json(),2500,ticket);
  if(!live(ticket))return;
  if(!ack.ok||ack.source_id!==task.source_id||!Number.isInteger(ack.sequence)||ack.sequence<1||ack.pool_id!==sid||ack.participant_id!==pid||ack.assignment_id!==task.assignment_id||ack.scene_version!==revision||ack.width!==item.output.width||ack.height!==item.output.height)throw Error("Invalid frame acknowledgement");
  // Admission is paced at the server. Start the next interval after its ACK so
  // encode/network jitter cannot make a healthy contributor arrive too early.
  lastFrame.set(task.grant,performance.now());total++;fault="";
 }catch(e){if(live(ticket)){fault="Camera task paused: "+e.message;if(e.status===409){state=null;void poll();}else guard.pause(performance.now(),fault);}}
 finally{if(live(ticket))charge();if(renderJob===job)renderJob=null;display();}
}
async function stop(){
 const person=pid;active=false;changing=false;pid=null;resetWork();$("workerAgree").checked=false;display();
 if(person){try{await request(cleanup,`/participants/${person}`,"DELETE");}catch(e){if(!disposed&&!active){fault="Stopped locally; server acknowledgement unavailable. Participation will expire.";$("poolWorkerStatus").textContent=fault;}}}
}
$("workerJoin").onclick=async()=>{
 if(active||joining||disposed)return;
 if(!$("workerAgree").checked){fault="Check consent before offering capacity";display();return;}
 const offeredNow=limits();resetWork();const ticket=work.version;joiningVersion=ticket;joining=true;display();
 try{
  const result=await request(joins,"/join","POST",{consent:true,label:$("workerLabel").value,limits:offeredNow});
  if(disposed||!work.current(ticket)||!$("workerAgree").checked){await request(cleanup,`/participants/${result.participant_id}`,"DELETE");return;}
  pid=result.participant_id;offered=offeredNow;active=true;guard=new PubCastCameraPoolGuard.Guard();outgoing=new PubCastCameraPoolGuard.UploadBudget();expensiveJobs=0;lastRaf=0;lastTick=performance.now();lastAnimation=lastTick;
  await poll();
 }catch(e){if(!disposed&&work.current(ticket)){fault=e.message;$("poolWorkerStatus").textContent=fault;}}
 finally{joining=false;display();}
};
$("workerLimits").onclick=async()=>{
 if(!active)return;
 const person=pid;changing=true;resetWork();const ticket=work.version;
 try{await request(work,`/participants/${person}/limits`,"PUT",limits(),ticket);if(live(ticket)){changing=false;guard=new PubCastCameraPoolGuard.Guard();expensiveJobs=0;lastRaf=0;await poll();}}
 catch(e){if(live(ticket)){if(terminal(e))endLocally(e);else fault="Limits update failed; work remains paused: "+e.message;display();}}
};
$("workerLeave").onclick=stop;$("workerAgree").onchange=()=>{if(!$("workerAgree").checked&&(active||joining))void stop();};
let raf;
function uiFrame(now){if(lastRaf)guard.sample(now-lastRaf,now);lastRaf=now;raf=requestAnimationFrame(uiFrame);}
raf=requestAnimationFrame(uiFrame);
let observer;
try{observer=new PerformanceObserver(list=>{for(const entry of list.getEntries())if(active&&guard.base!==null&&entry.duration>180)guard.pause(performance.now(),"Long UI task detected");});observer.observe({type:"longtask",buffered:false});}catch(_){}
const pollTimer=setInterval(poll,1500),renderTimer=setInterval(()=>{void tick();},50);
window.PubCastCameraPoolWorker={stop,status:()=>({active,joining,participant_id:pid,frames:total,renderCalls:{...counts},in_flight:!!renderJob,preparing:!!assetJob,loaded_actors:actors.size,performance:performanceState()})};
display();
window.addEventListener("pagehide",()=>{const person=pid;disposed=true;active=false;work.reset();joins.reset();clearInterval(pollTimer);clearInterval(renderTimer);cancelAnimationFrame(raf);observer?.disconnect();clearViews();clearActors();if(person)fetch("/api/camera-pool/sessions/"+sid+"/participants/"+person,{method:"DELETE",keepalive:true}).catch(()=>{});});
window.addEventListener("pageshow",event=>{if(event.persisted)location.reload();});
if(!sid||!/^pool_[a-f0-9]{32}$/.test(sid)){$("workerJoin").disabled=true;$("poolWorkerStatus").textContent="Open the invitation link provided by your director.";}
})();
