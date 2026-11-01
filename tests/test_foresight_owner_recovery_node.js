'use strict';
// Actual storage/startup functions under controlled DOM/IndexedDB/network.
// This checks identity boundaries and failure behavior, not browser rendering.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');
const files=read('static/foresight_files.js'), reach=read('2i/2i-assets/reach.js');
const databases=new Map(), opened=[];
function storageContext(owner,{offline=false,missing=false}={}){
 let token='token-'+owner;
 const storage={getItem:k=>k==='pubcast_token'?token:null};
 const ctx={window:{},sessionStorage:storage,localStorage:storage,console,
   fetch:async()=>{if(offline)throw Error('unavailable');return {ok:true,json:async()=>missing?{}:{user_id:owner}}},
   indexedDB:{open(name){
     opened.push(name);if(!databases.has(name))databases.set(name,new Map());
     const records=databases.get(name), req={result:{close(){},transaction(){
       const tx={objectStore(){return {
         get(id){const r={};queueMicrotask(()=>{r.result=records.get(id);r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.())});return r},
         put(value){const r={};queueMicrotask(()=>{records.set(value.id,value);r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.())});return r}
       }}};return tx;
     }}};queueMicrotask(()=>req.onsuccess?.());return req;
   }}
 };
 vm.createContext(ctx);vm.runInContext(files,ctx);
 return {api:ctx.window.ForesightFiles,changeToken:()=>{token='different-account'}};
}
async function startupTests(){
 const source=reach.slice(reach.indexOf('async function startReach() {'),reach.indexOf('window.reachStarted='));
 function context(fileMode,fail=false){
   const calls=[],ctx={reachFileMode:fileMode,networked:true,initializing:true,documentDirty:false,saveConflict:false,
     init(){},api:async url=>{calls.push(url);return {auth_enforced:false}},
     connectReach:async()=>{if(fail)throw Error('identity unavailable')},setSaveStatus(){},showAccount:async()=>{},
     stored(){throw Error('must not read an unverified or ordinary manuscript recovery key')},render(){},
     saveDocument:async()=>{throw Error('must not save another manuscript')},reachHeaders:()=>({})};
   vm.createContext(ctx);vm.runInContext(source,ctx);return {ctx,calls};
 }
 const file=context('file-one');await file.ctx.startReach();
 assert.equal(file.ctx.initializing,false);assert.deepEqual(file.calls,['/api/auth/status']);
 const failed=context(null,true);await assert.rejects(failed.ctx.startReach(),/identity unavailable/);
 assert.equal(failed.ctx.initializing,true,'no editing/recovery under an unverified owner');
 const write=reach.slice(reach.indexOf('function writeRecovery() {'),reach.indexOf('function markDirty() {'));
 const ctx={reachFileMode:'file-one',networked:true,serverReady:true};
 vm.createContext(ctx);vm.runInContext(write,ctx);ctx.writeRecovery();
 console.log('PASS: file trays never restore/write ordinary manuscript recovery; identity outage fails closed');
}
(async()=>{
 const alice=storageContext('alice'),bob=storageContext('bob');
 await alice.api.record('same-id',{id:'same-id',draft:'Alice original'});
 assert.equal(await bob.api.record('same-id'),undefined,'another owner cannot load the same file ID');
 await bob.api.record('same-id',{id:'same-id',draft:'Bob original'});
 assert.equal((await alice.api.record('same-id')).draft,'Alice original');
 assert.equal((await bob.api.record('same-id')).draft,'Bob original');
 assert(!opened.includes('pubcast-foresight-files-v1'),'never silently claim legacy ownerless bytes');
 alice.changeToken();await assert.rejects(alice.api.record('same-id'),/account changed/);
 const before=opened.length;
 await assert.rejects(storageContext('offline',{offline:true}).api.record('same-id'),/unavailable/);
 await assert.rejects(storageContext('missing',{missing:true}).api.record('same-id'),/owner/);
 assert.equal(opened.length,before,'unverified identities cannot open any storage');
 console.log('PASS: owner-scoped working copies; credential change, identity outage and missing owner refused; legacy untouched');
 await startupTests();
 const html=read('static/foresight_counter.html');
 const oldPaid=JSON.stringify({provider:'anthropic',model:'old-owner-paid'});
 const settings=new Map([['reach2i_model_v1',oldPaid],['pubcast2i_llm_v2',JSON.stringify({provider:'claude'})]]);
 const settingsContext={MODEL_KEY:null,LLM_KEY:null,llmCfg:null,modelConfig:null,
   stored:(key,fallback)=>settings.has(key)?JSON.parse(settings.get(key)):fallback,
   hostLocalProvider:provider=>provider,
   loadLLM(){return this.stored(this.LLM_KEY,{provider:'pubpartner'})}};
 // loadLLM is normally a same-script function; bind it to its test global.
 settingsContext.loadLLM=()=>settingsContext.stored(settingsContext.LLM_KEY,{provider:'pubpartner'});
 vm.createContext(settingsContext);
 vm.runInContext(reach.slice(reach.indexOf('function configureOwnerModels('),reach.indexOf('async function connectReach() {')),settingsContext);
 settingsContext.configureOwnerModels('alice',{provider:'ollama',model:'free-local'});
 assert.equal(settingsContext.modelConfig.model,'free-local');assert.equal(settingsContext.llmCfg.provider,'pubpartner');
 settings.set('reach2i_model_v1_alice',JSON.stringify({provider:'openai',model:'explicit-alice-choice'}));
 settingsContext.configureOwnerModels('alice',{provider:'ollama'});
 assert.equal(settingsContext.modelConfig.model,'explicit-alice-choice','preserve owner-specific explicit choices');
 settingsContext.configureOwnerModels('bob',{provider:'ollama',model:'bob-local'});
 assert.equal(settingsContext.modelConfig.model,'bob-local');assert.equal(settings.get('reach2i_model_v1'),oldPaid);
 console.log('PASS: ownerless/other-account paid settings never become a new account’s defaults');
 const boot=html.slice(html.indexOf('async function boot(){'),html.lastIndexOf('boot();'));
 const legacy=JSON.stringify({trays:[{id:'legacy-private-title'}]});
 const layouts=new Map([['foresight.counter.v3',legacy],['foresight.counter.v3:alice',JSON.stringify({trays:[{id:'alice-only'}]})]]);
 for(const owner of ['alice','bob']){
   let restored,key;
   const ctx={window:{},hintEl:{style:{}},ForesightFiles:{ownerScope:async()=>owner},
     hostLayout:{enable(){},load:async()=>null,stamp:()=>0,save(){}},
     params:{has:k=>k==='once'},counter:{setStorageKey:k=>{key=k},restore:v=>{restored=v}},
     refreshDots(){},setInterval(){},updateHint(){},localStorage:{getItem:k=>layouts.get(k)}};
   vm.createContext(ctx);vm.runInContext(boot,ctx);await ctx.boot();
   assert.equal(key,'foresight.counter.v3:'+owner);
   assert.equal(restored?.trays[0].id,owner==='alice'?'alice-only':undefined);
 }
 assert.equal(layouts.get('foresight.counter.v3'),legacy,'unowned legacy layouts remain intact');
 const create=html.slice(html.indexOf('function createRenderer('),html.indexOf('const G = createRenderer'));
 const notice={style:{},appendChild(link){this.link=link}};
 const graphics={ForesightGL:class{constructor(){throw Error('No GPU')}},
   ForesightCanvas2D:class{constructor(){throw Error('No 2D renderer')}},document:{createElement:()=>({})}};
 vm.createContext(graphics);vm.runInContext(create,graphics);
 assert.throws(()=>graphics.createRenderer({},notice),/No 2D renderer/);
 assert.equal(notice.link.href,'/writers-room');
 console.log('PASS: account-scoped layout restore preserves legacy; missing renderers offer the genuine 2i route');
})().catch(error=>{console.error(error);process.exitCode=1});
