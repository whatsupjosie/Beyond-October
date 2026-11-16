/* Native 2i authoring menus. */
(function installFormatMenu(){
  if(!nativeFormatting)return;
  const C=TwoiFormatCore;
  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;if(parent)parent.append(n);return n;};
  const menu=el("nav",null);menu.id="twoiMenuBar";menu.setAttribute("aria-label","2i document menus");
  ($("twoiVersionBar")||document.querySelector(".top-bar")).after(menu);
  function commandAvailable(command){try{return !command.run.available||!!command.run.available();}catch{return false;}}
  const conditional=(run,allowed)=>{run.available=allowed;return run;};
  const go=(id,allowed=()=>true)=>{const run=()=>{if(!run.available())throw Error("This control is not available in the current mode.");$(id).click();};run.available=()=>{const b=$(id);return !!b&&!b.disabled&&b.getAttribute("aria-disabled")!=="true"&&!!allowed();};return run;};
  const idle=()=>!initializing&&!generating&&!chatSending&&editingIdx===null;
  const collabIdle=()=>coWriting&&idle();
  function safe(fn){try{const r=fn();if(r?.catch)r.catch(e=>addChat("notice",e.message));}catch(e){addChat("notice",e.message);}}
  function select(host,label,items,initial=""){
    const s=el("select",null,host);s.setAttribute("aria-label",label);s.title=label;
    for(const [value,name] of items){const o=el("option",name,s);o.value=value;}s.value=initial;return s;
  }
  const commands=[];
  function commandMenu(label,items){
    const entries=items.map(([name,run,keywords])=>({group:label,label:name,run,keywords}));commands.push(...entries);
    const s=select(menu,label,[["",label],...entries.map((cmd,i)=>[String(i),cmd.label])]);
    const refresh=()=>{entries.forEach((cmd,i)=>{const option=s.options[i+1];if(option)option.disabled=!commandAvailable(cmd);});};
    s.addEventListener("focus",refresh);s.addEventListener("pointerdown",refresh);
    s.onchange=()=>{const i=s.value;s.value="";if(i==="")return;const cmd=entries[Number(i)];safe(()=>{if(!cmd||!commandAvailable(cmd))throw Error("That command is unavailable in the current editor state.");return cmd.run();});};
    refresh();
  }
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
    ready();const source=documentId,html=output(),filename=safeName()+".html";
    const d=dialog("Formatted manuscript preview");d.classList.add("wide");
    el("p","Snapshot of committed manuscript only. Drafts, latent prose, notes and chat are excluded. Browser print pagination can differ from professional production requirements.",d);
    const frame=el("iframe",null);frame.title="Formatted manuscript";
    // The exported markup escapes manuscript text; scripts remain forbidden.
    // Same-origin is necessary to invoke the isolated iframe's print method.
    frame.setAttribute("sandbox","allow-same-origin allow-modals");
    const status=textStatus(d);
    const print=button(d,"Print this snapshot",()=>{
      try{if(source!==documentId)throw Error("The active manuscript changed. Reopen the preview.");if(typeof frame.contentWindow?.print!=="function")throw Error("This browser does not support printing the preview. Export printable HTML instead.");frame.contentWindow.focus();frame.contentWindow.print();status.textContent="Print dialog requested. Check your browser's print preview.";}catch(error){status.textContent=error.message;}
    });print.disabled=true;
    button(d,"Export this snapshot as HTML",()=>downloadFile(filename,html,"text/html"));
    button(d,"Close",()=>d.close());
    frame.addEventListener("load",()=>{print.disabled=false;});frame.srcdoc=html;d.insertBefore(frame,status);d.showModal();
  }
  function scriptProfile(){return ["script","multi"].includes(C.profiles[syncManuscriptFormat().profile]?.kind);}
  function fdxExport(){
    ready();const source=documentId,result=C.exportFdx(committed.slice(),syncManuscriptFormat()),filename=safeName()+".fdx",d=dialog("Export screenplay exchange file");
    el("p",result.paragraphs+" committed paragraph(s). Basic typed Final Draft XML exchange, not verified Final Draft compatibility. No title-page layout, page lock, revision colors, custom formatting, private notes, or AI records are exported.",d);
    if(result.untyped)el("p",result.untyped+" unstyled nonblank paragraph(s) will be exported as Action. No screenplay role is inferred from capitalization.",d);
    if(result.fallbackRoles.length)el("p","Unsupported roles exported as General: "+result.fallbackRoles.map(r=>C.names[r]||r).join(", ")+". Exact text retained; original role metadata remains in native .2i.",d);
    el("p","Use the native .2i copy for full recovery. Open this exchange copy in your target screenwriting software and inspect pagination and formatting.",d);
    button(d,"Download FDX exchange copy",()=>{if(source!==documentId)throw Error("The active manuscript changed.");downloadFile(filename,result.xml,"application/xml;charset=utf-8");d.close();});
    button(d,"Cancel",()=>d.close());d.showModal();
  }
  function dialogueReview(){
    ready();const d=dialog("Dialogue and scene review"),source=documentId,basis=committed.slice(),get=()=>C.dialogueIndex(committed,syncManuscriptFormat()),result=get(),stamp=JSON.stringify(result);
    el("p","Read-only report from explicitly styled character cues and scene headings. Exact cue labels, including extensions, remain separate; no inferred characters or AI judgments. Unstyled prose is not analyzed.",d);
    el("p",result.scenes.length+" scene/act/segment headings · "+result.speakers.length+" distinct cue labels · "+result.unassigned.length+" unassigned dialogue/parenthetical paragraphs · "+result.untagged+" unstyled nonblank paragraphs.",d);
    const categories=[["","All cues"],...result.speakers.map((c,i)=>[String(i),c.name])],pick=select(d,"Character cue",categories),list=el("div",null,d),status=textStatus(d);
    function jump(index){try{ready();if(source!==documentId||basis.length!==committed.length||basis.some((x,i)=>x!==committed[i])||JSON.stringify(get())!==stamp)throw Error("The source changed. Reopen dialogue review.");paragraphOffset(committed,index);d.close();goToParagraph(index);}catch(e){status.textContent=e.message;}}
    function passage(r,parent){const p=el("p",r.text||"(Blank paragraph)",parent);p.style.whiteSpace="pre-wrap";p.style.overflowWrap="anywhere";button(parent,"Go to paragraph "+(r.index+1),()=>jump(r.index));}
    function refresh(){list.replaceChildren();const selected=pick.value===""?result.speakers:[result.speakers[Number(pick.value)]];let shown=0,limited=false;for(const c of selected){if(!c||shown>=200){limited=true;break;}const section=el("section",null,list);section.style.borderTop="1px solid #ad9b83";el("strong",c.name+" · "+c.cues.length+" cue(s), "+c.dialogue.filter(r=>r.role==="dialogue").length+" dialogue paragraphs",section);for(const r of c.dialogue){if(shown>=200){limited=true;break;}passage(r,section);shown++;}}if(limited)el("p","Preview limited to the first 200 passages; select a cue to narrow the review.",list);}
    const scenes=el("details",null,d);el("summary","Scene breakdown",scenes);for(const s of result.scenes.slice(0,200)){el("p",s.title+" · "+s.cues+" cues · "+s.dialogue+" dialogue paragraphs",scenes);button(scenes,"Go to paragraph "+(s.index+1),()=>jump(s.index));}
    if(result.scenes.length>200)el("p","First 200 scenes shown.",scenes);
    const orphan=el("details",null,d);el("summary","Unassigned dialogue / parentheticals",orphan);for(const r of result.unassigned.slice(0,100))passage(r,orphan);if(result.unassigned.length>100)el("p","First 100 unassigned passages shown.",orphan);
    pick.onchange=refresh;button(d,"Close",()=>d.close());refresh();d.showModal();
  }
  function stats(){const d=dialog("Document statistics"),t=committed.join("\n"),draft=buffer.join("\n"),wc=x=>x.trim().split(/\s+/).filter(Boolean).length;el("p","Committed: "+wc(t)+" words · "+[...t].length+" characters · "+committed.length+" lines",d);el("p","Presented draft: "+wc(draft)+" words. Withheld material is not included.",d);el("p","Estimated reading time: "+Math.ceil(wc(t)/200)+" min at 200 words/min.",d);button(d,"Close",()=>d.close());d.showModal();}
  function unmapped(){
    const d=dialog("Formatting recovery"),rows=syncManuscriptFormat().unmapped;
    el("p",rows.length?rows.length+" format record(s) were detached by text edits; source text was not changed. Apply the desired format again to the correct paragraph.":"No detached formatting records.",d);
    for(const r of rows){const p=el("pre",r.text+"\n"+JSON.stringify(r.style,null,2),d);p.style.whiteSpace="pre-wrap";}
    button(d,"Close",()=>d.close());d.showModal();
  }
  // Line offsets are UTF-16, as required by textarea.setSelectionRange.
  function paragraphOffset(lines,index){
    if(!Array.isArray(lines)||!Number.isInteger(index)||index<0||index>=lines.length)throw Error("Paragraph is outside the committed manuscript.");
    let start=0;for(let i=0;i<index;i++)start+=lines[i].length+1;
    return {start,end:start+lines[index].length};
  }
  function outlineEntries(lines,chapters,format,scenes){
    const rows=[];
    for(let i=0;i<chapters.length;i++){const c=chapters[i];rows.push({kind:"Chapter",title:c.title,index:c.startLine,reason:Number.isInteger(c.startLine)&&c.startLine>=0&&c.startLine<lines.length?"":"No committed text at this chapter yet.",key:"chapter:"+i});}
    for(const r of format.rows||[]){if(!["heading1","heading2","heading3","scene","act","segment"].includes(r.style.role))continue;if(lines[r.index]!==r.text)continue;rows.push({kind:C.names[r.style.role],title:r.text||"(Untitled heading)",index:r.index,reason:"",key:"format:"+r.index});}
    for(const s of scenes)rows.push({kind:"Scene dossier",title:s.title,index:s.start,reason:s.reason||"",key:"scene:"+s.id});
    for(const a of format.annotations||[])if(a.kind==="bookmark"&&a.status!=="archived")rows.push({kind:"Bookmark",title:a.label,index:a.index,reason:a.detachedReason||"",key:"bookmark:"+a.id});
    return rows.sort((a,b)=>a.index-b.index);
  }
  function goToParagraph(index){
    ready();const range=paragraphOffset(committed,index);
    if(coWriting){
      selectedIdx=index;render();const target=manuscriptLines.querySelector('[data-paragraph-index="'+index+'"]');
      if(!target)throw Error("The selected paragraph is not visible.");target.focus({preventScroll:true});target.scrollIntoView({block:"center",inline:"nearest"});
    }else{
      if(soloTextarea.value!==committed.join("\n"))throw Error("The writing surface is not synchronized.");
      soloTextarea.focus({preventScroll:true});soloTextarea.setSelectionRange(range.start,range.end);
      // Caret selection is exact; approximate viewport movement for wrapped text.
      const max=Math.max(0,soloTextarea.scrollHeight-soloTextarea.clientHeight);
      soloTextarea.scrollTop=committed.length>1?max*index/(committed.length-1):0;
    }
  }
  function navigation(){
    ready();const d=dialog("Manuscript navigator"),source=documentId;
    const basis=committed.slice(),getRows=()=>outlineEntries(committed,chapters,syncManuscriptFormat(),typeof window.twoiSceneNavigation==="function"?window.twoiSceneNavigation():[]);
    const entries=getRows(),stamp=JSON.stringify(entries);
    el("p","Browse committed chapters, styled headings, bookmarks and scene dossiers. Opening a passage does not change the active AI scene or your manuscript.",d);
    const q=el("input",null,d);q.type="search";q.placeholder="Find a chapter, heading or scene";q.setAttribute("aria-label","Search manuscript outline");
    const list=el("div",null,d),status=textStatus(d);
    function verify(){ready();if(source!==documentId||basis.length!==committed.length||basis.some((s,i)=>s!==committed[i])||stamp!==JSON.stringify(getRows()))throw Error("The manuscript outline changed. Reopen the navigator.");}
    function jump(index){try{verify();paragraphOffset(committed,index);d.close();goToParagraph(index);}catch(e){status.textContent=e.message;}}
    function refresh(){list.replaceChildren();const term=q.value.toLowerCase().trim();const matches=entries.filter(r=>!term||(r.kind+" "+r.title).toLowerCase().includes(term));status.textContent=matches.length+" outline entries";for(const r of matches){const b=button(list,r.kind+" · "+r.title+" · paragraph "+(r.index+1),()=>jump(r.index));b.style.display="block";b.style.whiteSpace="normal";b.style.minHeight="42px";b.disabled=!!r.reason;if(r.reason)el("p",r.reason,list);}}
    q.addEventListener("input",refresh);
    const number=el("input",null,d);number.type="number";number.min="1";number.max=String(committed.length);number.step="1";number.placeholder="Paragraph number";number.setAttribute("aria-label","Paragraph number");button(d,"Go to paragraph",()=>jump(Number(number.value)-1));
    button(d,"Close",()=>d.close());refresh();d.showModal();q.focus();
  }
  function annotate(kind){
    ready();const indices=stableSelection(),index=indices[0],source=documentId,basis=committed.slice();paragraphOffset(basis,index);
    const d=dialog(kind==="bookmark"?"Add bookmark":"Add editorial comment");
    el("p","Private document annotation · paragraph "+(index+1)+(indices.length>1?" (first selected paragraph)":"")+". No manuscript words will change.",d);
    const quote=el("p",basis[index]||"(Blank paragraph)",d);quote.style.whiteSpace="pre-wrap";quote.style.overflowWrap="anywhere";quote.style.maxHeight="18dvh";quote.style.overflow="auto";
    const name=el("input",null);name.maxLength=160;name.value=kind==="bookmark"?"": "Editorial comment";field(d,"Label",name);
    const body=el("textarea",null);body.rows=4;body.maxLength=8000;field(d,kind==="bookmark"?"Optional note":"Comment",body);
    const status=textStatus(d);
    button(d,"Save annotation",()=>{try{
      ready();if(source!==documentId||basis.length!==committed.length||basis.some((s,i)=>s!==committed[i]))throw Error("Manuscript changed. Select the intended passage again.");
      const next=C.clone(syncManuscriptFormat());C.addAnnotation(next,committed,{id:uuid(),kind,label:name.value,body:body.value,index,createdAt:new Date().toISOString()});
      snapshot();manuscriptFormat=next;update();d.close();
    }catch(e){status.textContent=e.message;}});
    button(d,"Cancel",()=>d.close());d.showModal();(kind==="bookmark"?name:body).focus();
  }
  function annotationManager(){
    ready();const source=documentId,basis=committed.slice(),d=dialog("Bookmarks and comments");
    el("p","Annotations are private manuscript metadata, included in native saves and versions but excluded from plain-text and formatted manuscript exports. Detached notes retain their original source anchor.",d);
    const q=el("input",null,d);q.type="search";q.placeholder="Search annotation labels and notes";q.setAttribute("aria-label","Search annotations");
    const archived=el("input",null);archived.type="checkbox";field(d,"Show archived annotations",archived);
    const list=el("div",null,d),status=textStatus(d);
    function verify(){ready();if(source!==documentId||basis.length!==committed.length||basis.some((s,i)=>s!==committed[i]))throw Error("Manuscript changed. Reopen annotations.");}
    function change(id,action,index){try{verify();const next=C.clone(syncManuscriptFormat());C.changeAnnotation(next,committed,id,action,index);snapshot();manuscriptFormat=next;update();refresh();}catch(e){status.textContent=e.message;}}
    function refresh(){
      list.replaceChildren();const term=q.value.toLowerCase().trim(),items=(syncManuscriptFormat().annotations||[]).filter(a=>(archived.checked||a.status!=="archived")&&(!term||(a.label+" "+a.body).toLowerCase().includes(term)));
      status.textContent=items.length+" matching annotation(s)";
      for(const a of items){const row=el("section",null,list);row.style.borderTop="1px solid #ad9b83";el("strong",(a.kind==="bookmark"?"Bookmark":"Comment")+" · "+a.label+" · "+a.status,row);
        const note=el("p",a.body||"(No note)",row);note.style.whiteSpace="pre-wrap";note.style.overflowWrap="anywhere";
        const anchor=el("p",(a.detachedReason?"Detached from paragraph ":"Paragraph ")+(a.index+1)+": "+a.text,row);anchor.style.whiteSpace="pre-wrap";anchor.style.overflowWrap="anywhere";anchor.style.maxHeight="16dvh";anchor.style.overflow="auto";
        if(a.detachedReason)el("p",a.detachedReason,row);
        if(a.priorAnchors.length)el("p",a.priorAnchors.length+" earlier anchor(s) retained in native document.",row);
        if(a.status==="archived"){button(row,"Restore annotation",()=>change(a.id,"restore"));continue;}
        if(!a.detachedReason)button(row,"Go to paragraph",()=>{verify();const current=(syncManuscriptFormat().annotations||[]).find(x=>x.id===a.id);if(!current||current.detachedReason||committed[current.index]!==current.text)throw Error("Annotation anchor changed.");d.close();goToParagraph(current.index);});
        else button(row,"Reattach…",()=>{verify();const raw=prompt("Enter the intended committed paragraph number (1–"+committed.length+")",String(Math.min(a.index+1,committed.length)));if(raw===null)return;const index=Number(raw)-1;paragraphOffset(committed,index);if(confirm("Reattach to paragraph "+(index+1)+": "+committed[index].slice(0,200)+"? Original anchor is retained."))change(a.id,"reattach",index);});
        if(a.kind==="comment")button(row,a.status==="resolved"?"Reopen comment":"Resolve comment",()=>change(a.id,a.status==="resolved"?"reopen":"resolve"));
        button(row,"Archive",()=>{if(confirm("Archive this annotation? It remains recoverable."))change(a.id,"archive");});
      }
    }
    q.addEventListener("input",refresh);archived.addEventListener("change",refresh);button(d,"Close",()=>d.close());refresh();d.showModal();q.focus();
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
  commandMenu("File",[["New",go("hmNewDoc")],["Open .2i",go("hmOpenDoc")],["My manuscripts",go("shelfBtn")],["Save",go("saveBtn",()=>!initializing&&editingIdx===null)],["Save a copy (.2i)",go("hmSaveAs")],["Export Markdown (includes presented draft)",go("exportBtn"),"markdown md"],["Export committed text only",exportCommitted,"plain txt manuscript privacy"],["Export formatted HTML",conditional(()=>downloadFile(safeName()+".html",output(),"text/html"),idle)],["Export screenplay FDX exchange",conditional(fdxExport,()=>idle()&&scriptProfile()),"final draft screenplay interchange"],["Print committed manuscript…",conditional(preview,idle),"print page paper pdf"],["Restore autosave",go("hmRestoreAutosave")],["Rename",go("hmRenameDoc")]]);
  commandMenu("Edit",[["Undo manuscript operation",conditional(()=>undo(),()=>idle()&&undoStack.length>0)],["Redo manuscript operation",conditional(()=>redo(),()=>idle()&&redoStack.length>0)],["Find & replace",go("hmFindReplace")]]);
  commandMenu("Insert",[["New chapter",go("newChapterBtn")],["Add bookmark",conditional(()=>annotate("bookmark"),idle)],["Add editorial comment",conditional(()=>annotate("comment"),idle)]]);
  commandMenu("Format",[["Document type / script presets",templates],["Paragraph style, alignment, indent…",paragraph],["Formatting recovery",unmapped]]);
  commandMenu("Layout",[["Page setup",page],["Formatted preview",preview]]);
  commandMenu("References",[["Browse or search references",referenceArchive,"research notes archive"],["Add reference",go("addRefBtn")]]);
  commandMenu("Manuscript",[["Chapter and scene navigator",conditional(navigation,idle),"outline go to paragraph headings"],["Scene intelligence",go("narrativeOpen")],["Dialogue and scene review",conditional(dialogueReview,()=>idle()&&scriptProfile()),"character dialogue tuner script breakdown"],["New chapter",go("newChapterBtn")],["Generate draft",go("genBtn",()=>collabIdle()&&llmOk()&&!buffer.length)],["Commit presented draft",go("approveBtn",()=>collabIdle()&&buffer.length>0)],["Archive presented draft",go("narrativeArchiveDraft",collabIdle)]]);
  commandMenu("Review",[["Revision history",go("narrativeHistory",()=>idle()&&networked&&serverReady)],["Story versions",go("twoiVersionManage",()=>idle()&&networked&&serverReady)],["Creative contribution records",go("narrativeContribution",idle),"authorship provenance evidence disclosure"],["Private creative session",go("narrativeSession",idle),"recording capture session milestone"],["Bookmarks and comments",conditional(annotationManager,idle),"resolve archive reattach editorial annotations"],["Lock scene",go("lockSceneBtn")],["Lock all",go("lockAllBtn")],["Unlock",go("unlockBtn")]]);
  const present=mode=>()=>window.twoiSetPresentation(mode);
  const presentations=typeof window.twoiSetPresentation==="function"?[["Standard document view",present("standard")],["Notebook view",present("notebook")],...(window.twoiCanPresent("typewriter")?[["Typewriter view",present("typewriter")]]:[])]:[];
  commandMenu("View",[...presentations,["Write / Collab",go("modeBadge")],["Toggle sidebar",go("sidebarToggle")],["Zoom manuscript in",()=>adjustZoom("manuscript",1)],["Zoom manuscript out",()=>adjustZoom("manuscript",-1)],["Formatted preview",preview]]);
  commandMenu("Tools",[["Word and character count",stats],["Read / pause presented draft",go("playBtn",()=>coWriting&&(playing||(!generating&&!chatSending&&buffer.some(s=>s.trim()))))],["Stop reading / generation",go("stopBtn",()=>playing||generating)],["Model settings",go("hmLLMSettings")]]);
  commandMenu("Studio",[["Inbox",go("twoiNotesInbox",()=>!initializing&&networked&&serverReady)],["Write note",go("twoiWriteNote",()=>!initializing&&networked&&serverReady)],["Place sticky note",go("twoiPlaceNote",()=>!initializing&&networked&&serverReady)]]);
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
    const available=commandAvailable;
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
  // Narrow screens keep the menus on one swipeable row (format-menu.css). Mark which edge has more menus beyond it
  // so the style sheet can fade that edge; a cut-off menu must never look like the end of the row.
  const markEdges=()=>{const hidden=menu.scrollWidth-menu.clientWidth;menu.classList.toggle("more-before",menu.scrollLeft>2);menu.classList.toggle("more-after",hidden-menu.scrollLeft>2);};
  menu.addEventListener("scroll",markEdges,{passive:true});window.addEventListener("resize",markEdges);
  if(typeof ResizeObserver==="function")new ResizeObserver(markEdges).observe(menu);
  markEdges();
})();
