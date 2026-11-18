'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Keys=require('../2i/2i-assets/typewriter-key-bridge.js');

function editor(value='',start=value.length,end=start){
  let focusCalls=0,commands=[];
  const field={
    tagName:'TEXTAREA',value,readOnly:false,disabled:false,
    selectionStart:start,selectionEnd:end,
    focus(){focusCalls++;},
    setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;}
  };
  const document={execCommand(name,ignored,text){
    commands.push({name,text});
    if(name!=='insertText'&&name!=='delete')return false;
    const a=field.selectionStart,b=field.selectionEnd;
    const replacement=name==='delete'?'':text;
    field.value=field.value.slice(0,a)+replacement+field.value.slice(b);
    field.setSelectionRange(a+replacement.length,a+replacement.length);
    return true;
  }};
  return {field,document,commands,focusCalls:()=>focusCalls};
}
test('Claude key and carriage return events insert into the real editor',()=>{
  const e=editor('One');
  assert.equal(Keys.write(e.document,e.field,{char:'SPACE',text:' '}),true);
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'A'}),true);
  assert.equal(Keys.write(e.document,e.field,{char:'RETURN',text:'\n'}),true);
  assert.equal(e.field.value,'One A\n');
  assert.deepEqual(e.commands.map(x=>x.name),['insertText','insertText','insertText']);
});
test('Backspace removes a selected range or one full Unicode grapheme',()=>{
  const emoji='Hi 👩‍💻';
  const e=editor(emoji);
  assert.equal(Keys.write(e.document,e.field,{char:'BACKSPACE'}),true);
  assert.equal(e.field.value,'Hi ');
  const range=editor('Alpha beta',6,10);
  assert.equal(Keys.write(range.document,range.field,{char:'BACKSPACE'}),true);
  assert.equal(range.field.value,'Alpha ');
});
test('typing replaces selected words and retains caret position',()=>{
  const e=editor('abcDEFghi',3,6);
  assert.equal(Keys.write(e.document,e.field,{char:'X',text:'x'}),true);
  assert.equal(e.field.value,'abcxghi');
  assert.equal(e.field.selectionStart,4);
});
test('Shift and blank keys never mutate the manuscript',()=>{
  const e=editor('keep');
  assert.equal(Keys.write(e.document,e.field,{char:'SHIFT',text:''}),false);
  assert.equal(Keys.write(e.document,e.field,{char:'BLANK',text:''}),false);
  assert.equal(Keys.write(e.document,e.field,{char:'?',text:''}),false);
  assert.equal(e.field.value,'keep');
  assert.equal(e.commands.length,0);
});
test('read-only, disabled and non-textarea targets fail closed',()=>{
  const e=editor('keep');
  e.field.readOnly=true;
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'A'}),false);
  e.field.readOnly=false;e.field.disabled=true;
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'A'}),false);
  e.field.disabled=false;e.field.tagName='DIV';
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'A'}),false);
  assert.equal(e.commands.length,0);
});
test('unsupported commands, control bytes and bulk payloads are ignored',()=>{
  const e=editor('keep');
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'x'.repeat(17)}),false);
  assert.equal(Keys.write(e.document,e.field,{char:'A',text:'\u0000'}),false);
  assert.equal(Keys.write({},e.field,{char:'A',text:'x'}),false);
  assert.equal(e.field.value,'keep');
  assert.equal(e.commands.length,0);
});
