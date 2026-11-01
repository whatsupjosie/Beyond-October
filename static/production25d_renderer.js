/* PubCast 2.5D scene compositor. Original procedural development sets, separable layers,
 * real stage-world camera crops, foreground occlusion, and existing PubCastGLB actors.
 * The resulting canvas pixels are the input to actual program recording.
 */
(function (root, factory) {
  const api=factory();
  if (typeof module==="object" && module.exports) module.exports=api;
  else root.PubCast25DRenderer=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
const W=1280,H=720, TAU=Math.PI*2;
function rect(c,x,y,w,h,color){c.fillStyle=color;c.fillRect(x,y,w,h);}
function circle(c,x,y,r,color){c.fillStyle=color;c.beginPath();c.arc(x,y,r,0,TAU);c.fill();}
function text(c,s,x,y,size,color,align="center"){c.save();c.fillStyle=color;c.font="bold "+size+"px system-ui,sans-serif";c.textAlign=align;c.fillText(s,x,y);c.restore();}
function imageCover(ctx,img,dx,dy,dw,dh){
  if(!img||!img.complete||!img.naturalWidth)return false;
  const scale=Math.max(dw/img.naturalWidth,dh/img.naturalHeight);
  const sw=dw/scale,sh=dh/scale;
  ctx.drawImage(img,(img.naturalWidth-sw)/2,(img.naturalHeight-sh)/2,sw,sh,dx,dy,dw,dh);
  return true;
}
function drawBack(c,pkg,assets,shift){
 const [dark,mid,light]=pkg.theme;
 const g=c.createLinearGradient(0,0,W,H);g.addColorStop(0,dark);g.addColorStop(.67,mid);g.addColorStop(1,dark);
 c.fillStyle=g;c.fillRect(0,0,W,H);
 c.save();c.translate(shift*.17,0);
 if(!imageCover(c,assets.back,0,0,W,H)){
   rect(c,50,36,W-100,440,"#09101a55");
   for(let i=0;i<10;i++){rect(c,65+i*130,60,7,430,light+"44");}
   circle(c,640,280,330,light+"14");
   text(c,pkg.graphics,640,143,46,light);
   rect(c,115,178,1050,4,light+"88");
 }
 c.restore();
}
function drawMiddle(c,pkg,assets,shift){
 const [dark,mid,light]=pkg.theme;
 c.save();c.translate(shift*.48,0);
 if(!imageCover(c,assets.mid,0,0,W,H)){
  const floor=c.createLinearGradient(0,420,0,H);floor.addColorStop(0,dark);floor.addColorStop(1,"#090f1a");
  rect(c,0,452,W,268,floor);rect(c,0,455,W,4,light+"77");
  for(let i=0;i<7;i++){c.strokeStyle=light+"22";c.lineWidth=2;c.beginPath();c.moveTo(640,453);c.lineTo(i*240-80,720);c.stroke();}
  if(pkg.furnishings.includes("screen")){
    rect(c,900,199,255,175,"#080e18");rect(c,910,210,235,155,mid);
    text(c,"PRODUCTION",1027,290,24,"#f2f4f4");
  }
  if(pkg.furnishings.includes("curtain")){
    for(let i=0;i<12;i++) rect(c,i*111,80,62,365,mid+(i%2?"77":"44"));
  }
  if(pkg.furnishings.includes("scoreboard")){
    rect(c,445,180,390,170,"#0b1021");rect(c,456,191,368,148,mid);
    text(c,"SCOREBOARD",640,240,29,light);
  }
 }
 c.restore();
}
function drawFurniture(c,pkg,assets,shift){
 if(assets.front&&assets.front.complete&&assets.front.naturalWidth){
  c.save();c.translate(shift*.95,0);imageCover(c,assets.front,0,0,W,H);c.restore();return;
 }
 const [dark,mid,light]=pkg.theme;
 c.save();c.translate(shift*.82,0);
 if(pkg.furnishings.includes("desk")){
   rect(c,320,580,640,111,dark);rect(c,308,570,662,17,light);rect(c,370,603,540,8,mid);
 }
 if(pkg.furnishings.includes("panel")){
   rect(c,160,590,960,100,dark);rect(c,155,579,970,17,light);
 }
 if(pkg.furnishings.includes("podiums")){
   for(const x of [235,595,955]){rect(c,x,589,108,135,dark);rect(c,x-8,578,124,17,light);}
 }
 if(pkg.furnishings.includes("sofa")){
   rect(c,760,618,270,65,dark);rect(c,745,581,299,54,mid);rect(c,755,630,285,12,light+"55");
 }
 if(pkg.furnishings.includes("chairs")){
   rect(c,735,650,85,48,dark);rect(c,735,588,85,74,mid);
 }
 if(pkg.furnishings.includes("risers")){
   rect(c,195,658,890,45,dark);rect(c,190,653,900,8,light);
 }
 c.restore();
}
function drawOverlay(c,pkg,state){
 if(state?.lowerThird){
   rect(c,42,580,775,100,"#0b172add");rect(c,42,580,9,100,pkg.theme[2]);
   text(c,pkg.graphics,72,619,22,pkg.theme[2],"left");
   text(c,state.lowerText||"LIVE FROM BELLA FAUX PAS",72,660,27,"#f8faff","left");
 }
 if(pkg.id==="game"){
   rect(c,1002,27,240,92,"#101827e8");
   text(c,"PLAYER 1   "+(state?.scores?.[0]||0),1121,65,20,"#fff");
   text(c,"PLAYER 2   "+(state?.scores?.[1]||0),1121,96,20,"#fff");
 }
 if(state?.blackout)rect(c,0,0,W,H,"#000000");
}
function renderWorld(c,pkg,state,shot,dt){
 c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,W,H);
 const shift=(shot.center[0]-.5)*100;
 const assets=state.assets||{};
 drawBack(c,pkg,assets,shift);
 drawMiddle(c,pkg,assets,shift);
 const glb=state.avatarBridge;
 for(const p of state.performers||[]){
    const pos=p.position||[.5,.82],x=pos[0]*W,y=pos[1]*H;
    const height=220+(pos[1]-.8)*115;
    if(!glb?.has?.(p.id)) continue; // no fake sprite fallback
    try{glb.draw(c,p.id,x,y,height,{vx:p.vx||0,vy:p.vy||0,moving:!!p.moving,dt:dt||0});}
    catch(e){if(!state.avatarError)state.avatarError="3D actor render failed: "+e.message;}
 }
 drawFurniture(c,pkg,assets,shift);
}
function renderCamera(c,pkg,shot,state,world,dt){
 renderWorld(world.getContext("2d"),pkg,state,shot,dt);
 const source=PubShot(shot);
 c.save();c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,W,H);
 c.drawImage(world,source.x,source.y,source.w,source.h,0,0,W,H);
 drawOverlay(c,pkg,state);c.restore();
}
function PubShot(s){
 const w=W/s.zoom,h=H/s.zoom;return {x:Math.max(0,Math.min(W-w,s.center[0]*W-w/2)),y:Math.max(0,Math.min(H-h,s.center[1]*H-h/2)),w,h};
}
return {W,H,renderWorld,renderCamera,viewport:PubShot};
});
