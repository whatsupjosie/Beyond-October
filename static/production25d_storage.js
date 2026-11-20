/* PubCast 2.5D local session store. IndexedDB transactions are awaited through completion;
 * no false success if quota errors, aborts or unavailable browser storage occur. */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DStore=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const NAME="pubcast-25d-local", VERSION=2;
 function open() {
  return new Promise((resolve,reject)=>{
   if(typeof indexedDB==="undefined")return reject(Error("IndexedDB is unavailable"));
   const q=indexedDB.open(NAME,VERSION);
   q.onupgradeneeded=()=>{
     const db=q.result;
     if(!db.objectStoreNames.contains("sessions"))db.createObjectStore("sessions",{keyPath:"id"});
     if(!db.objectStoreNames.contains("chunks"))db.createObjectStore("chunks",{keyPath:["takeId","sequence"]});
     if(!db.objectStoreNames.contains("journals"))db.createObjectStore("journals",{keyPath:"id"}).createIndex("sessionId","sessionId");
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
 function chunkRange(id){
  return IDBKeyRange.bound([id,0],[id,Number.MAX_SAFE_INTEGER]);
 }
 function appendChunk(take,sequence,blob){
  return transaction("readwrite",["chunks","journals"],tx=>{
    tx.objectStore("chunks").add({takeId:take.id,sequence,blob});
    tx.objectStore("journals").put(take);
  });
 }
 function chunkBlob(tx,id,mime,done){
  const q=tx.objectStore("chunks").getAll(chunkRange(id));
  q.onsuccess=()=>done(new Blob(q.result.map(part=>part.blob),{type:mime}));
 }
 function readChunks(id,mime){
  return transaction("readonly",["chunks"],(tx,done)=>chunkBlob(tx,id,mime,done));
 }
 function save(session,blob,chunked=false){
  if(!session||typeof session.id!=="string")return Promise.reject(Error("Invalid session record"));
  if(blob!=null&&!(blob instanceof Blob))return Promise.reject(Error("Invalid recording blob"));
  return transaction("readwrite",blob?["sessions","media","journals","chunks"]:["sessions"],tx=>{
    tx.objectStore("sessions").put(session);
    if(!blob)return;
    const id=session.media?.id||session.id;
    const media={id,sessionId:session.id};
    if(chunked){media.chunked=true;media.mime=blob.type;}
    else{media.blob=blob;tx.objectStore("chunks").delete(chunkRange(id));}
    tx.objectStore("media").put(media);
    tx.objectStore("journals").delete(id);
  });
 }
 function withJournals(session,journals){
  if(!session||!journals.length)return session;
  const takes=session.recordings?.slice()||(session.media?[{id:session.id,...session.media}]:[]);
  for(const take of journals.sort((a,b)=>a.startedAt.localeCompare(b.startedAt))){
    if(!takes.some(item=>item.id===take.id))takes.push(take);
  }
  return {...session,recordings:takes,media:takes[takes.length-1]};
 }
 function read(id,takeId){
  return transaction("readonly",["sessions","media","journals","chunks"],(tx,done)=>{
    const q=tx.objectStore("sessions").get(id);
    q.onsuccess=()=>{
      const drafts=tx.objectStore("journals").index("sessionId").getAll(id);
      drafts.onsuccess=()=>{
        const session=withJournals(q.result||null,drafts.result);
        const key=takeId||session?.media?.id||id;
        const m=tx.objectStore("media").get(key);
        m.onsuccess=()=>{
          const draft=drafts.result.find(item=>item.id===key);
          if(m.result?.chunked||draft)chunkBlob(tx,key,m.result?.mime||draft.mime,blob=>done({session,blob}));
          else done({session,blob:m.result?.blob||null});
        };
      };
    };
  });
 }
 function list(){
  return transaction("readonly",["sessions","journals"],(tx,done)=>{
    const q=tx.objectStore("sessions").getAll();
    q.onsuccess=()=>{
      const drafts=tx.objectStore("journals").getAll();
      drafts.onsuccess=()=>done(q.result.map(s=>withJournals(s,drafts.result.filter(d=>d.sessionId===s.id)))
        .sort((a,b)=>b.startedAt.localeCompare(a.startedAt)));
    };
  });
 }
 return {open,save,read,list,appendChunk,readChunks};
});
