// PubCast AI — avatar_import.js
// Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
// Rearview Foresight LLC — All Rights Reserved · Feic Mo Chroí — See My Heart
//
// Universal avatar import. Reads GLB, glTF (with its .bin and textures), OBJ (with
// .mtl and textures), FBX, or a .zip holding any of those. Every avatar leaves here
// as ONE GLB in metres, standing on the floor at the origin, facing +Z, scaled so
// its standing height equals its canonical height. Skeletons and animations are
// kept when the source has them; the server re-measures the result and refuses
// anything whose height does not match.
//
// Offline: three.js is vendored under /static/vendor/three-0.160.0. Pages must
// provide an import map that resolves "three" to that copy.

import * as THREE from 'three';
import { GLTFLoader } from '/static/vendor/three-0.160.0/examples/jsm/loaders/GLTFLoader.js';
import { OBJLoader } from '/static/vendor/three-0.160.0/examples/jsm/loaders/OBJLoader.js';
import { MTLLoader } from '/static/vendor/three-0.160.0/examples/jsm/loaders/MTLLoader.js';
import { FBXLoader } from '/static/vendor/three-0.160.0/examples/jsm/loaders/FBXLoader.js';
import { GLTFExporter } from '/static/vendor/three-0.160.0/examples/jsm/exporters/GLTFExporter.js';
import { unzipSync } from '/static/vendor/three-0.160.0/examples/jsm/libs/fflate.module.js';

export const INCH_M = 0.0254;
export const FORMATS = ['glb', 'gltf', 'obj', 'fbx', 'zip'];
const MODEL_EXTS = ['glb', 'gltf', 'fbx', 'obj'];          // preference order inside a bundle

const ext = (name) => (name.split('.').pop() || '').toLowerCase();
const base = (name) => name.split(/[\\/]/).pop();

/** Flatten dropped files (and any .zip among them) into {name -> Blob}. */
export async function collectFiles(fileList) {
  const files = new Map();
  for (const file of fileList) {
    if (ext(file.name) === 'zip') {
      const entries = unzipSync(new Uint8Array(await file.arrayBuffer()));
      for (const [path, bytes] of Object.entries(entries)) {
        if (path.endsWith('/') || path.includes('__MACOSX')) continue;
        files.set(base(path), new Blob([bytes]));
      }
    } else {
      files.set(base(file.name), file);
    }
  }
  return files;
}

/** Pick the model file from a bundle: the one the person most likely meant. */
export function pickModel(files) {
  for (const kind of MODEL_EXTS) {
    const hit = [...files.keys()].find((n) => ext(n) === kind);
    if (hit) return hit;
  }
  throw new Error(`No 3D model found. Supported: ${MODEL_EXTS.join(', ').toUpperCase()} (or a .zip of one).`);
}

/** A LoadingManager that resolves a model's sibling files (bin, mtl, textures) from the bundle. */
function bundleManager(files, urls) {
  const manager = new THREE.LoadingManager();
  const byLower = new Map([...files.keys()].map((n) => [n.toLowerCase(), n]));
  manager.setURLModifier((url) => {
    if (/^(data|blob):/.test(url)) return url;
    const name = byLower.get(decodeURIComponent(base(url)).toLowerCase());
    if (!name) return url;                       // missing texture: loader reports it, model still loads
    if (!urls.has(name)) urls.set(name, URL.createObjectURL(files.get(name)));
    return urls.get(name);
  });
  return manager;
}

