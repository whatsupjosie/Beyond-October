import {readRecoveryRecord, writeRecoveryRecord} from './recovery.mjs';
import {saveLookFile} from './files.mjs';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {parseAvatar, dispose, prepareSurface, composeSurface, decodeLayer, surfacePoint} from './model.mjs';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {TEXTURE_SIZE, LAYERS, LIMITS, History, TileEdit, strokePoints, softenPixels, checkProjectSize, validateProject, bytesToBase64, base64ToBytes} from './core.mjs';

const $ = id => document.getElementById(id);
const history = new History();
let renderer, scene, camera, controls, avatar, animations = [], source, source64, targets = [], active = 0, layerIndex = 5;
let tool = 'lipstick', edit = null, previous = null, pointer = null, busy = false, dirty = false, comparing = false;
let db = null, recoveryTimer, generation = 0, recoveryWrites = Promise.resolve();
let graphicsReady = false, pendingFrame = null, recoveryRevision = 0;
const ndc = new THREE.Vector2();
const viewport = $('viewport');

function status(message, error = false) { $('status').textContent = message; $('status').dataset.error = String(error); }
function canvas() { const c = document.createElement('canvas'); c.width = c.height = TEXTURE_SIZE; return c; }
function context(c) { return c.getContext('2d', {willReadFrequently: true}); }
function download(blob, name) {
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
}
function safeName() { return ($('avatar-name').textContent || 'My look').replace(/[^\p{L}\p{N}_ -]/gu, '').slice(0, 80) || 'My look'; }
function markChanged() { dirty = true; updateControls(); scheduleRecovery(); }
function updateControls() {
  const loaded = !!avatar && graphicsReady;
  for (const id of ['export', 'frame', 'face', 'compare', 'snapshot']) $(id).disabled = busy || !loaded;
  $('save').disabled = busy || !avatar;
  const paintable = loaded && targets.length > 0 && !busy && !comparing;
  for (const id of ['surface', 'layer', 'layer-opacity', 'visible', 'brushes', 'clear']) $(id).disabled = !paintable;
  $('undo').disabled = busy || !graphicsReady || comparing || !history.past.length;
  $('redo').disabled = busy || !graphicsReady || comparing || !history.future.length;
  for (const id of ['avatar-file', 'project-file', 'welcome-file', 'recover']) $(id).disabled = busy || !graphicsReady;
  $('history-info').textContent = `${history.past.length} undo / ${history.future.length} redo · ${(history.bytes / 1048576).toFixed(1)} MiB`;
}
function run(action, needsGraphics = true) {
  return async (...args) => {
    if (busy || (needsGraphics && !graphicsReady)) return;
    finishStroke(); busy = true; updateControls();
    try { await action(...args); } catch (error) { if (error.name === 'AbortError') status('Save cancelled. Your work is still open.');
      else { console.error(error); status(error.message || 'The operation failed. Your current work is still open.', true); } }
    finally { busy = false; updateControls(); if (avatar && !graphicsReady) status('Graphics unavailable. Save your look before reloading.', true); }
  };
}

