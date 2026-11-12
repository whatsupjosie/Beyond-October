(function(){
'use strict';
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search),mode=query.get('mode')||'join';
const message=value=>{$('status').textContent=value;};
let prepared=null,popup=null,homeOrigin=null,pollTimer=null,polling=false;
const consent={tos:true,recording:true,ai_disclosure:true,data_processing:true};
async function api(path,body){
 const response=await fetch('/api/guests/'+path.replace(/^\//,''),{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000),cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The visit request failed ('+response.status+')');
 return {data,response};
}
function origin(value){const u=new URL(value);if(!['https:','http:'].includes(u.protocol)||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('Use your PubCast address without a page path');return u.origin;}
function restorePrepared(){try{prepared=JSON.parse(sessionStorage.getItem('pubcast.visit.pending')||'null');if(prepared){$('challengeOut').value=JSON.stringify(prepared.challenge);$('prepared').hidden=false;}}catch(_){prepared=null;}}
async function poll(){
 if(!prepared||polling)return;polling=true;clearTimeout(pollTimer);
 try{const {data}=await api('/status',{poll_token:prepared.poll_token});
  if(data.access_token){ReachAuth.saveSession(data);sessionStorage.removeItem('pubcast.visit.pending');prepared=null;$('enter').hidden=false;message('Your host approved your visit. You can enter the studio.');}
  else if(['denied','expired'].includes(data.status)){sessionStorage.removeItem('pubcast.visit.pending');prepared=null;message(data.status==='denied'?'Your host declined this visit.':'This visit expired. Ask for a new invitation.');}
  else {message('Your card is verified. Waiting for your host to open the door.');pollTimer=setTimeout(poll,2000);}
 }catch(e){message(e.message+' You can retry by sending your card again.');}
 finally{polling=false;}
}
async function submit(proof){
 if(!prepared)throw Error('Prepare your visit first');
 const received=proof?.payload?.challenge;
 if(!received||Object.keys(received).length!==Object.keys(prepared.challenge).length||Object.keys(prepared.challenge).some(key=>received[key]!==prepared.challenge[key]))throw Error('This card belongs to a different visit request');
 await api('/request',proof);prepared.submitted=true;sessionStorage.setItem('pubcast.visit.pending',JSON.stringify(prepared));await poll();
}
$('prepare').onsubmit=async event=>{event.preventDefault();$('prepareButton').disabled=true;
 try{const {data}=await api('/challenge',{invite_code:$('invite').value.trim()});prepared=data;sessionStorage.setItem('pubcast.visit.pending',JSON.stringify(data));$('challengeOut').value=JSON.stringify(data.challenge);$('prepared').hidden=false;$('enter').hidden=true;message('Open your own copy to approve this visit.');}
 catch(e){message(e.message);}finally{$('prepareButton').disabled=false;}
};
$('openHome').onclick=()=>{try{
 if(!prepared)throw Error('Prepare your visit first');homeOrigin=origin($('homeOrigin').value.trim());
 popup=window.open(homeOrigin+'/static/human_visits.html?mode=sign&challenge='+encodeURIComponent(JSON.stringify(prepared.challenge)),'pubcast-visit-home');
 if(!popup)message('The browser blocked the new window. Use the manual exchange below.');
}catch(e){message(e.message);}};
window.addEventListener('message',event=>{
 if(!popup||event.source!==popup||event.origin!==homeOrigin||event.data?.type!=='pubcast.visiting-card')return;
 submit(event.data.proof).catch(e=>message(e.message));
});
$('submitProof').onclick=async()=>{try{await submit(JSON.parse($('proofIn').value));}catch(e){message(e.message);}};
function showTarget(){
 try{const challenge=JSON.parse($('challengeIn').value);const target=origin(challenge.origin);
 $('target').textContent='Visiting '+target+' · Host '+challenge.host_id;$('terms').href=target+'/static/waiting_room.html';$('terms').hidden=false;
 }catch(_){$('target').textContent='Paste a valid visit request to see its host.';$('terms').hidden=true;}
}
$('challengeIn').oninput=showTarget;
$('signCard').onclick=async()=>{if(!$('consent').checked){message('Review and accept this visit’s production consents first.');return;}$('signCard').disabled=true;
 try{const challenge=JSON.parse($('challengeIn').value);const target=origin(challenge.origin);
  const {data,response}=await api('/sign',{challenge,consents:consent});$('proofOut').value=JSON.stringify(data);$('fingerprint').textContent=response.headers.get('X-PubCast-Identity-Fingerprint');$('signed').hidden=false;
  if(window.opener){window.opener.postMessage({type:'pubcast.visiting-card',proof:data},target);$('sentMessage').textContent='Card sent to your visit window. Return there to wait for admission.';}
  else $('sentMessage').textContent='Copy this signed card back into your visit window.';
  message('Your visiting card is ready.');
 }catch(e){message(e.message);}finally{$('signCard').disabled=false;}
};
async function pending(){
 const {data}=await api('/pending');$('pending').replaceChildren();
 for(const person of data.pending){
  const box=document.createElement('article'),heading=document.createElement('h3');heading.textContent=person.card.display_name+' · Human';box.append(heading);
  const id=document.createElement('p');id.className='key';id.textContent=person.card.user_id+' · Visit '+person.entry_id;box.append(id);
  const trust=document.createElement('p');trust.textContent=person.known_key?'Returning identity: the key matches.':'First visit: compare this key with the person you invited.';box.append(trust);
  const key=document.createElement('p');key.className='key';key.textContent=person.fingerprint;box.append(key);
  for(const action of ['approve','deny']){const button=document.createElement('button');button.type='button';button.textContent=action==='approve'?'Approve visit':'Decline';button.onclick=async()=>{button.disabled=true;try{
   await api('/entries/'+encodeURIComponent(person.entry_id)+'/'+action,action==='approve'?{fingerprint:person.fingerprint}:{});await pending();message(action==='approve'?'Visit approved.':'Visit declined.');
  }catch(e){message(e.message);button.disabled=false;}};box.append(button);}
  $('pending').append(box);
 }
 if(!data.pending.length)$('pending').textContent='No verified guests are waiting.';
}
$('refresh').onclick=()=>pending().catch(e=>message(e.message));
$('createInvite').onclick=async()=>{try{const {data}=await api('/invites',{});$('inviteOut').value=data.invite_code;$('inviteLabel').hidden=false;message('Share this invitation with the person you want to invite.');}catch(e){message(e.message);}};
async function settings(){const {data}=await api('/settings');$('doorState').textContent=(data.locked?'Door: owner approval required.':'Door: verified invitations may enter.')+' Host '+data.host_id;}
for(const [id,locked]of [['lockDoor',true],['unlockDoor',false]])$(id).onclick=async()=>{try{await api('/door',{locked});await settings();message(locked?'New guests will wait for approval.':'Verified guests with valid invitations can enter.');}catch(e){message(e.message);}};
$('revoke').onsubmit=async e=>{e.preventDefault();try{await api('/entries/'+encodeURIComponent($('revokeId').value.trim())+'/revoke',{});message('Visit access revoked.');}catch(error){message(error.message);}};
window.addEventListener('pagehide',()=>clearTimeout(pollTimer));
if(mode==='sign'){
 $('sign').hidden=false;$('challengeIn').value=query.get('challenge')||'';showTarget();
 ReachAuth.requireSession(location.pathname+location.search).catch(e=>message(e.message));
}else if(mode==='host'){
 $('host').hidden=false;ReachAuth.requireSession(location.pathname+location.search).then(session=>{if(session)return Promise.all([pending(),settings()]);}).catch(e=>message(e.message));
}else{$('join').hidden=false;restorePrepared();if(prepared?.submitted)poll();}
})();
