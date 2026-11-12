/* PubCast 2.5D local session store. IndexedDB transactions are awaited through completion;
 * no false success if quota errors, aborts or unavailable browser storage occur. */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DStore=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const NAME="pubcast-25d-local", VERSION=3, LEASE_MS=15000;
 function open() {
  return new Promise((resolve,reject)=>{
   if(typeof indexedDB==="undefined")return reject(Error("IndexedDB is unavailable"));
   const q=indexedDB.open(NAME,VERSION);
   let blocked=false;
   q.onupgradeneeded=()=>{
     const db=q.result;
     if(!db.objectStoreNames.contains("sessions"))db.createObjectStore("sessions",{keyPath:"id"});
     if(!db.objectStoreNames.contains("media"))db.createObjectStore("media",{keyPath:"id"});
     if(!db.objectStoreNames.contains("archives"))db.createObjectStore("archives",{keyPath:"id"});
     const captures=db.objectStoreNames.contains("captures")?q.transaction.objectStore("captures"):db.createObjectStore("captures",{keyPath:"id"});
     if(!captures.indexNames.contains("state"))captures.createIndex("state","state");
     if(!db.objectStoreNames.contains("captureChunks"))db.createObjectStore("captureChunks",{keyPath:["takeId","index"]});
   };
   q.onerror=()=>reject(q.error||Error("Failed to open IndexedDB"));
   q.onblocked=()=>{blocked=true;reject(Error("IndexedDB open blocked by another tab"));};
   q.onsuccess=()=>{if(blocked){q.result.close();return;}q.result.onversionchange=()=>q.result.close();resolve(q.result);};
  });
 }
 async function transaction(mode,stores,work) {
  const db=await open();
  try{
   return await new Promise((resolve,reject)=>{
     let tx;
     try{
       // Request disk durability rather than acknowledging a relaxed write cache.
       try{tx=db.transaction(stores,mode,{durability:"strict"});}
       catch(e){if(e.name!=="TypeError")throw e;tx=db.transaction(stores,mode);}
     }catch(e){reject(e);return;}
     let value, error;
     tx.oncomplete=()=>resolve(value);
     tx.onerror=()=>{error=tx.error||Error("Database transaction failed");reject(error);};
     tx.onabort=()=>reject(error||tx.error||Error("Database transaction aborted"));
     const fail=e=>{error=e;try{tx.abort();}catch(_){}reject(e);};
     try{work(tx,(v)=>{value=v;},fail);}catch(e){fail(e);}
   });
  }finally{db.close();}
 }
 function save(session,blob,capture){
  if(!session||typeof session.id!=="string")return Promise.reject(Error("Invalid session record"));
  if(blob!=null&&!(blob instanceof Blob))return Promise.reject(Error("Invalid recording blob"));
  const stores=blob?["sessions","media"]:["sessions"];
  if(capture)stores.push("captures");
  return transaction("readwrite",stores,(tx,done,fail)=>{
   const write=()=>{
    tx.objectStore("sessions").put(session);
    if(blob)tx.objectStore("media").put({id:session.media?.id||session.id,sessionId:session.id,blob});
   };
   if(!capture){write();return;}
   const q=tx.objectStore("captures").get(capture.id);
   q.onsuccess=()=>{
    const row=q.result;
    if(!row||row.owner!==capture.owner||row.state==="complete")return fail(Error("Capture ownership changed; journal retained"));
    if(row.session.id!==session.id||session.media?.id!==row.id||!blob?.size)return fail(Error("Capture and saved take do not match"));
    write();row.state="complete";row.leaseUntil=0;row.completedAt=Date.now();
    tx.objectStore("captures").put(row);
   };
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
 function saveSource(session,source,blob,capture){
  if(!blob?.size||source.id!==capture.id||!source.parentTakeId)return Promise.reject(Error('Invalid source recording'));
  return transaction('readwrite',['sessions','media','captures'],(tx,done,fail)=>{
   owned(tx,capture.id,capture.owner,fail,row=>{
    if(row.session.id!==session.id||row.kind!=='audio-source')throw Error('Source capture does not match session');
    const q=tx.objectStore('sessions').get(session.id);
    q.onsuccess=()=>{
     const saved=q.result||session;
     saved.sourceTracks=[...(saved.sourceTracks||[]).filter(t=>t.id!==source.id),source];
     tx.objectStore('sessions').put(saved);
     tx.objectStore('media').put({id:source.id,sessionId:session.id,blob});
     row.state='complete';row.leaseUntil=0;row.completedAt=Date.now();tx.objectStore('captures').put(row);
    };
   });
  });
 }
 function list(){
  return transaction("readonly",["sessions"],(tx,done)=>{
    const q=tx.objectStore("sessions").getAll();
    q.onsuccess=()=>done(q.result.sort((a,b)=>b.startedAt.localeCompare(a.startedAt)));
  });
 }
 function archive(id){return transaction("readonly",["archives"],(tx,done)=>{const q=tx.objectStore("archives").get(id);q.onsuccess=()=>done(q.result||null);});}
 function saveArchive(record){return transaction("readwrite",["archives"],tx=>tx.objectStore("archives").put(record));}
 function owned(tx,id,owner,fail,work){
  const q=tx.objectStore("captures").get(id);
  q.onsuccess=()=>{
   const row=q.result;
   if(!row||row.owner!==owner||row.state==="complete")return fail(Error("Capture ownership changed; journal retained"));
   try{work(row);}catch(e){fail(e);}
  };
 }
 function beginCapture(record){
  return transaction("readwrite",["captures"],tx=>tx.objectStore("captures").add({...record,
   state:"capturing",nextIndex:0,bytes:0,durationMs:0,leaseUntil:Date.now()+LEASE_MS}));
 }
 function renewCapture(id,owner){
  return transaction("readwrite",["captures"],(tx,done,fail)=>owned(tx,id,owner,fail,row=>{
   row.leaseUntil=Date.now()+LEASE_MS;tx.objectStore("captures").put(row);
  }));
 }
 function appendCapture(id,owner,piece,session,timing){
  return transaction("readwrite",["captures","captureChunks"],(tx,done,fail)=>owned(tx,id,owner,fail,row=>{
   if(piece.index!==row.nextIndex||!(piece.blob instanceof Blob)||!piece.blob.size||!/^[a-f0-9]{64}$/.test(piece.sha256))throw Error("Invalid capture chunk sequence or proof");
   if(session.id!==row.session.id)throw Error("Capture and session do not match");
   tx.objectStore("captureChunks").add({...piece,takeId:id});
   row.nextIndex++;row.bytes+=piece.blob.size;row.durationMs=Math.max(row.durationMs,piece.durationMs);
   row.lastCheckpointAt=Date.now();row.leaseUntil=Date.now()+LEASE_MS;row.session=session;
   if(timing){row.startedAt=timing.startedAt;row.offsetMs=timing.offsetMs;}
   tx.objectStore("captures").put(row);done(row);
  }));
 }
 function releaseCapture(id,owner){
  return transaction("readwrite",["captures"],(tx,done,fail)=>owned(tx,id,owner,fail,row=>{
   row.state="interrupted";row.leaseUntil=0;tx.objectStore("captures").put(row);
  }));
 }
 function listCaptures(){
  return transaction("readonly",["captures"],(tx,done)=>{
   const index=tx.objectStore("captures").index("state"),rows=[];let waiting=3;
   for(const state of ["capturing","interrupted","recovering"]){
    const q=index.getAll(state);q.onsuccess=()=>{rows.push(...q.result);if(!--waiting)done(rows);};
   }
  });
 }
 function claimCapture(id,owner){
  return transaction("readwrite",["captures"],(tx,done,fail)=>{
   const q=tx.objectStore("captures").get(id);
   q.onsuccess=()=>{
    const row=q.result;
    if(!row||row.state==="complete")return fail(Error("Capture already recovered or unavailable"));
    if(row.leaseUntil>Date.now())return fail(Error("This take is still active in another studio tab. Wait for it to stop or disconnect."));
    row.owner=owner;row.leaseUntil=Date.now()+LEASE_MS;row.state="recovering";
    tx.objectStore("captures").put(row);done(row);
   };
  });
 }
 function readCapture(id){
  return transaction("readonly",["captures","captureChunks"],(tx,done)=>{
   const q=tx.objectStore("captures").get(id);
   q.onsuccess=()=>{
    const capture=q.result;if(!capture){done(null);return;}
    const c=tx.objectStore("captureChunks").getAll(IDBKeyRange.bound([id,0],[id,Number.MAX_SAFE_INTEGER]));
    c.onsuccess=()=>done({capture,chunks:c.result});
   };
  });
 }
 return {open,save,saveSource,read,list,archive,saveArchive,beginCapture,renewCapture,appendCapture,
  releaseCapture,listCaptures,claimCapture,readCapture,LEASE_MS};
});
