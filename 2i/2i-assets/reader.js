/* Read existing text only. This controller never generates or edits prose.
 * Speech events vary by device. Resume uses the last reported boundary, or
 * replays the current short chunk when a voice supplies no boundary events.
 */
'use strict';
window.ReachReadAloud=class ReachReadAloud {
  constructor({getText,getKey,onChange=()=>{},beforePlay=()=>{},synth=window.speechSynthesis,Utterance=window.SpeechSynthesisUtterance,startTimeout=8000}) {
    Object.assign(this,{getText,getKey,onChange,beforePlay,synth,Utterance,startTimeout});
    this.source='manuscript';this.phase='idle';this.message='Ready to read';this.rate=1;this.volume=1;this.voiceURI='';
    this.paragraphs=[];this.index=0;this.offset=0;this.text=null;this.key=null;this.token=0;this.utterance=null;this.timer=null;
  }
  get supported(){return !!(this.synth&&this.Utterance&&typeof this.synth.speak==='function');}
  get active(){return this.phase==='reading'||this.phase==='starting';}
  get state(){return {source:this.source,phase:this.phase,message:this.message,index:this.index,offset:this.offset,total:this.paragraphs.length,text:this.paragraphs[this.index]?.text||'',rate:this.rate,volume:this.volume,supported:this.supported};}
  notify(){this.onChange(this.state);}
  cancel(){
    this.token++;clearTimeout(this.timer);this.timer=null;this.utterance=null;
    try{this.synth?.cancel();}catch(_){}
  }
  sync(){
    const key=String(this.getKey(this.source)),text=String(this.getText(this.source)||'');
    if(key===this.key&&text===this.text)return false;
    const hadText=this.text!==null,wasActive=this.active||this.phase==='paused';
    this.cancel();this.key=key;this.text=text;this.index=0;this.offset=0;this.phase='idle';this.paragraphs=[];
    for(const match of text.matchAll(/[^\r\n]+/g)){
      const value=match[0].trim();if(!value)continue;
      this.paragraphs.push({text:value,start:match.index+match[0].indexOf(value)});
    }
    this.message=!this.paragraphs.length?'No text to read':hadText&&wasActive?'Text changed · press Play to read the updated text':'Ready to read';
    this.notify();return true;
  }
  checkForChanges(){if(this.text!==null)this.sync();}
  setSource(source){if(!['manuscript','draft','partner'].includes(source))return;this.source=source;this.key=null;this.sync();}
  fail(message){this.cancel();this.phase='error';this.message=message;this.notify();}
  finish(){this.cancel();this.phase='ended';this.index=Math.max(0,this.paragraphs.length-1);this.offset=this.paragraphs[this.index]?.text.length||0;this.message='Reading finished';this.notify();}
  play({fromStart=false,position=null}={}){
    this.sync();
    if(!this.paragraphs.length){this.message='Write or choose some text first';this.notify();return;}
    if(!this.supported){this.fail('Read-aloud is unavailable in this view. Try the standalone phone file in a browser with speech support.');return;}
    if(fromStart||this.phase==='ended'){this.index=0;this.offset=0;}
    if(Number.isFinite(position)){
      const index=this.paragraphs.findLastIndex(p=>p.start<=position);this.index=Math.max(0,index);
      this.offset=Math.max(0,Math.min(position-this.paragraphs[this.index].start,this.paragraphs[this.index].text.length));
    }
    this.beforePlay();this.speakCurrent();
  }
  speakCurrent(){
    this.cancel();
    while(this.index<this.paragraphs.length&&this.offset>=this.paragraphs[this.index].text.length){this.index++;this.offset=0;}
    if(this.index>=this.paragraphs.length){this.finish();return;}
    const paragraph=this.paragraphs[this.index],start=this.offset;
    let end=Math.min(paragraph.text.length,start+220);
    if(end<paragraph.text.length){const space=paragraph.text.lastIndexOf(' ',end-1);if(space>start+30)end=space+1;}
    const text=paragraph.text.slice(start,end),token=this.token;
    let utterance;
    try{utterance=new this.Utterance(text);}catch(_){this.fail('This view could not create a speech request.');return;}
    this.utterance=utterance;utterance.rate=this.rate;utterance.volume=this.volume;
    let voices=[];try{voices=this.synth.getVoices();}catch(_){}
    const voice=voices.find(v=>v.voiceURI===this.voiceURI);if(voice){utterance.voice=voice;utterance.lang=voice.lang;}
    const live=()=>token===this.token;
    const speaking=()=>{
      if(!live())return;clearTimeout(this.timer);this.phase='reading';this.message=this.volume===0?'Reading · volume is muted':'Reading aloud';
      this.timer=setTimeout(()=>{if(live())this.fail('The voice stopped responding. Press Play to retry from the current position.');},Math.max(20000,text.split(/\s+/).length*1200/this.rate+15000));
      this.notify();
    };
    utterance.onstart=speaking;
    utterance.onboundary=event=>{
      if(!live())return;
      if(this.phase==='starting')speaking();
      if(Number.isFinite(event.charIndex))this.offset=start+Math.max(0,Math.min(event.charIndex,text.length));
      this.notify();
    };
    utterance.onend=()=>{
      if(!live())return;clearTimeout(this.timer);this.offset=end;
      if(end>=paragraph.text.length){this.index++;this.offset=0;}
      if(this.index>=this.paragraphs.length){this.finish();return;}
      Promise.resolve().then(()=>{if(live())this.speakCurrent();});
    };
    utterance.onerror=event=>{
      if(!live())return;
      const errors={
        'not-allowed':'This chat or browser blocked audio. Try Read again, or open the standalone phone file in a browser.',
        'audio-busy':'Your audio output is busy. Stop other audio, then press Play.',
        'audio-hardware':'Your phone could not use its audio output.',
        'voice-unavailable':'That voice is unavailable. Choose another voice.',
        'language-unavailable':'No voice is available for that language.',
        'synthesis-unavailable':'No speech engine is available on this device.',
        'network':'The selected voice could not connect. Try an on-device voice.',
        'interrupted':'Reading was interrupted. Press Play to continue.',
        'canceled':'Reading was canceled. Press Play to continue.'
      };
      this.fail(errors[event.error]||'The voice could not read this passage. Choose another voice or press Play to retry.');
    };
    this.phase='starting';this.message='Starting voice…';this.notify();
    this.timer=setTimeout(()=>{if(live())this.fail('No audio start was reported. This view may block speech; try the standalone phone file.');},this.startTimeout);
    try{this.synth.resume?.();this.synth.speak(utterance);}catch(error){this.fail('Audio could not start: '+(error.message||'speech unavailable'));}
  }
  pause(){if(!this.active)return;this.cancel();this.phase='paused';this.message='Paused · Play resumes near the last spoken word';this.notify();}
  toggle(){if(this.active)this.pause();else this.play();}
  stop(){this.cancel();this.phase='idle';this.index=0;this.offset=0;this.message='Stopped · ready from the beginning';this.notify();}
  paragraph(delta){
    this.sync();if(!this.paragraphs.length)return;
    const run=this.active;this.cancel();this.index=Math.max(0,Math.min(this.paragraphs.length-1,this.index+delta));this.offset=0;
    this.phase='paused';this.message='Paragraph selected · press Play';if(run)this.speakCurrent();else this.notify();
  }
  words(delta){
    this.sync();if(!this.paragraphs.length)return;
    const run=this.active,words=[];
    this.paragraphs.forEach((p,index)=>{for(const word of p.text.matchAll(/\S+/g))words.push({index,offset:word.index});});
    let current=words.findLastIndex(w=>w.index<this.index||(w.index===this.index&&w.offset<=this.offset));
    const target=Math.max(0,Math.min(words.length-1,Math.max(0,current)+delta));
    this.cancel();Object.assign(this,words[target]);this.phase='paused';this.message='Reading position moved · press Play';if(run)this.speakCurrent();else this.notify();
  }
  configure({rate=this.rate,volume=this.volume,voiceURI=this.voiceURI}={}){
    if(!Number.isFinite(rate)||rate<0.5||rate>2.5||!Number.isFinite(volume)||volume<0||volume>1)return;
    const run=this.active;this.rate=rate;this.volume=volume;this.voiceURI=String(voiceURI);
    if(run)this.speakCurrent();else this.notify();
  }
};
