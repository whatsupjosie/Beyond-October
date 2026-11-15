/* Native 2i authoring menus. */
(function installFormatMenu(){
  if(!nativeFormatting)return;
  const C=TwoiFormatCore;
  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;if(parent)parent.append(n);return n;};
  const menu=el("nav",null);menu.id="twoiMenuBar";menu.setAttribute("aria-label","2i document menus");
  ($("twoiVersionBar")||document.querySelector(".top-bar")).after(menu);
  const go=id=>()=>{const b=$(id);if(!b)throw Error("This control is not available in the current mode.");b.click();};
  function safe(fn){try{const r=fn();if(r?.catch)r.catch(e=>addChat("notice",e.message));}catch(e){addChat("notice",e.message);}}
  function select(host,label,items,initial=""){
    const s=el("select",null,host);s.setAttribute("aria-label",label);
    for(const [value,name] of items){const o=el("option",name,s);o.value=value;}s.value=initial;return s;
  }
  function commandMenu(label,items){const s=select(menu,label,[["",label],...items.map(([name],i)=>[String(i),name])]);s.onchange=()=>{const i=s.value;s.value="";if(i!=="")safe(items[Number(i)][1]);};}
  const button=(host,label,fn)=>{const b=el("button",label,host);b.type="button";b.className="mc-btn";b.onclick=()=>safe(fn);return b;};
  let selection={document:null,indices:[]};
  const recordSelection=()=>{
    if(coWriting){selection={document:documentId,indices:Number.isInteger(selectedIdx)?[selectedIdx]:[]};return;}
    const value=soloTextarea.value,start=soloTextarea.selectionStart,end=soloTextarea.selectionEnd;
    const first=value.slice(0,start).split("\n").length-1,last=value.slice(0,end>start?end-1:end).split("\n").length-1;
    selection={document:documentId,indices:Array.from({length:Math.max(1,last-first+1)},(_,i)=>first+i)};
  };
  for(const name of ["select","keyup","pointerup","blur"])soloTextarea.addEventListener(name,recordSelection);
  document.addEventListener("pointerdown",e=>{if(menu.contains(e.target))recordSelection();},true);
  function stableSelection(){
    if(coWriting)recordSelection();
    if(selection.document!==documentId||!selection.indices.length)throw Error("Put the cursor in a paragraph, or select manuscript paragraphs first. In Collab, select a committed line.");
    return selection.indices.slice();
  }
  function ready(){if(initializing||generating||chatSending||editingIdx!==null)throw Error("Finish the active request or edit before changing document formatting.");}
  function dialog(title){
    const old=$("twoiFormatDialog");if(old)old.remove();
    const d=el("dialog",null,document.body);d.id="twoiFormatDialog";d.setAttribute("aria-label",title);
    el("h2",title,d);d.addEventListener("close",()=>d.remove(),{once:true});return d;
  }
  const field=(d,label,node)=>{const l=el("label",label,d);l.append(node);return node;};
  const textStatus=(d)=>{const n=el("p","",d);n.setAttribute("role","status");return n;};
  function update(){markDirty();render();if(typeof writeRecovery==="function")writeRecovery();}
  function templates(){
    ready();const d=dialog("Document format"),s=el("select",null),current=syncManuscriptFormat();
    for(const group of [...new Set(Object.values(C.profiles).map(p=>p.group))]){
      const g=el("optgroup",null,s);g.label=group;for(const [key,p] of Object.entries(C.profiles).filter(([k,p])=>p.group===group)){const o=el("option",p.label,g);o.value=key;}
    }
    s.value=current.profile;field(d,"Template",s);
    const info=el("p","",d);function refresh(){const p=C.profiles[s.value];info.textContent=p.guidance+" Available paragraph roles: "+p.roles.map(k=>C.names[k]).join(" · ")+". This is a starting convention, not certification for a specific broadcaster, studio or submission.";}s.onchange=refresh;refresh();
    el("p","Changing the template does not rewrite the manuscript or convert narrative content. Previously chosen paragraph roles remain preserved; review them after changing formats.",d);
    const source=documentId;button(d,"Apply template",()=>{ready();if(documentId!==source)throw Error("Manuscript changed; reopen format.");snapshot();manuscriptFormat.profile=s.value;update();d.close();});
    button(d,"Cancel",()=>d.close());d.showModal();
  }
  function paragraph(){
    ready();const indices=stableSelection(),source=documentId,basis=committed.slice(),d=dialog("Paragraph and text appearance"),st=syncManuscriptFormat(),p=C.profiles[st.profile],existing=st.rows.find(r=>r.index===indices[0])?.style;
    const initial=existing&&p.roles.includes(existing.role)?existing:C.defaultStyle(p.roles[0]);
    el("p","Editing "+indices.length+" committed paragraph(s). Whole-paragraph styling only. For character-range formatting, use the future rich-document editor integration.",d);
    const role=field(d,"Paragraph role",select(null,"Paragraph role",p.roles.map(k=>[k,C.names[k]]),initial.role));
    const align=field(d,"Alignment",select(null,"Alignment",["default","left","center","right","justify"].map(k=>[k,k]),initial.align));
    const font=field(d,"Font family",select(null,"Font family",["default","serif","sans","mono"].map(k=>[k,k]),initial.font));
    const indent=field(d,"Left indent (inches)",select(null,"Left indent",[0,.25,.5,.75,1,1.5,2,2.5,3,4].map(n=>[String(n),String(n)]),String(initial.indent)));
    const size=field(d,"Point size",select(null,"Point size",[0,10,11,12,14,16,18,20,24,28,36,48].map(n=>[String(n),n?String(n):"Template default"]),String(initial.size)));
    const spacing=field(d,"Line spacing",select(null,"Line spacing",[0,1,1.15,1.5,2].map(n=>[String(n),n?String(n):"Template default"]),String(initial.spacing)));
    const flags={};for(const key of ["bold","italic","underline"]){const i=el("input",null);i.type="checkbox";i.checked=initial[key];flags[key]=field(d,key,i);}
    const status=textStatus(d);
    function verify(){ready();if(source!==documentId||basis.length!==committed.length||basis.some((x,i)=>x!==committed[i]))throw Error("Manuscript text changed. Select the intended paragraph again.");}
    button(d,"Apply",()=>{try{verify();const next=C.clone(syncManuscriptFormat());C.apply(next,committed,indices,{role:role.value,align:align.value,font:font.value,indent:Number(indent.value),size:Number(size.value),spacing:Number(spacing.value),...Object.fromEntries(Object.entries(flags).map(([k,v])=>[k,v.checked]))},lockedLines);snapshot();manuscriptFormat=next;update();d.close();}catch(e){status.textContent=e.message;}});
    button(d,"Clear selected formatting",()=>{try{verify();const next=C.clone(syncManuscriptFormat());C.clear(next,indices,lockedLines);snapshot();manuscriptFormat=next;update();d.close();}catch(e){status.textContent=e.message;}});
    button(d,"Cancel",()=>d.close());d.showModal();
  }
  function page(){
    ready();const d=dialog("Page setup"),p=syncManuscriptFormat().page,source=documentId;
    const size=field(d,"Paper size",select(null,"Paper size",[["letter","US Letter"],["a4","A4"],["legal","US Legal"]],p.size));
    const orientation=field(d,"Orientation",select(null,"Orientation",[["portrait","Portrait"],["landscape","Landscape"]],p.orientation));
    const margin=field(d,"Margins (all sides, inches)",select(null,"Margins",[.5,.75,1,1.25,1.5].map(x=>[String(x),String(x)]),String(p.margin)));
    el("p","Page layout applies to formatted preview and HTML export. It does not change the text or calculate exact manuscript pagination.",d);
    button(d,"Apply",()=>{ready();if(source!==documentId)throw Error("Manuscript changed.");snapshot();manuscriptFormat.page={size:size.value,orientation:orientation.value,margin:Number(margin.value)};update();d.close();});button(d,"Cancel",()=>d.close());d.showModal();
  }
  function output(){return C.exportHtml(documentTitle,committed.slice(),syncManuscriptFormat(),chapters);}
  function preview(){
    const d=dialog("Formatted manuscript preview");d.classList.add("wide");
    el("p","Committed manuscript only. Drafts, latent prose, notes and chat are excluded. This is a browser layout proof, not certified screenplay pagination.",d);
    const frame=el("iframe",null,d);frame.title="Formatted manuscript";frame.setAttribute("sandbox","");frame.srcdoc=output();
    button(d,"Export printable HTML",()=>downloadFile(safeName()+".html",output(),"text/html"));button(d,"Close",()=>d.close());d.showModal();
  }
  function stats(){const d=dialog("Document statistics"),t=committed.join("\n"),draft=buffer.join("\n"),wc=x=>x.trim().split(/\s+/).filter(Boolean).length;el("p","Committed: "+wc(t)+" words · "+[...t].length+" characters · "+committed.length+" lines",d);el("p","Presented draft: "+wc(draft)+" words. Withheld material is not included.",d);el("p","Estimated reading time: "+Math.ceil(wc(t)/200)+" min at 200 words/min.",d);button(d,"Close",()=>d.close());d.showModal();}
  function unmapped(){
    const d=dialog("Formatting recovery"),rows=syncManuscriptFormat().unmapped;
    el("p",rows.length?rows.length+" format record(s) were detached by text edits; source text was not changed. Apply the desired format again to the correct paragraph.":"No detached formatting records.",d);
    for(const r of rows){const p=el("pre",r.text+"\n"+JSON.stringify(r.style,null,2),d);p.style.whiteSpace="pre-wrap";}
    button(d,"Close",()=>d.close());d.showModal();
  }
  commandMenu("File",[["New",go("hmNewDoc")],["Open .2i",go("hmOpenDoc")],["My manuscripts",go("shelfBtn")],["Save",go("saveBtn")],["Save a copy (.2i)",go("hmSaveAs")],["Export Markdown",go("exportBtn")],["Export formatted HTML",()=>downloadFile(safeName()+".html",output(),"text/html")],["Restore autosave",go("hmRestoreAutosave")],["Rename",go("hmRenameDoc")]]);
  commandMenu("Edit",[["Undo",()=>undo()],["Redo",()=>redo()],["Find & replace",go("hmFindReplace")]]);
  commandMenu("Insert",[["New chapter",go("newChapterBtn")]]);
  commandMenu("Format",[["Document type / script presets",templates],["Paragraph style, alignment, indent…",paragraph],["Formatting recovery",unmapped]]);
  commandMenu("Layout",[["Page setup",page],["Formatted preview",preview]]);
  commandMenu("Review",[["Scene intelligence",go("narrativeOpen")],["Archive presented draft",go("narrativeArchiveDraft")],["Revision history",go("narrativeHistory")],["Lock scene",go("lockSceneBtn")],["Lock all",go("lockAllBtn")],["Unlock",go("unlockBtn")],["Commit presented draft",go("approveBtn")]]);
  commandMenu("View",[["Write / Collab",go("modeBadge")],["Toggle sidebar",go("sidebarToggle")],["Zoom manuscript in",()=>adjustZoom("manuscript",1)],["Zoom manuscript out",()=>adjustZoom("manuscript",-1)],["Formatted preview",preview]]);
  commandMenu("Tools",[["Word and character count",stats],["Read presented draft",go("playBtn")],["Stop reading / generation",go("stopBtn")],["Model settings",go("hmLLMSettings")],["Keyboard shortcuts",go("hmKeyboardHelp")]]);
  commandMenu("Studio",[["Inbox",go("twoiNotesInbox")],["Write note",go("twoiWriteNote")],["Place sticky note",go("twoiPlaceNote")]]);
  const quick=select(menu,"Quick paragraph element",[]);let lastProfile=null;
  function refreshQuick(){const profile=syncManuscriptFormat().profile;if(profile===lastProfile)return;lastProfile=profile;quick.replaceChildren();const first=el("option","Element…",quick);first.value="";for(const role of C.profiles[profile].roles){const o=el("option",C.names[role],quick);o.value=role;}quick.value="";quick.title=C.profiles[profile].label;}
  quick.onchange=()=>{const role=quick.value;quick.value="";if(!role)return;safe(()=>{ready();const indices=stableSelection(),next=C.clone(syncManuscriptFormat());for(const i of indices){const current=next.rows.find(r=>r.index===i)?.style||C.defaultStyle(role);C.apply(next,committed,[i],{...current,role},lockedLines);}snapshot();manuscriptFormat=next;update();});};
  document.addEventListener("foresight:work-change",refreshQuick);window.addEventListener("focus",refreshQuick);const renderPrevious=render;render=function(){renderPrevious();refreshQuick();};refreshQuick();
})();
