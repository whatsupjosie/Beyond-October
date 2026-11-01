// Foresight Matter — physically based material renderer for the Foresight Counter.
//
// Paints workshop-bench trays pixel by pixel: a raised rim (gold, brass,
// copper, silver, wood) around a recessed floor (marble, granite, sandstone,
// wood, nacre, tortoiseshell, tinted glass), lit by ONE key light shared by
// the whole Counter, with environment reflections, ambient occlusion and a
// cast shadow onto the bench.
//
// Builds two ways from this one file:
//   * WebAssembly (clang --target=wasm32, freestanding) for the browser page
//   * native (g++ -DFM_NATIVE) for preview sheets and tests
//
// The shape is a signed distance field, so the frame always surrounds the
// tray's content rectangle and only ever bulges outward from it.

#include <stdint.h>

#if defined(FM_NATIVE)
#  define FM_EXPORT(name) extern "C"
#else
#  define FM_EXPORT(name) extern "C" __attribute__((export_name(name)))
#endif

namespace fm {

// ───────────────────────────── math (freestanding) ─────────────────────────────
constexpr float PI = 3.14159265358979f;
static inline float fabs_(float x) { return __builtin_fabsf(x); }
static inline float sqrt_(float x) { return __builtin_sqrtf(x > 0.f ? x : 0.f); }
static inline float floor_(float x) { return __builtin_floorf(x); }
static inline float min_(float a, float b) { return a < b ? a : b; }
static inline float max_(float a, float b) { return a > b ? a : b; }
static inline float clamp(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float sat(float x) { return clamp(x, 0.f, 1.f); }
static inline float mix(float a, float b, float t) { return a + (b - a) * t; }
static inline float fract(float x) { return x - floor_(x); }
static inline float smoothstep(float a, float b, float x) {
  float t = sat((x - a) / (b - a)); return t * t * (3.f - 2.f * t);
}
// sin/cos: reduce to [-pi, pi], then an odd 9th-order minimax polynomial.
static inline float sin_(float x) {
  x = x - 2.f * PI * floor_((x + PI) / (2.f * PI));
  float x2 = x * x;
  return x * (1.f + x2 * (-0.16666667f + x2 * (0.0083333310f + x2 * (-0.00019840874f + x2 * 2.7525562e-6f))));
}
static inline float cos_(float x) { return sin_(x + PI * 0.5f); }
// exp2/log2 via IEEE bit manipulation plus polynomial refinement.
static inline float exp2_(float x) {
  x = clamp(x, -126.f, 126.f);
  float fi = floor_(x), f = x - fi;
  float p = 1.f + f * (0.6931472f + f * (0.2402265f + f * (0.0555041f + f * (0.0096181f + f * 0.0013334f))));
  union { float f; int32_t i; } u; u.i = (int32_t)((fi + 127.f)) << 23; return u.f * p;
}
static inline float log2_(float x) {
  if (x <= 0.f) return -126.f;
  union { float f; int32_t i; } u; u.f = x;
  float e = (float)(((u.i >> 23) & 255) - 127);
  u.i = (u.i & 0x007FFFFF) | 0x3F800000;               // mantissa in [1,2)
  float m = u.f - 1.f;
  return e + m * (1.4425449f + m * (-0.7181452f + m * (0.4575485f + m * (-0.2779042f + m * (0.1217970f + m * (-0.0258411f))))));
}
static inline float pow_(float b, float e) { return b <= 0.f ? 0.f : exp2_(e * log2_(b)); }
static inline float exp_(float x) { return exp2_(x * 1.4426950f); }
static inline float atan2_(float y, float x) {
  float ax = fabs_(x), ay = fabs_(y);
  float a = min_(ax, ay) / (max_(ax, ay) + 1e-12f), s = a * a;
  float r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
  if (ay > ax) r = 1.57079637f - r;
  if (x < 0.f) r = PI - r;
  return y < 0.f ? -r : r;
}

struct v2 { float x, y; };
struct v3 { float x, y, z; };
static inline v2 V2(float x, float y) { return {x, y}; }
static inline v3 V3(float x, float y, float z) { return {x, y, z}; }
static inline v2 operator+(v2 a, v2 b) { return {a.x + b.x, a.y + b.y}; }
static inline v2 operator-(v2 a, v2 b) { return {a.x - b.x, a.y - b.y}; }
static inline v2 operator*(v2 a, float s) { return {a.x * s, a.y * s}; }
static inline float dot(v2 a, v2 b) { return a.x * b.x + a.y * b.y; }
static inline float len(v2 a) { return sqrt_(dot(a, a)); }
static inline v3 operator+(v3 a, v3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
static inline v3 operator-(v3 a, v3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
static inline v3 operator*(v3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
static inline v3 operator*(v3 a, v3 b) { return {a.x * b.x, a.y * b.y, a.z * b.z}; }
static inline float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline v3 norm(v3 a) { float l = sqrt_(dot(a, a)); return l > 0.f ? a * (1.f / l) : a; }
static inline v3 mix(v3 a, v3 b, float t) { return a + (b - a) * t; }
static inline v3 rgb(int hex) { return V3(((hex >> 16) & 255) / 255.f, ((hex >> 8) & 255) / 255.f, (hex & 255) / 255.f); }
static inline v3 lin(v3 c) { return V3(pow_(c.x, 2.2f), pow_(c.y, 2.2f), pow_(c.z, 2.2f)); }   // sRGB -> linear

// ───────────────────────────── noise ─────────────────────────────
static inline uint32_t hash_u(int32_t x, int32_t y, uint32_t s) {
  uint32_t h = (uint32_t)x * 0x8da6b343u ^ (uint32_t)y * 0xd8163841u ^ s * 0xcb1ab31fu;
  h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15; return h;
}
static inline float hash(int32_t x, int32_t y, uint32_t s) { return (hash_u(x, y, s) & 0xFFFFFF) / 16777216.f; }
static inline float vnoise(float x, float y, uint32_t s) {
  float fx = floor_(x), fy = floor_(y); int32_t ix = (int32_t)fx, iy = (int32_t)fy;
  float tx = x - fx, ty = y - fy;
  float ux = tx * tx * tx * (tx * (tx * 6.f - 15.f) + 10.f), uy = ty * ty * ty * (ty * (ty * 6.f - 15.f) + 10.f);
  float a = hash(ix, iy, s), b = hash(ix + 1, iy, s), c = hash(ix, iy + 1, s), d = hash(ix + 1, iy + 1, s);
  return mix(mix(a, b, ux), mix(c, d, ux), uy);
}
static inline float fbm(float x, float y, int oct, uint32_t s) {
  float v = 0.f, a = 0.5f, n = 0.f;
  for (int i = 0; i < oct; ++i) { v += a * vnoise(x, y, s + i * 101u); n += a; float nx = 1.6f * x + 1.2f * y, ny = -1.2f * x + 1.6f * y; x = nx + 3.1f; y = ny + 1.7f; a *= 0.5f; }
  return v / n;
}
static inline float ridged(float x, float y, int oct, uint32_t s) {
  float v = 0.f, a = 0.5f, n = 0.f;
  for (int i = 0; i < oct; ++i) { float r = 1.f - fabs_(2.f * vnoise(x, y, s + i * 71u) - 1.f); v += a * r * r; n += a; float nx = 1.7f * x + 1.1f * y, ny = -1.1f * x + 1.7f * y; x = nx + 5.3f; y = ny + 2.9f; a *= 0.5f; }
  return v / n;
}
// Cellular (Worley) distance to nearest feature point; returns F1 and the cell's id hash.
static inline float worley(float x, float y, uint32_t s, float* id) {
  int32_t ix = (int32_t)floor_(x), iy = (int32_t)floor_(y); float best = 9.f; float bid = 0.f;
  for (int j = -1; j <= 1; ++j) for (int i = -1; i <= 1; ++i) {
    float px = ix + i + hash(ix + i, iy + j, s), py = iy + j + hash(ix + i, iy + j, s + 7u);
    float dx = px - x, dy = py - y, d = dx * dx + dy * dy;
    if (d < best) { best = d; bid = hash(ix + i, iy + j, s + 13u); }
  }
  if (id) *id = bid;
  return sqrt_(best);
}

// ───────────────────────────── shapes (signed distance) ─────────────────────────────
enum Shape : int { ROUNDRECT = 0, CHAMFER = 1, GEM = 2, LONGHEX = 3, ELLIPSE = 4, SHELL = 5, PETAL = 6, PILL = 7, CUSHION = 8, ARCH = 9 };

static float sdPolygon(v2 p, const v2* v, int n) {
  float d = dot(p - v[0], p - v[0]); float s = 1.f;
  for (int i = 0, j = n - 1; i < n; j = i, ++i) {
    v2 e = v[j] - v[i], w = p - v[i];
    v2 b = w - e * clamp(dot(w, e) / dot(e, e), 0.f, 1.f);
    d = min_(d, dot(b, b));
    bool c1 = p.y >= v[i].y, c2 = p.y < v[j].y, c3 = e.x * w.y > e.y * w.x;
    if ((c1 && c2 && c3) || (!c1 && !c2 && !c3)) s = -s;
  }
  return s * sqrt_(d);
}
static float sdRoundBox(v2 p, float hx, float hy, float r) {
  float qx = fabs_(p.x) - hx + r, qy = fabs_(p.y) - hy + r;
  return len(V2(max_(qx, 0.f), max_(qy, 0.f))) + min_(max_(qx, qy), 0.f) - r;
}
// Polygon given in unit coordinates (-1..1), stretched to the half extents and
// rounded with radius r while staying inside the same outer bounds.
static float sdUnitPoly(v2 p, const float* uv, int n, float hx, float hy, float r) {
  v2 v[16]; float sx = hx - r, sy = hy - r;
  for (int i = 0; i < n; ++i) v[i] = V2(uv[2 * i] * sx, uv[2 * i + 1] * sy);
  return sdPolygon(p, v, n) - r;
}
static inline float smin(float a, float b, float k) { float h = sat(0.5f + 0.5f * (b - a) / k); return mix(b, a, h) - k * h * (1.f - h); }

struct ShapeSpec { int kind; float hx, hy, round, a, b; };

// Distance in pixels; negative inside. p is relative to the shape's center.
static float shapeSDF(const ShapeSpec& s, v2 p) {
  switch (s.kind) {
    case CHAMFER: {           // octagon with softened chamfers (tool tray)
      float c = clamp(s.a, 0.05f, 0.45f);
      float cx = 1.f - c * (s.hy / s.hx), cy = 1.f - c;
      const float u[16] = {-cx, -1, cx, -1, 1, -cy, 1, cy, cx, 1, -cx, 1, -1, cy, -1, -cy};
      return sdUnitPoly(p, u, 8, s.hx, s.hy, s.round);
    }
    case GEM: {               // irregular soft hexagon (preview / feature tray)
      const float u[12] = {-0.78f, -1, 0.80f, -1, 1, -0.08f, 0.76f, 1, -0.82f, 1, -1, 0.10f};
      return sdUnitPoly(p, u, 6, s.hx, s.hy, s.round);
    }
    case LONGHEX: {           // elongated hexagon
      float k = clamp(s.a, 0.05f, 0.4f);
      const float u[12] = {-1 + k, -1, 1 - k, -1, 1, 0, 1 - k, 1, -1 + k, 1, -1, 0};
      return sdUnitPoly(p, u, 6, s.hx, s.hy, s.round);
    }
    case ELLIPSE: {
      float rx = s.hx, ry = s.hy; v2 q = V2(p.x / rx, p.y / ry);
      float k = len(q); return (k - 1.f) * min_(rx, ry);
    }
    case SHELL: {             // scallop: fluted fan opening upward from a hinge at the bottom
      v2 hinge = V2(0.f, s.hy * 0.92f);
      v2 q = p - hinge; float r = len(q);
      float ang = atan2_(q.x, -q.y);                       // 0 = straight up
      float spread = clamp(s.a, 0.6f, 1.45f);              // half-angle in radians
      float R = min_(s.hy * 1.84f, s.hx / sin_(spread) * 0.98f);
      int ribs = (int)clamp(s.b, 5.f, 21.f);
      float lobe = fabs_(cos_(ang * ribs * 0.5f * PI / spread));
      float edge = R * (0.93f + 0.07f * pow_(lobe, 0.6f));
      float dRad = r - edge;
      float dAng = (fabs_(ang) - spread) * r;              // outside the fan's opening angle
      float body = max_(dRad, dAng);
      float ears = sdRoundBox(p - V2(0.f, s.hy * 0.80f), s.hx * 0.30f, s.hy * 0.12f, s.hy * 0.08f);
      return smin(body, ears, s.hy * 0.08f) ;
    }
    case PETAL: {             // fan blade: narrow at the pivot (left), broad rounded tip (right)
      float r1 = s.hy * 0.38f, r2 = s.hy;
      float h = 2.f * s.hx - r1 - r2;
      v2 q = V2(fabs_(p.y), p.x + s.hx - r1);          // capsule axis runs along +x from the pivot
      float bb = (r1 - r2) / h, a = sqrt_(1.f - bb * bb);
      float k = -bb * q.x + a * q.y;
      if (k < 0.f) return len(q) - r1;
      if (k > a * h) return len(q - V2(0.f, h)) - r2;
      return a * q.x + bb * q.y - r1;
    }
    case PILL: return sdRoundBox(p, s.hx, s.hy, min_(s.hx, s.hy));
    case CUSHION: {           // rounded rectangle whose sides bow gently outward
      float bow = s.a;
      float ex = s.hx * (1.f + bow * (1.f - (p.y / s.hy) * (p.y / s.hy)) * 0.04f);
      float ey = s.hy * (1.f + bow * (1.f - (p.x / s.hx) * (p.x / s.hx)) * 0.06f);
      return sdRoundBox(p, ex, ey, s.round);
    }
    case ARCH: {              // flat bottom, high rounded crown (cabinet / quick-access arch)
      float body = sdRoundBox(p - V2(0.f, s.hy * 0.25f), s.hx, s.hy * 0.75f, s.round);
      float crown = (len(V2(p.x / s.hx, (p.y + s.hy * 0.15f) / (s.hy * 0.85f))) - 1.f) * s.hy * 0.85f;
      return min_(body, crown);
    }
    default: return sdRoundBox(p, s.hx, s.hy, s.round);
  }
}

// ───────────────────────────── materials ─────────────────────────────
enum Mat : int {
  GOLD = 0, BRASS = 1, COPPER = 2, SILVER = 3, BRONZE = 4,
  MARBLE_WHITE = 10, MARBLE_ROSE = 11, MARBLE_GREEN = 12, MARBLE_BLACK = 13,
  GRANITE = 20, GRANITE_BLACK = 21,
  SANDSTONE = 30,
  WALNUT = 40, OAK = 41, MAHOGANY = 42,
  NACRE = 50, PEARL = 51,            // PEARL = Rearview Pearl (canonical Wallet palette)
  TORTOISE = 60,
  GLASS_AMETHYST = 70, GLASS_EMERALD = 71, GLASS_SAPPHIRE = 72, GLASS_SMOKE = 73,
  EMERALD_ENAMEL = 74, OBSIDIAN_LACQUER = 75,
  LEATHER = 80
};

struct Surface {
  v3 albedo;      // linear diffuse colour (dielectrics)
  v3 f0;          // specular reflectance at normal incidence
  float rough;    // perceptual roughness 0..1
  float metal;    // 1 = conductor
  float coat;     // clear-coat strength (polish / varnish)
  float bump;     // height for normal perturbation
  float sparkle;  // extra glint (mica, metal flake)
  float irid;     // thin-film iridescence (nacre)
};

static inline bool isMetal(int m) { return m >= GOLD && m <= BRONZE; }

// p: position in pixels (world, shared across the Counter so textures line up),
// tdir: unit tangent along the rim (for brushing), radial: angle around the shell hinge.
static Surface material(int m, v2 p, v2 tdir, float radial, uint32_t seed) {
  Surface s{}; s.f0 = V3(0.04f, 0.04f, 0.04f); s.rough = 0.5f; s.coat = 0.f; s.bump = 0.f; s.sparkle = 0.f; s.irid = 0.f; s.metal = 0.f;
  float x = p.x, y = p.y;
  if (isMetal(m)) {
    v3 c = m == GOLD ? V3(1.00f, 0.71f, 0.29f) : m == BRASS ? V3(0.91f, 0.74f, 0.40f)
         : m == COPPER ? V3(0.95f, 0.58f, 0.43f) : m == SILVER ? V3(0.97f, 0.96f, 0.92f) : V3(0.80f, 0.53f, 0.30f);
    // Brushing runs along the rim: noise stretched along the tangent.
    float along = x * tdir.x + y * tdir.y, across = -x * tdir.y + y * tdir.x;
    float brush = vnoise(along * 0.04f, across * 1.6f, seed + 3u);
    float wear = fbm(x * 0.012f, y * 0.012f, 4, seed + 9u);
    float tarnish = m == BRASS || m == BRONZE ? smoothstep(0.55f, 0.85f, wear) * 0.35f : (m == COPPER ? smoothstep(0.6f, 0.9f, wear) * 0.25f : 0.f);
    s.f0 = mix(c, c * V3(0.55f, 0.52f, 0.42f), tarnish);
    s.metal = 1.f;
    s.rough = clamp((m == GOLD ? 0.16f : m == SILVER ? 0.14f : 0.24f) + brush * 0.10f + tarnish * 0.3f, 0.05f, 0.9f);
    s.bump = brush * 0.25f;
    s.albedo = s.f0;
    return s;
  }
  if (m >= MARBLE_WHITE && m <= MARBLE_BLACK) {
    v3 base, vein, cloud;
    if (m == MARBLE_WHITE) { base = rgb(0xF2EEE6); vein = rgb(0x8C8478); cloud = rgb(0xD9D2C6); }
    else if (m == MARBLE_ROSE) { base = rgb(0xF3E4DA); vein = rgb(0xB0806C); cloud = rgb(0xE6C7B8); }
    else if (m == MARBLE_GREEN) { base = rgb(0x1E4B40); vein = rgb(0xC8DCCF); cloud = rgb(0x2F6A5A); }
    else { base = rgb(0x17181B); vein = rgb(0xE8E2D4); cloud = rgb(0x2A2B30); }
    float sc = 0.0042f;
    float warp = fbm(x * sc * 2.f, y * sc * 2.f, 6, seed);
    float t = sin_((x * 0.82f + y * 0.57f) * sc * 9.f + warp * 9.5f);
    float v1 = pow_(1.f - fabs_(t), 26.f);                         // fine main vein
    float t2 = sin_((x * -0.4f + y * 0.92f) * sc * 5.f + fbm(x * sc * 3.f, y * sc * 3.f, 5, seed + 41u) * 12.f);
    float v2v = pow_(1.f - fabs_(t2), 60.f) * 0.7f;                // secondary hairline veins
    float c = fbm(x * sc * 1.2f, y * sc * 1.2f, 5, seed + 77u);
    v3 col = mix(base, cloud, smoothstep(0.35f, 0.8f, c) * 0.55f);
    col = mix(col, vein, sat(v1 * 0.85f + v2v));
    s.albedo = lin(col); s.rough = 0.10f + c * 0.06f; s.coat = 0.85f; s.bump = (v1 + v2v) * 0.04f;
    return s;
  }
  if (m == GRANITE || m == GRANITE_BLACK) {
    float id1, id2, id3;
    float f1 = worley(x * 0.16f, y * 0.16f, seed, &id1);          // large crystals
    worley(x * 0.42f, y * 0.42f, seed + 5u, &id2);                // medium
    worley(x * 1.10f, y * 1.10f, seed + 9u, &id3);                // fine grain
    v3 col;
    if (m == GRANITE) {
      v3 quartz = rgb(0xD9D4CD), feld = rgb(0xD4A897), feld2 = rgb(0xB98476), bio = rgb(0x16151A), grey = rgb(0x8F8984);
      col = id1 < 0.30f ? quartz : id1 < 0.52f ? feld : id1 < 0.66f ? feld2 : id1 < 0.84f ? grey : bio;
      col = mix(col, id2 < 0.5f ? quartz : bio, (id2 > 0.78f || id2 < 0.12f) ? 0.85f : 0.f);
      col = mix(col, id3 < 0.5f ? grey : bio, id3 > 0.86f ? 0.7f : 0.f);
    } else {
      float j1, j2;
      worley(x * 0.24f, y * 0.24f, seed + 21u, &j1); worley(x * 0.7f, y * 0.7f, seed + 23u, &j2);
      v3 a = rgb(0x0B0C0F), b = rgb(0x1C1E23), c = rgb(0x3E414A), d = rgb(0x8A8E98);
      col = j1 < 0.58f ? a : j1 < 0.86f ? b : j1 < 0.97f ? c : d;
      col = mix(col, j2 < 0.6f ? a : c, j2 > 0.8f ? 0.7f : 0.f);
      id1 = 0.f;
      col = mix(col, id2 < 0.5f ? a : c, id2 > 0.85f ? 0.8f : 0.f);
      col = mix(col, d, id3 > 0.93f ? 0.6f : 0.f);
    }
    col = col * (0.9f + 0.18f * vnoise(x * 2.0f, y * 2.0f, seed + 2u));
    s.albedo = lin(col); s.rough = 0.10f; s.coat = 0.95f;
    s.bump = smoothstep(0.0f, 0.06f, f1) * 0.03f;
    s.sparkle = hash((int32_t)x, (int32_t)y, seed + 99u) > 0.996f ? 0.8f : 0.f;     // mica glints
    return s;
  }
  if (m == SANDSTONE) {
    float warp = fbm(x * 0.006f, y * 0.006f, 5, seed);
    float band = y * 0.035f + warp * 6.f + fbm(x * 0.02f, y * 0.02f, 3, seed + 3u) * 1.5f;
    float strata = 0.5f + 0.5f * sin_(band);
    float fine = 0.5f + 0.5f * sin_(band * 3.7f + 1.3f);
    v3 c1 = rgb(0xD8B38A), c2 = rgb(0xC08A5C), c3 = rgb(0xE6CBA6);
    v3 col = mix(mix(c1, c2, strata), c3, fine * 0.35f);
    float grain = hash((int32_t)x, (int32_t)y, seed + 8u);
    col = col * (0.86f + 0.22f * grain) * (0.9f + 0.2f * vnoise(x * 0.3f, y * 0.3f, seed + 4u));
    s.albedo = lin(col); s.rough = 0.88f; s.bump = grain * 0.35f + strata * 0.2f;
    return s;
  }
  if (m == WALNUT || m == OAK || m == MAHOGANY) {
    v3 light, dark;
    if (m == WALNUT) { light = rgb(0x6E4A30); dark = rgb(0x2E1C12); }
    else if (m == OAK) { light = rgb(0xB8925E); dark = rgb(0x6E4C2C); }
    else { light = rgb(0x7C3420); dark = rgb(0x3A140A); }
    // Planks run horizontally; each plank has its own tone and grain offset.
    float plankH = 118.f;
    float pi_ = floor_(y / plankH);
    float py_ = y - pi_ * plankH;
    float joint = floor_((x + hash((int32_t)pi_, 0, seed) * 900.f) / 1100.f);
    uint32_t ps = seed + (uint32_t)(pi_ * 31.f + joint * 7.f);
    float tone = hash((int32_t)pi_, (int32_t)joint, seed + 1u);
    // Long, fine fibres: anisotropic noise stretched along x.
    // Grain lines are nearly straight; they drift very slowly along the board.
    float drift = fbm(x * 0.0007f, pi_ * 3.1f, 3, ps + 5u) * 22.f + fbm(x * 0.003f, y * 0.004f, 2, ps + 8u) * 3.f;
    float gy = y + drift;
    float fib = fbm(x * 0.0015f, gy * 0.30f, 5, ps);               // fine fibre streaks
    float ring = fract(gy * 0.045f + fbm(x * 0.0006f, gy * 0.01f, 3, ps + 2u) * 2.2f + vnoise(x * 0.002f, gy * 0.05f, ps + 3u) * 0.25f);
    float late = smoothstep(0.55f, 0.95f, ring) * smoothstep(1.0f, 0.95f, ring);
    float figure = fbm(x * 0.0009f, gy * 0.012f, 3, ps + 11u);     // broad colour figure
    // Open pores: short dark dashes along the grain.
    float pore = smoothstep(0.82f, 0.9f, vnoise(x * 0.09f, gy * 1.6f, ps + 13u));
    v3 col = mix(light, dark, sat(late * 0.38f + (fib - 0.5f) * 0.22f + (figure - 0.5f) * 0.6f + 0.22f));
    col = col * (0.84f + 0.26f * tone) * (1.f - pore * 0.28f);
    float fib2 = fib;
    // Plank seams (long edges and butt joints) are dark, slightly recessed lines.
    float seamY = min_(py_, plankH - py_);
    float xj = x + hash((int32_t)pi_, 0, seed) * 900.f; float seamX = fabs_(xj - floor_(xj / 1100.f + 0.5f) * 1100.f);
    float seam = 1.f - smoothstep(0.f, 1.6f, min_(seamY, seamX));
    col = col * (1.f - seam * 0.75f);
    s.albedo = lin(col); s.rough = 0.38f + fib * 0.15f; s.coat = 0.55f;
    s.bump = late * 0.04f + fib2 * 0.03f - pore * 0.05f - seam * 0.8f;
    return s;
  }
  if (m == PEARL) {
    // Rearview Pearl: warm, diffuse, faintly iridescent satin — not plastic white.
    float n1 = fbm(x * 0.006f, y * 0.006f, 5, seed);
    float n2 = fbm(x * 0.03f, y * 0.03f, 3, seed + 2u);
    v3 warm = rgb(0xFAF7F0), mid = rgb(0xE9E6DF), cool = rgb(0xCFD9DF), blush = rgb(0xEBDCE6);
    v3 col = mix(mix(warm, mid, n1), cool, smoothstep(0.55f, 0.8f, n1) * 0.6f);
    col = mix(col, blush, smoothstep(0.6f, 0.85f, n2) * 0.35f);
    float sheen = fbm(x * 0.0025f + n1, y * 0.0025f, 3, seed + 5u);
    col = mix(col, cool, smoothstep(0.45f, 0.75f, sheen) * 0.45f);
    // Pearlescence: a soft thin-film colour shift that drifts across the surface.
    float ph = sheen * 1.8f + n1 * 0.9f;
    v3 film = V3(0.5f + 0.5f * cos_(6.283f * ph), 0.5f + 0.5f * cos_(6.283f * (ph + 0.33f)), 0.5f + 0.5f * cos_(6.283f * (ph + 0.67f)));
    col = col * (V3(0.86f, 0.86f, 0.86f) + film * 0.16f);
    s.albedo = lin(col); s.rough = 0.24f; s.coat = 0.6f; s.bump = n2 * 0.08f + sheen * 0.25f; s.irid = 0.4f;
    return s;
  }
  if (m == EMERALD_ENAMEL) {
    // Dense jewel enamel fired over a metal ground: deep green body, faint fused bubbles.
    float n1 = fbm(x * 0.004f, y * 0.004f, 4, seed);
    float id; float f = worley(x * 0.08f, y * 0.08f, seed + 3u, &id);
    float bubble = (1.f - smoothstep(0.0f, 0.12f, f)) * (id > 0.8f ? 1.f : 0.f);
    v3 col = mix(rgb(0x0B2A20), rgb(0x1C5A47), n1);
    col = col * (1.f + bubble * 0.25f);
    s.albedo = lin(col); s.rough = 0.05f; s.coat = 1.f; s.bump = -bubble * 0.15f;
    return s;
  }
  if (m == OBSIDIAN_LACQUER) {
    // Near-black lacquer with a deep clear coat; a warm depth glows faintly under it.
    float n1 = fbm(x * 0.003f, y * 0.003f, 4, seed);
    float orange = fbm(x * 0.05f, y * 0.05f, 2, seed + 7u);       // lacquer "orange peel"
    v3 col = mix(rgb(0x040507), rgb(0x150F0E), n1 * 0.6f);
    s.albedo = lin(col); s.rough = 0.04f; s.coat = 1.f; s.bump = orange * 0.012f;
    return s;
  }
  if (m == NACRE) {
    // Clamshell: pearly base, radial ribs from the hinge and concentric growth lines,
    // with thin-film iridescence that shifts with the viewing angle.
    float ribs = pow_(0.5f + 0.5f * cos_(radial * 26.f), 0.7f);
    float fine = 0.5f + 0.5f * cos_(radial * 130.f);
    float growth = 0.5f + 0.5f * sin_(len(p) * 0.11f + fbm(x * 0.01f, y * 0.01f, 4, seed) * 5.f);
    v3 base = mix(rgb(0xF6EEE8), rgb(0xE8D6CC), growth * 0.45f + (1.f - ribs) * 0.25f);
    s.albedo = lin(base); s.rough = 0.16f; s.coat = 0.8f;
    s.bump = ribs * 1.6f + fine * 0.12f + growth * 0.08f; s.irid = 0.7f;
    return s;
  }
  if (m == TORTOISE) {
    float wx = fbm(x * 0.006f, y * 0.006f, 4, seed + 30u) * 90.f;
    float wy = fbm(x * 0.006f + 7.f, y * 0.006f, 4, seed + 31u) * 90.f;
    float X = x + wx, Y = y + wy;
    float a = fbm(X * 0.011f, Y * 0.026f, 6, seed);                 // elongated mottling
    float b = fbm(X * 0.04f, Y * 0.09f, 4, seed + 4u);
    float spot = smoothstep(0.52f, 0.60f, a + (b - 0.5f) * 0.22f);
    float core = smoothstep(0.60f, 0.70f, a);
    float fleck = smoothstep(0.70f, 0.74f, b) * (1.f - spot);
    v3 honey = rgb(0xD99A45), amber = rgb(0x9C5418), umber = rgb(0x55230A), black = rgb(0x1E0B04);
    v3 col = mix(honey, amber, sat((a - 0.3f) * 2.2f));
    col = mix(col, umber, spot * 0.9f + fleck * 0.5f);
    col = mix(col, black, core * 0.85f);
    // translucency: light seems to come from inside the honey areas
    col = col * (1.f + (1.f - spot) * 0.12f);
    s.albedo = lin(col); s.rough = 0.05f; s.coat = 1.f; s.bump = 0.f;
    return s;
  }
  if (m >= GLASS_AMETHYST && m <= GLASS_SMOKE) {
    v3 tint = m == GLASS_AMETHYST ? rgb(0x3A1F4C) : m == GLASS_EMERALD ? rgb(0x123E32) : m == GLASS_SAPPHIRE ? rgb(0x0F2A40) : rgb(0x1A1C20);
    float depth = fbm(x * 0.003f, y * 0.003f, 4, seed);
    float swirl = fbm(x * 0.012f + depth * 2.f, y * 0.012f, 3, seed + 6u);
    v3 col = tint * (0.55f + 0.9f * depth) + tint * (swirl * 0.35f);
    s.albedo = lin(col); s.rough = 0.03f; s.coat = 1.f; s.bump = swirl * 0.02f;
    return s;
  }
  if (m == LEATHER) {
    float id; float f = worley(x * 0.18f, y * 0.18f, seed, &id);
    v3 col = rgb(0x4A2C1C) * (0.85f + 0.3f * id);
    s.albedo = lin(col); s.rough = 0.62f; s.bump = smoothstep(0.0f, 0.5f, f) * 0.5f;
    return s;
  }
  s.albedo = V3(0.5f, 0.5f, 0.5f); return s;
}

// ───────────────────────────── lighting ─────────────────────────────
struct Light { v3 dir; v3 color; float ambient; v2 shadow2d; };

// Colour of a black-body light at a Kelvin temperature (Tanner Helland fit), linear-ish 0..1.
static v3 kelvinRGB(float K) {
  float t = clamp(K, 1000.f, 40000.f) / 100.f, r, g, b;
  if (t <= 66.f) { r = 1.f; g = clamp((99.4708025861f * log2_(t) * 0.6931472f - 161.1195681661f) / 255.f, 0.f, 1.f); }
  else { r = clamp(329.698727446f * pow_(t - 60.f, -0.1332047592f) / 255.f, 0.f, 1.f); g = clamp(288.1221695283f * pow_(t - 60.f, -0.0755148492f) / 255.f, 0.f, 1.f); }
  if (t >= 66.f) b = 1.f; else if (t <= 19.f) b = 0.f;
  else b = clamp((138.5177312231f * log2_(t - 10.f) * 0.6931472f - 305.0447927307f) / 255.f, 0.f, 1.f);
  return V3(r * r, g * g, b * b);                 // to linear
}
// Global lighting rig, settable from a Lighting Explorer preset.
struct Rig { float keyK, keyI, fillK, fillI, rimI, soft; };
static Rig g_rig = {4300.f, 1.f, 6200.f, 0.35f, 0.6f, 0.3f};

static Light makeLight(float azimuthDeg, float elevationDeg) {
  float az = azimuthDeg * PI / 180.f, el = elevationDeg * PI / 180.f;
  Light L; L.dir = norm(V3(cos_(az) * cos_(el), -sin_(az) * cos_(el), sin_(el)));   // screen y points down
  v3 kc = kelvinRGB(g_rig.keyK);
  float lum = kc.x * 0.2126f + kc.y * 0.7152f + kc.z * 0.0722f;
  L.color = kc * (2.85f * g_rig.keyI / max_(lum, 0.05f));      // same brightness at any colour
  L.ambient = 0.10f + 0.34f * g_rig.fillI;
  L.shadow2d = V2(-L.dir.x, -L.dir.y);         // shadows fall away from the light
  return L;
}

// A studio environment for reflections: dark room, warm softbox overhead toward the
// light, a cool fill opposite, and a dim floor bounce. Roughness widens the lobes.
static v3 environment(v3 r, const Light& L, float rough) {
  // A warm, lamp-lit room: dark wood walls low, warm plaster high, a big softbox
  // toward the key light, a window-ish cool fill opposite and a hot strip light.
  float up = r.z;
  float hz = r.y;                                   // screen-up is -y
  v3 low = V3(0.10f, 0.065f, 0.04f), mid = V3(0.42f, 0.33f, 0.24f), high = V3(0.85f, 0.74f, 0.58f);
  float t = sat(up * 0.6f + 0.4f - hz * 0.35f);
  v3 room = t < 0.5f ? mix(low, mid, t * 2.f) : mix(mid, high, (t - 0.5f) * 2.f);
  float spread = (6.f + 260.f * (1.f - rough) * (1.f - rough)) * (1.3f - g_rig.soft);
  float key = pow_(sat(dot(r, L.dir)), spread);
  v3 fillDir = norm(V3(-L.dir.x, -L.dir.y, 0.45f));
  float fill = pow_(sat(dot(r, fillDir)), 4.f + 50.f * (1.f - rough));
  float sharp = 30.f * (1.f - rough) + 3.f;
  float strip = exp_(-(hz + 0.35f) * (hz + 0.35f) * sharp * 3.f) * sat(up * 1.5f + 0.3f);
  float strip2 = exp_(-(r.x - 0.45f) * (r.x - 0.45f) * sharp * 2.f) * sat(up * 1.2f);
  v3 kc = kelvinRGB(g_rig.keyK), fc = kelvinRGB(g_rig.fillK);
  float kl = max_(kc.x * 0.2126f + kc.y * 0.7152f + kc.z * 0.0722f, 0.05f), fl = max_(fc.x * 0.2126f + fc.y * 0.7152f + fc.z * 0.0722f, 0.05f);
  v3 c = room * 0.9f + kc * (8.f * g_rig.keyI / kl) * key + fc * (1.6f * g_rig.fillI / fl) * fill
       + V3(2.4f, 2.1f, 1.7f) * strip + V3(1.0f, 0.9f, 0.75f) * strip2 * 0.7f;
  return c;
}

static inline v3 fresnel(v3 f0, float cosT) {
  float m = 1.f - sat(cosT), m5 = m * m * m * m * m;
  return f0 + (V3(1, 1, 1) - f0) * m5;
}
static inline float ggx(float nh, float rough) {
  float a = rough * rough, a2 = a * a, d = nh * nh * (a2 - 1.f) + 1.f;
  return a2 / (PI * d * d + 1e-6f);
}

static v3 shade(const Surface& s, v3 n, const Light& L, float ao, float shadow) {
  v3 V = V3(0, 0, 1), H = norm(L.dir + V);
  float nl = sat(dot(n, L.dir)), nv = sat(dot(n, V)) + 1e-3f, nh = sat(dot(n, H));
  v3 r = n * (2.f * dot(n, V)) - V;
  v3 F = fresnel(s.metal > 0.5f ? s.f0 : V3(0.04f, 0.04f, 0.04f), nv);
  float D = ggx(nh, max_(s.rough, 0.04f));
  float G = 1.f / (4.f * nl * nv + 1e-3f) * (nl * nv * 4.f) / (1.f + s.rough * 2.f);   // tempered visibility
  v3 spec = F * (D * G * nl) * shadow;
  v3 env = environment(r, L, s.rough) * ao;
  v3 col;
  if (s.metal > 0.5f) {
    col = (L.color * spec) + env * F;
    col = col + s.f0 * (L.ambient * 0.15f * ao);
  } else {
    v3 diff = s.albedo * (nl * shadow) * L.color * (1.f / PI) * 2.0f;
    v3 amb = s.albedo * (L.ambient * ao) * 1.6f;
    col = diff + amb;
    // clear coat: a second, sharp dielectric layer on polished stone, varnish, glass
    if (s.coat > 0.f) {
      float Fc = 0.04f + 0.96f * pow_(1.f - nv, 5.f);
      float Dc = ggx(nh, 0.06f);
      v3 cenv = environment(r, L, 0.08f) * ao;
      col = col * (1.f - Fc * s.coat) + (L.color * (Dc * nl * 0.25f * shadow) + cenv * Fc) * s.coat;
    } else {
      col = col + L.color * spec;
    }
    if (s.irid > 0.f) {                 // thin film: hue rotates with view angle and surface tilt
      float ph = nv * 2.6f + n.x * 1.7f + n.y * 1.3f;
      v3 film = V3(0.5f + 0.5f * cos_(6.283f * (ph + 0.0f)), 0.5f + 0.5f * cos_(6.283f * (ph + 0.33f)), 0.5f + 0.5f * cos_(6.283f * (ph + 0.67f)));
      col = mix(col, col * (film * 0.6f + V3(0.7f, 0.7f, 0.7f)), s.irid);
    }
  }
  if (s.sparkle > 0.f) col = col + V3(2.5f, 2.4f, 2.2f) * s.sparkle * nl * shadow;
  return col;
}

// Filmic tone map (ACES fitted) and sRGB encode.
static inline float aces(float x) { return sat((x * (2.51f * x + 0.03f)) / (x * (2.43f * x + 0.59f) + 0.14f)); }
static inline uint8_t enc(float v) { return (uint8_t)(pow_(aces(v * 0.9f), 1.f / 2.2f) * 255.f + 0.5f); }

// ───────────────────────────── tray rendering ─────────────────────────────
struct TrayParams {
  int W, H;            // canvas size in px (includes shadow margin)
  int margin;          // margin around the shape for the cast shadow
  ShapeSpec shape;     // centred in the canvas
  int rimMat, floorMat;
  float rimW;          // rim width in px
  float height;        // how tall the rim stands (shadow length)
  float lightAz, lightEl;
  float worldX, worldY; // canvas origin on the Counter, so textures stay put when trays move
  uint32_t seed;
  float hx0, hy0, hx1, hy1;   // optional hole (relative to centre): covered by content, left transparent
};

static uint8_t* g_out = nullptr;

static void renderTray(const TrayParams& t, uint8_t* out) {
  Light L = makeLight(t.lightAz, t.lightEl);
  const float cx = t.W * 0.5f, cy = t.H * 0.5f, e = 0.75f;
  const float rim = t.rimW;
  for (int py = 0; py < t.H; ++py) {
    for (int px = 0; px < t.W; ++px) {
      v2 p = V2(px + 0.5f - cx, py + 0.5f - cy);
      uint8_t* o = out + 4 * (py * t.W + px);
      if (p.x > t.hx0 && p.x < t.hx1 && p.y > t.hy0 && p.y < t.hy1) { o[0] = o[1] = o[2] = o[3] = 0; continue; }
      float d = shapeSDF(t.shape, p);
      if (d > 1.0f) {
        // Cast shadow on the bench: soft, offset away from the light, longer for taller rims.
        v2 sp = p - L.shadow2d * (t.height * 1.6f);
        float ds = shapeSDF(t.shape, sp);
        float blur = 6.f + t.height * 1.2f;
        float a = (1.f - smoothstep(-blur, blur, ds)) * 0.62f;
        float contact = (1.f - smoothstep(0.f, 5.f, d)) * 0.35f;   // tight contact shadow at the base
        float alpha = sat(max_(a, contact));
        o[0] = 0; o[1] = 0; o[2] = 0; o[3] = (uint8_t)(alpha * 255.f);
        continue;
      }
      // Gradient of the field (outward normal in 2D) by central differences.
      float gx = shapeSDF(t.shape, V2(p.x + e, p.y)) - shapeSDF(t.shape, V2(p.x - e, p.y));
      float gy = shapeSDF(t.shape, V2(p.x, p.y + e)) - shapeSDF(t.shape, V2(p.x, p.y - e));
      v2 g = V2(gx, gy); float gl = len(g); g = gl > 0.f ? g * (1.f / gl) : V2(0, -1);
      v2 tdir = V2(-g.y, g.x);
      v2 wp = V2(t.worldX + px, t.worldY + py);
      float inside = -d;
      v3 col; float alpha = 1.f;
      if (inside < rim) {
        // Rim: a rounded lip (half-round moulding) with a fine inner bead.
        float u = inside / rim;                               // 0 at the outer edge, 1 at the inner edge
        // Profile: big outer roll (0..0.62), a dark groove (0.62..0.72), a small bead (0.72..1).
        float slope, bead = 0.f, groove = 0.f;
        if (u < 0.62f) slope = cos_(u / 0.62f * PI) * 1.6f;
        else if (u < 0.72f) { slope = -0.4f; groove = sin_((u - 0.62f) / 0.10f * PI); }
        else { slope = cos_((u - 0.72f) / 0.28f * PI) * 1.2f; }
        Surface s = material(t.rimMat, wp, tdir, 0.f, t.seed + 17u);
        float tilt = slope + bead * 0.6f;
        (void)groove;
        v3 n = norm(V3(g.x * tilt, g.y * tilt, 1.f));
        // Fine surface detail from the material's bump, sampled as a height field.
        float hb = s.bump;
        Surface s2 = material(t.rimMat, wp + V2(1.f, 0.f), tdir, 0.f, t.seed + 17u);
        Surface s3 = material(t.rimMat, wp + V2(0.f, 1.f), tdir, 0.f, t.seed + 17u);
        n = norm(n + V3(-(s2.bump - hb), -(s3.bump - hb), 0.f) * 1.2f);
        float ao = (0.78f + 0.22f * sin_(u * PI)) * (1.f - groove * 0.55f);
        col = shade(s, n, L, ao, 1.f);
        alpha = sat(0.5f - d);                                 // antialiased outer edge
      } else {
        // Floor: recessed below the rim. Ambient occlusion along the inside wall,
        // and the rim's own shadow cast across the floor away from the light.
        float fromWall = inside - rim;
        float ao = 1.f - 0.55f * exp_(-fromWall / (rim * 0.9f + 4.f));
        v2 toward = L.shadow2d * -1.f;                          // look back toward the light
        float occl = 0.f;
        for (int k = 1; k <= 4; ++k) {
          float step = k * (t.height * 0.55f + 2.f);
          float dk = shapeSDF(t.shape, p + toward * step);
          if (-dk < rim) occl = max_(occl, 1.f - (float)(k - 1) / 4.f);
        }
        float shadow = 1.f - occl * 0.55f;
        float radial = atan2_(p.x, -(p.y - t.shape.hy * 0.92f));
        Surface s = material(t.floorMat, wp, tdir, radial, t.seed);
        float hb = s.bump;
        Surface s2 = material(t.floorMat, wp + V2(1.f, 0.f), tdir, atan2_(p.x + 1.f, -(p.y - t.shape.hy * 0.92f)), t.seed);
        Surface s3 = material(t.floorMat, wp + V2(0.f, 1.f), tdir, atan2_(p.x, -(p.y + 1.f - t.shape.hy * 0.92f)), t.seed);
        v3 n = norm(V3(-(s2.bump - hb) * 2.2f, -(s3.bump - hb) * 2.2f, 1.f));
        col = shade(s, n, L, ao, shadow);
        if (t.floorMat >= GLASS_AMETHYST && t.floorMat <= GLASS_SMOKE) {
          // Light passes through the glass and pools on the far wall (a caustic),
          // while the near wall shows a darker band of thickness.
          float side = dot(g, L.shadow2d * -1.f);                // >0 on the wall facing away from the light
          float wallBand = exp_(-fromWall / 26.f);
          v3 tint = s.albedo * 3.5f + V3(0.02f, 0.02f, 0.02f);
          col = col + tint * (sat(-side) * wallBand * 1.4f);
          col = col * (1.f - sat(side) * wallBand * 0.5f);
        }
        if ((t.floorMat >= GLASS_AMETHYST && t.floorMat <= OBSIDIAN_LACQUER) || t.floorMat == TORTOISE) {
          // Polished, deep surfaces mirror the room: one broad soft band and one razor-thin
          // highlight, both running the same way (the window behind the key light).
          float u = (p.x * 0.55f + p.y) / (t.shape.hy * 2.f);
          float broad = smoothstep(0.30f, 0.0f, fabs_(u + 0.30f));
          // The window's reflection: a soft-edged bright pane, strongest near the light, fading away.
          float along = smoothstep(t.shape.hx * 0.9f, -t.shape.hx * 0.6f, p.x) * smoothstep(t.shape.hy * 1.2f, -t.shape.hy * 0.4f, p.y);
          float razor = (smoothstep(0.075f, 0.02f, fabs_(u + 0.10f)) * 0.35f + smoothstep(0.03f, 0.0f, fabs_(u + 0.17f)) * 0.25f) * along;
          float k = t.floorMat == OBSIDIAN_LACQUER ? 1.f : 0.6f;
          col = col + V3(0.22f, 0.21f, 0.20f) * broad * 0.30f * k + V3(1.6f, 1.5f, 1.35f) * razor * 0.55f * k;
          if (t.floorMat == OBSIDIAN_LACQUER) col = col + V3(0.10f, 0.045f, 0.015f) * smoothstep(0.2f, -0.6f, u) * 0.6f;  // warm ember depth
        }
      }
      o[0] = enc(col.x); o[1] = enc(col.y); o[2] = enc(col.z); o[3] = (uint8_t)(alpha * 255.f);
    }
  }
}

// The workbench itself: a full-bleed surface with a broad light pool from the key light.
static void renderBench(int W, int H, int mat, float lightAz, float lightEl, uint32_t seed, uint8_t* out) {
  Light L = makeLight(lightAz, lightEl);
  float lx = W * 0.5f - L.dir.x * W * 0.6f, ly = H * 0.5f - L.dir.y * H * 0.6f;   // centre of the light pool
  float diag = sqrt_((float)W * W + (float)H * H);
  for (int py = 0; py < H; ++py) for (int px = 0; px < W; ++px) {
    v2 wp = V2((float)px, (float)py);
    Surface s = material(mat, wp, V2(1, 0), 0.f, seed);
    Surface s2 = material(mat, wp + V2(1, 0), V2(1, 0), 0.f, seed);
    Surface s3 = material(mat, wp + V2(0, 1), V2(1, 0), 0.f, seed);
    v3 n = norm(V3(-(s2.bump - s.bump) * 2.f, -(s3.bump - s.bump) * 2.f, 1.f));
    float dx = px - lx, dy = py - ly, dist = sqrt_(dx * dx + dy * dy) / diag;
    float pool = 0.45f + 0.75f * exp_(-dist * dist * 3.2f);
    v3 col = shade(s, n, L, pool, pool);
    uint8_t* o = out + 4 * (py * W + px);
    o[0] = enc(col.x); o[1] = enc(col.y); o[2] = enc(col.z); o[3] = 255;
  }
}

}  // namespace fm

// ───────────────────────────── exported API ─────────────────────────────
// One output buffer, reused. Large enough for a 2560x1600 bench.
static uint8_t g_buffer[2560 * 1600 * 4];

FM_EXPORT("fm_buffer") uint8_t* fm_buffer() { return g_buffer; }
FM_EXPORT("fm_buffer_size") int fm_buffer_size() { return (int)sizeof(g_buffer); }

// Returns 0 on success, -1 if the canvas would not fit the buffer.
FM_EXPORT("fm_render_tray") int fm_render_tray(int W, int H, int margin, int shape, float hx, float hy, float round, float a, float b,
                                               int rimMat, int floorMat, float rimW, float height,
                                               float lightAz, float lightEl, float worldX, float worldY, int seed,
                                               float holeX0, float holeY0, float holeX1, float holeY1) {
  if (W <= 0 || H <= 0 || (long)W * H * 4 > (long)sizeof(g_buffer)) return -1;
  fm::TrayParams t;
  t.W = W; t.H = H; t.margin = margin;
  t.shape = fm::ShapeSpec{shape, hx, hy, round, a, b};
  t.rimMat = rimMat; t.floorMat = floorMat; t.rimW = rimW; t.height = height;
  t.lightAz = lightAz; t.lightEl = lightEl; t.worldX = worldX; t.worldY = worldY; t.seed = (uint32_t)seed;
  t.hx0 = holeX0; t.hy0 = holeY0; t.hx1 = holeX1; t.hy1 = holeY1;      // pass an empty box (0,0,0,0) for none
  fm::renderTray(t, g_buffer);
  return 0;
}
// Set the lighting rig from a Lighting Explorer preset (key Kelvin and intensity,
// fill Kelvin and level, rim level, softness). Applies to every render after it.
FM_EXPORT("fm_set_light") void fm_set_light(float keyK, float keyI, float fillK, float fillI, float rimI, float soft) {
  fm::g_rig = fm::Rig{keyK, keyI, fillK, fillI, rimI, soft};
}
FM_EXPORT("fm_render_bench") int fm_render_bench(int W, int H, int mat, float lightAz, float lightEl, int seed) {
  if (W <= 0 || H <= 0 || (long)W * H * 4 > (long)sizeof(g_buffer)) return -1;
  fm::renderBench(W, H, mat, lightAz, lightEl, (uint32_t)seed, g_buffer);
  return 0;
}
// Signed distance query so the page can hit-test clicks against the real silhouette.
FM_EXPORT("fm_shape_distance") float fm_shape_distance(int shape, float hx, float hy, float round, float a, float b, float x, float y) {
  return fm::shapeSDF(fm::ShapeSpec{shape, hx, hy, round, a, b}, fm::V2(x, y));
}

#if defined(FM_NATIVE)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
// Native preview: composite a sample sheet of trays on a bench and write a PPM.
struct Canvas { int W, H; uint8_t* px; };
static void blit(Canvas& dst, int ox, int oy, int W, int H, const uint8_t* src) {
  for (int y = 0; y < H; ++y) for (int x = 0; x < W; ++x) {
    int dx = ox + x, dy = oy + y; if (dx < 0 || dy < 0 || dx >= dst.W || dy >= dst.H) continue;
    const uint8_t* s = src + 4 * (y * W + x); uint8_t* d = dst.px + 3 * (dy * dst.W + dx);
    float a = s[3] / 255.f;
    for (int c = 0; c < 3; ++c) d[c] = (uint8_t)(s[c] * a + d[c] * (1.f - a) + 0.5f);
  }
}
int main(int argc, char** argv) {
  const char* out = argc > 1 ? argv[1] : "sheet.ppm";
  int bench = argc > 2 ? atoi(argv[2]) : fm::WALNUT;
  float az = 135.f, el = 48.f;
  Canvas c{1600, 1000, (uint8_t*)malloc(1600 * 1000 * 3)};
  fm_render_bench(c.W, c.H, bench, az, el, 7);
  for (int i = 0; i < c.W * c.H; ++i) memcpy(c.px + 3 * i, g_buffer + 4 * i, 3);
  struct Item { int x, y, w, h, shape; float round, a, b; int rim, floor; float rimW; };
  Item items[] = {
    {30, 30, 470, 300, fm::CHAMFER, 16, 0.18f, 0, fm::GOLD, fm::MARBLE_WHITE, 22},
    {540, 30, 520, 320, fm::GEM, 28, 0, 0, fm::BRASS, fm::GRANITE_BLACK, 20},
    {1100, 20, 460, 420, fm::SHELL, 10, 1.05f, 13, fm::GOLD, fm::NACRE, 16},
    {30, 380, 420, 290, fm::CUSHION, 40, 1, 0, fm::BRASS, fm::PEARL, 18},
    {480, 400, 560, 250, fm::LONGHEX, 18, 0.16f, 0, fm::GOLD, fm::EMERALD_ENAMEL, 20},
    {1080, 480, 480, 300, fm::ELLIPSE, 0, 0, 0, fm::SILVER, fm::MARBLE_GREEN, 18},
    {30, 720, 460, 250, fm::ARCH, 30, 0, 0, fm::COPPER, fm::OBSIDIAN_LACQUER, 18},
    {520, 700, 520, 270, fm::CHAMFER, 14, 0.22f, 0, fm::SILVER, fm::GLASS_SAPPHIRE, 20},
    {1080, 800, 420, 170, fm::PETAL, 0, 0, 0, fm::GOLD, fm::MARBLE_ROSE, 12},
  };
  for (auto& it : items) {
    int m = 40; int W = it.w + 2 * m, H = it.h + 2 * m;
    float hx = it.w * 0.5f, hy = it.h * 0.5f;
    fm_render_tray(W, H, m, it.shape, hx, hy, it.round, it.a, it.b, it.rim, it.floor, it.rimW, 10.f, az, el, (float)it.x, (float)it.y, 3, 0, 0, 0, 0);
    blit(c, it.x - m, it.y - m, W, H, g_buffer);
  }
  FILE* f = fopen(out, "wb"); fprintf(f, "P6\n%d %d\n255\n", c.W, c.H); fwrite(c.px, 1, c.W * c.H * 3, f); fclose(f);
  printf("wrote %s\n", out);
  return 0;
}
#endif
