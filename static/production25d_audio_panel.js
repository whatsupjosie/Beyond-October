(function(){'use strict';
const $=id=>document.getElementById(id),mixer=window.PubcastProgramAudio,rows=new Map();
const desk=window.PubCastAudioDesk=new PubCastParticipantAudio({mixer,onState:message=>{$('participantAudioStatus').textContent=message;}});
function controls(){ $('audioOpen').disabled=!desk.closed;$('audioClose').disabled=desk.closed;if(desk.closed)$('audioInvite').value='';}
$('audioOpen').onclick=async()=>{
 $('audioOpen').disabled=true;
 try{
  if(!window.PubCast25DStudio?.state().session)throw Error('Start a production before opening its audio desk');
  const room=await desk.open();$('audioInvite').value=new URL('./participant_audio.html?room='+room,location.href).href;
 }catch(e){$('participantAudioStatus').textContent=e.message;}finally{controls();}
};
$('audioClose').onclick=async()=>{await desk.close();controls();$('participantAudioStatus').textContent='Audio desk closed. Participant microphones disconnected.';};
function row(input){
 const node=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=input.label;node.appendChild(legend);
 const meter=document.createElement('meter');meter.min=0;meter.max=1;meter.setAttribute('aria-label',input.label+' audio level');node.appendChild(meter);
 const mute=document.createElement('button'),solo=document.createElement('button');mute.type=solo.type='button';
 mute.onclick=()=>mixer.configureInput(input.id,{muted:!input.muted});solo.onclick=()=>mixer.configureInput(input.id,{solo:!input.solo});node.append(mute,solo);
 const sliders={};
 const slider=(label,min,max,value,change)=>{
  const wrap=document.createElement('label');wrap.style.display='block';wrap.textContent=label;
  const range=document.createElement('input');range.type='range';Object.assign(range,{min,max,value});range.setAttribute('aria-label',input.label+' '+label);range.oninput=()=>change(Number(range.value));wrap.appendChild(range);node.appendChild(wrap);return range;
 };
 sliders.volume=slider('Level',0,200,input.volume*100,value=>mixer.configureInput(input.id,{volume:value/100}));
 const eq=['Low EQ (dB)','Mid EQ (dB)','High EQ (dB)'].map((label,i)=>slider(label,-12,12,0,value=>{const eq=input.eq.slice();eq[i]=value;mixer.configureInput(input.id,{eq});}));
 $('audioInputs').appendChild(node);return {node,meter,mute,solo,sliders,eq,data:new Float32Array(input.analyser.fftSize),input};
}
const unsubscribe=mixer.onInput((type,input)=>{
 if(type==='removed'){rows.get(input.id)?.node.remove();rows.delete(input.id);return;}
 const item=rows.get(input.id)||row(input);rows.set(input.id,item);
 item.mute.textContent=input.muted?'UNMUTE':'MUTE';item.mute.setAttribute('aria-pressed',String(input.muted));
 item.solo.textContent=input.solo?'CLEAR SOLO':'SOLO';item.solo.setAttribute('aria-pressed',String(input.solo));
 item.sliders.volume.value=input.volume*100;item.eq.forEach((e,i)=>e.value=input.eq[i]);
});
const timer=setInterval(()=>{controls();for(const item of rows.values()){
 item.input.analyser.getFloatTimeDomainData(item.data);item.meter.value=Math.sqrt(item.data.reduce((n,x)=>n+x*x,0)/item.data.length);
}},200);
window.addEventListener('pagehide',()=>{clearInterval(timer);unsubscribe();desk.close().catch(()=>{});});
})();
