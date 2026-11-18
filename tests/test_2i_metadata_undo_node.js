'use strict';
// Guard Claude's no-data-loss undo fix while retaining Fable's full text undo.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const NarrativeCore=require('../2i/2i-assets/narrative-core.js');
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
    nativeFormatting:false,NarrativeCore,window:{twoiNarrativeHistory:null,twoiCreativeSession:null},
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

test('metadata undo remaps an existing lock after a new line is inserted before it',()=>{
  const x=fixture();
  x.committed=['A','PROTECTED','Z'];
  x.soloTextarea.value=x.committed.join('\n');
  x.lockedLines=new Set([1]);
  x.snapshot(true);
  x.committed=['New','A','PROTECTED','Z'];
  x.soloTextarea.value=x.committed.join('\n');
  x.lockedLines=new Set([2]);
  x.undo();
  assert.equal(x.soloTextarea.value,'New\nA\nPROTECTED\nZ');
  assert.deepEqual(Array.from(x.lockedLines),[2]);
  x.redo();
  assert.deepEqual(Array.from(x.lockedLines),[2]);
});
test('ambiguous chapter movement refuses undo without consuming the history',()=>{
  const x=fixture();
  x.committed=['A','B','C','D'];
  x.soloTextarea.value=x.committed.join('\n');
  x.chapters=[{title:'One',startLine:0},{title:'Two',startLine:2}];
  const notices=[];
  x.addChat=(who,message)=>notices.push({who,message});
  x.snapshot(true);
  x.committed=['A','Edited B','Edited C','D'];
  x.soloTextarea.value=x.committed.join('\n');
  x.undo();
  assert.equal(x.soloTextarea.value,'A\nEdited B\nEdited C\nD');
  assert.equal(x.undoStack.length,1);
  assert.equal(x.redoStack.length,0);
  assert.equal(x.chapters[1].startLine,2);
  assert.match(notices.at(-1).message,/chapter boundary/i);
});
