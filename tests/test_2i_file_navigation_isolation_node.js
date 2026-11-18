'use strict';
/* Foresight file-tray operations must not leak into the distinct Reach
 * manuscript collection while loading or after a file session is mounted. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const reach=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reach.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../2i/writers-room-v22.html'),'utf8');

function until(start,end) {
  const a=reach.indexOf(start),b=reach.indexOf(end,a);
  assert.ok(a>=0 && b>a,'Expected Reach functions to remain present: '+start);
  return reach.slice(a,b);
}
const saveCopy=until('function blockReachFileOperation(', 'async function exportManuscript()');
const newOpen=until('async function openDocument()', 'function restoreConversation()');
const shelfStart=reach.indexOf('async function showShelf()');
const shelfEnd=reach.indexOf('\n}\n',shelfStart);
assert.ok(shelfStart>=0 && shelfEnd>shelfStart);
const shelf=reach.slice(shelfStart,shelfEnd+3);

function fixture({mounted=false,file=true}={}){
  const calls=[],notices=[];
  const state={
    reachFileMode:file?'file-123':null,
    window:{foresightFileSession:mounted?{}:null},
    networked:true,
    addChat:(who,text)=>notices.push({who,text}),
    writeRecovery(){calls.push('writeRecovery')},
    downloadFile(){calls.push('downloadFile')},
    saveDocument(){calls.push('Reach save');return Promise.resolve(true)},
    preserveBeforeSwitch(){calls.push('Reach manuscript switch');return Promise.resolve(true)},
    document:{createElement(){calls.push('pick file');return {click(){}}}},
    $:()=>{calls.push('Reach shelf element');return {replaceChildren(){}}},
    api:async()=>{calls.push('Reach manuscript list');return {documents:[]}}
  };
  vm.createContext(state);
  vm.runInContext(saveCopy+'\n'+newOpen+'\n'+shelf,state);
  return {state,calls,notices};
}
test('pre-mount Foresight new/open/save-as/shelf never touch Reach state',async()=>{
  const f=fixture();
  await f.state.newDocument();
  await f.state.openDocument();
  await f.state.saveDocumentAs();
  await f.state.showShelf();
  assert.deepEqual(f.calls,[]);
  assert.equal(f.notices.length,4);
  for(const n of f.notices)assert.match(n.text,/Finish opening this Foresight file/);
});
test('original Reach commands remain fenced after Foresight session mounts',async()=>{
  const f=fixture({mounted:true});
  await f.state.newDocument();
  await f.state.openDocument();
  await f.state.saveDocumentAs();
  await f.state.showShelf();
  assert.deepEqual(f.calls,[]);
  assert.equal(f.notices.length,4);
  for(const n of f.notices)assert.match(n.text,/Use the Foresight file controls/);
});
test('normal Reach authoring path is not blocked',()=>{
  const f=fixture({file:false});
  assert.equal(f.state.blockReachFileOperation('open another document'),false);
  assert.deepEqual(f.calls,[]);
  assert.deepEqual(f.notices,[]);
});
test('Foresight document hides Reach-specific manuscript shelf control',()=>{
  assert.match(reach,/if\(reachFileMode\)\$\('shelfBtn'\)\.style\.display='none'/);
});
test('drop before Foresight file mount cannot import into Reach manuscript',async()=>{
  const a=html.indexOf("document.addEventListener('drop', async e => {");
  const b=html.indexOf('\n});\n\ninit();',a);
  assert.ok(a>=0&&b>a);
  const handlers={},calls=[],notices=[];
  const state={
    reachFileMode:'file-123',
    document:{addEventListener:(name,fn)=>handlers[name]=fn},
    addChat:(who,text)=>notices.push({who,text}),
    importDocument:async()=>calls.push('Reach import')
  };
  vm.createContext(state);
  vm.runInContext(html.slice(a,b+4),state);
  let prevented=false;
  await handlers.drop({preventDefault(){prevented=true},dataTransfer:{files:[{name:'other.2i'}]}});
  assert.equal(prevented,true);
  assert.deepEqual(calls,[]);
  assert.match(notices[0].text,/Finish opening this Foresight file/);
});
