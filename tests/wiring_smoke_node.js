/* Regression tests for Foresight ↔ normal 2i message/save handshake and chat outcomes.
 * No browser, server, or AI response is pretended to be live. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const fileBridge=fs.readFileSync(path.join(ROOT,'2i/2i-assets/file-workspace.js'),'utf8');
const reach=fs.readFileSync(path.join(ROOT,'2i/2i-assets/reach.js'),'utf8');
const html=fs.readFileSync(path.join(ROOT,'2i/writers-room-v22.html'),'utf8');
function tick(){return new Promise(resolve=>setImmediate(resolve));}
function localProviderTests(){
 const begin=reach.indexOf('function hostLocalProvider(config) {');
 const end=reach.indexOf('let recoveryTimer',begin);
 assert.ok(begin>=0 && end>begin,'host-based local provider resolution must exist');
 const ctx=vm.createContext({});
 vm.runInContext(reach.slice(begin,end)+';globalThis.resolveLocal=hostLocalProvider;',ctx);
 const local=ctx.resolveLocal;
 assert.equal(local({provider:'ollama',model:'chosen-offline-model'}).model,'chosen-offline-model');
 assert.equal(local({provider:'openai_compatible',model:'local-alias',base_url:'http://127.0.0.1:2345/v1'}).model,'local-alias');
 assert.equal(local({provider:'openai_compatible',base_url:'https://api.openai.com/v1'}),null);
 assert.equal(local({provider:'ollama',base_url:'https://billed.example/v1'}),null,'remote Ollama endpoint is not a free-local default');
 for (const p of ['anthropic','claude','openai','gemini','mistral','groq','mock','offline'])
   assert.equal(local({provider:p,model:'some-model'}),null,'must never default to '+p);
 assert.equal(local(null),null);
 assert.ok(reach.includes('provider:modelConfig, allow_fallback:false'),'no silent provider fallback');
 assert.ok(reach.includes('No local model is configured.'),'unconfigured must fail clearly');
 assert.ok(!reach.includes("{provider:'ollama', model:'ministral-pubcast:3b'}"),'no hardcoded first-run model tag');
 console.log('PASS: local model is host-selected; paid/default fallback rejected; no hardcoded model tag');
}
async function bridgeTest(){
 const events={}, out=[],saveCalls=[];
 const save=async()=>{saveCalls.push('save');return true;};
 const lastResult=()=>out.filter(x=>x.data.type==='foresight:file-result').at(-1);
 const context={
   window:{reachStarted:Promise.resolve()},location:{search:'',origin:'http://127.0.0.1:8000'},
   parent:{postMessage:function(data,target){out.push({data,target})}},
   addEventListener:(type,fn)=>{events[type]=fn},
   $:(id)=>{if(id==='saveBtn')return {disabled:true};throw Error('Unexpected query '+id)},
   saveDocument:save,docPayload:()=>({format:'2i-document',version:4,state:{committed:['My untouched draft']}}),safeName:()=>"Original_Work",
   Blob,URLSearchParams,Promise,console,Event:class Event{constructor(type){this.type=type}},
   document:{documentElement:{dataset:{}},addEventListener(){},dispatchEvent(){}},
   documentDirty:false,saveConflict:false,savePromise:null,chatSending:false,generating:false,PP:{inflight:false},recoverySafe:true,
 };
 vm.runInNewContext(fileBridge,context,{filename:'file-workspace.js'});
 await tick();
 assert.equal(context.saveDocument,save,'native adapter must not overwrite Reach ownership');
 assert.equal(typeof events.message,'function','host handshake must exist');
 const msg=(command,origin='http://127.0.0.1:8000',fileId=undefined)=>events.message({origin,source:context.parent,data:{type:'foresight:file-command',requestId:'r-'+out.length,fileId,command,sessionNonce:null}});
 await msg('save');
 assert.equal(saveCalls.length,1);
 assert.equal(lastResult().data.result,true);
 await msg('export');
 assert.equal(lastResult().data.result.name,'Original_Work.2i');
 const exported=JSON.parse(await lastResult().data.result.data.text());
 assert.deepEqual(exported.state.committed,['My untouched draft']);
 await msg('save','https://malicious.example');
 assert.equal(saveCalls.length,1,'cross-origin commands must be ignored');
 await msg('save','http://127.0.0.1:8000','some-other-file');
 assert.equal(saveCalls.length,1,'normal writer must not process file-scoped commands');
 context.saveDocument=async()=>false;
 await msg('save');
 assert.equal(lastResult().data.result,false,'unconfirmed server save must not be reported as saved');
 await msg('status');
 assert.equal(lastResult().data.result.ready,true);
 assert.equal(lastResult().data.result.mode,'full');
 assert.equal(lastResult().data.result.dirty,false);
 // A real acknowledgement changes the 2i presentation policy, without stopping saving.
 await events.message({origin:context.location.origin,source:context.parent,
   data:{type:'foresight:file-command',requestId:'activity-reduced',sessionNonce:null,command:'activity',payload:{mode:'reduced'}}});
 assert.equal(context.document.documentElement.dataset.foresightActivity,'reduced');
 assert.equal(lastResult().data.result.mode,'reduced');
 await events.message({origin:context.location.origin,source:context.parent,
   data:{type:'foresight:file-command',requestId:'activity-pause',sessionNonce:null,command:'activity',payload:{mode:'pause-optional'}}});
 assert.equal(context.document.documentElement.dataset.foresightActivity,'pause-optional');
 context.chatSending=true;
 await msg('prepare-close');
 assert.equal(lastResult().data.result.canClose,false,'ongoing conversation prevents destructive close');
 context.chatSending=false;
 context.saveDocument=save;
 await msg('prepare-close');
 assert.equal(lastResult().data.result.canClose,true);
 context.saveDocument=async()=>{context.chatSending=true;return true;};
 await msg('prepare-close');
 assert.equal(lastResult().data.result.canClose,false,'work starting during awaited Save blocks destruction');
 context.chatSending=false;
 context.saveDocument=async()=>{context.documentDirty=true;return true;};
 await msg('prepare-close');
 assert.equal(lastResult().data.result.canClose,false,'edits during Save block destruction');
 context.documentDirty=false;context.saveDocument=save;
 const oldLength=out.length;
 await events.message({origin:context.location.origin,source:{},data:{type:'foresight:file-command',requestId:'spoof',sessionNonce:null,command:'activity',payload:{mode:'full'}}});
 assert.equal(out.length,oldLength,'untrusted iframe source cannot control 2i');
 console.log('PASS: 2i host Save/Export/status/activity/close protection; origin and source checks');
}
function chatContext(initial){
 const begin=reach.indexOf('async function sendChat() {'),end=reach.indexOf('async function switchPartner() {',begin);
 assert.ok(begin>=0&&end>begin);
 const notices=[],messages=[],buttons={chatSendBtn:{disabled:false},partnerNote:{textContent:''}},input={value:initial};
 let respond;
 const ctx=vm.createContext({
  documentId:'document-1',partnerId:'alex',chatSending:false,generating:false,
  reachFileMode:null,recoverySafe:true,initializing:false,writeRecovery(){},
  chatInput:input,chatHistory:[],conversations:{},MAX_CHAT:40,
  $:id=>buttons[id],addChat:(who,value)=>{notices.push({who,value});return {remove(){}}},
  markDirty:()=>{},callLLM:async m=>{messages.push(m);return await new Promise((resolve,reject)=>{respond={resolve,reject}})},
  console,
 });
 vm.runInContext(reach.slice(begin,end)+';globalThis.runSend=sendChat;',ctx);
 return {ctx,input,notices,messages,respond:()=>respond};
}
async function chatTests(){
 const s=chatContext('First manuscript question');
 const pending=s.ctx.runSend();
 assert.equal(s.input.value,'First manuscript question','draft must stay until confirmed');
 assert.equal(s.ctx.chatHistory[0].delivery,'pending');
 assert.equal(s.messages[0].length,1);
 s.respond().resolve('A real provider response (simulated in test)');
 await pending;
 assert.equal(s.input.value,'');
 assert.equal(s.ctx.chatHistory[0].delivery,undefined);
 assert.equal(s.ctx.chatHistory[1].role,'assistant');
 assert.equal(s.ctx.chatSending,false);
 assert.equal(s.ctx.conversations.alex,s.ctx.chatHistory);
 const t=chatContext('Network timeout case');
 let first=t.ctx.runSend();
 t.respond().reject(new Error('Timeout'));
 await first;
 assert.equal(t.input.value,'Network timeout case','failed draft must stay editable');
 assert.equal(t.ctx.chatHistory[0].delivery,'unknown');
 assert.ok(t.notices.some(n=>n.value.includes('may have reached PubPartner')));
 t.input.value='New question after timeout';
 let next=t.ctx.runSend();
 assert.deepEqual(JSON.parse(JSON.stringify(t.messages[1])),[{role:'user',content:'New question after timeout'}], 'unknown prior send must not be resent as context');
 t.respond().resolve('Fresh answer');await next;
 assert.equal(t.ctx.chatHistory.length,3);
 const h=chatContext('Known HTTP rejection');
 const known=h.ctx.runSend(),err=Object.assign(new Error('Unavailable'),{status:503});h.respond().reject(err);await known;
 assert.equal(h.ctx.chatHistory[0].delivery,'failed');
 assert.ok(!h.notices.some(n=>n.value.includes('may have reached PubPartner')));
 const lost=chatContext('No recovery space');lost.ctx.recoverySafe=false;
 await lost.ctx.runSend();assert.equal(lost.messages.length,0,'storage failure must prevent any network send');
 assert.equal(lost.input.value,'No recovery space');assert.equal(lost.ctx.chatHistory[0].delivery,'failed');
 const file=chatContext('Retain in file first');file.ctx.reachFileMode='file-one';
 let release;file.ctx.window={foresightFileSession:{flush:()=>new Promise(resolve=>{release=resolve})}};
 const sending=file.ctx.runSend();assert.equal(file.messages.length,0,'file retention must finish before provider invocation');
 release();await tick();assert.equal(file.messages.length,1);file.respond().resolve('Retained reply');await sending;
 console.log('PASS: chat pending/ack, draft preservation, successful commit, unknown delivery, failed delivery, no replay of unconfirmed context');
}
(async()=>{
 assert.ok(html.includes("provider:'pubpartner'"),'PubPartner must be the first-run default');
 assert.ok(reach.includes("'reach_' + documentId + '_'"),'autosave snapshots must be document-scoped');
 console.log('PASS: first-run PubPartner selection and per-document autosave keys');
 localProviderTests();await bridgeTest();await chatTests();
 console.log('ALL 2i wiring contract tests passed. Model responses were simulated; no provider was contacted.');
})().catch(e=>{console.error(e);process.exitCode=1});
