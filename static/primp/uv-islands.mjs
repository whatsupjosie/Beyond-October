const edge = (a, b, x, y) => (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]);
const topLeft = (a, b) => b[1] < a[1] || (b[1] === a[1] && b[0] > a[0]);
const key = point => point.map(x => Math.round(x * 1e6)).join(',');

// Positions join only physically adjacent edges with identical texture endpoints.
// A material shared by separate meshes does not imply a continuous paint island.
export function buildIslandAtlas(triangles, size) {
  if (![1024, 2048].includes(size) || triangles.length > 100000) throw new Error('This paint atlas exceeds the supported detail or triangle budget.');
  const parent = Int32Array.from(triangles, (_, i) => i), edges = new Map();
  const find = i => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  for (let i = 0; i < triangles.length; i++) {
    const t = triangles[i];
    if (!t.uv.flat().every(Number.isFinite) || !t.positions.flat().every(Number.isFinite)) throw new Error('Invalid paint UV coordinates.');
    for (let e = 0; e < 3; e++) {
      const next = (e + 1) % 3;
      const a = key([...t.positions[e], ...t.uv[e]]), b = key([...t.positions[next], ...t.uv[next]]);
      const id = `${t.mesh}:${a < b ? a + ':' + b : b + ':' + a}`;
      if (edges.has(id)) parent[find(i)] = find(edges.get(id)); else edges.set(id, i);
    }
  }
  const roots = new Map(), charts = Int32Array.from(triangles, (_, i) => {
    const root = find(i); if (!roots.has(root)) roots.set(root, roots.size + 1); return roots.get(root);
  });
  const mask = new Int32Array(size * size), owner = new Int32Array(size * size).fill(-1);
  const blocked = new Set(), validFaces = new Uint8Array(triangles.length).fill(1), coverage = new Uint32Array(roots.size + 1);
  let work = 0;
  for (let i = 0; i < triangles.length; i++) {
    const id = charts[i];
    let points = triangles[i].uv.map(uv => uv.map(value => value * size));
    if (points.some(p => p.some(value => value < -1e-4 || value > size + 1e-4))) { validFaces[i] = 0; continue; }
    const area = edge(points[0], points[1], points[2][0], points[2][1]);
    if (Math.abs(area) < 1e-8) { validFaces[i] = 0; continue; }
    if (area < 0) points = [points[0], points[2], points[1]];
    const x0 = Math.max(0, Math.floor(Math.min(...points.map(p => p[0]))));
    const x1 = Math.min(size - 1, Math.ceil(Math.max(...points.map(p => p[0]))));
    const y0 = Math.max(0, Math.floor(Math.min(...points.map(p => p[1]))));
    const y1 = Math.min(size - 1, Math.ceil(Math.max(...points.map(p => p[1]))));
    work += (x1 - x0 + 1) * (y1 - y0 + 1);
    if (work > size * size * 64) throw new Error('UV overlap or rasterization work exceeds the paint budget. Prepare a unique UV layout.');
    const sides = points.map((a, e) => [a, points[(e + 1) % 3], topLeft(a, points[(e + 1) % 3])]);
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      if (!sides.every(([a, b, include]) => { const value = edge(a, b, x + .5, y + .5); return value > 1e-7 || (Math.abs(value) <= 1e-7 && include); })) continue;
      const pixel = y * size + x;
      if (owner[pixel] !== -1 && owner[pixel] !== i) {
        blocked.add(id); blocked.add(charts[owner[pixel]]); mask[pixel] = -1;
      } else { owner[pixel] = i; mask[pixel] = id; coverage[id]++; }
    }
  }
  return {size, charts, mask, blocked, validFaces, coverage, chartCount: roots.size};
}

// Preserve all pixels outside the selected island, including prior work there.
export function retainIsland(after, before, atlas, chart, left, top) {
  const {width, height, data} = after;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if (atlas.mask[(top + y) * atlas.size + left + x] === chart) continue;
    const pixel = (y * width + x) * 4;
    for (let c = 0; c < 4; c++) data[pixel + c] = before ? before.data[pixel + c] : 0;
  }
  return after;
}
