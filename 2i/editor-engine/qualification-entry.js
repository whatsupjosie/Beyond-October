import { createDocxEditor, loadFonts } from '@docx-editor.dev/core';
window.qualifyEngine = async function(bytes) {
 const fonts = await loadFonts({sources:[{url:'/local-font.ttf',family:'Courier New',weight:400,style:'normal'}]});
 if(fonts.failures.length) throw Error('Local font did not load');
 const editor=createDocxEditor({container:document.getElementById('editor'),document:new Uint8Array(bytes),fonts});
 window.editor=editor; return true;
};
