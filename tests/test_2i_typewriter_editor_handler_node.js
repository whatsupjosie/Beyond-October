'use strict';
/* Verify the real 2i input event handler receives and protects typewriter edits.
 * These tests extract Fable's existing handler, not a duplicate implementation. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const engine=require('../2i/2i-assets/typewriter-input.js');
const html=fs.readFileSync(path.join(__dirname,'../2i/writers-room-v22.html'),'utf8');
const start=html.indexOf('function creativeInputType(event)');
const end=html.indexOf("draftArea.addEventListener('input'",start);
assert.ok(start>=0&&end>start,'2i input handler must be discoverable');
const handlerSource=html.slice(start,end);

function setup({text='Hello',protectedText=false}={}) {
  const notices=[],dirty=[];
  const target={
    value:text,selectionStart:text.length,selectionEnd:text.length,listeners:{},
    focus(){},
    addEventListener(type,handler){this.listeners[type]=handler;},
    setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;},
    setRangeText(value,a,b){
      this.value=this.value.slice(0,a)+value+this.value.slice(b);
      this.selectionStart=this.selectionEnd=a+value.length;
    },
    dispatchEvent(event){if(event.type==='input')this.listeners.input(event);return true;}
  };
  target.ownerDocument={
    execCommand(_name,_unused,value){
      target.setRangeText(value,target.selectionStart,target.selectionEnd);
      target.dispatchEvent({type:'input',inputType:'insertText'});
      return true;
    }
  };
  const state={
    soloTextarea:target,committed:[text],lockedLines:new Set(protectedText?[0]:[]),
    window:{twoiNarrativeHistory:protectedText?{}:null,twoiCreativeSession:null},
    NarrativeCore:{
      remapProtected(before,after,locked){
        for(const i of locked)if(before[i]!==after[i])throw Error('Protected line');
        return locked;
      }
    },
    updateLineNumbers(){},keepChapterPositions(){},
    markDirty(){dirty.push('dirty');},countWordsSoon(){},
    addChat:(who,message)=>notices.push({who,message})
  };
  vm.createContext(state);
  vm.runInContext(handlerSource,state,{filename:'real-2i-input-handler.js'});
  return {state,target,notices,dirty};
}
test('typewriter insertion triggers real 2i input and marks manuscript unsaved',()=>{
  const x=setup();
  const r=engine.apply(x.target,{char:'A',text:'a'});
  assert.equal(r.applied,true);
  assert.equal(x.target.value,'Helloa');
  assert.deepEqual(Array.from(x.state.committed),['Helloa']);
  assert.equal(x.dirty.length,1);
});
test('typewriter cannot rewrite a protected line even with native execCommand',()=>{
  const x=setup({text:'Locked',protectedText:true});
  const r=engine.apply(x.target,{char:'A',text:'a'});
  assert.equal(r.applied,false);
  assert.equal(x.target.value,'Locked');
  assert.deepEqual(Array.from(x.state.committed),['Locked']);
  assert.equal(x.state.lockedLines.has(0),true);
  assert.equal(x.dirty.length,0);
  assert.match(x.notices.at(-1).message,/Protected line/);
});