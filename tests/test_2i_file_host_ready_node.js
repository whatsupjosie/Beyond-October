'use strict';
/* Run the real Foresight file adapter against a fake host that sends its
 * first Save command immediately after hearing Ready. This catches a startup
 * race that static asset checks and unit tests cannot. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const script=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/file-workspace.js'),'utf8');

async function launch({failReach=false,authPending=false,missingFile=false,mountThrows=false,decodeFailure=false}={}) {
  const events=[],handlers={},created=[];
  class ResizeObserver{observe(){}disconnect(){}}
  const shell={style:{}};
  const document={
    body:{insertBefore(node){created.push(node)}},
    hidden:false,
    createElement:tag=>({
      tag,style:{},children:[],setAttribute(){},
      prepend(node){this.children.unshift(node);this.textContent=this.children.map(c=>c.textContent||'').join('');},
      getBoundingClientRect:()=>({height:35})
    }),
    querySelector:()=>shell,
    addEventListener(type,fn){(handlers['doc:'+type]??=[]).push(fn)}
  };
  const session={
    save:async()=>{events.push({type:'session-save'});return true;},
    saveAs:async()=>true,flush:async()=>true,
    activity:()=>({dirty:false,busy:false,recovery:!missingFile}),
    pending:()=>false,prepareClose:async()=>true,export:async()=>({})
  };
  const window={reachStarted:failReach?Promise.reject(Error('Account unavailable')):Promise.resolve()};
  const parent={
    postMessage(data,origin){
      events.push({type:data.type,origin,data});
      if(data.type!=='foresight:file-ready')return;
      const listeners=handlers.message||[];
      events.push({type:'handler-count-at-ready',value:listeners.length});
      // This command happens synchronously, like a very fast parent frame.
      for(const fn of listeners)void fn({
        origin:'https://local.test',source:parent,
        data:{type:'foresight:file-command',fileId:'file123',
          sessionNonce:'nonce123',requestId:'first-save',command:'save'}
      });
    }
  };
  const buttons={saveBtn:{},saveIndicator:{}};
  const soloTextarea={readOnly:true,dispatchEvent(){}};
  const draftArea={readOnly:true};
  const ctx={
    window,parent,document,ResizeObserver,URLSearchParams,
    location:{search:'?file=file123&foresightSession=nonce123',origin:'https://local.test'},
    $:id=>buttons[id]||{},
    addEventListener:(type,fn)=>(handlers[type]??=[]).push(fn),
    ForesightFiles:{mount:async(_c,_h,_file,options)=>{if(mountThrows)throw Error('Storage offline');if(decodeFailure){_h.body.children.push({id:'download-original',textContent:'Download original'});options.onError?.();}return session;},record:async()=>true},
    soloTextarea,draftArea,
    markDirty(){},getDocState:()=>({}),loadDocState(){},render(){},
    coWriting:false,committed:['Text'],documentTitle:'Untitled',
    initializing:authPending,chatSending:false,generating:false,editingIdx:null,PP:{inflight:false},
    saveDocument:()=>false,saveDocumentAs:()=>false,
    openDocument:()=>false,newDocument:()=>false,
    Event:class{constructor(type){this.type=type}}
  };
  await vm.runInNewContext(script,ctx,{filename:'file-workspace.js'});
  // Flush a host command's async response after its Save completes.
  await Promise.resolve();await Promise.resolve();
  return {events,handlers,buttons,session,window,created,soloTextarea,draftArea};
}
test('file-tray Ready fires once after host-command subscription',async()=>{
  const f=await launch();
  const ready=f.events.filter(x=>x.type==='foresight:file-ready');
  assert.equal(ready.length,1);
  assert.equal(ready[0].data.fileId,'file123');
  assert.equal(ready[0].data.sessionNonce,'nonce123');
  assert.equal(f.events.find(x=>x.type==='handler-count-at-ready').value,1);
  assert.equal(f.events.filter(x=>x.type==='session-save').length,1);
  assert.equal(f.events.filter(x=>x.type==='foresight:file-result').length,1);
  assert.equal(f.window.foresightFileSession,f.session);
  assert.equal(f.buttons.saveBtn.disabled,false);
  assert.equal(f.soloTextarea.readOnly,false);
  assert.equal(f.draftArea.readOnly,false);
});
test('failed account startup announces no readiness and disables Save',async()=>{
  const f=await launch({failReach:true});
  assert.equal(f.events.filter(x=>x.type==='foresight:file-ready').length,0);
  assert.equal(f.buttons.saveBtn.disabled,true);
  assert.match(f.buttons.saveIndicator.textContent,/Account unavailable/);
});
test('a visible login prompt is not falsely announced as a ready document',async()=>{
  // Reach's startReach() returns after showAccount() while initializing=true.
  const f=await launch({authPending:true});
  assert.equal(f.events.filter(x=>x.type==='foresight:file-ready').length,0);
  assert.equal(f.events.filter(x=>x.type==='session-save').length,0);
  assert.equal(f.window.foresightFileSession,undefined);
  assert.equal(f.buttons.saveBtn.disabled,true);
  assert.match(f.buttons.saveIndicator.textContent,/Sign in to Reach/);
});

test('missing Foresight file is not misreported as loaded or save-ready',async()=>{
  const f=await launch({missingFile:true});
  assert.equal(f.events.filter(x=>x.type==='foresight:file-ready').length,0);
  assert.equal(f.events.filter(x=>x.type==='session-save').length,0);
  assert.equal(f.window.foresightFileSession,undefined);
  assert.equal(f.buttons.saveBtn.disabled,true);
  assert.match(f.buttons.saveIndicator.textContent,/not opened/);
  assert.match(f.created[0].textContent,/did not open safely/);
});
test('file mount failure blocks Save and never tells host it is ready',async()=>{
  const f=await launch({mountThrows:true});
  assert.equal(f.events.filter(x=>x.type==='foresight:file-ready').length,0);
  assert.equal(f.buttons.saveBtn.disabled,true);
  assert.match(f.created[0].textContent,/Storage offline/);
});

test('a decoded-file error blocks readiness even if its original record survives',async()=>{
  const f=await launch({decodeFailure:true});
  assert.equal(f.events.filter(x=>x.type==='foresight:file-ready').length,0);
  assert.equal(f.events.filter(x=>x.type==='session-save').length,0);
  assert.equal(f.window.foresightFileSession,undefined);
  assert.equal(f.buttons.saveBtn.disabled,true);
  assert.match(f.created[0].textContent,/did not open safely/);
  assert.equal(f.created[0].children.some(node=>node.id==='download-original'),true,
    'Working-copy failure must not delete the original recovery download');
});

test('missing or damaged file never unlocks editor fields',async()=>{
  for(const options of [{missingFile:true},{decodeFailure:true},{mountThrows:true}]){
    const f=await launch(options);
    assert.equal(f.soloTextarea.readOnly,true);
    assert.equal(f.draftArea.readOnly,true);
  }
});
