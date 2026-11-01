"use strict";

const state = {
  gl: null,
  program: null,
  floorProgram: null,
  avatar: null,
  avatarId: "manny",
  position: [0, 0, 0],
  heading: 0,
  keys: new Set(),
  lastTime: 0,
  log: [],
  manifest: null,
};

const $ = (id) => document.getElementById(id);

function log(message, level = "info") {
  const stamp = new Date().toLocaleTimeString([], {hour12: false});
  state.log.unshift(`${stamp}  ${message}`);
  state.log = state.log.slice(0, 60);
  $("walkLog").innerHTML = state.log.map(line => `<div class="${level}">${escapeHTML(line)}</div>`).join("");
}

function status(message, kind = "warn") {
  const el = $("walkStatus");
  el.textContent = message;
  el.className = kind;
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

async function fetchJSON(url) {
  const res = await fetch(url, {cache: "no-store"});
  if (!res.ok) throw new Error(`${url} HTTP ${res.status}`);
  return res.json();
}

async function fetchArrayBuffer(url) {
  const res = await fetch(url, {cache: "no-store"});
  if (!res.ok) throw new Error(`${url} HTTP ${res.status}`);
  return res.arrayBuffer();
}

function flattenManifest(manifest) {
  const out = {};
  for (const pack of manifest.packs || []) {
    for (const asset of pack.assets || []) out[asset.id] = asset;
  }
  return out;
}

function componentInfo(type) {
  const map = {
    5120: [Int8Array, 1],
    5121: [Uint8Array, 1],
    5122: [Int16Array, 2],
    5123: [Uint16Array, 2],
    5125: [Uint32Array, 4],
    5126: [Float32Array, 4],
  };
  return map[type];
}

function componentsFor(type) {
  return {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16}[type] || 1;
}

function accessorArray(gltf, bin, index) {
  const accessor = gltf.accessors[index];
  const view = gltf.bufferViews[accessor.bufferView];
  const [Ctor, bytes] = componentInfo(accessor.componentType);
  const comps = componentsFor(accessor.type);
  const stride = view.byteStride || comps * bytes;
  const base = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const count = accessor.count;
  const normalized = !!accessor.normalized;
  const values = new Float32Array(count * comps);
  const dv = new DataView(bin, base, (view.byteLength || 0) - (accessor.byteOffset || 0));
  for (let i = 0; i < count; i++) {
    for (let c = 0; c < comps; c++) {
      const off = i * stride + c * bytes;
      let v;
      if (Ctor === Float32Array) v = dv.getFloat32(off, true);
      else if (Ctor === Uint32Array) v = dv.getUint32(off, true);
      else if (Ctor === Uint16Array) v = dv.getUint16(off, true);
      else if (Ctor === Int16Array) v = dv.getInt16(off, true);
      else if (Ctor === Uint8Array) v = dv.getUint8(off);
      else v = dv.getInt8(off);
      if (normalized) {
        if (Ctor === Uint8Array) v = v / 255;
        else if (Ctor === Uint16Array) v = v / 65535;
        else if (Ctor === Int8Array) v = Math.max(v / 127, -1);
        else if (Ctor === Int16Array) v = Math.max(v / 32767, -1);
      }
      values[i * comps + c] = v;
    }
  }
  return {values, count, comps, componentType: accessor.componentType};
}

function accessorIndices(gltf, bin, index) {
  const accessor = gltf.accessors[index];
  const view = gltf.bufferViews[accessor.bufferView];
  const [Ctor, bytes] = componentInfo(accessor.componentType);
  const base = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const count = accessor.count;
  const values = new Uint32Array(count);
  const dv = new DataView(bin, base, (view.byteLength || 0) - (accessor.byteOffset || 0));
  for (let i = 0; i < count; i++) {
    const off = i * bytes;
    values[i] = Ctor === Uint32Array ? dv.getUint32(off, true) : Ctor === Uint16Array ? dv.getUint16(off, true) : dv.getUint8(off);
  }
  return values;
}

function parseGLB(buffer) {
  const dv = new DataView(buffer);
  if (String.fromCharCode(...new Uint8Array(buffer, 0, 4)) !== "glTF") throw new Error("Not a GLB/glTF binary");
  const version = dv.getUint32(4, true);
  if (version !== 2) throw new Error(`Unsupported GLB version ${version}`);
  const length = dv.getUint32(8, true);
  let off = 12;
  let gltf = null;
  let bin = null;
  while (off < length) {
    const chunkLength = dv.getUint32(off, true);
    const chunkType = String.fromCharCode(...new Uint8Array(buffer, off + 4, 4));
    off += 8;
    const chunk = buffer.slice(off, off + chunkLength);
    off += chunkLength;
    if (chunkType === "JSON") gltf = JSON.parse(new TextDecoder().decode(chunk).replace(/\0+$/, ""));
    if (chunkType === "BIN\0") bin = chunk;
  }
  if (!gltf || !bin) throw new Error("GLB missing JSON or BIN chunk");
  const mesh = gltf.meshes?.[0];
  const primitive = mesh?.primitives?.[0];
  if (!primitive?.attributes?.POSITION) throw new Error("GLB has no POSITION mesh data");
  const pos = accessorArray(gltf, bin, primitive.attributes.POSITION);
  const col = primitive.attributes.COLOR_0 !== undefined ? accessorArray(gltf, bin, primitive.attributes.COLOR_0) : null;
  const idx = primitive.indices !== undefined ? accessorIndices(gltf, bin, primitive.indices) : null;
  const vertices = [];
  let min = [Infinity, Infinity, Infinity];
  let max = [-Infinity, -Infinity, -Infinity];
  const pushVertex = (vi) => {
    const x = pos.values[vi * 3], y = pos.values[vi * 3 + 1], z = pos.values[vi * 3 + 2];
    min = [Math.min(min[0], x), Math.min(min[1], y), Math.min(min[2], z)];
    max = [Math.max(max[0], x), Math.max(max[1], y), Math.max(max[2], z)];
    vertices.push(x, y, z);
    if (col) {
      vertices.push(col.values[vi * col.comps] ?? 0.35, col.values[vi * col.comps + 1] ?? 0.9, col.values[vi * col.comps + 2] ?? 1.0);
    } else {
      vertices.push(0.1, 0.85, 1.0);
    }
  };
  if (idx) {
    for (const vi of idx) pushVertex(vi);
  } else {
    for (let vi = 0; vi < pos.count; vi++) pushVertex(vi);
  }
  return {
    name: mesh?.name || "Unnamed GLB",
    vertices: new Float32Array(vertices),
    vertexCount: vertices.length / 6,
    min, max,
    skins: gltf.skins?.length || 0,
    nodes: gltf.nodes?.length || 0,
    animations: (gltf.animations || []).map(a => a.name || "unnamed"),
  };
}

function shader(gl, type, source) {
  const s = gl.createShader(type);
  gl.shaderSource(s, source);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}

function program(gl, vs, fs) {
  const p = gl.createProgram();
  gl.attachShader(p, shader(gl, gl.VERTEX_SHADER, vs));
  gl.attachShader(p, shader(gl, gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}

function mat4Identity() { return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]; }
function mat4Multiply(a, b) {
  const o = new Array(16).fill(0);
  for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) for (let k = 0; k < 4; k++) o[c*4+r] += a[k*4+r] * b[c*4+k];
  return o;
}
function mat4Perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return [f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,(2*far*near)*nf,0];
}
function vec3Normalize(v) { const l = Math.hypot(v[0],v[1],v[2]) || 1; return [v[0]/l,v[1]/l,v[2]/l]; }
function vec3Cross(a,b) { return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }
function vec3Dot(a,b) { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
function mat4LookAt(eye, center, up) {
  const z = vec3Normalize([eye[0]-center[0], eye[1]-center[1], eye[2]-center[2]]);
  const x = vec3Normalize(vec3Cross(up, z));
  const y = vec3Cross(z, x);
  return [x[0],y[0],z[0],0, x[1],y[1],z[1],0, x[2],y[2],z[2],0, -vec3Dot(x,eye),-vec3Dot(y,eye),-vec3Dot(z,eye),1];
}
function mat4Translate(m, v) {
  const t = mat4Identity(); t[12]=v[0]; t[13]=v[1]; t[14]=v[2];
  return mat4Multiply(m, t);
}
function mat4Scale(m, s) {
  const t = mat4Identity(); t[0]=s[0]; t[5]=s[1]; t[10]=s[2];
  return mat4Multiply(m, t);
}
function mat4RotateY(m, a) {
  const c=Math.cos(a), s=Math.sin(a);
  return mat4Multiply(m, [c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]);
}

function makeFloor() {
  const verts = [];
  const size = 10;
  for (let i = -size; i <= size; i++) {
    verts.push(-size,0,i, 0.18,0.7,0.8, size,0,i, 0.18,0.7,0.8);
    verts.push(i,0,-size, 0.5,0.35,0.12, i,0,size, 0.5,0.35,0.12);
  }
  return new Float32Array(verts);
}

function createBuffer(gl, data) {
  const b = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  return b;
}

function setupGL() {
  const canvas = $("walkCanvas");
  const gl = canvas.getContext("webgl", {antialias: true});
  if (!gl) throw new Error("WebGL unavailable in this browser");
  state.gl = gl;
  const vs = `
    attribute vec3 aPosition;
    attribute vec3 aColor;
    uniform mat4 uMVP;
    varying vec3 vColor;
    void main(){ gl_Position = uMVP * vec4(aPosition, 1.0); vColor = aColor; }
  `;
  const fs = `
    precision mediump float;
    varying vec3 vColor;
    void main(){ gl_FragColor = vec4(vColor, 1.0); }
  `;
  state.program = program(gl, vs, fs);
  state.floorBuffer = createBuffer(gl, makeFloor());
  state.floorCount = makeFloor().length / 6;
  gl.enable(gl.DEPTH_TEST);
  gl.clearColor(0.015, 0.012, 0.01, 1);
}

async function loadAvatar(id) {
  const assets = flattenManifest(state.manifest);
  const asset = assets[id];
  if (!asset) throw new Error(`Avatar '${id}' is not in manifest`);
  if (asset.sprite_replacement_allowed !== false || asset.asset_type !== "glb") throw new Error(`${id} is not marked as protected GLB performer asset`);
  status(`Loading ${asset.display_name || asset.name} GLB`, "warn");
  const buffer = await fetchArrayBuffer(asset.url);
  const parsed = parseGLB(buffer);
  const gl = state.gl;
  state.avatar = {
    ...parsed,
    asset,
    buffer: createBuffer(gl, parsed.vertices),
  };
  const height = parsed.max[1] - parsed.min[1] || 1;
  state.avatar.scale = 1.8 / height;
  state.position = [0, 0, 0];
  state.heading = 0;
  $("avatarMeta").textContent = `${asset.display_name || asset.name}: ${parsed.name} | nodes ${parsed.nodes} | skins ${parsed.skins} | animations ${parsed.animations.length ? parsed.animations.join(", ") : "none embedded"}`;
  status(`${asset.display_name || asset.name} loaded as real GLB performer asset`, "ok");
  log(`${asset.display_name || asset.name} GLB loaded; no sprite replacement`);
}

function drawBuffer(buffer, count, mvp, mode) {
  const gl = state.gl, p = state.program;
  gl.useProgram(p);
  gl.uniformMatrix4fv(gl.getUniformLocation(p, "uMVP"), false, new Float32Array(mvp));
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  const stride = 6 * 4;
  const aPos = gl.getAttribLocation(p, "aPosition");
  const aCol = gl.getAttribLocation(p, "aColor");
  gl.enableVertexAttribArray(aPos);
  gl.enableVertexAttribArray(aCol);
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, stride, 0);
  gl.vertexAttribPointer(aCol, 3, gl.FLOAT, false, stride, 3 * 4);
  gl.drawArrays(mode, 0, count);
}

