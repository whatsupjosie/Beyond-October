/* Independent pre-fader voice recordings, using the same durable chunk journal
 * and backpressure behavior as the program take. Late arrivals become separate
 * clocked segments; a disconnected/rejoined source never overwrites a segment.
 */
(function(global){
'use strict';
const Store=global.PubCast25DStore,Capture=global.PubCast25DCapture;
class SourceRecordings {
 constructor({mixer,session,parentTakeId,owner,references=[],onFailure=()=>{}}){
  Object.assign(this,{mixer,session,parentTakeId,owner,references,onFailure});this.jobs=[];this.closed=false;
 }
 async start(){
  this.unsubscribe=this.mixer.onInput((type,input)=>{
   if(type==='added'&&!this.closed)this.add(input).catch(this.onFailure);
   if(type==='removed')for(const job of this.jobs)if(job.input===input)job.stop();
  });
  await Promise.all([...this.mixer.inputs.values(),...this.references].map(input=>this.add(input)));
 }
 async add(input){
  if(this.closed)return;
  const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(m=>MediaRecorder.isTypeSupported(m));
  if(!mime)throw Error('This browser cannot record independent audio sources');
  const recorder=new MediaRecorder(input.rawStream,{mimeType:mime,audioBitsPerSecond:128000});
  const id=this.parentTakeId+'-voice-'+Capture.id().slice(0,16);
  const timing={id,owner:this.owner,kind:'audio-source',parentTakeId:this.parentTakeId,
   session:structuredClone(this.session),sourceId:input.id,label:input.label,sourceKind:input.kind||'voice',
   syncReferenceId:input.syncReferenceId||null,mime:recorder.mimeType,
   startedAt:new Date().toISOString(),offsetMs:Date.now()-Date.parse(this.session.startedAt)};
  let resolve,reject,stopped=false,settling=false,failure=null,renewing=false;
  const completion=new Promise((a,b)=>{resolve=a;reject=b;});completion.catch(()=>{});
  const job={input,timing,completion,ready:null,stop:()=>{
   stopped=true;if(recorder.state!=='inactive')recorder.stop();
  }};this.jobs.push(job);
  const fail=e=>{failure=failure||e;this.onFailure(e);job.stop();};
  job.ready=(async()=>{
   await Store.beginCapture(timing);
   const writer=Capture.create({store:Store,id,owner:this.owner,session:this.session,timing,onFailure:fail});
   const timer=setInterval(async()=>{
    if(renewing)return;renewing=true;
    try{await Store.renewCapture(id,this.owner);}catch(e){if(!settling)fail(e);}finally{renewing=false;}
   },2000);
   recorder.ondataavailable=e=>{if(e.data?.size)writer.push(e.data,Date.now()-Date.parse(timing.startedAt));};
   recorder.onerror=e=>fail(e.error||Error('Source audio encoder failed'));
   recorder.onstop=async()=>{
    if(settling)return;settling=true;
    try{
     const pending=await writer.settle();failure=failure||pending.error||input.failure;
     const record=await Store.readCapture(id),blob=await Capture.assemble(record,pending.pending);
     const source={id,parentTakeId:this.parentTakeId,sourceId:input.id,label:input.label,kind:timing.sourceKind,syncReferenceId:timing.syncReferenceId,
      mime:blob.type,bytes:blob.size,startedAt:timing.startedAt,offsetMs:timing.offsetMs,
      durationMs:Date.now()-Date.parse(timing.startedAt),preFader:true,incomplete:!!failure};
     await Store.saveSource(this.session,source,blob,{id,owner:this.owner});
     this.session.sourceTracks=[...(this.session.sourceTracks||[]).filter(s=>s.id!==id),source];
     resolve(source);
    }catch(e){await Store.releaseCapture(id,this.owner).catch(()=>{});this.onFailure(e);reject(e);}
    finally{clearInterval(timer);}
   };
   if(stopped||this.closed||(!input.reference&&!this.mixer.inputs.has(input.id))){
    clearInterval(timer);await Store.releaseCapture(id,this.owner);resolve(null);return;
   }
   timing.startedAt=new Date().toISOString();timing.offsetMs=Date.now()-Date.parse(this.session.startedAt);
   recorder.start(1000);
  })();
  try{await job.ready;}catch(e){reject(e);throw e;}
 }
 async stop(){
  this.closed=true;this.unsubscribe?.();
  await Promise.allSettled(this.jobs.map(j=>j.ready));
  this.jobs.forEach(j=>j.stop());
  const results=await Promise.allSettled(this.jobs.map(j=>j.completion));
  const failure=results.find(r=>r.status==='rejected');if(failure)throw failure.reason;
  return results.map(r=>r.value).filter(Boolean);
 }
}
global.PubCast25DSourceRecordings=SourceRecordings;
})(window);
