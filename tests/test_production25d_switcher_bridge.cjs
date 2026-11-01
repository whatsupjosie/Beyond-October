/* Shared 2.5D stage cameras flow through the same canonical switcher used by Control Room. */
const test=require("node:test"), assert=require("node:assert/strict");
const Core=require("../static/production25d_core.js");
const Bridge=require("../static/production25d_switcher_bridge.js");

function fakeServer() {
 let sources=[],program="wide_shot",preview="medium_shot",requests=[],transition={type:"cut",duration_ms:0};
 const result=()=>({sources:sources.slice(),program,preview,transition:{...transition}});
 async function fetch(path,init={}) {
  requests.push({path,init});const body=init.body?JSON.parse(init.body):{};
  if(path==="/api/switcher/state")return {ok:true,json:async()=>result()};
  if(path==="/api/cameras/register"){sources.push({id:body.source_id,name:body.name});return {ok:true,json:async()=>({ok:true})};}
  if(path==="/api/switcher/select"){
    if(!sources.some(s=>s.id===body.program)||!sources.some(s=>s.id===body.preview))return {ok:false,status:404};
    program=body.program;preview=body.preview;return {ok:true,json:async()=>result()};
  }
  if(path.startsWith("/api/switcher/cut/")){program=decodeURIComponent(path.split("/").pop());return {ok:true,json:async()=>result()};}
  if(path.startsWith("/api/switcher/preview/")){preview=decodeURIComponent(path.split("/").pop());return {ok:true,json:async()=>result()};}
  if(path==="/api/switcher/cut"||path==="/api/switcher/transition"){
    [program,preview]=[preview,program];transition={type:path.endsWith("transition")?"dissolve":"cut",duration_ms:path.endsWith("transition")?body.duration_ms:0};
    return {ok:true,json:async()=>result()};
  }
  throw Error("Unexpected HTTP "+path);
 }
 return {fetch,requests,result};
}

test("one shared switcher registers genre cameras and actually switches",async()=>{
 const server=fakeServer(),events=[];
 const bridge=Bridge.create({fetch:server.fetch,onState:s=>events.push(s),setInterval:()=>1,clearInterval:()=>{}});
 const status=await bridge.attach(Core.PACKAGES.news);
 assert.equal(status.shared,true);assert.equal(server.result().sources.length,5);
 assert.equal(server.result().program,"p25d_news_wide");
 assert.equal(server.result().preview,"p25d_news_anchor");
 await bridge.choosePreview("coanchor");
 assert.equal(server.result().preview,"p25d_news_coanchor");
 await bridge.take();
 assert.equal(server.result().program,"p25d_news_coanchor");
 assert.equal(server.result().preview,"p25d_news_wide");
 await bridge.take(true);
 assert.equal(server.result().program,"p25d_news_wide");
 assert.equal(server.result().transition.type,"dissolve");
 assert.ok(events.length>=4);
 bridge.detach();assert.equal(bridge.connected(),false);
});

test("offline operation never falsely reports server connectivity",async()=>{
 const bridge=Bridge.create({fetch:()=>Promise.reject(Error("no host"))});
 const result=await bridge.attach(Core.PACKAGES.game);
 assert.equal(result.shared,false);assert.match(result.reason,/no host/);assert.equal(bridge.connected(),false);
});

test("external cameras remain explicitly unsupported by local renderer",async()=>{
 const server=fakeServer(),events=[];
 const bridge=Bridge.create({fetch:server.fetch,onState:s=>events.push(s),setInterval:()=>1,clearInterval:()=>{}});
 await bridge.attach(Core.PACKAGES.variety);
 const original=server.result();
 // Simulate a server change to the global Program source outside this genre:
 const response=await server.fetch("/api/switcher/cut/wide_shot",{method:"POST"});
 assert.equal((await response.json()).program,"wide_shot");
 const state=await bridge.refresh();
 assert.equal(state.program,null);assert.equal(state.remoteProgram,"wide_shot");
 bridge.detach();
});
