/* Separate source heartbeats, view requests and consent controls by lifetime. */
(function(){
"use strict";
window.PubCastPoolPanelController={mount(section,flows){
 const $=id=>section.querySelector("#"+id),view=new PubCastPoolAsync.Scope(),sourceRequests=new PubCastPoolAsync.Scope(),actions=new PubCastPoolAsync.Scope(),closing=new PubCastPoolAsync.Scope();
 const closeJobs=new Map();
 const images=new Map(),imageErrors=new Map();
 let sid="",state=null,source=null,refreshJob=null,sourceJob=null,sourceStateJob=null,disposed=false,creating=false,mutating=false,retryClose="";
 const message=text=>{$("poolMessage").textContent=text;};
 function api(scope,path,method="GET",body,ticket=scope.version){return scope.request("/api/camera-pool/"+path.replace(/^\//,""),{method,headers:body?{"Content-Type":"application/json"}:undefined,body:body?JSON.stringify(body):undefined},r=>r.json(),4000,ticket);}
 function clearImages(){for(const item of images.values())URL.revokeObjectURL(item.url);images.clear();imageErrors.clear();}
 function options(select,items){const previous=select.value;select.replaceChildren();for(const item of items){const option=document.createElement("option");option.value=item.id;option.textContent=item.label;option.disabled=!!item.disabled;select.appendChild(option);}if(items.some(i=>i.id===previous&&!i.disabled))select.value=previous;}
 function currentImage(task,next=state){const item=images.get(task.source_id);return item&&next?.scene_fresh&&item.scene===next.sequence&&item.assignment===task.assignment_id&&performance.now()-item.at<2500?item:null;}
 function buttons(){
  $("poolCreate").hidden=!window.PubCast25DStudio;$("poolCreate").disabled=creating||!!source;
  $("poolOpen").disabled=creating||mutating;$("poolAssignment").disabled=!state?.is_director||mutating;
  $("poolClose").disabled=mutating||(!state?.is_director&&!retryClose);
 }
 function draw(){
  buttons();$("poolMembers").replaceChildren();
  if(!state){$("poolTasks").replaceChildren();flows.textContent="";return;}
  for(const m of state.members){
   const row=document.createElement("tr");row.dataset.participant=m.id;
   const tasks=state.assignments.filter(t=>t.participant_id===m.id).map(t=>t.source_id+" ("+t.fps+" fps)");
   const perf=m.performance;
   for(const value of [m.label+" / "+(m.active?"consenting":"offline / stopped"),m.limits.max_cameras+" cameras; "+m.limits.max_fps+" fps; "+m.limits.max_upload_kbps+" kbps; "+m.limits.render_ms_per_sec+" ms/s render target",tasks.join(", ")||"None",m.upload_kbps+" kbps",m.relay_out_kbps+" kbps",m.frames+" / "+m.bytes+" B; "+m.actual_fps+" fps",m.render_ms.toFixed(1)+" ms; "+(perf?perf.state+" / UI p95 "+(perf.frame_p95_ms?.toFixed(1)||"—")+" ms / "+perf.reason:"waiting for performance report")]){const cell=document.createElement("td");cell.textContent=value;cell.style.padding="7px";row.appendChild(cell);}
   $("poolMembers").appendChild(row);
  }
  options($("poolPerson"),state.members.filter(m=>m.active).map(m=>({id:m.id,label:m.label})));
  const boxes=$("poolTasks");
  for(const box of [...boxes.children])if(!state.assignments.some(t=>t.source_id===box.dataset.source))box.remove();
  for(const task of state.assignments){
   let box=[...boxes.children].find(b=>b.dataset.source===task.source_id);
   if(!box){box=document.createElement("div");box.dataset.source=task.source_id;const caption=document.createElement("p"),image=document.createElement("img"),release=document.createElement("button");image.width=240;image.height=135;image.alt="Decoded assigned camera preview";image.style.background="#000";release.textContent="Release camera";box.append(caption,image,release);boxes.appendChild(box);}
   const cached=currentImage(task),freshness=imageErrors.get(task.source_id)||(!cached?(task.age_ms===null?"waiting for frames":"no current decoded frame"):"decoded frame");
   box.querySelector("p").textContent=task.source_id+" / "+freshness+" / "+task.upload_kbps+" kbps; target "+task.fps+" fps, actual "+task.actual_fps+" fps; "+(task.dimensions?.join("×")||"no frame yet");
   const image=box.querySelector("img");if(cached){image.src=cached.url;image.hidden=false;}else{image.hidden=true;image.removeAttribute("src");}
   const id=sid,assignment=task.assignment_id,sourceId=task.source_id,ticket=view.version;
   const release=box.querySelector("button");release.disabled=!state.is_director||mutating;
   release.onclick=()=>mutate(async()=>{if(!view.current(ticket))return;await api(actions,`/sessions/${id}/assignments/${sourceId}?assignment_id=${assignment}`,"DELETE");});
  }
  flows.textContent=state.flows.map(f=>`${f.from} → ${f.via} → ${f.to}: ${f.source_id}, ${f.kbps} kbps`).join(" · ")||"No deliveries measured in the current window.";
 }
 async function monitor(task,next,ticket){
  const existing=images.get(task.source_id);
  if(task.age_ms===null||task.age_ms>=2500||existing&&existing.frames===task.frames&&existing.scene===next.sequence&&existing.assignment===task.assignment_id)return;
  let url="";
  const requestedAt=performance.now();
  try{
   const data=await view.request("/api/studio25d/media/frames/"+encodeURIComponent(task.source_id),{},async response=>({blob:await response.blob(),age:response.headers.has("X-Studio-Frame-Age-Ms")?Number(response.headers.get("X-Studio-Frame-Age-Ms")):NaN,scene:Number(response.headers.get("X-Pool-Scene-Version")),assignment:response.headers.get("X-Pool-Assignment")}),2000,ticket);
   if(!Number.isFinite(data.age)||data.age<0||data.age>=2500||data.scene!==next.sequence||data.assignment!==task.assignment_id)return;
   url=URL.createObjectURL(data.blob);const image=new Image();image.dataset.poolAssignment=task.assignment_id;image.src=url;
   await view.operation(()=>image.decode(),1500,ticket);
   if(disposed||!view.current(ticket)||state!==next||!state.assignments.some(t=>t.assignment_id===task.assignment_id))return;
   const old=images.get(task.source_id);if(old)URL.revokeObjectURL(old.url);
   images.set(task.source_id,{image,url,at:requestedAt-data.age,scene:next.sequence,assignment:task.assignment_id,frames:task.frames});url="";imageErrors.delete(task.source_id);
  }catch(e){if(view.current(ticket)&&state===next)imageErrors.set(task.source_id,e.status===503?"source unavailable":"frame unavailable / decode failed");}
  finally{if(url)URL.revokeObjectURL(url);}
 }
 function refresh(){
  if(disposed||!sid)return Promise.resolve();
  const ticket=view.version,id=sid;
  if(refreshJob?.ticket===ticket)return refreshJob.promise;
  const job={ticket};refreshJob=job;
  job.promise=(async()=>{
   try{
    const next=await api(view,`/sessions/${id}`,"GET",undefined,ticket);
    if(disposed||!view.current(ticket)||sid!==id)return;
    state=next;retryClose="";
    if(source?.id===id){source.liveState=next;source.stateAt=performance.now();}
    const cameras=await view.request("/api/switcher/state",{},r=>r.json(),2000,ticket);
    if(!view.current(ticket)||state!==next)return;
    options($("poolSource"),cameras.sources.filter(c=>c.id.startsWith("p25d_"+next.package+"_")).map(c=>({id:c.id,label:c.name+(c.id===next.program?" — Program stays local":""),disabled:c.id===next.program})));
    draw();message((next.scene_fresh?"Scene current. ":"Scene stale: work is paused. ")+next.members.filter(m=>m.active).length+" consenting participants; "+next.assignments.length+" assigned previews. "+(next.notice||""));
    await Promise.allSettled(next.assignments.map(task=>monitor(task,next,ticket)));
    if(view.current(ticket)&&state===next)draw();
   }catch(e){if(!disposed&&view.current(ticket)){if(e.status===404&&source?.id===id){sourceRequests.reset();source=null;}state=null;clearImages();draw();message("Pool unavailable: "+e.message);}}
   finally{if(refreshJob===job)refreshJob=null;}
  })();return job.promise;
 }
 async function removeWorker(){const frame=$("poolLocalWorker").querySelector("iframe");if(frame){try{await frame.contentWindow.PubCastCameraPoolWorker?.stop();}catch(_){}frame.remove();}}
 async function open(id){
  if(!/^pool_[a-f0-9]{32}$/.test(id))throw Error("Choose a valid pool");
  view.reset();actions.reset();state=null;sid=id;retryClose="";clearImages();draw();
  $("poolInvite").value=new URL("control_room.html?camera_pool="+id,location.href).href;
  await removeWorker();await refresh();
 }
 async function pump(){
  if(disposed||!source||sourceJob)return;
  if(source.paused){if(performance.now()>source.retryAt){source.retryAt=performance.now()+5000;void close(source.id).catch(()=>{});}return;}
  const target=source,ticket=sourceRequests.version,job={};sourceJob=job;
  try{
   const studio=window.PubCast25DStudio;
   if(!studio||studio.state().session!==target.production)throw Error("Source production ended");
   await api(sourceRequests,`/sessions/${target.id}/scene`,"PUT",studio.poolSnapshot(),ticket);
   if(!sourceStateJob){
    const job=sourceRequests.request(`/api/camera-pool/sessions/${target.id}`,{},r=>r.json(),1000,ticket)
     .then(next=>{if(source===target&&sourceRequests.current(ticket)){target.liveState=next;target.stateAt=performance.now();}})
     .catch(()=>{}).finally(()=>{if(sourceStateJob===job)sourceStateJob=null;});sourceStateJob=job;
   }
  }catch(e){if(sourceRequests.current(ticket)&&source===target){if(e.status===404){source=null;buttons();}message("Source scene update failed; remote jobs pause if updates stop: "+e.message);}}
  finally{if(sourceJob===job)sourceJob=null;}
 }
 async function mutate(action){if(mutating||disposed)return;mutating=true;buttons();try{await action();await refresh();}catch(e){if(!disposed)message(e.message);}finally{mutating=false;buttons();}}
 function close(id){
  if(closeJobs.has(id))return closeJobs.get(id);
  const promise=closeNow(id).finally(()=>closeJobs.delete(id));closeJobs.set(id,promise);return promise;
 }
 async function closeNow(id){
  const affectedSource=source?.id===id;if(affectedSource){source.paused=true;source.retryAt=performance.now()+5000;sourceRequests.reset();}
  if(sid===id){view.reset();state=null;clearImages();await removeWorker();draw();}
  try{await api(closing,`/sessions/${id}`,"DELETE");}
  catch(e){if(e.status!==404){if(sid===id)retryClose=id;buttons();throw Error("Stopped locally; server closure unconfirmed for "+id+". Retry Close pool. "+e.message);}}
  if(source?.id===id)source=null;
  if(sid===id){sid="";$("poolInvite").value="";retryClose="";draw();message("Pool closed; assignments withdrawn.");}
  buttons();
 }
 $("poolCreate").onclick=async()=>{
  if(creating||source||disposed)return;creating=true;buttons();
  try{const scene=PubCast25DStudio.poolSnapshot();if(!PubCast25DStudio.state().session)await PubCast25DStudio.startProduction();const production=PubCast25DStudio.state().session;const result=await api(actions,"/sessions","POST",{package:scene.package});if(disposed)return;source={id:result.id,production,paused:false};const option=document.createElement("option");option.value=result.id;option.textContent=result.id;$("poolSessions").appendChild(option);$("poolSessions").value=result.id;await pump();await open(result.id);}
  catch(e){if(!disposed)message(e.message);}finally{creating=false;buttons();}
 };
 $("poolOpen").onclick=()=>mutate(()=>open($("poolSessions").value));
 $("poolAssign").onclick=()=>mutate(async()=>{const id=sid;await api(actions,`/sessions/${id}/assignments`,"POST",{source_id:$("poolSource").value,participant_id:$("poolPerson").value,fps:Number($("poolFps").value),task:"camera_preview"});});
 $("poolClose").onclick=()=>mutate(()=>close(retryClose||sid));
 $("poolContribute").onclick=()=>{if(!sid)return message("Open a pool first");if($("poolLocalWorker").querySelector("iframe"))return;const frame=document.createElement("iframe");frame.src=new URL("camera_pool_worker.html?pool="+sid,location.href).href;frame.title="Consent and contribution controls";frame.name="camera-pool-contribution";frame.style.cssText="width:100%;height:700px;border:1px solid #59718a";$("poolLocalWorker").appendChild(frame);};
 window.PubCastCameraPool={assignedSources:()=>{const live=source&&!source.paused&&performance.now()-source.stateAt<4000?source.liveState:state;return live?.assignments.map(t=>t.source_id)||[];},previewFor:id=>{const task=state?.assignments.find(t=>t.source_id===id);return task&&id!==state.program?currentImage(task)?.image||null:null;},state:()=>state,endProduction:async()=>{if(source)await close(source.id);}};
 window.addEventListener("production25d-ready",buttons);
 const initial=actions.version;
 api(actions,"/sessions").then(async data=>{if(disposed||!actions.current(initial))return;for(const session of data.sessions){const option=document.createElement("option");option.value=session.id;option.textContent=session.package+" / "+session.id;$("poolSessions").appendChild(option);}const invited=new URLSearchParams(location.search).get("camera_pool");if(invited&&/^pool_[a-f0-9]{32}$/.test(invited)){if(!data.sessions.some(s=>s.id===invited)){const option=document.createElement("option");option.value=invited;option.textContent="Invited session";$("poolSessions").appendChild(option);}$("poolSessions").value=invited;await open(invited);}}).catch(e=>{if(!disposed&&actions.current(initial))message(e.message);});
 const pollTimer=setInterval(refresh,1500),sourceTimer=setInterval(pump,1000);
 window.addEventListener("pagehide",()=>{disposed=true;view.reset();sourceRequests.reset();actions.reset();closing.reset();clearInterval(pollTimer);clearInterval(sourceTimer);clearImages();state=null;});
 buttons();
}};
})();
