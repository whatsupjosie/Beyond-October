/* node --test tests/test_editor_sync_interchange.cjs
 * Offline-first editorial handoff, exact clacker and conservative CMX3600 checks.
 * No proprietary finishing/editor assets or optional npm packages.
 */
const test=require("node:test");
const assert=require("node:assert/strict");
const C=require("../static/editor_sync_core.js");
const X=require("../static/editor_interchange.js");

function shoot(){
 const p=C.createProject("Take One",1700000000000,"edit-test");
 C.addTrack(p,{id:"cam1",kind:"camera",label:"CAM 01.mov",mediaRef:"temporary:CAM 01.mov"});
 C.addTrack(p,{id:"cam2",kind:"camera",label:"CAM 02.mov",mediaRef:"local:cam2"});
 C.addTrack(p,{id:"voice",kind:"audio",label:"Dialogue.wav",mediaRef:"local:voice"});
 for(const track of p.tracks) {
   C.addClackerMark(p,track.id,0,0);
   C.addClackerMark(p,track.id,1,15000000);
 }
 return p;
}
test("clacker reference is exactly fifteen seconds and offset is microsecond-accurate",()=>{
 const p=shoot();assert.equal(C.INTERVAL_US,15000000);
 assert.equal(C.setOffsetSeconds(p,"cam1","0.030"),30000);
 assert.equal(C.sourceTimeUs(p,"cam1",10000000),10030000);
 assert.equal(C.editTimeUs(p,"cam1",10030000),10000000);
 assert.equal(C.adjustOffsetSeconds(p,"cam1","-0.015"),15000);
 assert.equal(C.formatSeconds(p.tracks[0].manualOffsetUs),"0.015000");
});
test("wrong clacker drift is rejected before corrupt project save",()=>{
 const p=shoot();
 C.addClackerMark(p,"cam1",2,35000000);
 assert.throws(()=>C.validateProject(p),/drift exceeds/);
});
test("clacker drift fit describes measured rate and maps correct media time",()=>{
 const p=shoot();
 C.addClackerMark(p,"cam1",1,15001500);
 const a=C.alignment(p,p.tracks[0]);
 assert.ok(a.driftPpm>90&&a.driftPpm<110);
 assert.equal(C.sourceTimeUs(p,"cam1",30000000),30003000);
});
test("arbitrary 0.03 timing correction cannot affect another camera",()=>{
 const p=shoot();C.setOffsetSeconds(p,"cam1","0.030");
 assert.equal(C.sourceTimeUs(p,"cam2",10000000),10000000);
 assert.equal(C.sourceTimeUs(p,"voice",10000000),10000000);
});
test("rough-cut split, lift, ripple-delete and remove-gap preserve source originals",()=>{
 const p=shoot();
 C.addSelection(p,{id:"a",trackId:"cam1",inUs:0,outUs:2000000});
 C.addSelection(p,{id:"b",trackId:"cam2",inUs:2000000,outUs:4000000});
 const [left,right]=C.splitAt(p,"a",1000000);
 assert.equal(left.outUs,1000000);assert.equal(right.inUs,1000000);
 C.deleteSelection(p,"a",false);
 assert.deepEqual(C.timelineEntries(p).map(x=>x.kind),["gap","shot","shot"]);
 const gap=p.selections[0];
 assert.throws(()=>C.deleteSelection(p,gap.id,false),/blank interval/);
 assert.equal(C.closeGaps(p),1);
 assert.deepEqual(C.timelineEntries(p).map(x=>x.timelineInUs),[0,1000000]);
 C.deleteSelection(p,right.id,true);
 assert.equal(p.selections.length,1);
 assert.equal(p.tracks[0].mediaRef,"temporary:CAM 01.mov");
});
test("CMX3600 requires explicit supported non-drop timebase",()=>{
 for(const fps of [24,25,30])assert.equal(X.validFrameRate(fps),fps);
 for(const fps of [23.976,29.97,60,0])assert.throws(()=>X.validFrameRate(fps));
});
test("CMX3600 yields source in/out and sequential record in/out",()=>{
 const p=shoot();C.setOffsetSeconds(p,"cam1","0.030");
 C.addSelection(p,{id:"s1",trackId:"cam1",inUs:10000000,outUs:11000000});
 C.addSelection(p,{id:"s2",trackId:"cam2",inUs:20000000,outUs:22000000});
 const result=X.toEDL(p,C,30);
 assert.equal(result.rate,30);assert.equal(result.eventCount,2);
 assert.match(result.edl,/001\s+P0000001\s+V\s+C\s+00:00:10:01 00:00:11:01 01:00:00:00 01:00:01:00/);
 assert.match(result.edl,/002\s+P0000002\s+V\s+C\s+00:00:20:00 00:00:22:00 01:00:01:00 01:00:03:00/);
});
test("CMX3600 quantizes cumulative boundaries, not each cut independently",()=>{
 const p=shoot();
 for(let i=0;i<100;i++)C.addSelection(p,{
   id:"shot-"+i,trackId:"cam1",inUs:1000000+i*50000,outUs:1000000+(i+1)*50000
 });
 const e=X.toEDL(p,C,24).edl.split("\n").filter(x=>/^\d{3}\s+/.test(x));
 assert.equal(e.length,100);
 const end=e[e.length-1].trim().split(/\s+/).at(-1);
 assert.equal(end,"01:00:05:00","100 x 50ms clips must total 5 seconds, not 100 independently-rounded 2-frame clips");
});
test("sub-frame or negative-source EDL edits fail rather than silently change cuts",()=>{
 const p=shoot();C.addSelection(p,{id:"too-small",trackId:"cam1",inUs:0,outUs:100});
 assert.throws(()=>X.toEDL(p,C,24),/shorter than one frame/);
 p.selections=[];C.setOffsetSeconds(p,"cam1","-0.030");
 C.addSelection(p,{id:"negative",trackId:"cam1",inUs:0,outUs:1000000});
 assert.throws(()=>X.toEDL(p,C,30),/Negative source time/);
});
test("full sidecar retains manual microsecond offset and rejects unsupported master quality",()=>{
 const p=shoot();C.setOffsetSeconds(p,"cam1","0.030");
 C.addSelection(p,{id:"s1",trackId:"cam1",inUs:1000000,outUs:2000000});
 const pack=X.packageManifest(p,C,{frameRate:24});
 assert.equal(pack.deliverableType,"editorial_interchange_not_final_film");
 assert.equal(pack.editorial.shots[0].manualOffsetUs,30000);
 assert.equal(pack.editorial.shots[0].sourceInUs,1030000);
 assert.equal(pack.audit.readyForProfessionalFinishing,false);
 assert.ok(pack.audit.warnings.some(w=>/source/.test(w)||/unverified/.test(w)));
});
test("simply tagging low-res footage as cinema master never clears provenance gate",()=>{
 const p=shoot();
 C.addSelection(p,{id:"s1",trackId:"cam1",inUs:0,outUs:1000000});
 p.tracks[0].quality={role:"high_quality_render",width:4096,height:2160,verified:false,bytePreserved:false};
 const a=X.audit(p,C);
 assert.equal(a.readyForProfessionalFinishing,false);
 assert.ok(a.problems.some(x=>/bytes/.test(x)));
});
test("frame rounding, gap and shot event identifiers remain in handoff",()=>{
 const p=shoot();C.addSelection(p,{id:"s1",trackId:"cam1",inUs:0,outUs:1000000});
 C.gap(p,1000000,"rest");
 C.addSelection(p,{id:"s2",trackId:"cam1",inUs:2000000,outUs:3000000});
 const out=X.toEDL(p,C,25);
 assert.equal(out.eventCount,3);assert.match(out.edl,/BL\s+V/);
 assert.equal(C.exportManifest(p).shots[1].kind,"gap");
 assert.equal(C.exportManifest(p).shots[2].timelineInUs,2000000);
});
