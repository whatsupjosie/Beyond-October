/* Foresight GL — the Counter's renderer, on the graphics card.

   One canvas sits behind the whole Counter. It draws the bench, then every tray,
   fan blade, the lantern and the system bar, each as a rounded polygon from
   foresight_shapes.js: a thick polished rim with bevels and highlights, a
   recessed floor of stone, wood, pearl or jewel glass (glass shows the bench
   blurred behind it), an inlay line, a seated lip around the content, a cast
   shadow and a coloured glow. Because it runs on the graphics card, shapes can
   change every frame while trays push against each other.

   Materials are the ones from the C++ renderer (foresight_matter.cpp), ported
   line for line to GLSL, plus the canonical Wallet palette and the looks in
   Josie's mockups (rose gold, champagne, frosted pearl glass, burgundy glass,
   parchment).

   API: const gl = new ForesightGL(canvas); gl.setTheme('tigereye'|'pearl'|'indigo')  (walnut is retired);
        gl.draw(items)   items = [{q, r, rim, pad, rimMat, floorMat, glow:[r,g,b,a],
                                   focus, content:[x0,y0,x1,y1]|null, seed, height,
                                   inlay, emissive:[r,g,b,a], center:[x,y]}]
   Coordinates are CSS pixels of the canvas. */
