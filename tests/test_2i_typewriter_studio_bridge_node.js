'use strict';
/* Exercise the real studio-desk script with a minimal DOM, without rewriting
 * Claude's key engine or making live API requests. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/studio-desk.js'),'utf8');

function boot() {
  const objects=[],sent=[],calls=[],notices=[];
  function element(tag) {
    const e={
      tag,style:{},dataset:{},listeners:{},children:[],
      classList:{
        flags:new Set(),
        contains(name){return this.flags.has(name);},
        toggle(name,value){
          const on=value===undefined?!this.flags.has(name):!!value;
          if(on)this.flags.add(name);else this.flags.delete(name);
          return on;
        }
      },
      append(child){this.children.push(child);},
      addEventListener(type,handler){this.listeners[type]=handler;},
      setAttribute(name,value){this[name]=value;},
      querySelector(){return element('section');}
    };
    if(tag==='iframe')e.contentWindow={postMessage:(data,origin)=>sent.push({data,origin})};
    objects.push(e);return e;
  }
  const mcSection=element('section'),notebook=element('notebook');
  const document={
    body:element('body'),head:element('head'),listeners:{},
    createElement:element,
    addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);},
    dispatchEvent(event){for(const handler of this.listeners[event.type]||[])handler(event);}
  };
  const window={
    listeners:{},reachStarted:null,
    addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);}
  };
  const soloTextarea=element('textarea'),draftArea=element('textarea');
  soloTextarea.value='First';draftArea.value='Draft';
  const state={
    window,document,reachFileMode:false,
    TwoiStudioBridge:{presentation(){return{seated:false,room:null,returnPath:null};}},
    URLSearchParams,location:{search:'',origin:'https://local.test'},
    $:id=>({mcSection,notebookFrame:notebook})[id],
    soloTextarea,draftArea,coWriting:false,committed:['First'],buffer:['Draft'],
    initializing:false,generating:false,chatSending:false,editingIdx:null,
    networked:true,serverReady:true,render(){},
    CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},
    addChat:(who,text)=>notices.push({who,text})
  };
  window.TwoiTypewriterInput={
    apply(target,key){
      calls.push({target:target===soloTextarea?'solo':'draft',key});
      if(typeof key.text==='string')target.value+=key.text;
      return {applied:true};
    }
  };
  vm.runInNewContext(source,state,{filename:'studio-desk.js'});
  const iframe=objects.find(x=>x.tag==='iframe');
  const figure=objects.find(x=>x.tag==='figure');
  const expand=objects.find(x=>x.id==='twoiTypewriterExpand');
  assert.ok(iframe&&figure&&expand);
  const message=(data,sourceWindow=iframe.contentWindow,origin='https://local.test')=>{
    for(const handler of window.listeners.message||[])handler({data,source:sourceWindow,origin});
  };
  return {state,window,document,iframe,figure,expand,soloTextarea,draftArea,calls,notices,sent,message};
}
test('authenticated iframe keys edit the live Write manuscript, not the bench buffer',()=>{
  const x=boot();x.window.twoiSetPresentation('typewriter');
  x.message({type:'pubcast:2i-ready'});
  assert.equal(x.sent.at(-1).data.text,'First');
  x.message({type:'pubcast:2i-key',key:{char:'A',text:'a',source:'pointer'}});
  assert.deepEqual(x.calls.map(y=>y.target),['solo']);
  assert.equal(x.soloTextarea.value,'Firsta');
  assert.equal(x.iframe.src,'/typewriter-console?embedded=2i');
});
test('different window or origin cannot inject manuscript text',()=>{
  const x=boot();x.window.twoiSetPresentation('typewriter');
  x.message({type:'pubcast:2i-key',key:{char:'Z',text:'z'}},{});
  x.message({type:'pubcast:2i-key',key:{char:'Z',text:'z'}},x.iframe.contentWindow,'https://evil.test');
  assert.equal(x.calls.length,0);
  assert.equal(x.soloTextarea.value,'First');
});
test('Collab keys target draft, active requests block edits',()=>{
  const x=boot();x.window.twoiSetPresentation('typewriter');
  x.state.coWriting=true;
  x.message({type:'pubcast:2i-key',key:{char:'A',text:'a'}});
  assert.equal(x.draftArea.value,'Drafta');
  assert.equal(x.soloTextarea.value,'First');
  x.state.generating=true;
  x.message({type:'pubcast:2i-key',key:{char:'B',text:'b'}});
  assert.equal(x.calls.length,1);
  assert.equal(x.notices.at(-1).who,'notice');
});
test('expanded keys collapse with Escape and automatically on view change',()=>{
  const x=boot();x.window.twoiSetPresentation('typewriter');
  x.expand.onclick();assert.equal(x.figure.classList.contains('is-expanded'),true);
  x.message({type:'pubcast:2i-collapse'});
  assert.equal(x.figure.classList.contains('is-expanded'),false);
  x.expand.onclick();x.window.twoiSetPresentation('notebook');
  assert.equal(x.figure.classList.contains('is-expanded'),false);
  x.message({type:'pubcast:2i-key',key:{char:'Q',text:'q'}});
  assert.equal(x.calls.length,0);
});