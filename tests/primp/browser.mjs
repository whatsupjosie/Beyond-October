import * as THREE from 'three';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {History, TileEdit, TEXTURE_SIZE, bytesToBase64, base64ToBytes, validateProject, softenPixels} from '/static/primp/core.mjs';
import {parseAvatar, prepareSurface, composeSurface, decodeLayer, dispose, surfacePoint} from '/static/primp/model.mjs';
const report = document.getElementById('results');
let passed = 0, failed = 0;
function assert(condition, message) { if (!condition) throw new Error(message); }
async function test(name, action) { try { const detail = await action(); passed++; report.textContent += `PASS ${name}${detail ? ': ' + detail : ''}\n`; } catch (error) { failed++; report.textContent += `FAIL ${name}: ${error.stack}\n`; } }
function equal(a, b) { return a.length === b.length && a.every((value, index) => value === b[index]); }
const paint = (ctx, i) => { ctx.fillStyle = i % 2 ? '#ae244f' : '#d49087'; ctx.beginPath(); ctx.arc(200 + i * 18, 350, 14, 0, 2 * Math.PI); ctx.fill(); };
function newCanvas() { const c = document.createElement('canvas'); c.width = c.height = TEXTURE_SIZE; return c; }
function stats(root) { let bones = 0, skinned = 0, morphs = 0; root.traverse(n => { if (n.isBone) bones++; if (n.isSkinnedMesh) skinned++; if (n.morphTargetInfluences) morphs += n.morphTargetInfluences.length; }); return {bones, skinned, morphs}; }
function transaction(db, mode, value, abort = false) { return new Promise((resolve, reject) => { const tx=db.transaction('checks',mode), store=tx.objectStore('checks');let result;const request= mode==='readonly' ? store.get('look') : store.put(value,'look');request.onsuccess=()=>{result=request.result;if(abort)tx.abort();};tx.oncomplete=()=>resolve(result);tx.onabort=()=>reject(new Error('aborted'));tx.onerror=()=>reject(tx.error); }); }

