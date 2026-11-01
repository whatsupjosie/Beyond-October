const {JSDOM}=require('jsdom');
const fs=require('fs');
const assert=require('node:assert/strict');
const root=process.argv[2] || require('path').resolve(__dirname,'..');
const html=fs.readFileSync(root+'/static/pubpartner.html','utf8');
const dom=new JSDOM(html,{url:'http://127.0.0.1:8000/pubpartner',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
w.Headers=Headers;w.Request=Request;w.Response=Response;
w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
w.sessionStorage.setItem('pubcast_token','synthetic-token');
w.sessionStorage.setItem('pubcast_user',JSON.stringify({username:'owner',role:'owner'}));
const errors=[];w.addEventListener('error',e=>errors.push(e.message));
let configResolve;let live=[];let sessionCalls=0;
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
w.fetch=async(url,options={})=>{
 const path=new URL(typeof url==='string'?url:url.url,w.location.href).pathname;
 if(path==='/api/auth/status')return response({auth_enforced:true,setup_required:false});
 if(path==='/api/auth/verify')return response({username:'owner',role:'owner'});
 if(path==='/api/pubpartner/providers/local-config')return new Promise(r=>{configResolve=r});
 if(path==='/api/pubpartner/sessions'){sessionCalls++;return response({friend:{name:'Alex'}})}
 if(path==='/api/pubpartner/turns/live')return new Promise(resolve=>live.push({body:JSON.parse(options.body),resolve}));
 return response({ok:true,lessons:[],encounters:[],models:[],credentials:[],providers:{},friends:[],items:[]});
};
function tick(){return new Promise(r=>setTimeout(r,15))}
(async()=>{
 try{
 w.eval(fs.readFileSync(root+'/static/reach_auth.js','utf8'));
 w.eval(fs.readFileSync(root+'/static/pubpartner.js','utf8'));
 await tick();
 assert.ok(configResolve,'startup requested local configuration');
 const $=id=>w.document.getElementById(id);
 $('message').value='  Exact first message\n';$('send').click();$('send').click();await tick();
 assert.equal(live.length,0,'send waits for local config');
 configResolve(response({enabled:true,provider:{provider:'openai_compatible',model:'smollm2',base_url:'http://127.0.0.1:8081/v1'}}));
 await tick();assert.equal(live.length,1,'double send is suppressed');
 assert.equal(live[0].body.message,'  Exact first message\n');
 assert.equal(live[0].body.provider.model,'smollm2');assert.equal(live[0].body.prompt_mode,'full');
 live[0].resolve(response({ok:true,friend_response:'First answer',provider_result:{ok:true}}));await tick();
 $('message').value='Second message';$('send').click();await tick();
 assert.equal(live[1].body.history[0].content,'  Exact first message\n');
 const oldId=$('sessionId').value;$('newSession').click();await tick();
 assert.notEqual($('sessionId').value,oldId,'new session creates a new id');
 live[1].resolve(response({ok:true,friend_response:'STALE REPLY MUST NOT APPEAR',provider_result:{ok:true}}));await tick();
 assert.ok(!$('messages').textContent.includes('STALE REPLY'));
 $('message').value='Keep this draft';$('send').click();await tick();
 assert.equal(live[2].body.history.length,0,'new session has no old history');
 live[2].resolve(response({provider_result:{error:'model interrupted'},fcp1:{private:'SHOULD NOT DISPLAY'}},503));await tick();
 assert.equal($('message').value,'Keep this draft');
 assert.ok(!$('messages').textContent.includes('SHOULD NOT DISPLAY'));
 assert.equal($('send').disabled,false);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({passed:true,checks:['configuration gate','duplicate-send guard','exact source and history','new session id','late-reply isolation','draft recovery','safe error display','button recovery'],sessionCalls}));
 }finally{w.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
