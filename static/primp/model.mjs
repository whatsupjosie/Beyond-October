import {buildIslandAtlas} from './uv-islands.mjs';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {TEXTURE_SIZE, LAYERS, LIMITS, validateGLB, bounded, allowPaintAllocation} from './core.mjs';
function canvas() { const c = document.createElement('canvas'); c.width = c.height = TEXTURE_SIZE; return c; }
function context(c) { return c.getContext('2d', {willReadFrequently: true}); }
export async function parseAvatar(bytes) {
  validateGLB(bytes);
  const manager = new THREE.LoadingManager();
  // GLB buffers and texture blobs are local; no remote file may be fetched by an imported model.
  manager.setURLModifier(url => { if (!url.startsWith('blob:') && !url.startsWith('data:')) throw new Error('External avatar resources are blocked.'); return url; });
  const gltf = await new GLTFLoader(manager).parseAsync(bytes.slice(0), '');
  const materials = new Map(), surfaces = [];
  try {
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(mesh => {
      if (!mesh.isMesh) return;
      const list = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const copies = list.map(material => {
        const copy = materials.get(material) || material.clone(); materials.set(material, copy);
        const uvName = material.map?.channel ? `uv${material.map.channel}` : 'uv';
        if (!surfaces.some(t => t.material === copy) && ['uv', 'uv1'].includes(uvName) && mesh.geometry.getAttribute(uvName) && !material.map?.isCompressedTexture) {
          surfaces.push({id: surfaces.length, material: copy, originalMap: copy.map, originalColor: copy.color?.clone(), uvName, label: `${material.name || mesh.name || 'Surface'} · ${surfaces.length + 1}`, meshes: [], layers: LAYERS.map(() => ({canvas: null, visible: true, opacity: 1})), base: null, composite: null, texture: null});
        }
        return copy;
      });
      mesh.material = Array.isArray(mesh.material) ? copies : copies[0];
      for (const target of surfaces) if (copies.includes(target.material) && mesh.geometry.getAttribute(target.uvName) && !target.meshes.includes(mesh)) target.meshes.push(mesh);
    });
    const bounds = new THREE.Box3().setFromObject(gltf.scene), size = bounds.getSize(new THREE.Vector3());
    if (bounds.isEmpty() || ![size.x, size.y, size.z].every(Number.isFinite) || size.length() < .00001) throw new Error('The avatar has no usable visible geometry.');
    return {root: gltf.scene, animations: gltf.animations, targets: surfaces};
  } catch (error) { dispose(gltf.scene, surfaces); throw error; }
}
export function dispose(root, surfaces) {
  const textures = new Set(), materials = new Set(), geometries = new Set();
  root.traverse(node => { if (!node.isMesh) return; geometries.add(node.geometry); for (const m of (Array.isArray(node.material) ? node.material : [node.material])) { materials.add(m); for (const value of Object.values(m)) if (value?.isTexture) textures.add(value); } });
  for (const t of surfaces) if (t.originalMap) textures.add(t.originalMap);
  for (const t of textures) { t.dispose(); if (typeof t.image?.close === 'function') t.image.close(); }
  for (const m of materials) m.dispose(); for (const g of geometries) g.dispose();
}
export function preparePaintAtlas(target, size = TEXTURE_SIZE) {
  const triangles = [], references = [];
  const mapping = target.texture || target.originalMap;
  if (mapping?.matrixAutoUpdate) mapping.updateMatrix();
  const faces = new Map();
  for (const [meshIndex, mesh] of (target.meshes || []).entries()) {
    const geometry = mesh.geometry, uv = geometry.getAttribute(target.uvName), position = geometry.getAttribute('position');
    const count = geometry.index?.count ?? position.count;
    const ids = new Int32Array(Math.floor(count / 3)).fill(-1); faces.set(mesh, ids);
    for (let start = 0; start + 2 < count; start += 3) {
      const group = geometry.groups.find(g => start >= g.start && start < g.start + g.count);
      const material = Array.isArray(mesh.material) ? mesh.material[group?.materialIndex ?? 0] : mesh.material;
      if (material !== target.material) continue;
      const vertices = [0,1,2].map(i => geometry.index ? geometry.index.getX(start + i) : start + i);
      const texcoords = vertices.map(i => {
        const point = new THREE.Vector2(uv.getX(i), uv.getY(i));
        if (mapping) { point.applyMatrix3(mapping.matrix); if (mapping.flipY) point.y = 1 - point.y; }
        return [point.x, point.y];
      });
      references.push([ids, start / 3]);
      triangles.push({mesh: meshIndex, positions: vertices.map(i => [position.getX(i),position.getY(i),position.getZ(i)]), uv: texcoords});
    }
  }
  const atlas = buildIslandAtlas(triangles, size);
  for (let i = 0; i < references.length; i++) references[i][0][references[i][1]] = i;
  return {...atlas, faces};
}