function initRenderer() {
  renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  scene = new THREE.Scene(); scene.background = new THREE.Color($('backdrop').value);
  camera = new THREE.PerspectiveCamera(35, 1, 0.001, 10000); camera.position.set(0, 1, 4);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = false;
  controls.enableRotate = false; controls.enablePan = false;
  controls.minDistance = .01; controls.maxDistance = 1000;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8b7b92, 2.0));
  const key = new THREE.DirectionalLight(0xffffff, 2.5); key.name = 'mirror-key'; key.position.set(3, 4, 5); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 1.5); fill.position.set(-3, 1, 2); scene.add(fill);
  renderer.domElement.setAttribute("aria-label", "Avatar painting surface");
  renderer.domElement.tabIndex = 0;
  viewport.append(renderer.domElement);
  const resize = () => { const w = viewport.clientWidth, h = viewport.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render(); };
  new ResizeObserver(resize).observe(viewport);
  controls.addEventListener('change', render);
  renderer.domElement.addEventListener('webglcontextlost', event => { event.preventDefault(); finishStroke(); graphicsReady = false; updateControls(); status('Graphics context lost. Reload and recover your local look.', true); });
  renderer.domElement.addEventListener('webglcontextrestored', () => { graphicsReady = true; for (const target of targets) if (target.texture) target.texture.needsUpdate = true; updateControls(); render(); status('Graphics restored.'); });
  graphicsReady = true; setupPointers(); resize(); updateControls();
}
function renderNow() { if (graphicsReady && renderer && scene && camera) renderer.render(scene, camera); }
function render() {
  if (pendingFrame !== null || !graphicsReady) return;
  pendingFrame = requestAnimationFrame(() => { pendingFrame = null; renderNow(); });
}
function frame(close = false) {
  if (!avatar || !renderer) return;
  const box = new THREE.Box3().setFromObject(avatar), center = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  let height = size.y;
  if (close) {
    const head = avatar.getObjectByProperty('isBone', true);
    let headBone;
    avatar.traverse(node => { if (node.isBone && /^(head|mixamorighead|head_?joint)$/i.test(node.name.replace(/[: ]/g, ''))) headBone = node; });
    if (!headBone && !head) status('No head bone found; framing the upper avatar.');
    if (headBone) headBone.getWorldPosition(center); else center.y = box.max.y - size.y * .12;
    height = size.y * .28;
  }
  const distance = Math.max(height, close ? size.x * .4 / camera.aspect : size.x / camera.aspect) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.2;
  controls.target.copy(center); camera.position.copy(center).add(new THREE.Vector3(0, 0, Math.max(distance, .01)));
  camera.near = Math.max(distance / 1000, .0001); camera.far = Math.max(distance * 100, 100);
  camera.updateProjectionMatrix(); controls.update(); render();
}

function install(parsed, bytes, name) {
  if (avatar) { scene.remove(avatar); dispose(avatar, targets); }
  avatar = parsed.root; animations = parsed.animations; targets = parsed.targets; source = bytes; source64 = null; active = 0;
  generation++; clearTimeout(recoveryTimer); history.clear(); comparing = false;
  $('compare').setAttribute('aria-pressed', 'false');
  scene.add(avatar); $('welcome').hidden = true; $('avatar-name').textContent = name;
  $('surface').replaceChildren(...targets.map(t => new Option(t.label, t.id)));
  $('layer').replaceChildren(...LAYERS.map((name, i) => new Option(name, i)));
  $('layer').value = String(layerIndex); syncLayerControls(); frame(); dirty = false; updateControls(); render();
}
async function openAvatar(file) {
  if (!file) return;
  if (dirty && !confirm('Replace this look? Save it first if you want to keep it.')) return;
  if (file.size > LIMITS.source) throw new Error('Choose a GLB smaller than 30 MiB.');
  status('Opening avatar…'); const bytes = await file.arrayBuffer(); const parsed = await parseAvatar(bytes);
  install(parsed, bytes, file.name.replace(/\.glb$/i, ''));
  status(targets.length ? 'Avatar ready. Choose a surface and paint layer.' : 'This avatar has no paintable UV surfaces. You can still inspect and export it.', !targets.length);
  scheduleRecovery();
}
function ensureSurface(target, allTargets = targets) { return prepareSurface(target, allTargets, render); }
function composite(target) { return composeSurface(target, comparing, render); }
function syncLayerControls() {
  const layer = targets[active]?.layers[layerIndex];
  $('layer-opacity').value = String((layer?.opacity ?? 1) * 100); $('visible').checked = layer?.visible ?? true;
}
function changeLayerProperty(property, value) {
  const target = targets[active], layer = target.layers[layerIndex], before = layer[property];
  try { ensureSurface(target); } catch (error) { syncLayerControls(); status(error.message, true); return; }
  if (before === value) return;
  const apply = v => { layer[property] = v; composite(target); syncLayerControls(); };
  apply(value); history.push({bytes: 64, undo: () => apply(before), redo: () => apply(value)}); markChanged();
}
function hitPoint(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  ndc.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
  return surfacePoint(avatar, targets[active], ndc, camera);
}
function stamp(point) {
  const radius = Number($('size').value), flow = Number($('flow').value) / 100, ctx = edit.context;
  edit.capture(point.x, point.y, radius);
  ctx.save();
  try {
    ctx.globalAlpha = flow; ctx.globalCompositeOperation = tool === 'erase' ? 'destination-out' : 'source-over';
    if (tool === 'blend') {
      const x = Math.max(0, Math.floor(point.x - radius)), y = Math.max(0, Math.floor(point.y - radius));
      const w = Math.min(TEXTURE_SIZE - x, Math.ceil(radius * 2)), h = Math.min(TEXTURE_SIZE - y, Math.ceil(radius * 2));
      const image = ctx.getImageData(x, y, w, h);
      softenPixels(image, point.x - x, point.y - y, radius, flow);
      ctx.putImageData(image, x, y); return;
    } else if (tool === 'powder') {
      const gradient = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
      gradient.addColorStop(0, $('color').value); gradient.addColorStop(1, `${$('color').value}00`); ctx.fillStyle = gradient;
    } else ctx.fillStyle = $('color').value;
    ctx.beginPath(); ctx.arc(point.x, point.y, radius, 0, Math.PI * 2); ctx.fill();
  } finally { ctx.restore(); }
}
function finishStroke(cancel = false) {
  if (!edit) return;
  const completed = edit, capturedPointer = pointer;
  edit = null; previous = null; pointer = null;
  try {
    if (cancel) completed.cancel();
    else {
      const command = completed.finish();
      if (command) { history.push(command); markChanged(); }
    }
  } catch (error) {
    try { completed.cancel(); }
    catch { markChanged(); }
    status(`The stroke could not be completed: ${error.message}`, true);
  } finally {
    const el = renderer?.domElement;
    if (capturedPointer !== null && el?.hasPointerCapture(capturedPointer)) el.releasePointerCapture(capturedPointer);
    updateControls();
  }
}

