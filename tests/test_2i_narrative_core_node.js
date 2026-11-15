/* Run: node --test tests/test_2i_narrative_core_node.js */
const {test}=require("node:test");
const assert=require("node:assert/strict");
const C=require("../2i/2i-assets/narrative-core.js");
const S=C.scene("s1","A scene",2,null,{purpose:"Reveal trust",information:"Audience | the letter | unaware | suspects"});
test("dossier roundtrip and invalid schema",()=>{const s=C.fresh();s.scenes.push(S);s.activeSceneId="s1";assert.deepEqual(C.restore(s),s);assert.throws(()=>C.scene("","",0,null));assert.throws(()=>C.disclosure("Audience | secret | knows"));});
test("bound presentation and preserve every character",()=>{for(const text of [Array.from({length:750},(_,i)=>"word"+i+" ").join(""),"Line.\n".repeat(121)]){const p=C.partition(text);assert(C.fits(p.presented));assert.equal(p.presented+p.latent,text);assert(p.latent.length>0)}assert.throws(()=>C.partition("x".repeat(4000)));});
test("full section, prior chapter and confirmed context",()=>{const c=C.context({lines:["prior0","prior1","first","last"],chapters:[{startLine:0},{startLine:2}],active:S,decisions:["changed"]});assert.equal(c.previous,"prior0\nprior1");assert.equal(c.section,"first\nlast");assert.equal(c.knowledge[0].intended,"suspects");assert(C.prompt(c,"draft")[0].content.includes("changed"));assert.throws(()=>C.prompt({section:"x".repeat(81000)},"draft"));});
test("invalid and archived hidden responses",()=>{assert.throws(()=>C.parseDraft("not JSON"));const p=C.parseDraft(JSON.stringify({draft:"word ".repeat(800),latent:"later",notes:"observation"}));assert(C.fits(p.presented));assert(p.latent.endsWith("later"));const s=C.fresh();C.archive(s,"abandoned",p.latent,{scene:"s1"});assert.equal(s.archive[0].text,p.latent);});
test("past scene is not append target",()=>assert.equal(C.context({lines:["a","b"],chapters:[],active:C.scene("s","Earlier",0,1)}).endsAtManuscriptEnd,false));
