'use strict';
/* ForesightFiles owns file-tray input, autosave and background flushing.
 * Reach must never auto-create a separate manuscript in this route. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reach.js'),'utf8');
function section(start,end){
  const i=source.indexOf(start),j=source.indexOf(end,i);
  assert.ok(i>=0&&j>i,'Missing source: '+start);
  return source.slice(i,j);
}
const startup=section('const networked = location.protocol', '// Autosave history belongs');
const dirty=section('function markDirty() {', 'async function writeAutosave()');
const visibility=section("document.addEventListener('visibilitychange',()=>{", '// Associate the donor');
const saveStart=source.indexOf('async function saveDocument() {');
const saveEnd=source.indexOf('\n}\n',saveStart);
assert.ok(saveStart>=0&&saveEnd>saveStart);
const defaultSave=source.slice(saveStart,saveEnd+3);

test('file-route editor fields and Save button remain locked before file mount',()=>{
  const btn={disabled:false},solo={readOnly:false},draft={readOnly:false};
  const c={location:{protocol:'http:'},reachFileMode:'file-id',
    soloTextarea:solo,draftArea:draft,$:()=>btn};
  vm.runInNewContext(startup,c);
  assert.equal(solo.readOnly,true);
  assert.equal(draft.readOnly,true);
  assert.equal(btn.disabled,true);
});
test('normal Reach editor is never locked by file-tray startup protection',()=>{
  const btn={disabled:false},solo={readOnly:false},draft={readOnly:false};
  vm.runInNewContext(startup,{location:{protocol:'http:'},reachFileMode:null,
    soloTextarea:solo,draftArea:draft,$:()=>btn});
  assert.equal(solo.readOnly,false);assert.equal(draft.readOnly,false);
  assert.equal(btn.disabled,false);
});
function dirtyTest(file){
  const timers=[],c={
    reachFileMode:file?'file-id':null,initializing:false,documentDirty:false,
    recoverySafe:true,mutation:0,saveConflict:false,
    recoveryTimer:null,serverTimer:null,
    setSaveStatus(){},clearTimeout(){},
    setTimeout(_fn,delay){timers.push(delay);return delay;},
    writeRecovery(){},saveDocument(){},
    document:{dispatchEvent(){}},Event:class{constructor(type){this.type=type}}
  };
  vm.createContext(c);vm.runInContext(dirty,c);c.markDirty();
  return {timers,c};
}
test('markDirty in a Foresight file never schedules Reach server autosave',()=>{
  const f=dirtyTest(true);
  assert.deepEqual(f.timers,[120]); // browser recovery timer remains safe
  assert.equal(f.c.documentDirty,true);
});
test('normal Reach manuscript still schedules its original autosave',()=>{
  assert.deepEqual(dirtyTest(false).timers,[120,1000]);
});
test('default Reach saveDocument refuses file-tray writes even without initializing',async()=>{
  const c={reachFileMode:'file-id',initializing:false};
  vm.createContext(c);vm.runInContext(defaultSave,c);
  assert.equal(await c.saveDocument(),false);
});
test('visibilitychange does not invoke Reach backup or saver for a file tray',()=>{
  const calls=[],listeners={};
  const c={reachFileMode:'file-id',document:{hidden:true,addEventListener:(t,fn)=>listeners[t]=fn},
    writeRecovery:()=>calls.push('Reach recovery'),saveDocument:()=>calls.push('Reach save')};
  vm.runInNewContext(visibility,c);
  listeners.visibilitychange();
  assert.deepEqual(calls,[]);
});
test('normal Reach background saving remains unchanged',()=>{
  const calls=[],listeners={};
  const c={reachFileMode:null,document:{hidden:true,addEventListener:(t,fn)=>listeners[t]=fn},
    writeRecovery:()=>calls.push('Reach recovery'),saveDocument:()=>calls.push('Reach save')};
  vm.runInNewContext(visibility,c);listeners.visibilitychange();
  assert.deepEqual(calls,['Reach recovery','Reach save']);
});
