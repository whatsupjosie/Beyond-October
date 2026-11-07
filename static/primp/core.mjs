export const TEXTURE_SIZE = 1024;
export const LAYERS = ['Foundation', 'Contour', 'Blush', 'Eyeshadow', 'Eyeliner', 'Lips'];
export const LIMITS = Object.freeze({source: 30 * 1024 * 1024, project: 70 * 1024 * 1024, history: 64 * 1024 * 1024, targets: 4});

export function bounded(value, min, max) {
  if (!Number.isFinite(value)) throw new Error('Expected a finite number.');
  return Math.max(min, Math.min(max, value));
}

// A seam or interrupted hit starts a new segment; never draw across the atlas.
export function strokePoints(a, b, radius, size = TEXTURE_SIZE) {
  const distance = a ? Math.hypot(b.x - a.x, b.y - a.y) : Infinity;
  if (!a || distance > size / 4) return [b];
  const count = Math.max(1, Math.ceil(distance / Math.max(1, radius * 0.25)));
  return Array.from({length: count}, (_, i) => ({x: a.x + (b.x - a.x) * (i + 1) / count, y: a.y + (b.y - a.y) * (i + 1) / count}));
}

export class History {
  constructor(limit = LIMITS.history, steps = 10) { this.limit = limit; this.steps = steps; this.past = []; this.future = []; this.bytes = 0; }
  push(command) {
    if (!Number.isSafeInteger(command.bytes) || command.bytes < 0 || command.bytes > this.limit) throw new Error('This edit exceeds the undo memory budget.');
    this.bytes -= this.future.reduce((sum, item) => sum + item.bytes, 0);
    this.future = [];
    this.past.push(command); this.bytes += command.bytes;
    while (this.past.length > this.steps || this.bytes > this.limit) this.bytes -= this.past.shift().bytes;
  }
  undo() { const item = this.past.pop(); if (!item) return false; item.undo(); this.future.push(item); return true; }
  redo() { const item = this.future.pop(); if (!item) return false; item.redo(); this.past.push(item); return true; }
  clear() { this.past = []; this.future = []; this.bytes = 0; }
}

// Capture only touched tiles, once per stroke. Both undo and redo are exact pixels.
export class TileEdit {
  constructor(context, changed, tileSize = 64) { this.context = context; this.changed = changed; this.tileSize = tileSize; this.tiles = new Map(); }
  capture(x, y, radius) {
    const {width, height} = this.context.canvas, tile = this.tileSize;
    const left = Math.max(0, Math.floor((x - radius - 1) / tile));
    const top = Math.max(0, Math.floor((y - radius - 1) / tile));
    const right = Math.min(Math.ceil(width / tile) - 1, Math.floor((x + radius + 1) / tile));
    const bottom = Math.min(Math.ceil(height / tile) - 1, Math.floor((y + radius + 1) / tile));
    for (let row = top; row <= bottom; row++) for (let col = left; col <= right; col++) {
      const key = `${col}:${row}`;
      if (!this.tiles.has(key)) {
        const tx = col * tile, ty = row * tile, w = Math.min(tile, width - tx), h = Math.min(tile, height - ty);
        this.tiles.set(key, {x: tx, y: ty, before: this.context.getImageData(tx, ty, w, h)});
      }
    }
  }
  finish() {
    const tiles = [...this.tiles.values()];
    if (!tiles.length) return null;
    for (const t of tiles) t.after = this.context.getImageData(t.x, t.y, t.before.width, t.before.height);
    const apply = key => { for (const t of tiles) this.context.putImageData(t[key], t.x, t.y); this.changed(); };
    return {bytes: tiles.reduce((sum, t) => sum + t.before.data.byteLength + t.after.data.byteLength, 0), undo: () => apply('before'), redo: () => apply('after')};
  }
  cancel() { for (const t of this.tiles.values()) this.context.putImageData(t.before, t.x, t.y); this.changed(); }
}

export function validateGLB(buffer) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 20 || buffer.byteLength > LIMITS.source) throw new Error('Choose a self-contained GLB smaller than 30 MiB.');
  const view = new DataView(buffer);
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== buffer.byteLength) throw new Error('This is not a valid glTF 2 GLB file.');
  const length = view.getUint32(12, true);
  if (view.getUint32(16, true) !== 0x4e4f534a || length > buffer.byteLength - 20) throw new Error('The GLB JSON chunk is invalid.');
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, length)).trim());
  for (const item of [...(json.images || []), ...(json.buffers || [])]) {
    if (item.uri && !/^data:(?:image\/(?:png|jpeg|webp)|application\/octet-stream);base64,/.test(item.uri)) throw new Error('External avatar resources are not allowed. Export an embedded GLB.');
  }
  if (json.extensionsRequired?.some(x => !['KHR_materials_unlit', 'KHR_texture_transform', 'KHR_mesh_quantization', 'KHR_materials_clearcoat', 'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_sheen', 'KHR_materials_emissive_strength', 'EXT_mesh_gpu_instancing'].includes(x))) throw new Error('This avatar requires unsupported extensions. Export an uncompressed GLB.');
  return json;
}

export function bytesToBase64(bytes) {
  let text = '';
  for (let offset = 0; offset < bytes.length; offset += 32768) text += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return btoa(text);
}
export function base64ToBytes(text) {
  if (typeof text !== 'string' || text.length > Math.ceil(LIMITS.source / 3) * 4 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(text)) throw new Error('Invalid embedded avatar.');
  return Uint8Array.from(atob(text), char => char.charCodeAt(0));
}
export function validateProject(value) {
  if (!value || value.format !== 'primp' || value.version !== 1 || typeof value.name !== 'string' || value.name.length > 120 || !Array.isArray(value.targets) || value.targets.length > LIMITS.targets) throw new Error('Unsupported or invalid Primp project.');
  validateGLB(base64ToBytes(value.source).buffer);
  const seen = new Set();
  for (const t of value.targets) {
    if (!Number.isSafeInteger(t.id) || t.id < 0 || seen.has(t.id) || !Array.isArray(t.layers) || t.layers.length !== LAYERS.length) throw new Error('Invalid paint surfaces.');
    seen.add(t.id);
    for (const l of t.layers) {
      if (!l || typeof l.visible !== 'boolean' || !Number.isFinite(l.opacity) || l.opacity < 0 || l.opacity > 1 || (l.png !== null && (typeof l.png !== 'string' || l.png.length > 8 * 1024 * 1024 || !l.png.startsWith('data:image/png;base64,iVBORw0KGgo')))) throw new Error('Invalid makeup layer.');
    }
  }
  return value;
}

// A premultiplied-alpha kernel avoids dark fringes at transparent makeup edges.
export function softenPixels(image, centerX, centerY, radius, flow) {
  const {width, height, data} = image, output = new Uint8ClampedArray(data);
  for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) {
    const distance = Math.hypot(x - centerX, y - centerY);
    if (distance >= radius) continue;
    let alpha = 0, r = 0, g = 0, b = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const i = ((y + dy) * width + x + dx) * 4, a = data[i + 3];
      alpha += a; r += data[i] * a; g += data[i + 1] * a; b += data[i + 2] * a;
    }
    const i = (y * width + x) * 4, mix = flow * (1 - distance / radius), oldA = data[i + 3], newA = oldA * (1 - mix) + alpha / 9 * mix;
    output[i + 3] = newA;
    for (let c = 0; c < 3; c++) output[i + c] = newA ? (data[i + c] * oldA * (1 - mix) + [r, g, b][c] / 9 * mix) / newA : 0;
  }
  data.set(output); return image;
}
