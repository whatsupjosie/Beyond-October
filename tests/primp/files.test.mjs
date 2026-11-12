import test from 'node:test';
import assert from 'node:assert/strict';
import {saveLookFile} from '../../static/primp/files.mjs';
const blob=new Blob(['look']);

test('a fallback download request cannot claim a confirmed save',async()=>{
 let requested;const result=await saveLookFile(blob,'look.primp',{download:(data,name)=>requested={data,name}});
 assert.equal(result.confirmed,false);assert.equal(requested.data,blob);assert.equal(requested.name,'look.primp');
});
test('save is confirmed only after the writer closes successfully',async()=>{
 const events=[];let finishClose;const closing=new Promise(resolve=>finishClose=resolve);
 const pending=saveLookFile(blob,'look.primp',{picker:async()=>({createWritable:async()=>({write:async data=>events.push(data),close:async()=>{events.push('closing');await closing;events.push('closed');}})})});
 let resolved=false;pending.then(()=>resolved=true);await new Promise(resolve=>setImmediate(resolve));assert.equal(resolved,false);assert.deepEqual(events,[blob,'closing']);finishClose();assert.deepEqual(await pending,{confirmed:true});assert.equal(events.at(-1),'closed');
});
test('cancelled picker and failed write/close do not fall back or claim success',async()=>{
 let downloads=0,aborts=0;const download=()=>downloads++;
 await assert.rejects(saveLookFile(blob,'look.primp',{picker:async()=>{throw new DOMException('cancel','AbortError');},download}),{name:'AbortError'});
 for(const failAt of ['write','close'])await assert.rejects(saveLookFile(blob,'look.primp',{download,picker:async()=>({createWritable:async()=>({write:async()=>{if(failAt==='write')throw Error('disk failure');},close:async()=>{if(failAt==='close')throw Error('disk failure');},abort:async()=>aborts++})})}),/disk failure/);
 assert.equal(downloads,0);assert.equal(aborts,2);
});
test('picker opens before expensive serialization; preparation failure never opens a writer',async()=>{
 const events=[];
 await saveLookFile(()=>{events.push('serialize');return blob;},'look.primp',{picker:async()=>{events.push('picker');return {createWritable:async()=>({write:async()=>{},close:async()=>{}})};}});
 assert.deepEqual(events,['picker','serialize']);
 await assert.rejects(saveLookFile(()=>{throw Error('too large');},'look.primp',{picker:async()=>({createWritable:async()=>{throw Error('must not open');}})}),/too large/);
});
