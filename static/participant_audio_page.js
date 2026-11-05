(function(){'use strict';
const $=id=>document.getElementById(id),room=new URLSearchParams(location.search).get('room');
$('login').href='/login?next='+encodeURIComponent(location.pathname+location.search);
const audio=window.PubCastAudioContribution=new PubCastParticipantAudio({onState:(message,state)=>{
 $('status').textContent=message;$('connect').disabled=!state.closed;$('leave').disabled=state.closed;
}});
$('connect').onclick=async()=>{
 $('connect').disabled=true;$('leave').disabled=false;
 try{if(!room)throw Error('Ask the director for an audio invitation');await audio.join(room,{consent:$('consent').checked});}
 catch(e){$('status').textContent=e.message;}
 finally{$('connect').disabled=!audio.closed;$('leave').disabled=audio.closed;}
};
$('leave').onclick=async()=>{await audio.close();$('connect').disabled=false;$('leave').disabled=true;$('status').textContent='Disconnected. Your microphone is off.';};
window.addEventListener('pagehide',()=>audio.close().catch(()=>{}));
})();
