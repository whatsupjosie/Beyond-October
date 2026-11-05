/* Bounded operations whose results cannot escape the UI/session generation. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastPoolAsync=api;})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
function cancelled(){return new DOMException("Operation no longer belongs to the active session","AbortError");}
class Scope{
 constructor(fetcher){this.version=0;this.controllers=new Set();this.fetch=fetcher||((...args)=>fetch(...args));}
 reset(){this.version++;for(const c of this.controllers)c.abort();return this.version;}
 current(version){return version===this.version;}
 async operation(action,timeout=3500,version=this.version){
  if(!this.current(version))throw cancelled();
  const controller=new AbortController();this.controllers.add(controller);
  let rejectAbort;
  const stopped=new Promise((_,reject)=>{rejectAbort=()=>reject(controller.signal.reason||cancelled());controller.signal.addEventListener("abort",rejectAbort,{once:true});});
  const timer=setTimeout(()=>controller.abort(new DOMException("Camera operation timed out","TimeoutError")),timeout);
  try{
   const result=await Promise.race([Promise.resolve().then(()=>{if(controller.signal.aborted||!this.current(version))throw cancelled();return action(controller.signal);}),stopped]);
   if(!this.current(version))throw cancelled();
   return result;
  }finally{clearTimeout(timer);controller.signal.removeEventListener("abort",rejectAbort);this.controllers.delete(controller);}
 }
 async request(url,init={},decode=r=>r.json(),timeout=3500,version=this.version){
  return this.operation(async signal=>{
   const response=await this.fetch(url,{...init,signal,credentials:"same-origin",cache:"no-store"});
   if(!response.ok){
    let detail="HTTP "+response.status;
    try{detail=(await response.json()).detail||detail;}catch(_){}
    const error=new Error((typeof detail==="string"?detail:JSON.stringify(detail)).slice(0,500));error.status=response.status;throw error;
   }
   return decode(response);
  },timeout,version);
 }
}
return {Scope,cancelled};
});
