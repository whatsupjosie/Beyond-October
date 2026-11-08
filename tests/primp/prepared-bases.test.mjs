import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {validateGLB} from '../../static/primp/core.mjs';
import {buildIslandAtlas} from '../../static/primp/uv-islands.mjs';
const root=new URL('../../',import.meta.url);
const read=path=>new Uint8Array(readFileSync(new URL(path,root)));
function unpack(bytes) {
 const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),size=v.getUint32(12,true);
 return {json:JSON.parse(new TextDecoder().decode(bytes.subarray(20,20+size))),binary:bytes.subarray(28+size)};
}
function data(model,id) {
 const a=model.json.accessors[id],b=model.json.bufferViews[a.bufferView];
 const components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16}[a.type], widths={5121:1,5123:2,5125:4,5126:4},width=widths[a.componentType];
 const v=new DataView(model.binary.buffer,model.binary.byteOffset,model.binary.byteLength),offset=(b.byteOffset||0)+(a.byteOffset||0),stride=b.byteStride||components*width;
 const getter={5121:'getUint8',5123:'getUint16',5125:'getUint32',5126:'getFloat32'}[a.componentType];
 return Array.from({length:a.count},(_,i)=>Array.from({length:components},(_,c)=>v[getter](offset+i*stride+c*width,true)));
}
const provenance=JSON.parse(new TextDecoder().decode(read('static/primp/avatars/PROVENANCE.json')));
for(const record of provenance.records) test(`${record.name} derivative preserves source, triangle attributes and rig with unique paint UVs`,()=>{
 const original=read(`assets/avatar/${record.name}.glb`),derived=read(`static/primp/avatars/${record.name}.glb`);
 for(const [bytes,hash] of [[original,record.source_sha256],[derived,record.derived_sha256]]) assert.equal(createHash('sha256').update(bytes).digest('hex'),hash);
 validateGLB(derived.buffer.slice(derived.byteOffset,derived.byteOffset+derived.byteLength));
 const source=unpack(original),prepared=unpack(derived),a=source.json.meshes[0].primitives[0],b=prepared.json.meshes[0].primitives[0];
 for(const key of ['nodes','skins','animations','scenes']) assert.deepEqual(prepared.json[key],source.json[key]);
 const originalMaterial=source.json.materials[a.material],material=structuredClone(prepared.json.materials[b.material]);delete material.pbrMetallicRoughness.baseColorTexture;assert.deepEqual(material,originalMaterial);
 assert.equal(b.attributes.COLOR_0,undefined);
 const before=data(source,a.indices).flat(),after=data(prepared,b.indices).flat();assert.equal(before.length,after.length);
 for(const semantic of ['POSITION','NORMAL','JOINTS_0','WEIGHTS_0']) {
  const x=data(source,a.attributes[semantic]),y=data(prepared,b.attributes[semantic]);
  for(let i=0;i<before.length;i++) assert.deepEqual(y[after[i]],x[before[i]],`${semantic} triangle corner ${i}`);
 }
 const position=data(prepared,b.attributes.POSITION),uv=data(prepared,b.attributes.TEXCOORD_0),triangles=[];
 for(let i=0;i<after.length;i+=3) triangles.push({mesh:0,positions:after.slice(i,i+3).map(j=>position[j]),uv:after.slice(i,i+3).map(j=>uv[j])});
 const atlas=buildIslandAtlas(triangles,2048);assert.equal(atlas.blocked.size,0);assert.ok(atlas.chartCount>0);
 let degenerate=0;
 for(let i=0;i<triangles.length;i++) if(!atlas.validFaces[i]) {
  const [p,q,r]=triangles[i].positions,u=q.map((v,j)=>v-p[j]),v=r.map((x,j)=>x-p[j]);
  assert.ok(Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])<1e-16,'Visible triangle lost paint UVs');degenerate++;
 }
 assert.equal(degenerate,34,'Legacy degenerate pole triangles changed');
});
