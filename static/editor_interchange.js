/* PubCast portable editorial interchange. Original implementation, no third-party
 * editor code. CMX3600 basic cut list + full-fidelity PubCast JSON sidecar.
 * IMPORTANT: EDL is lossy (one video edit track, frame-based, no clacker drift
 * curves/audio layout). Keep the JSON manifest; export real source media unchanged.
 * No proxy is ever relabeled as a professional camera/scene master.
 */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCastEditorInterchange=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const BASE_TC_HOUR=1,MAX_EDL_EVENTS=999;
 const fpsAllowed=new Set([24,25,30]);
 function validFrameRate(rate){
   if(!fpsAllowed.has(rate))throw Error("CMX3600 non-drop export requires an explicit 24, 25, or 30 fps rate");
   return rate;
 }
 function safeName(raw){
   const s=String(raw||"").replace(/[\r\n\0]/g," ").trim();
   return s.length?s.slice(0,160):"UNNAMED";
 }
 function toFrames(us,fps){
   if(!Number.isSafeInteger(us)||us<0)throw Error("Invalid nonnegative microsecond time");
   return Math.round(us*fps/1000000);
 }
 function toTC(frames,fps){
   validFrameRate(fps);
   if(!Number.isSafeInteger(frames)||frames<0)throw Error("Invalid frame number");
   const f=frames%fps,seconds=Math.floor(frames/fps);
   const s=seconds%60,m=Math.floor(seconds/60)%60,h=Math.floor(seconds/3600);
   if(h>23)throw Error("CMX timecode exceeds 23:59:59; split into reels");
   return [h,m,s,f].map(n=>String(n).padStart(2,"0")).join(":");
 }
 function reel(id){
   // Keep reel IDs unique by track index; never use filename suffix to claim a media relationship.
   const match=String(id).match(/^\w{1,8}$/);
   return match?id:"AX";
 }
 function qualityOf(track){
   const q=track?.quality||{};
   const role=["camera_original","high_quality_render","replayable_scene","proxy","unverified"].includes(q.role)?q.role:"unverified";
   const width=Number.isSafeInteger(q.width)&&q.width>0?q.width:null;
   const height=Number.isSafeInteger(q.height)&&q.height>0?q.height:null;
   return {role,width,height,codec:q.codec||null,bitDepth:q.bitDepth||null,
     bytePreserved:!!q.bytePreserved,
     verified:!!q.verified,
     mediaFormat:q.mediaFormat||null};
 }
 function audit(project,Core){
   Core.validateProject(project);
   const problems=[],warnings=[],included=[],trackById=new Map(project.tracks.map(t=>[t.id,t]));
   for(const shot of project.selections){
     if(shot.kind==="gap")continue;
     const t=trackById.get(shot.trackId);if(!t)continue;
     const q=qualityOf(t);
     if(!included.some(x=>x.trackId===t.id))included.push({trackId:t.id,name:t.label,ref:t.mediaRef,
       quality:q,durationUs:t.durationUs??null,manualOffsetUs:t.manualOffsetUs,markers:t.clackerMarks.length});
     if(q.role==="proxy")problems.push(t.label+": only a proxy is identified; cannot claim professional source quality");
     if(q.role==="unverified")warnings.push(t.label+": camera/master status and decode quality are unverified");
     if(q.role!=="unverified"&&q.role!=="proxy"&&!q.verified)
       warnings.push(t.label+": source quality provenance has not been independently verified");
     if(q.role!=="unverified"&&q.role!=="proxy"&&!q.bytePreserved)
       problems.push(t.label+": source bytes are not confirmed preserved");
     if(t.mediaRef?.startsWith("local:"))
       warnings.push(t.label+": this media currently lives in browser-local IndexedDB, not in a portable finishing folder");
     if(t.mediaRef?.startsWith("studio:"))
       warnings.push(t.label+": this is a browser-recorded stage file, not automatically a full-fidelity scene master");
     if(!q.width||!q.height)warnings.push(t.label+": original pixel dimensions not recorded");
     if(q.role==="replayable_scene")warnings.push(t.label+": full-fidelity scene replay renderer and material assets must accompany this transfer");
     if(q.role==="high_quality_render"&&!q.verified)warnings.push(t.label+": high-quality render has not been verified");
     if(!t.mediaRef)problems.push(t.label+": no media reference");
     if(t.mediaRef?.startsWith("temporary:"))warnings.push(t.label+": file is held only in this browser session; export or preserve it before closing");
   }
   if(!project.selections.length)warnings.push("No rough-cut coverage has been selected");
   return {readyForProfessionalFinishing:problems.length===0&&warnings.length===0,
     problems:[...new Set(problems)],warnings:[...new Set(warnings)],included};
 }
 function packageManifest(project,Core,options={}){
   Core.validateProject(project);
   const assessment=audit(project,Core),plan=Core.exportManifest(project);
   return {
     schema:"pubcast.professional-handoff",version:1,
     title:project.title,projectId:project.id,
     generatedAt:new Date().toISOString(),
     deliverableType:"editorial_interchange_not_final_film",
     qualityPromise:{
       noForcedProxyFinish:true,originalBytesMustBePreserved:true,
       sourceQualityMustBeVerified:true,fullResolutionReplayRenderingRequiredForVirtualScenes:true,
       warning:"A proxy or the current 1280x720 browser capture is NOT a cinema master. This manifest does not render or improve source resolution."
     },
     frameRate:options.frameRate||null,
     clock:{originUnixMs:project.originUnixMs,intervalUs:Core.INTERVAL_US},
     tracks:project.tracks.map(t=>({
       id:t.id,name:safeName(t.label),kind:t.kind,mediaRef:t.mediaRef,
       sourceStartUnixMs:t.sourceStartUnixMs,
       quality:qualityOf(t),durationUs:t.durationUs,
       clackerMarks:t.clackerMarks,manualOffsetUs:t.manualOffsetUs,
       sync:Core.alignment(project,t)
     })),
     editorial:plan,
     audit:assessment,
     instructions:[
       "Preserve the full-resolution recording originals and replayable scene data; never replace with a low-resolution preview.",
       "Relink camera/source media by full original filename and independent checksums where available.",
       "Apply exact integer-microsecond clacker alignment and manual track offsets from this manifest.",
       "Frame-quantize only as required by the destination timeline's declared timebase.",
       "CMX3600 is a simple one-track cuts reference, not a lossless transfer of multitrack audio or subframe sync.",
       "Use a verified full-fidelity rendering pipeline before declaring theatrical output capability."
     ]
   };
 }
 function toEDL(project,Core,rate){
   const fps=validFrameRate(Number(rate));
   Core.validateProject(project);
   const entries=Core.timelineEntries(project);
   if(entries.length>MAX_EDL_EVENTS)throw Error("CMX3600 limited to 999 events; split the cut");
   const tracks=new Map(project.tracks.map((t,i)=>[t.id,{track:t,reel:"P"+String(i+1).padStart(7,"0") }]));
   const name=safeName(project.title).replace(/[:\r\n]/g," ").slice(0,80);
   const lines=["TITLE: "+name,"FCM: NON-DROP FRAME","","* PUBCAST FRAME RATE: "+fps,
     "* EXPORT: SIMPLE CUTS + BLANK GAPS ONLY; RETAIN THE .pubcast-handoff.json FOR SYNC AND AUDIO"];
   const warnings=[];
   let recordFrame=BASE_TC_HOUR*3600*fps,recordOffsetUs=0;
   for(let i=0;i<entries.length;i++){
     const e=entries[i],isGap=e.kind==="gap";
     // Round cumulative sequence boundaries, rather than independently rounding
     // every shot. Otherwise fractional frame loss accumulates over hundreds of cuts.
     const nextOffsetUs=recordOffsetUs+e.durationUs;
     const durFrames=toFrames(nextOffsetUs,fps)-toFrames(recordOffsetUs,fps);
     if(durFrames<1)throw Error("A clip or gap is shorter than one frame at "+fps+" fps");
     const clipInfo=isGap?null:tracks.get(e.trackId);
     if(!isGap&&!clipInfo)throw Error("Missing source track for "+e.id);
     const sourceStart=isGap?0:Core.sourceTimeUs(project,e.trackId,e.inUs);
     const sourceEnd=isGap?e.durationUs:Core.sourceTimeUs(project,e.trackId,e.outUs);
     if(sourceStart<0||sourceEnd<0)throw Error("Negative source time for "+e.id+"; adjust sync before interchange");
     const sourceInFrame=isGap?0:toFrames(sourceStart,fps);
     const sourceFrames=toFrames(sourceEnd,fps)-sourceInFrame;
     if(!isGap&&Math.abs(sourceFrames-durFrames)>1)warnings.push(e.id+": source clock drift needs a separate conform step");
     const srcOutFrame=sourceInFrame+durFrames;
     const recordOut=recordFrame+durFrames;
     if(recordOut>24*3600*fps)throw Error("EDL record timecode overflows 24 hours");
     const reelId=isGap?"BL":clipInfo.reel;
     lines.push(String(i+1).padStart(3,"0")+"  "+reelId.padEnd(8," ")+" V     C        "+
       toTC(sourceInFrame,fps)+" "+toTC(srcOutFrame,fps)+" "+toTC(recordFrame,fps)+" "+toTC(recordOut,fps));
     if(isGap)lines.push("* PUBCAST BLANK SPACE ("+e.durationUs+" microseconds)");
     else{
       lines.push("* FROM CLIP NAME: "+safeName(clipInfo.track.label));
       lines.push("* PUBCAST SOURCE TRACK: "+clipInfo.track.id);
       if(clipInfo.track.manualOffsetUs)
         lines.push("* PUBCAST MANUAL OFFSET US: "+clipInfo.track.manualOffsetUs);
     }
     recordFrame=recordOut;recordOffsetUs=nextOffsetUs;
   }
   lines.push("");
   return {edl:lines.join("\n"),warnings,rate:fps,eventCount:entries.length,
     note:"CMX3600 times are non-drop and frame-quantized. Exact clacker/drift/subframe offsets require sidecar."};
 }
 return {validFrameRate,toFrames,toTC,qualityOf,audit,packageManifest,toEDL};
});