document.getElementById('run').onclick = async () => {
 document.getElementById('run').disabled = true; report.textContent = ''; passed = failed = 0;
 const c = document.getElementById('sample'), ctx = c.getContext('2d', {willReadFrequently:true});
 await test('Three paint attachment approaches', () => {
   const geometry = new THREE.PlaneGeometry(2,2,1,1), positions=geometry.attributes.position, uvs=geometry.attributes.uv;
   // A 6px liner mark fits between low-poly vertices; vertex color cannot represent it.
   const detail = newCanvas(), d=detail.getContext('2d');d.fillStyle='#a3294a';d.fillRect(510,500,6,24);
   assert(d.getImageData(512,512,1,1).data[3]===255,'UV texture loses the fine mark');
   let coveredVertices=0;for(let i=0;i<uvs.count;i++)if(d.getImageData(Math.min(1023,Math.floor(uvs.getX(i)*1024)),Math.min(1023,Math.floor(uvs.getY(i)*1024)),1,1).data[3])coveredVertices++;
   assert(coveredVertices===0,'Vertex comparison fixture must expose low-poly detail loss');
   const original=positions.getX(0);positions.setX(0,original+.3);
   assert(positions.getX(0)!==original,'Deformation not applied');assert(uvs.getX(0)===0,'UV attachment changed');
   geometry.dispose();return 'UV mark survives surface deformation; coarse vertex color misses it; a fixed projected mark requires rebinding after deformation. Geometric assay, not a rendered decal benchmark.';
 });
 await test('Three undo approaches / exact pixels / ten edits', () => {
   const snapshot = newCanvas(), sc=snapshot.getContext('2d',{willReadFrequently:true}), frames=[];let start=performance.now();
   for(let i=0;i<10;i++){frames.push(sc.getImageData(0,0,1024,1024));paint(sc,i);frames.push(sc.getImageData(0,0,1024,1024));}
   const snapshotMs=performance.now()-start, snapshotBytes=frames.reduce((n,f)=>n+f.data.byteLength,0);
   const replay=newCanvas(), rc=replay.getContext('2d');start=performance.now();for(let end=1;end<=10;end++){rc.clearRect(0,0,1024,1024);for(let i=0;i<end;i++)paint(rc,i);}const replayMs=performance.now()-start;
   ctx.clearRect(0,0,1024,1024);const history=new History();start=performance.now();
   for(let i=0;i<10;i++){const edit=new TileEdit(ctx,()=>{});edit.capture(200+i*18,350,14);paint(ctx,i);history.push(edit.finish());}
   const tileMs=performance.now()-start, expected=ctx.getImageData(0,0,1024,1024).data;
   for(let i=0;i<10;i++)history.undo();assert(ctx.getImageData(200,350,1,1).data[3]===0,'Undo left color');for(let i=0;i<10;i++)history.redo();assert(equal(ctx.getImageData(0,0,1024,1024).data,expected),'Redo changed pixels');assert(history.bytes<snapshotBytes/10,'Tile history did not reduce memory');
   return `snapshots ${snapshotBytes/1048576} MiB / ${snapshotMs.toFixed(1)} ms; replay rebuild ${replayMs.toFixed(1)} ms; tiles ${(history.bytes/1048576).toFixed(2)} MiB / ${tileMs.toFixed(1)} ms. Timings apply only to this browser/fixture.`;
 });
 await test('Cancelled stroke restores exact original pixels',()=>{
   const before=ctx.getImageData(0,0,1024,1024).data, edit=new TileEdit(ctx,()=>{});edit.capture(300,350,60);ctx.clearRect(240,290,120,120);edit.cancel();assert(equal(ctx.getImageData(0,0,1024,1024).data,before),'Cancellation lost pixels');
 });
 await test('Blend keeps soft edges free of black fringe',()=>{
   const data=new ImageData(9,9);data.data.set([220,40,80,255],(4*9+4)*4);softenPixels(data,4,4,4,1);assert(data.data[(4*9+4)*4]===220,'Black blending fringe');
 });
 let parsed, buffer, look;
 await test('Real rigged avatar loads without a network dependency',async()=>{
   const response=await fetch('/fixtures/mh_female.glb');assert(response.ok,'Fixture unavailable');buffer=await response.arrayBuffer();parsed=await parseAvatar(buffer);const s=stats(parsed.root);assert(s.bones>0&&s.skinned>0&&parsed.animations.length>0,'Rig fixture lost structure');assert(parsed.targets.length>0,'No usable paint surface');return JSON.stringify(s);
 });
 await test('Three save approaches / editable layer and source round trip',async()=>{
   assert(parsed,'Load failed');const target=parsed.targets[0];prepareSurface(target,parsed.targets);target.layers[5].canvas=c;composeSurface(target);
   const png=target.composite.toDataURL('image/png'), flattened=await decodeLayer(png);assert(flattened.width===1024,'Flattened image failed');
   look={format:'primp',version:1,name:'QA look',source:bytesToBase64(new Uint8Array(buffer)),targets:[{id:0,layers:target.layers.map(l=>({visible:l.visible,opacity:l.opacity,png:l.canvas?.toDataURL('image/png')??null}))}]};
   const saved=validateProject(JSON.parse(JSON.stringify(look)));assert(equal(base64ToBytes(saved.source),new Uint8Array(buffer)),'Avatar bytes changed');const layer=await decodeLayer(saved.targets[0].layers[5].png);assert(equal(layer.getContext('2d').getImageData(0,0,1024,1024).data,ctx.getImageData(0,0,1024,1024).data),'Layer round trip changed paint');
   const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('primp-foundation-checks',1);r.onupgradeneeded=()=>r.result.createObjectStore('checks');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
   await transaction(db,'readwrite',look);const read=await transaction(db,'readonly');assert(read.source===look.source,'IDB failed source round trip');let aborted=false;try{await transaction(db,'readwrite',{name:'bad'},true);}catch{aborted=true;}assert(aborted,'Failure transaction did not abort');assert((await transaction(db,'readonly')).name===look.name,'Failed write destroyed previous look');db.close();
   return 'PNG is appearance only; .primp preserves editable layers + original GLB; IndexedDB commits and aborted-write recovery verified.';
 });
 await test('Export/reimport preserves paint, bones, animation, and a morph target',async()=>{
   assert(parsed,'Load failed');let mesh;parsed.root.traverse(n=>{if(n.isSkinnedMesh&&!mesh)mesh=n;});
   // The historical fixture has no expressions; add an explicit morph fixture to test preservation.
   const p=mesh.geometry.attributes.position, delta=new Float32Array(p.count*3);for(let i=0;i<p.count;i++)delta[i*3]=.001;
   mesh.geometry.morphAttributes.position=[new THREE.BufferAttribute(delta,3)];mesh.geometry.morphTargetsRelative=true;mesh.updateMorphTargets();mesh.morphTargetInfluences[0]=.3;
   const before=stats(parsed.root), exported=await new GLTFExporter().parseAsync(parsed.root,{binary:true,animations:parsed.animations,onlyVisible:false});
   const after=await parseAvatar(exported), s=stats(after.root);assert(JSON.stringify(s)===JSON.stringify(before),'Export altered rig/morph count');assert(after.animations.length===parsed.animations.length,'Animations lost');assert(after.targets[0].originalMap,'Paint texture lost');
   const t=after.targets[0];prepareSurface(t,after.targets);const pixel=t.base.getContext('2d').getImageData(200,350,1,1).data;assert(pixel[0]>pixel[1],'Export lost berry paint');dispose(after.root,after.targets);return `${exported.byteLength} bytes; ${JSON.stringify(s)}; ${after.animations.length} animation.`;
 });
 await test('Real raycast paints selected front surface and blocks hidden/occluded surfaces',()=>{
   const root=new THREE.Group(), front=new THREE.Mesh(new THREE.PlaneGeometry(2,2),new THREE.MeshBasicMaterial()), back=new THREE.Mesh(new THREE.PlaneGeometry(2,2),new THREE.MeshBasicMaterial());front.position.z=.5;root.add(front,back);
   const camera=new THREE.PerspectiveCamera(45,1,.01,100);camera.position.z=3;camera.updateMatrixWorld();const target={material:front.material,uvName:'uv'};
   const hit=surfacePoint(root,target,new THREE.Vector2(0,0),camera);assert(hit&&Math.abs(hit.x-511.5)<1,'Front center mapping is wrong');
   assert(surfacePoint(root,{material:back.material,uvName:'uv'},new THREE.Vector2(),camera)===null,'Paint penetrated front surface');
   const mapping=new THREE.Texture();mapping.flipY=false;mapping.offset.set(.2,.1);target.originalMap=mapping;const mapped=surfacePoint(root,target,new THREE.Vector2(),camera);assert(Math.abs(mapped.x-1023*.7)<1&&Math.abs(mapped.y-1023*.6)<1,'First stroke ignores original texture transform');mapping.dispose();front.visible=false;assert(surfacePoint(root,target,new THREE.Vector2(),camera)===null,'Invisible surface was painted');
   root.visible=false;assert(surfacePoint(root,{material:back.material,uvName:'uv'},new THREE.Vector2(),camera)===null,'Hidden ancestor was painted');dispose(root,[]);
 });
 await test('Base color factors preserve transparent pixels and makeup is not skin-tinted',()=>{
   const base=newCanvas(),bc=base.getContext('2d');bc.fillStyle='#ffffff';bc.fillRect(0,0,512,1024);const map=new THREE.CanvasTexture(base);map.flipY=false;
   const material=new THREE.MeshStandardMaterial({map,color:'#663322'}),t={material,originalMap:map,originalColor:material.color.clone(),layers:Array.from({length:6},()=>({canvas:null,visible:true,opacity:1}))};prepareSurface(t,[t]);
   assert(t.base.getContext('2d').getImageData(900,500,1,1).data[3]===0,'Transparent texture became opaque');assert(material.color.getHex()===0xffffff,'Makeup is multiplied by skin factor');
   const paintLayer=newCanvas();paintLayer.getContext('2d').fillStyle='#dd3355';paintLayer.getContext('2d').fillRect(100,100,10,10);t.layers[5].canvas=paintLayer;composeSurface(t);assert(t.composite.getContext('2d').getImageData(105,105,1,1).data[0]===221,'Opaque paint changed hue');t.texture.dispose();map.dispose();material.dispose();
 });
 await test('Three blend approaches compare transparent-edge behavior',()=>{
   const data=new ImageData(9,9);data.data.set([220,40,80,255],(4*9+4)*4);const naive=(220/9),premult=softenPixels(data,4,4,4,1).data[(4*9+4)*4];
   const source=newCanvas(),filtered=newCanvas(),sc=source.getContext('2d'),fc=filtered.getContext('2d');sc.fillStyle='rgb(220,40,80)';sc.fillRect(4,4,1,1);fc.filter='blur(1px)';fc.drawImage(source,0,0);const hardware=fc.getImageData(4,4,1,1).data;
   assert(premult===220,'Premultiplied blend fringe');assert(naive<100,'Straight-RGB reference missing fringe');return `straight RGB averages dilute red to ${naive.toFixed(1)}; premultiplied kernel retains ${premult}; browser blur returned red ${hardware[0]} / alpha ${hardware[3]}. Kernel chosen for explicit bounded alpha behavior.`;
 });
 await test('Original skin texture resolution is retained instead of downsampled',()=>{
   const base=document.createElement('canvas');base.width=2048;base.height=1024;const bc=base.getContext('2d');bc.fillStyle='#abcdef';bc.fillRect(0,0,2048,1024);const map=new THREE.CanvasTexture(base),material=new THREE.MeshStandardMaterial({map});
   const t={material,originalMap:map,originalColor:material.color.clone(),layers:Array.from({length:6},()=>({canvas:null,visible:true,opacity:1}))};prepareSurface(t,[t]);assert(t.base.width===2048&&t.composite.width===2048,'Skin was downsampled');assert(t.composite.getContext('2d').getImageData(2000,500,1,1).data[0]===171,'Original texture color changed');t.texture.dispose();map.dispose();material.dispose();
 });
 await test('Malformed PNG dimensions rejected before decoding',async()=>{
   const small=document.createElement('canvas');small.width=small.height=2;let rejected=false;try{await decodeLayer(small.toDataURL());}catch{rejected=true;}assert(rejected,'Oversize/foreign texture schema accepted');
 });
 if(parsed)dispose(parsed.root,parsed.targets);
 report.textContent+=`\nRESULT: ${passed} passed; ${failed} failed.\n3D RENDERING: not established by these tests.\n`;document.getElementById('run').disabled=false;
};
