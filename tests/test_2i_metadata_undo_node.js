'use strict';
// Guard Claude's no-data-loss undo fix while retaining Fable's full text undo.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/writers-room-v22.html'),'utf8');
function slice(begin,end){
  const a=source.indexOf(begin),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a,'Cannot find '+begin);
  return source.slice(a,b);
}
const undoCode=slice('function captureUndoPoint()', '// ── DIRTY / AUTOSAVE');
const actionCode=slice('function lockScene()', 'function numberToWord(');
function fixture(){
  const state={
    coWriting:false, committed:['Opening'], buffer:[], lockedLines:new Set(),
    chapters:[{title:'Chapter One',startLine:0}],undoStack:[],redoStack:[],MAX_UNDO:60,
    selectedIdx:null,editingIdx:null,generating:false,chatSending:false,playing:false,
    nativeFormatting:false,window:{twoiNarrativeHistory:null,twoiCreativeSession:null},
    soloTextarea:{value:'Opening',selectionStart:0},
    markDirty(){},render(){},addChat(){},numberToWord:n=>String(n),
    prompt:()=>null
  };
  vm.createContext(state);
  vm.runInContext(undoCode+'\n'+actionCode,state);
  return state;
}
function authorWritesMore(x){
  x.soloTextarea.value='Opening\nThe words the author added afterwards.';
  x.committed=x.soloTextarea.value.split('\n');
}
test('undo/redo of a scene lock never erases writing entered after the lock',()=>{
  const x=fixture();
  x.lockAll();
  assert.equal(x.lockedLines.has(0),true);
  authorWritesMore(x);
  x.undo();
  assert.equal(x.lockedLines.size,0);
  assert.equal(x.soloTextarea.value,'Opening\nThe words the author added afterwards.');
  x.redo();
  assert.equal(x.lockedLines.has(0),true);
  assert.equal(x.soloTextarea.value,'Opening\nThe words the author added afterwards.');
});
test('undo/redo of chapter metadata preserves all later writing',()=>{
  const x=fixture();
  x.prompt=(message)=>message.startsWith('Chapter title')?'Second Chapter':'';
  x.newChapter();
  assert.equal(x.chapters.length,2);
  authorWritesMore(x);
  x.undo();
  assert.equal(x.chapters.length,1);
  assert.equal(x.soloTextarea.value,'Opening\nThe words the author added afterwards.');
  x.redo();
  assert.equal(x.chapters.length,2);
  assert.equal(x.soloTextarea.value,'Opening\nThe words the author added afterwards.');
});
test('a real text snapshot still rolls back text, unlike metadata-only actions',()=>{
  const x=fixture();
  x.snapshot();
  x.committed=['Changed'];
  x.soloTextarea.value='Changed';
  x.undo();
  assert.equal(x.soloTextarea.value,'Opening');
  x.redo();
  assert.equal(x.soloTextarea.value,'Changed');
});