export function prepareSurface(target, allTargets, changed = () => {}) {
  if (target.base) return;
  if (target.material.vertexColors && target.meshes?.some(mesh => mesh.geometry.getAttribute('color'))) throw new Error('This surface uses live vertex colors that would tint the makeup. Prepare a texture-based paint layout first; the original avatar is unchanged.');
  if (allTargets.filter(t => t.base).length >= LIMITS.targets) throw new Error('This look already uses four paint surfaces. Save it before starting another.');
  const atlas = target.meshes?.length ? preparePaintAtlas(target, target.size || TEXTURE_SIZE) : null;
  allowPaintAllocation(allTargets, atlas?.mask.byteLength || 0);
  const imageSize = target.originalMap?.image;
  const width = imageSize?.width || TEXTURE_SIZE, height = imageSize?.height || TEXTURE_SIZE;
  const compositeWidth = Math.max(width, target.size || TEXTURE_SIZE), compositeHeight = Math.max(height, target.size || TEXTURE_SIZE);
  if (width > 4096 || height > 4096 || allTargets.reduce((n, t) => n + (t.base ? t.base.width * t.base.height + t.composite.width * t.composite.height : 0), 0) + width * height + compositeWidth * compositeHeight > 32 * 1024 * 1024) throw new Error('This surface exceeds the texture memory budget. The original texture has not been reduced or changed.');
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
  const composite = canvas(); composite.width = compositeWidth; composite.height = compositeHeight;
  const texture = new THREE.CanvasTexture(composite), original = target.originalMap;
  const previousMap = target.material.map, previousColor = target.material.color?.clone();
  try {
    texture.colorSpace = THREE.SRGBColorSpace; texture.flipY = original?.flipY ?? false;
    if (original) {
      for (const prop of ['wrapS', 'wrapT', 'magFilter', 'minFilter', 'anisotropy', 'channel', 'rotation']) texture[prop] = original[prop];
      texture.offset.copy(original.offset); texture.repeat.copy(original.repeat); texture.center.copy(original.center);
      texture.matrixAutoUpdate = original.matrixAutoUpdate;
      texture.matrix.copy(original.matrix);
    }
    composeSurface({...target, base, composite, texture});
    Object.assign(target, {base, composite, texture, atlas});
    target.material.map = texture; target.material.color?.set(0xffffff); target.material.needsUpdate = true;
    changed();
  } catch (error) {
    Object.assign(target, {base: null, composite: null, texture: null, atlas: null});
    target.material.map = previousMap;
    if (previousColor) target.material.color.copy(previousColor);
    target.material.needsUpdate = true;
    texture.dispose(); base.width = composite.width = 0;
    throw error;
  }
}
export function composeSurface(target, comparing = false, changed = () => {}) {
  if (!target.base) return;
  const ctx = context(target.composite); ctx.clearRect(0, 0, target.composite.width, target.composite.height); ctx.drawImage(target.base, 0, 0, target.composite.width, target.composite.height);
  if (!comparing) for (const layer of target.layers) if (layer.canvas && layer.visible) { ctx.globalAlpha = layer.opacity; ctx.drawImage(layer.canvas, 0, 0, target.composite.width, target.composite.height); }
  ctx.globalAlpha = 1; target.texture.needsUpdate = true;
  // Compare and fully hidden paint use the exact imported material appearance.
  const original = comparing || !target.layers.some(layer => layer.canvas && layer.visible && layer.opacity > 0);
  const map = original ? target.originalMap || null : target.texture;
  if (target.material.map !== map) { target.material.map = map; target.material.needsUpdate = true; }
  if (original && target.originalColor) target.material.color.copy(target.originalColor);
  else target.material.color?.set(0xffffff);
  changed();
}
export async function decodeLayer(png, size = TEXTURE_SIZE) {
  if (![1024, 2048].includes(size)) throw new Error('Unsupported paint resolution.');
  // Validate PNG dimensions before decoding; reject decompression bombs and foreign formats.
  const raw = atob(png.slice('data:image/png;base64,'.length));
  if (raw.length < 24) throw new Error('Truncated paint layer.');
  const view = new DataView(Uint8Array.from(raw.slice(0, 24), c => c.charCodeAt(0)).buffer);
  if (view.getUint32(16) !== size || view.getUint32(20) !== size) throw new Error(`Paint layers must be ${size} × ${size} PNGs.`);
  const image = new Image(); image.src = png; await image.decode();
  const c = canvas(); c.width = c.height = size; context(c).drawImage(image, 0, 0); return c;
}

