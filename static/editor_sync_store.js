/* Offline-first post-production project + proxy blob persistence.
 * All write outcomes require IndexedDB transaction completion, never request
 * success alone. No remote media is silently fetched or cached.
 */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCastEditorSyncStore=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const DB="pubcast-editor-sync-v1",VERSION=1;
 function open(){
   return new Promise((resolve,reject)=>{
     if(typeof indexedDB==="undefined")return reject(Error("IndexedDB unavailable"));
     const q=indexedDB.open(DB,VERSION);
     q.onupgradeneeded=()=>{
       const db=q.result;
       if(!db.objectStoreNames.contains("projects"))db.createObjectStore("projects",{keyPath:"id"});
       if(!db.objectStoreNames.contains("media"))db.createObjectStore("media",{keyPath:"id"});
     };
     q.onsuccess=()=>resolve(q.result);
     q.onerror=()=>reject(q.error||Error("Editor database failed"));
     q.onblocked=()=>reject(Error("Editor database upgrade blocked by another open tab"));
   });
 }
 async function tx(mode,stores,work){
   const db=await open();
   try {
     return await new Promise((resolve,reject)=>{
       let tr;try{tr=db.transaction(stores,mode);}catch(e){reject(e);return;}
       let value;
       tr.oncomplete=()=>resolve(value);
       tr.onerror=()=>reject(tr.error||Error("Editor transaction failed"));
       tr.onabort=()=>reject(tr.error||Error("Editor transaction aborted"));
       try{work(tr,v=>{value=v;});}catch(e){try{tr.abort()}catch(_){}reject(e);}
     });
   }finally{db.close();}
 }
 function saveProject(project){
   if(!project||!project.id) return Promise.reject(Error("Invalid editor project"));
   return tx("readwrite",["projects"],tr=>tr.objectStore("projects").put(project));
 }
 function readProject(id){
   return tx("readonly",["projects"],(tr,done)=>{
     const q=tr.objectStore("projects").get(id);
     q.onsuccess=()=>done(q.result||null);
   });
 }
 function listProjects(){
   return tx("readonly",["projects"],(tr,done)=>{
     const q=tr.objectStore("projects").getAll();
     q.onsuccess=()=>done(q.result.sort((a,b)=>String(b.updatedAt).localeCompare(String(a.updatedAt))));
   });
 }
 function saveMedia(id,blob,name){
   if(typeof id!=="string"||!id||!(blob instanceof Blob))return Promise.reject(Error("Invalid proxy media"));
   if(blob.size>1024*1024*1024)return Promise.reject(Error("Proxy exceeds 1 GB per stored file"));
   return tx("readwrite",["media"],tr=>tr.objectStore("media").put({id,blob,name:String(name||id).slice(0,160)}));
 }
 function readMedia(id){
   return tx("readonly",["media"],(tr,done)=>{
     const q=tr.objectStore("media").get(id);
     q.onsuccess=()=>done(q.result||null);
   });
 }
 function deleteMedia(id){return tx("readwrite",["media"],tr=>tr.objectStore("media").delete(id));}
 function deleteProject(id){return tx("readwrite",["projects"],tr=>tr.objectStore("projects").delete(id));}
 return {open,saveProject,readProject,listProjects,saveMedia,readMedia,deleteMedia,deleteProject};
});
