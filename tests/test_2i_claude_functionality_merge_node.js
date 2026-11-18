'use strict';
/**
 * Integration regressions for Claude's 2i editor fixes carried into Fable's
 * later editor. Run: node --test tests/test_2i_claude_functionality_merge_node.js
 * Extracts the functions actually served by v22; no reimplemented editor logic.
 */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'../2i');
const page=fs.readFileSync(path.join(root,'writers-room-v22.html'),'utf8');
const reach=fs.readFileSync(path.join(root,'2i-assets/reach.js'),'utf8');

function take(src,from,until){
  const start=src.indexOf(from),end=src.indexOf(until,start);
  assert.ok(start>=0&&end>start, 'Missing served implementation: '+from);
  return src.slice(start,end);
}
function fixture(){
  const notes=[],events=[];
  const context={
    committed:['First.'],buffer:[],lockedLines:new Set(),
    chapters:[{title:'Chapter One',subtitle:'',startLine:0}],
    undoStack:[],redoStack:[],MAX_UNDO:60,coWriting:false,
    nativeFormatting:false,manuscriptFormat:{token:'new'},
    selectedIdx:null,editingIdx:null,generating:false,chatSending:false,playing:false,
    soloTextarea:{value:'First.',selectionStart:0,selectionEnd:0},
    window:{twoiCreativeSession:{record:kind=>events.push(kind)}},
    addChat:(role,message)=>notes.push({role,message}),
    markDirty:()=>{},render:()=>{},
    prompt:()=>null,numberToWord:()=> 'Two',
    keepChapterPositions:(before,after)=>{}, // chapter zero is invariant in these scenarios
    NarrativeCore:{remapProtected:(before,after,protectedLines)=>{
      let first=0,last=0;
      while(first<before.length&&first<after.length&&before[first]===after[first])first++;
      while(last<before.length-first&&last<after.length-first&&before[before.length-last-1]===after[after.length-last-1])last++;
      const oldEnd=before.length-last,delta=after.length-before.length;
      return [...protectedLines].map(i=>{
        if(i<first)return i;
        if(i>=oldEnd)return i+delta;
        throw Error('Protected line changed');
      });
    }}
  };
  vm.createContext(context);
  vm.runInContext(take(page,'function captureUndoPoint()','// ── DIRTY / AUTOSAVE'),context);
  vm.runInContext(take(page,'function lockScene()','function numberToWord(n)'),context);
  return {context,notes,events};
}
test('undoing a lock in Write mode retains every character typed since it',()=>{
  const {context:c}=fixture();
  c.lockScene();
  assert.deepEqual([...c.lockedLines],[0]);
  c.soloTextarea.value='First.\nA paragraph written after the lock.';
  c.committed=['First.','A paragraph written after the lock.'];
  c.undo();
  assert.deepEqual([...c.lockedLines],[]);
  assert.equal(c.soloTextarea.value,'First.\nA paragraph written after the lock.');
  assert.deepEqual(Array.from(c.committed),['First.','A paragraph written after the lock.']);
  c.redo();
  assert.deepEqual([...c.lockedLines],[0]);
  assert.equal(c.soloTextarea.value,'First.\nA paragraph written after the lock.');
});
test('Write-mode unlock acts on the caret line, not a stale Collab selection',()=>{
  const {context:c}=fixture();
  c.soloTextarea.value='A\nB\nC';c.committed=['A','B','C'];
  c.lockedLines=new Set([0,1,2]);c.soloTextarea.selectionStart=3;
  c.unlockSelected();
  assert.deepEqual([...c.lockedLines],[0,2]);
  assert.equal(c.committed.join('\n'),'A\nB\nC');
});
test('cancelling the chapter dialog creates no undo point',()=>{
  const {context:c}=fixture();
  c.prompt=()=>null;
  c.newChapter();
  assert.equal(c.undoStack.length,0);
  assert.equal(c.chapters.length,1);
});
test('manuscript shortcut owner preserves every native text-field undo',()=>{
  const s=take(page,'function manuscriptShortcut(',"\ndocument.addEventListener('keydown',e=>{");
  const shortcut=vm.runInNewContext('('+s+')');
  for(const key of ['z','Z','y']){
    for(const shiftKey of [false,true]){
      assert.equal(shortcut({key,ctrlKey:true,shiftKey},{nativeTextField:true}),null);
    }
  }
  assert.equal(shortcut({key:'z',ctrlKey:true},{nativeTextField:false}),'undo');
  assert.equal(shortcut({key:'z',ctrlKey:true,shiftKey:true},{nativeTextField:false}),'redo');
});
test('Reach capture guard stops Ctrl+Z in Find and Rename, not Save',()=>{
  const s=take(reach,"// Preserve native undo in EVERY text entry",'// Drop is handled once');
  let callback=null;
  const c={
    document:{
      activeElement:null,
      addEventListener:(name,fn,capture)=>{
        assert.equal(name,'keydown');assert.equal(capture,true);callback=fn;
      }
    },
    $:()=>({classList:{contains:()=>false}})
  };
  vm.runInNewContext(s,c);
  function event(tag,key,inline=false){
    let stops=0;
    c.document.activeElement={tagName:tag,isContentEditable:false,closest:selector=>selector==='.m-line-edit'&&inline?{}:null};
    callback({key,ctrlKey:true,metaKey:false,stopImmediatePropagation:()=>stops++,preventDefault:()=>{}});
    return stops;
  }
  assert.equal(event('INPUT','z'),1);
  assert.equal(event('SELECT','y'),1);
  assert.equal(event('TEXTAREA','Z'),1);
  assert.equal(event('INPUT','s'),0);
  assert.equal(event('TEXTAREA','z',true),0);
  assert.equal(event('DIV','z'),0);
});
test('standalone Replace All counts once and never edits protected lines',()=>{
  const elements={
    frReplaceAllBtn:{},frFind:{value:'cat'},frReplace:{value:'fox'},
    frResult:{textContent:'',className:''}
  };
  const c={
    $:name=>elements[name],window:{twoiNarrativeHistory:null},
    committed:['the cat sat','the cat is locked','a cat and a cat'],
    buffer:[],lockedLines:new Set([1]),coWriting:false,
    soloTextarea:{value:'the cat sat\nthe cat is locked\na cat and a cat'},
    reading:null,generating:false,chatSending:false,editingIdx:null,playing:false,
    snapshot:()=>{},markDirty:()=>{},render:()=>{}
  };
  vm.runInNewContext(take(page,"$('frReplaceAllBtn').onclick = () => {",'// ── CONTEXT MENU'),c);
  elements.frReplaceAllBtn.onclick();
  assert.equal(c.soloTextarea.value,'the fox sat\nthe cat is locked\na fox and a fox');
  assert.equal(c.committed.join('\n'),c.soloTextarea.value);
  assert.equal(elements.frResult.textContent,'3 replacements made; 1 in locked lines left as they are');
});
