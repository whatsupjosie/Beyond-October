const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('../node_modules/jsdom');
const root=path.resolve(__dirname,'..');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function setup(){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'static/human_contacts.html'),'utf8'),{url:'http://pubcast.test/static/human_contacts.html',runScripts:'outside-only'}),w=dom.window;
 w.ReachAuth={requireSession:async()=>({authenticated:true}),verify:async()=>({valid:true}),getUser:()=>({username:'me'}),websocketURL:target=>'ws://pubcast.test'+target};
 w.fetch=async url=>({ok:true,json:async()=>url.endsWith('/active')?{rooms:[{other_user:'one',dm_room:'dm____me____one'},{other_user:'two',dm_room:'dm____me____two'}]}:url.endsWith('/pending')?{requests:[]}:{people:[]}});
 const sockets=[];w.WebSocket=class {static OPEN=1;constructor(){this.readyState=1;this.sent=[];sockets.push(this);}close(){this.readyState=3;this.onclose?.();}send(value){this.sent.push(JSON.parse(value));}};
 w.eval(fs.readFileSync(path.join(root,'static/human_contacts.js'),'utf8'));await tick();await tick();
 const opens=[...w.document.querySelectorAll('#active button')].filter(b=>b.textContent==='Open conversation');
 return {dom,w,sockets,open:async index=>{opens[index].click();await tick();},type:value=>{w.document.getElementById('text').value=value;w.document.getElementById('text').dispatchEvent(new w.Event('input'));}};
}

test('a late old-room frame never appears in the new conversation',async()=>{
 const ui=await setup();try{await ui.open(0);const old=ui.sockets[0];await ui.open(1);old.onmessage({data:JSON.stringify({type:'chat',payload:{user:'one',text:'OLD ROOM FRAME'}})});assert(!ui.w.document.getElementById('log').textContent.includes('OLD ROOM FRAME'));}finally{ui.dom.window.close();}
});
test('private drafts stay with their own conversation',async()=>{
 const ui=await setup();try{await ui.open(0);ui.type('Private first draft');await ui.open(1);assert.equal(ui.w.document.getElementById('text').value,'');ui.type('Other draft');await ui.open(0);assert.equal(ui.w.document.getElementById('text').value,'Private first draft');}finally{ui.dom.window.close();}
});
test('unconfirmed text survives reconnect and retries with the same receipt identity',async()=>{
 const ui=await setup();try{await ui.open(0);ui.type('Keep until acknowledged');const send=()=>ui.w.document.getElementById('send').dispatchEvent(new ui.w.Event('submit',{cancelable:true}));send();const original=ui.sockets[0].sent[0];assert.equal(ui.w.document.getElementById('text').value,original.text);ui.sockets[0].close();await ui.open(0);send();const retry=ui.sockets[1].sent[0];assert.equal(retry.client_message_id,original.client_message_id);ui.sockets[1].onmessage({data:JSON.stringify({type:'chat_receipt',payload:{client_message_id:original.client_message_id}})});assert.equal(ui.w.document.getElementById('text').value,'');assert(!ui.w.document.querySelector('#send button').disabled);}finally{ui.dom.window.close();}
});
test('a lost receipt releases the editor and retry preserves the message ID',async()=>{
 const ui=await setup();try{
  const callbacks=[];const schedule=ui.w.setTimeout.bind(ui.w);
  ui.w.setTimeout=(fn,delay,...args)=>{if(delay===15000){callbacks.push(fn);return 9876;}return schedule(fn,delay,...args);};
  await ui.open(0);ui.type('Network lost the acknowledgement');
  const send=()=>ui.w.document.getElementById('send').dispatchEvent(new ui.w.Event('submit',{cancelable:true}));
  send();const original=ui.sockets[0].sent[0];
  assert.equal(callbacks.length,1,'send needs an acknowledgement deadline');callbacks[0]();
  assert(!ui.w.document.querySelector('#send button').disabled);
  assert(ui.w.document.getElementById('status').textContent.includes('not confirmed'));
  send();assert.equal(ui.sockets[0].sent[1].client_message_id,original.client_message_id);
 }finally{ui.dom.window.close();}
});
