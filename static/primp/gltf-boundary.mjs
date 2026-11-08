const SUPPORTED = new Set(['KHR_materials_unlit', 'KHR_texture_transform', 'KHR_mesh_quantization', 'KHR_materials_clearcoat', 'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_sheen', 'KHR_materials_emissive_strength', 'EXT_mesh_gpu_instancing']);
const COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4};
const COMPONENTS = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16};
export const IMPORT_LIMITS = Object.freeze({nodes: 2048, depth: 128, decodedGeometry: 64 * 1024 * 1024, imagePixels: 16 * 1024 * 1024, imageSide: 4096});
const fail = message => { throw new Error(message); };
const integer = (n, min = 0) => Number.isSafeInteger(n) && n >= min;
function list(value, name, limit) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > limit || value.some(item => !item || typeof item !== 'object' || Array.isArray(item))) fail(`Invalid or excessive ${name}.`);
  return value;
}
function dataBytes(uri, limit) {
  if (typeof uri !== 'string' || !/^data:(?:image\/(?:png|jpeg|webp)|application\/(?:octet-stream|gltf-buffer));base64,/.test(uri)) fail('External avatar resources are not allowed. Export an embedded GLB.');
  const text = uri.slice(uri.indexOf(',') + 1), padding = text.endsWith('==') ? 2 : text.endsWith('=') ? 1 : 0;
  if (text.length % 4 || text.length / 4 * 3 - padding > limit || /[^A-Za-z0-9+/]/.test(text.slice(0, text.length - padding))) fail('Invalid embedded resource.');
  return Uint8Array.from(atob(text), char => char.charCodeAt(0));
}

// Read dimensions before handing compressed pixels to the browser decoder.
export function imageDimensions(bytes) {
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), n = bytes.length;
  if (n >= 24 && v.getUint32(0) === 0x89504e47 && v.getUint32(4) === 0x0d0a1a0a && v.getUint32(8) === 13 && v.getUint32(12) === 0x49484452) return [v.getUint32(16), v.getUint32(20)];
  if (n >= 4 && bytes[0] === 255 && bytes[1] === 216) {
    let offset = 2;
    while (offset < n) {
      if (bytes[offset++] !== 255) break;
      while (offset < n && bytes[offset] === 255) offset++;
      const marker = bytes[offset++];
      if (marker === 217 || marker === 218) break;
      if (marker === 1 || (marker >= 208 && marker <= 215)) continue;
      if (offset + 2 > n) break;
      const length = v.getUint16(offset);
      if (length < 2 || offset + length > n) break;
      if ([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)) {
        if (length < 8) break;
        return [v.getUint16(offset + 5), v.getUint16(offset + 3)];
      }
      offset += length;
    }
  }
  if (n >= 25 && v.getUint32(0) === 0x52494646 && v.getUint32(8) === 0x57454250 && v.getUint32(4, true) + 8 <= n) {
    const tag = v.getUint32(12), chunkSize = v.getUint32(16, true);
    if (chunkSize > n - 20) fail('Truncated WebP image chunk.');
    if (tag === 0x56503858 && n >= 30 && chunkSize >= 10) {
      if (bytes[20] & 2) fail('Animated WebP textures are not supported.');
      return [1 + bytes[24] + (bytes[25] << 8) + (bytes[26] << 16), 1 + bytes[27] + (bytes[28] << 8) + (bytes[29] << 16)];
    }
    if (tag === 0x5650384c && chunkSize >= 5 && bytes[20] === 47) {
      const bits = v.getUint32(21, true); return [1 + (bits & 16383), 1 + ((bits >>> 14) & 16383)];
    }
    if (tag === 0x56503820 && n >= 30 && chunkSize >= 10 && bytes[23] === 157 && bytes[24] === 1 && bytes[25] === 42) return [v.getUint16(26, true) & 16383, v.getUint16(28, true) & 16383];
  }
  fail('Unsupported or malformed image header.');
}

