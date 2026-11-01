/* PubCast 2.5D local session store. IndexedDB transactions are awaited through completion;
 * no false success if quota errors, aborts or unavailable browser storage occur. */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DStore=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const NAME="pubcast-25d-local", VERSION=1;
 function open() {
  return new Promise((resolve,reject)=>{
   if(typeof indexedDB==="undefined")return reject(Error("IndexedDB is unavailable"));
   const q=indexedDB.open(NAME,VERSION);
   q.onupgradeneeded=()=>{
     const db=q.result;
     if(!db.objectStoreNames.contains("sessions"))db.createObjectStore("sessions",{keyPath:"id"});
     if(!db.objectStoreNames.contains("media"))db.createObjectStore("media",{keyPath:"id"});
   };
   q.onerror=()=>reject(q.error||Error("Failed to open IndexedDB"));
   q.onblocked=()=>reject(Error("IndexedDB open blocked by another tab"));
   q.onsuccess=()=>resolve(q.result);
  });
 }
 async function transaction(mode,stores,work) {
  const db=await open();
  try{
   return await new Promise((resolve,reject)=>{
     let tx;
     try{tx=db.transaction(stores,mode)}catch(e){reject(e);return;}
     let value, error;
     tx.oncomplete=()=>resolve(value);
     tx.onerror=()=>{error=tx.error||Error("Database transaction failed");reject(error);};
     tx.onabort=()=>reject(error||tx.error||Error("Database transaction aborted"));
     try{work(tx,(v)=>{value=v;});}catch(e){error=e;try{tx.abort();}catch(_){}reject(e);}
   });
  }finally{db.close();}
 }
 function save(session,blob){
  if(!session||typeof session.id!=="string")return Promise.reject(Error("Invalid session record"));
  if(blob!=null&&!(blob instanceof Blob))return Promise.reject(Error("Invalid recording blob"));
  return transaction("readwrite",blob?["sessions","media"]:["sessions"],(tx)=>{
    tx.objectStore("sessions").put(session);
    if(blob)tx.objectStore("media").put({id:session.media?.id||session.id,sessionId:session.id,blob});
  });
 }
 function read(id,takeId){
  return transaction("readonly",["sessions","media"],(tx,done)=>{
    const result={session:null,blob:null};
    const q=tx.objectStore("sessions").get(id);
    q.onsuccess=()=>{
      result.session=q.result||null;
      const m=tx.objectStore("media").get(takeId||result.session?.media?.id||id);
      m.onsuccess=()=>{result.blob=m.result?.blob||null;done(result)};
    };
  });
 }
 function list(){
  return transaction("readonly",["sessions"],(tx,done)=>{
    const q=tx.objectStore("sessions").getAll();
    q.onsuccess=()=>done(q.result.sort((a,b)=>b.startedAt.localeCompare(a.startedAt)));
  });
 }
 return {open,save,read,list};
});
