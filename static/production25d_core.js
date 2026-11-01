/* PubCast 2.5D television production - declarative genre and shot geometry.
 * No dependency on a server, browser or DOM. Camera frames are real source-world
 * viewports, not names painted over one shared picture.
 * Copyright 2026 Rearview Foresight. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PubCast25D = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const W = 1280, H = 720;
  const slots = {
    anchor: [0.50,0.80], coanchor:[0.68,0.80], host:[0.31,0.82],
    guest:[0.69,0.82], guest2:[0.81,0.82], speaker:[0.50,0.83],
    moderator:[0.50,0.82], left:[0.24,0.83], right:[0.76,0.83],
    contestant1:[0.28,0.84], contestant2:[0.72,0.84], ensemble:[0.50,0.82]
  };
  const raw = {
    news: { title:"News", subtitle:"Anchor desk + standing presentation", theme:["#102b43","#205777","#a7cfde"], people:["anchor","coanchor"],
      cameras:[["wide","Newsroom wide",.50,.49,1],["anchor","Anchor close",.50,.62,2.6],["coanchor","Co-anchor close",.68,.62,2.7],["two","Desk two-shot",.59,.57,1.6],["presentation","Presentation screen",.28,.49,1.55]],
      furnishings:["desk","screen"], graphics:"NEWS DESK" },
    late_night: { title:"Late-night talk",subtitle:"Monologue, interview, performance",theme:["#271e4c","#755398","#d4a957"],people:["host","guest"],
      cameras:[["wide","Stage wide",.5,.50,1],["host","Host close",.31,.62,2.6],["guest","Guest close",.69,.62,2.7],["interview","Interview two-shot",.5,.59,1.65],["performance","Performance stage",.5,.55,1.25]],
      furnishings:["desk","sofa","curtain"],graphics:"LATE NIGHT" },
    debate: {title:"Formal debate",subtitle:"Moderator, opposing podiums and rebuttal shots",theme:["#1b2636","#536b81","#d4a16c"], people:["left","moderator","right"],
      cameras:[["wide","Debate podium wide",.5,.53,1],["moderator","Moderator close",.5,.61,2.5],["left","Debater left",.24,.62,2.4],["right","Debater right",.76,.62,2.4],["rebuttal","Rebuttal exchange",.50,.57,1.5]],
      furnishings:["podiums","screen"],graphics:"THE DEBATE" },
    political_discussion: {title:"Political roundtable",subtitle:"Roundtable discussion with host and multiple panelists",theme:["#1b302f","#3f6c60","#dfc397"],people:["host","left","right","guest2"],
      positions:{host:[.42,.82],left:[.18,.83],right:[.65,.83],guest2:[.86,.83]},
      cameras:[["wide","Roundtable wide",.5,.53,1],["host","Host analysis",.42,.63,2.55],["left","Panelist left",.18,.62,2.4],["right","Panelist right",.65,.62,2.4],["guest2","Panelist far right",.86,.62,2.4],["pair","Cross-table discussion",.52,.59,1.58],["four","Four-person panel",.52,.55,1.22]],
      furnishings:["panel","screen"],graphics:"POLITICAL ROUNDTABLE" },
    audience: {title:"Audience talk",subtitle:"Host, guests and floor participation",theme:["#30253e","#855d83","#daa47b"], people:["host","guest","guest2"],
      cameras:[["wide","Talk stage wide",.5,.51,1],["host","Host close",.31,.62,2.5],["guest","Guest close",.69,.62,2.6],["two","Guest reactions",.76,.6,2.0],["floor","Audience-facing floor",.5,.54,1.4]],
      furnishings:["sofa","chairs","curtain"],graphics:"OPEN FLOOR" },
    game: {title:"Game show",subtitle:"Host, contestants and scoring",theme:["#24224b","#614fc5","#efbe47"],people:["contestant1","speaker","contestant2"],
      cameras:[["wide","Competition wide",.5,.50,1],["host","Host center",.5,.62,2.5],["left","Contestant one",.28,.62,2.6],["right","Contestant two",.72,.62,2.6],["board","Scoreboard",.5,.27,2.0]],
      furnishings:["podiums","scoreboard"],graphics:"GAME NIGHT" },
    variety: {title:"Variety & sketch",subtitle:"Stage performance, group and entrances",theme:["#39182b","#99495d","#e2b780"], people:["left","speaker","right"],
      cameras:[["wide","Proscenium wide",.5,.5,1],["center","Center performance",.5,.62,2.1],["left","Stage left",.24,.62,2.4],["right","Stage right",.76,.62,2.4],["group","Ensemble",.5,.54,1.55]],
      furnishings:["curtain","risers"],graphics:"VARIETY STAGE" },
    general: {title:"General studio",subtitle:"Flexible production space",theme:["#20353b","#397277","#a4c1bb"],people:["left","speaker","right"],
      cameras:[["wide","Studio wide",.5,.5,1],["center","Center close",.5,.62,2.5],["left","Left close",.24,.62,2.6],["right","Right close",.76,.62,2.6],["two","Two-shot",.5,.57,1.65]],
      furnishings:["screen"],graphics:"PUBCAST STUDIO" }
  };
  function ensure(condition, message) { if (!condition) throw Error(message); }
  function build(id, data) {
    const cameras = data.cameras.map(([key,label,x,y,zoom]) => ({id:key,label,center:[x,y],zoom}));
    const performers = data.people.map((slot,i)=>({id:"performer-"+(i+1),slot,
      position:(data.positions?.[slot]||slots[slot]).slice(),avatar:i===0?"female":"male"}));
    return {id,title:data.title,subtitle:data.subtitle,theme:data.theme.slice(),graphics:data.graphics,
      furnishings:data.furnishings.slice(),performers,cameras,assetOverrides:{back:null,mid:null,front:null,logo:null},
      graphicsEnabled:true};
  }
  const PACKAGES = Object.freeze(Object.fromEntries(Object.entries(raw).map(([id,data])=>[id,build(id,data)])));
  function validate(pkg) {
    ensure(pkg && typeof pkg.id==="string" && Array.isArray(pkg.cameras) && pkg.cameras.length>=2,"Invalid production package");
    const ids = new Set();
    for (const c of pkg.cameras) {
      ensure(!ids.has(c.id),"Duplicate camera "+c.id); ids.add(c.id);
      ensure(Number.isFinite(c.zoom)&&c.zoom>=1&&c.zoom<=4,"Invalid zoom for "+c.id);
      ensure(c.center.length===2&&c.center.every(n=>Number.isFinite(n)&&n>=0&&n<=1),"Invalid center for "+c.id);
    }
    for(const p of pkg.performers) ensure(p.position.length===2&&p.position.every(n=>Number.isFinite(n)&&n>=0&&n<=1),"Invalid performer");
    return true;
  }
  Object.values(PACKAGES).forEach(validate);
  function shot(pkg,id) { const s=pkg.cameras.find(c=>c.id===id);ensure(s,"Unknown shot: "+id);return s; }
  function viewport(s) {
    const w=W/s.zoom,h=H/s.zoom;
    const x=Math.max(0,Math.min(W-w,s.center[0]*W-w/2)),y=Math.max(0,Math.min(H-h,s.center[1]*H-h/2));
    return {x,y,w,h};
  }
  function makeSession(pkg,now) {
    return {version:1,id:"pubcast25d-"+now+"-"+Math.random().toString(36).slice(2,8),packageId:pkg.id,
      startedAt:new Date(now).toISOString(),endedAt:null,events:[]};
  }
  function event(session,type,payload,now) {
    ensure(session&&!session.endedAt,"Session is closed");
    const item={offsetMs:Math.max(0,now-Date.parse(session.startedAt)),type,payload:JSON.parse(JSON.stringify(payload||{}))};
    session.events.push(item);return item;
  }
  function finish(session,now) {ensure(session&&!session.endedAt,"Session already closed"); session.endedAt=new Date(now).toISOString(); return session;}
  return {W,H,PACKAGES,validate,shot,viewport,makeSession,event,finish};
});