// Sample only one texel: cutout picking must not allocate a duplicate full atlas.
let alphaSample;
function textureChannel(texture, hit, channel) {
  if (!texture) return 1;
  const name = texture.channel ? `uv${texture.channel}` : 'uv';
  // Three r160 raycasts expose the first two UV sets. Unknown channels remain occluders.
  const point = (name === 'uv' ? hit.uv : name === 'uv1' ? hit.uv1 : null)?.clone();
  const image = texture.image;
  if (!point || !image?.width || !image?.height || texture.isCompressedTexture) return null;
  if (texture.matrixAutoUpdate) texture.updateMatrix();
  texture.transformUv(point);
  alphaSample ||= document.createElement('canvas'); alphaSample.width = alphaSample.height = 1;
  const ctx = alphaSample.getContext('2d', {willReadFrequently: true});
  ctx.drawImage(image, Math.min(image.width - 1, Math.max(0, Math.floor(point.x * image.width))), Math.min(image.height - 1, Math.max(0, Math.floor(point.y * image.height))), 1, 1, 0, 0, 1, 1);
  return ctx.getImageData(0, 0, 1, 1).data[channel] / 255;
}
function visibleTexel(material, hit) {
  if (!material.transparent && !material.alphaTest) return true;
  const colorAlpha = textureChannel(material.map, hit, 3), maskAlpha = textureChannel(material.alphaMap, hit, 1);
  if (colorAlpha === null || maskAlpha === null) return true;
  const alpha = material.opacity * colorAlpha * maskAlpha;
  return alpha >= (material.alphaTest || 0) && (!material.transparent || alpha > 0);
}

export function surfacePoint(root, target, ndc, camera) {
  const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, camera); root.updateMatrixWorld(true);
  const visible = object => { for (let node = object; node; node = node.parent) if (!node.visible) return false; return true; };
  const hit = ray.intersectObject(root, true).find(h => {
    if (!visible(h.object) || !h.face) return false;
    const material = Array.isArray(h.object.material) ? h.object.material[h.face.materialIndex] : h.object.material;
    return material && material.visible !== false && visibleTexel(material, h);
  });
  if (!hit) return null;
  const material = Array.isArray(hit.object.material) ? hit.object.material[hit.face.materialIndex] : hit.object.material;
  if (material !== target.material) return null;
  const uv = (target.uvName === 'uv' ? hit.uv : hit.uv1)?.clone();
  if (!uv) return null;
  const mapping = target.texture || target.originalMap;
  if (mapping) { if (mapping.matrixAutoUpdate) mapping.updateMatrix(); mapping.transformUv(uv); }
  let chart;
  if (target.atlas) {
    const index = target.atlas.faces.get(hit.object)?.[hit.faceIndex];
    chart = target.atlas.charts[index];
    if (index === undefined || index < 0 || !target.atlas.validFaces[index] || !target.atlas.coverage[chart]) throw new Error('This face has no usable paint UV area at the selected detail.');
    if (target.atlas.blocked.has(chart)) throw new Error('This region has overlapping UVs. Prepare a unique paint layout before painting.');
  }
  const size = target.size || TEXTURE_SIZE;
  return {x: bounded(uv.x, 0, 1) * (size - 1), y: bounded(uv.y, 0, 1) * (size - 1), chart};
}
