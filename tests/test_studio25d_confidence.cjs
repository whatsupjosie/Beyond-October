const test=require("node:test"),assert=require("node:assert/strict");
const Pub=require("../static/production25d_frame_publisher.js");
const View=require("../static/studio25d_remote_feed.js");
test("program and preview publish distinct acknowledged frames",async()=>{
 const calls=[];
 const p=Pub.create({session:"pubcast25d-test-001",sourceId:id=>"p25d_news_"+id,
  encode:async()=>({size:1000}),
  fetch:async(path,options)=>{calls.push([path,options]);return options.method==="DELETE"?{ok:true}:{ok:true,json:async()=>({ok:true,source_id:path.split("/").pop(),sequence:1})};}});
 assert.deepEqual(await Promise.all([p.publish("wide",{},1000),p.publish("anchor",{},1000)]),[true,true]);
 assert.equal(calls.length,2);assert.equal(await p.publish("wide",{},1010),false);
 await p.stop();assert.equal(calls.at(-1)[1].method,"DELETE");
});
test("remote monitor rejects stale content without pretending it is live",async()=>{
 const img={hidden:true,src:"",removeAttribute(){this.src=""}},status={style:{}};
 const viewer=View.create({targets:{program:{image:img,status}},decode:async()=>{},
  fetch:async()=>({ok:false,status:503}),urlAPI:{createObjectURL:()=>"",revokeObjectURL:()=>{}}});
 viewer.setSources("p25d_news_wide",null);
 await viewer.refresh();assert.equal(img.hidden,true);assert.match(status.textContent,/NO FRESH/);
 viewer.stop();
});
test("delegated camera handover does not throttle unrelated camera feeds",async()=>{
 let accepted=0;
 const p=Pub.create({session:"pubcast25d-handover-001",sourceId:id=>"p25d_news_"+id,encode:async()=>({size:1000}),
  fetch:async path=>path.endsWith('anchor')?{ok:false,status:409,json:async()=>({detail:"Camera rendering is assigned to a pool participant"})}
    :{ok:true,json:async()=>({ok:true,source_id:path.split('/').pop(),sequence:++accepted})}});
 for(let i=0;i<8;i++)assert.equal(await p.publish('anchor',{},1000+i*300),false);
 assert.equal(p.status().errors,0);assert.equal(await p.publish('wide',{},4000),true);
});
