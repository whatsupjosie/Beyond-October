/* PubCast post-production multicamera sync core.
 * One immutable clacker timeline; one explicit non-destructive correction per track.
 * All times use INTEGER MICROSECONDS (not floating-point seconds/frames).
 * Positive manual offset = source plays ahead: at edit t, seek source t+offset.
 * Works offline and is independent of UI, DOM, backend or render transport.
 */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCastEditorSync=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const VERSION=1,INTERVAL_US=15000000,MAX_OFFSET_US=60000000,MAX_DURATION_US=24*3600*1000000;
 const ID=/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
 const bounded=(n,name,lo,hi)=>{if(!Number.isSafeInteger(n)||n<lo||n>hi)throw Error(name+" out of range");return n;};
 const id=(s,name="id")=>{if(typeof s!=="string"||!ID.test(s))throw Error("Invalid "+name);return s;};
 function parseSeconds(value,name="offset"){
   if(typeof value!=="string"&&typeof value!=="number")throw Error(name+" must be a number");
   const str=String(value).trim();
   if(!/^[+-]?(?:\d+(?:\.\d{1,6})?|\.\d{1,6})$/.test(str))throw Error("Invalid "+name+" seconds");
   const us=Math.round(Number(str)*1000000);
   return bounded(us,name,-MAX_OFFSET_US,MAX_OFFSET_US);
 }
 function formatSeconds(us){return (bounded(us,"offset",-MAX_OFFSET_US,MAX_OFFSET_US)/1000000).toFixed(6);}
 function createProject(name,originUnixMs=Date.now(),projectId){
   bounded(originUnixMs,"project clock",0,8640000000000000);
   return {schema:"pubcast.editor-sync",version:VERSION,
     id:id(projectId||"edit-"+originUnixMs,"project ID"),title:String(name||"Untitled shoot").slice(0,128),
     originUnixMs,clackerIntervalUs:INTERVAL_US,createdAt:new Date().toISOString(),
     updatedAt:new Date().toISOString(),tracks:[],selections:[],revision:0};
 }
 function validateTrack(t){
   if(!t||typeof t!=="object")throw Error("Invalid track");
   id(t.id,"track ID");
   if(!["video","audio","camera","blip"].includes(t.kind))throw Error("Invalid track kind");
   if(typeof t.label!=="string"||t.label.length>128)throw Error("Invalid track label");
   bounded(t.manualOffsetUs,"manual offset",-MAX_OFFSET_US,MAX_OFFSET_US);
   if(t.sourceStartUnixMs!=null)bounded(t.sourceStartUnixMs,"source wallclock",0,8640000000000000);
   if(t.durationUs!=null)bounded(t.durationUs,"duration",0,MAX_DURATION_US);
   if(!Array.isArray(t.clackerMarks))throw Error("Invalid clacker marks");
   const seen=new Set();
   for(const mark of t.clackerMarks){
     bounded(mark.sequence,"marker sequence",0,MAX_DURATION_US/INTERVAL_US);
     bounded(mark.sourceUs,"marker source time",0,MAX_DURATION_US);
     if(seen.has(mark.sequence))throw Error("Duplicate clacker marker");
     seen.add(mark.sequence);
   }
   return true;
 }
 function addTrack(project,config){
   validateProject(project);
   if(project.tracks.length>=32)throw Error("Maximum 32 synchronized tracks");
   const track={id:id(config.id,"track ID"),kind:config.kind||"camera",
     label:String(config.label||config.id).slice(0,128),
     mediaRef:config.mediaRef?String(config.mediaRef).slice(0,180):null,
     sourceStartUnixMs:config.sourceStartUnixMs??null,durationUs:config.durationUs??null,
     manualOffsetUs:0,clackerMarks:[],enabled:true};
   validateTrack(track);
   if(project.tracks.some(t=>t.id===track.id))throw Error("Duplicate track ID");
   project.tracks.push(track);touch(project);return track;
 }
 function track(project,trackId){
   const found=project.tracks.find(t=>t.id===trackId);
   if(!found)throw Error("Unknown track "+trackId);
   return found;
 }
 function setOffsetUs(project,trackId,value){
   const t=track(project,trackId);
   t.manualOffsetUs=bounded(value,"manual offset",-MAX_OFFSET_US,MAX_OFFSET_US);
   touch(project);return t.manualOffsetUs;
 }
 function setOffsetSeconds(project,trackId,seconds){return setOffsetUs(project,trackId,parseSeconds(seconds));}
 function adjustOffsetSeconds(project,trackId,delta){
   const step=parseSeconds(delta,"adjustment"),t=track(project,trackId);
   return setOffsetUs(project,trackId,t.manualOffsetUs+step);
 }
 function addClackerMark(project,trackId,sequence,sourceTimeUs){
   const t=track(project,trackId);
   bounded(sequence,"marker sequence",0,MAX_DURATION_US/INTERVAL_US);
   bounded(sourceTimeUs,"source clacker time",0,MAX_DURATION_US);
   const other=t.clackerMarks.find(m=>m.sequence===sequence);
   if(other)other.sourceUs=sourceTimeUs;
   else t.clackerMarks.push({sequence,sourceUs:sourceTimeUs});
   t.clackerMarks.sort((a,b)=>a.sequence-b.sequence);
   validateTrack(t);touch(project);return t.clackerMarks.length;
 }
 function alignment(project,t){
   const marks=t.clackerMarks;
   if(marks.length){
     if(marks.length===1)return {scale:1,interceptUs:marks[0].sourceUs-marks[0].sequence*INTERVAL_US,
       origin:"clacker",markers:1,driftPpm:0,residualUs:0};
     // Fit a linear clock model; interpolation handles modest hardware clock drift.
     const xs=marks.map(m=>m.sequence*INTERVAL_US),ys=marks.map(m=>m.sourceUs);
     const x0=xs[0],y0=ys[0],xn=xs.map(x=>x-x0),yn=ys.map(y=>y-y0);
     const meanX=xn.reduce((a,b)=>a+b,0)/xn.length,meanY=yn.reduce((a,b)=>a+b,0)/yn.length;
     let cov=0,variance=0;
     for(let i=0;i<xn.length;i++){cov+=(xn[i]-meanX)*(yn[i]-meanY);variance+=(xn[i]-meanX)**2;}
     if(!variance)throw Error("Insufficient distinct clacker marks");
     const scale=cov/variance,driftPpm=(scale-1)*1000000;
     if(!Number.isFinite(scale)||Math.abs(driftPpm)>5000)throw Error("Track clacker drift exceeds 5000 ppm; inspect marker attribution");
     const interceptUs=(y0+meanY)-scale*(x0+meanX);
     const residualUs=Math.round(Math.max(...xs.map((x,i)=>Math.abs((scale*x+interceptUs)-ys[i]))));
     return {scale,interceptUs,origin:"clacker",markers:marks.length,driftPpm,residualUs};
   }
   if(t.sourceStartUnixMs!=null){
     return {scale:1,interceptUs:(project.originUnixMs-t.sourceStartUnixMs)*1000,
       origin:"wallclock",markers:0,driftPpm:0,residualUs:0};
   }
   return {scale:1,interceptUs:0,origin:"unanchored",markers:0,driftPpm:0,residualUs:0};
 }
 function sourceTimeUs(project,trackId,editTimeUs){
   bounded(editTimeUs,"edit time",0,MAX_DURATION_US);
   const t=track(project,trackId),a=alignment(project,t);
   return Math.round(editTimeUs*a.scale+a.interceptUs+t.manualOffsetUs);
 }
 function editTimeUs(project,trackId,sourceTime){
   bounded(sourceTime,"source time",0,MAX_DURATION_US);
   const t=track(project,trackId),a=alignment(project,t);
   return Math.round((sourceTime-a.interceptUs-t.manualOffsetUs)/a.scale);
 }
 function markersBetween(startUs,endUs,intervalUs=INTERVAL_US){
   bounded(startUs,"start time",0,MAX_DURATION_US);
   bounded(endUs,"end time",startUs,MAX_DURATION_US);
   bounded(intervalUs,"clacker interval",1000000,MAX_DURATION_US);
   const result=[];
   for(let index=Math.ceil(startUs/intervalUs);index*intervalUs<=endUs;index++){
     result.push({sequence:index,editTimeUs:index*intervalUs});
     if(result.length>MAX_DURATION_US/intervalUs+1)throw Error("Marker range exceeds limit");
   }
   return result;
 }
 function addSelection(project,config){
   validateProject(project);
   const item={id:id(config.id||"select-"+(project.selections.length+1),"selection"),
     kind:"shot",trackId:id(config.trackId,"source track"),
     inUs:bounded(config.inUs,"in",0,MAX_DURATION_US),
     outUs:bounded(config.outUs,"out",0,MAX_DURATION_US),
     label:String(config.label||"").slice(0,128)};
   if(item.outUs<=item.inUs)throw Error("Selection out must exceed in");
   track(project,item.trackId);
   if(project.selections.some(e=>e.id===item.id))throw Error("Duplicate selection ID");
   project.selections.push(item);touch(project);return item;
 }
 function validateProject(p){
   if(!p||p.schema!=="pubcast.editor-sync"||p.version!==VERSION)throw Error("Unsupported sync project");
   id(p.id,"project ID");
   bounded(p.originUnixMs,"project clock",0,8640000000000000);
   if(p.clackerIntervalUs!==INTERVAL_US)throw Error("Unsupported clacker interval");
   if(!Array.isArray(p.tracks)||p.tracks.length>32||!Array.isArray(p.selections)||p.selections.length>10000)throw Error("Invalid project collections");
   const ids=new Set();
   for(const t of p.tracks){
     validateTrack(t);if(ids.has(t.id))throw Error("Duplicate track");ids.add(t.id);
     alignment(p,t); // Reject incoherent multi-mark clocks before saving a project.
   }
   const selectIds=new Set();
   let assembledDurationUs=0;
   for(const s of p.selections){
     id(s.id,"selection ID");
     if(selectIds.has(s.id))throw Error("Duplicate selection");
     selectIds.add(s.id);
     let duration;
     if(s.kind==="gap"){
       duration=bounded(s.durationUs,"gap duration",1,MAX_DURATION_US);
     }else{
       if(s.kind!=null&&s.kind!=="shot")throw Error("Invalid selection kind");
       if(!ids.has(s.trackId))throw Error("Selection refers to missing track");
       bounded(s.inUs,"selection in",0,MAX_DURATION_US);
       bounded(s.outUs,"selection out",0,MAX_DURATION_US);
       if(s.outUs<=s.inUs)throw Error("Selection out must exceed in");
       duration=s.outUs-s.inUs;
     }
     assembledDurationUs+=duration;
     if(assembledDurationUs>MAX_DURATION_US)throw Error("Assembled timeline exceeds 24 hours");
   }
   return true;
 }
 function touch(p){p.updatedAt=new Date().toISOString();p.revision=(p.revision||0)+1;}
 function exportManifest(p){
   validateProject(p);
   return {schema:"pubcast.render-selection",version:1,projectId:p.id,
     clock:{originUnixMs:p.originUnixMs,intervalUs:INTERVAL_US},
     shots:timelineEntries(p).map(s=>{
       if(s.kind==="gap")return {id:s.id,kind:"gap",timelineInUs:s.timelineInUs,
         timelineOutUs:s.timelineOutUs,durationUs:s.durationUs};
       const t=track(p,s.trackId),a=alignment(p,t);
       return {id:s.id,kind:"shot",trackId:t.id,mediaRef:t.mediaRef,
         timelineInUs:s.timelineInUs,timelineOutUs:s.timelineOutUs,
         editInUs:s.inUs,editOutUs:s.outUs,
         sourceInUs:sourceTimeUs(p,t.id,s.inUs),sourceOutUs:sourceTimeUs(p,t.id,s.outUs),
         syncOrigin:a.origin,clackerMarkers:a.markers,manualOffsetUs:t.manualOffsetUs,
         driftPpm:a.driftPpm};
     })};
 }
 /** Sequential rough-cut assembly, including explicit blank spaces. */
 function timelineEntries(p){
   validateProject(p);
   let at=0;
   return p.selections.map(s=>{
     const durationUs=s.kind==="gap"?s.durationUs:s.outUs-s.inUs;
     const entry={...s,timelineInUs:at,timelineOutUs:at+durationUs,durationUs};
     at+=durationUs;return entry;
   });
 }
 function entryAt(p,atUs){
   bounded(atUs,"timeline time",0,MAX_DURATION_US);
   const list=timelineEntries(p);
   return list.find(e=>atUs>=e.timelineInUs&&atUs<e.timelineOutUs)||
     (atUs===list.at(-1)?.timelineOutUs?list.at(-1):null);
 }
 function gap(p,durationUs,entryId){
   validateProject(p);
   bounded(durationUs,"gap duration",1,MAX_DURATION_US);
   const item={id:id(entryId||"gap-"+Date.now()+"-"+(p.selections.length+1),"gap ID"),
     kind:"gap",durationUs};
   if(p.selections.some(s=>s.id===item.id))throw Error("Duplicate selection ID");
   p.selections.push(item);validateProject(p);touch(p);return item;
 }
 function splitAt(p,selectionId,timelineUs){
   validateProject(p);bounded(timelineUs,"split time",0,MAX_DURATION_US);
   const e=timelineEntries(p).find(e=>e.id===selectionId);
   if(!e||e.kind==="gap")throw Error("Choose a video/audio shot to split");
   if(timelineUs<=e.timelineInUs||timelineUs>=e.timelineOutUs)throw Error("Split must be inside clip, not at its edge");
   const cutUs=e.inUs+(timelineUs-e.timelineInUs);
   const i=p.selections.findIndex(s=>s.id===selectionId);
   const original=p.selections[i],left={...original,outUs:cutUs},
     right={...original,id:id(original.id+"-split-"+(p.revision+1),"new split ID"),inUs:cutUs};
   if(p.selections.some(x=>x.id===right.id))throw Error("Split ID conflict");
   p.selections.splice(i,1,left,right);validateProject(p);touch(p);return [left,right];
 }
 function deleteSelection(p,selectionId,ripple=true){
   validateProject(p);
   const i=p.selections.findIndex(x=>x.id===selectionId);
   if(i<0)throw Error("Selected clip missing");
   const s=p.selections[i],duration=s.kind==="gap"?s.durationUs:s.outUs-s.inUs;
   if(!ripple&&s.kind==="gap")throw Error("A blank interval cannot be lifted into another blank; use Ripple Delete or Close Gaps");
   if(ripple)p.selections.splice(i,1);
   else p.selections.splice(i,1,{id:id("lift-"+s.id+"-"+(p.revision+1),"lift ID"),kind:"gap",durationUs:duration});
   validateProject(p);touch(p);return {durationUs:duration,ripple};
 }
 function closeGaps(p){
   validateProject(p);const removed=p.selections.filter(s=>s.kind==="gap").length;
   if(!removed)return 0;
   p.selections=p.selections.filter(s=>s.kind!=="gap");
   validateProject(p);touch(p);return removed;
 }
 function moveSelection(p,selectionId,direction){
   validateProject(p);
   if(direction!==-1&&direction!==1)throw Error("Movement must be -1 or +1");
   const i=p.selections.findIndex(x=>x.id===selectionId),j=i+direction;
   if(i<0)throw Error("Unknown rough-cut selection");
   if(j<0||j>=p.selections.length)return false;
   [p.selections[i],p.selections[j]]=[p.selections[j],p.selections[i]];
   touch(p);return true;
 }
 function clackerPCM(durationUs,sampleRate=48000){
   bounded(durationUs,"duration",0,12*3600*1000000);
   bounded(sampleRate,"sample rate",8000,96000);
   const seconds=Math.ceil(durationUs/1000000),n=seconds*sampleRate;
   if(n>sampleRate*3600)throw Error("Blip WAV export limited to one hour per part");
   const audio=new Int16Array(n);
   for(const mark of markersBetween(0,durationUs)){
     const start=Math.round(mark.editTimeUs/1000000*sampleRate);
     for(let i=0;i<Math.min(.025*sampleRate,n-start);i++){
       const envelope=Math.sin(Math.PI*i/(.025*sampleRate))**2;
       audio[start+i]=Math.round(9000*envelope*Math.sin(2*Math.PI*1000*i/sampleRate));
     }
   }
   // WAV is a reference track, not mixed into live program audio.
   const header=new ArrayBuffer(44),v=new DataView(header),fmt=(off,s)=>{for(let i=0;i<s.length;i++)v.setUint8(off+i,s.charCodeAt(i));};
   fmt(0,"RIFF");v.setUint32(4,36+n*2,true);fmt(8,"WAVE");fmt(12,"fmt ");v.setUint32(16,16,true);
   v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sampleRate,true);
   v.setUint32(28,sampleRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);
   fmt(36,"data");v.setUint32(40,n*2,true);
   return {header,pcm:audio,sampleRate,durationUs};
 }
 return {VERSION,INTERVAL_US,parseSeconds,formatSeconds,createProject,validateProject,
   addTrack,setOffsetUs,setOffsetSeconds,adjustOffsetSeconds,addClackerMark,alignment,
   sourceTimeUs,editTimeUs,markersBetween,addSelection,timelineEntries,entryAt,
   gap,splitAt,deleteSelection,closeGaps,moveSelection,exportManifest,clackerPCM};
});
