'use strict';
/* Protect Claude's standalone typewriter while testing the new 2i relay. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const script=fs.readFileSync(path.join(__dirname,'../static/typewriter_console_demo.js'),'utf8');

function fixture(embedded) {
  const messages=[],docEvents={},windowEvents={},frameEvents={},nodes=[];
  const parent={postMessage:(data,origin)=>messages.push({data,origin})};
  const document={
    body:{classList:{add(value){document.body.embeddedClass=value;}}},
    addEventListener:(type,handler)=>{docEvents[type]=handler;},
    createElement:tag=>{
      const item={
        tag,style:{},className:'',clientWidth:300,scrollHeight:40,scrollTop:0,
        classList:{add(){}},setAttribute(){},getBoundingClientRect(){return {width:100};}
      };
      nodes.push(item);return item;
    }
  };
  const frame={clientWidth:1000,appendChild(){},addEventListener:(type,handler)=>{frameEvents[type]=handler;}};
  const window={addEventListener:(type,handler)=>{windowEvents[type]=handler;}};
  const parentWindow=embedded?parent:window;
  const location={search:embedded?'?embedded=2i':'',origin:'https://local.test'};
  vm.runInNewContext(script,{
    window,document,parent:parentWindow,location,URLSearchParams,
    getComputedStyle:()=>({font:'12px monospace',paddingLeft:'0',paddingRight:'0'})
  },{filename:'typewriter_console_demo.js'});
  docEvents['pubcast:console-ready']({detail:{frame,manifest:{paper:{x:0,y:0,w:0.5,h:0.4}}}});
  const paper=nodes.find(x=>x.className==='pc-typewriter-paper');
  assert.ok(paper);
  return {
    windowEvents,messages,paper,
    key:(char,text)=>frameEvents['pubcast:key']({detail:{id:'test.'+char,char,text,source:'pointer'}}),
    message:(origin,source,text)=>windowEvents.message({origin,source,data:{type:'pubcast:2i-manuscript',text}}),
    parent
  };
}
test('original standalone typewriter still writes into its bench paper',()=>{
  const x=fixture(false);
  x.key('A','a'); x.key('B','b');
  assert.equal(x.paper.textContent,'ab');
  assert.deepEqual(x.messages,[]);
});
test('embedded keys relay to 2i rather than writing to an independent buffer',()=>{
  const x=fixture(true);
  assert.deepEqual(x.messages[0].data,{type:'pubcast:2i-ready'});
  x.key('A','a');
  assert.equal(x.paper.textContent,'');
  assert.equal(x.messages[1].data.type,'pubcast:2i-key');
  assert.equal(x.messages[1].data.key.text,'a');
  assert.equal(x.messages[1].origin,'https://local.test');
  x.message('https://local.test',x.parent,'Saved manuscript');
  assert.equal(x.paper.textContent,'Saved manuscript');
});
test('embedded paper rejects commands from wrong origin or source',()=>{
  const x=fixture(true);
  x.message('https://untrusted.test',x.parent,'Untrusted');
  assert.equal(x.paper.textContent,'');
  x.message('https://local.test',{},'Wrong window');
  assert.equal(x.paper.textContent,'');
});