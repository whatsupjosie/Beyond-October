const assert = require('assert');
class Node {
  constructor() {this.gain={value:1};this.pan={value:0};}
  connect() {} disconnect() {}
}
class Context {
  constructor() {this.destination={};this.state='running';}
  createGain() {return new Node();}
  createMediaElementSource() {return new Node();}
  async resume() {}
}
class Media {
  constructor(url) {this.url=url;this.listeners={};}
  async play() {if(this.url==='fail')throw new Error('autoplay blocked');}
  pause() {} addEventListener(type,fn) {this.listeners[type]=fn;}
}
global.AudioContext=Context;global.Audio=Media;
const {ProgramAudioRuntime}=require('../static/program_audio_runtime.js');
(async()=>{
 const runtime=new ProgramAudioRuntime();
 await assert.rejects(runtime.playUrl('fail',{bus:'dialogue'}));
 assert.equal(runtime.active.size,0);assert.equal(runtime.dialogueActive,0);
 await runtime.playUrl('voice',{bus:'dialogue'});
 assert.equal(runtime.dialogueActive,1);
 runtime.setRoom('dressing');assert.equal(runtime.active.size,0);
 await assert.rejects(runtime.playUrl('music',{bus:'music'}));
 assert.equal(runtime.playUISound(),null);
 const announcement=await runtime.consume({action:'play',room:'dressing',url:'call',bus:'dialogue',authorized_director:true});
 assert(announcement.audio);runtime.stopAll();
 assert.deepEqual(await runtime.consume({action:'play',room:'studio',url:'private'}),{skipped:true});
 assert.deepEqual(await runtime.consume({action:'play',url:'ordinary'}),{blocked:true});
 console.log('PASS: room policy, director exception, rejected playback cleanup, interruption');
})().catch(e=>{console.error(e);process.exitCode=1;});
