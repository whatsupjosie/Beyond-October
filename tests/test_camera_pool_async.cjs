const test=require('node:test'),assert=require('node:assert/strict');
const {Scope}=require('../static/camera_pool_async.js');
test('changing a session cancels an unfinished operation and rejects its late result',async()=>{
 const scope=new Scope();let complete;const old=scope.operation(()=>new Promise(resolve=>{complete=resolve;}),1000);
 await Promise.resolve();scope.reset();await assert.rejects(old,{name:'AbortError'});
 complete('old session');assert.equal(await scope.operation(async()=> 'new session'), 'new session');
 assert.equal(scope.controllers.size,0);
});
test('an operation that never finishes times out and releases its controller',async()=>{
 const scope=new Scope();await assert.rejects(scope.operation(()=>new Promise(()=>{}),20),{name:'TimeoutError'});
 assert.equal(scope.controllers.size,0);
});
test('request deadlines also bound response body decoding',async()=>{
 const previous=global.fetch;global.fetch=async()=>({ok:true,json:()=>new Promise(()=>{})});
 try{const scope=new Scope();await assert.rejects(scope.request('/slow',{},r=>r.json(),20),{name:'TimeoutError'});assert.equal(scope.controllers.size,0);}
 finally{global.fetch=previous;}
});
test('cancellation before a queued action starts performs no work',async()=>{
 const scope=new Scope();let calls=0;const pending=scope.operation(()=>{calls++;return 'late';});
 scope.reset();await assert.rejects(pending,{name:'AbortError'});assert.equal(calls,0);
});
