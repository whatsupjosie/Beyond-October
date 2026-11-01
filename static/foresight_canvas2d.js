/* Foresight Canvas 2D compatibility renderer.
 *
 * The Counter's genuine geometry, hit targets, physics and content hosting
 * remain the same. Only the GPU-dependent drawing backend changes. No remote
 * resources or runtime installation are required. This is intentionally a
 * legible fallback, not a claim of material parity with the HDR renderer.
 */
(function (root) {
  'use strict';
  const MATERIAL = Object.freeze({
    0:'#dfb968',1:'#d9a49b',2:'#bc8846',3:'#b77c54',4:'#a7abb7',5:'#9a7f60',6:'#d9c69d',7:'#889aa8',
    10:'#f0ecdf',11:'#dfb2b4',12:'#669c80',13:'#303339',14:'#475778',
    20:'#747577',21:'#24282f',30:'#af9175',40:'#4f3327',41:'#ac8154',42:'#693e3a',
    50:'#c8baae',51:'#dfdcce',52:'#c9d2d7',53:'#b3bdca',60:'#6b463b',
    70:'#63466a',71:'#286858',72:'#3b5e90',73:'#434754',74:'#723c52',75:'#256452',76:'#17171d',
    80:'#d2bd9c',81:'#50382a'
  });
  const PALETTE=Object.freeze({
    tigereye:['#1d120d','#4b2e18','#100a09'],pearl:['#2c2830','#746a6b','#17151a'],
    indigo:['#101527','#313a62','#090b15'],nero:['#090a0b','#303239','#060608'],
    walnut:['#24150f','#51311f','#160e0b']
  });
  const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
  function polygon(ctx,points){
    if(!Array.isArray(points)||points.length<3)return false;
    if(!points.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))return false;
    ctx.beginPath();ctx.moveTo(points[0][0],points[0][1]);
    for(let i=1;i<points.length;i++)ctx.lineTo(points[i][0],points[i][1]);
    ctx.closePath();return true;
  }
  class ForesightCanvas2D {
    constructor(canvas){
      if(!canvas||typeof canvas.getContext!=='function')throw new Error('Canvas 2D requires a canvas');
      const ctx=canvas.getContext('2d',{alpha:false});
      if(!ctx)throw new Error('Canvas 2D unavailable; unable to create the Counter renderer');
      this.canvas=canvas;this.ctx=ctx;this.gl={finish(){}};
      this.theme='tigereye';this.quality='full';this.lamp=true;
      this.lightPos=[130,65];this.lampHeight=.3;this.exposure=1.0;this.bloomMix=0;
      this.light2={intensity:.5};this._items=[];
    }
    setTheme(theme){this.theme=Object.hasOwn(PALETTE,theme)?theme:'tigereye';}
    setLight2(light){this.light2=Object.assign({},light||{});}
    loadStone(){ /* The drawn material is local; there is no image/network dependency. */ }
    resize(){
      const dpr=clamp(root.devicePixelRatio||1,1,2),w=Math.max(1,Math.round(this.canvas.clientWidth*dpr)),
            h=Math.max(1,Math.round(this.canvas.clientHeight*dpr));
      if(this.canvas.width!==w)this.canvas.width=w;
      if(this.canvas.height!==h)this.canvas.height=h;
      return dpr;
    }
    draw(items){
      if(!Array.isArray(items))throw new TypeError('Canvas 2D draw expects scene items');
      const dpr=this.resize(),ctx=this.ctx,width=this.canvas.width/dpr,height=this.canvas.height/dpr;
      ctx.save();ctx.setTransform(dpr,0,0,dpr,0,0);
      try{
        const c=PALETTE[this.theme],background=ctx.createLinearGradient(0,0,width,height);
        background.addColorStop(0,c[0]);background.addColorStop(.45,c[1]);background.addColorStop(1,c[2]);
        ctx.fillStyle=background;ctx.fillRect(0,0,width,height);
        if(this.lamp){
          const light=ctx.createRadialGradient(this.lightPos[0],this.lightPos[1],10,this.lightPos[0],this.lightPos[1],Math.max(width,height)*.85);
          light.addColorStop(0,'rgba(255,215,141,.22)');light.addColorStop(1,'rgba(255,215,141,0)');
          ctx.fillStyle=light;ctx.fillRect(0,0,width,height);
        }
        for(const it of items){
          if(!it||!polygon(ctx,it.q))continue;
          const rim=MATERIAL[it.rimMat]||'#a39a8d';
          const floor=MATERIAL[it.floorMat]||'#201b19';
          ctx.save();
          ctx.shadowColor='rgba(0,0,0,.65)';ctx.shadowBlur=16;
          ctx.shadowOffsetY=7;
          ctx.fillStyle=floor;ctx.fill();
          ctx.restore();
          if(!polygon(ctx,it.q))continue;
          ctx.save();ctx.lineJoin='round';ctx.lineCap='round';
          ctx.strokeStyle=rim;
          ctx.lineWidth=clamp((it.rim||5)*1.7,3,22);
          ctx.stroke();
          if(it.focus||it.backlight){
            const glow=Array.isArray(it.glow)?it.glow:[.95,.7,.4,1], rgb=glow.slice(0,3).map(x=>Math.round(clamp(x,0,1)*255));
            ctx.shadowColor=`rgba(${rgb.join(',')},.75)`;ctx.shadowBlur=16;
            ctx.lineWidth=3;ctx.strokeStyle=`rgba(${rgb.join(',')},.9)`;ctx.stroke();
          }
          ctx.restore();
          if(it.screen){
            // The document/iframe is a separate accessible DOM layer; this
            // only makes its irregular surrounding tray frame visible.
            if(!polygon(ctx,it.q))continue;
            ctx.save();ctx.strokeStyle='rgba(247,227,184,.42)';ctx.lineWidth=1.5;ctx.stroke();ctx.restore();
          }
        }
      }finally{ctx.restore();}
    }
  }
  root.ForesightCanvas2D=ForesightCanvas2D;
})(window);
