/* Original encoded takes: bounded chunks, durable ACKs, resumable server save.
 * Local session/media stores are never replaced or deleted by an upload.
 */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCast25DArchive=api;})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
const CHUNK=256*1024,MAX=2*1024**3,SEED="pubcast-encoded-take/1";
const hex=b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,"0")).join("");
const unhex=s=>Uint8Array.from(s.match(/../g)||[],v=>parseInt(v,16));
function create(options={}){
 const store=options.store||globalThis.PubCast25DStore,Async=options.Async||globalThis.PubCastPoolAsync;
 const fetcher=options.fetch||((...args)=>fetch(...args));
 const sessionKey=options.sessionKey||(()=>{try{return globalThis.sessionStorage?.getItem("pubcast_token")??null;}catch(_){return null;}});
 let identityKey=null,viewJob=null;
 const work=new Async.Scope((...args)=>{if(identityKey!==null&&sessionKey()!==identityKey)throw Async.cancelled();return fetcher(...args);}),view=new Async.Scope(fetcher);
 const crypto=options.crypto||globalThis.crypto,onState=options.onState||(()=>{});
 let busy=false;
 const request=(scope,path,method="GET",body,headers={})=>scope.request("/api/studio25d/recordings"+path,{method,headers:{...(body&&!(body instanceof Blob)?{"Content-Type":"application/json"}:{}),...headers},body:body instanceof Blob?body:body?JSON.stringify(body):undefined},r=>r.json(),25000);
 const hash=async data=>hex(await crypto.subtle.digest("SHA-256",data));
 async function chain(previous,digest,size){const bytes=new Uint8Array(72);bytes.set(unhex(previous));bytes.set(unhex(digest),32);new DataView(bytes.buffer).setUint32(68,size);return hash(bytes);}
 async function save(item){
  if(busy||viewJob)throw Error("Another server transfer is in progress");
  if(!item?.blob?.size||!item.take?.id)throw Error("Select a locally saved take first");
  if(item.blob.size>MAX)throw Error("This server-save path accepts takes up to 2 GiB; your local take is retained");
  if(!crypto?.subtle)throw Error("Server saving requires HTTPS or localhost for media integrity checks");
  busy=true;work.reset();identityKey=sessionKey();const ticket=work.version;let record,authorizedRecord=false;
  const current=()=>{if(!work.current(ticket)||(identityKey!==null&&sessionKey()!==identityKey))throw Async.cancelled();};
  try{
   onState({state:"checking",message:"Checking local take; local copy retained"});
   const identity=await work.request("/api/auth/verify",{},r=>r.json(),5000,ticket);current();
   if(!identity.valid||!identity.username)throw Error("Sign in before saving a take on this server");
   record=await store.archive(item.take.id);current();
   if(record&&record.owner!==identity.username)throw Error("This take's pending save belongs to another account");
   authorizedRecord=true;
   const digests=[],chains=[await work.operation(()=>hash(new TextEncoder().encode(SEED)),5000,ticket)];current();
   for(let offset=0;offset<item.blob.size;offset+=CHUNK){
    const part=item.blob.slice(offset,offset+CHUNK),bytes=await work.operation(()=>part.arrayBuffer(),5000,ticket);
    const digest=await work.operation(()=>hash(bytes),5000,ticket);current();
    digests.push(digest);chains.push(await work.operation(()=>chain(chains.at(-1),digest,part.size),5000,ticket));current();
   }
   if(!record){
    const session=JSON.parse(JSON.stringify(item.session));
    const spec={take_id:item.take.id,production_id:session.id,source_id:item.sourceId,
     mime:item.blob.type,bytes:item.blob.size,chain:chains.at(-1),width:item.blob.type.startsWith('audio/')?0:1280,height:item.blob.type.startsWith('audio/')?0:720,
     duration_ms:Math.max(1,Math.round(item.take.durationMs)),capture_incomplete:!!item.take.incomplete,manifest:session};
    if(new TextEncoder().encode(JSON.stringify(spec)).length>128*1024)throw Error("Session manifest exceeds server-save limit; export the full local manifest");
    record={id:item.take.id,owner:identity.username,sessionId:session.id,spec,state:"uploading"};
    await store.saveArchive(record);current();
   }
   if(record.spec.bytes!==item.blob.size||record.spec.chain!==chains.at(-1))throw Error("The local take differs from the pending upload; original server reservation retained");
   let ack=await request(work,"","POST",record.spec);current();
   function valid(value){
    if(!/^enc_[a-f0-9]{40}$/.test(value?.id)||value.owner!==record.owner||value.take_id!==record.id||value.expected_bytes!==item.blob.size||value.chunk_bytes!==CHUNK||!Number.isInteger(value.next_index)||value.next_index<0||value.next_index>digests.length||value.received_bytes!==Math.min(item.blob.size,value.next_index*CHUNK)||value.chain!==chains[value.next_index])throw Error("Server save acknowledgement did not match the local take");
   }
   valid(ack);record.serverId=ack.id;await store.saveArchive(record);current();
   for(let index=ack.next_index;index<digests.length;index++){
    onState({state:"uploading",bytes:ack.received_bytes,total:item.blob.size,message:`Saving on server: ${ack.received_bytes} / ${item.blob.size} bytes confirmed`});
    ack=await request(work,"/"+record.serverId+"/chunks/"+index,"PUT",item.blob.slice(index*CHUNK,(index+1)*CHUNK),{"Content-Type":"application/octet-stream","X-Chunk-SHA256":digests[index]});current();valid(ack);
    if(ack.next_index!==index+1)throw Error("Server did not commit exactly the uploaded chunk");
   }
   onState({state:"validating",message:"Validating saved media; local copy retained"});
   ack=await request(work,"/"+record.serverId+"/complete","POST");current();valid(ack);
   if(ack.state!=="complete"||!/^[a-f0-9]{64}$/.test(ack.sha256))throw Error("Server did not confirm a validated completed video");
   record={...record,state:"complete",sha256:ack.sha256};await store.saveArchive(record);current();
   onState({state:"complete",...ack,message:`Saved on server: ${ack.received_bytes} bytes verified. Local copy retained.`});return ack;
  }catch(error){
   if(record&&authorizedRecord){try{await store.saveArchive({...record,state:"pending",error:String(error.message).slice(0,200)});}catch(_){} }
   if(work.current(ticket))onState({state:"pending",message:"Server save unconfirmed. Local take retained; retry to resume. "+error.message});
   throw error;
  }finally{busy=false;identityKey=null;}
 }
 function cancelView(){view.reset();viewJob=null;}
 function cancel(){work.reset();cancelView();onState({state:"pending",message:"Server transfer paused. Local takes and confirmed server chunks are retained."});}
 function beginView(){if(busy)throw Error("Pause the server save before opening another transfer");view.reset();const job={ticket:view.version,key:sessionKey()};viewJob=job;return job;}
 function checkView(job){if(!view.current(job.ticket)||sessionKey()!==job.key)throw Async.cancelled();}
 function endView(job){if(viewJob===job)viewJob=null;}
 async function list(){const job=beginView();try{const data=await request(view,"");checkView(job);return data.takes;}finally{endView(job);}}
 async function transfer(path,method,job,expectedBytes){
  const controller=new AbortController();let reader;
  const bounded=action=>view.operation(async signal=>{
   const abort=()=>controller.abort(signal.reason);signal.addEventListener("abort",abort,{once:true});
   try{checkView(job);return await action();}finally{signal.removeEventListener("abort",abort);}
  },options.readTimeout||20000,job.ticket);
  onState({state:"downloading",message:"Downloading saved source; transfer can be paused"});
  try{
   const response=await view.operation(async signal=>{
    const abort=()=>controller.abort(signal.reason);signal.addEventListener("abort",abort,{once:true});
    try{checkView(job);return await fetcher(path,{method,signal:controller.signal,credentials:"same-origin",cache:"no-store"});}
    finally{signal.removeEventListener("abort",abort);}
   },120000,job.ticket);checkView(job);
   if(!response.ok){const error=new Error("Source transfer HTTP "+response.status);error.status=response.status;throw error;}
   // Fetch exposes decoded bytes: a gzip Content-Length counts different bytes.
   const encoding=response.headers.get("Content-Encoding");
   const declared=encoding&&encoding!=="identity"?null:response.headers.get("Content-Length"),limit=MAX+4*1024*1024;
   if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>limit||expectedBytes!==undefined&&Number(declared)!==expectedBytes))throw Error("Source transfer length does not match its receipt");
   if(!response.body?.getReader)throw Error("Streaming downloads are unavailable in this browser");
   reader=response.body.getReader();const blobs=[];let parts=[],buffered=0,total=0,lastReport=0;
   for(;;){
    const result=await bounded(()=>reader.read());checkView(job);if(result.done)break;
    total+=result.value.byteLength;buffered+=result.value.byteLength;
    if(total>limit||expectedBytes!==undefined&&total>expectedBytes)throw Error("Source exceeds its transfer budget");
    parts.push(result.value);
    if(buffered>=4*1024*1024){blobs.push(new Blob(parts));parts=[];buffered=0;}
    const now=globalThis.performance?.now?.()||Date.now();
    if(now-lastReport>250){onState({state:"downloading",message:`Downloading saved source: ${total} bytes received`});lastReport=now;}
   }
   if(declared!==null&&total!==Number(declared)||expectedBytes!==undefined&&total!==expectedBytes)throw Error("Source download ended before all bytes arrived");
   if(parts.length)blobs.push(new Blob(parts));
   return {blob:new Blob(blobs,{type:response.headers.get("Content-Type")||"application/octet-stream"}),sha256:response.headers.get("X-Source-SHA256")};
  }finally{controller.abort();if(reader)try{Promise.resolve(reader.cancel()).catch(()=>{});}catch(_){} }
 }
 async function download(id){
  if(!/^enc_[a-f0-9]{40}$/.test(id))throw Error("Invalid saved take");const job=beginView(),ticket=job.ticket;
  try{
  const expected=await request(view,"/"+id);
  checkView(job);
  const result=await transfer("/api/studio25d/recordings/"+id+"/media","GET",job,expected.expected_bytes);
  if(expected.state!=="complete"||result.blob.size!==expected.expected_bytes||result.sha256!==expected.sha256)throw Error("Saved source response does not match its receipt");
  let proof=await view.operation(()=>hash(new TextEncoder().encode(SEED)),5000,ticket);
  for(let offset=0;offset<result.blob.size;offset+=CHUNK){
   const part=result.blob.slice(offset,offset+CHUNK),bytes=await view.operation(()=>part.arrayBuffer(),5000,ticket);
   const digest=await view.operation(()=>hash(bytes),5000,ticket);
   proof=await view.operation(()=>chain(proof,digest,part.size),5000,ticket);
   checkView(job);
  }
  if(proof!==expected.chain)throw Error("Downloaded source failed its original chunk integrity proof");
  return result;
  }finally{if(viewJob===job)onState({state:"idle",message:"Server transfer finished or paused; saved source retained."});endView(job);}
 }
 async function bundle(id){if(!/^enc_[a-f0-9]{40}$/.test(id))throw Error("Invalid saved take");const job=beginView();try{const result=await transfer("/api/studio25d/recordings/"+id+"/bundle","POST",job);checkView(job);return result.blob;}finally{if(viewJob===job)onState({state:"idle",message:"Source bundle transfer finished or paused; saved source retained."});endView(job);}}
 async function abandon(id){if(!/^enc_[a-f0-9]{40}$/.test(id))throw Error("Invalid saved take");return request(view,"/"+id+"/abandon","POST");}
 function close(){work.reset();cancelView();}
 return {save,cancel,list,download,bundle,abandon,close,cancelView,status:()=>({busy,viewBusy:!!viewJob||view.controllers.size>0})};
}
return {create,CHUNK,MAX};
});
