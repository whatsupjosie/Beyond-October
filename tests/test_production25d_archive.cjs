const test=require('node:test'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const Archive=require('../static/production25d_archive.js'),Async=require('../static/camera_pool_async.js');
const hex=b=>Buffer.from(b).toString('hex');
const digest=async b=>hex(await webcrypto.subtle.digest('SHA-256',b));
function harness({lost=false,forged=false,identity='producer'}={}){
 const records=new Map(),calls=[];let saved=null,fail=lost;
 const store={archive:async id=>records.has(id)?structuredClone(records.get(id)):null,saveArchive:async r=>records.set(r.id,structuredClone(r))};
 const fetch=async(url,init={})=>{
  calls.push(url);
  if(url==='/api/auth/verify')return Response.json({valid:true,username:identity});
  if(url==='/api/studio25d/recordings'){
   const spec=JSON.parse(init.body);
   if(saved)assert.deepEqual(spec,saved.spec);
   else saved={spec,id:'enc_'+'a'.repeat(40),owner:identity,take_id:spec.take_id,expected_bytes:spec.bytes,received_bytes:0,next_index:0,chunk_bytes:Archive.CHUNK,chain:await digest(new TextEncoder().encode('pubcast-encoded-take/1')),state:'uploading'};
   return Response.json({...saved,spec:undefined,owner:forged?'someone-else':identity});
  }
  if(url.includes('/chunks/')){
   const index=Number(url.split('/').at(-1));assert.equal(index,saved.next_index);
   const bytes=await init.body.arrayBuffer(),sha=await digest(bytes);assert.equal(sha,init.headers['X-Chunk-SHA256']);
   const chain=new Uint8Array(72);chain.set(Buffer.from(saved.chain,'hex'));chain.set(Buffer.from(sha,'hex'),32);new DataView(chain.buffer).setUint32(68,bytes.byteLength);
   saved.chain=await digest(chain);saved.received_bytes+=bytes.byteLength;saved.next_index++;
   if(fail){fail=false;throw new TypeError('Connection lost after commit');}
   return Response.json({...saved,spec:undefined});
  }
  assert.ok(url.endsWith('/complete'));
  assert.equal(saved.chain,saved.spec.chain);saved.state='complete';saved.sha256='b'.repeat(64);
  return Response.json({...saved,spec:undefined});
 };
 const status=[];const archive=Archive.create({store,Async,fetch,crypto:webcrypto,onState:s=>status.push(s)});
 const item={session:{id:'pubcast25d-production-test',packageId:'news',events:[]},take:{id:'pubcast25d-archive-take-001',durationMs:1500},blob:new Blob([new Uint8Array(Archive.CHUNK*2+123).fill(42)],{type:'video/webm'}),sourceId:'p25d_news_wide'};
 return {archive,item,records,calls,status,store};
}
test('a lost chunk ACK resumes from durable server progress without resending confirmed bytes',async()=>{
 const h=harness({lost:true});await assert.rejects(h.archive.save(h.item),/lost after commit/);
 assert.equal(h.records.get(h.item.take.id).state,'pending');
 assert.equal(h.status.some(s=>s.state==='complete'),false);
 h.item.session.events.push({type:'production.stop'}); // Retry must retain original manifest.
 const result=await h.archive.save(h.item);assert.equal(result.state,'complete');
 assert.equal(h.calls.filter(p=>p.endsWith('/chunks/0')).length,1);
 assert.equal(h.calls.filter(p=>p.includes('/chunks/')).length,3);
 assert.equal(h.records.get(h.item.take.id).state,'complete');h.archive.close();
});
test('a forged owner acknowledgement never turns into a saved indicator',async()=>{
 const h=harness({forged:true});await assert.rejects(h.archive.save(h.item),/acknowledgement/);
 assert.equal(h.status.some(s=>s.state==='complete'),false);assert.equal(h.calls.filter(p=>p.includes('/chunks/')).length,0);h.archive.close();
});
test('another account cannot resume a previous owner pending upload',async()=>{
 const h=harness();h.records.set(h.item.take.id,{id:h.item.take.id,owner:'another-owner'});
 await assert.rejects(h.archive.save(h.item),/another account/);
 assert.deepEqual(h.records.get(h.item.take.id),{id:h.item.take.id,owner:'another-owner'});
 assert.deepEqual(h.calls,['/api/auth/verify']);h.archive.close();
});
test('pausing an unfinished server request releases busy state and discards late replies',async()=>{
 let held,release;
 const h=harness();
 const archive=Archive.create({store:h.store,Async,crypto:webcrypto,fetch:async url=>{
  if(url==='/api/auth/verify')return Response.json({valid:true,username:'producer'});
  held=true;return new Promise(resolve=>{release=()=>resolve(Response.json({id:'enc_'+'a'.repeat(40)}));});
 }});
 const pending=archive.save(h.item);
 while(!held)await new Promise(r=>setTimeout(r,1));
 archive.cancel();await assert.rejects(pending,e=>e.name==='AbortError');release();
 assert.equal(archive.status().busy,false);assert.equal(h.records.get(h.item.take.id).state,'pending');archive.close();
});
test('pausing while local hashing is stuck releases the save without any upload',async()=>{
 const h=harness();let hashing=false;
 const archive=Archive.create({store:h.store,Async,crypto:{subtle:{digest:()=>{hashing=true;return new Promise(()=>{});}}},fetch:async()=>Response.json({valid:true,username:'producer'})});
 const pending=archive.save(h.item);while(!hashing)await new Promise(r=>setTimeout(r,1));
 archive.cancel();await assert.rejects(pending,e=>e.name==='AbortError');assert.equal(archive.status().busy,false);archive.close();
});
test('an account change stops the save before private metadata is posted',async()=>{
 const h=harness();let key='first-account',posted=false;
 const archive=Archive.create({store:h.store,Async,crypto:webcrypto,sessionKey:()=>key,fetch:async url=>{
  if(url==='/api/auth/verify'){key='second-account';return Response.json({valid:true,username:'producer'});}
  posted=true;throw Error('Unexpected private post');
 }});
 await assert.rejects(archive.save(h.item),e=>e.name==='AbortError');assert.equal(posted,false);assert.equal(archive.status().busy,false);archive.close();
});
async function downloadHarness({stall=false,corrupt=false,gzip=false}={}){
 const bytes=new TextEncoder().encode('bounded-stream-source-bytes-12345'),sha=await digest(bytes);
 const prefix=await digest(new TextEncoder().encode('pubcast-encoded-take/1'));
 const chain=new Uint8Array(72);chain.set(Buffer.from(prefix,'hex'));chain.set(Buffer.from(sha,'hex'),32);new DataView(chain.buffer).setUint32(68,bytes.length);
 const proof=await digest(chain);let cancelled=false;
 const archive=Archive.create({Async,crypto:webcrypto,readTimeout:80,fetch:async url=>{
  if(!url.endsWith('/media'))return Response.json({state:'complete',expected_bytes:bytes.length,sha256:sha,chain:proof});
  let offset=0;
  const body=new ReadableStream({async pull(controller){
   if(stall)return new Promise(()=>{});
   await new Promise(r=>setTimeout(r,20));if(cancelled)return;
   if(offset>=bytes.length){controller.close();return;}
   const chunk=bytes.slice(offset,offset+3);if(corrupt&&offset===0)chunk[0]^=1;
   offset+=chunk.length;controller.enqueue(chunk);
  },cancel(){cancelled=true;}});
  return new Response(body,{headers:{'Content-Type':'video/webm','Content-Length':gzip?'1':String(bytes.length),'X-Source-SHA256':sha,...(gzip?{'Content-Encoding':'gzip'}:{})}});
 }});
 return {archive,bytes};
}
test('a progressing stream outlives a read deadline and gzip transport keeps the original byte proof',async()=>{
 const h=await downloadHarness({gzip:true});const result=await h.archive.download('enc_'+'a'.repeat(40));
 assert.deepEqual(new Uint8Array(await result.blob.arrayBuffer()),h.bytes);assert.equal(h.archive.status().viewBusy,false);h.archive.close();
});
test('a stalled source body times out and releases the view job',async()=>{
 const h=await downloadHarness({stall:true});await assert.rejects(h.archive.download('enc_'+'a'.repeat(40)),e=>e.name==='TimeoutError');
 assert.equal(h.archive.status().viewBusy,false);h.archive.close();
});
test('equal-sized corrupted source bytes fail the original download proof',async()=>{
 const h=await downloadHarness({corrupt:true});await assert.rejects(h.archive.download('enc_'+'a'.repeat(40)),/integrity proof/);h.archive.close();
});
