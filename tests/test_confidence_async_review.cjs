const test=require('node:test'),assert=require('node:assert/strict');
const View=require('../static/studio25d_remote_feed.js'),Pub=require('../static/production25d_frame_publisher.js');
function target(){return {image:{hidden:true,src:'',removeAttribute(){this.src='';}},status:{style:{}}};}
const response=(age='0')=>({ok:true,headers:{get:name=>name==='content-type'?'image/jpeg':age},blob:async()=>({size:400})});
test('Director source changes cancel a decoder that never resolves',async()=>{
 const t=target();let decoding,wait=new Promise(resolve=>{decoding=resolve;});
 const viewer=View.create({targets:{program:t},fetch:async()=>response(),decode:()=>{decoding();return new Promise(()=>{});},urlAPI:{createObjectURL:()=> 'blob:review',revokeObjectURL(){}}});
 viewer.setSources('p25d_news_anchor',null);const pending=viewer.refresh();await wait;
 viewer.setSources('p25d_news_coanchor',null);await pending;
 assert.equal(t.image.hidden,true);viewer.stop();
});
test('Director rejects missing or negative age and includes time spent decoding',async()=>{
 for(const age of [null,'-1','4900']){
  const t=target();let now=0;
  const viewer=View.create({targets:{program:t},now:()=>now,fetch:async()=>response(age),decode:async()=>{now+=200;},urlAPI:{createObjectURL:()=> 'blob:review',revokeObjectURL(){}}});
  viewer.setSources('p25d_news_anchor',null);await viewer.refresh();assert.equal(t.image.hidden,true);viewer.stop();
 }
});
test('stopping the stage publisher cancels a hung encoder and releases busy state',async()=>{
 const pub=Pub.create({session:'pubcast25d-review-001',sourceId:id=>'p25d_news_'+id,encode:()=>new Promise(()=>{}),fetch:async()=>({ok:true})});
 const pending=pub.publish('anchor',{},1000);await Promise.resolve();await pub.stop();assert.equal(await pending,false);assert.equal(pub.status().busy,false);
});
test('publisher pacing and recovery share a monotonic clock',async()=>{
 let time=1000,healthy=false,calls=0;
 const pub=Pub.create({session:'pubcast25d-clock-review',sourceId:id=>'p25d_news_'+id,now:()=>time,encode:async()=>({size:400}),fetch:async(path,init)=>{
  if(init.method==='DELETE')return {ok:true};calls++;return healthy?{ok:true,json:async()=>({ok:true,source_id:'p25d_news_anchor',sequence:1})}:{ok:false,status:503};}});
 for(let i=0;i<5;i++){await pub.publish('anchor',{});time+=300;}
 assert.equal(calls,5);assert.equal(await pub.publish('anchor',{}),false);
 time+=5001;healthy=true;assert.equal(await pub.publish('anchor',{}),true);await pub.stop();
});
test('publisher never reports a non-positive sequence as a live frame',async()=>{
 for(const sequence of [0,-1]){
  let reported=false;
  const pub=Pub.create({session:'pubcast25d-ack-review',sourceId:id=>'p25d_news_'+id,encode:async()=>({size:400}),onState:s=>{if(s.live)reported=true;},fetch:async(path,init)=>({ok:true,json:async()=>({ok:true,source_id:'p25d_news_anchor',sequence})})});
  assert.equal(await pub.publish('anchor',{},1000),false);assert.equal(reported,false);assert.equal(pub.status().acknowledged,0);await pub.stop();
 }
});
