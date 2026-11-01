'use strict';
// Offline contract test for the actual ForesightFiles rich-document recovery UI.
// The DOM/storage/network are narrow labeled doubles; no browser renderer is claimed.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.style={};this.listeners={};this.attrs={};this.textContent='';}
  setAttribute(name,value){this.attrs[name]=String(value)}
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=[...items]}
  remove(){}
  click(){this.onclick?.()}
  addEventListener(event,handler){this.listeners[event]=handler}
  querySelector(){return null}
  getElementsByTagName(name){return this.children.flatMap(child=>[
    ...(child.tagName===name.toUpperCase()?[child]:[]), ...child.getElementsByTagName?.(name)||[]
  ])}
}

async function run({corrupt=false,legacy=false}={}) {
  const source=legacy
    ?Buffer.from(JSON.stringify({format:'2i-document',version:4,state:{committed:['Original v4 text'],buffer:[],pool:[]}}))
    :Buffer.from('PK\x03\x04verified-container', 'latin1');
  const original=Buffer.from('preserved source bytes');
  const working=Buffer.from('PK\x03\x04working-docx', 'latin1');
  const file={id:'case-1',name:'Manuscript.2i',mime:'application/zip',original:new Blob([source]),updated:10};
  const records=new Map([[file.id,file]]);
  const downloads=[];
  const calls=[];
  const body=new Element('body');
  const document={body,createElement:tag=>new Element(tag)};
  const origin='https://127.0.0.1:8000';
  const indexedDB={open(){
    const req={result:{
      createObjectStore(){},
      transaction(_name,mode){
        const tx={objectStore(){return {
          get(id){const request={};queueMicrotask(()=>{request.result=records.get(id);request.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.())});return request},
          put(value){const request={};queueMicrotask(()=>{records.set(value.id,value);request.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.())});return request}
        }}};return tx},
      close(){}
    }};
    queueMicrotask(()=>req.onsuccess?.());return req;
  }};
  const URL={createObjectURL(blob){const id='blob:mock-'+downloads.length;downloads.push({id,blob});return id},revokeObjectURL(){}};
  const window={location:{origin},URL,sessionStorage:{getItem:()=>null},localStorage:{getItem:()=>null}};
  const context={window,indexedDB,document,URL,sessionStorage:window.sessionStorage,localStorage:window.localStorage,Blob,atob,TextDecoder,crypto:require('node:crypto').webcrypto,
    FileReader:class {readAsDataURL(blob){blob.arrayBuffer().then(raw=>{this.result='data:application/octet-stream;base64,'+Buffer.from(raw).toString('base64');this.onload?.()}).catch(e=>this.onerror?.(e))}},
    fetch:async (url,options)=>{if(url==='/api/writers-room/config')return {ok:true,json:async()=>({user_id:'rich-test-owner'})};calls.push({url,body:JSON.parse(options.body)});return corrupt
      ?{ok:false,status:422,json:async()=>({detail:'Payload integrity failed'})}
      :{ok:true,json:async()=>({kind:'rich-v5',document_id:'00000000-0000-4000-8000-000000000001',original_name:'Source.docx',original_mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',original_data_b64:original.toString('base64'),working_docx_b64:working.toString('base64'),metadata:{title:'Rich manuscript'}})}},
    setTimeout:()=>0,clearTimeout:()=>{}, console, File:Blob, structuredClone, parent:window
  };
  vm.createContext(context);
  const script=readFileSync(path.join(__dirname,'../static/foresight_files.js'),'utf8');
  vm.runInContext(script,context,{filename:'foresight_files.js'});
  const host={body:new Element('div'),changed(){},setTitle(){}};
  const c={data:{fileId:file.id}};
  const callbacks={onPreview(active){assert.equal(active,true)}};
  const session=await window.ForesightFiles.mount(c,host,null,callbacks);
  const ui=host.body.getElementsByTagName('button');
  const labels=ui.map(button=>button.textContent);
  if(legacy){
    assert.equal(calls.length,0,'legacy manuscript never contacts rich verification route');
    assert.match(host.body.children[0].children[1].textContent,/text editor ready/i);
    assert.equal(host.body.getElementsByTagName('textarea')[0].value,'Original v4 text');
    const exported=await session.export();
    assert.equal(JSON.parse(await exported.data.text()).version,4);
    return;
  }
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/foresight/files/native-rich/read');
  assert.deepEqual(Buffer.from(calls[0].body.data_b64,'base64'),source);
  if(corrupt){
    assert.match(host.body.children[0].children[1].textContent,/original has not been altered/i);
    assert(!labels.includes('Download working DOCX'));
    assert.equal(records.get(file.id).original,file.original);
    return;
  }
  assert(labels.includes('Download preserved source'));
  assert(labels.includes('Download working DOCX'));
  assert(labels.includes('Download verified rich 2i'));
  assert.equal(session.pending(),false);
  for(const label of ['Download preserved source','Download working DOCX','Download verified rich 2i']){
    const button=ui.find(btn=>btn.textContent===label);
    await button.onclick();
    await new Promise(resolve=>setImmediate(resolve));
  }
  assert.deepEqual(Buffer.from(await downloads[0].blob.arrayBuffer()),original);
  assert.deepEqual(Buffer.from(await downloads[1].blob.arrayBuffer()),working);
  assert.deepEqual(Buffer.from(await downloads[2].blob.arrayBuffer()),source);
  assert.equal(records.get(file.id).original,file.original);
  assert.match(host.body.children[0].children[1].textContent,/read-only until rich editor integration/i);
}

(async()=>{await run();await run({corrupt:true});await run({legacy:true});console.log('2i rich recovery UI contract: passed (verified, recoverable, failure-safe, v4 unchanged)')})().catch(e=>{console.error(e);process.exitCode=1});