/** Load the bundle's model into a three.js object, with its animation clips. */
export async function loadModel(files, modelName = pickModel(files)) {
  const urls = new Map();
  const manager = bundleManager(files, urls);
  const blob = files.get(modelName);
  const kind = ext(modelName);
  const warnings = [];
  try {
    if (kind === 'glb' || kind === 'gltf') {
      const loader = new GLTFLoader(manager);
      const data = kind === 'glb' ? await blob.arrayBuffer() : await blob.text();
      const gltf = await loader.parseAsync(data, '');
      return { object: gltf.scene, clips: gltf.animations || [], format: kind, modelName, warnings };
    }
    if (kind === 'fbx') {
      const object = new FBXLoader(manager).parse(await blob.arrayBuffer(), '');
      return { object, clips: object.animations || [], format: kind, modelName, warnings };
    }
    if (kind === 'obj') {
      const loader = new OBJLoader(manager);
      const text = await blob.text();
      const mtlRef = (text.match(/^mtllib\s+(.+)$/m) || [])[1];
      const mtlName = mtlRef && [...files.keys()].find((n) => n.toLowerCase() === base(mtlRef.trim()).toLowerCase());
      if (mtlName) {
        const materials = new MTLLoader(manager).parse(await files.get(mtlName).text(), '');
        materials.preload();
        loader.setMaterials(materials);
      } else if (mtlRef) {
        warnings.push(`Material file ${mtlRef.trim()} was not included; using a plain material.`);
      }
      warnings.push('OBJ files cannot hold a skeleton, so this avatar imports as a standing figure.');
      return { object: loader.parse(text), clips: [], format: kind, modelName, warnings };
    }
  } finally {
    // Textures are decoded during parse/preload; keep URLs alive until export finishes.
    setTimeout(() => urls.forEach((u) => URL.revokeObjectURL(u)), 60000);
  }
  throw new Error(`Unsupported file type: .${kind}`);
}

const MAX_SKINNED_SAMPLES = 200000;   // vertices skinned per mesh when measuring; denser meshes are strided

/**
 * World bounding box exactly as the renderer will draw the model.
 * Skinned meshes are measured by skinning their vertices with three.js's own
 * applyBoneTransform. A shortcut through one bone is wrong for files whose
 * bind matrix is not identity (FBX commonly carries centimetre scale and an
 * axis turn there) and for files not saved in their rest pose.
 */
export function measure(object) {
  object.updateMatrixWorld(true);
  const box = new THREE.Box3();
  const v = new THREE.Vector3();
  object.traverse((node) => {
    if (!node.isMesh || !node.visible) return;
    if (node.isSkinnedMesh && node.skeleton) {
      node.skeleton.bones.forEach((b) => b.updateMatrixWorld(true));
      const pos = node.geometry.attributes.position;
      const stride = Math.max(1, Math.ceil(pos.count / MAX_SKINNED_SAMPLES));
      for (let i = 0; i < pos.count; i += stride) {
        v.fromBufferAttribute(pos, i);
        node.applyBoneTransform(i, v);           // mesh space, as the vertex shader computes it
        box.expandByPoint(v.applyMatrix4(node.matrixWorld));
      }
    } else {
      node.geometry.computeBoundingBox();
      box.union(node.geometry.boundingBox.clone().applyMatrix4(node.matrixWorld));
    }
  });
  if (box.isEmpty()) throw new Error('The file contains no visible geometry.');
  return box;
}

/**
 * Guess which axis is "up". glTF and FBX (after FBXLoader) are Y-up by spec; OBJ has
 * no convention, and many tools write Z-up, which leaves a figure lying on its back.
 * A standing figure's height is its largest dimension; if that is Z, rotate it up.
 */
export function guessUpRotation(object, format) {
  if (format !== 'obj') return 0;
  const size = measure(object).getSize(new THREE.Vector3());
  return size.z > size.y * 1.3 && size.z > size.x ? -Math.PI / 2 : 0;
}

/** Use PBR materials so the GLB keeps colours and textures faithfully. */
function standardise(object) {
  object.traverse((node) => {
    if (!node.isMesh) return;
    const convert = (m) => {
      if (!m || m.isMeshStandardMaterial || m.isMeshBasicMaterial) return m;
      // Emissive colour only counts at its intensity: FBX commonly says "white at 0".
      const glow = m.emissive ? m.emissive.clone().multiplyScalar(m.emissiveIntensity ?? 1) : new THREE.Color(0, 0, 0);
      const s = new THREE.MeshStandardMaterial({
        name: m.name, color: m.color ? m.color.clone() : new THREE.Color(0xcccccc),
        map: m.map || null, normalMap: m.normalMap || null, emissive: glow,
        emissiveMap: m.emissiveMap || null, alphaMap: m.alphaMap || null, transparent: !!m.transparent,
        opacity: m.opacity ?? 1, side: m.side, roughness: 0.7, metalness: 0,
      });
      if (m.shininess !== undefined) s.roughness = Math.max(0.15, Math.min(1, 1 - m.shininess / 120));
      return s;
    };
    node.material = Array.isArray(node.material) ? node.material.map(convert) : convert(node.material);
  });
}

