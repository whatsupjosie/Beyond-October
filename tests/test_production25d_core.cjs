/* Run: node --test tests/test_production25d_core.cjs
 * Dependency-free regression coverage of seven genre packages and session invariants. */
const test=require("node:test"), assert=require("node:assert/strict");
const C=require("../static/production25d_core.js");
test("eight independently configured genre packages",()=>{
 assert.equal(Object.keys(C.PACKAGES).length,8);
 const signatures=new Set();
 for(const [id,p] of Object.entries(C.PACKAGES)){
  assert.equal(C.validate(p),true);
  assert.equal(id,p.id);
  assert.ok(p.cameras.length>=5,id+" has insufficient shots");
  assert.ok(p.performers.length>=2,id+" has insufficient performers");
  const frames=p.cameras.map(c=>C.viewport(c));
  for(const f of frames){assert.ok(f.x>=0&&f.y>=0&&f.w>0&&f.h>0);assert.ok(f.x+f.w<=C.W+.001&&f.y+f.h<=C.H+.001);}
  assert.ok(new Set(frames.map(f=>JSON.stringify(f))).size>=3,id+" lacks distinct real viewports");
  signatures.add(JSON.stringify([p.furnishings,p.performers.map(x=>x.slot),p.cameras.map(x=>x.center)]));
 }
 assert.equal(signatures.size,8,"genres must not be identical renamed packages");
});
test("unknown shots are rejected",()=>assert.throws(()=>C.shot(C.PACKAGES.news,"invalid"),/Unknown shot/));
test("invalid geometry and duplicate camera identifiers are rejected",()=>{
 const pkg=structuredClone(C.PACKAGES.news);
 pkg.cameras[1].id=pkg.cameras[0].id;
 assert.throws(()=>C.validate(pkg),/Duplicate camera/);
 pkg.cameras[1].id="distinct";pkg.cameras[1].zoom=0;
 assert.throws(()=>C.validate(pkg),/Invalid zoom/);
 pkg.cameras[1].zoom=2;pkg.cameras[1].center=[1.2,.5];
 assert.throws(()=>C.validate(pkg),/Invalid center/);
});
test("production event timeline and closure are enforced",()=>{
 const s=C.makeSession(C.PACKAGES.debate,1700000000000);
 const e=C.event(s,"camera.cut",{from:"wide",to:"moderator"},1700000001250);
 assert.equal(e.offsetMs,1250);assert.deepEqual(e.payload,{from:"wide",to:"moderator"});
 C.finish(s,1700000005000);
 assert.equal(s.events.length,1);assert.ok(s.endedAt);
 assert.throws(()=>C.event(s,"cue",{},1700000006000),/closed/);
 assert.throws(()=>C.finish(s,1700000006000),/closed/);
});
test("camera viewport always remains inside source frame",()=>{
 for(const p of Object.values(C.PACKAGES))for(const shot of p.cameras){
  const f=C.viewport(shot);
  assert.ok(f.x>=0&&f.y>=0&&f.x+f.w<=1280+.001&&f.y+f.h<=720+.001);
 }
});