(function(root){
  'use strict';

  const MAT = {
    GOLD:0, ROSE_GOLD:1, BRASS:2, COPPER:3, SILVER:4, BRONZE:5, CHAMPAGNE:6, STEEL:7,
    MARBLE_WHITE:10, MARBLE_ROSE:11, MARBLE_VERDE:12, MARBLE_BLACK:13, MARBLE_INDIGO:14,
    GRANITE:20, GRANITE_BLACK:21, SANDSTONE:30, WALNUT:40, OAK:41, MAHOGANY:42,
    NACRE:50, PEARL:51, PEARL_GLASS:52, OPAL:53, TORTOISE:60,
    GLASS_AMETHYST:70, GLASS_EMERALD:71, GLASS_SAPPHIRE:72, GLASS_SMOKE:73, GLASS_BURGUNDY:74,
    EMERALD_ENAMEL:75, OBSIDIAN:76, PARCHMENT:80, LEATHER:81,
  };
  const THEME = {walnut:0, pearl:1, indigo:2, tigereye:3, nero:4};
  const MAXV = 40;
  const ENV_LEVELS = 6;      // studio mips 256..8, roughness (level/5)^2

  const COMMON = `#version 300 es
precision highp float; precision highp int;
const float PI = 3.14159265;
uint hashu(int x, int y, uint s){ uint h = uint(x)*0x8da6b343u ^ uint(y)*0xd8163841u ^ s*0xcb1ab31fu; h ^= h>>13; h *= 0x5bd1e995u; h ^= h>>15; return h; }
float hash(int x, int y, uint s){ return float(hashu(x,y,s) & 0xFFFFFFu) / 16777216.0; }
float vnoise(vec2 p, uint s){
  vec2 f = floor(p); ivec2 i = ivec2(f); vec2 t = p - f;
  vec2 u = t*t*t*(t*(t*6.0-15.0)+10.0);
  float a = hash(i.x,i.y,s), b = hash(i.x+1,i.y,s), c = hash(i.x,i.y+1,s), d = hash(i.x+1,i.y+1,s);
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}
float fbm(vec2 p, int oct, uint s){
  float v = 0.0, a = 0.5, n = 0.0;
  for(int i=0;i<8;i++){ if(i>=oct) break; v += a*vnoise(p, s + uint(i)*101u); n += a;
    p = vec2(1.6*p.x + 1.2*p.y + 3.1, -1.2*p.x + 1.6*p.y + 1.7); a *= 0.5; }
  return v/n;
}
float worley(vec2 p, uint s, out float id){
  ivec2 i = ivec2(floor(p)); float best = 9.0; id = 0.0;
  for(int y=-1;y<=1;y++) for(int x=-1;x<=1;x++){
    ivec2 c = i + ivec2(x,y);
    vec2 q = vec2(c) + vec2(hash(c.x,c.y,s), hash(c.x,c.y,s+7u));
    float d = dot(q-p, q-p);
    if(d < best){ best = d; id = hash(c.x,c.y,s+13u); }
  }
  return sqrt(best);
}
// Gradient (Perlin) noise: smoother and less blocky than value noise. Range
// about -0.7..0.7. Octaves are rotated 37 degrees with lacunarity 2.01 so the
// layers never line up into a visible grid.
float gnoise(vec2 p, uint s){
  vec2 f = floor(p); ivec2 i = ivec2(f); vec2 t = p - f;
  vec2 u = t*t*t*(t*(t*6.0-15.0)+10.0);
  float a0 = hash(i.x,i.y,s)*6.2831853, a1 = hash(i.x+1,i.y,s)*6.2831853, a2 = hash(i.x,i.y+1,s)*6.2831853, a3 = hash(i.x+1,i.y+1,s)*6.2831853;
  float a = dot(vec2(cos(a0),sin(a0)), t), b = dot(vec2(cos(a1),sin(a1)), t - vec2(1,0));
  float c = dot(vec2(cos(a2),sin(a2)), t - vec2(0,1)), d = dot(vec2(cos(a3),sin(a3)), t - vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}
float gfbm(vec2 p, int oct, uint s){
  float v = 0.0, a = 0.5;
  for(int i=0;i<8;i++){ if(i>=oct) break; v += a*gnoise(p, s + uint(i)*101u);
    p = mat2(0.799, 0.602, -0.602, 0.799)*p*2.01 + vec2(17.3, 9.1); a *= 0.5; }
  return v;
}
vec3 rgb(int h){ return vec3(float((h>>16)&255), float((h>>8)&255), float(h&255)) / 255.0; }
vec3 lin(vec3 c){ return pow(max(c, 0.0), vec3(2.2)); }
vec3 aces(vec3 x){ return clamp((x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14), 0.0, 1.0); }
#ifdef HDR
// Everything is drawn in linear light into a floating-point buffer and tone
// mapped once, in the final pass. Values above 1.0 survive, so highlights add
// up instead of clipping and the bloom pass has something to work with.
vec3 encode(vec3 c){ return c; }
vec3 benchRead(vec3 c){ return c; }
#else
// Fallback for a browser without float render targets: the old per-shader
// curve. Correct enough to look at; it clips highlights and cannot bloom.
vec3 encode(vec3 c){ return pow(aces(c*0.92), vec3(1.0/2.2)); }
vec3 benchRead(vec3 c){ return lin(c); }
#endif
`;

  // ---------- bench (rendered once into a texture) ----------
  const BENCH_FS = COMMON + `
uniform vec2 uView; uniform int uTheme; uniform vec3 uL; uniform vec3 uKey; uniform vec2 uPool; uniform float uPoolK; uniform float uLampZ; uniform vec3 uL2d, uK2;
in vec2 vP; out vec4 o;
// ---- an antique walnut tabletop ----
// Modelled as the tree, not painted as a board. Each board was cut from a log
// whose pith runs a little below the face at a slight tilt, so the growth rings
// meet the surface as straight grain at the edges and as cathedral arches where
// the rings rise through the face. Rings grow unevenly year to year; walnut's
// late wood is darker; pores run as fine dashes along the grain, denser in the
// early wood; old walnut carries dark mineral streaks, honeyed zones, and a
// wavy figure that catches the light. Wide boards with hairline joints, as on a
// fine table, not floor planks. Units are millimetres: one CSS pixel ~ 0.75 mm.
const float WAL_MM = 0.75, WAL_BOARD = 232.0, WAL_OFF = 61.0;
vec3 walnut(vec2 p, out float h){
  vec2 q = p*WAL_MM;
  float by = (q.y + WAL_OFF)/WAL_BOARD, bi = floor(by), yb = (by - bi)*WAL_BOARD;
  int ib = int(bi);
  uint bs = 7u + uint(ib + 64)*977u;
  float r1 = hash(ib,1,bs), r2 = hash(ib,2,bs), r3 = hash(ib,3,bs), r4 = hash(ib,4,bs), r5 = hash(ib,5,bs);
  float x = q.x + r4*3000.0;                                     // where along the log this board came from
  // the pith: off to one side or the other, wandering with the tree's sweep, and
  // tilted relative to the face so the rings rise through it into arches
  float y0 = WAL_BOARD*(0.5 + (r1 - 0.5)*1.5) + gfbm(vec2(x*0.0011, bi*7.3), 3, bs+1u)*16.0;
  float z0 = max(8.0 + r2*110.0 + (q.x - 600.0)*(r3 - 0.5)*0.06, 5.0);
  float wob = gfbm(vec2(x*0.0035, yb*0.010), 4, bs+2u)*9.0 + gfbm(vec2(x*0.02, yb*0.045), 3, bs+3u)*1.2;
  float rr = length(vec2(yb - y0, z0)) + wob;
  // years: ring width wanders between good and lean seasons, so the lines bunch
  // and spread instead of ruling the board like paper
  float yr = rr/4.6 + gfbm(vec2(rr*0.012, bi*3.0), 3, bs+4u)*4.5;
  float t = fract(yr);
  float late = smoothstep(0.45, 0.88, t)*(1.0 - smoothstep(0.93, 1.0, t));
  late *= 0.55 + 0.45*smoothstep(-0.2, 0.3, gfbm(vec2(yr*0.31, bi), 2, bs+12u));   // some years barely mark
  // fine fibre striation along the grain
  float fib = gfbm(vec2(x*0.028, yb*1.05), 3, bs+7u);
  // pores: long faint dashes along the grain, a few millimetres long and a
  // fraction wide, denser in early wood; faded once finer than a pixel so the
  // bench never shimmers
  float pid; float pf = worley(vec2(x*0.06, (yb + wob*0.4)*1.4), bs+9u, pid);
  float poreFade = 1.0 - smoothstep(0.7, 1.3, fwidth(q.y)*1.4);
  float pore = (1.0 - smoothstep(0.05, 0.26, pf)) * step(pid, 0.42) * poreFade
             * smoothstep(0.50, 0.08, t);                          // gathered in the early wood at the start of each year
  // colour: early and late wood, then the board's own character. Antique
  // walnut is chocolate brown with grey and violet in it, not orange.
  vec3 ew = rgb(0x4C3424), lw = rgb(0x271810), amber = rgb(0x6E4C2E), mineral = rgb(0x231819);
  vec3 col = mix(ew, lw, late*0.7);
  col *= 0.80 + 0.30*r5;                                          // board to board tone
  float honey = smoothstep(0.05, 0.40, gfbm(vec2(x*0.0009, yb*0.006), 3, bs+5u));
  col = mix(col, amber, honey*(0.18 + 0.2*r2));
  float streak = smoothstep(0.12, 0.42, gfbm(vec2(x*0.0010, yb*0.034), 4, bs+6u));
  col = mix(col, mineral, streak*0.5);
  col *= 0.92 + 0.16*(fib + 0.5);
  col = mix(col, lw*0.8, pore*0.22);
  // figure: the fibres undulate, so bands across the grain catch the light differently
  float wave = gfbm(vec2(x*0.032, yb*0.0045), 3, bs+8u);
  float figured = smoothstep(0.3, 0.9, r2 + 0.35*gfbm(vec2(x*0.002, yb*0.01), 2, bs+10u));
  col *= 1.0 + 0.10*figured*sin(wave*10.0 + (uL.x - uL.y)*3.0);
  // the joints: a hairline, with old wax and grime gathered along them
  float dseam = min(yb, WAL_BOARD - yb)/WAL_MM;                  // CSS px to the nearest joint
  float seam = 1.0 - smoothstep(0.0, 1.3, dseam);
  col *= (1.0 - seam*0.85) * (1.0 - 0.22*exp(-dseam/5.0));
  h = late*0.025 + fib*0.01 - pore*0.35 - seam*0.6;
  return lin(col);
}
// ---- tiger's eye ----
// A slab cut across parallel fibres of crocidolite turned to quartz. Each fibre
// bundle tilts a little differently from its neighbour, so with the light where
// it is, some bands glow gold and silky while the next one sits dark brown: the
// stripes are the light, not paint. Bands are not ruled; the seams wander. Faint
// red-brown where the iron has oxidised, and a few dark hairline inclusions.
uniform sampler2D uStone; uniform float uStoneOn;
// Photographed tiger's eye (flattened, mirror-tiled), graded to lit-from-within amber:
// the dark inclusions are lifted to deep tortoiseshell brown so the slab reads evenly
// translucent, and the cream veins glow. The tray lights still land on top of this.
vec3 tigerEyeTex(vec2 p, out float h){
  vec2 uv = p/vec2(3300.0, 2060.0) + vec2(0.02, 0.03);
  vec3 t = texture(uStone, uv).rgb;                       // sRGB
  float l = dot(t, vec3(0.299, 0.587, 0.114));
  vec3 amber = vec3(0.70, 0.40, 0.11), shell = vec3(0.11, 0.05, 0.022);
  vec3 g = mix(shell, amber, smoothstep(0.10, 0.62, l));  // dark -> tortoiseshell, mid -> amber
  g = mix(g, vec3(0.85, 0.60, 0.26), smoothstep(0.62, 0.98, l)*0.55);   // veins: lit honey
  g = mix(g, t*vec3(1.05, 0.95, 0.80), 0.35);             // keep some of the real stone's own colour
  h = (l - 0.5)*0.01;
  return lin(g)*0.26;
}
vec3 tigerEye(vec2 p, out float h){
  if(uStoneOn > 0.5) return tigerEyeTex(p, h);
  const vec2 D = vec2(0.9703, -0.2419);
  vec2 N = vec2(-D.y, D.x);
  float u = dot(p, D), c0 = dot(p, N);
  float c = c0 + gfbm(vec2(u*0.0014, c0*0.0030), 3, 301u)*16.0 + gfbm(vec2(u*0.006, c0*0.012), 2, 302u)*2.5;
  float tilt = gfbm(vec2(c*0.024, u*0.0009), 3, 303u);
  float chat = pow(clamp(cos(tilt*7.0 - 0.5), 0.0, 1.0), 3.2);
  chat = 0.6*chat + 0.4*smoothstep(0.22, 0.70, chat);           // bands with defined edges, still soft
  float fine = gfbm(vec2(u*0.0025, c*0.75), 3, 304u);
  float broad = gfbm(vec2(u*0.003, c*0.30), 3, 305u);
  vec3 dark = rgb(0x140D09), brown = rgb(0x30211A), gold = rgb(0x6F5530), honey = rgb(0x9C7C48), red = rgb(0x3E2218);
  vec3 col = mix(dark, brown, smoothstep(0.0, 0.45, chat));
  col = mix(col, gold, smoothstep(0.25, 0.80, chat));
  col = mix(col, honey, smoothstep(0.78, 1.0, chat)*0.75);
  float redz = smoothstep(0.0, 0.5, gfbm(p*0.0011, 3, 306u));
  col = mix(col, red, redz*0.30*(1.0 - chat*0.6));
  col *= 0.78 + 0.40*(fine + 0.5) + 0.10*broad;
  col += vec3(0.56, 0.42, 0.20)*pow(chat, 6.0)*0.10;                 // the silk: a thin bright core on the glowing bands
  float hair = smoothstep(0.93, 0.985, vnoise(vec2(c*0.34, u*0.002), 307u));
  col *= 1.0 - hair*0.55;
  h = fine*0.004;
  return lin(col)*0.40;
}
vec3 marbleSlab(vec2 p, vec3 base, vec3 vein, vec3 cloud, uint seed, out float h){
  float sc = 0.0021;
  float warp = fbm(p*sc*2.0, 6, seed);
  float t = sin((p.x*0.82 + p.y*0.57)*sc*9.0 + warp*9.5);
  float v1 = pow(1.0 - abs(t), 22.0);
  float t2 = sin((p.x*-0.4 + p.y*0.92)*sc*5.0 + fbm(p*sc*3.0, 5, seed+41u)*12.0);
  float v2 = pow(1.0 - abs(t2), 60.0)*0.6;
  float c = fbm(p*sc*1.2, 5, seed+77u);
  vec3 col = mix(base, cloud, smoothstep(0.35, 0.8, c)*0.6);
  col = mix(col, vein, clamp(v1*0.7 + v2, 0.0, 1.0));
  h = (v1+v2)*0.02;
  return lin(col);
}
void main(){
  vec2 p = vP; float h = 0.0; vec3 alb;
  if(uTheme == 0) alb = walnut(p, h);
  else if(uTheme == 1) alb = marbleSlab(p, rgb(0xEFEAE3), rgb(0xA79C90), rgb(0xDCD4CA), 11u, h);
  else if(uTheme == 2) alb = marbleSlab(p, rgb(0x120E24), rgb(0x3B3060), rgb(0x1E1838), 23u, h);
  else if(uTheme == 4) alb = mix(marbleSlab(p, rgb(0x0E0E11), rgb(0x9A8A68), rgb(0x26242C), 37u, h), marbleSlab(p*1.7 + 400.0, rgb(0x0E0E11), rgb(0x55504A), rgb(0x18171C), 41u, h), 0.35);   // nero: black marble with gilded veins
  else alb = tigerEye(p, h);
  vec3 n = normalize(vec3(-dFdx(h)*6.0, -dFdy(h)*6.0, 1.0));
  // one key light from the upper left, a pool of light, and a soft vignette
  vec2 pool = uPool;                       // the lantern: a real, visible source the light can be traced back to
  float dpool = length((p - pool)/uView);
  // the walnut falls off more steeply, so the table has depth instead of an even wash
  float lightPool = uTheme == 0 ? 0.42 + 0.95*exp(-dpool*dpool*2.2) : 0.55 + 0.75*exp(-dpool*dpool*2.6);
  lightPool *= mix(1.0, 0.45 + 1.25*exp(-dpool*dpool*5.0), uPoolK);   // inverse-square-ish falloff from that source
  float nl = max(dot(n, uL), 0.0);
  vec3 col = alb * (uKey*nl*0.55 + vec3(0.36)) * lightPool;
  if(uLampZ > 0.0){
    // The lantern as the one real light: direction and strength from where it hangs, almost no ambient.
    vec2 lp = pool - p; float dl2 = dot(lp, lp);
    vec3 Lb = normalize(vec3(lp, uLampZ));
    float att = min(2.4*uLampZ*uLampZ/(uLampZ*uLampZ + dl2), 1.7);
    col = alb * (uKey*max(dot(n, Lb), 0.0)*1.05*pow(att, 1.4) + vec3(0.05) + uK2*max(dot(n, uL2d), 0.0)*0.55);
  }
#ifndef HDR
  // polished stone and varnished wood catch a broad reflection (the HDR path
  // reflects the real studio instead, in the clear-coat pass)
  float coat = uTheme == 0 ? 0.35 : 0.8;
  float fres = 0.04 + 0.96*pow(1.0 - n.z, 5.0);
  float sheen = exp(-pow((p.x/uView.x)*0.8 + (p.y/uView.y) - 0.55, 2.0)*14.0);
  col += vec3(1.0, 0.95, 0.88) * sheen * coat * 0.10 + fres*0.05;
#endif
  if(uTheme == 2) col += rgb(0x5B3BA6) * 0.10 * exp(-dpool*dpool*1.4);   // violet ambience
  vec2 q = p/uView - 0.5; col *= 1.0 - dot(q,q)*(uTheme == 0 ? 0.75 : 0.55);
  o = vec4(encode(col), 1.0);
}`;

  // ---------- the bench's finish: a clear coat reflecting the studio ----------
  // Polish is what makes a fine table read as fine. The coat reflects the same
  // studio the frames do, seen from a camera at a finite height above the
  // middle of the screen, so the reflection moves across the table instead of
  // being one flat tint: the overhead scrim gives a soft broad sheen, and toward
  // the key's corner the key softbox shows as a warm glare. Walnut boards are
  // very slightly cupped, so the sheen bends at each joint; stone is flat with a
  // faint ripple in the polish. Blended over the bench as F*reflection + (1-F)*bench.
  const BENCHCOAT_FS = COMMON + `
uniform samplerCube uEnv; uniform float uEnvMaxLod; uniform vec2 uView; uniform int uTheme;
in vec2 vP; out vec4 o;
const float WAL_MM = 0.75, WAL_BOARD = 232.0, WAL_OFF = 61.0;
void main(){
  vec2 p = vP;
  vec3 n = vec3(0.0, 0.0, 1.0);
  float rough, strength;
  if(uTheme == 0){
    float yb = fract((p.y*WAL_MM + WAL_OFF)/WAL_BOARD);
    float cup = 0.016 + 0.01*hash(int(floor((p.y*WAL_MM + WAL_OFF)/WAL_BOARD)), 9, 31u);
    n = normalize(vec3(gfbm(p*0.004, 2, 41u)*0.006, -(yb - 0.5)*2.0*cup, 1.0));
    rough = 0.11; strength = 0.9;                       // French polish over open-ish grain
  } else {
    n = normalize(vec3(gfbm(p*0.006, 2, 43u)*0.004, gfbm(p*0.006 + 9.0, 2, 47u)*0.004, 1.0));
    rough = 0.06; strength = 1.0;                       // honed and polished stone
  }
  vec3 cam = vec3(uView*0.5, uView.x*0.95);
  vec3 V = normalize(cam - vec3(p, 0.0));
  vec3 r = reflect(-V, n);
  float nv = max(dot(n, V), 0.0);
  float F = (0.04 + 0.96*pow(1.0 - nv, 5.0))*strength;
  vec3 refl = textureLod(uEnv, r, sqrt(rough)*uEnvMaxLod).rgb;
  o = vec4(refl*F, F);
}`;

  const QUAD_VS = `#version 300 es
in vec2 aPos; uniform vec4 uRect; uniform vec2 uView; out vec2 vP;
void main(){ vec2 p = mix(uRect.xy, uRect.zw, aPos); vP = p; vec2 c = p/uView*2.0 - 1.0; gl_Position = vec4(c.x, -c.y, 0.0, 1.0); }`;

  const BLIT_FS = `#version 300 es
precision highp float; uniform sampler2D uTex; uniform vec2 uRes; out vec4 o;
void main(){ o = texture(uTex, gl_FragCoord.xy / uRes); }`;

  // A quad over the whole target, for the passes that work in screen space.
  const FULL_VS = `#version 300 es
in vec2 aPos; void main(){ gl_Position = vec4(aPos*2.0 - 1.0, 0.0, 1.0); }`;

  // ---------- bloom (Jimenez: weighted downsample pyramid, tent upsample) ----------
  // No threshold. The whole image goes through the chain and is mixed back at a
  // low level, so only genuinely bright pixels show a glow and nothing pops on
  // or off as trays move.
  const DOWN_FS = `#version 300 es
precision highp float;
uniform sampler2D uTex; uniform vec2 uTexel, uRes; uniform int uFirst;
out vec4 o;
float luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
void main(){
  vec2 uv = gl_FragCoord.xy/uRes, d = uTexel;
  vec3 a = texture(uTex, uv + d*vec2(-2.0, 2.0)).rgb, b = texture(uTex, uv + d*vec2(0.0, 2.0)).rgb, c = texture(uTex, uv + d*vec2(2.0, 2.0)).rgb;
  vec3 e = texture(uTex, uv + d*vec2(-2.0, 0.0)).rgb, f = texture(uTex, uv).rgb,                    g = texture(uTex, uv + d*vec2(2.0, 0.0)).rgb;
  vec3 h = texture(uTex, uv + d*vec2(-2.0,-2.0)).rgb, i = texture(uTex, uv + d*vec2(0.0,-2.0)).rgb, j = texture(uTex, uv + d*vec2(2.0,-2.0)).rgb;
  vec3 k = texture(uTex, uv + d*vec2(-1.0, 1.0)).rgb, l = texture(uTex, uv + d*vec2(1.0, 1.0)).rgb;
  vec3 m = texture(uTex, uv + d*vec2(-1.0,-1.0)).rgb, n = texture(uTex, uv + d*vec2(1.0,-1.0)).rgb;
  vec3 r;
  if(uFirst == 1){
    // First step only: weight each group of four by 1/(1+brightness), so one
    // runaway pixel cannot flicker into a firefly as the image moves.
    vec3 g0 = (k+l+m+n)*0.25, g1 = (a+b+e+f)*0.25, g2 = (b+c+f+g)*0.25, g3 = (e+f+h+i)*0.25, g4 = (f+g+i+j)*0.25;
    float w0 = 0.500/(1.0+luma(g0)), w1 = 0.125/(1.0+luma(g1)), w2 = 0.125/(1.0+luma(g2));
    float w3 = 0.125/(1.0+luma(g3)), w4 = 0.125/(1.0+luma(g4));
    r = (g0*w0 + g1*w1 + g2*w2 + g3*w3 + g4*w4)/max(w0+w1+w2+w3+w4, 1e-6);
  } else {
    r = f*0.125 + (a+c+h+j)*0.03125 + (b+e+g+i)*0.0625 + (k+l+m+n)*0.125;
  }
  o = vec4(r, 1.0);
}`;

  const UP_FS = `#version 300 es
precision highp float;
uniform sampler2D uTex; uniform vec2 uTexel, uRes; uniform float uRadius;
out vec4 o;
void main(){
  vec2 uv = gl_FragCoord.xy/uRes, d = uTexel*uRadius;
  vec3 s = texture(uTex, uv + d*vec2(-1.0, 1.0)).rgb + texture(uTex, uv + d*vec2(1.0, 1.0)).rgb
         + texture(uTex, uv + d*vec2(-1.0,-1.0)).rgb + texture(uTex, uv + d*vec2(1.0,-1.0)).rgb;
  s += (texture(uTex, uv + d*vec2(0.0, 1.0)).rgb + texture(uTex, uv + d*vec2(-1.0, 0.0)).rgb
      + texture(uTex, uv + d*vec2(1.0, 0.0)).rgb + texture(uTex, uv + d*vec2(0.0,-1.0)).rgb) * 2.0;
  s += texture(uTex, uv).rgb * 4.0;
  o = vec4(s/16.0, 1.0);
}`;

  // ---------- the photographer's studio the metal reflects ----------
  // Polished metal looks like whatever it reflects, so the frames get a real
  // studio to reflect instead of a vague warm room: a near-black space, one
  // long key softbox placed exactly where the key light is (so the scene keeps
  // one light), a cooler kicker strip opposite, a soft overhead scrim brighter
  // toward the key, dark gaps between them (the "black flags" product
  // photographers use to give metal its edges), and a dim bounce off the bench
  // below the horizon in the bench's own colour.
  // Built once on the graphics card whenever the light or bench changes,
  // blurred per roughness, and then read with a single texture lookup.
  // The direction a cube map texel stands for, in the GL cube-map convention, so
  // that what is written here is exactly what texture(cube, r) reads back.
  const FACEDIR = `
vec3 faceDir(int f, vec2 uv){
  vec2 s = uv*2.0 - 1.0;
  vec3 d = f==0 ? vec3(1.0, -s.y, -s.x) : f==1 ? vec3(-1.0, -s.y, s.x) : f==2 ? vec3(s.x, 1.0, s.y)
         : f==3 ? vec3(s.x, -1.0, -s.y) : f==4 ? vec3(s.x, -s.y, 1.0) : vec3(-s.x, -s.y, -1.0);
  return normalize(d);
}
`;
  const STUDIO = FACEDIR + `
uniform vec3 uL, uKey; uniform float uFill, uKeyOn; uniform sampler2D uBench;
// A flat rectangular softbox facing the centre of the room. q is where the ray
// meets the softbox's own plane, so straight edges stay straight.
float softbox(vec3 r, vec3 c, float halfLong, float halfNarrow, float soft){
  float rc = dot(r, c); if(rc <= 0.0) return 0.0;
  vec3 up = abs(c.z) > 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0);
  vec3 t1 = normalize(cross(up, c)), t2 = cross(c, t1);
  vec2 q = vec2(dot(r, t1), dot(r, t2))/rc;
  float m = smoothstep(halfLong + soft, halfLong - soft, abs(q.x)) * smoothstep(halfNarrow + soft, halfNarrow - soft, abs(q.y));
  return m * (1.0 - 0.22*q.x*q.x/(halfLong*halfLong));      // diffusion fabric is a little hotter in the middle
}
// Seen from straight above, a rim facet tilted t degrees shows the room 2t
// degrees from overhead. The rims' flats (under ~16 degrees) therefore see the
// scrim and read as gold, their shoulders see the key and the dark flags, the
// steeper flanks see the low ring of cards, and the steepest see the bench.
vec3 studio(vec3 r){
  vec2 L2 = normalize(uL.xy + 1e-5);
  vec3 room = vec3(0.022, 0.019, 0.016);
  vec3 bounce = textureLod(uBench, vec2(0.5), 20.0).rgb * 0.7;       // the bench's average colour, from its last mip
  vec3 col = mix(room, bounce*uFill, smoothstep(0.02, -0.35, r.z));
  float th = acos(clamp(r.z, -1.0, 1.0));
  // overhead diffusion scrim, about 32 degrees across, brighter toward the key
  float scrim = smoothstep(0.66, 0.56, th);
  float grad = clamp(0.5 + 0.5*dot(r.xy, L2)/0.55, 0.0, 1.0);
  // Deep on the far side, so the light has a direction. Peak kept below the tone
  // curve's shoulder, where gold would desaturate toward white; the key carries
  // the hot highlights.
  col += vec3(1.0, 0.97, 0.92) * scrim * mix(0.06, 0.50, grad*grad) * uFill;
  // the key: a big softbox exactly where the key light is
  col += uKey * 2.2 * uKeyOn * softbox(r, normalize(uL), 0.55, 0.26, 0.03);
  // a cool kicker strip opposite, a little lower
  vec3 kick = normalize(vec3(-L2*0.819, 0.574));                     // 55 degrees from overhead
  col += vec3(0.80, 0.88, 1.0) * 2.6 * uFill * softbox(r, kick, 0.34, 0.07, 0.014);
  // a ring of four white cards low around the set, black gaps between them;
  // the cards facing the key catch more of it, as real fill cards do
  for(int i=0;i<4;i++){
    float phi = atan(L2.y, L2.x) + 0.7854 + float(i)*1.5708;
    vec2 az = vec2(cos(phi), sin(phi));
    vec3 c = vec3(az*0.951, 0.309);                                  // 72 degrees from overhead
    float lit = 0.22 + 0.50*max(-dot(az, L2), 0.0);
    col += vec3(1.0, 0.96, 0.90) * lit * uFill * softbox(r, c, 0.58, 0.18, 0.03);
  }
  return col;
}
`;
  // Low-discrepancy sample points and GGX importance sampling, shared by the
  // prefilter and the DFG table. WebGL2 has no bitfieldReverse, so the radical
  // inverse is done by hand.
  const SAMPLING = `
float radinv(uint b){
  b = (b << 16u) | (b >> 16u);
  b = ((b & 0x55555555u) << 1u) | ((b & 0xAAAAAAAAu) >> 1u);
  b = ((b & 0x33333333u) << 2u) | ((b & 0xCCCCCCCCu) >> 2u);
  b = ((b & 0x0F0F0F0Fu) << 4u) | ((b & 0xF0F0F0F0u) >> 4u);
  b = ((b & 0x00FF00FFu) << 8u) | ((b & 0xFF00FF00u) >> 8u);
  return float(b) * 2.3283064365386963e-10;
}
vec2 hammersley(int i, int n){ return vec2(float(i)/float(n), radinv(uint(i))); }
mat3 basisOf(vec3 n){
  vec3 up = abs(n.z) < 0.999 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
  vec3 t = normalize(cross(up, n)); return mat3(t, cross(n, t), n);
}
vec3 sampleGGX(vec2 xi, float a){       // a = roughness squared
  float phi = 2.0*PI*xi.x;
  float ct = sqrt((1.0 - xi.y)/(1.0 + (a*a - 1.0)*xi.y)), st = sqrt(1.0 - ct*ct);
  return vec3(cos(phi)*st, sin(phi)*st, ct);
}
float D_GGX(float nh, float a){ float a2 = a*a, d = nh*nh*(a2 - 1.0) + 1.0; return a2/(PI*d*d); }
`;
  const ENV_FS = COMMON + STUDIO + `
uniform int uFace; uniform float uSize; out vec4 o;
void main(){ o = vec4(studio(faceDir(uFace, gl_FragCoord.xy/uSize)), 1.0); }`;

  // Diffuse light from the studio, without the key (the key's diffuse is added
  // directly so shadows can still act on it): cosine-weighted average of the
  // radiance around each direction, which is exactly what a matte surface sees.
  const IRR_FS = COMMON + STUDIO + SAMPLING + `
uniform int uFace; uniform float uSize; out vec4 o;
void main(){
  vec3 n = faceDir(uFace, gl_FragCoord.xy/uSize); mat3 B = basisOf(n);
  vec3 sum = vec3(0.0); const int NS = 256;
  for(int i=0;i<NS;i++){
    vec2 xi = hammersley(i, NS); float phi = 2.0*PI*xi.x, st = sqrt(xi.y);
    sum += studio(B * vec3(cos(phi)*st, sin(phi)*st, sqrt(1.0 - xi.y)));
  }
  o = vec4(sum/float(NS), 1.0);
}`;

  // Split-sum prefilter (Karis 2013): each mip level is the studio blurred by the
  // GGX lobe of one roughness. Samples read a blurrier source mip where the lobe
  // is wide (filtered importance sampling), so small bright strips do not
  // break into fireflies.
  const PREFILTER_FS = COMMON + FACEDIR + SAMPLING + `
uniform samplerCube uSrc; uniform int uFace; uniform float uSize, uSrcSize, uRough; out vec4 o;
void main(){
  vec3 N = faceDir(uFace, gl_FragCoord.xy/uSize); mat3 B = basisOf(N);
  float a = uRough*uRough;
  float texelSolid = 4.0*PI/(6.0*uSrcSize*uSrcSize);
  vec3 sum = vec3(0.0); float w = 0.0; const int NS = 128;
  for(int i=0;i<NS;i++){
    vec3 H = B * sampleGGX(hammersley(i, NS), a);
    vec3 L = 2.0*dot(N, H)*H - N;
    float nl = dot(N, L);
    if(nl > 0.0){
      float pdf = D_GGX(max(dot(N, H), 0.0), a)*0.25;          // view = normal, so D*NdotH/(4*VdotH) = D/4
      float lod = max(0.5*log2((1.0/(float(NS)*pdf + 1e-6))/texelSolid) + 1.0, 0.0);
      sum += textureLod(uSrc, L, lod).rgb*nl; w += nl;
    }
  }
  o = vec4(sum/max(w, 1e-6), 1.0);
}`;
  // The DFG table: how much of the prefiltered light a GGX surface returns at each
  // viewing angle and roughness, split into the part scaled by F0 (x), the
  // part that is not (y), and the integral of the F82-tint correction term (z). Computed here from the definition rather than taken
  // from a fitted curve. Smith G with k = roughness^2/2, Karis's choice for IBL.
  const DFG_FS = COMMON + SAMPLING + `
uniform vec2 uSize; out vec4 o;
float G1(float x, float k){ return x/(x*(1.0 - k) + k); }
void main(){
  vec2 uv = gl_FragCoord.xy/uSize;
  float nv = max(uv.x, 1e-3), rough = uv.y, a = rough*rough, k = a*0.5;
  vec3 V = vec3(sqrt(1.0 - nv*nv), 0.0, nv);
  float A = 0.0, Bs = 0.0, C = 0.0; const int NS = 512;
  for(int i=0;i<NS;i++){
    vec3 H = sampleGGX(hammersley(i, NS), a);
    vec3 L = 2.0*dot(V, H)*H - V;
    float nl = max(L.z, 0.0), nh = max(H.z, 0.0), vh = max(dot(V, H), 0.0);
    if(nl > 0.0){
      float gv = G1(nv, k)*G1(nl, k)*vh/(nh*nv);
      float fc = pow(1.0 - vh, 5.0);
      A += (1.0 - fc)*gv; Bs += fc*gv;
      C += vh*pow(1.0 - vh, 6.0)*gv;      // the F82-tint correction's shape, mu(1-mu)^6
    }
  }
  o = vec4(A/float(NS), Bs/float(NS), C/float(NS), 1.0);
}`;

  // ---------- the one place light becomes pixels ----------
  // Khronos PBR Neutral, checked line for line against the reference
  // implementation. It leaves colour alone up to a knee and compresses only the
  // highlights, so gold stays gold and white marble stays neutral; the ACES fit
  // this replaces shifted both.
  const FINAL_FS = COMMON + `
uniform sampler2D uScene, uBloom; uniform vec2 uRes; uniform float uExposure, uBloomMix, uSat, uContrast, uAged, uPaint;
out vec4 o;
vec3 pbrNeutral(vec3 c){
  const float startCompression = 0.8 - 0.04;
  const float desaturation = 0.15;
  float x = min(c.r, min(c.g, c.b));
  float offset = x < 0.08 ? x - 6.25*x*x : 0.04;
  c -= offset;
  float peak = max(c.r, max(c.g, c.b));
  if(peak < startCompression) return c;
  float d = 1.0 - startCompression;
  float newPeak = 1.0 - d*d/(peak + d - startCompression);
  c *= newPeak/peak;
  float gg = 1.0 - 1.0/(desaturation*(peak - newPeak) + 1.0);
  return mix(c, vec3(newPeak), gg);
}
// The exact sRGB curve, not a 2.2 power: the power curve crushes the darkest
// values, which is where banding shows on the bench.
vec3 srgbEncode(vec3 c){
  c = clamp(c, 0.0, 1.0);
  return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4)) - 0.055, step(vec3(0.0031308), c));
}
void main(){
  vec2 uv = gl_FragCoord.xy/uRes;
  // A hint of lens fringe toward the edges (colour only, no geometry moves, so the
  // canvas stays registered with the screens laid over it).
  vec2 cu = uv - 0.5; float fr = uAged*0.0022*dot(cu, cu)*4.0;
  vec2 gq = gl_FragCoord.xy;
  vec2 uvs = uv;
  float edgeP = 0.0;
  if(uPaint > 0.0){
    // Wet edges: the whole picture wanders by a pixel or two on slow noise, like pigment finding its own boundary.
    uvs = uv + (vec2(fbm(gq*0.021, 3, 201u), fbm(gq*0.021 + 31.7, 3, 202u)) - 0.5)*3.2*uPaint/uRes;
  }
  vec3 c = vec3(texture(uScene, uvs + cu*fr).r, texture(uScene, uvs).g, texture(uScene, uvs - cu*fr).b);
  if(uPaint > 0.0){
    // Brush: a short smear along a slowly turning stroke direction. Detail survives (mixed, not replaced).
    float ang = fbm(gq*0.0065, 2, 203u)*12.566;
    vec2 sd = vec2(cos(ang), sin(ang))/uRes*uPaint;
    vec3 sm = texture(uScene, uvs - sd*7.0).rgb*0.14 + texture(uScene, uvs - sd*3.5).rgb*0.22 + c*0.28
            + texture(uScene, uvs + sd*3.5).rgb*0.22 + texture(uScene, uvs + sd*7.0).rgb*0.14;
    c = mix(c, sm, 0.55*uPaint);
    // Pigment pools where one tone meets another: a darker rim on edges, from the luminance gradient.
    vec2 e1 = vec2(2.0, 0.0)/uRes, e2 = vec2(0.0, 2.0)/uRes;
    float lx = dot(texture(uScene, uvs + e1).rgb - texture(uScene, uvs - e1).rgb, vec3(0.2126, 0.7152, 0.0722));
    float ly = dot(texture(uScene, uvs + e2).rgb - texture(uScene, uvs - e2).rgb, vec3(0.2126, 0.7152, 0.0722));
    edgeP = smoothstep(0.03, 0.30, length(vec2(lx, ly))/(1.0 + 0.5*dot(c, vec3(0.3333))));
  }
  c = mix(c, texture(uBloom, uv).rgb, uBloomMix);
  c = srgbEncode(pbrNeutral(max(c*uExposure, 0.0)));
  // Overall grade, in display space: saturation about the luma, then contrast about
  // a mid pivot. 1 and 1 leave the picture untouched.
  float yl = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = clamp(mix(vec3(yl), c, uSat), 0.0, 1.0);
  c = clamp((c - 0.40)*uContrast + 0.40, 0.0, 1.0);
  // Aged, unfinished: warm brass in the lights, cool tarnish in the shadows, black
  // lifted a little (not crushed, not gone), a darker corner and fine film grain.
  float ya = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = mix(c, c*mix(vec3(0.86, 0.95, 1.02), vec3(1.07, 1.0, 0.86), smoothstep(0.15, 0.7, ya)), uAged);
  c = mix(c, c*0.93 + 0.045*vec3(1.0, 0.92, 0.80), uAged);
  vec2 vq = uv - 0.5; c *= 1.0 - uAged*0.55*dot(vq, vq);
  ivec2 gp = ivec2(gl_FragCoord.xy);
  c += (hash(gp.x, gp.y, 0xC2B2AE35u) - 0.5)*0.045*uAged*(1.0 - ya*0.6);
  if(uPaint > 0.0){
    float yp = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float dark = 1.0 - yp;
    // Pigment pools at edges, in the colour's own hue (a deeper version of itself, not grey).
    c = mix(c, c*c*0.85, edgeP*0.55*uPaint);
    // Translucent wash: the darkest darks never reach black, the lights stay near paper, and the colour is a glaze over white.
    vec3 paper = vec3(0.975, 0.945, 0.885);
    c = mix(c, paper - (paper - c)*0.84, 0.75*uPaint);
    // Granulation: pigment settles into the paper's tooth, so mid and dark tones are blotchy, light tones are not.
    float gran = fbm(gq*0.42, 3, 211u);
    c *= 1.0 - uPaint*0.20*smoothstep(0.35, 0.80, gran)*smoothstep(0.10, 0.65, dark);
    c *= 1.0 + uPaint*0.07*(fbm(gq*0.05, 3, 212u) - 0.5)*2.0;          // uneven wash density
    // Colored pencil: loose diagonal hatching in the shadows, broken up by the tooth so it never reads as a regular pattern.
    float hs = dot(gq, vec2(0.7193, 0.6947))/4.6 + 3.0*fbm(gq*0.035, 2, 213u);
    float hatch = smoothstep(0.30, 0.50, fract(hs))*(1.0 - smoothstep(0.50, 0.72, fract(hs)));
    float tooth = smoothstep(0.30, 0.75, vnoise(gq*0.55, 214u));
    c *= 1.0 - uPaint*0.16*hatch*tooth*smoothstep(0.18, 0.62, dark);
    // Paper tooth over everything: fine grain plus a few fibres, showing most in the lights.
    float fib = vnoise(gq*vec2(0.9, 0.22), 215u)*0.6 + vnoise(gq*vec2(0.25, 0.8), 216u)*0.4;
    float grain = hash(int(gq.x), int(gq.y), 0xA511E9B3u);
    c *= 1.0 + uPaint*(0.10*(fib - 0.5) + 0.07*(grain - 0.5))*(0.55 + 0.9*yp);
    c = clamp(c, 0.0, 1.0);
  }
  // A triangular-noise dither of one step, faded out at pure black and white so
  // the deepest shadows stay black. Removes the banding in smooth gradients.
  ivec2 ip = ivec2(gl_FragCoord.xy);
  float tri = hash(ip.x, ip.y, 0x9E3779B9u) + hash(ip.x, ip.y, 0x85EBCA6Bu) - 1.0;
  float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
  o = vec4(c + tri*(1.0/255.0)*smoothstep(0.0, 0.05, lum)*smoothstep(1.0, 0.95, lum), 1.0);
}`;

  // ---------- trays, blades, lantern, bar ----------
  const TRAY_FS = COMMON + `
#define MAXV ${MAXV}
uniform vec2 uQ[MAXV]; uniform int uN; uniform float uR, uRim, uPad, uHeight, uThick, uBack, uGloss;
uniform int uRimMat, uFloorMat, uInlay, uScreen; uniform float uSeed, uFocus, uWear, uOrnate, uRamp, uRampN; uniform int uOrnStyle;
uniform vec4 uGlow, uEmissive, uContent; uniform vec2 uCenter;
uniform vec3 uL, uKey; uniform float uAmb; uniform vec2 uView, uRes; uniform sampler2D uBench;
uniform vec3 uL2d, uK2;                  // a second, cooler directional light from another side (uK2 = 0: off)
uniform vec3 uLamp;                      // the lantern as a point light: xy = where it is, z = how high above the bench (0 = off, one distant light as before)
in vec2 vP; out vec4 o;

float sdPoly(vec2 p, out vec2 grad){
  float d = dot(p-uQ[0], p-uQ[0]); vec2 bb = p - uQ[0]; float s = 1.0;
  for(int i=0;i<MAXV;i++){
    if(i>=uN) break;
    int j = i==0 ? uN-1 : i-1;
    vec2 vi = uQ[i], vj = uQ[j];
    vec2 e = vj - vi, w = p - vi;
    vec2 b = w - e*clamp(dot(w,e)/dot(e,e), 0.0, 1.0);
    float db = dot(b,b); if(db < d){ d = db; bb = b; }
    bool c1 = p.y >= vi.y, c2 = p.y < vj.y, c3 = e.x*w.y > e.y*w.x;
    if((c1&&c2&&c3) || (!c1&&!c2&&!c3)) s = -s;
  }
  float l = sqrt(d); grad = s*bb/max(l, 1e-4); return s*l;
}
float sdPolyOnly(vec2 p){ vec2 g; return sdPoly(p, g); }

struct Surf { vec3 alb; vec3 f0; float rough; float metal; float coat; float h; float sparkle; float irid; float glass; vec3 tint; vec3 edge; };

// Metal reflectance at normal incidence, linear. Gold, brass, copper and silver
// are Filament's measured table (given there in sRGB) converted exactly to
// linear. Rose gold, bronze and champagne have no measured data and are tuned
// by eye. edge is the F82 tint (OpenPBR specular_color): the fraction of the
// Schlick curve kept at the grazing angle near 82 degrees; also tuned by eye.
Surf metalSurf(int m, vec2 p, vec2 tdir){
  Surf s; s.coat = 0.0; s.sparkle = 0.0; s.irid = 0.0; s.glass = 0.0; s.tint = vec3(0); s.metal = 1.0;
  vec3 c = m==0 ? vec3(1.000,0.692,0.285) : m==1 ? vec3(0.98,0.66,0.55) : m==2 ? vec3(0.955,0.787,0.307)
         : m==3 ? vec3(0.933,0.507,0.342) : m==4 ? vec3(0.925,0.935,0.955) : m==5 ? vec3(0.64,0.50,0.31) : m==7 ? vec3(0.66,0.69,0.74) : vec3(0.95,0.85,0.66);
  s.edge = m==0 ? vec3(1.0,0.94,0.86) : m==1 ? vec3(1.0,0.93,0.92) : m==2 ? vec3(1.0,0.95,0.88)
         : m==3 ? vec3(1.0,0.90,0.86) : m==4 ? vec3(1.0) : m==5 ? vec3(1.0,0.92,0.84) : m==7 ? vec3(0.96,0.98,1.0) : vec3(1.0,0.98,0.95);
  float along = dot(p, tdir), across = dot(p, vec2(-tdir.y, tdir.x));
  float brush = vnoise(vec2(along*0.04, across*1.6), 3u);
  s.f0 = c; s.alb = c;
  s.rough = clamp((m==0||m==1||m==6 ? 0.085 : m==4 ? 0.075 : m==7 ? 0.11 : 0.13) + brush*0.04, 0.04, 0.9);
  s.h = brush*0.15;
  return s;
}

// What a frame can be made of: any of the metals, or a pearly non-metal (shell, opal) that
// gets its colour from thin-film shimmer and a glossy coat instead of a metal's tinted mirror.
Surf rimSurf(int m, vec2 p, vec2 tdir){
  if(m < 10) return metalSurf(m, p, tdir);
  Surf s; s.f0 = vec3(0.04); s.metal = 0.0; s.coat = 0.9; s.h = 0.0; s.sparkle = 0.0; s.irid = 0.0; s.glass = 0.0; s.tint = vec3(0); s.rough = 0.14; s.edge = vec3(1.0);
  float across = dot(p, vec2(-tdir.y, tdir.x));
  if(m == 53){                                   // opal: milky body, patches of fire
    float n = fbm(p*0.045, 4, 71u), n2 = fbm(p*0.16, 3, 72u);
    vec3 body = vec3(0.86, 0.91, 0.96);
    vec3 aqua = vec3(0.55, 0.85, 0.90), green = vec3(0.60, 0.88, 0.70), gold = vec3(0.95, 0.80, 0.58), blue = vec3(0.55, 0.66, 0.92);
    vec3 fire = mix(mix(aqua, green, smoothstep(0.3, 0.6, n2)), mix(blue, gold, smoothstep(0.4, 0.8, n2)), smoothstep(0.45, 0.75, n));
    float flash = smoothstep(0.50, 0.78, n)*smoothstep(0.25, 0.55, n2);
    s.alb = lin(mix(body, fire, flash*0.50)); s.irid = 0.40; s.rough = 0.12; s.coat = 1.0;
    return s;
  }
  // shell (mother-of-pearl): cream with blush and sea-green drifting in slow growth bands
  float band = 0.5 + 0.5*sin(across*0.12 + fbm(p*0.012, 4, 73u)*5.0);
  vec3 cream = vec3(0.96, 0.925, 0.89), blush = vec3(0.94, 0.80, 0.82), sea = vec3(0.78, 0.90, 0.88);
  vec3 col = mix(mix(cream, blush, smoothstep(0.35, 0.75, band)), sea, smoothstep(0.55, 0.9, fbm(p*0.02 + 5.0, 3, 74u))*0.55);
  s.alb = lin(col); s.irid = 0.45; s.rough = 0.13; s.coat = 0.95;
  return s;
}

// Age. Gilded metal wears the way real gilding does: the gold rubs through on the
// parts hands and edges touch and shows the red clay under it, tarnish gathers in the
// recesses, a few chips show the dark substrate, and fine scratches dull the shine.
// hi = how exposed this spot is (0..1), lo = how recessed (0..1). Nothing happens at uWear = 0.
void applyWear(inout Surf s, vec2 p, float hi, float lo){
  if(uWear <= 0.0) return;
  vec2 q = p + vec2(uSeed*17.0, uSeed*29.0);
  float n1 = fbm(q*0.11, 4, 91u), n2 = fbm(q*0.55, 3, 92u);
  float id; float f1 = worley(q*0.13, 93u, id);
  // gold rubbed through, only where it is exposed and only in patches
  float thr = mix(1.30, 0.95, uWear);
  float worn = smoothstep(thr, thr + 0.12, 0.5 + hi*0.35 + (n1 - 0.5)*1.5 + (n2 - 0.5)*0.5);
  // tarnish in the recesses
  float tarn = smoothstep(0.15, 0.70, lo)*smoothstep(0.20, 0.65, n1 + 0.25*n2)*uWear;
  // chips: a few small, hard-edged losses of the surface
  float chipGate = smoothstep(mix(0.90, 0.40, uWear), mix(0.98, 0.50, uWear), n1*0.8 + n2*0.3 + hi*0.25);
  float chip = (1.0 - smoothstep(0.05, 0.11, f1)) * chipGate;
  // fine scratches
  float sc = vnoise(vec2(dot(q, vec2(0.82, 0.57))*0.018, dot(q, vec2(-0.57, 0.82))*2.3), 94u);
  float scr = smoothstep(0.80, 0.90, sc) * (0.4 + 0.6*uWear);
  vec3 under = uRimMat == 4 ? vec3(0.10, 0.10, 0.11) : vec3(0.16, 0.06, 0.04);   // gilding shows red clay; silver just dulls and darkens
  s.f0 = mix(s.f0, under, worn*0.95);
  s.f0 = mix(s.f0, s.f0*vec3(0.30, 0.26, 0.14), tarn*0.90);       // tarnish
  s.f0 = mix(s.f0, vec3(0.045, 0.035, 0.03), chip);                // chip down to the substrate
  s.f0 *= 1.0 - 0.20*uWear*n1 - 0.12*scr;
  s.alb = s.f0;
  s.rough = clamp(s.rough + worn*0.30 + tarn*0.30 + chip*0.35 + scr*0.10 + uWear*0.06*n2, 0.05, 0.95);
}

Surf floorSurf(int m, vec2 p, vec2 rel, uint seed){
  if(m < 10){ Surf ms = metalSurf(m, p, vec2(1.0, 0.0)); ms.rough = 0.32; ms.h *= 0.25; return ms; }
  Surf s; s.f0 = vec3(0.04); s.metal = 0.0; s.coat = 0.0; s.h = 0.0; s.sparkle = 0.0; s.irid = 0.0; s.glass = 0.0; s.tint = vec3(0); s.rough = 0.5; s.edge = vec3(1.0);
  float x = p.x, y = p.y;
  if(m >= 10 && m <= 14){
    vec3 base, vein, cloud;
    if(m==10){ base=rgb(0xF2EEE6); vein=rgb(0x8C8478); cloud=rgb(0xD9D2C6); }
    else if(m==11){ base=rgb(0xF3E4DA); vein=rgb(0xB0806C); cloud=rgb(0xE6C7B8); }
    else if(m==12){ base=rgb(0x1E4B40); vein=rgb(0xC8DCCF); cloud=rgb(0x2F6A5A); }
    else if(m==13){ base=rgb(0x17181B); vein=rgb(0xE8E2D4); cloud=rgb(0x2A2B30); }
    else { base=rgb(0x1A1433); vein=rgb(0xB9A6E6); cloud=rgb(0x2C2152); }
    float sc = 0.0042;
    float warp = fbm(vec2(x,y)*sc*2.0, 6, seed);
    float t = sin((x*0.82 + y*0.57)*sc*9.0 + warp*9.5);
    float v1 = pow(1.0-abs(t), 26.0);
    float t2 = sin((x*-0.4 + y*0.92)*sc*5.0 + fbm(vec2(x,y)*sc*3.0, 5, seed+41u)*12.0);
    float v2 = pow(1.0-abs(t2), 60.0)*0.7;
    float c = fbm(vec2(x,y)*sc*1.2, 5, seed+77u);
    vec3 col = mix(base, cloud, smoothstep(0.35, 0.8, c)*0.55);
    col = mix(col, vein, clamp(v1*0.85 + v2, 0.0, 1.0));
    s.alb = lin(col); s.rough = 0.10 + c*0.06; s.coat = 0.9; s.h = (v1+v2)*0.04;
    return s;
  }
  if(m == 20 || m == 21){
    float id1, id2, id3;
    float f1 = worley(vec2(x,y)*0.16, seed, id1);
    worley(vec2(x,y)*0.42, seed+5u, id2);
    worley(vec2(x,y)*1.10, seed+9u, id3);
    vec3 col;
    if(m == 20){
      vec3 quartz=rgb(0xD9D4CD), feld=rgb(0xD4A897), feld2=rgb(0xB98476), bio=rgb(0x16151A), grey=rgb(0x8F8984);
      col = id1<0.30 ? quartz : id1<0.52 ? feld : id1<0.66 ? feld2 : id1<0.84 ? grey : bio;
      col = mix(col, id2<0.5 ? quartz : bio, (id2>0.78 || id2<0.12) ? 0.85 : 0.0);
      col = mix(col, id3<0.5 ? grey : bio, id3>0.86 ? 0.7 : 0.0);
    } else {
      float j1, j2; worley(vec2(x,y)*0.24, seed+21u, j1); worley(vec2(x,y)*0.7, seed+23u, j2);
      vec3 a=rgb(0x0B0C0F), b=rgb(0x1C1E23), c=rgb(0x3E414A), d=rgb(0x8A8E98);
      col = j1<0.58 ? a : j1<0.86 ? b : j1<0.97 ? c : d;
      col = mix(col, j2<0.6 ? a : c, j2>0.8 ? 0.7 : 0.0);
      col = mix(col, id2<0.5 ? a : c, id2>0.85 ? 0.8 : 0.0);
      col = mix(col, d, id3>0.93 ? 0.6 : 0.0);
    }
    col *= 0.9 + 0.18*vnoise(vec2(x,y)*2.0, seed+2u);
    s.alb = lin(col); s.rough = 0.10; s.coat = 0.95; s.h = smoothstep(0.0, 0.06, f1)*0.03;
    s.sparkle = hash(int(x), int(y), seed+99u) > 0.996 ? 0.8 : 0.0;
    return s;
  }
  if(m == 30){
    float warp = fbm(vec2(x,y)*0.006, 5, seed);
    float band = y*0.035 + warp*6.0 + fbm(vec2(x,y)*0.02, 3, seed+3u)*1.5;
    float strata = 0.5 + 0.5*sin(band), fine = 0.5 + 0.5*sin(band*3.7 + 1.3);
    vec3 col = mix(mix(rgb(0xD8B38A), rgb(0xC08A5C), strata), rgb(0xE6CBA6), fine*0.35);
    float grain = hash(int(x), int(y), seed+8u);
    col *= (0.86 + 0.22*grain) * (0.9 + 0.2*vnoise(vec2(x,y)*0.3, seed+4u));
    s.alb = lin(col); s.rough = 0.88; s.h = grain*0.35 + strata*0.2;
    return s;
  }
  if(m >= 40 && m <= 42){
    vec3 light = m==40 ? rgb(0x6E4A30) : m==41 ? rgb(0xB8925E) : rgb(0x7C3420);
    vec3 dark  = m==40 ? rgb(0x2E1C12) : m==41 ? rgb(0x6E4C2C) : rgb(0x3A140A);
    float drift = fbm(vec2(x*0.0007, y*0.002), 3, seed+5u)*22.0;
    float gy = y + drift;
    float fib = fbm(vec2(x*0.0015, gy*0.30), 5, seed);
    float ring = fract(gy*0.045 + fbm(vec2(x*0.0006, gy*0.01), 3, seed+2u)*2.2);
    float late = smoothstep(0.55, 0.95, ring)*smoothstep(1.0, 0.95, ring);
    float figure = fbm(vec2(x*0.0009, gy*0.012), 3, seed+11u);
    float pore = smoothstep(0.82, 0.9, vnoise(vec2(x*0.09, gy*1.6), seed+13u));
    vec3 col = mix(light, dark, clamp(late*0.38 + (fib-0.5)*0.22 + (figure-0.5)*0.6 + 0.22, 0.0, 1.0));
    col *= 1.0 - pore*0.28;
    s.alb = lin(col); s.rough = 0.35; s.coat = 0.6; s.h = late*0.04 + fib*0.03 - pore*0.05;
    return s;
  }
  if(m == 50){
    float radial = atan(rel.x, -rel.y);
    float ribs = pow(0.5 + 0.5*cos(radial*26.0), 0.7);
    float growth = 0.5 + 0.5*sin(length(rel)*0.11 + fbm(vec2(x,y)*0.01, 4, seed)*5.0);
    vec3 base = mix(rgb(0xF6EEE8), rgb(0xE8D6CC), growth*0.45 + (1.0-ribs)*0.25);
    s.alb = lin(base); s.rough = 0.16; s.coat = 0.8; s.h = ribs*0.4 + growth*0.05; s.irid = 0.7;
    return s;
  }
  if(m == 51 || m == 52){
    float n1 = fbm(vec2(x,y)*0.006, 5, seed), n2 = fbm(vec2(x,y)*0.03, 3, seed+2u);
    vec3 warm=rgb(0xFAF7F0), mid=rgb(0xE9E6DF), cool=rgb(0xCFD9DF), blush=rgb(0xEBDCE6);
    vec3 col = mix(mix(warm, mid, n1), cool, smoothstep(0.55, 0.8, n1)*0.6);
    col = mix(col, blush, smoothstep(0.6, 0.85, n2)*0.35);
    float sheen = fbm(vec2(x*0.0025 + n1, y*0.0025), 3, seed+5u);
    col = mix(col, cool, smoothstep(0.45, 0.75, sheen)*0.45);
    float ph = sheen*1.8 + n1*0.9;
    vec3 film = 0.5 + 0.5*cos(6.283*(ph + vec3(0.0, 0.33, 0.67)));
    col *= vec3(0.86) + film*0.16;
    s.alb = lin(col); s.rough = 0.24; s.coat = 0.7; s.h = n2*0.03 + sheen*0.05; s.irid = 0.45;
    if(m == 52){ s.glass = 0.55; s.tint = lin(rgb(0xF4F1EC)); }    // frosted pearl glass: the bench shows through, milky
    return s;
  }
  if(m == 60){
    float wx = fbm(vec2(x,y)*0.006, 4, seed+30u)*90.0, wy = fbm(vec2(x*0.006+7.0, y*0.006), 4, seed+31u)*90.0;
    vec2 Q = vec2(x+wx, y+wy);
    float a = fbm(vec2(Q.x*0.011, Q.y*0.026), 6, seed), b = fbm(vec2(Q.x*0.04, Q.y*0.09), 4, seed+4u);
    float spot = smoothstep(0.52, 0.60, a + (b-0.5)*0.22), core = smoothstep(0.60, 0.70, a);
    float fleck = smoothstep(0.70, 0.74, b)*(1.0-spot);
    vec3 col = mix(rgb(0xD99A45), rgb(0x9C5418), clamp((a-0.3)*2.2, 0.0, 1.0));
    col = mix(col, rgb(0x55230A), spot*0.9 + fleck*0.5);
    col = mix(col, rgb(0x1E0B04), core*0.85);
    s.alb = lin(col); s.rough = 0.05; s.coat = 1.0;
    return s;
  }
  if(m >= 70 && m <= 74){
    vec3 tint = m==70 ? rgb(0x5A2E7E) : m==71 ? rgb(0x135C47) : m==72 ? rgb(0x1B4F86) : m==73 ? rgb(0x2A2C33) : rgb(0x6E1A26);
    float depth = fbm(vec2(x,y)*0.003, 4, seed);
    float swirl = fbm(vec2(x*0.012 + depth*2.0, y*0.012), 3, seed+6u);
    s.tint = lin(tint) * (0.75 + 0.5*depth + swirl*0.25);
    s.alb = s.tint * 0.35; s.rough = 0.03; s.coat = 1.0; s.h = swirl*0.01; s.glass = 0.42;
    return s;
  }
  if(m == 75){
    float n1 = fbm(vec2(x,y)*0.004, 4, seed); float id; float f = worley(vec2(x,y)*0.08, seed+3u, id);
    float bubble = (1.0 - smoothstep(0.0, 0.12, f))*(id > 0.8 ? 1.0 : 0.0);
    vec3 col = mix(rgb(0x0B2A20), rgb(0x1C5A47), n1)*(1.0 + bubble*0.25);
    s.alb = lin(col); s.rough = 0.05; s.coat = 1.0; s.h = -bubble*0.05;
    return s;
  }
  if(m == 76){
    float n1 = fbm(vec2(x,y)*0.003, 4, seed), peel = fbm(vec2(x,y)*0.05, 2, seed+7u);
    s.alb = lin(mix(rgb(0x040507), rgb(0x150F0E), n1*0.6)); s.rough = 0.04; s.coat = 1.0; s.h = peel*0.006;
    return s;
  }
  if(m == 80){
    float n1 = fbm(vec2(x,y)*0.008, 5, seed), fib = fbm(vec2(x*0.08, y*0.08), 3, seed+3u);
    vec3 col = mix(rgb(0xF3E7CF), rgb(0xE2CFA9), n1*0.7) * (0.95 + fib*0.08);
    s.alb = lin(col); s.rough = 0.7; s.coat = 0.15; s.h = fib*0.03;
    return s;
  }
  float id; float f = worley(vec2(x,y)*0.18, seed, id);
  s.alb = lin(rgb(0x4A2C1C)*(0.85 + 0.3*id)); s.rough = 0.62; s.h = smoothstep(0.0, 0.5, f)*0.1;
  return s;
}

// A warm, lamp-lit room for reflections: dark low, warm high, a big softbox toward
// the key light, a cool fill opposite, and two hot strip lights.
vec3 env(vec3 r, float rough){
  float up = r.z, hz = r.y;
  vec3 low = vec3(0.05,0.035,0.025), mid = vec3(0.30,0.23,0.17), high = vec3(0.80,0.70,0.55);
  float t = clamp(up*0.6 + 0.4 - hz*0.35, 0.0, 1.0);
  vec3 room = t < 0.5 ? mix(low, mid, t*2.0) : mix(mid, high, (t-0.5)*2.0);
  float spread = 6.0 + 260.0*(1.0-rough)*(1.0-rough);
  float key = pow(max(dot(r, uL), 0.0), spread);
  vec3 fillDir = normalize(vec3(-uL.x, -uL.y, 0.45));
  float fill = pow(max(dot(r, fillDir), 0.0), 4.0 + 50.0*(1.0-rough));
  float sharp = 30.0*(1.0-rough) + 3.0;
  float strip = exp(-(hz+0.35)*(hz+0.35)*sharp*3.0) * clamp(up*1.5 + 0.3, 0.0, 1.0);
  float strip2 = exp(-(r.x-0.45)*(r.x-0.45)*sharp*2.0) * clamp(up*1.2, 0.0, 1.0);
  return room*0.85 + uKey*3.4*key + vec3(0.45,0.55,0.7)*fill + vec3(3.0,2.7,2.2)*strip + vec3(1.3,1.15,0.95)*strip2*0.8;
}
vec3 fresnel(vec3 f0, float c){ return f0 + (1.0-f0)*pow(1.0-c, 5.0); }
float ggx(float nh, float r){ float a = r*r, a2 = a*a, d = nh*nh*(a2-1.0) + 1.0; return a2/(PI*d*d + 1e-6); }
// Light as seen from this pixel. With the lantern on, every pixel has its own direction to it, so
// highlights, shading and shadows all fan out from one traceable place and weaken with distance.
vec3 gL; vec3 gShift; float gAtt; float gOcc = 1.0;   // gOcc: how much of the studio this facet can see (facets turned away from every light go dark)

// Geometric specular antialiasing (Kaplanyan 2016, Tokuyoshi & Kaplanyan 2019),
// as Filament implements it, with Filament's defaults (variance 0.15, threshold
// 0.2). Filament feeds it dFdx/dFdy of the normal; here the rim is shaded
// inside a branch where screen derivatives are undefined, so the caller passes
// the normal's change per pixel, worked out from the rim profile's curvature.
float aaRough(float rough, float dnPerPx){
  float a = rough*rough;
  float kernel = min(2.0*0.15*dnPerPx*dnPerPx, 0.2);
  return sqrt(sqrt(clamp(a*a + kernel, 0.0, 1.0)));
}

#ifdef HDR
// Image-based lighting from the prefiltered studio. Specular comes only from
// the studio, whose key softbox sits where the key light is, so the key is
// never counted twice. Mip levels were built at roughness (level/max)^2, which
// puts more of them where the polished rims live; this reads them back the same way.
uniform samplerCube uEnv, uIrr; uniform sampler2D uDFG; uniform float uEnvMaxLod;
vec3 envSpec(vec3 r, float rough){ return textureLod(uEnv, r, sqrt(clamp(rough, 0.0, 1.0))*uEnvMaxLod).rgb; }
vec3 dfg(float nv, float rough){ return texture(uDFG, (vec2(nv, rough)*31.0 + 0.5)/32.0).rgb; }   // texel centres of the 32x32 table

vec3 shade(Surf s, vec3 n, float ao, float shadow){
  vec3 V = vec3(0,0,1);
  float nl = max(dot(n, gL), 0.0), nv = clamp(n.z, 1e-3, 1.0);
  vec3 r = normalize(reflect(-V, n) + gShift);   // the studio's key sits at uL; sliding the look-up by (uL - gL) puts its highlight where this pixel's own light is
  vec3 col;
  if(s.metal > 0.5){
    vec3 t = dfg(nv, s.rough);
    // F82-tint (Kutz 2021, after Hoffman 2019; OpenPBR's metal Fresnel):
    // Schlick minus mu(1-mu)^6 scaled so the curve passes through edge*Schlick
    // at mu = 1/7. Integrated against the lobe by the table's third channel.
    vec3 fs82 = s.f0 + (1.0 - s.f0)*pow(6.0/7.0, 5.0);
    vec3 spec = s.f0*t.x + t.y - fs82*(1.0 - s.edge)/0.0566528*t.z;
    // Energy lost to single scattering comes back (Filament's form; t.x + t.y
    // is the lobe's directional albedo for a perfect mirror), so rough and
    // satin metals stay bright instead of turning grey.
    spec *= 1.0 + s.f0*(1.0/max(t.x + t.y, 1e-3) - 1.0);
    col = envSpec(r, s.rough) * spec * ao * (0.40 + 0.60*min(gAtt, 1.0)) * gOcc;
    if(dot(uK2, vec3(1.0)) > 0.0){
      vec3 Hb = normalize(uL2d + V);
      float nlb = max(dot(n, uL2d), 0.0), nhb = max(dot(n, Hb), 0.0);
      vec3 Fb = s.f0 + (1.0 - s.f0)*pow(1.0 - max(dot(Hb, V), 0.0), 5.0);
      col += uK2*Fb*min(ggx(nhb, max(s.rough, 0.16)), 60.0)*nlb*0.012*shadow;
    }
  } else {
    // Matte light: the direct key, plus the studio's diffuse light. The studio
    // is built for reflections and is much darker than the level the matte
    // surfaces were tuned at, so it sets the direction and colour of the
    // ambient light while uAmb keeps its overall level.
    vec3 irr = textureLod(uIrr, n, 0.0).rgb / max(textureLod(uIrr, vec3(0,0,1), 0.0).rgb, vec3(1e-4));
    col = s.alb*(nl*shadow)*uKey*gAtt*(2.0/PI) + s.alb*uAmb*1.7*irr*ao + s.alb*max(dot(n, uL2d), 0.0)*shadow*uK2*(2.0/PI);
    if(s.coat > 0.0){
      vec3 ab = dfg(nv, 0.06); float sc = 0.04*ab.x + ab.y;
      col = col*(1.0 - sc*s.coat) + envSpec(r, 0.06)*sc*ao*s.coat*(0.40 + 0.60*min(gAtt, 1.0));
    }
    if(s.irid > 0.0){
      float ph = nv*2.6 + n.x*1.7 + n.y*1.3;
      vec3 film = 0.5 + 0.5*cos(6.283*(ph + vec3(0.0, 0.33, 0.67)));
      col = mix(col, col*(film*0.6 + 0.7), s.irid);
    }
  }
  col += vec3(2.5,2.4,2.2)*s.sparkle*nl*shadow*gAtt;
  return col;
}
#else
vec3 shade(Surf s, vec3 n, float ao, float shadow){
  vec3 V = vec3(0,0,1), H = normalize(gL + V);
  float nl = max(dot(n, gL), 0.0), nv = max(dot(n, V), 0.0) + 1e-3, nh = max(dot(n, H), 0.0);
  vec3 r = normalize(reflect(-V, n) + gShift);
  vec3 col;
  if(s.metal > 0.5){
    vec3 F = fresnel(s.f0, nv);
    col = uKey*F*ggx(nh, max(s.rough, 0.04))*nl*0.6*shadow + env(r, s.rough)*F*ao + s.f0*uAmb*0.15*ao;
  } else {
    col = s.alb*(nl*shadow)*uKey*gAtt*(2.0/PI) + s.alb*uAmb*ao*1.7;
    if(s.coat > 0.0){
      float Fc = 0.04 + 0.96*pow(1.0-nv, 5.0);
      col = col*(1.0 - Fc*s.coat) + (uKey*ggx(nh, 0.06)*nl*0.25*shadow + env(r, 0.08)*ao*Fc)*s.coat;
    }
    if(s.irid > 0.0){
      float ph = nv*2.6 + n.x*1.7 + n.y*1.3;
      vec3 film = 0.5 + 0.5*cos(6.283*(ph + vec3(0.0, 0.33, 0.67)));
      col = mix(col, col*(film*0.6 + 0.7), s.irid);
    }
  }
  col += vec3(2.5,2.4,2.2)*s.sparkle*nl*shadow*gAtt;
  return col;
}
#endif

// The rim as a moulded frame, swept along the outline: a round-over at the
// outer edge, a bead, a broad gently crowned field, a cove, a fine bead, and a
// drop to the screen. Heights are in rim widths, so the slope is the facet's
// tilt directly. From straight above, a facet tilted t shows the studio 2t
// from overhead: the field (under 6 degrees) shows the scrim and reads as
// gold, the beads and cove (about 34-37 degrees at their steepest) sweep
// through the key, the black flags and the cards, which is what draws the
// bright-dark-bright lines of a machined moulding. Each piece returns height,
// slope and curvature analytically (H = h, dh/du, d2h/du2), the curvature
// feeding the specular antialiasing.
void addRise(float u, float u0, float u1, float a, inout vec3 H){      // a(1-(1-x)^3)
  float w = u1 - u0, x = clamp((u - u0)/w, 0.0, 1.0), m = 1.0 - x;
  H.x += a*(1.0 - m*m*m);
  if(u > u0 && u < u1){ H.y += 3.0*a*m*m/w; H.z -= 6.0*a*m/(w*w); }
}
void addBead(float u, float c, float w, float a, inout vec3 H){        // a(1-x^2)^2, a < 0 is a cove
  float x = (u - c)/w; if(abs(x) >= 1.0) return;
  float q = 1.0 - x*x;
  H.x += a*q*q; H.y -= 4.0*a*x*q/w; H.z -= 4.0*a*(1.0 - 3.0*x*x)/(w*w);
}
void addDrop(float u, float u0, float u1, float a, inout vec3 H){      // -a x^2
  float w = u1 - u0, x = clamp((u - u0)/w, 0.0, 1.0);
  H.x -= a*x*x;
  if(u > u0){ H.y -= 2.0*a*x/w; if(u < u1) H.z -= 2.0*a/(w*w); }
}
// Art Deco picture-frame ornament, modelled as relief on the rim (it changes the
// surface normal, so it catches the same light as the metal: nothing is painted on).
// s runs along the frame, v is the distance in from its outer edge, both in CSS px.
// A row of rhombus studs sits on the bead; chevrons step across the field.
// Picture-frame ornament, a few large clear motifs along the straight runs of the frame. s runs along the
// frame, v across it (both px), rim is the frame's width. Five designs, chosen per tray; each returns a
// small height that becomes a slope in the shading.
float ornamentH(float s, float v, float rim, int style){
  float P = rim*1.45;
  float x = (fract(s/P + 0.5) - 0.5)*P;                 // along the frame, 0 at each motif's centre
  float vn = v/rim;
  // a row of pearls on the bead, shared by three of the designs
  vec2 pq = vec2((fract(s/(P*0.5) + 0.5) - 0.5)*2.0, (v - rim*0.22)/(rim*0.085));
  float pearl = smoothstep(1.0, 0.35, length(pq));
  // a fine bead-and-reel on the outer edge and a dash row by the screen, shared by every design: the frame
  // always has a second and third band under its main motif
  float tickR = smoothstep(rim*0.045, 0.0, abs(v - rim*0.82))*smoothstep(0.30, 0.16, abs(fract(s/(P*0.25) + 0.5) - 0.5)*2.0);
  float beadR = smoothstep(rim*0.035, 0.0, abs(v - rim*0.10))*0.6;
  float bands = tickR*0.22 + beadR*0.25;
  if(style == 5){                                        // egg and dart: plump ovals, a dart between each
    vec2 q = vec2(x/(P*0.30), (v - rim*0.52)/(rim*0.20));
    float egg = smoothstep(1.0, 0.2, length(q));
    float xd = abs(abs(x) - P*0.5), dy = abs(vn - 0.52);
    float dart = smoothstep(rim*0.05*(1.0 - dy/0.22), 0.0, xd)*step(dy, 0.22);
    return egg*0.55 + dart*0.55 + pearl*0.5 + bands;
  }
  if(style == 6){                                        // stepped: nested bars narrowing like a ziggurat
    float st = 0.0;
    for(int k = 0; k < 3; k++){
      float yk = rim*(0.36 + 0.11*float(k)), wk = P*(0.46 - 0.13*float(k));
      st += smoothstep(rim*0.032, 0.0, abs(v - yk))*smoothstep(wk + rim*0.03, wk - rim*0.03, abs(x));
    }
    return st*0.6 + pearl*0.45 + bands;
  }
  if(style == 7){                                        // guilloche: two waves crossing, over and under
    float ph = 6.2832*s/P, w = rim*0.13*sin(ph);
    float l1 = smoothstep(rim*0.042, 0.0, abs(v - rim*0.52 - w));
    float l2 = smoothstep(rim*0.042, 0.0, abs(v - rim*0.52 + w));
    return (l1 + l2)*0.5 + pearl*0.45 + bands;
  }
  if(style == 8){                                        // meander (Greek key, deco style): a square wave with its risers
    float sq = sign(sin(6.2832*s/P));
    float line = smoothstep(rim*0.04, 0.0, abs(v - rim*(0.52 + 0.12*sq)));
    float xt = min(abs(x), abs(abs(x) - P*0.5));
    float riser = smoothstep(rim*0.04, 0.0, xt)*step(abs(vn - 0.52), 0.12);
    return (line + riser)*0.55 + pearl*0.4 + bands;
  }
  if(style == 1){                                        // gadroon: a row of plump lobes down the field
    vec2 q = vec2(x/(P*0.47), (v - rim*0.52)/(rim*0.21));
    float lobe = smoothstep(1.0, 0.15, length(q));
    return pearl*0.8 + lobe*0.55 + bands;
  }
  if(style == 2){                                        // flutes: short ridges across the field, pearls on the bead
    float fx = (fract(s/(P*0.30) + 0.5) - 0.5)*P*0.30;
    float flute = smoothstep(rim*0.05, 0.0, abs(fx))*smoothstep(0.32, 0.40, vn)*smoothstep(0.72, 0.64, vn);
    return pearl*0.8 + flute*0.42 + bands;
  }
  if(style == 3){                                        // rope: a diagonal twist along the field
    float dg = fract(s/(P*0.62) + (vn - 0.52)*0.9);
    float rope = smoothstep(0.0, 0.5, dg)*smoothstep(1.0, 0.5, dg);
    float mask = smoothstep(0.32, 0.38, vn)*smoothstep(0.72, 0.66, vn);
    return rope*mask*0.62 + pearl*0.55 + bands;
  }
  if(style == 4){                                        // sunburst: a fan of rays rising from the bead, ringed by an arc
    vec2 w = vec2(x, v - rim*0.30);
    float r = length(w);
    float ang = atan(w.x, max(w.y, 1e-3));
    float rays = (0.5 + 0.5*cos(ang*11.0))*smoothstep(rim*0.55, rim*0.44, r)*smoothstep(rim*0.05, rim*0.16, r)*step(-rim*0.02, w.y);
    float ring = smoothstep(rim*0.035, 0.0, abs(r - rim*0.58))*step(-rim*0.02, w.y);
    return rays*0.62 + ring*0.70 + pearl*0.35 + bands;
  }
  // 0: deco chevrons with rhombus studs (the first design)
  vec2 q = vec2(x/(P*0.30), (v - rim*0.22)/(rim*0.12));
  float stud = smoothstep(1.0, 0.45, abs(q.x) + abs(q.y));
  float cv = v - rim*0.52, cl = abs(x)*0.42 - rim*0.06;
  float chev = smoothstep(rim*0.075, 0.0, abs(cv - cl)) * step(abs(x), P*0.5);
  float tick = smoothstep(rim*0.05, 0.0, abs(v - rim*0.80)) * smoothstep(0.32, 0.18, abs(x)/P);
  return stud*0.9 + chev*0.32 + tick*0.25 + bands;
}

vec3 rimProfile(float u, float detail){
  vec3 H = vec3(0.0);
  addRise(u, 0.0, 0.14, 0.10, H);                 // round-over from the wall, up to about 65 degrees
  addBead(u, 0.22, 0.08, 0.035, H);               // bead
  addBead(u, 0.46, 0.18, 0.012, H);               // the field's slight crown
  addBead(u, 0.68, 0.06, -0.028*detail, H);       // cove
  addBead(u, 0.81, 0.045, 0.022*detail, H);       // fine bead
  addDrop(u, 0.90, 1.0, 0.13, H);                 // down to the screen
  return H;
}

void main(){
  vec2 p = vP;
  vec2 g; float d = sdPoly(p, g) - uR;
  vec2 tdir = vec2(-g.y, g.x);
  // Edge coverage straight from the distance field, ramped over about 1.2
  // pixels: the width Red Blob Games measured as right (0.5 reads blocky, 2.0
  // blurry). This is ~256 levels of coverage per edge at the screen's own
  // resolution, where supersampling gave four.
  float aa = 1.2*max(fwidth(d), 1e-3);
  // CSS pixels per device pixel, taken here where every pixel runs it (screen
  // derivatives are only defined outside branches).
  float pxd = length(vec2(dFdx(d), dFdy(d)));
  // how sharply the outline turns here, per CSS px: ~0 on straight runs, ~1/r at a rounded corner
  float kc = length(vec2(length(dFdx(g)), length(dFdy(g))))/max(pxd, 1e-3);
  float lampD = length(uLamp.xy - p);
  bool lampOn = uLamp.z > 0.0;
  gL = lampOn ? normalize(vec3(uLamp.xy - p, uLamp.z)) : uL;
  gShift = uL - gL;
  gOcc = 1.0;
  gAtt = lampOn ? min(2.4*uLamp.z*uLamp.z/(uLamp.z*uLamp.z + lampD*lampD), 1.2) : 1.0;   // capped: things hung close to the lantern get brighter, but not brighter than everything else
  vec2 L2 = normalize(gL.xy + 1e-5);
  vec2 rel = p - uCenter;

  // Weight: the frame is a thick object. Its side wall shows on the side away
  // from the light and toward the viewer; it stands on the bench and casts a shadow.
  vec2 T = normalize(vec2(-L2.x*0.4, 1.0)) * uThick;
  float dw = min(min(sdPolyOnly(p - T*0.34), sdPolyOnly(p - T*0.67)), sdPolyOnly(p - T)) - uR;   // the extruded body
  dw = min(dw, d);

  Surf rimS = rimSurf(uRimMat, p, tdir);
  vec3 metalTint = rimS.metal > 0.5 ? rimS.f0 : rimS.alb;
  vec4 res = vec4(0);

  // ---- on the bench around the tray: shadow, light underneath, reflection, backlight ----
  if(dw > -aa){
    float shLen = lampOn ? clamp(0.55 + lampD/(uLamp.z*1.6), 0.55, 1.7) : 1.0;   // a point light throws longer shadows the farther the object is from it
    vec2 S = -L2*(uHeight*1.3*shLen) + T;
    float ds = sdPolyOnly(p - S) - uR;
    float blur = 7.0 + uHeight*1.4;
    float sh = (1.0 - smoothstep(-blur, blur*(lampOn ? 1.0 + 0.5*shLen : 1.2), ds))*(lampOn ? 0.74 : 0.62);
    float contact = exp(-max(dw, 0.0)/3.0)*0.55;
    float sh2 = 0.0;
    if(dot(uK2, vec3(1.0)) > 0.0){
      vec2 S2 = -normalize(uL2d.xy + 1e-5)*(uHeight*1.1);
      sh2 = (1.0 - smoothstep(-blur, blur*1.3, sdPolyOnly(p - S2) - uR))*0.34;
    }
    float a = clamp(max(max(sh, sh2), contact), 0.0, 0.85);
    float dwp = max(dw, 0.0);
    // subtle light underneath, in the tray's own colour
    vec3 add = uGlow.rgb * uGlow.a * exp(-dwp/10.0) * (lampOn ? 0.11*(0.06 + 0.94*smoothstep(-0.10, 0.85, g.y)) : 0.30);   // lantern mode: the tray is lit from beneath, so its light pools on the bench below its lower edges and barely shows over the top
    // a faint reflection of the frame on a polished bench, below the tray (toward the viewer)
    float facing = smoothstep(0.15, 0.85, g.y);
    add += metalTint * uGloss * exp(-dwp/6.0) * facing * (lampOn ? 0.14 : 0.35);   // the frame's mirror image in the polished bench: fainter under one real light, so pale metals don't throw a white band
    // selected: a bright backlight from behind the whole tray
    // light from behind the frame spills out around its edge: brightest right at the rim
    vec3 bl = mix(vec3(1.0, 0.90, 0.72), uGlow.rgb, 0.45);
    float dp = max(dw, 0.0);
#ifdef HDR
    // Real light, brighter than white and tight to the rim. The wide, soft part
    // of the glow is no longer painted on here: the bloom pass spreads it, the
    // way light actually spreads, and it spills onto neighbouring trays too.
    // Light from underneath: it escapes from beneath the tray, so it pools below and
    // along the lower sides and barely shows over the top edge. The distance is
    // measured from the outline shifted up, which slides the glow down and behind it.
    float dpu = max(sdPolyOnly(p - vec2(0.0, -uHeight*0.9)) - uR, 0.0);
    float under = 0.18 + 0.82*smoothstep(-0.35, 0.85, g.y);
    add += bl * uBack * under * (exp(-dpu/4.5)*1.5 + exp(-dpu/17.0)*0.38);
    add *= 1.0 - smoothstep(74.0, 92.0, dp);
#else
    add += bl * uBack * (exp(-dp/5.0)*1.1 + exp(-dp/16.0)*0.45 + exp(-dp/40.0)*0.10);
    add *= 1.0 - smoothstep(70.0, 88.0, dp);
#endif
    res = vec4(encode(add), a);
  }

  // ---- the side wall ----
  if(dw < aa && d > -aa){
    float wallT = clamp(d / max(dot(normalize(T), g)*uThick, 1.0), 0.0, 1.0);   // 0 at the rim, 1 at the bench
    Surf ms = rimSurf(uRimMat, p, tdir);
    applyWear(ms, p, (1.0 - wallT)*0.45, wallT);
    vec3 n = normalize(vec3(g*0.95, 0.30 - wallT*0.25));
    vec3 c = shade(ms, n, 0.85 - wallT*0.45, 1.0) * (0.85 - wallT*0.45);
    c += metalTint * smoothstep(0.22, 0.0, wallT) * 0.35;           // the lip where the wall meets the rim
    float cw = clamp(0.5 - dw/aa, 0.0, 1.0);
    res = vec4(encode(c), 1.0)*cw + res*(1.0 - cw);
  }

  // ---- rim and floor ----
  if(d < aa){
    float into = -d;
    vec3 inside;
    if(into < uRim){
      float u = clamp(into/uRim, 0.0, 1.0);
      // The fine bead and cove are about 0.09 of the rim across. Below about
      // three device pixels a pixel grid cannot hold them and they stipple, so
      // they fade into the field: small rims and native resolution get a
      // simpler moulding, oversampled large rims keep all of it.
      float detail = smoothstep(2.0, 3.5, 0.09*uRim/max(pxd, 1e-3));
      vec3 H = rimProfile(u, detail);
      Surf s = rimSurf(uRimMat, p + vec2(uSeed*37.0, uSeed*53.0), tdir);
      // Finish: each material answers the light its own way. envFloor is how dark the reflection gets where a facet
      // sees no light (polished metal mirrors a dark room almost black; satin metal scatters, so it never goes as dark);
      // glintK is how hard the lantern's own highlight bites; patina is how much darker, greener metal gathers in the recesses.
      float envFloor = 0.12, glintK = 1.0, patina = 0.0, brushed = 0.0;
      if(uRimMat == 0){ s.rough = 0.07; envFloor = 0.05; glintK = 1.0; }            // gold: polished, deep darks, bright glints
      else if(uRimMat == 1){ s.rough = 0.10; envFloor = 0.07; glintK = 0.9; }       // rose gold
      else if(uRimMat == 2){ s.rough = 0.18; envFloor = 0.11; glintK = 0.6; patina = 0.55; }   // brass: soft, tarnish in the coves
      else if(uRimMat == 3){ s.rough = 0.14; envFloor = 0.09; glintK = 0.8; patina = 0.30; }   // copper
      else if(uRimMat == 4){ s.rough = 0.045; envFloor = 0.03; glintK = 1.3; }      // silver: near mirror, the hardest contrast
      else if(uRimMat == 5){ s.rough = 0.32; envFloor = 0.20; glintK = 0.45; patina = 0.75; }  // bronze: satin, broad gradients, dark patina
      else if(uRimMat == 6){ s.rough = 0.12; envFloor = 0.09; glintK = 0.8; }       // champagne
      else if(uRimMat == 7){ s.rough = 0.22; envFloor = 0.12; glintK = 0.75; brushed = 1.0; }  // steel: brushed along the frame
      else { envFloor = 0.20; glintK = 1.6; }                                        // shell, opal: glossy coat over a soft body
      // Age: gilding rubs through on the bead and round-over, tarnish gathers in the cove and by the screen.
      if(uRimMat < 10) applyWear(s, p, clamp(exp(-pow((u - 0.22)/0.12, 2.0)) + 0.8*exp(-pow((u - 0.81)/0.07, 2.0)) + 0.6*smoothstep(0.14, 0.0, u), 0.0, 1.0),
                      clamp(exp(-pow((u - 0.68)/0.07, 2.0)) + 0.6*smoothstep(0.88, 0.98, u), 0.0, 1.0));
      // Machining: fine grooves running along the frame, in the normal (not
      // painted on). They fade out before they get finer than about two pixels,
      // so they never shimmer when a tray moves.
      float gfade = 1.0 - smoothstep(0.15, 0.3, 0.45*pxd);
      float groove = (vnoise(vec2(into*0.45, dot(p, tdir)*0.004), 17u) - 0.5)*0.05*gfade;
      float slope = H.y*1.75 + groove;
      // picture-frame ornament: on straight runs of a rim wide enough to hold it
      float ofade = smoothstep(11.0, 17.0, uRim/max(pxd, 1e-3))*(1.0 - smoothstep(0.006, 0.016, kc))*uOrnate;
      float along = dot(p, tdir), vin = into;
      vec2 oSlope = vec2(0.0);
      if(ofade > 0.0){
        float e = max(pxd*0.8, 0.35);
        float h0 = ornamentH(along, vin, uRim, uOrnStyle);
        oSlope = vec2(ornamentH(along + e, vin, uRim, uOrnStyle) - h0, ornamentH(along, vin + e, uRim, uOrnStyle) - h0)/e*ofade*1.1*(s.metal > 0.5 ? 1.0 : 2.4);
      }
      // corner jewels: where the outline turns, the bead swells and takes the tray's own glow colour
      float jewel = smoothstep(0.008, 0.02, kc)*exp(-pow((u - 0.30)/0.16, 2.0))*uOrnate;
      s.f0 = mix(s.f0, mix(s.f0, uGlow.rgb*1.1 + 0.15, 0.28), jewel*step(0.001, uGlow.a));
      s.rough = max(s.rough - jewel*0.06, 0.05);
      vec3 n = normalize(vec3(g*(slope - oSlope.y*0.9) + tdir*oSlope.x*0.9 + g*jewel*0.12*(0.5 - u), 1.0));
      // how fast the normal turns per device pixel: profile curvature times the
      // pixel's share of the rim, over (1 + slope^2) for the angle; plus the grooves
      float dn = abs(H.z)*(pxd/uRim)/(1.0 + slope*slope) + abs(groove)*0.9*pxd;
      s.rough = aaRough(s.rough, dn);
      // Weight: light cannot reach the bottom of a cove or the channel where the frame meets the screen,
      // so those stay dark whatever the light does; the outer round-over rolls into shadow at the very edge.
      float ao = mix(0.32, 1.0, smoothstep(-0.02, 0.11, H.x));
      ao *= mix(1.0, 0.30, smoothstep(0.84, 0.99, u))*mix(0.55, 1.0, smoothstep(0.0, 0.06, u));
      if(patina > 0.0 && s.metal > 0.5) s.f0 = mix(s.f0, s.f0*vec3(0.42, 0.46, 0.36), patina*(1.0 - ao)*1.3);
      if(lampOn){
        float lit1 = smoothstep(0.12, 0.70, dot(n, gL));
        float lit2 = smoothstep(0.12, 0.70, dot(n, uL2d))*clamp(max(uK2.r, max(uK2.g, uK2.b)), 0.0, 1.0);
        gOcc = mix(envFloor, 1.0, max(lit1, 0.85*lit2));
      }
      vec3 c = shade(s, n, ao, 1.0);
      if(lampOn){
        // The lantern's own highlight: a real specular glint that moves with the light. Sharp and hot on polished
        // metal, broad and soft on satin, streaked along the grain on brushed steel, a small white spark on a glossy coat.
        vec3 Vv = vec3(0.0, 0.0, 1.0), Hh = normalize(gL + Vv);
        float nh = max(dot(n, Hh), 0.0), nlg = max(dot(n, gL), 0.0);
        float gr = s.metal > 0.5 ? max(s.rough, 0.05) : 0.06;
        vec3 f0g = s.metal > 0.5 ? s.f0 : vec3(0.05);
        vec3 Fg = f0g + (1.0 - f0g)*pow(1.0 - max(dot(Hh, Vv), 0.0), 5.0);
        float D = min(ggx(nh, gr), 80.0);
        if(brushed > 0.0) D *= 0.45 + 1.1*vnoise(vec2(dot(p, tdir)*0.015, dot(p, vec2(-tdir.y, tdir.x))*1.4), 31u);
        c += uKey*gAtt*Fg*D*nlg*0.010*glintK*ao;
      }
      if(lampOn && s.metal < 0.5){
        c *= 0.50*(0.20 + 0.80*gOcc);   // pearly frames take the same shadow as the metal ones; the direct light is tuned for floors, so they start too bright
        if(uRimMat == 53) c += s.alb*0.05*(0.6 + 0.4*(1.0 - gOcc));   // opal: a little light seems to come from inside the stone
      }
      // Light diffusing through the middle of the moulding: a broad soft glow on the crown,
      // stronger on the faces that look toward the key, so the metal has body, not just edges.
      c += (s.metal > 0.5 ? s.f0 : s.alb*0.55)*uKey*0.09*exp(-pow((u - 0.46)/0.24, 2.0))*(0.40 + 0.60*clamp(dot(g, L2)*0.5 + 0.5, 0.0, 1.0))*(lampOn ? 0.25*gOcc*(0.5 + envFloor*2.5) : 1.0);
      if(lampOn) c += uGlow.rgb*uGlow.a*0.40*smoothstep(0.0, 0.9, g.y)*smoothstep(0.55, 0.0, u)*(0.25 + 0.75*gOcc);   // the tray's own light reaching the downward-facing bevels of its lower frame
      c *= 1.0 + uFocus*0.06 + uBack*0.18;
      // Limited tone ramp (the old-game look): brightness is gathered into a few steps with soft
      // edges, hue untouched, so bevels read by their light/dark structure. Nothing happens at uRamp = 0.
      if(uRamp > 0.0){
        float Lr = dot(c, vec3(0.2126, 0.7152, 0.0722));
        float xr = Lr/(1.0 + Lr)*uRampN;
        float br = floor(xr);
        float tq = (br + smoothstep(0.30, 0.70, xr - br))/uRampN;
        float Lq = min(tq, 0.985)/(1.0 - min(tq, 0.985));
        c = mix(c, c*(Lq/max(Lr, 1e-4)), uRamp);
      }
#ifdef HDR
      c += vec3(1.0, 0.95, 0.85) * uBack * smoothstep(0.25, 0.0, u) * (0.12 + 0.55*smoothstep(-0.35, 0.85, g.y));   // backlight catching the outer edge, above white so it blooms
#else
      c += vec3(1.0, 0.95, 0.85) * uBack * smoothstep(0.25, 0.0, u) * 0.35;
#endif
      inside = c;
    } else {
      float dd = into - uRim;
      if(uScreen > 0 && dd > uPad + 1.0){
        inside = vec3(0.012);                     // covered by the screen
      } else {
        Surf s = floorSurf(uFloorMat, p + vec2(uSeed*131.0, uSeed*71.0), rel, uint(uSeed) + 3u);
        vec3 n = normalize(vec3(-dFdx(s.h)*2.2, -dFdy(s.h)*2.2, 1.0));
        float ao = 1.0 - 0.6*exp(-dd/(uRim*0.8 + 4.0));
        float sideAway = clamp(dot(-g, -L2), 0.0, 1.0);
        float shadow = 1.0 - 0.45*exp(-dd/(uHeight*1.2 + 3.0))*sideAway;
        vec3 c = shade(s, n, ao, shadow);
        if(s.glass > 0.0){
          vec2 suv = gl_FragCoord.xy / uRes;
          vec3 behind = benchRead(textureLod(uBench, suv, 4.5).rgb);
          c = mix(c, behind*(s.tint*1.6 + 0.08) + c*0.45, s.glass);
          c += s.tint * exp(-dd/22.0) * clamp(dot(-g, L2), 0.0, 1.0) * 1.3;
        }
        float ext = max(max(uContent.z - uContent.x, uContent.w - uContent.y)*0.5 + 40.0, 60.0);
        c *= 0.80 + 0.34*clamp(0.5 + 0.5*dot(rel, -L2)/ext, 0.0, 1.0);
        if(uWear > 0.0) c *= 1.0 - uWear*(0.16*fbm(p*0.012, 4, 95u) + 0.26*exp(-dd/16.0)*fbm(p*0.07, 3, 96u));   // grime, heaviest where it meets the frame
        c += uGlow.rgb * uGlow.a * exp(-dd/10.0) * 0.18;
        if(uInlay > 0 && uScreen == 0){
          float li = 1.0 - smoothstep(0.9, 1.9, abs(dd - 7.0));
          Surf ms = rimSurf(uRimMat, p, tdir);
          c = mix(c, shade(ms, normalize(vec3(g*(dd < 7.0 ? 0.6 : -0.6), 1.0)), 1.0, 1.0), li*0.85);
        }
        if(uEmissive.a > 0.0){
          float core = exp(-dot(rel, rel)/(uEmissive.a*900.0 + 1.0));
          c = c*0.55 + uEmissive.rgb*(core*2.2 + 0.35);
        }
        // the screen's edge sits in the frame: a soft dark bevel against the rim
        if(uScreen > 0) c *= 0.35;
        inside = c;
      }
    }
    float cov = clamp(0.5 - d/aa, 0.0, 1.0);
    res = vec4(encode(inside), 1.0)*cov + res*(1.0 - cov);
  }
  o = res;
}`;

  function compile(gl, type, src){
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if(!gl.getShaderParameter(s, gl.COMPILE_STATUS)){
      const log = gl.getShaderInfoLog(s); gl.deleteShader(s);
      throw new Error('Foresight GL shader: ' + log);
    }
    return s;
  }
  // #version has to stay the first line, so defines go in just after it.
  function withDefs(src, defs){
    if(!defs) return src;
    const i = src.indexOf('\n');
    return src.slice(0, i+1) + defs + src.slice(i+1);
  }
  function program(gl, vs, fs, defs){
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, withDefs(vs, defs))); gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, withDefs(fs, defs)));
    gl.bindAttribLocation(p, 0, 'aPos'); gl.linkProgram(p);
    if(!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('Foresight GL link: ' + gl.getProgramInfoLog(p));
    const u = {}; const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for(let i=0;i<n;i++){ const info = gl.getActiveUniform(p, i); const name = info.name.replace(/\[0\]$/, ''); u[name] = gl.getUniformLocation(p, info.name); }
    return {p, u};
  }

  // Float render targets are what make linear compositing, values above 1.0 and
  // bloom possible. The extension string alone is not proof, so try the formats
  // and keep the first that gives a complete framebuffer. Cheapest first:
  // R11F_G11F_B10F carries HDR at the same 4 bytes per pixel as RGBA8, and the
  // bench underneath is opaque so no alpha channel is needed. Blending into
  // 16-bit and 11-bit float targets is covered by EXT_color_buffer_float;
  // EXT_float_blend is only needed for 32-bit float, which this never uses.
  function pickHDRFormat(gl){
    if(!gl.getExtension('EXT_color_buffer_float')) return 0;
    for(const f of [gl.R11F_G11F_B10F, gl.RGBA16F]){
      const t = gl.createTexture(), fb = gl.createFramebuffer();
      let ok = false;
      try {
        gl.bindTexture(gl.TEXTURE_2D, t);
        gl.texStorage2D(gl.TEXTURE_2D, 1, f, 4, 4);
        gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
        ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE && gl.getError() === gl.NO_ERROR;
      } catch(e){ ok = false; }
      gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.deleteFramebuffer(fb); gl.deleteTexture(t);
      if(ok) return f;
    }
    return 0;
  }

  function kelvin(K){
    const t = Math.max(1000, Math.min(40000, K))/100; let r, g, b;
    if(t <= 66){ r = 1; g = Math.max(0, Math.min(1, (99.4708025861*Math.log(t) - 161.1195681661)/255)); }
    else { r = Math.max(0, Math.min(1, 329.698727446*Math.pow(t-60, -0.1332047592)/255)); g = Math.max(0, Math.min(1, 288.1221695283*Math.pow(t-60, -0.0755148492)/255)); }
    b = t >= 66 ? 1 : t <= 19 ? 0 : Math.max(0, Math.min(1, (138.5177312231*Math.log(t-10) - 305.0447927307)/255));
    return [r*r, g*g, b*b];
  }

  class ForesightGL {
    constructor(canvas){
      this.canvas = canvas;
      const gl = canvas.getContext('webgl2', {antialias:false, alpha:false, depth:false, stencil:false,
        premultipliedAlpha:true, powerPreference:'high-performance'});
      if(!gl) throw new Error('WebGL2 is not available in this browser');
      this.gl = gl;
      this.hdr = pickHDRFormat(gl);
      const defs = this.hdr ? '#define HDR 1\n' : '';
      this.bench = program(gl, QUAD_VS, BENCH_FS, defs);
      this.blit = program(gl, FULL_VS, BLIT_FS);
      this.tray = program(gl, QUAD_VS, TRAY_FS, defs);
      if(this.hdr){
        this.down = program(gl, FULL_VS, DOWN_FS);
        this.up = program(gl, FULL_VS, UP_FS);
        this.final = program(gl, FULL_VS, FINAL_FS, defs);
        this.envP = program(gl, FULL_VS, ENV_FS, defs);
        this.irrP = program(gl, FULL_VS, IRR_FS, defs);
        this.preP = program(gl, FULL_VS, PREFILTER_FS, defs);
        this.dfgP = program(gl, FULL_VS, DFG_FS, defs);
        this.coatP = program(gl, QUAD_VS, BENCHCOAT_FS, defs);
      }
      const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0,0, 1,0, 0,1, 1,1]), gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      this.theme = 'tigereye'; this.gloss = 0.70; this.wear = 0; this.saturation = 1; this.contrast = 1; this.aged = 0; this.paint = 0; this.lamp = false; this.lampHeight = 0.30; this.L2 = [0.0, 0.0, 1.0]; this.K2 = [0, 0, 0]; this.ramp = 0; this.rampSteps = 6; this.lightPos = null; this.quality = 'full';
      // Exposure sets where mid tones land before the tone curve; bloom is mixed
      // in at a low level with no threshold, so only genuinely bright pixels glow.
      this.exposure = 1.6; this.bloomMix = 0.045;
      this.envDirty = true;
      this.setLight({az:135, el:48, kelvin:4300, intensity:1, fill:0.35});
      this.benchDirty = true;
      if(this.hdr) this.buildDFG();
      this.qbuf = new Float32Array(MAXV*2);
      this.mips = [];
    }
    // gloss: how much the bench mirrors what stands on it (varnished wood a little, polished stone more)
    // Photographed stone for the bench, loaded once; the bench redraws when it arrives.
    loadStone(url){
      const img = new Image(); this.stoneReady = false;
      img.onload = () => { const gl = this.gl; const t = gl.createTexture();
        gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D, t);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.generateMipmap(gl.TEXTURE_2D);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
        gl.activeTexture(gl.TEXTURE0); this.stoneTex = t; this.stoneReady = true; this.benchDirty = true; };
      img.src = url;
    }
    // A second directional light from another side: cool and weaker than the lantern, low and raking, so it rims the
    // frames the lantern leaves dark instead of filling them evenly. intensity 0 turns it off.
    setLight2({az=-35, el=24, intensity=0.6, color=[0.60, 0.76, 1.0]}={}){
      const a = az*Math.PI/180, e = el*Math.PI/180;
      const v = [Math.cos(a)*Math.cos(e), -Math.sin(a)*Math.cos(e), Math.sin(e)], l = Math.hypot(...v);
      this.L2 = v.map(x => x/l); this.K2 = color.map(x => x*2.4*intensity);
    }
    setTheme(name){ if(THEME[name] === undefined) throw new Error('unknown theme '+name); this.theme = name; this.gloss = {walnut:0.35, pearl:0.75, indigo:0.65, tigereye:0.70, nero:0.85}[name]; this.benchDirty = true; this.envDirty = true; }
    // Lighting Explorer values: key azimuth/elevation (degrees), Kelvin, intensity, fill level.
    setLight({az=135, el=48, kelvin:K=4300, intensity=1, fill=0.35}={}){
      const a = az*Math.PI/180, e = el*Math.PI/180;
      this.L = [Math.cos(a)*Math.cos(e), -Math.sin(a)*Math.cos(e), Math.sin(e)];
      const l = Math.hypot(...this.L); this.L = this.L.map(v=>v/l);
      const kc = kelvin(K), lum = Math.max(0.05, kc[0]*0.2126 + kc[1]*0.7152 + kc[2]*0.0722);
      this.key = kc.map(v => v*2.85*intensity/lum);
      this.amb = 0.10 + 0.34*fill;
      this.fill = fill/0.35;              // 1 at the default fill: scales the studio's scrim, kicker and bounce
      this.benchDirty = true; this.envDirty = true;
    }
    // A full-viewport pass into one face (or the 2D table) of a texture.
    passInto(tex, target, level, w, h){
      const gl = this.gl;
      if(!this.envFbo) this.envFbo = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.envFbo);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, target, tex, level);
      gl.viewport(0, 0, w, h);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    // The 32x32 DFG table never changes, so it is built once.
    buildDFG(){
      const gl = this.gl, N = 32;
      this.dfgTex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.dfgTex);
      gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA16F, N, N);
      for(const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      gl.disable(gl.BLEND);
      const P = this.dfgP; gl.useProgram(P.p); gl.uniform2f(P.u.uSize, N, N);
      this.passInto(this.dfgTex, gl.TEXTURE_2D, 0, N, N);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }
    // The studio: drawn into a 256 cube with a full mip chain (the prefilter's
    // source), then blurred into ENV_LEVELS levels of roughness, plus a 16 cube
    // of diffuse light. Runs only when the light, fill or bench changes.
    buildEnv(){
      const gl = this.gl, S = 256, LV = ENV_LEVELS, IR = 16;
      const cube = (size, levels) => {
        const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_CUBE_MAP, t);
        // 16-bit float, not the scene's 11/11/10 format: the reflected scrim is a
        // long smooth gradient, and 10-bit-float blue (5-bit mantissa) bands in it.
        gl.texStorage2D(gl.TEXTURE_CUBE_MAP, levels, gl.RGBA16F, size, size);
        gl.texParameteri(gl.TEXTURE_CUBE_MAP, gl.TEXTURE_MIN_FILTER, levels > 1 ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_CUBE_MAP, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        for(const w of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) gl.texParameteri(gl.TEXTURE_CUBE_MAP, w, gl.CLAMP_TO_EDGE);
        return t;
      };
      if(!this.envSrc){
        this.envSrc = cube(S, Math.log2(S) + 1);
        this.envTex = cube(S, LV);
        this.irrTex = cube(IR, 1);
      }
      gl.disable(gl.BLEND);
      const face = f => gl.TEXTURE_CUBE_MAP_POSITIVE_X + f;
      const studioUniforms = (P, keyOn) => {
        gl.useProgram(P.p);
        gl.uniform3fv(P.u.uL, this.L); gl.uniform3fv(P.u.uKey, this.key);
        gl.uniform1f(P.u.uFill, this.fill); gl.uniform1f(P.u.uKeyOn, keyOn);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.benchTex); gl.uniform1i(P.u.uBench, 0);
      };
      // the sharp studio, into the source and into level 0 (a mirror needs no blur)
      studioUniforms(this.envP, 1); gl.uniform1f(this.envP.u.uSize, S);
      for(let f=0; f<6; f++){
        gl.uniform1i(this.envP.u.uFace, f);
        this.passInto(this.envSrc, face(f), 0, S, S);
        this.passInto(this.envTex, face(f), 0, S, S);
      }
      gl.bindTexture(gl.TEXTURE_CUBE_MAP, this.envSrc); gl.generateMipmap(gl.TEXTURE_CUBE_MAP);
      // each rougher level, by GGX importance sampling of the source
      const P = this.preP; gl.useProgram(P.p);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_CUBE_MAP, this.envSrc); gl.uniform1i(P.u.uSrc, 0);
      gl.uniform1f(P.u.uSrcSize, S);
      for(let l=1; l<LV; l++){
        const size = S >> l, t = l/(LV - 1);
        gl.uniform1f(P.u.uSize, size); gl.uniform1f(P.u.uRough, t*t);
        for(let f=0; f<6; f++){ gl.uniform1i(P.u.uFace, f); this.passInto(this.envTex, face(f), l, size, size); }
      }
      // diffuse light without the key
      studioUniforms(this.irrP, 0); gl.uniform1f(this.irrP.u.uSize, IR);
      for(let f=0; f<6; f++){ gl.uniform1i(this.irrP.u.uFace, f); this.passInto(this.irrTex, face(f), 0, IR, IR); }
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.bindTexture(gl.TEXTURE_CUBE_MAP, null);
      this.envDirty = false;
    }
    // The silhouette is now antialiased analytically, but the rim's thin bead
    // highlights still are not: their sharpness comes from the shading, and
    // nothing filters it yet. Measured at native resolution they visibly
    // stair-step, so 'full' keeps oversampling until geometric specular
    // antialiasing lands; then 'native' becomes the default and costs a quarter
    // of the pixels. 'fast' drops to 0.75x mid-drag.
    resize(){
      const base = window.devicePixelRatio || 1, cap = Math.min(base, 2);
      const dpr = this.quality === 'native' ? cap
        : this.quality === 'fast' ? Math.min(Math.max(base, 2), 3)*0.75
        : Math.min(Math.max(base, 2), 3);
      const w = Math.round(this.canvas.clientWidth*dpr), h = Math.round(this.canvas.clientHeight*dpr);
      if(this.canvas.width !== w || this.canvas.height !== h){ this.canvas.width = w; this.canvas.height = h; this.benchDirty = true; }
      this.dpr = dpr; this.view = [this.canvas.clientWidth, this.canvas.clientHeight];
    }
    renderBench(){
      const gl = this.gl, W = this.canvas.width, H = this.canvas.height;
      if(!this.benchTex || this.benchW !== W || this.benchH !== H){
        if(this.benchTex) gl.deleteTexture(this.benchTex);
        if(this.fbo) gl.deleteFramebuffer(this.fbo);
        this.benchTex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.benchTex);
        gl.texStorage2D(gl.TEXTURE_2D, Math.floor(Math.log2(Math.max(W,H)))+1, this.hdr || gl.RGBA8, W, H);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        this.fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.benchTex, 0);
        this.benchW = W; this.benchH = H;
      }
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo); gl.viewport(0, 0, W, H); gl.disable(gl.BLEND);
      const P = this.bench; gl.useProgram(P.p);
      gl.uniform4f(P.u.uRect, 0, 0, this.view[0], this.view[1]); gl.uniform2f(P.u.uView, this.view[0], this.view[1]);
      gl.uniform1i(P.u.uTheme, THEME[this.theme]); gl.uniform3fv(P.u.uL, this.L); gl.uniform3fv(P.u.uKey, this.key);
      { const lp = this.lightPos || [this.view[0]*0.28, this.view[1]*0.18]; gl.uniform2f(P.u.uPool, lp[0], lp[1]); gl.uniform1f(P.u.uPoolK, this.lightPos ? 1 : 0); gl.uniform1f(P.u.uLampZ, this.lamp && this.lightPos ? this.lampHeight*this.view[0] : 0); gl.uniform3fv(P.u.uL2d, this.L2); gl.uniform3fv(P.u.uK2, this.K2); }
      gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D, this.stoneTex || null); gl.uniform1i(P.u.uStone, 5); gl.uniform1f(P.u.uStoneOn, this.stoneTex ? 1 : 0); gl.activeTexture(gl.TEXTURE0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.bindTexture(gl.TEXTURE_2D, this.benchTex); gl.generateMipmap(gl.TEXTURE_2D);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      this.benchDirty = false;
    }
    // The finish on the bench, blended over it in place, then the mips rebuilt
    // (frosted glass and the studio both read the bench's mips).
    coatBench(){
      const gl = this.gl, W = this.canvas.width, H = this.canvas.height;
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo); gl.viewport(0, 0, W, H);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const P = this.coatP; gl.useProgram(P.p);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_CUBE_MAP, this.envTex); gl.uniform1i(P.u.uEnv, 1);
      gl.uniform1f(P.u.uEnvMaxLod, ENV_LEVELS - 1);
      gl.uniform4f(P.u.uRect, 0, 0, this.view[0], this.view[1]); gl.uniform2f(P.u.uView, this.view[0], this.view[1]);
      gl.uniform1i(P.u.uTheme, THEME[this.theme]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.disable(gl.BLEND);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.benchTex); gl.generateMipmap(gl.TEXTURE_2D);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }
    // The scene buffer everything is composited into, and the half-size chain
    // the bloom is built in. Rebuilt only when the canvas changes size.
    ensureTargets(){
      const gl = this.gl, W = this.canvas.width, H = this.canvas.height;
      if(this.scene && this.targetW === W && this.targetH === H) return;
      this.freeTargets();
      const mk = (w, h) => {
        const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
        gl.texStorage2D(gl.TEXTURE_2D, 1, this.hdr, w, h);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        const f = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, f);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
        return {t, f, w, h};
      };
      this.scene = mk(W, H);
      this.mips = [];
      let w = W>>1, h = H>>1;
      for(let i=0; i<6 && w >= 8 && h >= 8; i++){ this.mips.push(mk(w, h)); w >>= 1; h >>= 1; }
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      this.targetW = W; this.targetH = H;
    }
    freeTargets(){
      const gl = this.gl;
      for(const m of [this.scene, ...(this.mips||[])]) if(m){ gl.deleteTexture(m.t); gl.deleteFramebuffer(m.f); }
      this.scene = null; this.mips = [];
    }
    // Jimenez's bloom: down the pyramid with a firefly-suppressing first step,
    // then back up with a tent filter, each level averaged with the one above so
    // the result stays an energy-preserving blur of the scene rather than a
    // stack of ever-brighter copies.
    renderBloom(){
      const gl = this.gl, mips = this.mips;
      if(!mips.length) return null;
      gl.disable(gl.BLEND);
      const D = this.down; gl.useProgram(D.p); gl.uniform1i(D.u.uTex, 0); gl.activeTexture(gl.TEXTURE0);
      let src = this.scene;
      for(let i=0;i<mips.length;i++){
        const dst = mips[i];
        gl.bindFramebuffer(gl.FRAMEBUFFER, dst.f); gl.viewport(0, 0, dst.w, dst.h);
        gl.bindTexture(gl.TEXTURE_2D, src.t);
        gl.uniform2f(D.u.uTexel, 1/src.w, 1/src.h); gl.uniform2f(D.u.uRes, dst.w, dst.h);
        gl.uniform1i(D.u.uFirst, i === 0 ? 1 : 0);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        src = dst;
      }
      gl.enable(gl.BLEND); gl.blendFunc(gl.CONSTANT_ALPHA, gl.ONE_MINUS_CONSTANT_ALPHA); gl.blendColor(0, 0, 0, 0.5);
      const U = this.up; gl.useProgram(U.p); gl.uniform1i(U.u.uTex, 0); gl.uniform1f(U.u.uRadius, 1.0);
      for(let i=mips.length-1;i>0;i--){
        const s = mips[i], dst = mips[i-1];
        gl.bindFramebuffer(gl.FRAMEBUFFER, dst.f); gl.viewport(0, 0, dst.w, dst.h);
        gl.bindTexture(gl.TEXTURE_2D, s.t);
        gl.uniform2f(U.u.uTexel, 1/s.w, 1/s.h); gl.uniform2f(U.u.uRes, dst.w, dst.h);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      }
      gl.disable(gl.BLEND);
      return mips[0];
    }
    draw(items){
      this.resize();
      // Order matters: the bench first, then the studio (its floor bounce reads the
      // bench's average colour), then the bench's clear coat (which reflects the studio).
      if(this.benchDirty){
        this.renderBench();
        if(this.hdr){ if(this.envDirty) this.buildEnv(); this.coatBench(); }
      } else if(this.hdr && this.envDirty) this.buildEnv();
      const gl = this.gl, W = this.canvas.width, H = this.canvas.height;
      if(this.hdr) this.ensureTargets();
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.hdr ? this.scene.f : null);
      gl.viewport(0, 0, W, H);
      // bench
      gl.disable(gl.BLEND);
      gl.useProgram(this.blit.p); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.benchTex);
      gl.uniform1i(this.blit.u.uTex, 0); gl.uniform2f(this.blit.u.uRes, W, H);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      // trays and the rest, in order
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const P = this.tray; gl.useProgram(P.p);
      gl.uniform1i(P.u.uBench, 0); gl.uniform2f(P.u.uRes, W, H); gl.uniform2f(P.u.uView, this.view[0], this.view[1]);
      gl.uniform3fv(P.u.uL, this.L); gl.uniform3fv(P.u.uKey, this.key); gl.uniform1f(P.u.uAmb, this.amb); gl.uniform3fv(P.u.uL2d, this.L2); gl.uniform3fv(P.u.uK2, this.K2); { const lp = this.lamp && this.lightPos; gl.uniform3f(P.u.uLamp, lp ? lp[0] : 0, lp ? lp[1] : 0, lp ? this.lampHeight*this.view[0] : 0); }
      if(this.hdr){
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_CUBE_MAP, this.envTex); gl.uniform1i(P.u.uEnv, 1);
        gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_CUBE_MAP, this.irrTex); gl.uniform1i(P.u.uIrr, 2);
        gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D, this.dfgTex); gl.uniform1i(P.u.uDFG, 3);
        gl.uniform1f(P.u.uEnvMaxLod, ENV_LEVELS - 1);
        gl.activeTexture(gl.TEXTURE0);
      }
      for(const it of items){
        if(!it.q || it.q.length < 3) continue;
        const n = Math.min(MAXV, it.q.length);
        const qb = this.qbuf; qb.fill(0);
        let x0=Infinity, y0=Infinity, x1=-Infinity, y1=-Infinity;
        for(let i=0;i<n;i++){ const [x,y] = it.q[i]; qb[2*i]=x; qb[2*i+1]=y; x0=Math.min(x0,x); y0=Math.min(y0,y); x1=Math.max(x1,x); y1=Math.max(y1,y); }
        const m = it.r + 90 + (it.height||10)*2 + (it.thick ?? 10);
        gl.uniform4f(P.u.uRect, x0-m, y0-m, x1+m, y1+m);
        gl.uniform2fv(P.u.uQ, qb); gl.uniform1i(P.u.uN, n);
        gl.uniform1f(P.u.uR, it.r); gl.uniform1f(P.u.uRim, it.rim); gl.uniform1f(P.u.uPad, it.pad||5); gl.uniform1f(P.u.uHeight, it.height||10);
        gl.uniform1i(P.u.uRimMat, it.rimMat ?? MAT.GOLD); gl.uniform1i(P.u.uFloorMat, it.floorMat ?? MAT.MARBLE_WHITE);
        gl.uniform1i(P.u.uInlay, it.inlay ? 1 : 0); gl.uniform1f(P.u.uSeed, it.seed||0); gl.uniform1f(P.u.uFocus, it.focus||0);
        gl.uniform1f(P.u.uThick, it.thick ?? 10); gl.uniform1f(P.u.uBack, it.backlight || 0); gl.uniform1f(P.u.uGloss, this.gloss); gl.uniform1f(P.u.uWear, it.wear ?? this.wear); gl.uniform1f(P.u.uOrnate, it.ornate ? 1 : 0); gl.uniform1i(P.u.uOrnStyle, it.ornStyle | 0); gl.uniform1f(P.u.uRamp, it.ramp ?? this.ramp); gl.uniform1f(P.u.uRampN, Math.max(2, this.rampSteps));
        gl.uniform1i(P.u.uScreen, it.screen ? 1 : 0);
        gl.uniform4fv(P.u.uGlow, it.glow || [0,0,0,0]); gl.uniform4fv(P.u.uEmissive, it.emissive || [0,0,0,0]);
        gl.uniform4fv(P.u.uContent, it.content || [0,0,0,0]);
        const c = it.center || [(x0+x1)/2, (y0+y1)/2]; gl.uniform2f(P.u.uCenter, c[0], c[1]);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      }
      if(!this.hdr) return;
      // One tone map, at the end, over the finished linear image.
      const bloom = this.renderBloom();
      gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H); gl.disable(gl.BLEND);
      const F = this.final; gl.useProgram(F.p);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.scene.t); gl.uniform1i(F.u.uScene, 0);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, (bloom || this.scene).t); gl.uniform1i(F.u.uBloom, 1);
      gl.uniform2f(F.u.uRes, W, H);
      gl.uniform1f(F.u.uExposure, this.exposure); gl.uniform1f(F.u.uSat, this.saturation); gl.uniform1f(F.u.uContrast, this.contrast); gl.uniform1f(F.u.uAged, this.aged); gl.uniform1f(F.u.uPaint, this.paint);
      gl.uniform1f(F.u.uBloomMix, bloom ? this.bloomMix : 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.activeTexture(gl.TEXTURE0);
    }
  }
  ForesightGL.MAT = MAT; ForesightGL.THEMES = Object.keys(THEME);
  root.ForesightGL = ForesightGL;
})(window);
