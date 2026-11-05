const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

test('audio-clock reference preserves exact fifteen-second samples while main thread is absent', () => {
  const marks = [];
  const scope = vm.createContext({sampleRate:48000, currentFrame:0, Math, Number,
    AudioWorkletProcessor:class {constructor(){this.port={postMessage:mark=>marks.push(mark)};}},
    registerProcessor:(name, Type)=>{scope.Type=Type;}
  });
  vm.runInContext(fs.readFileSync('static/production25d_clacker_worklet.js','utf8'), scope);
  const processor = new scope.Type({processorOptions:{originFrame:48000}});
  let betweenPower=0, pulsePower=0;
  for(let frame=0;frame<32*48000;frame+=128){
    scope.currentFrame=frame;
    const samples=new Float32Array(128);
    assert.equal(processor.process([],[[samples]]),true);
    for(let i=0;i<samples.length;i++){
      const elapsed=frame+i-48000, phase=elapsed%(15*48000);
      if(elapsed<0||phase>=2400)betweenPower+=samples[i]*samples[i];
      else pulsePower+=samples[i]*samples[i];
    }
  }
  assert.deepEqual(marks.map(m=>[m.sequence,m.frame]),[[1,768000],[2,1488000]]);
  assert.equal(betweenPower,0);
  assert.ok(pulsePower>100);
  processor.port.onmessage({data:'stop'});
  assert.equal(processor.process([],[[new Float32Array(128)]]),false);
  assert.throws(()=>new scope.Type({processorOptions:{originFrame:NaN}}),/Invalid clacker origin/);
});
