'use strict';
/* Real studio-desk source under a minimal DOM: hosted and Foresight file
 * startup must both expose a usable typewriter without replacing persistence. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/studio-desk.js'),'utf8');

function boot(fileMode) {
  const nodes=[],post=[],applied=[],notices=[];
  function element(tag) {
    const el={tag,dataset:{},style:{},children:[],listeners:{},
      classList:{values:new Set(),
        contains(s){return this.values.has(s)},
        toggle(s,force){
          const add=force===undefined?!this.values.has(s):!!force;
          if(add)this.values.add(s);else this.values.delete(s);
          return add;
        }},
      append(child){this.children.push(child)},
      querySelector(){return element('section')},
      setAttribute(name,value){this[name]=value},
      addEventListener(type,handler){this.listeners[type]=handler}
    };
    if(tag==='iframe')el.contentWindow={postMessage:(data,origin)=>post.push({data,origin})};
    nodes.push(el);
    return el;
  }
  const topbar=element('topbar'),mc=element('mc'),notebook=element('notebook');
  const solo=element('textarea'),draft=element('textarea');
  solo.value='Original';draft.value='Draft';
  const document={body:element('body'),head:element('head'),listeners:{},
    createElement:element,
    querySelector:query=>query==='.top-bar'?topbar:null,
    addEventListener(type,handler){(this.listeners[type]??=[]).push(handler)},
    dispatchEvent(event){for(const handler of this.listeners[event.type]||[])handler(event)}
  };
  const window={listeners:{},reachStarted:null,foresightFileSession:fileMode?{}:undefined,
    addEventListener(type,handler){(this.listeners[type]??=[]).push(handler)},
    TwoiTypewriterInput:{apply(target,key){applied.push({target:target===solo?'write':'draft',key});return {applied:true}}}
  };
  const ctx={window,document,reachFileMode:fileMode?'file-123':null,
    location:{search:fileMode?'?file=file-123':'',origin:'https://local.test'},
    URLSearchParams,TwoiStudioBridge:{presentation:()=>({seated:false,room:null,returnPath:null})},
    $:id=>({mcSection:mc,notebookFrame:notebook})[id],
    soloTextarea:solo,draftArea:draft,coWriting:false,committed:['Original'],buffer:['Draft'],
    initializing:false,generating:false,chatSending:false,editingIdx:null,
    networked:true,serverReady:true,render(){},addChat:(who,text)=>notices.push({who,text}),
    CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail}}
  };
  vm.runInNewContext(source,ctx,{filename:'studio-desk.js'});
  const get=id=>nodes.find(el=>el.id===id);
  const iframe=get('twoiTypewriterConsole');
  assert.ok(iframe,'Required console iframe not installed');
  function message(data,origin=ctx.location.origin,source=iframe.contentWindow) {
    for(const handler of window.listeners.message||[])handler({data,origin,source});
  }
  return {window,document,ctx,get,post,applied,notices,message,iframe};
}
test('Foresight file document gets a visible View selector without studio-note controls',()=>{
  const f=boot(true);
  assert.equal(f.document.body.dataset.twoiDesk,'standard');
  assert.ok(f.get('twoiFilePresentation'));
  assert.equal(f.get('twoiStudioControls'),undefined);
  assert.equal(f.iframe.src,'/typewriter-console?embedded=2i');
});
test('file-tray selector opens a real typewriter whose keys reach the current document',()=>{
  const f=boot(true),choose=f.get('twoiFilePresentation');
  choose.value='typewriter';choose.onchange();
  assert.equal(f.document.body.dataset.twoiDesk,'typewriter');
  assert.equal(f.get('twoiDeskScene').hidden,false);
  f.message({type:'pubcast:2i-ready'});
  f.message({type:'pubcast:2i-key',key:{char:'A',text:'a',source:'pointer'}});
  assert.equal(f.applied.length,1);
  assert.equal(f.applied[0].target,'write');
  assert.equal(f.post.at(-1).data.text,'Original');
});
test('file-tray iframe rejects unrelated windows and blocks typing during active work',()=>{
  const f=boot(true);
  f.window.twoiSetPresentation('typewriter');
  f.message({type:'pubcast:2i-key',key:{char:'X',text:'x'}},'https://foreign.test');
  f.message({type:'pubcast:2i-key',key:{char:'X',text:'x'}},'https://local.test',{});
  assert.equal(f.applied.length,0);
  f.ctx.generating=true;
  f.message({type:'pubcast:2i-key',key:{char:'Y',text:'y'}});
  assert.equal(f.applied.length,0);
  assert.match(f.notices.at(-1).text,/Finish the active edit/);
});
test('normal hosted 2i retains studio-note controls and menu-driven presentation',()=>{
  const f=boot(false);
  assert.ok(f.get('twoiStudioControls'));
  assert.equal(f.get('twoiFilePresentation'),undefined);
  f.window.twoiSetPresentation('typewriter');
  assert.equal(f.document.body.dataset.twoiDesk,'typewriter');
});

test('file-tray typewriter blocks edits until the real save session is mounted',()=>{
  const f=boot(true);
  f.window.twoiSetPresentation('typewriter');
  f.window.foresightFileSession=undefined;
  f.message({type:'pubcast:2i-key',key:{char:'X',text:'x'}});
  assert.equal(f.applied.length,0);
  assert.match(f.notices.at(-1).text,/Finish opening this Foresight file/);
  f.window.foresightFileSession={save(){}};
  f.message({type:'pubcast:2i-key',key:{char:'X',text:'x'}});
  assert.equal(f.applied.length,1);
});
