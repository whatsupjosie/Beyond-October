/* Native 2i authoring menus. */
(function installFormatMenu(){
  if(!nativeFormatting)return;
  const C=TwoiFormatCore;
  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;if(parent)parent.append(n);return n;};
  const menu=el("nav",null);menu.id="twoiMenuBar";menu.setAttribute("aria-label","2i document menus");
  ($("twoiVersionBar")||document.querySelector(".top-bar")).after(menu);
  const go=id=>{const run=()=>{const b=$(id);if(!b||b.disabled||b.getAttribute("aria-disabled")==="true")throw Error("This control is not available in the current mode.");b.click();};run.available=()=>{const b=$(id);return !!b&&!b.disabled&&b.getAttribute("aria-disabled")!=="true";};return run;};
  function safe(fn){try{const r=fn();if(r?.catch)r.catch(e=>addChat("notice",e.message));}catch(e){addChat("notice",e.message);}}
  function select(host,label,items,initial=""){
    const s=el("select",null,host);s.setAttribute("aria-label",label);
    for(const [value,name] of items){const o=el("option",name,s);o.value=value;}s.value=initial;return s;
  }
  const commands=[];
  function commandMenu(label,items){const entries=items.map(([name,run,keywords])=>({group:label,label:name,run,keywords}));commands.push(...entries);const s=select(menu,label,[["",label],...entries.map((cmd,i)=>[String(i),cmd.label])]);s.onchange=()=>{const i=s.value;s.value="";if(i!=="")safe(entries[Number(i)].run);};}
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
  function committedText(){return committed.join("\n");}
  function exportCommitted(){downloadFile(safeName()+".txt",committedText(),"text/plain;charset=utf-8");}
  function referenceArchive(){
    const d=dialog("Reference archive"),source=documentId;
    const q=el("input",null,d);q.type="search";q.placeholder="Search names or contents";q.setAttribute("aria-label","Search reference archive");q.style.width="100%";
    const list=el("div",null,d),status=textStatus(d);
    function refresh(){list.replaceChildren();const term=q.value.toLowerCase().trim();const rows=references.filter(r=>!term||r.name.toLowerCase().includes(term)||r.content.toLowerCase().includes(term));status.textContent=rows.length+" matching reference(s)";for(const r of rows){const b=button(list,r.name,()=>{if(source!==documentId||!references.includes(r))throw Error("The reference changed. Reopen the archive.");d.close();viewReferenceRecord(r);});b.style.display="block";b.style.whiteSpace="normal";b.style.minHeight="42px";}}
    q.addEventListener("input",refresh);button(d,"Add reference",()=>{if(source!==documentId)throw Error("The manuscript changed.");d.close();go("addRefBtn")();});button(d,"Close",()=>d.close());refresh();d.showModal();q.focus();
  }
  commandMenu("File",[["New",go("hmNewDoc")],["Open .2i",go("hmOpenDoc")],["My manuscripts",go("shelfBtn")],["Save",go("saveBtn")],["Save a copy (.2i)",go("hmSaveAs")],["Export Markdown (includes presented draft)",go("exportBtn"),"markdown md"],["Export committed text only",exportCommitted,"plain txt manuscript privacy"],["Export formatted HTML",()=>downloadFile(safeName()+".html",output(),"text/html")],["Restore autosave",go("hmRestoreAutosave")],["Rename",go("hmRenameDoc")]]);
  commandMenu("Edit",[["Undo",()=>undo()],["Redo",()=>redo()],["Find & replace",go("hmFindReplace")]]);
  commandMenu("Insert",[["New chapter",go("newChapterBtn")]]);
  commandMenu("Format",[["Document type / script presets",templates],["Paragraph style, alignment, indent…",paragraph],["Formatting recovery",unmapped]]);
  commandMenu("Layout",[["Page setup",page],["Formatted preview",preview]]);
  commandMenu("References",[["Browse or search references",referenceArchive,"research notes archive"],["Add reference",go("addRefBtn")]]);
  commandMenu("Manuscript",[["Scene intelligence",go("narrativeOpen")],["New chapter",go("newChapterBtn")],["Generate draft",go("genBtn")],["Commit presented draft",go("approveBtn")],["Archive presented draft",go("narrativeArchiveDraft")]]);
  commandMenu("Review",[["Revision history",go("narrativeHistory")],["Creative contribution records",go("narrativeContribution"),"authorship provenance evidence disclosure"],["Lock scene",go("lockSceneBtn")],["Lock all",go("lockAllBtn")],["Unlock",go("unlockBtn")]]);
  const present=mode=>()=>window.twoiSetPresentation(mode);
  const presentations=typeof window.twoiSetPresentation==="function"?[["Standard document view",present("standard")],["Notebook view",present("notebook")],...(window.twoiCanPresent("typewriter")?[["Typewriter view",present("typewriter")]]:[])]:[];
  commandMenu("View",[...presentations,["Write / Collab",go("modeBadge")],["Toggle sidebar",go("sidebarToggle")],["Zoom manuscript in",()=>adjustZoom("manuscript",1)],["Zoom manuscript out",()=>adjustZoom("manuscript",-1)],["Formatted preview",preview]]);
  commandMenu("Tools",[["Word and character count",stats],["Read presented draft",go("playBtn")],["Stop reading / generation",go("stopBtn")],["Model settings",go("hmLLMSettings")]]);
  commandMenu("Studio",[["Inbox",go("twoiNotesInbox")],["Write note",go("twoiWriteNote")],["Place sticky note",go("twoiPlaceNote")]]);
  commandMenu("Help",[["Keyboard shortcuts",go("hmKeyboardHelp")]]);

  function rankCommands(commands,query){
  const terms=String(query||"").toLowerCase().trim().split(/\s+/).filter(Boolean);
  return commands.map((cmd,index)=>{
    const label=cmd.label.toLowerCase(), group=cmd.group.toLowerCase(), full=group+" "+label+" "+(cmd.keywords||"").toLowerCase();
    if(!terms.every(term=>full.includes(term)))return null;
    const score=terms.reduce((n,t)=>n+(label===t?12:label.startsWith(t)?7:label.includes(t)?4:group.includes(t)?2:1),0);
    return {cmd,index,score};
  }).filter(Boolean).sort((a,b)=>b.score-a.score||a.index-b.index).map(x=>x.cmd);
}
  function openPalette(){
    if(document.querySelector("dialog[open], .modal-backdrop.open"))return;
    recordSelection();
    const origin=document.activeElement,source=documentId;
    const d=el("dialog",null,document.body);d.id="twoiCommandPalette";d.setAttribute("aria-labelledby","twoiCommandTitle");
    Object.assign(d.style,{width:"min(560px,94vw)",maxHeight:"85dvh",overflow:"auto",padding:"16px",borderRadius:"10px",background:"#f7efe0",color:"#29231b",border:"1px solid #8b7250"});
    const heading=el("h2","Find a command",d);heading.id="twoiCommandTitle";
    const search=el("input",null,d);search.type="search";search.placeholder="Search commands or menus…";search.setAttribute("aria-label","Search commands");search.autocomplete="off";Object.assign(search.style,{boxSizing:"border-box",width:"100%",minHeight:"42px",padding:"8px"});
    const status=el("p","",d);status.setAttribute("role","status");
    const list=el("div",null,d);Object.assign(list.style,{display:"grid",gap:"6px",maxHeight:"52dvh",overflowY:"auto"});
    const close=button(d,"Close",()=>d.close());close.style.marginTop="12px";
    let rows=[],executing=false;
    const available=cmd=>!cmd.run.available||cmd.run.available();
    function execute(cmd){
      if(source!==documentId){status.textContent="The active manuscript changed. Reopen the command palette.";return;}
      if(!available(cmd)){status.textContent="That command is no longer available.";refresh();return;}
      executing=true;d.close();if(origin?.isConnected)origin.focus();safe(cmd.run);
    }
    function refresh(){
      list.replaceChildren();rows=[];
      const matches=rankCommands(commands.filter(available),search.value);
      status.textContent=matches.length+(matches.length===1?" command":" commands")+" · Enter runs the first match; Esc closes.";
      for(const cmd of matches){
        const b=el("button",cmd.group+" · "+cmd.label,list);b.type="button";Object.assign(b.style,{textAlign:"left",minHeight:"42px",padding:"7px 10px",border:"1px solid #aa987c",borderRadius:"5px",background:"#fffaf1",color:"#29231b"});b.onclick=()=>execute(cmd);rows.push({b,cmd});
      }
      if(!matches.length)el("p","No matching available commands.",list);
    }
    search.addEventListener("input",refresh);
    d.addEventListener("keydown",e=>{
      e.stopPropagation(); // Never send search-box editing keystrokes to manuscript shortcuts.
      if(e.key==="Escape"){e.preventDefault();d.close();return;}
      if(e.isComposing)return;
      if(e.target===search&&e.key==="Enter"){e.preventDefault();if(rows.length)execute(rows[0].cmd);}
      if(e.key==="ArrowDown"||e.key==="ArrowUp"){
        const i=rows.findIndex(r=>r.b===document.activeElement);
        if(e.target!==search&&i<0)return;
        if(!rows.length)return;e.preventDefault();
        if(e.key==="ArrowUp"&&(i===0||i<0))search.focus();
        else rows[Math.min(rows.length-1,Math.max(0,i+(e.key==="ArrowUp"?-1:1)))].b.focus();
      }
    });
    d.addEventListener("close",()=>{d.remove();if(!executing&&origin?.isConnected)origin.focus();},{once:true});
    refresh();d.showModal();search.focus();
  }
  const paletteButton=button(menu,"Commands",openPalette);paletteButton.id="twoiCommands";paletteButton.title="Find a command (Ctrl/Command+Shift+P)";paletteButton.setAttribute("aria-keyshortcuts","Control+Shift+P Meta+Shift+P");paletteButton.style.flex="0 0 auto";paletteButton.style.minHeight="34px";menu.prepend(paletteButton);
  document.addEventListener("keydown",e=>{
    if(e.isComposing||e.repeat||!(e.ctrlKey||e.metaKey)||!e.shiftKey||e.altKey||e.key.toLowerCase()!=="p"||document.querySelector("dialog[open], .modal-backdrop.open"))return;
    e.preventDefault();e.stopPropagation();openPalette();
  },true);
  const quick=select(menu,"Quick paragraph element",[]);let lastProfile=null;
  function refreshQuick(){const profile=syncManuscriptFormat().profile;if(profile===lastProfile)return;lastProfile=profile;quick.replaceChildren();const first=el("option","Element…",quick);first.value="";for(const role of C.profiles[profile].roles){const o=el("option",C.names[role],quick);o.value=role;}quick.value="";quick.title=C.profiles[profile].label;}
  quick.onchange=()=>{const role=quick.value;quick.value="";if(!role)return;safe(()=>{ready();const indices=stableSelection(),next=C.clone(syncManuscriptFormat());for(const i of indices){const current=next.rows.find(r=>r.index===i)?.style||C.defaultStyle(role);C.apply(next,committed,[i],{...current,role},lockedLines);}snapshot();manuscriptFormat=next;update();});};
  document.addEventListener("foresight:work-change",refreshQuick);window.addEventListener("focus",refreshQuick);const renderPrevious=render;render=function(){renderPrevious();refreshQuick();};refreshQuick();
})();
