'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const engine=require('../2i/2i-assets/typewriter-input.js');
class FakeEvent {
  constructor(type,info={}) { this.type=type;Object.assign(this,info);this.defaultPrevented=false; }
  preventDefault(){this.defaultPrevented=true;}
}
function fixture(value='hello',cursor=value.length) {
  const events=[];
  const doc={defaultView:{InputEvent:FakeEvent},execCommand(){return false;}};
  const editor={
    value,selectionStart:cursor,selectionEnd:cursor,disabled:false,readOnly:false,ownerDocument:doc,
    focus(){},
    setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;},
    setRangeText(text,start,end){
      this.value=this.value.slice(0,start)+text+this.value.slice(end);
      this.selectionStart=this.selectionEnd=start+text.length;
    },
    dispatchEvent(event){events.push(event.type);return !event.defaultPrevented;}
  };
  return {editor,doc,events};
}
test('touch key inserts at retained caret instead of appending',()=>{
  const f=fixture('abcd',2);
  assert.equal(engine.apply(f.editor,{char:'X',text:'x'},{selection:{start:2,end:2}}).applied,true);
  assert.equal(f.editor.value,'abxcd');
  assert.deepEqual(f.events,['beforeinput','input']);
});
test('typing over selection replaces selected text exactly once',()=>{
  const f=fixture('abcd',1);
  assert.equal(engine.apply(f.editor,{char:'Y',text:'y'},{selection:{start:1,end:3}}).applied,true);
  assert.equal(f.editor.value,'ayd');
});
test('return and space insert their actual characters',()=>{
  const f=fixture('Hi',2);
  engine.apply(f.editor,{char:'SPACE',text:' '});
  engine.apply(f.editor,{char:'RETURN',text:'\n'});
  assert.equal(f.editor.value,'Hi \n');
});
test('backspace removes previous whole grapheme, not part of an emoji',()=>{
  const text='a👩🏽‍💻';
  const f=fixture(text,text.length);
  engine.apply(f.editor,{char:'BACKSPACE',text:''});
  assert.equal(f.editor.value,'a');
});
test('Shift, invalid controls and read-only cannot modify the manuscript',()=>{
  const f=fixture();
  assert.equal(engine.apply(f.editor,{char:'SHIFT',text:''}).applied,false);
  assert.equal(engine.apply(f.editor,{char:'X',text:'\n\n'}).applied,false);
  f.editor.readOnly=true;
  assert.equal(engine.apply(f.editor,{char:'X',text:'x'}).applied,false);
  assert.equal(f.editor.value,'hello');
});
test('native browser insertText path avoids duplicate input events',()=>{
  const f=fixture('abc',1);
  f.doc.execCommand=(_,__,text)=>{
    f.editor.setRangeText(text,f.editor.selectionStart,f.editor.selectionEnd);
    f.events.push('native');return true;
  };
  engine.apply(f.editor,{char:'Q',text:'q'});
  assert.equal(f.editor.value,'aqbc');
  assert.deepEqual(f.events,['beforeinput','native']);
});
test('cancelled beforeinput prevents a fallback write',()=>{
  const f=fixture('abc');
  f.editor.dispatchEvent=event=>event.type!=='beforeinput';
  assert.equal(engine.apply(f.editor,{char:'X',text:'x'}).applied,false);
  assert.equal(f.editor.value,'abc');
});
test('cancelled beforeinput stops native insertion before execCommand runs',()=>{
  const f=fixture('protected',3);
  let writes=0;
  f.doc.execCommand=()=>{writes++;return true;};
  f.editor.dispatchEvent=event=>event.type!=='beforeinput';
  assert.equal(engine.apply(f.editor,{char:'X',text:'x'}).applied,false);
  assert.equal(writes,0);
  assert.equal(f.editor.value,'protected');
});
