'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/file-workspace.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const events={},messages=[];
let resolveStartup,mounted=false,pending=false,onSave=()=>{};
const element=()=>({style:{},setAttribute(){},getBoundingClientRect:()=>({height:30})});
const session={save:async()=>{onSave();pending=false;return true},saveAs:async()=>{},pending:()=>pending,
 flush:async()=>{},export:async()=>({}),};
const ctx={window:{reachStarted:new Promise(resolve=>{resolveStartup=resolve})},
 location:{search:'?file=document-a&foresightSession=nonce',origin:'http://127.0.0.1:8000'},
 parent:{postMessage:message=>messages.push(message)},URLSearchParams,URL,Event:class{},
 addEventListener:(type,fn)=>{events[type]=fn},document:{createElement:element,querySelector:element,
 body:{insertBefore(){}},addEventListener(){},documentElement:{dataset:{}},dispatchEvent(){}},
 $:element,ResizeObserver:class{observe(){}disconnect(){}},markDirty(){},soloTextarea:{},
 ForesightFiles:{mount:async()=>{mounted=true;return session}},
 chatSending:false,generating:false,PP:{inflight:false},getDocState:()=>({}),render(){},console};
vm.createContext(ctx);vm.runInContext(source,ctx);
async function request(command){await events.message({origin:ctx.location.origin,source:ctx.parent,
 data:{type:'foresight:file-command',fileId:'document-a',requestId:command,sessionNonce:'nonce',command}});
 return messages.filter(m=>m.type==='foresight:file-result').at(-1)?.result;}
(async()=>{
 await tick();assert.equal(mounted,false,'file mounting must await account startup');
 resolveStartup();await tick();assert.equal(mounted,true);
 assert.equal(ctx.window.foresightFileSession,session);
 ctx.chatSending=true;assert.equal((await request('prepare-close')).canClose,false);
 ctx.chatSending=false;onSave=()=>{ctx.PP.inflight=true};
 assert.equal((await request('prepare-close')).canClose,false,'indexing started during file save must prevent destruction');
 ctx.PP.inflight=false;onSave=()=>{};
 assert.equal((await request('prepare-close')).canClose,true);
 console.log('PASS: file adapter awaits identity; close saves actual file and rejects active/new work');
})().catch(error=>{console.error(error);process.exitCode=1});
