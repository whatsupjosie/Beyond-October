/* Ordered local capture journal. Only uncommitted chunks remain in the writer.
 * Backpressure stops capture; it never drops encoded chunks to keep recording. */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DCapture=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 function id(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");}
 async function digest(blob){
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",await blob.arrayBuffer())),b=>b.toString(16).padStart(2,"0")).join("");
 }
 function create({store,id,owner,session,timing,onProgress=()=>{},onFailure=()=>{},maxPendingBytes=8*1024*1024,maxPendingChunks=8}){
  let pending=[],pendingBytes=0,nextIndex=0,durableBytes=0,error=null,task=null,notified=false;
  const fail=e=>{error=error||e;if(!notified){notified=true;onFailure(error);}};
  function pump(){
   if(task||error)return;
   task=(async()=>{
    while(pending.length&&!error){
     const piece=pending[0];
     try{
      piece.sha256=await digest(piece.blob);
      await store.appendCapture(id,owner,piece,structuredClone(session),timing&&{startedAt:timing.startedAt,offsetMs:timing.offsetMs});
      pending.shift();pendingBytes-=piece.blob.size;durableBytes+=piece.blob.size;
      onProgress({bytes:durableBytes,chunks:piece.index+1,pendingBytes,durationMs:piece.durationMs});
     }catch(e){fail(e);}
    }
   })().finally(()=>{task=null;});
  }
  function push(blob,durationMs){
   if(!blob?.size)return;
   pending.push({index:nextIndex++,blob,durationMs});pendingBytes+=blob.size;
   // The event crossing the threshold and the final stop event are retained.
   // Browser timeslices are advisory: a delayed event can itself be large.
   if(pendingBytes>maxPendingBytes||pending.length>maxPendingChunks)
    fail(Error("Local saving cannot keep up. Recording stopped to preserve available media."));
   pump();
  }
  async function settle(){if(task)await task;return {error,pending:pending.slice(),bytes:durableBytes,pendingBytes};}
  return {push,settle,status:()=>({bytes:durableBytes,chunks:nextIndex-pending.length,pendingBytes,pendingChunks:pending.length,error})};
 }
 async function assemble(record,pending=[]){
  if(!record)throw Error("Capture journal unavailable");
  const {capture,chunks}=record;
  if(chunks.length!==capture.nextIndex)throw Error("Capture journal has missing chunks; originals retained");
  let bytes=0;const parts=[];
  for(let i=0;i<chunks.length;i++){
   const piece=chunks[i];
   if(piece.index!==i||piece.takeId!==capture.id||!(piece.blob instanceof Blob)||
      await digest(piece.blob)!==piece.sha256)throw Error("Capture chunk integrity failed; originals retained");
   bytes+=piece.blob.size;parts.push(piece.blob);
  }
  if(bytes!==capture.bytes)throw Error("Capture byte count mismatch; originals retained");
  for(const [i,piece] of pending.entries()){
   if(piece.index!==chunks.length+i)throw Error("Unsaved capture chunk sequence mismatch");
   parts.push(piece.blob);
  }
  const blob=new Blob(parts,{type:capture.mime});
  if(!blob.size)throw Error("No encoded media reached this take's journal");
  return blob;
 }
 return {create,assemble,digest,id};
});
