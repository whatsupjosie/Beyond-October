import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {TEXTURE_SIZE, LAYERS, LIMITS, validateGLB, bounded} from './core.mjs';
function canvas() { const c = document.createElement('canvas'); c.width = c.height = TEXTURE_SIZE; return c; }
function context(c) { return c.getContext('2d', {willReadFrequently: true}); }
export async function parseAvatar(bytes) {
  validateGLB(bytes);
  const manager = new THREE.LoadingManager();
  // GLB buffers and texture blobs are local; no remote file may be fetched by an imported model.
  manager.setURLModifier(url => { if (!url.startsWith('blob:') && !url.startsWith('data:')) throw new Error('External avatar resources are blocked.'); return url; });
  const gltf = await new GLTFLoader(manager).parseAsync(bytes.slice(0), '');
  const materials = new Map(), surfaces = [];
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse(mesh => {
    if (!mesh.isMesh) return;
    const list = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const copies = list.map(material => {
      const copy = materials.get(material) || material.clone(); materials.set(material, copy);
      const uvName = material.map?.channel ? `uv${material.map.channel}` : 'uv';
      if (!surfaces.some(t => t.material === copy) && ['uv', 'uv1'].includes(uvName) && mesh.geometry.getAttribute(uvName) && !material.map?.isCompressedTexture) {
        surfaces.push({id: surfaces.length, material: copy, originalMap: copy.map, originalColor: copy.color?.clone(), uvName, label: `${material.name || mesh.name || 'Surface'} · ${surfaces.length + 1}`, layers: LAYERS.map(() => ({canvas: null, visible: true, opacity: 1})), base: null, composite: null, texture: null});
      }
      return copy;
    });
    mesh.material = Array.isArray(mesh.material) ? copies : copies[0];
  });
  const bounds = new THREE.Box3().setFromObject(gltf.scene), size = bounds.getSize(new THREE.Vector3());
  if (bounds.isEmpty() || ![size.x, size.y, size.z].every(Number.isFinite) || size.length() < .00001) { dispose(gltf.scene, surfaces); throw new Error('The avatar has no usable visible geometry.'); }
  return {root: gltf.scene, animations: gltf.animations, targets: surfaces};
}
export function dispose(root, surfaces) {
  const textures = new Set(), materials = new Set(), geometries = new Set();
  root.traverse(node => { if (!node.isMesh) return; geometries.add(node.geometry); for (const m of (Array.isArray(node.material) ? node.material : [node.material])) { materials.add(m); for (const value of Object.values(m)) if (value?.isTexture) textures.add(value); } });
  for (const t of surfaces) if (t.originalMap) textures.add(t.originalMap);
  for (const t of textures) { t.dispose(); if (typeof t.image?.close === 'function') t.image.close(); }
  for (const m of materials) m.dispose(); for (const g of geometries) g.dispose();
}
export function prepareSurface(target, allTargets, changed = () => {}) {
  if (target.base) return;
  if (allTargets.filter(t => t.base).length >= LIMITS.targets) throw new Error('This look already uses four paint surfaces. Save it before starting another.');
  const imageSize = target.originalMap?.image;
  const width = imageSize?.width || TEXTURE_SIZE, height = imageSize?.height || TEXTURE_SIZE;
  if (width > 4096 || height > 4096 || allTargets.reduce((n, t) => n + (t.base ? t.base.width * t.base.height * 2 : 0), 0) + width * height * 2 > 32 * 1024 * 1024) throw new Error('This surface exceeds the texture memory budget. The original texture has not been reduced or changed.');
  const base = canvas(); base.width = width; base.height = height; const ctx = context(base);
  if (target.originalMap) {
    const image = target.originalMap.image;
    if (!image?.width || !image?.height) throw new Error('This surface texture cannot be painted.');
    ctx.drawImage(image, 0, 0, width, height);
  } else { ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height); }
  if (target.originalColor && target.originalColor.getHex() !== 0xffffff) {
    const image = ctx.getImageData(0, 0, width, height);
    const factors = [target.originalColor.r, target.originalColor.g, target.originalColor.b];
    const tables = factors.map(factor => Array.from({length: 256}, (_, i) => {
      const value = i / 255;
      const linear = value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
      const tinted = linear * factor;
      return Math.round(255 * (tinted <= .0031308 ? tinted * 12.92 : 1.055 * tinted ** (1 / 2.4) - .055));
    }));
    for (let i = 0; i < image.data.length; i += 4) for (let c = 0; c < 3; c++) image.data[i + c] = tables[c][image.data[i + c]];
    ctx.putImageData(image, 0, 0);
  }
  target.base = base; target.composite = canvas(); target.composite.width = width; target.composite.height = height;
  const texture = new THREE.CanvasTexture(target.composite), original = target.originalMap;
  texture.colorSpace = THREE.SRGBColorSpace; texture.flipY = original?.flipY ?? false;
  if (original) {
    for (const prop of ['wrapS', 'wrapT', 'magFilter', 'minFilter', 'anisotropy', 'channel', 'rotation']) texture[prop] = original[prop];
    texture.offset.copy(original.offset); texture.repeat.copy(original.repeat); texture.center.copy(original.center);
  }
  target.texture = texture; target.material.map = texture; target.material.color?.set(0xffffff); target.material.needsUpdate = true;
  composeSurface(target, false, changed);
}
export function composeSurface(target, comparing = false, changed = () => {}) {
  if (!target.base) return;
  const ctx = context(target.composite); ctx.clearRect(0, 0, target.composite.width, target.composite.height); ctx.drawImage(target.base, 0, 0);
  if (!comparing) for (const layer of target.layers) if (layer.canvas && layer.visible) { ctx.globalAlpha = layer.opacity; ctx.drawImage(layer.canvas, 0, 0, target.composite.width, target.composite.height); }
  ctx.globalAlpha = 1; target.texture.needsUpdate = true; changed();
}
export async function decodeLayer(png) {
  // Validate PNG dimensions before decoding; reject decompression bombs and foreign formats.
  const raw = atob(png.slice('data:image/png;base64,'.length));
  if (raw.length < 24) throw new Error('Truncated paint layer.');
  const view = new DataView(Uint8Array.from(raw.slice(0, 24), c => c.charCodeAt(0)).buffer);
  if (view.getUint32(16) !== TEXTURE_SIZE || view.getUint32(20) !== TEXTURE_SIZE) throw new Error('Paint layers must be 1024 × 1024 PNGs.');
  const image = new Image(); image.src = png; await image.decode();
  const c = canvas(); context(c).drawImage(image, 0, 0); return c;
}

export function surfacePoint(root, target, ndc, camera) {
  const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, camera); root.updateMatrixWorld(true);
  const visible = object => { for (let node = object; node; node = node.parent) if (!node.visible) return false; return true; };
  const hit = ray.intersectObject(root, true).find(h => visible(h.object) && h.face);
  if (!hit) return null;
  const material = Array.isArray(hit.object.material) ? hit.object.material[hit.face.materialIndex] : hit.object.material;
  if (material !== target.material) return null;
  const uv = (target.uvName === 'uv' ? hit.uv : hit.uv1)?.clone();
  if (!uv) return null;
  const mapping = target.texture || target.originalMap;
  if (mapping) { mapping.updateMatrix(); mapping.transformUv(uv); }
  return {x: bounded(uv.x, 0, 1) * (TEXTURE_SIZE - 1), y: bounded(uv.y, 0, 1) * (TEXTURE_SIZE - 1)};
}
