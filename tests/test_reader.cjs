// Simulated speech events verify control logic; they do not prove audible output.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const context={window:{},setTimeout,clearTimeout};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reader.js'),'utf8'),context);
const Reader=context.window.ReachReadAloud;
class Utterance{constructor(text){this.text=text;}}
function voice(){
  return {calls:[],current:null,canceled:0,getVoices:()=>[{name:'Test voice',voiceURI:'test-local',lang:'en-US',localService:true}],
    resume(){},cancel(){this.canceled++;const old=this.current;this.current=null;if(old)old.onerror?.({error:'canceled'});},
    speak(u){this.calls.push(u);this.current=u;u.onstart?.();}};
}
const flush=async()=>{await Promise.resolve();await Promise.resolve();};
(async()=>{
  let text='One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen.\n\nSecond paragraph has its own words.\n\nLast paragraph.';
  let key='manuscript-a';const synth=voice(),reader=new Reader({getText:()=>text,getKey:()=>key,synth,Utterance});
  const original=text;reader.play({fromStart:true});assert.equal(reader.phase,'reading');assert.equal(synth.calls.length,1);assert(synth.current.text.startsWith('One two three'));
  const utterance=synth.current;utterance.onboundary({charIndex:utterance.text.indexOf('four')});reader.pause();assert.equal(reader.phase,'paused');
  const count=synth.calls.length;utterance.onend();assert.equal(synth.calls.length,count);reader.play();assert(synth.current.text.startsWith('four five'));
  reader.paragraph(1);assert.equal(synth.current.text,'Second paragraph has its own words.');reader.paragraph(-1);assert(synth.current.text.startsWith('One two'));
  reader.words(10);assert(synth.current.text.startsWith('eleven twelve'));reader.words(-10);assert(synth.current.text.startsWith('One two'));
  reader.configure({rate:1.5,volume:0.5,voiceURI:'test-local'});assert.equal(synth.current.rate,1.5);assert.equal(synth.current.volume,0.5);assert.equal(synth.current.voice.voiceURI,'test-local');
  const stale=synth.current;reader.stop();assert.equal(reader.phase,'idle');assert.equal(reader.offset,0);const stopped=synth.calls.length;stale.onend();await flush();assert.equal(synth.calls.length,stopped);
  assert.equal(text,original);
  console.log('PASS: read/pause/resume/stop, paragraph and 10-word navigation, rate/volume/voice, stale-event cancellation and text preservation');

  text='First paragraph.\n\nSecond paragraph.';reader.play({fromStart:true});synth.current.onend();await flush();assert.equal(synth.current.text,'Second paragraph.');synth.current.onend();await flush();assert.equal(reader.phase,'ended');
  reader.play();assert.equal(synth.current.text,'First paragraph.');synth.current.onerror({error:'not-allowed'});assert.equal(reader.phase,'error');assert.match(reader.message,/blocked audio/);
  const callsAfterError=synth.calls.length;await flush();assert.equal(synth.calls.length,callsAfterError);
  reader.play();text='Edited words';reader.checkForChanges();assert.equal(reader.phase,'idle');assert.match(reader.message,/Text changed/);reader.play();assert.equal(synth.current.text,'Edited words');
  key='different-document';reader.checkForChanges();assert.equal(reader.phase,'idle');assert.equal(reader.index,0);
  reader.stop();
  console.log('PASS: automatic paragraph progression and ending, speech failures, edits and document switches stop safely');

  text=Array.from({length:160},(_,i)=>'word'+i).join(' ');const before=synth.calls.length;reader.play({fromStart:true});
  while(reader.active){const current=synth.current;assert(current.text.length<=220);current.onend();await flush();}
  assert.equal(synth.calls.slice(before).map(u=>u.text).join(''),text);assert.equal(reader.phase,'ended');
  reader.play();const noBoundary=synth.current.text;reader.pause();reader.play();assert.equal(synth.current.text,noBoundary);reader.stop();
  const unsupported=new Reader({getText:()=>text,getKey:()=>key,synth:null,Utterance:null});unsupported.play();assert.equal(unsupported.phase,'error');assert.match(unsupported.message,/unavailable/);unsupported.stop();
  const silent=voice();silent.speak=function(u){this.calls.push(u);this.current=u;};
  const silentReader=new Reader({getText:()=>text,getKey:()=>key,synth:silent,Utterance,startTimeout:5});silentReader.play();await new Promise(resolve=>setTimeout(resolve,15));assert.equal(silentReader.phase,'error');assert.match(silentReader.message,/No audio start/);silentReader.stop();
  console.log('PASS: long-text chunks retain every word; absent boundaries replay only the current chunk; unsupported or silent speech reports failure');
})().catch(error=>{console.error(error);process.exit(1);});
