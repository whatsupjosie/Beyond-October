/* Shared Bella Faux Pas / 2i seat contract. */
function createStudioBridge(){
  const safe=v=>typeof v==="string"&&/^[a-z0-9_-]{1,80}$/i.test(v);
  const rooms=new Set(["dressing_room","writers_room"]);
  function seatAllowed(room){return rooms.has(room);}
  function entry(room,view,seated=false){
    if(!safe(room)||!safe(view))throw Error("Invalid room or view.");
    if(seated&&!seatAllowed(room))throw Error("No writing station configured in this room.");
    return "/2i?studio_room="+encodeURIComponent(room)+"&studio_view="+encodeURIComponent(view)+(seated?"&desk=typewriter":"");
  }
  function presentation(room,view,desk){
    const valid=safe(room)&&safe(view);
    return {seated:valid&&desk==="typewriter"&&seatAllowed(room),returnPath:valid?"/world-walk?view="+encodeURIComponent(room+"/"+view):null,room:valid?room:null};
  }
  function cue(before,after,position,inputType,data,columns=60){
    if(typeof inputType!=="string"||!inputType.startsWith("insert")||/paste|drop|replacement|composition/i.test(inputType)||before===after)return {click:false,bell:false};
    if(inputType==="insertLineBreak"||inputType==="insertParagraph")return {click:true,bell:true};
    if(typeof data!=="string"||[...data].length!==1)return {click:false,bell:false};
    const prefix=after.slice(0,position),col=[...prefix.slice(prefix.lastIndexOf("\n")+1)].length;
    return {click:true,bell:col>0&&col%columns===0};
  }
  return {seatAllowed,entry,presentation,cue};
}
const TwoiStudioBridge=createStudioBridge();
if(typeof module!=="undefined"&&module.exports)module.exports=TwoiStudioBridge;
