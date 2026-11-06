const test=require('node:test'),assert=require('node:assert/strict');
const C=require('../static/editor_sync_core.js'),X=require('../static/editor_interchange.js');
function source(){const p=C.createProject('Bounds',0,'bounds');C.addTrack(p,{id:'cam',kind:'camera',label:'take.webm',mediaRef:'file:take.webm',durationUs:2000000});return p;}
test('EDL cannot select frames beyond the available recorded source',()=>{
 const p=source();C.addSelection(p,{id:'clip',trackId:'cam',inUs:1500000,outUs:2500000});
 for(const fps of [24,25,30])assert.throws(()=>X.toEDL(p,C,fps),/source.*duration|available.*source/i);
});
test('positive 30ms correction cannot push an export past the recorded source',()=>{
 const p=source();C.addSelection(p,{id:'clip',trackId:'cam',inUs:1000000,outUs:2000000});C.setOffsetSeconds(p,'cam','0.030');
 assert.throws(()=>X.toEDL(p,C,30),/source.*duration|available.*source/i);
});
test('handoff audit identifies requested footage missing from available source',()=>{
 const p=source();C.addSelection(p,{id:'clip',trackId:'cam',inUs:1500000,outUs:2500000});
 assert(X.audit(p,C).problems.some(x=>/source.*duration|available.*source/i.test(x)));
});
