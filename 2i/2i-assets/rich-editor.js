/* Local, opt-in rich DOCX surface for 2i. No new editor or storage engine. */
const base="/2i-assets/vendor/docx/";
const fonts=[["LiberationMono","Courier New"],["LiberationSerif","Times New Roman"],["Carlito","Calibri"]].flatMap(([file,family])=>[["Regular",400,"normal"],["Bold",700,"normal"],["Italic",400,"italic"],["BoldItalic",700,"italic"]].map(([name,weight,style])=>({url:base+"fonts/"+file+"-"+name+".ttf",family,weight,style})));
let readyStyle;
function loadStyle(){
  if(!readyStyle)readyStyle=new Promise((resolve,reject)=>{
    const link=document.createElement("link");link.rel="stylesheet";link.href=base+"editor.css";
    link.onload=()=>resolve();link.onerror=()=>{link.remove();reject(Error("Local DOCX editor stylesheet is unavailable."))};document.head.append(link);
  }).catch(error=>{readyStyle=null;throw error});
  return readyStyle;
}
export async function mountRichEditor({container,bytes,onChange,onSave,onError,loadRuntime=()=>import("/2i-assets/vendor/docx/engine.js"),ensureStyle=loadStyle}){
  if(!(bytes instanceof Uint8Array)||!bytes.length)throw Error("No DOCX bytes supplied.");
  const engine=await loadRuntime();
  if(typeof engine.createDocxEditor!=="function"||typeof engine.loadFonts!=="function")throw Error("The pinned local DOCX runtime is not available.");
  await ensureStyle();
  const fontSet=await engine.loadFonts({sources:fonts});
  if(fontSet.failures?.length)throw Error("One or more local editing fonts are missing. Original document retained.");
  const node=(tag,text,parent)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(parent)parent.append(e);return e;};
  const host=node("section",null);host.style.cssText="display:flex;flex-direction:column;min-height:420px;height:100%;background:#eeeae2;color:#222";
  const tools=node("div",null,host);tools.style.cssText="display:flex;flex-wrap:wrap;gap:6px;padding:8px";
  const info=node("p","Opening formatted document…",host);info.setAttribute("role","status");info.style.cssText="margin:4px 8px;font:13px system-ui";
  const surface=node("div",null,host);surface.className="docx-editor";surface.style.cssText="flex:1;min-height:360px;overflow:auto";
  container.append(host);
  let editor,subs=[],closed=false;
  try{
    editor=engine.createDocxEditor({container:surface,document:bytes,fonts:fontSet});
    const deadline=Date.now()+20000;
    while(editor.snapshot().isLoading||editor.snapshot().isOpening){if(Date.now()>=deadline)throw Error("The formatted editor did not finish opening.");await new Promise(resolve=>setTimeout(resolve,50));}
    const snapshot=editor.snapshot();if(snapshot.parseError||!snapshot.editable)throw Error("The free local engine could not open this document for editing; the source remains available.");
    const controls=[];
    function refresh(){
      if(closed)return;
      for(const [button,command] of controls){try{button.disabled=!editor.can(command).ok;}catch{button.disabled=true;}}
      const s=editor.snapshot();const page=s.page;info.textContent=(page?.total?"Page "+page.current+" of "+page.total+" · ":"")+"Local font substitutions may affect layout. Review formatted exports.";
    }
    function command(label,type){
      const b=node("button",label,tools);b.type="button";b.style.minHeight="40px";const cmd={type};
      b.addEventListener("pointerdown",e=>e.preventDefault());
      b.onclick=()=>{try{if(!editor.can(cmd).ok)return;const result=editor.exec(cmd);if(!result.ok)throw Error(result.reason||"Formatting command refused.");editor.focus();refresh();}catch(e){onError?.(e);}};controls.push([b,cmd]);
    }
    command("Bold","toggleBold");command("Italic","toggleItalic");command("Underline","toggleUnderline");command("Undo","undo");command("Redo","redo");
    const save=node("button","Save working copy",tools);save.type="button";save.style.minHeight="40px";save.onclick=()=>Promise.resolve().then(onSave).catch(e=>onError?.(e));
    const shortcut=e=>{if(e.isComposing||e.repeat||!(e.ctrlKey||e.metaKey)||String(e.key).toLowerCase()!=="s")return;e.preventDefault();e.stopPropagation();save.click();};
    host.addEventListener("keydown",shortcut);
    subs.push(editor.on("change",change=>{if(closed)return;if(!["load","refresh","recovery"].includes(change?.source))onChange?.();refresh();}));
    subs.push(editor.on("selectionChange",refresh));subs.push(editor.on("error",error=>onError?.(error)));
    refresh();
    return {async saveBytes(){if(closed)throw Error("Formatted editor closed.");const raw=await editor.save();const result=new Uint8Array(raw);if(result.length<4||result[0]!==80||result[1]!==75||result[2]!==3||result[3]!==4)throw Error("Editor did not return a DOCX package.");return result;},destroy(){if(closed)return;closed=true;for(const unsubscribe of subs)if(typeof unsubscribe==="function")unsubscribe();host.removeEventListener("keydown",shortcut);editor.destroy();host.remove();}};
  }catch(error){for(const unsubscribe of subs)if(typeof unsubscribe==="function")unsubscribe();try{editor?.destroy();}finally{host.remove();}throw error;}
}
