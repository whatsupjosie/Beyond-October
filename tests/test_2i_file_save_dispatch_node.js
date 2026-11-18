'use strict';
/* Save buttons, File menu and Ctrl+S all invoke reach.js saveNow().
 * A Foresight file must never fall back to saving as a Reach manuscript
 * while its own asynchronous file session is still mounting. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reach.js'),'utf8');
const start=source.indexOf('function saveNow() {');
const end=source.indexOf('async function preserveBeforeSwitch()',start);
assert.ok(start>=0&&end>start,'Actual Reach saveNow function must exist');
const code=source.slice(start,end);

function harness({file=false,networked=true,mounted=false,fail=false,disabled=false}={}){
  const calls=[];
  const state={
    reachFileMode:file?'file-id':null,
    networked,
    $:id=>id==='saveBtn'?{disabled}:null,
    window:{foresightFileSession:mounted?{save(){calls.push('file-session');return fail?Promise.reject(Error('Disk full')):Promise.resolve(true);}}:undefined},
    setSaveStatus:message=>calls.push({status:message}),
    saveToFile:()=>{calls.push('native-file-picker');return Promise.resolve(true);},
    saveDocument:()=>{calls.push('Reach manuscript save');return Promise.resolve(true);}
  };
  if(mounted)state.saveDocument=()=>state.window.foresightFileSession.save();
  vm.createContext(state);
  vm.runInContext(code,state);
  return {save:()=>state.saveNow(),calls};
}

test('normal hosted writer still saves via Reach',async()=>{
  const x=harness();assert.equal(await x.save(),true);
  assert.deepEqual(x.calls,['Reach manuscript save']);
});
test('normal offline writer still uses its own downloadable file save',async()=>{
  const x=harness({networked:false});assert.equal(await x.save(),true);
  assert.deepEqual(x.calls,['native-file-picker']);
});
for(const online of [true,false]){
  test('file tray refuses '+(online?'hosted':'offline')+' Save before file session mounts',async()=>{
    const x=harness({file:true,networked:online});
    assert.equal(await x.save(),false);
    assert.equal(x.calls.length,1);
    assert.match(x.calls[0].status,/Opening Foresight file/);
  });
  test('file tray uses its mounted file session '+(online?'hosted':'offline'),async()=>{
    const x=harness({file:true,networked:online,mounted:true});
    assert.equal(await x.save(),true);
    assert.deepEqual(x.calls,['file-session']);
  });
}

test('failed file-session Save announces failure instead of producing unhandled rejection',async()=>{
  const x=harness({file:true,networked:true,mounted:true,fail:true});
  assert.equal(await x.save(),false);
  assert.equal(x.calls[0],'file-session');
  assert.match(x.calls[1].status,/Foresight file not saved/);
  assert.match(x.calls[1].status,/Disk full/);
});

test('Ctrl+S cannot overwrite a failed-mount recovery notice with a false opening status',async()=>{
  const x=harness({file:true,networked:true,mounted:false,disabled:true});
  assert.equal(await x.save(),false);
  assert.deepEqual(x.calls,[]);
});
test('button, File menu and Ctrl+S are wired to the guarded dispatcher',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../2i/writers-room-v22.html'),'utf8');
  assert.match(source, /\$\('saveBtn'\)\.onclick=\(\)=>saveNow\(\)/);
  assert.match(html, /if\(action==='save'\)\{if\(typeof saveNow==='function'\)saveNow\(\)/);
  assert.match(html, /if\(key==='s'\)return 'save'/);
});
