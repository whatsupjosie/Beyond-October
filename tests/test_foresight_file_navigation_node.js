'use strict';
// Exercising the actual file navigation helper without launching a browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/file-workspace.js'),'utf8');
const start=source.indexOf('function filePage(fileId){');
const stop=source.indexOf('// File-mode drafts have their own stable IDs;',start);
assert.ok(start>0 && stop>start,'The hosted file navigation helper must exist');
const helper=source.slice(start,stop);
const ctx=vm.createContext({
  location:{origin:'http://127.0.0.1:8000'},
  URL,URLSearchParams,sessionNonce:'a-session-id'
});
vm.runInContext(helper+';globalThis.nextFile=filePage;',ctx);
const next=ctx.nextFile('a-fresh-file');
assert.equal(next,'/writers-room?file=a-fresh-file&foresightSession=a-session-id');
const detached=vm.createContext({location:{origin:'http://127.0.0.1:8000'},URL,sessionNonce:null});
vm.runInContext(helper+';globalThis.nextFile=filePage;',detached);
assert.equal(detached.nextFile('another-document'),'/writers-room?file=another-document');
const provider=fs.readFileSync(path.join(__dirname,'../static/foresight_programs.js'),'utf8');
assert.match(provider,/c\.appReady=false;c\.frameLoaded=false;c\.activityRequest=null;\s*c\.readyPromise=new Promise/,
 'After changing documents, the host must require fresh readiness');
assert.match(source,/location\.assign\(filePage\(next\)\)/,
 'File open must preserve the hosted frame session identity');
console.log('PASS file navigation retains iframe identity and invalidates prior Ready state');
