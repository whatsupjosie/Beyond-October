const test=require('node:test'),assert=require('node:assert/strict');
global.crypto=require('node:crypto').webcrypto;
const Capture=require('../static/production25d_capture.js');
test('capture writer preserves byte order and releases committed chunks',async()=>{
 const pieces=[],progress=[];
 const writer=Capture.create({store:{appendCapture:async(id,owner,piece)=>pieces.push({...piece,takeId:id})},id:'take',owner:'page',session:{id:'session'},onProgress:p=>progress.push(p)});
 writer.push(new Blob(['first']),1000);writer.push(new Blob(['second']),2000);
 const result=await writer.settle();assert.equal(result.error,null);assert.deepEqual(result.pending,[]);
 assert.equal(writer.status().pendingBytes,0);assert.equal(writer.status().bytes,11);
 const blob=await Capture.assemble({capture:{id:'take',nextIndex:2,bytes:11,mime:'video/webm'},chunks:pieces});
 assert.equal(await blob.text(),'firstsecond');assert.equal(progress.length,2);
});
test('failed disk writes retain the exact uncommitted suffix for a recovery download',async()=>{
 const pieces=[],errors=[];
 const writer=Capture.create({store:{appendCapture:async(id,owner,piece)=>{if(piece.index===1)throw Error('disk full');pieces.push({...piece,takeId:id});}},id:'take',owner:'page',session:{},onFailure:e=>errors.push(e.message)});
 writer.push(new Blob(['a']),1000);writer.push(new Blob(['b']),2000);writer.push(new Blob(['c']),3000);
 const result=await writer.settle();assert.equal(result.error.message,'disk full');assert.equal(result.pendingBytes,2);
 const blob=await Capture.assemble({capture:{id:'take',nextIndex:1,bytes:1,mime:'video/webm'},chunks:pieces},result.pending);
 assert.equal(await blob.text(),'abc');assert.deepEqual(errors,['disk full']);
});
test('backpressure stops once without dropping the threshold-crossing or stop chunk',async()=>{
 let release,entered=false;const errors=[];
 const writer=Capture.create({store:{appendCapture:async()=>{entered=true;await new Promise(r=>release=r);}},id:'take',owner:'page',session:{},maxPendingBytes:5,onFailure:e=>errors.push(e.message)});
 writer.push(new Blob(['abc']),1000);
 while(!entered)await new Promise(r=>setTimeout(r,1));
 writer.push(new Blob(['def']),2000);writer.push(new Blob(['stop']),2001);
 assert.equal(errors.length,1);assert.equal(writer.status().pendingBytes,10);
 release();const result=await writer.settle();assert.equal(result.pendingBytes,7);assert.ok(result.error);
 assert.deepEqual(result.pending.map(p=>p.index),[1,2]);
});
test('recovery refuses corrupt or missing stored chunks while leaving originals intact',async()=>{
 const piece={takeId:'take',index:0,blob:new Blob(['original'])};piece.sha256=await Capture.digest(piece.blob);
 const capture={id:'take',nextIndex:1,bytes:8,mime:'video/webm'};
 await assert.rejects(Capture.assemble({capture,chunks:[{...piece,blob:new Blob(['tampered'])}]}),/integrity/);
 await assert.rejects(Capture.assemble({capture,chunks:[]}),/missing chunks/);
 assert.equal(await piece.blob.text(),'original');
});
