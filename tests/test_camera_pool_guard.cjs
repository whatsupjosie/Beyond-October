const test=require('node:test'),assert=require('node:assert/strict');
const {Guard,UploadBudget}=require('../static/camera_pool_guard.js');
function baseline(){const g=new Guard();for(let i=0;i<50;i++)g.sample(16.7,i*16.7);return g;}
test('calibration precedes donated work and a stall pauses it',()=>{
 const g=new Guard();assert.equal(g.report(0).work_scale,0);
 for(let i=0;i<50;i++)g.sample(16.7,i*16.7);
 assert.equal(g.report(1000).state,'running');g.sample(350,1300);
 assert.equal(g.report(1400).state,'paused');assert.equal(g.report(1400).work_scale,0);
 assert.equal(g.report(1400,false,false).preview_width,640);
 assert.equal(g.report(1400,false,true).preview_width,320);
});
test('persistent lag backs off, smooth recovery is gradual, hidden pauses',()=>{
 const g=baseline();for(let i=0;i<90;i++)g.sample(65,1000+i*65);
 assert.ok(g.scale<1);assert.equal(g.report(7000).state,'reduced');
 const reduced=g.scale;for(let i=0;i<300;i++)g.sample(16.7,8000+i*16.7);
 assert.ok(g.scale<=reduced);for(let i=0;i<2200;i++)g.sample(16.7,14000+i*16.7);
 assert.equal(g.scale,1);assert.equal(g.report(40000,true).work_scale,0);
});
test('held contributions do not restart just because the UI becomes idle',()=>{
 const g=baseline();g.held=true;g.reason='Repeated slow camera jobs';
 for(let i=0;i<4000;i++)g.sample(16.7,1000+i*16.7);
 assert.equal(g.report(100000).state,'paused');assert.equal(g.report(100000).work_scale,0);
 assert.equal(g.report(100000).reason,'Repeated slow camera jobs');
});
test('a poor baseline does not permit a large new UI stall',()=>{
 const g=new Guard();for(let i=0;i<50;i++)g.sample(130,i*130);
 assert.equal(g.report(7000).state,'paused');assert.equal(g.report(7000).work_scale,0);
 for(let i=0;i<70;i++)g.sample(16.7,8000+i*16.7);
 assert.equal(g.report(10000).state,'running');g.sample(450,11000);assert.equal(g.report(11100).state,'paused');
});
test('permitted quality reduction stays stable through rate recovery',()=>{
 const g=baseline();g.pause(1000,'overload');assert.equal(g.report(1100,false,true).preview_width,320);
 g.scale=1;assert.equal(g.report(100000,false,true).preview_width,320);
 assert.equal(g.report(100000,false,false).preview_width,640);
});
test('outgoing camera payload obeys the consented rolling bandwidth cap before sending',()=>{
 const b=new UploadBudget();for(let i=0;i<6;i++)assert.equal(b.reserve(5000,256,i*10),true);
 assert.equal(b.reserve(5000,256,999),false);assert.equal(b.reserve(5000,256,1000),true);
 assert.equal(b.reserve(40000,256,2000),false);assert.equal(b.reserve(NaN,256,2000),false);
});
