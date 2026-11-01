/* node --test tests/test_production25d_wiring.cjs
 * Static contract checks, not browser/runtime verification. */
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../static"),read=p=>fs.readFileSync(path.join(root,p),"utf8");
const html=read("production25d.html"),app=read("production25d_app.js"),renderer=read("production25d_renderer.js");
test("HTML script dependencies are in correct order and present",()=>{
 const scripts=[...html.matchAll(/<script[^>]*src="\.\/([^"]+)"/g)].map(x=>x[1]);
 for(const s of ["production25d_core.js","production25d_renderer.js","production25d_storage.js","world_walk_glb.js","production25d_app.js"])assert.ok(scripts.includes(s),s+" absent");
 for(const s of scripts)assert.ok(fs.existsSync(path.join(root,s)),s+" missing");
 assert.ok(scripts.indexOf("production25d_core.js")<scripts.indexOf("production25d_app.js"));
 assert.ok(scripts.indexOf("production25d_renderer.js")<scripts.indexOf("production25d_app.js"));
 assert.ok(scripts.indexOf("production25d_storage.js")<scripts.indexOf("production25d_app.js"));
});
test("all referenced control IDs exist in HTML",()=>{
 const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]));
 const refs=new Set([...app.matchAll(/\$\("([^"]+)"\)/g)].map(x=>x[1]));
 for(const id of refs)assert.ok(ids.has(id),"missing DOM element: "+id);
 const map=app.match(/const el=\{([\s\S]*?)\};/);
 assert.ok(map,"UI bindings not found");
 for(const match of map[1].matchAll(/:\$\("([^"]+)"\)/g))assert.ok(ids.has(match[1]),"missing bound DOM: "+match[1]);
});
test("local recording and persistence are real browser API paths, not placeholders",()=>{
 assert.match(app,/\.captureStream\(/);
 assert.match(app,/new MediaRecorder\(/);
 assert.match(app,/Store\.save\(/);
 assert.match(app,/Store\.read\(/);
 assert.match(app,/state\.avatarBridge/);
 assert.match(renderer,/glb\.draw\(/);
});
test("3D fixture paths exist",()=>{
 for(const file of ["MakeHuman_Female.glb","MakeHuman_Male.glb"])assert.ok(fs.existsSync(path.join(root,"world/test_avatars",file)),file+" missing");
});
test("Control Room has an entry to 2.5D console",()=>assert.match(read("control_room.html"),/production25d\.html/));
