import test from 'node:test';
import assert from 'node:assert/strict';
import {buildIslandAtlas, retainIsland} from '../../static/primp/uv-islands.mjs';
const triangle=(uv,positions=[[0,0,0],[1,0,0],[0,1,0]],mesh='a')=>({uv,positions,mesh});
test('edge-connected triangles share one island without false diagonal overlap',()=>{
 const atlas=buildIslandAtlas([triangle([[0,0],[1,0],[0,1]]),triangle([[1,0],[1,1],[0,1]],[[1,0,0],[1,1,0],[0,1,0]])],1024);
 assert.equal(atlas.chartCount,1);assert.equal(atlas.blocked.size,0);assert.equal(atlas.coverage[1],1024*1024);
});
test('nearby islands are separate and exact UV overlaps are explicitly blocked',()=>{
 const atlas=buildIslandAtlas([triangle([[0,0],[.4,0],[0,.4]]),triangle([[.42,0],[.82,0],[.42,.4]],[[2,0,0],[3,0,0],[2,1,0]])],1024);
 assert.equal(atlas.chartCount,2);assert.equal(atlas.blocked.size,0);
 const overlap=buildIslandAtlas([triangle([[0,0],[.4,0],[0,.4]]),triangle([[0,0],[.4,0],[0,.4]],[[2,0,0],[3,0,0],[2,1,0]])],1024);
 assert.equal(overlap.blocked.size,2);
});
test('color and blur inputs cannot contaminate an unrelated island',()=>{
 const atlas={size:2,mask:new Int32Array([1,2,0,1])};
 const before={width:2,height:2,data:new Uint8ClampedArray(16).fill(30)},after={width:2,height:2,data:new Uint8ClampedArray(16).fill(240)};
 retainIsland(after,before,atlas,1,0,0);assert.equal(after.data[0],240);assert.equal(after.data[4],30);assert.equal(after.data[8],30);
 retainIsland(after,null,atlas,1,0,0);assert.equal(after.data[4],0);assert.equal(after.data[8],0);
});
test('out-of-range and degenerate UVs cannot silently become paint targets',()=>{
 const atlas=buildIslandAtlas([triangle([[0,0],[2,0],[0,1]]),triangle([[0,0],[0,0],[0,0]])],1024);assert.equal([...atlas.validFaces].filter(x=>!x).length,2);
});
