// Local-only phone desk. No model calls, server, credentials or external assets.
document.documentElement.dataset.reachArtwork='original';
window.REACH_PHONE_STANDALONE=true;
function phoneLocalStorage(kind) {
  const prefix='reach-phone-standalone-v1:', memory=new Map();
  let backing=null;
  try {backing=window[kind];backing.setItem(prefix+'probe','1');backing.removeItem(prefix+'probe');}catch(_){backing=null;}
  const keys=()=>backing?Array.from({length:backing.length},(_,i)=>backing.key(i)).filter(k=>k?.startsWith(prefix)).map(k=>k.slice(prefix.length)):[...memory.keys()];
  return {
    get persistent(){return !!backing;}, get length(){return keys().length;}, key(i){return keys()[i]??null;},
    getItem(k){return backing?backing.getItem(prefix+k):(memory.get(k)??null);},
    setItem(k,v){if(backing)backing.setItem(prefix+k,String(v));else memory.set(k,String(v));},
    removeItem(k){if(backing)backing.removeItem(prefix+k);else memory.delete(k);}
  };
}
const reachPhoneStore=phoneLocalStorage('localStorage');
const reachPhoneSession=phoneLocalStorage('sessionStorage');
async function offlineNoNetwork(){throw Error('Live Reach services are not connected in this phone edition.');}
