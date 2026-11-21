/* Authenticated one-way PCM contribution; one canonical program mixer.
 * Ordered frames, fixed playout lead and strict latency/backpressure bounds.
 * A late/gapped stream is disconnected explicitly, never silently accelerated.
 */
(function(global){
'use strict';
class ParticipantAudio {
 constructor({mixer=global.PubcastProgramAudio,onState=()=>{}}={}){
  this.mixer=mixer;this.onState=onState;this.peers=new Map();this.closed=true;this.generation=0;this.lastFault=null;
 }
 report(message){this.onState(message,{closed:this.closed});}
 async request(path,method='GET',body,key){
  const response=await fetch('/api/participant-audio/'+path.replace(/^\//,''),{method,cache:'no-store',
   headers:{...(body?{'Content-Type':'application/json'}:{}),...(key?{'X-Audio-Key':key}:{})},
   body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(5000)});
  if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch(_){}
   throw Error(typeof detail==='string'?detail:'Audio connection HTTP '+response.status);}
  return response.json();
 }
 check(generation){if(this.closed||generation!==this.generation)throw new DOMException('Audio connection canceled','AbortError');}
 async socket(generation,rate=0){
  // The verified session cookie authenticates the socket; bearer tokens never
  // enter URLs. The capability is sent only after the same-origin handshake.
  const verified=await fetch('/api/auth/verify');if(!verified.ok)throw Error('Sign in before connecting audio');this.check(generation);
  const r=this.reservation,url=new URL('/api/participant-audio/rooms/'+r.room+'/peers/'+r.peer+'/media',location.href);
  url.protocol=location.protocol==='https:'?'wss:':'ws:';
  const worker=this.worker=new Worker('/static/participant_audio_worker.js');
  await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{reject(Error('Audio connection timed out'));},5000);
   worker.onerror=()=>{clearTimeout(timer);reject(Error('Audio worker failed'));};
   worker.onmessage=e=>{if(e.data.type==='ready'){clearTimeout(timer);resolve();}
    else if(e.data.type==='error'){clearTimeout(timer);reject(Error(e.data.message));}};
   worker.postMessage({type:'open',url:url.href,key:r.key,host:this.host,rate});
  });this.check(generation);
  worker.onerror=()=>{if(generation===this.generation)this.fail(Error('Audio worker failed'));};
  worker.onmessage=e=>{if(this.closed||generation!==this.generation)return;
   if(e.data.type==='sender-timing'){this.senderTiming=e.data;return;}
   try{this.receive(e.data);}catch(error){this.fail(error);}};
 }
 async open(){
  if(!this.closed)throw Error('Close the current audio connection first');
  if(!this.mixer?.allowed())throw Error('Audio contributions are blocked in this room');
  const generation=++this.generation;this.closed=false;this.host=true;this.lastFault=null;
  try{
   await this.mixer.ensureContext().resume();this.check(generation);
   const r=await this.request('/rooms','POST');await this.adopt(r,generation);
   await this.mixer.context.audioWorklet.addModule('/static/participant_pcm_worklet.js');this.check(generation);
   await this.socket(generation,this.mixer.context.sampleRate);
   this.stopWithMixer=()=>this.close().catch(()=>{});this.mixer.inputSessionStops.add(this.stopWithMixer);
   this.report('Audio desk open. Participants choose when to connect their microphones.');return r.room;
  }catch(e){if(generation===this.generation)await this.close();throw e;}
 }
 async adopt(reservation,generation){
  if(this.closed||generation!==this.generation){await this.request('/rooms/'+reservation.room+'/peers/'+reservation.peer,'DELETE',null,reservation.key);this.check(generation);}
  this.reservation=reservation;
 }
 async join(room,{consent=false,stream=null}={}){
  if(!this.closed)throw Error('Leave the current audio connection first');
  if(!consent)throw Error('Consent to send and record your microphone is required');
  if(/dressing/.test(location.pathname)||this.mixer?.room==='dressing')throw Error('Leave the dressing room before contributing audio');
  const generation=++this.generation;this.closed=false;this.host=false;
  try{
   this.report('Requesting microphone permission…');
   const media=stream||await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
   if(this.closed||generation!==this.generation){media.getTracks().forEach(t=>t.stop());this.check(generation);}
   this.stream=media;if(!media.getAudioTracks().some(t=>t.readyState==='live'))throw Error('No live microphone audio track');
   const r=await this.request('/rooms/'+encodeURIComponent(room)+'/peers','POST',{consent:true});await this.adopt(r,generation);
   this.context=new AudioContext({sampleRate:r.sample_rate});await this.context.resume();this.check(generation);
   if(this.context.sampleRate!==r.sample_rate)throw Error('This device cannot match the production audio sample rate');
   await this.context.audioWorklet.addModule('/static/blackbox_pcm_worklet.js');this.check(generation);
   await this.socket(generation,this.context.sampleRate);this.check(generation);
   this.source=this.context.createMediaStreamSource(media);this.node=new AudioWorkletNode(this.context,'blackbox-pcm',{processorOptions:{measure:true}});
   this.worker.postMessage({type:'send',port:this.node.port},[this.node.port]);
   this.source.connect(this.node);this.node.connect(this.context.destination);
   media.getAudioTracks().forEach(t=>t.addEventListener('ended',()=>this.close().catch(()=>{}),{once:true}));
   this.report('Microphone connected. The director can record your voice.');
  }catch(e){if(generation===this.generation)await this.close();throw e;}
 }
 receive(event){
  if(event.type==='error'){this.fail(Error(event.message));return;}
  if(!this.host)throw Error('Unexpected return audio');
  if(event.type==='left'||event.type==='fault'){
   if(event.type==='fault'){
    this.lastFault={peer:event.peer,message:event.message,diagnostic:event.diagnostic||null,observedAt:new Date().toISOString()};
    console.warn('Participant audio fault',JSON.stringify({message:event.message,diagnostic:event.diagnostic||null}));
   }
   this.drop(event.peer);this.report(event.message||'Participant disconnected; rejoin the invitation to reconnect.');return;
  }
  if(event.type!=='source'||this.peers.has(event.peer))throw Error('Invalid audio source');
  const ctx=this.mixer.context,destination=ctx.createMediaStreamDestination();
  const node=new AudioWorkletNode(ctx,'participant-pcm',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1],processorOptions:{rate:event.sample_rate}});
  node.connect(destination);
  const input=this.mixer.attachInput('participant-'+event.peer,destination.stream,{label:event.actor,
   onStop:()=>{if(this.peers.has(event.peer))this.worker?.postMessage({type:'drop',peer:event.peer});}});
  this.peers.set(event.peer,{input,destination,node});
  this.worker.postMessage({type:'receive',peer:event.peer,port:node.port},[node.port]);
  this.report('Participant microphone connected.');
 }
 drop(id){const peer=this.peers.get(id);if(!peer)return;this.peers.delete(id);peer.node.disconnect();peer.input.stop();peer.destination.stream.getTracks().forEach(t=>t.stop());}
 fail(error){if(this.closed)return;this.close().catch(()=>{});this.report(error.message);}
 async close(){
  if(this.closed)return;this.closed=true;this.generation++;
  this.mixer?.inputSessionStops.delete(this.stopWithMixer);
  for(const id of Array.from(this.peers.keys()))this.drop(id);
  if(this.node){this.node.disconnect();this.node=null;}this.source?.disconnect();this.source=null;
  this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;
  const context=this.context;this.context=null;if(context&&context.state!=='closed')context.close().catch(()=>{});
  const worker=this.worker;this.worker=null;if(worker){worker.onmessage=worker.onerror=null;worker.postMessage({type:'close'});setTimeout(()=>worker.terminate(),1000);}
  const r=this.reservation;this.reservation=null;this.report('Disconnected. Microphone contribution is off.');
  if(r){try{await this.request('/rooms/'+r.room+'/peers/'+r.peer,'DELETE',null,r.key);}catch(_){}}
 }
}
global.PubCastParticipantAudio=ParticipantAudio;
global.addEventListener('pubcast:room',event=>{if(event.detail.room==='dressing')global.PubCastAudioContribution?.close().catch(()=>{});});
})(window);