function checkNodes(nodes) {
  const parents = new Int32Array(nodes.length).fill(-1), children = nodes.map((node, index) => {
    const ids = node.children ?? [];
    if (!Array.isArray(ids)) fail('Invalid node children.');
    for (const child of ids) {
      if (!integer(child) || child >= nodes.length || parents[child] !== -1) fail('Invalid node reference or multiple parents.');
      parents[child] = index;
    }
    if (node.weights?.length > 256) fail('Excessive node morph weights.');
    for (const key of ['matrix', 'translation', 'rotation', 'scale', 'weights']) {
      if (node[key] !== undefined && (!Array.isArray(node[key]) || node[key].some(x => !Number.isFinite(x)))) fail('Non-finite node transform.');
    }
    return ids;
  });
  const pending = [];
  for (let i = 0; i < nodes.length; i++) if (parents[i] === -1) pending.push([i, 1]);
  let visited = 0;
  while (pending.length) {
    const [id, depth] = pending.pop();
    if (depth > IMPORT_LIMITS.depth) fail('Avatar node depth exceeds the supported limit.');
    visited++;
    for (const child of children[id]) pending.push([child, depth + 1]);
  }
  if (visited !== nodes.length) fail('Avatar node graph contains a cycle.');
}

export function inspectGLB(buffer, sourceLimit) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 20 || buffer.byteLength > sourceLimit) fail('Choose a self-contained GLB smaller than 30 MiB.');
  const view = new DataView(buffer);
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== buffer.byteLength) fail('This is not a valid glTF 2 GLB file.');
  let offset = 12, json, binary, chunks = 0;
  while (offset < buffer.byteLength) {
    if (offset + 8 > buffer.byteLength) fail('Truncated GLB chunk header.');
    const length = view.getUint32(offset, true), type = view.getUint32(offset + 4, true); offset += 8;
    if (length % 4 || length > buffer.byteLength - offset) fail('Invalid GLB chunk length.');
    if (chunks === 0 && type !== 0x4e4f534a) fail('The first GLB chunk must be JSON.');
    if (type === 0x4e4f534a) {
      if (length > 4 * 1024 * 1024) fail('GLB JSON metadata exceeds the supported limit.');
      if (chunks !== 0) fail('Duplicate GLB JSON chunk.');
      try { json = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(new Uint8Array(buffer, offset, length)).trim()); }
      catch { fail('Invalid GLB JSON chunk.'); }
    } else if (type === 0x004e4942) {
      if (binary || chunks !== 1) fail('Invalid GLB binary chunk order.');
      binary = new Uint8Array(buffer, offset, length);
    }
    chunks++; offset += length;
  }
  if (!json || typeof json !== 'object' || Array.isArray(json) || json.asset?.version !== '2.0' || (json.asset.minVersion !== undefined && json.asset.minVersion !== '2.0')) fail('Unsupported glTF asset version.');
  const pending = [[json, 0]];
  while (pending.length) {
    const [value, depth] = pending.pop();
    if (depth > 64) fail('GLB JSON metadata is nested too deeply.');
    if (typeof value === 'number' && !Number.isFinite(value)) fail('Non-finite GLB numeric metadata.');
    if (value && typeof value === 'object') for (const child of Object.values(value)) pending.push([child, depth + 1]);
  }
  const images = list(json.images, 'images', 128), buffers = list(json.buffers, 'buffers', 16);
  // Reject remote URIs before any resource processing or native decoding.
  for (const item of [...images, ...buffers]) if (item.uri !== undefined && (typeof item.uri !== 'string' || !item.uri.startsWith('data:'))) fail('External avatar resources are not allowed. Export an embedded GLB.');
  const required = json.extensionsRequired ?? [];
  if (!Array.isArray(required) || required.some(x => !SUPPORTED.has(x))) fail('This avatar requires unsupported extensions. Export an uncompressed GLB.');
  checkNodes(list(json.nodes, 'nodes', IMPORT_LIMITS.nodes));
  for (const name of ['meshes', 'materials', 'skins', 'animations', 'textures', 'scenes']) list(json[name], name, 2048);
  let primitives = 0;
  for (const mesh of json.meshes ?? []) {
    if (mesh.weights !== undefined && (!Array.isArray(mesh.weights) || mesh.weights.length > 256 || mesh.weights.some(x => !Number.isFinite(x)))) fail('Invalid or excessive mesh morph weights.');
    const entries = list(mesh.primitives, 'mesh primitives', 256);
    if (!entries.length || (primitives += entries.length) > 4096) fail('Invalid or excessive mesh primitives.');
    for (const entry of entries) if (entry.targets !== undefined) list(entry.targets, 'morph targets', 256);
  }
  let bufferBytes = 0;
  const data = buffers.map((item, i) => {
    if (!integer(item.byteLength, 1) || (bufferBytes += item.byteLength) > sourceLimit) fail('Invalid embedded buffer size.');
    const bytes = item.uri === undefined ? (i === 0 ? binary : undefined) : dataBytes(item.uri, sourceLimit);
    if (!bytes || bytes.length < item.byteLength || (item.uri === undefined && bytes.length - item.byteLength > 3)) fail('GLB binary buffer does not match its declared size.');
    return bytes.subarray(0, item.byteLength);
  });
  const views = list(json.bufferViews, 'buffer views', 8192).map(item => {
    if (!integer(item.buffer)) fail('A buffer view has no valid buffer index. Re-export as standard glTF 2 GLB.');
    const bytes = data[item.buffer], start = item.byteOffset ?? 0;
    if (!integer(item.buffer) || !bytes || !integer(start) || !integer(item.byteLength, 1) || start + item.byteLength > bytes.length) fail('Invalid buffer view bounds.');
    if (item.byteStride !== undefined && (!integer(item.byteStride, 4) || item.byteStride > 252 || item.byteStride % 4)) fail('Invalid buffer view stride.');
    return {bytes: bytes.subarray(start, start + item.byteLength), stride: item.byteStride};
  });
  let geometryBytes = 0;
  const span = (index, start, count, size, stride = size) => {
    const entry = views[index];
    if (!integer(index) || !entry || !integer(start) || stride < size || start + (count - 1) * stride + size > entry.bytes.length) fail('Accessor exceeds buffer view bounds.');
  };
  for (const accessor of list(json.accessors, 'accessors', 8192)) {
    const component = COMPONENT_BYTES[accessor.componentType], count = accessor.count, size = COMPONENTS[accessor.type] * component;
    if (!component || !size || !integer(count, 1) || (geometryBytes += count * size * (accessor.sparse ? 2 : 1)) > IMPORT_LIMITS.decodedGeometry) fail('Decoded accessor memory exceeds the supported limit.');
    if (accessor.type.startsWith('MAT') && component < 4 && Number(accessor.type.slice(3)) * component % 4) fail('Padded compact matrix accessors are not supported by this importer.');
    if ((accessor.byteOffset ?? 0) % component) fail('Misaligned accessor byte offset.');
    if (accessor.bufferView !== undefined) span(accessor.bufferView, accessor.byteOffset ?? 0, count, size, views[accessor.bufferView]?.stride ?? size);
    if (accessor.sparse !== undefined) {
      const sparse = accessor.sparse, indexSize = COMPONENT_BYTES[sparse?.indices?.componentType];
      if (!sparse || !integer(sparse.count, 1) || sparse.count > count || ![5121,5123,5125].includes(sparse.indices?.componentType) || !sparse.values) fail('Invalid sparse accessor.');
      span(sparse.indices.bufferView, sparse.indices.byteOffset ?? 0, sparse.count, indexSize);
      span(sparse.values.bufferView, sparse.values.byteOffset ?? 0, sparse.count, size);
      if ((sparse.indices.byteOffset ?? 0) % indexSize || (sparse.values.byteOffset ?? 0) % component) fail('Misaligned sparse accessor.');
      const bytes = views[sparse.indices.bufferView].bytes;
      const indexView = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      let previous = -1;
      for (let i = 0; i < sparse.count; i++) {
        const offset = (sparse.indices.byteOffset ?? 0) + i * indexSize;
        const index = indexSize === 1 ? indexView.getUint8(offset) : indexSize === 2 ? indexView.getUint16(offset, true) : indexView.getUint32(offset, true);
        if (index <= previous || index >= count) fail('Sparse accessor indices are not ordered or are out of range.');
        previous = index;
      }
    }
  }
  let pixels = 0;
  for (const image of images) {
    const bytes = image.uri !== undefined ? dataBytes(image.uri, sourceLimit) : views[image.bufferView]?.bytes;
    if (!bytes) fail('Invalid image buffer reference.');
    const [width, height] = imageDimensions(bytes);
    if (!width || !height || width > IMPORT_LIMITS.imageSide || height > IMPORT_LIMITS.imageSide || (pixels += width * height) > IMPORT_LIMITS.imagePixels) fail('Decoded image texture memory exceeds the supported limit.');
  }
  return json;
}
