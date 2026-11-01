'use strict';
// Contract integration with the actual host provider. The DOM and iframe are
// controlled fakes: this does not claim a Chromium or real-model acceptance run.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const src=fs.readFileSync(path.resolve(__dirname,'../static/foresight_programs.js'),'utf8');
const listeners=new Map(), outgoing=[];
const origin='http://127.0.0.1:8000';
let nonce=0;
function fakeElement(tag){
  const own=new Map();
  const element={tagName:tag.toUpperCase(),style:{},children:[],classList:{add(){}},
    setAttribute(k,v){this[k]=v},addEventListener(event,fn){own.set(event,fn)},
    appendChild(child){this.children.push(child)},remove(){},
    fire(event){own.get(event)?.()},
    get contentWindow(){return this._window ||= {postMessage:(data,target)=>{outgoing.push({data,target,source:this._window})}}}
  };
  return element;
}
const document={createElement:fakeElement,createTextNode:t=>({textContent:t})};
const root={document,location:{origin,protocol:'http:'},console,
  addEventListener:(type,fn)=>{const existing=listeners.get(type)||[];existing.push(fn);listeners.set(type,existing)},
  URL,URLSearchParams,setTimeout,clearTimeout,AbortController,
  crypto:{randomUUID(){return 'req-'+(++nonce)}}};
root.window=root;
vm.runInNewContext(src,root,{filename:'foresight_programs.js'});
const programs=root.ForesightPrograms.create({toast:()=>{}}),provider=programs.provider;
function send(originArg,source,data){for(const listener of listeners.get('message')||[])listener({origin:originArg,source,data})}
async function run(){
  const content={id:'c123',type:'twoi',data:{},state:{}};
  const host={body:fakeElement('div'),setTitle(){},changed(){}};
  const handle=provider.mount(content,host);
  const frame=content.frame;
  assert.ok(frame,'real 2i must be iframe-hosted');
  // An unrelated iframe and a navigation to a different origin are both ignored.
  send(origin,{}, {type:'foresight:file-ready',version:1,sessionNonce:content.sessionNonce});
  assert.equal(content.appReady,false);
  send('https://attacker.invalid',frame.contentWindow,{type:'foresight:file-ready',version:1,sessionNonce:content.sessionNonce});
  assert.equal(content.appReady,false);
  send(origin,frame.contentWindow,{type:'foresight:file-ready',version:1,sessionNonce:content.sessionNonce});
  assert.equal(content.appReady,true);
  frame.fire('load');
  const p=provider.setActivityPolicy(content,'reduced','background');
  await Promise.resolve();
  const a=outgoing.at(-1);
  assert.equal(a.target,origin);
  assert.equal(a.data.command,'activity');
  assert.equal(a.data.payload.mode,'reduced');
  const spoof=outgoing.length;
  send(origin,{}, {type:'foresight:file-result',requestId:a.data.requestId,sessionNonce:content.sessionNonce,result:{mode:'reduced'}});
  send('https://attacker.invalid',frame.contentWindow,{type:'foresight:file-result',requestId:a.data.requestId,sessionNonce:content.sessionNonce,result:{mode:'reduced'}});
  assert.equal(outgoing.length,spoof);
  send(origin,frame.contentWindow,{type:'foresight:file-result',requestId:a.data.requestId,sessionNonce:content.sessionNonce,result:{version:1,mode:'reduced',ready:true}});
  assert.equal((await p).supported,true);
  const close=provider.prepareClose(content);
  await Promise.resolve();
  const b=outgoing.at(-1);
  assert.equal(b.data.command,'prepare-close');
  send(origin,frame.contentWindow,{type:'foresight:file-result',requestId:b.data.requestId,sessionNonce:content.sessionNonce,result:{canClose:false,reason:'Active model request'}});
  assert.equal((await close).canClose,false,'host must honor the app refusal');
  assert.equal((await provider.setActivityPolicy({type:'stage'},'pause-optional')).supported,false);
  const pending=provider.getActivityStatus(content);
  await Promise.resolve();
  handle.destroy();
  await assert.rejects(pending,/closed before its operation/);
  console.log('PASS host protocol: trusted source/origin, ready handshake, real activity acknowledgement, close refusal, pending rejection, unsupported app');
}
run().catch(e=>{console.error(e);process.exitCode=1});
