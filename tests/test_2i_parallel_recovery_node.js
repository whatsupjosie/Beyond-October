const {test}=require("node:test");const assert=require("node:assert/strict");const fs=require("node:fs");const path=require("node:path");
const src=fs.readFileSync(path.join(__dirname,"../2i/2i-assets/reach.js"),"utf8");const block=src.slice(src.indexOf("/* Editor recovery selection"),src.indexOf("/* End editor recovery selection. */"));
const {uniqueEditorRecoveries:U,chooseEditorRecovery:C}=Function(block+"\nreturn {uniqueEditorRecoveries,chooseEditorRecovery};")();
const r=(id,writer,dirty,revision,ts)=>({id,writer,dirty,revision,ts,state:{committed:[writer]}});
test("dirty buffers for each editor remain separate",()=>{const a=r("v","a",true,1,1),b=r("v","b",true,1,2);assert.equal(U([a,b]).length,2);assert.equal(C({documentId:"v",explicit:false,records:[a,b]}),null);assert.equal(C({documentId:"v",previousWriter:"a",explicit:true,records:[a,b]}).writer,"a");});
test("new version tab is not another editor's draft",()=>{const a=r("v","a",true,1,10),b=r("v","saved",false,2,8);assert.equal(C({documentId:"v",explicit:true,records:[a,b]}).writer,"saved");assert.equal(C({documentId:"other",explicit:true,records:[a,b]}),null);});
test("legacy duplicated record and stale clean record",()=>{const a=r("v",null,true,1,1);assert.equal(U([a,{...a}]).length,1);assert.equal(U([r("v","old",false,1,100),r("v","new",false,2,1)])[0].revision,2);});