function setupPointers() {
  const el = renderer.domElement;
  // Capture phase makes the paint/orbit decision before OrbitControls receives the event.
  el.addEventListener('pointerdown', event => {
    if (!avatar || busy || comparing || !graphicsReady) return;
    if (pointer !== null) { event.stopImmediatePropagation(); event.preventDefault(); return; }
    controls.enableRotate = tool === 'orbit' || event.altKey; controls.enablePan = controls.enableRotate;
    if (controls.enableRotate) return;
    if (event.button !== 0 || !targets[active]) return;
    event.stopImmediatePropagation(); event.preventDefault();
    try {
      const target = targets[active];
      const point = hitPoint(event); if (!point) { status('Paint the selected surface, or select another surface from the list.'); return; }
      const layer = target.layers[layerIndex];
      if (!layer.visible || layer.opacity === 0) throw new Error('Show this layer and increase its opacity before painting.');
      ensureSurface(target);
      layer.canvas ||= canvas();
      edit = new TileEdit(context(layer.canvas), () => composite(target)); pointer = event.pointerId;
      el.setPointerCapture(pointer); stamp(point); previous = point; composite(target);
    } catch (e) { status(e.message, true); finishStroke(true); }
  }, true);
  el.addEventListener('pointermove', event => {
    if (!edit || event.pointerId !== pointer) return;
    event.stopImmediatePropagation(); event.preventDefault();
    try {
      const point = hitPoint(event); if (!point) { previous = null; return; }
      for (const p of strokePoints(previous, point, Number($('size').value))) stamp(p);
      previous = point; composite(targets[active]);
    } catch (e) { finishStroke(true); status(e.message, true); }
  }, true);
  el.addEventListener('pointerup', event => { if (event.pointerId === pointer) { event.stopImmediatePropagation(); finishStroke(); } }, true);
  el.addEventListener('pointercancel', event => { if (event.pointerId === pointer) finishStroke(true); });
  el.addEventListener('lostpointercapture', event => { if (event.pointerId === pointer) finishStroke(); });
}
function project() {
  source64 ||= bytesToBase64(new Uint8Array(source));
  const value = {format: 'primp', version: 1, name: safeName(), source: source64, targets: []};
  checkProjectSize(value);
  for (const target of targets) if (target.base) {
    const saved = {id: target.id, layers: []}; value.targets.push(saved);
    for (const layer of target.layers) {
      saved.layers.push({visible: layer.visible, opacity: layer.opacity, png: layer.canvas?.toDataURL('image/png') ?? null});
      checkProjectSize(value);
    }
  }
  return value;
}

