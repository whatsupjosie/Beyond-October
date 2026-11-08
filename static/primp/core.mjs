import {inspectGLB} from './gltf-boundary.mjs';
export const TEXTURE_SIZE = 1024;
export const LAYERS = ['Foundation', 'Contour', 'Blush', 'Eyeshadow', 'Eyeliner', 'Lips'];
export const LIMITS = Object.freeze({source: 30 * 1024 * 1024, project: 70 * 1024 * 1024, history: 64 * 1024 * 1024, targets: 4});

export function bounded(value, min, max) {
  if (!Number.isFinite(value)) throw new Error('Expected a finite number.');
  return Math.max(min, Math.min(max, value));
}

// Interrupted hits and large atlas jumps start a new segment. Nearby UV islands
// still require geometric island isolation; distance alone cannot identify them.
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
  undo() {
    const item = this.past.at(-1); if (!item) return false;
    try { item.undo(); }
    catch (error) { try { item.redo(); } catch { /* Keep the original failure and entry. */ } throw error; }
    this.past.pop(); this.future.push(item); return true;
  }
  redo() {
    const item = this.future.at(-1); if (!item) return false;
    try { item.redo(); }
    catch (error) { try { item.undo(); } catch { /* Keep the original failure and entry. */ } throw error; }
    this.future.pop(); this.past.push(item); return true;
  }
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
    for (const [key, t] of this.tiles) {
      t.after = this.context.getImageData(t.x, t.y, t.before.width, t.before.height);
      if (!t.before.data.some((value, i) => value !== t.after.data[i])) this.tiles.delete(key);
    }
    const tiles = [...this.tiles.values()];
    if (!tiles.length) return null;
    const apply = key => { for (const t of tiles) this.context.putImageData(t[key], t.x, t.y); this.changed(); };
    return {bytes: tiles.reduce((sum, t) => sum + t.before.data.byteLength + t.after.data.byteLength, 0), undo: () => apply('before'), redo: () => apply('after')};
  }
  cancel() { for (const t of this.tiles.values()) this.context.putImageData(t.before, t.x, t.y); this.changed(); }
}

export function validateGLB(buffer) { return inspectGLB(buffer, LIMITS.source); }

export function bytesToBase64(bytes) {
  let text = '';
  for (let offset = 0; offset < bytes.length; offset += 32768) text += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return btoa(text);
}
export function base64ToBytes(text) {
  const invalid = () => { throw new Error('Invalid embedded avatar.'); };
  if (typeof text !== 'string' || text.length % 4 !== 0 || text.length > Math.ceil(LIMITS.source / 3) * 4) invalid();
  const padding = text.endsWith('==') ? 2 : text.endsWith('=') ? 1 : 0;
  const body = text.slice(0, text.length - padding);
  // A repeated capture group over a multi-megabyte string can overflow V8's stack.
  if (/[^A-Za-z0-9+/]/.test(body) || text.length / 4 * 3 - padding > LIMITS.source) invalid();
  return Uint8Array.from(atob(text), char => char.charCodeAt(0));
}

// Count the canonical document without copying its large base64 strings into a
// second serialized string. Paint payloads and source are ASCII; names are UTF-8.
export function checkProjectSize(value, limit = LIMITS.project) {
  let payload = value.source.length;
  const targets = value.targets.map(t => ({id: t.id, layers: t.layers.map(layer => {
    if (layer.png !== null) payload += layer.png.length;
    return {visible: layer.visible, opacity: layer.opacity, png: layer.png === null ? null : ''};
  })}));
  const header = {format: 'primp', version: 1, name: value.name, source: '', targets};
  const bytes = payload + new TextEncoder().encode(JSON.stringify(header)).byteLength;
  if (bytes > limit) throw new Error('This look exceeds the 70 MiB portable project limit. Your open work has not been discarded.');
  return bytes;
}

export function validateProject(value) {
  if (!value || value.format !== 'primp' || value.version !== 1 || typeof value.name !== 'string' || value.name.length > 120 || !Array.isArray(value.targets) || value.targets.length > LIMITS.targets) throw new Error('Unsupported or invalid Primp project.');
  validateGLB(base64ToBytes(value.source).buffer);
  const seen = new Set();
  for (const t of value.targets) {
    if (!t || typeof t !== 'object' || !Number.isSafeInteger(t.id) || t.id < 0 || seen.has(t.id) || !Array.isArray(t.layers) || t.layers.length !== LAYERS.length) throw new Error('Invalid paint surfaces.');
    seen.add(t.id);
    for (const layer of t.layers) {
      if (!layer || typeof layer.visible !== 'boolean' || !Number.isFinite(layer.opacity) || layer.opacity < 0 || layer.opacity > 1) throw new Error('Invalid makeup layer.');
      if (layer.png === null) continue;
      if (typeof layer.png !== 'string' || layer.png.length > 8 * 1024 * 1024 || !layer.png.startsWith('data:image/png;base64,iVBORw0KGgo') || /[^A-Za-z0-9+/=]/.test(layer.png.slice(22))) throw new Error('Invalid makeup layer.');
    }
  }
  checkProjectSize(value);
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
