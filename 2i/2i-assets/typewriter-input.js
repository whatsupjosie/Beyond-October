/* 2i adapter for Claude's pubcast:key console contract. The live editor owns all text. */
(function(root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.TwoiTypewriterInput = api;
})(typeof window !== 'undefined' ? window : null, function() {
  'use strict';
  function keyAction(key) {
    if (!key || typeof key !== 'object') return null;
    if (key.char === 'SHIFT' || key.char === 'BLANK') return null;
    if (key.char === 'BACKSPACE') return {inputType:'deleteContentBackward', text:''};
    if (key.char === 'RETURN') return {inputType:'insertLineBreak', text:'\n'};
    if (key.char === 'SPACE') return {inputType:'insertText', text:' '};
    // Text comes from the existing touch/keyboard engine, not from the key label.
    const text = key.text;
    if (typeof text !== 'string' || text.length === 0 || text.length > 8 || /[\r\n\x00-\x1f]/.test(text)) return null;
    return {inputType:'insertText', text};
  }
  function previousGrapheme(text, at) {
    if (at <= 0) return 0;
    const head = text.slice(0,at);
    if (typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function') {
      let start = 0;
      for (const part of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(head)) start = part.index;
      return start;
    }
    const last = Array.from(head).at(-1);
    return at - (last ? last.length : 0);
  }
  function apply(editor, key, options = {}) {
    const action = keyAction(key);
    if (!action || !editor || typeof editor.setRangeText !== 'function' || editor.disabled || editor.readOnly)
      return {applied:false};
    const doc = options.document || editor.ownerDocument;
    const value = editor.value;
    let start = options.selection ? options.selection.start : editor.selectionStart;
    let end = options.selection ? options.selection.end : editor.selectionEnd;
    start = Math.max(0,Math.min(value.length,Number.isInteger(start)?start:value.length));
    end = Math.max(start,Math.min(value.length,Number.isInteger(end)?end:start));
    if (action.inputType === 'deleteContentBackward' && start === end) start = previousGrapheme(value,start);
    if (start === end && !action.text) return {applied:false};
    const next = value.slice(0,start)+action.text+value.slice(end);
    try { editor.focus({preventScroll:true}); } catch (_) { editor.focus(); }
    editor.setSelectionRange(start,end);
    // Chromium's execCommand('insertText') may not dispatch a cancelable
    // beforeinput event. Emit one before either insertion path so a protected
    // editor can decline the change without relying on reverting it afterward.
    const win = doc && doc.defaultView;
    const Input = win && (win.InputEvent || win.Event);
    if (Input && typeof editor.dispatchEvent === 'function') {
      const pre = new Input('beforeinput',{bubbles:true,cancelable:true,inputType:action.inputType,data:action.text});
      if (!editor.dispatchEvent(pre)) return {applied:false};
    }
    let native = false;
    if (doc && typeof doc.execCommand === 'function') {
      try { native = !!doc.execCommand('insertText',false,action.text); } catch (_) { /* not supported */ }
    }
    if (!native && editor.value === value) {
      editor.setRangeText(action.text,start,end,'end');
      if (Input) editor.dispatchEvent(new Input('input',{bubbles:true,inputType:action.inputType,data:action.text}));
    }
    return {applied:editor.value===next, start:editor.selectionStart, end:editor.selectionEnd};
  }
  return {keyAction,previousGrapheme,apply};
});
