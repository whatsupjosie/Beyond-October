/* Protect the participant's UI before spending their volunteered render budget. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastCameraPoolGuard=api;})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
const p95=values=>{const s=values.slice().sort((a,b)=>a-b);return s.length?s[Math.ceil(s.length*.95)-1]:null;};
class Guard{
 constructor(){this.baseline=[];this.recent=[];this.base=null;this.scale=1;this.pauseUntil=0;this.lastCheck=0;this.bad=0;this.goodSince=0;this.held=false;this.baselineBlocked=false;this.reason="Measuring UI baseline before starting donated work";}
 sample(ms,now){
  if(!Number.isFinite(ms)||ms<=0)return;
  if(this.base===null){this.baseline.push(ms);if(this.baseline.length>=45){this.base=p95(this.baseline);this.baselineBlocked=this.base>75;this.recent=[];this.reason=this.baselineBlocked?"Existing UI is too slow; no camera work admitted":"Baseline established";}return;}
  this.recent.push(ms);if(this.recent.length>60)this.recent.shift();
  if(this.held)return;
  if(this.baselineBlocked){if(this.recent.length>=45&&p95(this.recent)<=50){this.baselineBlocked=false;this.base=p95(this.recent);this.reason="UI recovered; capacity may be offered";}return;}
  if(ms>180)this.pause(now,"UI delay detected; donated work paused");
  if(now-this.lastCheck<1000)return;this.lastCheck=now;
  const slow=p95(this.recent)>Math.max(50,this.base*1.8);
  if(slow){this.bad++;this.goodSince=0;if(this.bad>=2){this.scale=Math.max(.25,this.scale*.5);this.reason="UI frame delays: reducing donated work";this.bad=0;}}
  else{this.bad=0;if(!this.goodSince)this.goodSince=now;if(now-this.goodSince>10000&&now>this.pauseUntil){this.scale=Math.min(1,this.scale+.25);this.goodSince=now;this.reason=this.scale===1?"UI stable":"UI recovering; cautiously restoring capacity";}}
 }
 pause(now,reason){this.pauseUntil=Math.max(this.pauseUntil,now+4000);this.scale=Math.max(.25,this.scale*.5);this.goodSince=0;this.reason=reason;}
 report(now,hidden=false,allowQuality=false){
  if(allowQuality&&this.scale<=.5)this.qualityLimited=true;
  const state=this.base===null?"calibrating":this.held||this.baselineBlocked||hidden||now<this.pauseUntil?"paused":this.scale<1||allowQuality&&this.qualityLimited?"reduced":"running";
  return {state,baseline_p95_ms:this.base,frame_p95_ms:p95(this.recent),work_scale:state==="paused"||state==="calibrating"?0:this.scale,
   preview_width:allowQuality&&this.qualityLimited?320:640,reason:hidden?"Page hidden; donated work paused":this.reason};
 }
}
class UploadBudget{
 constructor(){this.sent=[];}
 reserve(bytes,kbps,now){
  this.sent=this.sent.filter(([at])=>now-at<1000);
  if(!Number.isFinite(bytes)||bytes<=0||!Number.isFinite(kbps)||kbps<=0)return false;
  const capacity=kbps*1000/8;
  if(bytes+this.sent.reduce((sum,[,size])=>sum+size,0)>capacity)return false;
  this.sent.push([now,bytes]);return true;
 }
}
return {Guard,UploadBudget};
});
