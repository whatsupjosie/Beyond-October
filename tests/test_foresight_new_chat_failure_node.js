'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const source = fs.readFileSync(path.join(__dirname,'../static/foresight_programs.js'),'utf8');
const body = source.split('async function newChat(){')[1].split('\n    // --- reload')[0];
assert.ok(body);
const fn = new AsyncFunction('fetch','openProgram','toast', body.slice(0,body.lastIndexOf('\n    }')));
async function run(response, rejected=false){
  const opened=[], notifications=[];
  const result=await fn(async()=>{if(rejected) throw Error('network offline');return response;}, (...args)=>opened.push(args), msg=>notifications.push(msg));
  return {result,opened,notifications};
}
(async()=>{
  for(const [response,rejected] of [[{ok:false,status:401},false],[{ok:false,status:503},false],[{ok:true,json:async()=>({})},false],[null,true]]){
    const r=await run(response,rejected);
    assert.equal(r.result,false);
    assert.equal(r.opened.length,0,'failed archive creation must not open a chat tray');
    assert.equal(r.notifications.length,1);
  }
  const r=await run({ok:true,json:async()=>({conversation_id:'conv_real_1'})});
  assert.equal(r.result,true);
  assert.equal(r.opened.length,1);
  assert.equal(r.opened[0][1].conversationId,'conv_real_1');
  assert.equal(r.notifications.length,0);
  console.log('Foresight canonical conversation creation: 5 scenarios passed');
})().catch(err=>{console.error(err);process.exitCode=1});
