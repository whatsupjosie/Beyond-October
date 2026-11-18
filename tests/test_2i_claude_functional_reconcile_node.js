'use strict';
/* Integration regression: Claude's usability fixes alongside Fable's manuscript engine.
 * Run: node --test tests/test_2i_claude_functional_reconcile_node.js
 * Extracts the actual functions/handlers from the served 2i source.
 */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../2i/writers-room-v22.html'),'utf8');
const reach=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reach.js'),'utf8');
function section(source,start,end) {
  const a=source.indexOf(start),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a,'Source section must exist: '+start);
  return source.slice(a,b);
}

function editing() {
  let snapshots=0,dirty=0,renders=0;
  const messages=[];
  const state={
    lockedLines:new Set([1]),coWriting:false,selectedIdx:null,
    soloTextarea:{value:'Keep\nProtected\nTail',selectionStart:7},
    chapters:[{startLine:0}],committed:['Keep','Protected','Tail'],buffer:[],
    numberToWord:n=>String(n),
    prompt:()=>null, snapshot:()=>snapshots++,markDirty:()=>dirty++,
    render:()=>renders++,addChat:(role,message)=>messages.push({role,message})
  };
  vm.createContext(state);
  vm.runInContext(section(html,'function unlockSelected()','function numberToWord('),state);
  return {state,messages,counts:()=>({snapshots,dirty,renders})};
}

test('Write-mode cursor unlocks only the matching protected paragraph',()=>{
  const x=editing();
  x.state.soloTextarea.selectionStart='Keep\n'.length+2;
  x.state.unlockSelected();
  assert.equal(x.state.lockedLines.has(1),false);
  assert.equal(x.counts().snapshots,1);
  assert.equal(x.counts().dirty,1);
});
test('Unnecessary unlock creates neither dirty state nor undo entry',()=>{
  const x=editing();
  x.state.soloTextarea.selectionStart=2;
  x.state.unlockSelected();
  assert.equal(x.state.lockedLines.has(1),true);
  assert.equal(x.counts().snapshots,0);
  assert.equal(x.counts().dirty,0);
  assert.equal(x.messages.at(-1).role,'notice');
});
test('Cancel New Chapter does not create an undo entry',()=>{
  const x=editing();
  x.state.newChapter();
  assert.equal(x.counts().snapshots,0);
  assert.equal(x.state.chapters.length,1);
});

function replacing({narrative=false}={}) {
  let snapshots=0,dirty=0,renders=0;
  const fields={frFind:{value:'cat'},frReplace:{value:'dog'},frResult:{textContent:'',className:''},frReplaceAllBtn:{}};
  const state={
    $:id=>fields[id],window:{twoiNarrativeHistory:narrative?{}:null},
    committed:['cat cat','locked cat','cat'],buffer:[],lockedLines:new Set([1]),
    soloTextarea:{value:'cat cat\nlocked cat\ncat'},coWriting:false,
    reading:null,generating:false,chatSending:false,editingIdx:null,playing:false,
    stopPlaying(){},snapshot:()=>snapshots++,markDirty:()=>dirty++,render:()=>renders++
  };
  vm.createContext(state);
  vm.runInContext(section(html,"$('frReplaceAllBtn').onclick = () => {",'// ── CONTEXT MENU'),state);
  return {state,fields,counts:()=>({snapshots,dirty,renders})};
}
test('Fallback Replace All counts once and never changes locked lines',()=>{
  const x=replacing();
  x.state.$('frReplaceAllBtn').onclick();
  assert.equal(x.state.soloTextarea.value,'dog dog\nlocked cat\ndog');
  assert.equal(x.state.committed.join('\n'),x.state.soloTextarea.value);
  assert.equal(x.state.lockedLines.has(1),true);
  assert.match(x.fields.frResult.textContent,/3 replacements made/);
  assert.match(x.fields.frResult.textContent,/1 in locked lines/);
  assert.equal(x.counts().snapshots,1);
});
test('Fallback Replace All with no applicable changes leaves manuscript clean',()=>{
  const x=replacing();
  x.fields.frFind.value='locked cat';
  x.state.$('frReplaceAllBtn').onclick();
  assert.equal(x.state.soloTextarea.value,'cat cat\nlocked cat\ncat');
  assert.equal(x.counts().snapshots,0);
  assert.equal(x.counts().dirty,0);
});
test('Fable narrative protection remains active when its engine is available',()=>{
  const x=replacing({narrative:true});
  x.state.$('frReplaceAllBtn').onclick();
  assert.equal(x.state.soloTextarea.value,'dog dog\nlocked cat\ndog');
  assert.equal(x.state.lockedLines.has(1),true);
  assert.match(x.fields.frResult.textContent,/3 replacement\(s\) made/);
});

test('Native Ctrl+Z stays in ordinary text fields but not manuscript-only line edits',()=>{
  let listener;
  const editor={tagName:'INPUT',isContentEditable:false,closest:()=>null};
  const state={
    document:{
      activeElement:editor,
      addEventListener:(name,handler,capture)=>{if(name==='keydown'&&capture)listener=handler;}
    },
    $:()=>({classList:{contains:()=>false}})
  };
  vm.createContext(state);
  vm.runInContext(section(reach,'// Native undo belongs','// Drop is handled once'),state);
  assert.equal(typeof listener,'function');
  let stopped=0;
  const evt={key:'z',ctrlKey:true,metaKey:false,stopImmediatePropagation:()=>stopped++};
  listener(evt);assert.equal(stopped,1);
  editor.closest=()=>({className:'m-line-edit'});
  listener(evt);assert.equal(stopped,1);
});