function update(dt) {
  const speed = state.keys.has("Shift") ? 3.2 : 1.6;
  let dx = 0, dz = 0;
  if (state.keys.has("w") || state.keys.has("ArrowUp")) dz -= 1;
  if (state.keys.has("s") || state.keys.has("ArrowDown")) dz += 1;
  if (state.keys.has("a") || state.keys.has("ArrowLeft")) dx -= 1;
  if (state.keys.has("d") || state.keys.has("ArrowRight")) dx += 1;
  if (dx || dz) {
    const len = Math.hypot(dx, dz);
    dx /= len; dz /= len;
    state.position[0] += dx * speed * dt;
    state.position[2] += dz * speed * dt;
    state.heading = Math.atan2(dx, dz);
    $("avatarPosition").textContent = `x ${state.position[0].toFixed(2)} | y 0.00 | z ${state.position[2].toFixed(2)}`;
  }
}

function render(now) {
  const gl = state.gl;
  const dt = Math.min(0.05, ((now || 0) - state.lastTime) / 1000 || 0);
  state.lastTime = now || 0;
  update(dt);
  gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  const aspect = gl.canvas.width / gl.canvas.height;
  const proj = mat4Perspective(Math.PI / 3, aspect, 0.1, 80);
  const eye = [state.position[0] + 3.4, 2.4, state.position[2] + 6.2];
  const view = mat4LookAt(eye, [state.position[0], 0.9, state.position[2]], [0,1,0]);
  const vp = mat4Multiply(proj, view);
  drawBuffer(state.floorBuffer, state.floorCount, vp, gl.LINES);
  if (state.avatar) {
    const center = [
      (state.avatar.min[0] + state.avatar.max[0]) / 2,
      state.avatar.min[1],
      (state.avatar.min[2] + state.avatar.max[2]) / 2,
    ];
    let model = mat4Identity();
    model = mat4Translate(model, state.position);
    model = mat4RotateY(model, state.heading);
    model = mat4Scale(model, [state.avatar.scale, state.avatar.scale, state.avatar.scale]);
    model = mat4Translate(model, [-center[0], -center[1], -center[2]]);
    drawBuffer(state.avatar.buffer, state.avatar.vertexCount, mat4Multiply(vp, model), gl.TRIANGLES);
  }
  requestAnimationFrame(render);
}

