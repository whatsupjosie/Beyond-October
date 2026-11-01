"""Verify Foresight does not navigate away from unsaved 2i work."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_reload_requires_editor_close_handshake_and_rotates_session():
    source = (ROOT / 'static/foresight_programs.js').read_text(encoding='utf-8')
    function = source.split('    async function reload(c){', 1)[1].split('    // --- messages from the pages inside trays', 1)[0]
    assert 'await prepareClose(c)' in function
    assert 'if(!decision.canClose)' in function
    assert "c.type==='file'" in function
    assert 'c.sessionNonce=newId()' in function
    assert "url.searchParams.set('foresightSession',c.sessionNonce)" in function
    assert 'pending.reject(' in function


def test_reload_behaviour_with_node():
    source = (ROOT / 'static/foresight_programs.js').read_text(encoding='utf-8')
    body = source.split('    async function reload(c){', 1)[1].split('    // --- messages from the pages inside trays', 1)[0]
    script = r'''
const assert=require('node:assert/strict');
const {URL}=require('node:url');
const location={origin:'http://localhost:8080'};
const crypto={randomUUID:()=> 'new-nonce'};
const newId=()=>crypto.randomUUID();
const fileCommands=new Map();
const messages=[];
const toast=x=>messages.push(x);
const programFor=x=>({kind:x==='file'?'file':'page'});
const supportsLifecycle=c=>['file','twoi'].includes(c.type);
const urlOf=()=>'/writers-room';
let allowed=false;
const prepareClose=async()=>({canClose:allowed,reason:'unsaved work'});
const mountExternal=()=>{},mountRecordings=()=>{},mountVideo=()=>{};
const reload=async function(c){
''' + body + r'''
; (async()=>{
 const c={type:'file',data:{fileId:'original-id'},frame:{src:'/old'},title:'Draft',sessionNonce:'old-nonce'};
 assert.equal(await reload(c),false);
 assert.equal(c.frame.src,'/old','unsafe reload must not navigate');
 allowed=true;
 assert.equal(await reload(c),true);
 assert.equal(c.sessionNonce,'new-nonce');
 assert.equal(c.frame.src,'/writers-room?file=original-id&foresightSession=new-nonce');
 assert.equal(c.appReady,false);
 const twoi={type:'twoi',frame:{src:'/old'},title:'2i',sessionNonce:'old-nonce'};
 assert.equal(await reload(twoi),true);
 assert.equal(twoi.frame.src,'/writers-room?foresightSession=new-nonce');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
