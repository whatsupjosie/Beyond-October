/* PubCast 2.5D real-frame confidence publisher.
 * The same browser that renders program/preview publishes downscaled JPEGs to
 * an authenticated bounded server endpoint. This is a monitor confidence feed,
 * not a replacement for full frame-rate local capture or future WebRTC ingest.
 * No response means no claim of live media.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DFramePublisher=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 function create(options={}) {
   const fetcher=options.fetch||(typeof fetch!=="undefined"?fetch.bind(globalThis):null);
   const session=String(options.session||"");
   const sourceId=options.sourceId;
   const onState=typeof options.onState==="function"?options.onState:()=>{};
   const onError=typeof options.onError==="function"?options.onError:()=>{};
   if(!/^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$/.test(session))throw Error("Invalid publisher session");
   if(typeof sourceId!=="function")throw Error("Studio camera source mapping required");
   if(!fetcher)throw Error("Fetch unavailable");
   let stopped=false,acknowledged=0,errors=0,cooldownUntil=0;
   const busySources=new Set(),lastAtBySource=new Map();
   const schedule=options.setTimeout||globalThis.setTimeout?.bind(globalThis);
   const cancel=options.clearTimeout||globalThis.clearTimeout?.bind(globalThis);
   const clock=options.now||(()=>globalThis.performance?.now?.()??Date.now());
   const pending=new Set();
   async function boundedTask(action,limitMs){
     if(typeof AbortController==="undefined"||!schedule)return action(undefined);
     const controller=new AbortController();pending.add(controller);
     let rejectAbort;const aborted=new Promise((_,reject)=>{rejectAbort=()=>reject(Error("Confidence operation cancelled or timed out"));controller.signal.addEventListener("abort",rejectAbort,{once:true});});
     const timer=schedule(()=>controller.abort(),limitMs);
     try{return await Promise.race([Promise.resolve().then(()=>{if(stopped||controller.signal.aborted)throw Error("Publisher stopped");return action(controller.signal);}),aborted]);}
     finally{if(cancel)cancel(timer);controller.signal.removeEventListener("abort",rejectAbort);pending.delete(controller);}
   }
   async function boundedFetch(url,init,limitMs){
     if(typeof AbortController==="undefined"||!schedule)return fetcher(url,init);
     const controller=new AbortController(),timer=schedule(()=>controller.abort(),limitMs);
     try{return await fetcher(url,{...init,signal:controller.signal});}
     finally{if(cancel)cancel(timer);}
   }
   const size={width:640,height:360},minInterval=220;
   // Only constructed when a real browser canvas is available.
   const scratchBySource=new Map();
   function toJpeg(canvas,source) {
     if(typeof options.encode==="function")return options.encode(canvas,source);
     let item=scratchBySource.get(source);
     if(!item){
       const scratch=document.createElement("canvas");scratch.width=size.width;scratch.height=size.height;
       item={scratch,context:scratch.getContext("2d",{alpha:false})};
       scratchBySource.set(source,item);
     }
     if(!item.context||!canvas)throw Error("2.5D camera frame unavailable");
     item.context.drawImage(canvas,0,0,size.width,size.height);
     return new Promise((resolve,reject)=>{
       item.scratch.toBlob(blob=>blob&&blob.size?resolve(blob):reject(Error("JPEG confidence encoder returned no data")),"image/jpeg",.68);
     });
   }
   async function publish(cameraId,canvas,now=clock()){
     if(stopped||!cameraId||!canvas||now<cooldownUntil)return false;
     const id=sourceId(cameraId);
     if(busySources.has(id)||now-(lastAtBySource.get(id)||0)<minInterval)return false;
     busySources.add(id);lastAtBySource.set(id,now);
     try {
       const blob=await boundedTask(()=>toJpeg(canvas,id),2500);
       if(stopped)return false;
       if(!blob||blob.size>240000)throw Error("Confidence frame exceeds 240KB budget");
       const result=await boundedTask(async signal=>{
        const response=await fetcher("/api/studio25d/media/frames/"+encodeURIComponent(id),{
         method:"POST",credentials:"same-origin",headers:{"Content-Type":"image/jpeg","X-Studio-Session":session},body:blob,signal
        });
        if(response.status===409){
         const reason=await response.json().catch(()=>({}));
         // A pool assignment is an intentional lease handover. Do not put the
         // producer's other camera feeds into a global error cooldown for it.
         if(reason.detail==="Camera rendering is assigned to a pool participant")return {delegated:true};
        }
        if(!response.ok)throw Error("Confidence upload HTTP "+response.status);
        return response.json();
       },2000);
       if(stopped||result?.delegated)return false;
       if(!result?.ok||result.source_id!==id||!Number.isInteger(result.sequence)||result.sequence<1)throw Error("Video frame acknowledgment malformed");
       acknowledged++;errors=0;cooldownUntil=0;onState({live:true,frames:acknowledged,source:id,sequence:result.sequence});
       return true;
     }catch(e){
       if(stopped)return false;
       errors++;
       if(errors>=5)cooldownUntil=clock()+Math.min(20000,errors*1000);
       onError("Remote video confidence frame failed: "+e.message,errors);
       return false;
     }finally{busySources.delete(id);}
   }
   async function stop(){
     if(stopped)return;stopped=true;onState({live:false,frames:acknowledged});
     for(const controller of pending)controller.abort();
     try{
       const response=await boundedFetch("/api/studio25d/media/sessions/"+encodeURIComponent(session),{
         method:"DELETE",credentials:"same-origin"
       },1800);
       if(!response.ok)onError("Video publisher release HTTP "+response.status,errors);
     }catch(e){onError("Video publisher cleanup: "+e.message,errors);}
     for(const item of scratchBySource.values()){item.scratch.width=0;item.scratch.height=0;}
     scratchBySource.clear();
   }
   return {publish,stop,status:()=>({stopped,busy:busySources.size>0,acknowledged,errors})};
 }
 return {create};
});
