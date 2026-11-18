'use strict';
/**
 * Zero-install structural wiring checks for the served PubCast → 2i → typewriter
 * entry points. These do not claim that a live HTTP server or persistence works.
 *
 * node --test tests/test_2i_wiring_contract_node.js
 */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..');
const read=(p)=>fs.readFileSync(path.join(ROOT,p),'utf8');
const page=read('2i/writers-room-v22.html');
const machine=read('static/typewriter_console.html');
const main=read('main.py');
const studio=read('2i/2i-assets/studio-desk.js');
const work=read('2i/2i-assets/file-workspace.js');

function relativeAsset(route,src) {
  const url=new URL(src,'https://localhost'+route);
  assert.equal(url.origin,'https://localhost','No external script or stylesheet: '+src);
  if(url.pathname.startsWith('/static/'))return 'static/'+url.pathname.slice('/static/'.length);
  if(url.pathname.startsWith('/2i-assets/'))return '2i/2i-assets/'+url.pathname.slice('/2i-assets/'.length);
  return null;
}
function assetRefs(html) {
  return [...html.matchAll(/<(?:script|link)\b[^>]*?(?:src|href)=["']([^"']+)["'][^>]*>/gi)].map(x=>x[1]).filter(x=>/\.(?:js|css)(?:[?#]|$)/.test(x));
}
function scripts(html) {
  return [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/gi)]
    .map(m=>m[1]).filter(x=>x.trim());
}
test('combined PubCast server retains Fable's critical lifecycle and security wiring',()=>{
  // Regression against an earlier integration which copied Claude's older
  // main.py, dropping Fable's camera pool, Blackbox and upload protections.
  for(const required of [
    'create_studio25d_recording_router',
    'create_camera_pool_router',
    'GuestSessionGuardMiddleware',
    'GuestAdmission',
    'start_chat_replay',
    'stop_chat_replay',
    'blackbox_logger=internal_audit_logger',
    'MAX_FILE_BYTES = 5 * 1024 * 1024',
    'app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")'
  ])assert.ok(main.includes(required),'Missing Fable server integration: '+required);
  assert.match(main,/@app\.get\("\/typewriter-console"/);
});
test('PubCast hosts both real routes and both static asset directories',()=>{
  assert.match(main,/@app\.get\("\/writers-room"/);
  assert.match(main,/@app\.get\("\/typewriter-console"/);
  assert.match(main,/app\.mount\("\/2i-assets"/);
  assert.match(main,/app\.mount\("\/static"/);
});
test('every declared JavaScript and CSS dependency exists at its served path',()=>{
  for(const [route,html] of [['/writers-room',page],['/typewriter-console',machine]]) {
    const assets=assetRefs(html);
    assert.ok(assets.length>=4,'Expected actual dependencies on '+route);
    for(const src of assets) {
      const relative=relativeAsset(route,src);
      assert.ok(relative,'Unknown asset mapping: '+src);
      assert.ok(fs.existsSync(path.join(ROOT,relative)),src+' must be present in Git tree');
    }
  }
});
test('inline and external classic scripts parse before startup',()=>{
  for(const [route,html] of [['/writers-room',page],['/typewriter-console',machine]]) {
    for(const body of scripts(html))new vm.Script(body,{filename:route+' inline'});
    for(const src of assetRefs(html).filter(x=>/\.js(?:[?#]|$)/.test(x))) {
      const file=relativeAsset(route,src);
      new vm.Script(read(file),{filename:file});
    }
  }
});
test('2i startup loads its prerequisites before the manuscript and typewriter adapters',()=>{
  const deps=assetRefs(page);
  const find=name=>deps.findIndex(x=>x.endsWith(name));
  for(const name of ['format-core.js','narrative-core.js','narrative-room.js',
                     'reach.js','typewriter-input.js','studio-desk.js','file-workspace.js'])
    assert.ok(find(name)>=0,'Missing startup dependency '+name);
  assert.ok(find('format-core.js')<find('narrative-core.js'));
  assert.ok(find('narrative-core.js')<find('narrative-room.js'));
  assert.ok(find('narrative-room.js')<find('reach.js'));
  assert.ok(find('reach.js')<find('studio-desk.js'));
  assert.ok(find('typewriter-input.js')<find('studio-desk.js'));
  assert.ok(find('studio-desk.js')<find('file-workspace.js'));
});
test('2i page has no duplicate static control IDs',()=>{
  const ids=[...page.matchAll(/\bid=["']([^"']+)["']/g)].map(x=>x[1]);
  assert.ok(ids.length>=100);
  assert.equal(new Set(ids).size,ids.length,'Duplicate static id blocks handler discovery');
});
test('embedded typewriter console has original art and mapped keys',()=>{
  const manifest=JSON.parse(read('static/typewriter_console_hotspot_manifest.json'));
  assert.ok(fs.existsSync(path.join(ROOT,relativeAsset('/typewriter-console',manifest.image.clean_path))));
  assert.ok(manifest.hotspots.length>=45);
  assert.equal(new Set(manifest.hotspots.map(x=>x.id)).size,manifest.hotspots.length);
  assert.match(studio,/\/typewriter-console\?embedded=2i/);
  assert.match(studio,/event\.source!==typewriter\.contentWindow/);
  assert.match(studio,/event\.origin!==location\.origin/);
});
test('Foresight file-tray presentation is selectable without stealing its save adapter',()=>{
  assert.match(studio,/const filePresentation=!!reachFileMode/);
  assert.match(studio,/id="twoiFilePresentation"|chooser\.id="twoiFilePresentation"/);
  assert.match(studio,/chooser\.onchange=\(\)=>window\.twoiSetPresentation\(chooser\.value\)/);
  assert.match(work,/saveDocument=\(\)=>session\.save\(\)/);
  assert.match(work,/const originalMarkDirty=markDirty/);
  assert.match(work,/session\.flush\(\)/);
});
test('Reach awaits authenticated readiness before Foresight file mounting',()=>{
  const reach=read('2i/2i-assets/reach.js');
  assert.match(reach,/window\.reachStarted=startReach\(\)/);
  assert.match(work,/await window\.reachStarted/);
  assert.match(work,/ForesightFiles\.mount\(/);
});
