/* The SAME canonical PubCast vision switcher controls both production environments.
 * 2.5D shot sources are registered with CameraManager on a running PubCast host.
 * Offline static previews remain honest LOCAL ONLY; they do not fabricate a server link.
 * Node-testable: supply fetch, setInterval and clearInterval in create({ ... }).
 */
(function (root,factory) {
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DSharedSwitcher=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const SOURCE_PREFIX="p25d_";
 const encode=id=>encodeURIComponent(id);
 function sourceId(pkgId,shotId) {
   if(!/^[a-z][a-z0-9_]{0,39}$/.test(pkgId)||!/^[a-z][a-z0-9_]{0,39}$/.test(shotId))throw Error("Invalid studio camera ID");
   return SOURCE_PREFIX+pkgId+"_"+shotId;
 }
 function create(options={}) {
   const requestFetch=options.fetch||globalThis.fetch?.bind(globalThis);
   const schedule=options.setInterval||globalThis.setInterval?.bind(globalThis);
   const unschedule=options.clearInterval||globalThis.clearInterval?.bind(globalThis);
   const onState=typeof options.onState==="function"?options.onState:()=>{};
   const onError=typeof options.onError==="function"?options.onError:()=>{};
   let pkg=null,joined=false,timer=null,busy=false,last=null;
   function shotId(camera) {
     if(!pkg||!camera)return null;
     const found=pkg.cameras.find(c=>sourceId(pkg.id,c.id)===camera);
     return found?found.id:null;
   }
   function normalize(data) {
     if(!data||!Array.isArray(data.sources)||!("program" in data)||!("preview" in data))throw Error("Switcher state is malformed");
     return {program:shotId(data.program),preview:shotId(data.preview),
       remoteProgram:data.program&&!shotId(data.program)?data.program:null,
       remotePreview:data.preview&&!shotId(data.preview)?data.preview:null,
       transition:data.transition||{type:"cut",duration_ms:0},online:true};
   }
   async function request(path,method="GET",body) {
     if(!requestFetch)throw Error("Fetch is unavailable");
     const response=await requestFetch(path,{method,credentials:"same-origin",
       headers:body?{"Content-Type":"application/json"}:undefined,
       body:body?JSON.stringify(body):undefined,cache:method==="GET"?"no-store":undefined});
     if(!response.ok)throw Error("Shared switcher "+method+" "+path+" HTTP "+response.status);
     const result=await response.json();
     if(!result||typeof result!=="object")throw Error("Shared switcher returned invalid JSON");
     return result;
   }
   async function refresh() {
     if(!joined||busy)return null;
     busy=true;
     try {
       const data=await request("/api/switcher/state");
       const normalized=normalize(data);
       const signature=JSON.stringify(normalized);
       if(signature!==last){last=signature;onState(normalized);}
       return normalized;
     } catch(e) {
       onError("Shared video switcher unavailable: "+e.message);
       throw e;
     } finally {busy=false;}
   }
   async function attach(packageConfig) {
     detach();
     if(!packageConfig?.cameras?.length)throw Error("Production package has no cameras");
     pkg=packageConfig;
     // Read before writing. Missing backend or insufficient role means LOCAL ONLY,
     // never a fake connection. Registration is explicitly authorized by Start Production.
     let state;
     try{state=await request("/api/switcher/state");}
     catch(e){return {shared:false,reason:e.message};}
     if(!Array.isArray(state.sources))return {shared:false,reason:"Malformed shared switcher response"};
     const existing=new Set(state.sources.map(s=>s.id));
     try {
       for(const shot of pkg.cameras) {
         const id=sourceId(pkg.id,shot.id);
         if(existing.has(id))continue;
         await request("/api/cameras/register","POST",{
           source_id:id,name:pkg.title+" / "+shot.label,
           location:"studio25d",transport:"virtual",endpoint:"virtual://"+id,
           description:"2.5D television stage camera; frames rendered in active studio browser",
           position:[0,1.6,4],rotation:[0,0,0],fov:60,
           tags:["virtual","studio25d",pkg.id]
         });
       }
       // Activation selects BOTH sources in one canonical server transaction;
       // a failed Preview may not leave Program silently on the new stage.
       await request("/api/switcher/select","POST",{
         program:sourceId(pkg.id,pkg.cameras[0].id),
         preview:sourceId(pkg.id,pkg.cameras[1].id)
       });
     } catch(e){return {shared:false,reason:"Could not register/select production cameras: "+e.message};}
     joined=true;last=null;
     try{await refresh();}
     catch(e){joined=false;return {shared:false,reason:e.message};}
     if(schedule)timer=schedule(()=>refresh().catch(()=>{}),750);
     return {shared:true,sourceCount:pkg.cameras.length};
   }
   async function choosePreview(localShotId) {
     if(!joined)throw Error("Shared switcher is not connected");
     if(!pkg.cameras.some(c=>c.id===localShotId))throw Error("Unknown package camera");
     const response=await request("/api/switcher/preview/"+encode(sourceId(pkg.id,localShotId)),"POST");
     const next=normalize(response);last=JSON.stringify(next);onState(next);return next;
   }
   async function take(dissolve=false) {
     if(!joined)throw Error("Shared switcher is not connected");
     const response=dissolve
       ?await request("/api/switcher/transition","POST",{type:"dissolve",duration_ms:600})
       :await request("/api/switcher/cut","POST");
     const next=normalize(response);last=JSON.stringify(next);onState(next);return next;
   }
   function detach() {
     if(timer!=null&&unschedule)unschedule(timer);
     timer=null;joined=false;pkg=null;last=null;
   }
   return {attach,detach,refresh,choosePreview,take,connected:()=>joined,sourceId};
 }
 return {create,sourceId};
});
