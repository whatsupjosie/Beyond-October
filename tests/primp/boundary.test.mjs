import test from 'node:test';
import assert from 'node:assert/strict';
import {validateGLB, TileEdit} from '../../static/primp/core.mjs';

export function glb(json, binary) {
 const text=new TextEncoder().encode(JSON.stringify({asset:{version:'2.0'},...json}));
 const jsonLength=Math.ceil(text.length/4)*4, binLength=binary?Math.ceil(binary.length/4)*4:0;
 const result=new ArrayBuffer(20+jsonLength+(binary?8+binLength:0)),view=new DataView(result);
 view.setUint32(0,0x46546c67,true);view.setUint32(4,2,true);view.setUint32(8,result.byteLength,true);
 view.setUint32(12,jsonLength,true);view.setUint32(16,0x4e4f534a,true);new Uint8Array(result,20,jsonLength).fill(32);new Uint8Array(result,20,text.length).set(text);
 if(binary){view.setUint32(20+jsonLength,binLength,true);view.setUint32(24+jsonLength,0x004e4942,true);new Uint8Array(result,28+jsonLength,binary.length).set(binary);}
 return result;
}
test('truncated binary chunks fail before the loader',()=>{
 const data=glb({buffers:[{byteLength:4}]},new Uint8Array(4)),view=new DataView(data),offset=20+view.getUint32(12,true);view.setUint32(offset,1024,true);
 assert.throws(()=>validateGLB(data),/chunk/i);
});
test('cyclic and excessively deep node graphs fail before the loader',()=>{
 assert.throws(()=>validateGLB(glb({nodes:[{children:[0]}]})),/node|cycle/i);
 const nodes=Array.from({length:300},(_,i)=>i<299?{children:[i+1]}:{});
 assert.throws(()=>validateGLB(glb({nodes})),/depth|node/i);
});
test('tiny files cannot request enormous decoded geometry allocations',()=>{
 assert.throws(()=>validateGLB(glb({accessors:[{componentType:5126,type:'VEC3',count:1000000000}]})),/accessor|memory/i);
});
test('oversized embedded images are rejected before native decoding',()=>{
 const png=new Uint8Array(33),v=new DataView(png.buffer);png.set([137,80,78,71,13,10,26,10]);v.setUint32(8,13);png.set([73,72,68,82],12);v.setUint32(16,16000);v.setUint32(20,16000);
 assert.throws(()=>validateGLB(glb({buffers:[{byteLength:png.length}],bufferViews:[{buffer:0,byteLength:png.length}],images:[{bufferView:0,mimeType:'image/png'}]},png)),/image|texture/i);
});
test('unchanged tile buffers are actually released, not merely excluded from the byte count',()=>{
 let painted=false;const context={canvas:{width:256,height:256},getImageData(x,y,w,h){const data=new Uint8ClampedArray(w*h*4);if(painted&&x===64&&y===64)data[0]=1;return {width:w,height:h,data};}};
 const edit=new TileEdit(context,()=>{});edit.capture(100,100,70);painted=true;const command=edit.finish();assert.equal(command.bytes,64*64*4*2);assert.equal(edit.tiles.size,1);
});

test('valid buffer padding and small implicit accessors remain supported',()=>{
 assert.doesNotThrow(()=>validateGLB(glb({buffers:[{byteLength:1}]},new Uint8Array(1))));
 assert.doesNotThrow(()=>validateGLB(glb({accessors:[{componentType:5126,type:'VEC3',count:3}]})));
});
test('buffer views, sparse allocations and asset versions are checked explicitly',()=>{
 assert.throws(()=>validateGLB(glb({buffers:[{byteLength:4}],bufferViews:[{buffer:0,byteOffset:3,byteLength:4}]},new Uint8Array(4))),/buffer view/i);
 assert.throws(()=>validateGLB(glb({accessors:[{componentType:5126,type:'VEC3',count:10,sparse:{count:11,indices:{componentType:5121,bufferView:0},values:{bufferView:0}}}]})),/sparse/i);
 assert.throws(()=>validateGLB(glb({asset:{version:'1.0'}})),/version/i);
});
test('sparse accessor index ordering and range are checked without decoding geometry',()=>{
 const binary=new Uint8Array(28);binary.set([1,0]);
 const json={buffers:[{byteLength:28}],bufferViews:[{buffer:0,byteLength:2},{buffer:0,byteOffset:4,byteLength:24}],accessors:[{componentType:5126,type:'VEC3',count:2,sparse:{count:2,indices:{componentType:5121,bufferView:0},values:{bufferView:1}}}]};
 assert.throws(()=>validateGLB(glb(json,binary)),/indices/);binary.set([0,2]);assert.throws(()=>validateGLB(glb(json,binary)),/indices/);binary.set([0,1]);assert.doesNotThrow(()=>validateGLB(glb(json,binary)));
});
test('legacy Manny and Sheila are diagnosed without rewriting their original bytes',async()=>{
 const {readFileSync}=await import('node:fs');
 for(const name of ['manny','sheila']){const bytes=readFileSync(new URL(`../../assets/avatar/${name}.glb`,import.meta.url));assert.throws(()=>validateGLB(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)),/buffer index/);}
});
