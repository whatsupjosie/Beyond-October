const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function receiver() {
 const messages=[];
 const context=vm.createContext({sampleRate:48000,currentFrame:0,Int16Array,
  AudioWorkletProcessor:class {constructor(){this.port={postMessage:value=>messages.push(value)};}},
  registerProcessor:(_,value)=>context.Processor=value});
 vm.runInContext(fs.readFileSync('static/participant_pcm_worklet.js','utf8'),context);
 const node=new context.Processor({processorOptions:{rate:48000}});
 return {node,messages,send(samples){node.port.onmessage({data:samples.buffer});},
  render(){const output=new Float32Array(128);node.process([],[[output]]);context.currentFrame+=128;return output;}};
}

test('diagnostics preserve exact FIFO samples and identify drained audio clock',()=>{
 const r=receiver(),samples=Int16Array.from({length:24576},(_,i)=>(i%65535)-32768);
 r.send(samples);
 const actual=[];
 for(let i=0;i<192;i++)actual.push(...r.render());
 assert.deepEqual(actual,Array.from(samples,s=>s/32768));
 assert.equal(r.messages.length,0);
 assert.ok(r.render().every(s=>s===0));
 assert.equal(r.messages.length,1);
 const {fault,diagnostic:d}=r.messages[0];
 assert.equal(fault,'underflow');assert.equal(d.queuedFrames,0);
 assert.equal(d.receivedFrames,24576);assert.equal(d.renderedFrames,24576);
 assert.equal(d.currentFrame,24576);assert.equal(d.lastReceiveFrame,0);
 assert.equal(d.startFrame,0);assert.equal(d.capacityFrames,72000);
 r.render();r.send(new Int16Array(4096));assert.equal(r.messages.length,1);
});

test('overflow reports rejected packet without consuming or replacing queued samples',()=>{
 const r=receiver();r.send(new Int16Array(70000));r.send(new Int16Array(4096));
 const {fault,diagnostic:d}=r.messages[0];
 assert.equal(fault,'overflow');assert.equal(d.queuedFrames,70000);
 assert.equal(d.incomingFrames,4096);assert.equal(d.receivedFrames,74096);
 assert.equal(d.renderedFrames,0);assert.ok(r.render().every(s=>s===0));
});

test('queue history is bounded over a long continuously fed receiver',()=>{
 const r=receiver();r.send(new Int16Array(24576));
 for(let i=0;i<48000*70/128;i++){
  r.render();r.send(new Int16Array(128));
 }
 r.send(new Int16Array(72000));
 const d=r.messages[0].diagnostic;
 assert.equal(d.queueHistory.length,12);
 assert.ok(d.queueHistory[0].frame>=48000*10);
 assert.equal(d.maxReceiveGapFrames,128);
 assert.ok(d.queueHistory.every(s=>s.queuedFrames===24576));
});

test('host keeps the fault through cleanup but clears it before opening a new desk',async()=>{
 const context=vm.createContext({window:{addEventListener(){}},console:{warn(){}},Date,DOMException});
 vm.runInContext(fs.readFileSync('static/participant_audio.js','utf8'),context);
 const desk=new context.window.PubCastParticipantAudio({mixer:{allowed:()=>true,inputSessionStops:new Set(),ensureContext(){throw Error('deliberate open failure');}}});
 desk.host=true;desk.closed=false;
 desk.receive({type:'fault',peer:'test',message:'underflow',diagnostic:{reason:'underflow'}});
 desk.receive({type:'left',peer:'test'});
 await desk.close();assert.equal(desk.lastFault.diagnostic.reason,'underflow');
 await assert.rejects(desk.open(),/deliberate open failure/);
 assert.equal(desk.lastFault,null);
});
