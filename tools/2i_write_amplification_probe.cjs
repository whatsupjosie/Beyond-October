/* Explicit adversarial diagnostic. Not part of the ordinary passing test suite.
 *
 * Run: node tools/2i_write_amplification_probe.cjs
 *
 * Intentionally exits nonzero until rapid edits coalesce into a bounded
 * number of durable record operations. This probes the actual
 * ForesightFiles.persist()/persistRaw() source with a controlled record stub;
 * it does NOT prove physical disk writes or complete host behavior.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/foresight_files.js'), 'utf8');
const first = source.indexOf('function snapshot()');
const last = source.indexOf('function dirty()', first);
if (first < 0 || last < first) throw Error('Foresight persistence source moved; update probe');
const actual = source.slice(first, last);
const calls = [];
const ctx = {
  value: {id:'adversarial-doc',draft:'',title:'Stress probe',twoiState:{},revision:0},
  editor: {value:''},
  richMode:false, richEditor:null,
  changed:false,richMetadataDirty:false,opening:false,richOpening:false,
  writing:0,saving:Promise.resolve(),serial:0,diagnosticVersion:0,
  localSaveError:false,handle:null,timer:null,queuedPlain:null,exitWritten:false,
  clearTimeout(){},say(){},
  structuredClone,Date,
  options:{
    getText:()=>ctx.editor.value,
    getTitle:()=>ctx.value.title,
    getState:()=>({committed:[ctx.editor.value]})
  },
  async record(id,value,revision) {
    calls.push({id,text:value.draft,revision});
    return {revision:revision+1};
  }
};
vm.createContext(ctx);
vm.runInContext(actual+'\nthis.persistUnderTest=persist;',ctx,{filename:'static/foresight_files.js (extracted)'});

(async()=>{
  const count = 40, queued = [];
  for(let i=0;i<count;i++){
    ctx.editor.value += 'x';
    ctx.serial++;
    ctx.changed = true;
    // This is what the file adapter currently asks the session to do
    // after EACH edit, in addition to Foresight's own debounce.
    queued.push(ctx.persistUnderTest());
  }
  await Promise.all(queued);
  const identical = calls.every(c=>c.text===ctx.editor.value);
  const maxWrites = 3;
  console.log(JSON.stringify({
    kind:'source-driven diagnostic, mock record store',
    edits:count,queuedFlushes:queued.length,recordCalls:calls.length,
    identicalFinalSnapshots:identical,finalRevision:ctx.value.revision,
    budget:maxWrites
  },null,2));
  if(calls.length>maxWrites){
    console.error('FAIL (expected until fixed): edit burst caused excessive persisted record operations');
    process.exitCode=1;
  }else if(!identical||ctx.value.revision!==calls.length){
    console.error('FAIL: inconsistent revision or snapshot result');
    process.exitCode=1;
  }else console.log('PASS: burst coalesced without losing latest manuscript');
})().catch(error=>{console.error(error);process.exitCode=1;});