/**
 * Normalise to the world's rules and return a container ready to export:
 *  - stood upright (extraRotationX lets a person correct an odd file by hand),
 *  - scaled so standing height = canonical height, in metres,
 *  - feet on the floor (y = 0), centred on x/z.
 * The transform lives on one parent node, so skinned meshes are never distorted.
 */
export function normalise(loaded, heightIn, { extraRotationX = 0, extraRotationY = 0 } = {}) {
  if (!(heightIn > 0)) throw new Error('Every avatar needs a canonical height before it can be imported.');
  const { object, format } = loaded;
  standardise(object);
  const root = new THREE.Group();
  root.name = 'avatar_root';
  const upright = new THREE.Group();
  upright.name = 'avatar_upright';
  upright.add(object);
  root.add(upright);
  upright.rotation.set(guessUpRotation(object, format) + extraRotationX, extraRotationY, 0);
  root.updateMatrixWorld(true);
  let box = measure(root);
  const height = box.max.y - box.min.y;
  if (!(height > 1e-6)) throw new Error('The model has no height to measure.');
  const target = heightIn * INCH_M;
  const scale = target / height;
  upright.scale.setScalar(scale);
  root.updateMatrixWorld(true);
  box = measure(root);
  const centre = box.getCenter(new THREE.Vector3());
  upright.position.set(-centre.x, -box.min.y, -centre.z);
  root.updateMatrixWorld(true);
  const final = measure(root);
  const finalSize = final.getSize(new THREE.Vector3());
  return {
    root, scale, sourceHeight: height,
    heightM: finalSize.y, size: finalSize, feetY: final.min.y,
    stats: stats(root, loaded.clips),
  };
}

export function stats(root, clips = []) {
  let meshes = 0, triangles = 0, bones = new Set(), skinned = false;
  root.traverse((n) => {
    if (n.isMesh) {
      meshes += 1;
      const g = n.geometry;
      triangles += g.index ? g.index.count / 3 : g.attributes.position.count / 3;
      if (n.isSkinnedMesh) { skinned = true; n.skeleton.bones.forEach((b) => bones.add(b.uuid)); }
    }
  });
  return { meshes, triangles: Math.round(triangles), bones: bones.size, skinned, clips: clips.map((c) => c.name) };
}

/** Export the normalised avatar as a binary glTF (ArrayBuffer). */
export function exportGLB(root, clips = []) {
  return new Promise((resolve, reject) => {
    new GLTFExporter().parse(root, resolve, reject, { binary: true, animations: clips, onlyVisible: true });
  });
}

/** Upload to the host; the server re-measures and refuses a mismatched height. */
export async function uploadGLB(glb, { name, heightIn, characterId = '', sourceFormat, sourceName, token }) {
  const q = new URLSearchParams({ name, height_in: String(heightIn), character_id: characterId,
    source_format: sourceFormat || 'glb', source_name: sourceName || '' });
  const headers = { 'Content-Type': 'model/gltf-binary' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch('/api/avatars/imports?' + q, { method: 'POST', headers, body: glb });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Import failed (${response.status})`);
  return body.avatar;
}

/** Whole pipeline for code that already has the files and the height. */
export async function importAvatar(fileList, { name, heightIn, characterId, token, extraRotationX = 0, extraRotationY = 0 }) {
  const files = await collectFiles(fileList);
  const loaded = await loadModel(files);
  const result = normalise(loaded, heightIn, { extraRotationX, extraRotationY });
  const glb = await exportGLB(result.root, loaded.clips);
  const avatar = await uploadGLB(glb, { name, heightIn, characterId, sourceFormat: loaded.format, sourceName: loaded.modelName, token });
  return { avatar, result, loaded };
}
