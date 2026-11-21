/* Receiver clocked by Web Audio, independent of studio drawing/main-thread work.
 * Sender contexts use this desk's exact sample rate; device conversion stays in
 * the browser's native MediaStreamSource. Equal nominal rates still leave
 * independent clocks. Reconcile small rate differences at host playout.
 */
const LEAD_SECONDS = .5;
const QUEUE_AVERAGE_SECONDS = 2;
const QUEUE_TOLERANCE_SECONDS = .1;
const MAX_RATE_CORRECTION = .005;
const FILTER_RADIUS = 24;
const FILTER_PHASES = 256;
const FILTER_TAPS = FILTER_RADIUS * 2;
const FILTER_CUTOFF = .97;
const kernels = new Float32Array((FILTER_PHASES + 1) * FILTER_TAPS);

for (let phase = 0; phase <= FILTER_PHASES; phase++) {
 const offset = phase / FILTER_PHASES;
 let sum = 0;
 for (let tap = 0; tap < FILTER_TAPS; tap++) {
  const distance = tap - FILTER_RADIUS + 1 - offset;
  const angle = Math.PI * distance / FILTER_RADIUS;
  const window = .42 + .5 * Math.cos(angle) + .08 * Math.cos(2 * angle);
  const x = Math.PI * FILTER_CUTOFF * distance;
  const coefficient = FILTER_CUTOFF * (x ? Math.sin(x) / x : 1) * window;
  kernels[phase * FILTER_TAPS + tap] = coefficient;
  sum += coefficient;
 }
 for (let tap = 0; tap < FILTER_TAPS; tap++) kernels[phase * FILTER_TAPS + tap] /= sum;
}

class ParticipantPCM extends AudioWorkletProcessor {
 constructor(options){
  super();this.ring=new Int16Array(Math.ceil(sampleRate*1.5)+FILTER_RADIUS);this.capacity=this.ring.length-FILTER_RADIUS;this.read=0;this.write=0;this.count=0;this.started=false;this.failed=false;
  this.receivedFrames=0;this.renderedFrames=0;this.firstReceiveFrame=null;this.lastReceiveFrame=null;this.startFrame=null;this.maxReceiveGapFrames=0;this.queueHistory=[];this.nextSnapshotFrame=currentFrame;
  this.phase=0;this.consumedFrames=0;this.rate=1;this.averageQueue=0;this.targetQueue=0;
  if(options.processorOptions.rate!==sampleRate)throw Error('Audio sample rate mismatch');
  this.port.onmessage=e=>{
   if(e.data==='stop'){this.done=true;return;}
   if(this.failed)return;
   const data=new Int16Array(e.data);
   if(this.firstReceiveFrame===null)this.firstReceiveFrame=currentFrame;
   if(this.lastReceiveFrame!==null)this.maxReceiveGapFrames=Math.max(this.maxReceiveGapFrames,currentFrame-this.lastReceiveFrame);
   this.lastReceiveFrame=currentFrame;this.receivedFrames+=data.length;
   if(this.count+data.length>this.capacity){this.fail('overflow',data.length);return;}
   for(const sample of data){this.ring[this.write]=sample;this.write=(this.write+1)%this.ring.length;}
   this.count+=data.length;
  };
 }
 fail(reason,incomingFrames=0){
  if(this.failed)return;this.failed=true;
  // Numbers only, never microphone samples. Keep the last minute bounded.
  this.port.postMessage({fault:reason,diagnostic:{sampleRate,currentFrame,
   queuedFrames:this.count,capacityFrames:this.capacity,incomingFrames,
   receivedFrames:this.receivedFrames,renderedFrames:this.renderedFrames,
   consumedFrames:this.consumedFrames,playoutRate:this.rate,averageQueue:this.averageQueue,
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
  if(!this.started){
   if(this.count<sampleRate*LEAD_SECONDS)return true;
   this.started=true;this.startFrame=currentFrame;
   // Use the nominal lead as the target. Packet boundaries can overshoot it.
   this.averageQueue=this.targetQueue=sampleRate*LEAD_SECONDS;
  }
  // Smooth the packet-sized sawtooth before making small playout adjustments.
  this.averageQueue+=(this.count-this.averageQueue)*Math.min(1,output.length/(sampleRate*QUEUE_AVERAGE_SECONDS));
  const error=(this.averageQueue-this.targetQueue)/sampleRate;
  const correction=Math.sign(error)*Math.max(0,Math.abs(error)-QUEUE_TOLERANCE_SECONDS)*.04;
  this.rate=1+Math.max(-MAX_RATE_CORRECTION,Math.min(MAX_RATE_CORRECTION,correction));
  const end=this.phase+output.length*this.rate;
  const consumed=Math.floor(end);
  const passthrough=this.rate===1&&this.phase===0;
  const needed=passthrough?output.length:
   Math.max(consumed,Math.floor(this.phase+(output.length-1)*this.rate)+FILTER_RADIUS+1);
  if(this.count<needed){this.fail('underflow');return true;}
  const ring=this.ring;
  for(let i=0;i<output.length;i++){
   if(passthrough){
    output[i]=ring[(this.read+i)%ring.length]/32768;
    continue;
   }
   const position=this.phase+i*this.rate;
   const index=Math.floor(position);
   const kernel=Math.round((position-index)*FILTER_PHASES)*FILTER_TAPS;
   let cursor=(this.read+index+ring.length-FILTER_RADIUS+1)%ring.length;
   let sample=0;
   for(let tap=0;tap<FILTER_TAPS;tap++){
    sample+=ring[cursor]*kernels[kernel+tap];
    if(++cursor===ring.length)cursor=0;
   }
   output[i]=sample/32768;
  }
  this.phase=end-consumed;this.read=(this.read+consumed)%ring.length;
  this.count-=consumed;this.consumedFrames+=consumed;this.renderedFrames+=output.length;return true;
 }
}
registerProcessor('participant-pcm',ParticipantPCM);
