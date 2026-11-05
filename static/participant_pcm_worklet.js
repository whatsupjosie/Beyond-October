/* Receiver clocked by Web Audio, independent of studio drawing/main-thread work.
 * Sender contexts use this desk's exact sample rate; device conversion stays in
 * the browser's native MediaStreamSource. Never drop/repeat/accelerate samples.
 */
class ParticipantPCM extends AudioWorkletProcessor {
 constructor(options){
  super();this.ring=new Int16Array(Math.ceil(sampleRate*1.5));this.read=0;this.write=0;this.count=0;this.started=false;this.failed=false;
  if(options.processorOptions.rate!==sampleRate)throw Error('Audio sample rate mismatch');
  this.port.onmessage=e=>{
   if(e.data==='stop'){this.done=true;return;}
   if(this.failed)return;
   const data=new Int16Array(e.data);
   if(this.count+data.length>this.ring.length){this.fail('overflow');return;}
   for(const sample of data){this.ring[this.write]=sample;this.write=(this.write+1)%this.ring.length;}
   this.count+=data.length;
  };
 }
 fail(reason){if(this.failed)return;this.failed=true;this.port.postMessage({fault:reason});}
 process(inputs,outputs){
  if(this.done)return false;
  const output=outputs[0]?.[0];if(!output||this.failed)return true;
  if(!this.started){if(this.count<sampleRate*.5)return true;this.started=true;}
  if(this.count<output.length){this.fail('underflow');return true;}
  for(let i=0;i<output.length;i++){output[i]=this.ring[this.read]/32768;this.read=(this.read+1)%this.ring.length;}
  this.count-=output.length;return true;
 }
}
registerProcessor('participant-pcm',ParticipantPCM);
