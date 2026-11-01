/* Native browser interfaces are doubles here; this is not browser certification. */
const assert=require('assert'),fs=require('fs'),vm=require('vm');
let Worklet;
const packets=[];
class Processor {constructor(){this.port={postMessage:data=>packets.push(data)};}}
vm.runInNewContext(fs.readFileSync('static/blackbox_pcm_worklet.js','utf8'),{
 AudioWorkletProcessor:Processor,registerProcessor:(_,ctor)=>Worklet=ctor,Int16Array,Math
});
const worklet=new Worklet();worklet.process([[new Float32Array(4200).fill(.5)]]);
assert.equal(packets[0].byteLength,8192);
worklet.port.onmessage({data:'flush'});
assert.equal(packets[1].byteLength,208);assert.equal(packets[2],'flushed');
assert.equal(new Int16Array(packets[0])[0],16384);

const source=fs.readFileSync('static/stage.html','utf8');
const start=source.indexOf('// DOM stages need actual tab capture;');
const end=source.indexOf('// â•',start);
assert(start>0&&end>start);
function environment(valid=true,withAudio=true){
 const elements={};let stopped=0,downloads=0;
 const video={getSettings:()=>({displaySurface:'browser'}),
   getCaptureHandle:()=>valid?({origin:'http://localhost',handle:'pubcast-stage'}):null,
   stop:()=>stopped++};
 const stream={getVideoTracks:()=>[video],getAudioTracks:()=>withAudio?[{}]:[],getTracks:()=>[video]};
 class Recorder{
  static isTypeSupported(){return true;}
  constructor(){this.state='inactive';}
  start(){this.state='recording';}
  stop(){this.state='inactive';this.ondataavailable({data:new Blob(['actual-test-video'])});this.onstop();}
 }
 const window={MediaRecorder:Recorder};
 const context={window,MediaRecorder:Recorder,Blob,Date,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}},
   setTimeout:()=>{},location:{origin:'http://localhost'},
   document:{getElementById:id=>elements[id]||(elements[id]={classList:{toggle(){}},textContent:''}),
     createElement:()=>({click:()=>downloads++})},
   navigator:{mediaDevices:{getDisplayMedia:async()=>stream,setCaptureHandleConfig(){}}}};
 vm.runInNewContext(source.slice(start,end),context);
 return {window,elements,stopped:()=>stopped,downloads:()=>downloads};
}
(async()=>{
 const denied=environment(false);await denied.window.toggleRecord();
 assert.match(denied.elements.recText.textContent,/could not verify/);
 assert.equal(denied.downloads(),0);assert(denied.stopped());
 const audio=environment(true,true);await audio.window.toggleRecord();
 assert.equal(audio.elements.recText.textContent,'RECORDING VIDEO + TAB AUDIO');
 await audio.window.toggleRecord();assert.equal(audio.downloads(),1);assert(audio.stopped());
 const silent=environment(true,false);await silent.window.toggleRecord();
 assert.equal(silent.elements.recText.textContent,'RECORDING VIDEO ONLY');await silent.window.toggleRecord();
 console.log('PASS: PCM packets and final tail; tab verification; truthful video/audio labels; track cleanup');
})().catch(error=>{console.error(error);process.exitCode=1;});