async function restoreProject(value) {
  validateProject(value);
  if (dirty && !confirm('Replace this look? Save it first if you want to keep it.')) return;
  const bytes = base64ToBytes(value.source).buffer, parsed = await parseAvatar(bytes);
  try {
    for (const saved of value.targets) {
      const target = parsed.targets[saved.id]; if (!target) throw new Error('A saved paint surface is missing from this avatar.');
      ensureSurface(target, parsed.targets);
      for (let i = 0; i < saved.layers.length; i++) { const layer = saved.layers[i]; target.layers[i] = {visible: layer.visible, opacity: layer.opacity, canvas: layer.png ? await decodeLayer(layer.png) : null}; }
    }
  } catch (e) { dispose(parsed.root, parsed.targets); throw e; }
  install(parsed, bytes, value.name); for (const t of targets) composite(t);
  status('Editable look reopened.'); scheduleRecovery(); return true;
}
async function openProject(file) {
  if (!file) return; if (file.size > LIMITS.project) throw new Error('This project exceeds the 70 MiB limit.');
  status('Opening look…'); await restoreProject(JSON.parse(await file.text()));
}
async function exportAvatar() {
  const wasComparing = comparing; comparing = false; for (const t of targets) composite(t);
  status('Preparing avatar export…');
  let result; try { result = await new GLTFExporter().parseAsync(avatar, {binary: true, animations, onlyVisible: false}); } finally { comparing = wasComparing; for (const t of targets) composite(t); }
  download(new Blob([result], {type: 'model/gltf-binary'}), `${safeName()}.glb`); status('Avatar export download prepared.');
}
async function openDatabase() {
  if (!('indexedDB' in window)) throw new Error('Local recovery storage is unavailable. Save a look file to keep your work.');
  db = await new Promise((resolve, reject) => {
    const request = indexedDB.open('primp-mirror', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('looks');
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Local recovery storage is blocked by another tab.'));
  });
  const record = await readRecoveryRecord(db); recoveryRevision = record.revision;
  const existing = record.document; $('recover').hidden = !existing;
  $('storage-status').textContent = existing ? 'A local recovery look is available. Open it with Recover local look.' : 'Local recovery is available. Save a look file for a portable copy.';
}

function scheduleRecovery() {
  clearTimeout(recoveryTimer); if (!db || !avatar) return;
  const version = generation;
  recoveryTimer = setTimeout(() => {
    if (version !== generation || edit) return;
    recoveryWrites = recoveryWrites.catch(() => {}).then(async () => {
      if (version !== generation) return;
      const snapshot = project();
      recoveryRevision = await writeRecoveryRecord(db, snapshot, recoveryRevision);
      if (version !== generation) return;
      $('storage-status').textContent = 'Local recovery saved on this device.'; $('recover').hidden = false;
    }).catch(error => { if (version !== generation) return; $('storage-status').textContent = `Local recovery failed: ${error.message}. Save a look file now.`; });
  }, 600);
}

$('layer').onchange = () => { finishStroke(); layerIndex = Number($('layer').value); syncLayerControls(); };
$('surface').onchange = () => { finishStroke(); active = Number($('surface').value); syncLayerControls(); };
$('layer-opacity').onchange = () => changeLayerProperty('opacity', Number($('layer-opacity').value) / 100);
$('visible').onchange = () => changeLayerProperty('visible', $('visible').checked);
for (const button of document.querySelectorAll('[data-tool]')) button.onclick = () => {
  finishStroke(); tool = button.dataset.tool;
  if (tool === 'pencil') $('size').value = '4'; if (tool === 'lipstick') $('size').value = '18'; if (tool === 'powder') $('size').value = '45';
  for (const other of document.querySelectorAll('[data-tool]')) other.setAttribute('aria-pressed', String(other === button));
  controls.enableRotate = tool === 'orbit'; controls.enablePan = controls.enableRotate;
};
for (const button of document.querySelectorAll('[data-color]')) button.onclick = () => { $('color').value = button.dataset.color; };
for (const id of ['avatar-file', 'welcome-file']) $(id).onchange = run(async () => { const file = $(id).files[0]; $(id).value = ''; await openAvatar(file); });
$('project-file').onchange = run(async () => { const file = $('project-file').files[0]; $('project-file').value = ''; await openProject(file); });
$('save').onclick = run(async () => {
  const result = await saveLookFile(() => {
    const blob = new Blob([JSON.stringify(project())], {type: 'application/json'});
    if (blob.size > LIMITS.project) throw new Error('This look exceeds the portable project limit.');
    return blob;
  }, `${safeName()}.primp`, {
    picker: window.showSaveFilePicker?.bind(window), download,
  });
  if (result.confirmed) { dirty = false; status('Editable look saved to your file.'); }
  else status('Look download requested. Unsaved-work protection stays on because the browser cannot confirm completion.');
}, false);
$('export').onclick = run(exportAvatar);
$('recover').onclick = run(async () => {
  if (!db) throw new Error('Local recovery is unavailable.');
  clearTimeout(recoveryTimer);
  await recoveryWrites.catch(() => {});
  try {
    const record = await readRecoveryRecord(db);
    if (!record.document) throw new Error('No saved recovery look was found.');
    if (await restoreProject(record.document)) recoveryRevision = record.revision;
  } finally { if (avatar) scheduleRecovery(); }
});
function applyHistory(direction) {
  finishStroke();
  try {
    if (history[direction]()) { markChanged(); status(direction === 'undo' ? 'Undid the last edit.' : 'Redid the edit.'); }
  } catch (error) { status(`Could not ${direction} this edit: ${error.message}`, true); }
}
$('undo').onclick = () => applyHistory('undo');
$('redo').onclick = () => applyHistory('redo');
$('clear').onclick = () => {
  finishStroke(); const target = targets[active], layer = target.layers[layerIndex]; if (!layer.canvas) return;
  const transaction = new TileEdit(context(layer.canvas), () => composite(target)); transaction.capture(TEXTURE_SIZE / 2, TEXTURE_SIZE / 2, TEXTURE_SIZE);
  context(layer.canvas).clearRect(0, 0, TEXTURE_SIZE, TEXTURE_SIZE); const command = transaction.finish(); if (command) { history.push(command); composite(target); markChanged(); }
};
$('frame').onclick = () => frame(); $('face').onclick = () => frame(true);
$('compare').onclick = () => { finishStroke(); comparing = !comparing; $('compare').setAttribute('aria-pressed', String(comparing)); for (const t of targets) composite(t); updateControls(); };
$('snapshot').onclick = run(async () => { renderNow(); const blob = await new Promise(resolve => renderer.domElement.toBlob(resolve, 'image/png')); if (!blob) throw new Error('The mirror image could not be created.'); download(blob, `${safeName()}.png`); status('Mirror image download prepared.'); });
$('exposure').oninput = () => { if (!renderer || !scene) return; renderer.toneMappingExposure = Number($('exposure').value) / 100; render(); };
$('backdrop').oninput = () => { if (!scene) return; scene.background.set($('backdrop').value); render(); };
$('light').onchange = () => { if (!scene) return; scene.getObjectByName('mirror-key').color.set({neutral: '#ffffff', warm: '#ffd3a2', cool: '#c5d9ff'}[$('light').value]); render(); };
window.addEventListener('keydown', event => {
  if (event.target.matches('input,textarea,select,[contenteditable]') || busy || comparing || !avatar) return;
  if ((event.ctrlKey || event.metaKey) && ['z', 'y'].includes(event.key.toLowerCase())) { event.preventDefault(); if (event.key.toLowerCase() === 'y' || event.shiftKey) $('redo').click(); else $('undo').click(); }
  if (event.key === 'Escape') finishStroke(true);
});
window.addEventListener('blur', () => finishStroke());
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
try { initRenderer(); } catch (error) { busy = true; for (const id of ['light', 'exposure', 'backdrop']) $(id).disabled = true; status(`The digital mirror could not start: ${error.message}. WebGL is required.`, true); updateControls(); }
openDatabase().then(() => { if (avatar) scheduleRecovery(); }).catch(error => { $('storage-status').textContent = error.message; });
