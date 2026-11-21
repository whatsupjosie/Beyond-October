/* Bridge Claude's keyboard event contract to 2i's existing real editor.
 * No parallel manuscript buffer: native edit commands trigger the same input,
 * protected-line, undo, autosave and recovery paths as physical typing.
 */
'use strict';
const TwoiTypewriterKeys = (() => {
  function command(detail) {
    if(!detail || typeof detail!=='object')return null;
    if(detail.char==='SHIFT'||detail.char==='BLANK')return null;
    if(detail.char==='BACKSPACE')return {kind:'backspace'};
    if(detail.char==='RETURN')return {kind:'insert',text:'\n'};
    if(typeof detail.text!=='string'||!detail.text||detail.text.length>16)return null;
    if(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(detail.text))return null;
    return {kind:'insert',text:detail.text};
  }
  function previousGrapheme(text,position) {
    if(position<=0)return 0;
    if(typeof Intl!=='undefined'&&typeof Intl.Segmenter==='function'){
      const segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
      let last=0;
      for(const item of segmenter.segment(text.slice(0,position)))last=item.index;
      return last;
    }
    const end=text.charCodeAt(position-1);
    return position>=2&&end>=0xdc00&&end<=0xdfff
      &&text.charCodeAt(position-2)>=0xd800&&text.charCodeAt(position-2)<=0xdbff
      ? position-2:position-1;
  }
  function write(doc,target,detail) {
    const instruction=command(detail);
    if(!instruction||!target||target.tagName!=='TEXTAREA'||target.readOnly||target.disabled||typeof doc.execCommand!=='function')return false;
    // An iframe may have focus; preserve the real textarea's caret/selection.
    let start=target.selectionStart,end=target.selectionEnd;
    if(!Number.isInteger(start)||!Number.isInteger(end))return false;
    if(instruction.kind==='backspace'&&start===end){
      if(start===0)return true; // Backspace at start makes no change.
      start=previousGrapheme(target.value,start);
    }
    target.focus({preventScroll:true});
    target.setSelectionRange(start,end);
    if(instruction.kind==='backspace')return doc.execCommand('delete',false,null)===true;
    return doc.execCommand('insertText',false,instruction.text)===true;
  }
  return {command,write};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=TwoiTypewriterKeys;
