/* Receiver clocked by Web Audio, independent of studio drawing/main-thread work.
 * Sender contexts use this desk's exact sample rate; device conversion stays in
 * the browser's native MediaStreamSource. Never drop/repeat/accelerate samples.
 */
class ParticipantPCM extends AudioWorkletProcessor {
 constructor(options){
  super();this.ring=new Int16Array(Math.ceil(sampleRate*1.5));this.read=0;this.write=0;this.count=0;this.started=false;this.failed=false;
  this.receivedFrames=0;this.renderedFrames=0;this.firstReceiveFrame=null;this.lastReceiveFrame=null;this.startFrame=null;this.maxReceiveGapFrames=0;this.queueHistory=[];this.nextSnapshotFrame=currentFrame;
  if(options.processorOptions.rate!==sampleRate)throw Error('Audio sample rate mismatch');
  this.port.onmessage=e=>{
   if(e.data==='stop'){this.done=true;return;}
   if(this.failed)return;
   const data=new Int16Array(e.data);
   if(this.firstReceiveFrame===null)this.firstReceiveFrame=currentFrame;
   if(this.lastReceiveFrame!==null)this.maxReceiveGapFrames=Math.max(this.maxReceiveGapFrames,currentFrame-this.lastReceiveFrame);
   this.lastReceiveFrame=currentFrame;this.receivedFrames+=data.length;
   if(this.count+data.length>this.ring.length){this.fail('overflow',data.length);return;}
   for(const sample of data){this.ring[this.write]=sample;this.write=(this.write+1)%this.ring.length;}
   this.count+=data.length;
  };
 }
 fail(reason,incomingFrames=0){
  if(this.failed)return;this.failed=true;
  // Numbers only, never microphone samples. Keep the last minute bounded.
  this.port.postMessage({fault:reason,diagnostic:{sampleRate,currentFrame,
   queuedFrames:this.count,capacityFrames:this.ring.length,incomingFrames,
   receivedFrames:this.receivedFrames,renderedFrames:this.renderedFrames,
   firstReceiveFrame:this.firstReceiveFrame,lastReceiveFrame:this.lastReceiveFrame,
   startFrame:this.startFrame,maxReceiveGapFrames:this.maxReceiveGapFrames,
   queueHistory:this.queueHistory}});
 }
 process(inputs,outputs){
  if(this.done)return false;
  const output=outputs[0]?.[0];if(!output||this.failed)return true;
  if(currentFrame>=this.nextSnapshotFrame){
   this.queueHistory.push({frame:currentFrame,queuedFrames:this.count,receivedFrames:this.receivedFrames,renderedFrames:this.renderedFrames});
   if(this.queueHistory.length>12)this.queueHistory.shift();
   this.nextSnapshotFrame=currentFrame+sampleRate*5;
  }
  if(!this.started){if(this.count<sampleRate*.5)return true;this.started=true;this.startFrame=currentFrame;}
  if(this.count<output.length){this.fail('underflow');return true;}
  for(let i=0;i<output.length;i++){output[i]=this.ring[this.read]/32768;this.read=(this.read+1)%this.ring.length;}
  this.count-=output.length;this.renderedFrames+=output.length;return true;
 }
}
registerProcessor('participant-pcm',ParticipantPCM);
