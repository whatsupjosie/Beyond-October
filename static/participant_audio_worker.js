/* Socket and PCM ports stay off the studio/main thread. */
'use strict';
let socket,host=false,rate=0,timer,ready=false,sequence=0,stopped=false;
const peers=new Map();
function release(peer){if(peer?.port){peer.port.postMessage('stop');peer.port.close();}}
function fail(message){if(stopped)return;stopped=true;clearInterval(timer);socket?.close();for(const peer of peers.values())release(peer);postMessage({type:'error',message});}
function drop(id,message,diagnostic){
 const peer=peers.get(id);if(!peer||peer.rejected)return;
 peer.rejected=true;release(peer);peer.pending=[];
 socket.send(JSON.stringify({drop:id}));postMessage({type:'fault',peer:id,message,diagnostic});
}
function frame(data){
 if(!(data instanceof ArrayBuffer)||data.byteLength<22||data.byteLength>16404)throw Error('Invalid received audio frame');
 const bytes=new Uint8Array(data),id=Array.from(bytes.slice(0,16),b=>b.toString(16).padStart(2,'0')).join(''),peer=peers.get(id);
 if(!peer)throw Error('Unknown audio source');if(peer.rejected)return;
 if(new DataView(data).getUint32(16,true)!==peer.sequence++){drop(id,'Participant audio sequence lost; reconnect that microphone.');return;}
 const now=performance.now();
 if(peer.lastPacketAtMs!==null)peer.maxPacketGapMs=Math.max(peer.maxPacketGapMs,now-peer.lastPacketAtMs);
 if(peer.firstPacketAtMs===null)peer.firstPacketAtMs=now;
 peer.lastPacketAtMs=now;peer.packets++;
 const pcm=data.slice(20);
 if(peer.port)peer.port.postMessage(pcm,[pcm]);
 else{
  peer.pending.push(pcm);peer.bytes+=pcm.byteLength;
  if(peer.bytes>rate*3)drop(id,'Participant audio could not start in time; reconnect that microphone.');
 }
}
onmessage=e=>{
 const message=e.data;
 if(message.type==='open'){
  host=message.host;rate=message.rate;socket=new WebSocket(message.url);socket.binaryType='arraybuffer';
  socket.onopen=()=>socket.send(JSON.stringify({key:message.key,sample_rate:rate}));
  socket.onerror=()=>fail('Audio connection failed');socket.onclose=()=>fail('Audio connection lost. Reconnect your microphone.');
  socket.onmessage=event=>{
   try{
    if(!ready){if(!JSON.parse(event.data).ok)throw Error('Audio connection rejected');ready=true;
     timer=setInterval(()=>{if(socket.readyState===WebSocket.OPEN)socket.send('ping');},2000);postMessage({type:'ready'});return;}
    if(!host)throw Error('Unexpected return audio');
    if(typeof event.data!=='string'){frame(event.data);return;}
    const eventData=JSON.parse(event.data);
    if(eventData.type==='source'){
     if(peers.has(eventData.peer)||eventData.sample_rate!==rate)throw Error('Invalid audio source clock');
     peers.set(eventData.peer,{sequence:0,pending:[],bytes:0,port:null,rejected:false,packets:0,firstPacketAtMs:null,lastPacketAtMs:null,maxPacketGapMs:0});
    }else if(eventData.type==='left'){release(peers.get(eventData.peer));peers.delete(eventData.peer);}
    else throw Error('Invalid audio connection event');
    postMessage(eventData);
   }catch(error){fail(error.message);}
  };
 }else if(message.type==='receive'){
  const peer=peers.get(message.peer);if(!peer||peer.rejected){message.port.close();return;}
  peer.port=message.port;peer.port.onmessage=event=>{
   if(!event.data?.fault)return;
   const reason=event.data.fault;
   drop(message.peer,'Participant audio clock stopped or exceeded its buffer ('+reason+'); reconnect that microphone.',{
    reason,receiver:event.data.diagnostic,
    transport:{packets:peer.packets,firstPacketAtMs:peer.firstPacketAtMs,lastPacketAtMs:peer.lastPacketAtMs,
     maxPacketGapMs:peer.maxPacketGapMs,faultAtMs:performance.now()}
   });
  };
  for(const pcm of peer.pending)peer.port.postMessage(pcm,[pcm]);peer.pending=[];peer.bytes=0;
 }else if(message.type==='drop'&&host){drop(message.peer,'Participant audio stopped by the director.');
 }else if(message.type==='send'){
  message.port.onmessage=event=>{
   if(stopped||!(event.data instanceof ArrayBuffer))return;
   if(socket.readyState!==WebSocket.OPEN||socket.bufferedAmount>rate*.5){fail('Audio upload is too slow; reconnect your microphone.');return;}
   const packet=new Uint8Array(4+event.data.byteLength);new DataView(packet.buffer).setUint32(0,sequence++,true);packet.set(new Uint8Array(event.data),4);socket.send(packet);
  };
 }else if(message.type==='close'){stopped=true;clearInterval(timer);socket?.close();for(const peer of peers.values())release(peer);close();}
};
