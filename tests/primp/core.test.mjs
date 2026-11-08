import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {History, strokePoints, validateGLB, validateProject, bytesToBase64, base64ToBytes, softenPixels, bounded, LIMITS} from '../../static/primp/core.mjs';
const bytes = new Uint8Array(readFileSync(new URL('../fixtures/avatars/mh_female.glb', import.meta.url)));
const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);

test('real rigged avatar passes GLB boundary and binary round trip', () => {
 const json = validateGLB(buffer); assert.ok(json.skins.length); assert.ok(json.animations.length);
 assert.deepEqual(base64ToBytes(bytesToBase64(bytes)),bytes);
});
test('corruption and unexpected remote resources are rejected before loading', () => {
 const damaged=buffer.slice(0); new DataView(damaged).setUint32(8, 4, true); assert.throws(()=>validateGLB(damaged));
 const json=JSON.stringify({asset:{version:'2.0'},buffers:[{uri:'https://unexpected.example/avatar.bin'}]});
 const len=Math.ceil(json.length/4)*4,b=new ArrayBuffer(20+len),v=new DataView(b);v.setUint32(0,0x46546c67,true);v.setUint32(4,2,true);v.setUint32(8,b.byteLength,true);v.setUint32(12,len,true);v.setUint32(16,0x4e4f534a,true);new Uint8Array(b,20).fill(32);new Uint8Array(b,20).set(new TextEncoder().encode(json));assert.throws(()=>validateGLB(b),/External/);
});
test('ten edits undo and redo exactly; branching discards redo and accounts memory', () => {
 const history=new History(1000,10);let value=0;
 for(let i=1;i<=12;i++){const before=value,after=i;value=i;history.push({bytes:10,undo:()=>value=before,redo:()=>value=after});}
 assert.equal(history.past.length,10);for(let i=0;i<10;i++)history.undo();assert.equal(value,2);for(let i=0;i<10;i++)history.redo();assert.equal(value,12);
 history.undo();history.push({bytes:20,undo(){},redo(){}});assert.equal(history.future.length,0);assert.equal(history.bytes,110);
});
test('memory cap evicts oldest edits; oversized edit never destroys history', () => {
 const h=new History(100);for(let i=0;i<3;i++)h.push({bytes:40,undo(){},redo(){}});assert.equal(h.bytes,80);assert.equal(h.past.length,2);assert.throws(()=>h.push({bytes:101}));assert.equal(h.bytes,80);
});
test('sparse pointer samples interpolate; large atlas jumps start a new segment', () => {
 assert.ok(strokePoints({x:0,y:0},{x:100,y:0},10).length>20);assert.equal(strokePoints({x:1,y:1},{x:1000,y:1000},10).length,1);
 assert.throws(()=>bounded(NaN,0,1));
});
test('premultiplied blending softens alpha without black fringes', () => {
 const image={width:5,height:5,data:new Uint8ClampedArray(100)};const i=(2*5+2)*4;image.data.set([230,50,80,255],i);softenPixels(image,2,2,3,1);
 assert.ok(image.data[i+3]<255);assert.equal(image.data[i],230);assert.ok(image.data[((2*5+1)*4)+3]>0);
});
test('project schema enforces format, memory bounds, unique targets, and layer types', () => {
 const project={format:'primp',version:1,name:'Look',source:bytesToBase64(bytes),targets:[]};assert.equal(validateProject(project),project);
 assert.throws(()=>validateProject({...project,version:2}));
 const t={id:0,layers:Array.from({length:6},()=>({visible:true,opacity:1,png:null}))};assert.doesNotThrow(()=>validateProject({...project,targets:[t]}));assert.throws(()=>validateProject({...project,targets:[t,t]}));
 t.layers[0].opacity=NaN;assert.throws(()=>validateProject({...project,targets:[t]}));
});

test('large embedded avatars avoid regex stack overflow and enforce the byte limit', () => {
 const large=new Uint8Array(5*1024*1024);large.fill(7);
 assert.deepEqual(base64ToBytes(bytesToBase64(large)),large);
 for(const invalid of ['AAA','A===','AA=A','AA==AAAA','AAAA\n','!!!!','===='])assert.throws(()=>base64ToBytes(invalid),/Invalid/);
 assert.equal(base64ToBytes('AA==').length,1);
 assert.equal(base64ToBytes('AAA=').length,2);
 assert.throws(()=>base64ToBytes('A'.repeat(Math.ceil(LIMITS.source/3)*4+4)),/Invalid/);
});
test('failed undo or redo never silently loses its history entry',()=>{
 const h=new History();let failUndo=true,failRedo=false;
 h.push({bytes:4,undo(){if(failUndo)throw Error('undo failure');},redo(){if(failRedo)throw Error('redo failure');}});
 assert.throws(()=>h.undo(),/undo failure/);assert.equal(h.past.length,1);assert.equal(h.future.length,0);
 failUndo=false;h.undo();failRedo=true;assert.throws(()=>h.redo(),/redo failure/);assert.equal(h.past.length,0);assert.equal(h.future.length,1);assert.equal(h.bytes,4);
});

test('null paint surface records fail with an explicit validation error',()=>{
 const value={format:'primp',version:1,name:'Look',source:bytesToBase64(bytes),targets:[null]};
 assert.throws(()=>validateProject(value),/Invalid paint surfaces/);
});
test('failed history notifications roll the pixels/state back before reporting failure',()=>{
 const h=new History();let value=1,undoFailure=true,redoFailure=false;
 h.push({bytes:4,undo(){value=0;if(undoFailure)throw Error('undo notification');},redo(){value=1;if(redoFailure)throw Error('redo notification');}});
 assert.throws(()=>h.undo(),/undo notification/);assert.equal(value,1);assert.equal(h.past.length,1);
 undoFailure=false;h.undo();redoFailure=true;assert.throws(()=>h.redo(),/redo notification/);assert.equal(value,0);assert.equal(h.future.length,1);
});
