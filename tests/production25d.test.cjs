/* Deterministic Node tests for the 2.5D production core and compositor.
 * Run: node tests/production25d.test.cjs
 * This tests structure and drawing instructions, NOT browser/WebGL/MediaRecorder behavior.
 */
"use strict";
const assert=require("node:assert/strict");
const C=require("../static/production25d_core.js");
const R=require("../static/production25d_renderer.js");
let count=0;
function check(fn){fn();count++;}
check(()=>assert.deepEqual(Object.keys(C.PACKAGES).sort(),
 ["news","late_night","debate","political_discussion","audience","game","variety","general"].sort()));
for(const [id,pkg] of Object.entries(C.PACKAGES)){
 check(()=>assert.equal(C.validate(pkg),true,id));
 check(()=>assert.ok(pkg.cameras.length>=5,id));
 check(()=>assert.ok(new Set(pkg.cameras.map(c=>JSON.stringify(C.viewport(c)))).size>=3,id));
 check(()=>assert.ok(pkg.performers.length>=2,id));
}
check(()=>assert.throws(()=>C.validate({id:"bad",cameras:[]}),/Invalid production package/));
check(()=>assert.throws(()=>C.shot(C.PACKAGES.news,"missing"),/Unknown shot/));
const anchor=C.shot(C.PACKAGES.news,"anchor");
check(()=>assert.equal(C.viewport(anchor).w,C.W/anchor.zoom));
check(()=>assert.ok(C.viewport(anchor).x>=0&&C.viewport(anchor).y>=0));
const now=Date.UTC(2026,9,30,20,0,0);
const session=C.makeSession(C.PACKAGES.news,now);
check(()=>assert.equal(session.packageId,"news"));
const payload={from:"wide",to:"anchor"};C.event(session,"camera.cut",payload,now+1000);
payload.to="changed";
check(()=>assert.equal(session.events[0].payload.to,"anchor"));
check(()=>assert.equal(session.events[0].offsetMs,1000));
C.finish(session,now+4500);
check(()=>assert.equal(session.endedAt,new Date(now+4500).toISOString()));
check(()=>assert.throws(()=>C.event(session,"after.stop",{},now+5000),/closed/));
function fakeContext(trace){
 return {
  save(){},restore(){},clearRect(){},setTransform(){},fillRect(){},beginPath(){},
  arc(){},fill(){},stroke(){},moveTo(){},lineTo(){},translate(){},fillText(){},
  createLinearGradient(){return {addColorStop(){}}},
  drawImage(...args){trace.push(args)},
  set fillStyle(v){},set strokeStyle(v){},set lineWidth(v){},
  set font(v){},set textAlign(v){}
 };
}
const actions=[], dest=fakeContext(actions), world={getContext(){return fakeContext([])}};
const empty={assets:{},performers:[],scores:[0,0],lowerThird:false,blackout:false};
for(const camera of C.PACKAGES.news.cameras)R.renderCamera(dest,C.PACKAGES.news,camera,empty,world,0);
check(()=>assert.equal(actions.length,C.PACKAGES.news.cameras.length));
check(()=>assert.notDeepEqual(actions[0].slice(1,5),actions[1].slice(1,5)));
const glbDraw=[], stage={...empty,performers:[{id:"p1",position:[.5,.8],moving:true,vx:1,vy:0}],avatarBridge:{has(){return true},draw(...args){glbDraw.push(args)}}};
R.renderCamera(dest,C.PACKAGES.general,C.PACKAGES.general.cameras[0],stage,world,.04);
check(()=>assert.equal(glbDraw.length,1));
check(()=>assert.equal(glbDraw[0][1],"p1"));
check(()=>assert.equal(glbDraw[0][5].dt,.04));
console.log("PubCast 2.5D core and renderer: "+count+" assertions passed.");