async function init() {
  setupGL();
  state.manifest = await fetchJSON("/data/avatars/manifest.json").catch(async () => fetchJSON("../data/avatars/manifest.json"));
  const assets = flattenManifest(state.manifest);
  $("avatarSelect").innerHTML = Object.values(assets).map(a => `<option value="${escapeHTML(a.id)}">${escapeHTML(a.display_name || a.name || a.id)}</option>`).join("");
  $("avatarSelect").value = "manny";
  $("avatarSelect").onchange = () => loadAvatar($("avatarSelect").value).catch(err => { status(err.message, "bad"); log(err.message, "bad"); });
  $("resetAvatar").onclick = () => {
    state.position = [0,0,0];
    state.heading = 0;
    $("avatarPosition").textContent = "x 0.00 | y 0.00 | z 0.00";
    log("avatar reset to floor origin");
  };
  addEventListener("keydown", ev => {
    if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(ev.key)) ev.preventDefault();
    state.keys.add(ev.key.length === 1 ? ev.key.toLowerCase() : ev.key);
  });
  addEventListener("keyup", ev => state.keys.delete(ev.key.length === 1 ? ev.key.toLowerCase() : ev.key));
  await loadAvatar("manny");
  requestAnimationFrame(render);
}

init().catch(err => {
  status(err.message, "bad");
  log(`avatar walk proof failed visibly: ${err.message}`, "bad");
});
