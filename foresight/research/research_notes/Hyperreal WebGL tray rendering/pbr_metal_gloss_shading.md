# PBR Metal and Gloss Shading for Hyper-Real WebGL2 Trays (Foresight Counter)

Where this information comes from (read this before using any number below). Every WebFetch permission request in this session timed out because nobody was there to approve it, so I could not open the body of any page. I ran web searches to confirm that the primary documents exist at the URLs given. Sources tagged [S] were confirmed that way, by matching title and URL in search results. Sources tagged [M] are canonical URLs I know from before and did not re-confirm. I wrote all formulas, constants and code from my prior knowledge of these primary documents and did not re-read them this session. They are standard, widely reproduced material, but anything tagged [verify] should be checked against the source before it ships. I made up no numbers. Where I wasn't sure, I either hedged or put the point under Gaps.

Conventions used below: α = GGX roughness = perceptualRoughness² (Burley/Filament remap); μ = cosθ; NoV = dot(N,V), and so on. "ALU" is a rough count of scalar instructions, my own estimate unless a source is cited.

---

## 1. Image-based lighting: split-sum, prefiltered radiance, SH irradiance, DFG LUT vs analytic fit, building and prefiltering a studio environment in WebGL2, CC0 HDRIs

### Takeaway
Split-sum IBL is still the real-time standard in 2026. UE, Filament and three.js all use it. Per pixel it costs one trilinear `textureLod` into a GGX-prefiltered cubemap mip chain, one DFG term (a 2–3 channel LUT or Karis's ~10-ALU analytic fit) and a 9-coefficient SH polynomial for diffuse. All three pieces can be generated on the GPU at startup from the existing procedural "studio room" function. That means a fully hyper-real IBL path needs zero downloaded bytes and about 1 MB of VRAM. An HDRI is optional.

### Cited Findings
Baseline lobe (reference, current best practice):
- Filament's standard specular is GGX D × height-correlated Smith V × Schlick F, with α = perceptualRoughness². Reference GLSL (Filament) [verify]:
  ```glsl
  float D_GGX(float NoH, float a) { float a2=a*a; float f=(NoH*a2-NoH)*NoH+1.0; return a2/(PI*f*f); }
  float V_SmithGGXCorrelated(float NoV, float NoL, float a) {
      float a2=a*a;
      float GGXV = NoL*sqrt(NoV*NoV*(1.0-a2)+a2);
      float GGXL = NoV*sqrt(NoL*NoL*(1.0-a2)+a2);
      return 0.5/(GGXV+GGXL); }
  // fast approximation (Hammon 2017), as listed by Filament:
  float V_SmithGGXCorrelated_Fast(float NoV,float NoL,float a){ return 0.5/mix(2.0*NoL*NoV, NoL+NoV, a); }
  vec3 F_Schlick(vec3 f0, float f90, float VoH){ return f0+(vec3(f90)-f0)*pow(1.0-VoH,5.0); }
  ```
  — [Filament, "Physically Based Rendering in Filament"](https://google.github.io/filament/Filament.md.html) [S]
- Filament clamps the minimum perceptual roughness (0.045 at highp, 0.089 at mediump) to avoid fp16 overflow and specular singularities on mirror surfaces [verify] — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]

Split-sum (Karis 2013):
- The specular IBL integral is split into two Monte-Carlo sums. (1/N)Σ L_i(l_k) · (1/N)Σ f(l_k,v)cosθ_lk / p(l_k,v) becomes (a) a prefiltered radiance term, stored as cubemap mips indexed by roughness, and (b) an "environment BRDF" term that depends only on (NoV, roughness) and expands to F0·A + B, stored in a 2-channel (R16G16) 2D LUT — [Karis 2013, "Real Shading in Unreal Engine 4" (SIGGRAPH PBS course notes)](https://cgvr.informatik.uni-bremen.de/teaching/cg_literatur/Brian%20Karis%20-%20Real%20Shading%20in%20Unreal%20Engine%204,%202013%20Siggraph%20Course.pdf) [S]; canonical copy [selfshadow s2013 notes](https://blog.selfshadow.com/publications/s2013-shading-course/karis/s2013_pbs_epic_notes_v2.pdf) [M]
- The prefilter assumes n = v = r, i.e. an isotropic lobe. This loses the long stretched reflections seen at grazing angles. Karis weights prefilter samples by NoL, which he found gave better results — [Karis 2013](https://cgvr.informatik.uni-bremen.de/teaching/cg_literatur/Brian%20Karis%20-%20Real%20Shading%20in%20Unreal%20Engine%204,%202013%20Siggraph%20Course.pdf) [S]
- Karis's analytic env-BRDF approximation for mobile replaces the LUT with about 10 ALU. He describes it as derived from Lazarov's Black Ops II approach:
  ```glsl
  vec3 EnvBRDFApprox(vec3 specColor, float roughness, float NoV) {
      const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
      const vec4 c1 = vec4( 1.0,  0.0425,  1.040, -0.040);
      vec4 r = roughness * c0 + c1;
      float a004 = min(r.x*r.x, exp2(-9.28*NoV)) * r.x + r.y;
      vec2 AB = vec2(-1.04, 1.04) * a004 + r.zw;   // AB.x = scale (A), AB.y = bias (B)
      return specColor * AB.x + AB.y; }
  ```
  Here "roughness" means UE's perceptual roughness. — [Karis 2014, "Physically Based Shading on Mobile"](https://www.unrealengine.com/en-US/blog/physically-based-shading-on-mobile) [S]
- Filament stores its DFG LUT so that specular = mix(dfg.xxx, dfg.yyy, f0). dfg.x is the Fresnel-weighted term (∫ V·D·Fc…, with Fc = (1−v·h)^5) and dfg.y is the sum DFG1+DFG2, which equals the single-scatter directional albedo with F = 1. dfg.y is reused for multiscatter compensation (Section 2). A third channel holds the cloth/sheen "DG" term. The LUT is RGB16F, about 128×128 [verify size]. — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- Roughness to mip LOD: Filament uses `lod = iblRoughnessOneLevel * perceptualRoughness * (2.0 - perceptualRoughness)`, a quadratic fit to a log2 mapping tuned for a 256² cubemap with 5 used levels [verify]. UE4 uses a log mapping (`mip = NumMips − 1 − (1 − 1.2·log2(roughness))`) [verify]. — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]; [Karis 2013](https://blog.selfshadow.com/publications/s2013-shading-course/karis/s2013_pbs_epic_notes_v2.pdf) [M]
- Filtered importance sampling makes prefiltering cheap. Each GGX sample reads a lower-resolution mip of the source chosen from the sample's pdf: `lod = 0.5*log2(Ωs/Ωp)`, where Ωs = 1/(N·pdf) and Ωp = 4π/(6·w²) for face width w. This brings the sample count from thousands down to tens with no fireflies — [Colbert & Křivánek, GPU Gems 3 ch. 20, "GPU-Based Importance Sampling"](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-20-gpu-based-importance-sampling) [M]; Filament's cmgen uses the same idea — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- Diffuse irradiance with 9 SH coefficients (3 bands), pre-convolved with the clamped cosine, is what Filament ships — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]. The closed-form evaluation comes from Ramamoorthi & Hanrahan 2001: E(n) = c1·L22(x²−y²) + c3·L20·z² + c4·L00 − c5·L20 + 2c1(L2−2·xy + L21·xz + L2−1·yz) + 2c2(L11·x + L1−1·y + L10·z), with c1=0.429043, c2=0.511664, c3=0.743125, c4=0.886227, c5=0.247708. That is about 20 MADs per pixel — [Ramamoorthi & Hanrahan 2001, "An Efficient Representation for Irradiance Environment Maps"](https://graphics.stanford.edu/papers/envmap/) [M]
- Horizon specular occlusion stops reflection vectors that point below the geometric surface from fetching sky light. Filament: `float horizon = min(1.0 + dot(r, n), 1.0); specularIBL *= horizon*horizon;` (credited to Russell 2015) [verify] — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]. Activision's GTAO/GTSO is a fuller specular-occlusion approach — [SIGGRAPH 2016 PBS course page, Jimenez et al. "Practical Realtime Strategies for Accurate Indirect Occlusion"](https://blog.selfshadow.com/publications/s2016-shading-course/) [M]

Procedural studio environment and WebGL2 plumbing:
- three.js ships `RoomEnvironment`, a procedural "photo studio" scene made of boxes and emissive light panels. It is rendered through `PMREMGenerator.fromScene()` into a prefiltered radiance map and is the standard zero-download neutral studio IBL in the three.js / model-viewer ecosystem — [three.js RoomEnvironment.js](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/environments/RoomEnvironment.js) [M]; [three.js PMREMGenerator docs](https://threejs.org/docs/#api/en/extras/PMREMGenerator) [M]
- three.js PMREM packs all roughness levels into a single 2D "cubeUV" atlas, a WebGL1-era design. The original implementation approximated GGX filtering with successive blurs. Whether current three.js now uses true GGX importance sampling is unverified (see Gaps) — [three.js PMREMGenerator docs](https://threejs.org/docs/#api/en/extras/PMREMGenerator) [M]
- WebGL2 facts that matter here [M, from the WebGL 2.0 spec and GLSL ES 3.00]:
  - Seamless cube-map filtering is always on.
  - RGBA16F textures are filterable in core.
  - Rendering into RGBA16F/RGBA32F needs the EXT_color_buffer_float extension, which is near-universal on desktop.
  - Linear filtering of 32-bit float textures needs OES_texture_float_linear.
  - `textureLod`, `dFdx`/`dFdy` and `fwidth` are core in GLSL ES 3.00; no OES_standard_derivatives is needed.
  - [WebGL 2.0 specification](https://registry.khronos.org/webgl/specs/latest/2.0/) [M]

HDRIs and licensing:
- Poly Haven publishes every asset, including its HDRIs, under CC0. Commercial use is allowed and no attribution is required — [Poly Haven FAQ](https://polyhaven.com/faq) [S]; [Poly Haven docs FAQ](https://docs.polyhaven.com/en/faq) [S]
- Poly Haven studio HDRIs suited to product renders include the `studio_small_0X` series, `photo_studio_01`, the `brown_photostudio_0X` series and `photo_studio_loft_hall`. These are names I recall and should be checked on the site [verify]. — [Poly Haven](https://polyhaven.com/faq) [S]

WebGPU:
- In WebGPU, rgba16float is renderable, filterable and usable as a storage texture in core. Prefiltering can therefore be one compute dispatch per mip, writing through storage textures. 32-bit float filtering is the optional `float32-filterable` feature, and f16 arithmetic is the optional `shader-f16` feature — [WebGPU spec](https://www.w3.org/TR/webgpu/) [M] [verify feature names]. Nothing in this section requires WebGPU.

### Inferences
- **Recommended zero-download IBL pipeline** (my synthesis of Karis, Filament and three.js):
  1. Evaluate the existing procedural studio function into a 128² RGBA16F cubemap: 6 draws, rerun only when the key light's azimuth, elevation or Kelvin changes. Memory is 128·128·6·8 B ≈ 786 KB, and about 1.05 MB with the full mip chain.
  2. Prefilter mips 1..5 (64² → 4²) with 32–64 GGX/VNDF samples and filtered importance sampling, using α = (mip/maxMip)² or Filament's inverse LOD mapping. Total work is about 6 × 5.5k texels × 64 samples ≈ 2 M texture fetches. My estimate is roughly 1 ms on an Iris Xe-class GPU, so re-prefiltering live while the user drags the light is plausible. This is unbenchmarked.
  3. Generate the DFG LUT once at load with a fragment shader: RG16F (or RGBA16F to add the F82 channel from Section 7), 32×32 to 128×128, 64–256 samples per texel. The function is smooth, so even 32×32 (4 KB VRAM) should be visually indistinguishable. This is an inference to verify against a 128² reference. Alternatively, skip the LUT and use Karis's `EnvBRDFApprox`.
  4. Compute SH9 on the CPU by evaluating a JS mirror of the studio function at about 1–4k directions, or with a GPU reduction. Upload 9 vec3 uniforms.
- **Analytic alternative with no cubemap:** model each softbox as an anisotropic spherical Gaussian (ASG) and approximate the GGX lobe as an SG, so the specular convolution is closed-form per light. Matt Pettineo's "SG Series" blog posts cover the math [M: https://therealmjp.github.io/posts/sg-series-part-1-a-brief-and-incomplete-history-of-baked-lighting-representations/]. This is fully dynamic and roughness-correct, but rectangles become soft ellipses, so the crisp strip edges that sell "expensive metal" are lost. Use it only for fill lights.
- **Top-down geometry insight:** the camera looks straight down, so V ≈ +Z. A rim normal tilted by profile slope angle θ reflects to zenith angle 2θ, in the azimuth of the SDF gradient. The rim profile therefore scans a band of the environment from zenith (flat crest) to 2·θmax. Studio features need to sit inside that band or the rim will never "see" them. For example, if θmax = 45°, reflections reach the horizon.
- **Bandwidth if an HDRI is used:** reflections on rough or moderately glossy rims need very little resolution (a 256×128 RGBE PNG, tens of KB). Mirror-polished rims reveal low resolution, but our rims are small on screen, so 512×256 is likely the ceiling. Treat the HDRI as an optional download over the procedural default.
- **Overall cost frame** (my estimates; unbenchmarked): the 96-EU Iris Xe peaks at roughly 2 TFLOPS FP32 (back-of-envelope 96 EU × 8 lanes × 2 FLOP × ~1.3 GHz, unverified). At 1440p and 60 fps that is about 221 Mpix/s, which leaves on the order of 1–3k realistically usable ALU per pixel at 100% coverage. A full rim stack fits comfortably: direct GGX (~30) + split-sum IBL (1 fetch + ~15) + energy compensation (~3) + anisotropy (~25) + clear coat lobe (~40 + 1 fetch) + one LTC strip light (~100 + 2 fetches) + iridescence (~120, or 1 fetch if LUT'd) + specular AA (~15). The real risk is texture bandwidth and overdraw, not ALU.

### Gaps
- I could not confirm Filament's exact LUT size, its LOD formula or the UE mip formula verbatim; I didn't re-read the source text.
- I didn't verify whether three.js PMREMGenerator (2025–2026 releases) now uses GGX importance sampling or still uses blur approximations. I also didn't verify whether three.js replaced `DFGApprox` with a LUT.
- I could not confirm the exact list of Poly Haven studio HDRI names or their 1K/2K `.hdr` file sizes; I expect 1K `.hdr` to be about 1–2 MB, but that is unverified.
- No benchmark data for prefilter cost on Intel or AMD integrated GPUs was found or fetched.

---

## 2. Multiple-scattering energy compensation for GGX (Kulla-Conty, Turquin/Filament, Fdez-Agüera)

### Takeaway
Single-scatter GGX ignores light that bounces between microfacets more than once. Energy loss therefore grows with roughness, and rough or satin gold, brass and copper come out too dark and too desaturated. This is a big part of why ad-hoc PBR metals look "gray-plastic". The fix costs about 3–10 ALU and reuses the DFG values already fetched for IBL. Brightening is strongest for rough, high-F0 metals, and colored metals also get more saturated, which is the correct "rich gold" behavior.

### Cited Findings
- Kulla & Conty (Sony Imageworks, SIGGRAPH 2017) add a compensation lobe f_ms(μo, μi) = (1 − E(μo))(1 − E(μi)) / (π(1 − E_avg)), where E(μ) is the single-scatter directional albedo, stored in a small 2D table over (μ, roughness), and E_avg = 2∫E(μ)μdμ is a 1D table over roughness. For colored conductors, f_ms is multiplied by F_avg²·E_avg / (1 − F_avg(1 − E_avg)), with F_avg the cosine-weighted average Fresnel. Their furnace tests show rough GGX darkening and the corrected result; for colored metals the multiple-bounce term increases saturation. — [Kulla & Conty 2017, "Revisiting Physically Based Shading at Imageworks" slides](https://blog.selfshadow.com/publications/s2017-shading-course/imageworks/s2017_pbs_imageworks_slides.pdf) [S]; [SIGGRAPH 2017 PBS course page](https://blog.selfshadow.com/publications/s2017-shading-course/) [S]
- Filament's cheaper approach, following Turquin 2019, scales the whole specular lobe: `energyCompensation = 1.0 + f0 * (1.0 / dfg.y - 1.0);`, then `Fr *= energyCompensation` for direct lights and IBL alike. dfg.y is the LUT channel holding the single-scatter albedo with F = 1. This equals 1 + F0·(1 − E_ss)/E_ss. It is presented as a good approximation, not an exact solution. — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]; Turquin, "Practical multiple scattering compensation for microfacet models" (ILM tech report, 2019) [M: https://blog.selfshadow.com/publications/turquin/ms_comp_final.pdf]
- Fdez-Agüera 2019 gives a real-time IBL formulation that works directly from Karis's (A, B) DFG pair, plus energy-conserving diffuse for dielectrics [verify exact listing]:
  ```glsl
  vec2  f_ab   = DFG(NoV, roughness);                   // (A,B): LUT or EnvBRDFApprox terms
  vec3  Fr     = max(vec3(1.0 - roughness), F0) - F0;   // roughness-dependent Fresnel
  vec3  k_S    = F0 + Fr * pow(1.0 - NoV, 5.0);
  vec3  FssEss = k_S * f_ab.x + f_ab.y;                 // single-scatter
  float Ess    = f_ab.x + f_ab.y;
  float Ems    = 1.0 - Ess;
  vec3  Favg   = F0 + (1.0 - F0) / 21.0;                // cosine-weighted avg of Schlick
  vec3  Fms    = FssEss * Favg / (1.0 - Ems * Favg);
  vec3  Edss   = 1.0 - (FssEss + Fms * Ems);            // dielectric diffuse energy left
  vec3  kD     = diffuseColor * Edss;
  vec3  color  = FssEss * prefilteredRadiance + (Fms * Ems + kD) * irradianceSH;
  ```
  — [Fdez-Agüera 2019, "A Multiple-Scattering Microfacet Model for Real-Time Image-based Lighting", JCGT 8(1)](https://www.jcgt.org/published/0008/01/03/paper.pdf) [S]
- F_avg = F0 + (1−F0)/21 is exact for Schlick: 2∫₀¹(1−μ)⁵μ dμ = 2·B(2,6) = 2/42 = 1/21. I checked this by hand. — consistent with [Fdez-Agüera 2019](https://www.jcgt.org/published/0008/01/03/paper.pdf) [S]
- three.js MeshPhysicalMaterial implements Fdez-Agüera's multiscattering (`computeMultiscattering`) in `lights_physical_pars_fragment`, which makes it a GLSL ES 3.00-compatible reference — [three.js source](https://github.com/mrdoob/three.js/blob/dev/src/renderers/shaders/ShaderChunk/lights_physical_pars_fragment.glsl.js) [M]
- Blender EEVEE also carries a multiscatter GGX term; this pull request cleans it up — [Blender PR #111634](https://projects.blender.org/blender/blender/pulls/111634/files) [S]

### Inferences
- Use Filament's scalar `energyCompensation` on both the direct key light and the IBL. It needs one extra LUT channel you already have, or, with the analytic fit, Ess = AB.x + AB.y. Use Fdez-Agüera only if you want the slightly better IBL color behavior and energy-conserving diffuse on floors (marble, wood, lacquer).
- Expect the biggest visible change on brushed, satin or bead-blasted finishes (α ≈ 0.3–0.7) and almost none on mirror polish. This is what makes champagne, brushed-brass and bronze rims read as metal instead of dark plastic.
- Cost is about 3 ALU (Filament) or about 12 ALU (Fdez-Agüera) per pixel, with zero extra bytes.

### Gaps
- I could not re-check the exact magnitude of energy loss at α = 1 for GGX. Figures around "up to ~60%" are commonly quoted, but I could not verify them this session, so no number is asserted.
- The exact Kulla-Conty table resolutions were not confirmed.

---

## 3. Anisotropic GGX for brushed metal (tangent from the SDF gradient) and anisotropic IBL

### Takeaway
Anisotropic GGX with a tangent derived analytically from the SDF gradient gives brushed or "spun" metal rims that stretch highlights along or across the rim. Filament's "bent reflection vector" trick fakes the anisotropic IBL streak with about 10 ALU and no extra textures. The SDF of a rounded convex polygon gives a gradient that is continuous across the rim band, so the tangent field is seam-free by construction.

### Cited Findings
- Filament's anisotropic GGX D and correlated visibility [verify]:
  ```glsl
  float D_GGX_Anisotropic(float NoH, vec3 h, vec3 t, vec3 b, float at, float ab) {
      float ToH = dot(t,h), BoH = dot(b,h), a2 = at*ab;
      vec3 v = vec3(ab*ToH, at*BoH, a2*NoH);
      float v2 = dot(v,v), w2 = a2/v2;
      return a2*w2*w2*(1.0/PI); }
  float V_SmithGGXCorrelated_Anisotropic(float at, float ab, float ToV, float BoV,
                                         float ToL, float BoL, float NoV, float NoL) {
      float lambdaV = NoL*length(vec3(at*ToV, ab*BoV, NoV));
      float lambdaL = NoV*length(vec3(at*ToL, ab*BoL, NoL));
      return 0.5/(lambdaV + lambdaL); }
  ```
  — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- Filament parameterizes anisotropy as at = max(α(1+aniso), 0.001) and ab = max(α(1−aniso), 0.001), following Kulla & Conty 2017. It prefers this to Burley's aspect = sqrt(1−0.9·aniso) because it can produce sharper highlights — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]; [Kulla & Conty 2017](https://blog.selfshadow.com/publications/s2017-shading-course/imageworks/s2017_pbs_imageworks_slides.pdf) [S]
- Filament fakes anisotropic IBL with a bent normal or bent reflection vector [verify]:
  ```glsl
  vec3 anisoDir = anisotropy >= 0.0 ? B : T;
  vec3 anisoT   = cross(anisoDir, V);
  vec3 anisoN   = cross(anisoT, anisoDir);
  float bend    = abs(anisotropy) * saturate(5.0 * perceptualRoughness);
  vec3 bentN    = normalize(mix(N, anisoN, bend));
  vec3 r        = reflect(-V, bentN);   // then textureLod(prefiltered, r, lod)
  ```
  — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- glTF KHR_materials_anisotropy defines `anisotropyStrength` [0,1] and `anisotropyRotation` (radians), plus an `anisotropyTexture` (RG = direction in tangent space, B = strength). Roughness maps as α_t = mix(α, 1, strength²) and α_b = α [verify]. Khronos's Render-Fidelity test pages exist for comparing engines. — [Khronos glTF PBR overview](https://www.khronos.org/gltf/pbr/) [S]; [glTF-Transform KHRMaterialsAnisotropy](https://gltf-transform.dev/modules/extensions/classes/KHRMaterialsAnisotropy) [S]; [Khronos Render Fidelity: AnisotropyStrengthTest](https://github.khronos.org/glTF-Render-Fidelity/compare/AnisotropyStrengthTest) [S]; spec [KHR_materials_anisotropy README](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_anisotropy/README.md) [M]
- Engines are adopting the extension: Bevy has a pull request implementing KHR_materials_anisotropy — [Bevy PR #13450](https://github.com/bevyengine/bevy/pull/13450) [S]

### Inferences
- **Tangent from the SDF (my derivation):** let g = normalize(∇d) be the 2D SDF gradient, either analytic from the polygon SDF or from `dFdx/dFdy` on d.
  - Circumferential brushing, along the rim (the typical machined or brushed bezel look): t₀ = vec3(−g.y, g.x, 0).
  - Radial or "sunburst" brushing, across the rim: t₀ = vec3(g, 0).
  - Then Gram-Schmidt against the profile normal N: t = normalize(t₀ − N·dot(N, t₀)), b = cross(N, t).
- **Why there are no seams:** for a rounded convex polygon, d = sdConvexPolygon(p) − r. ∇d is continuous everywhere except on the polygon's medial axis, which lies in the interior. If the rim band is narrower than the inradius minus r, the tangent field is seam-free around corners. Direction rotates smoothly through each rounded corner, which is exactly how a lathe-turned or brushed frame catches light.
- **Brush streaks:** perturb the roughness or normal with 1D value noise indexed by the coordinate perpendicular to the brush direction (arc length or d). The noise must be band-limited by the pixel footprint (Section 6) or it will shimmer when trays animate.
- Use the analytic anisotropic D and V for the key light, plus the bent reflection vector for IBL. LTC tables are isotropic (Section 5), so for an anisotropic rim under an LTC strip light, fall back to evaluating the isotropic LTC with α = sqrt(at·ab), or with the bent normal. This is an approximation.
- Cost: about +25 ALU over isotropic, with no textures.

### Gaps
- The source attribution of Filament's bent-normal technique, and whether the `saturate(5·roughness)` factor is current Filament code, could not be re-checked.
- I could not re-confirm the KHR_materials_anisotropy roughness mapping formula verbatim.

---

## 4. Clear coat layering, thin-film iridescence (pearl/nacre) and sheen

### Takeaway
A Filament- or glTF-style clear coat (a second GGX lobe with f0 = 0.04 that attenuates the base by 1 − Fc) is the single biggest win for marble, varnished wood and lacquer floors. It gives the sharp "wet" highlight on top of a softer base. Belcour & Barla's analytic Airy thin-film Fresnel, as standardized in KHR_materials_iridescence, gives physically plausible pearl and nacre color shifts for about 100–150 ALU, or for a single fetch if it is baked into a small LUT at load. Charlie sheen is the right lobe for any velvet or felt tray lining.

### Cited Findings
Clear coat:
- Filament's clear coat is a GGX lobe with Kelemen visibility `V_Kelemen(LoH) = 0.25/(LoH*LoH)` and Schlick Fresnel with f0 = 0.04 and f90 = 1, scaled by `clearCoat` strength. The base layer is attenuated by (1 − Fc): `color = (Fd + Fr*energyComp)*(1.0 - Fc) + Frc`. The coat uses the geometric normal rather than the base's normal map, so the coat stays glassy-smooth over a detailed base. — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- Filament changes the base f0 under a coat, because the base interface is coat-to-material (IOR ≈ 1.5) rather than air-to-material. It uses a polynomial approximation [verify]: `f0Base = saturate(f0*(f0*(0.941892 - 0.263008*f0) + 0.346479) - 0.0285998)`. It also raises base roughness so the base is never smoother than the coat: `base = mix(base, max(base, coatRoughness), clearCoat)`. — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- For IBL, the coat does a second `textureLod` along reflect(−V, N_coat) at the coat's roughness LOD, weighted by Fc = F_Schlick(0.04, 1, NoV)·clearCoat, and the base IBL is multiplied by (1 − Fc) — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- glTF KHR_materials_clearcoat (`clearcoatFactor`, `clearcoatRoughnessFactor`, optional `clearcoatNormalTexture`) layers as f = f_base·(1 − clearcoat·F_c) + clearcoat·f_coat, with IOR fixed at 1.5 (F0 = 0.04) — [Khronos glTF PBR overview](https://www.khronos.org/gltf/pbr/) [S]; spec [KHR_materials_clearcoat README](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_clearcoat/README.md) [M]

Thin-film iridescence:
- Belcour & Barla (SIGGRAPH 2017) replace the Fresnel term of a microfacet BRDF with the Airy reflectance of a thin film over a base. Their key contribution is anti-aliasing the spectral oscillation: they integrate the Airy series against the CIE color-matching functions analytically in Fourier space, via a Gaussian fit of the CMF spectra. That gives correct RGB with no spectral sampling, at real-time cost. — [Belcour & Barla 2017, Unity blog summary](https://blog.unity.com/es/technology/a-practical-extension-to-microfacet-theory-for-the-modeling-of-varying-iridescence) [S]; [ACM SIGGRAPH History Archive entry](https://history.siggraph.org/?p=102374) [S]
- KHR_materials_iridescence parameters are `iridescenceFactor` (default 0), `iridescenceIor` (default 1.3), `iridescenceThicknessMinimum` (default 100 nm) and `iridescenceThicknessMaximum` (default 400 nm). The thickness texture's G channel interpolates between min and max. The result replaces Fresnel as F = mix(F_Schlick, F_iridescence, iridescenceFactor). — [KHR_materials_iridescence README](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_iridescence/README.md) [M] (this fetch was attempted and permission timed out); [Khronos glTF PBR overview](https://www.khronos.org/gltf/pbr/) [S]
- Reference implementation in the glTF spec and Sample Viewer, condensed [verify all constants]:
  ```glsl
  // cosTheta2 via Snell; return vec3(1) on TIR
  R12 = F_Schlick(IorToF0(etaFilm, 1.0), cosTheta1);   T121 = 1.0 - R12;
  phi12 = (etaFilm < 1.0) ? PI : 0.0;  phi21 = PI - phi12;
  baseIor = F0ToIor(clamp(baseF0, 0.0, 0.9999));
  R23 = F_Schlick(IorToF0(baseIor, etaFilm), cosTheta2);
  phi23 = per-channel (baseIor < etaFilm) ? PI : 0.0;
  OPD = 2.0 * etaFilm * thickness_nm * cosTheta2;  phi = phi21 + phi23;
  R123 = clamp(R12*R23, 1e-5, 0.9999);  r123 = sqrt(R123);
  Rs = T121*T121 * R23 / (1.0 - R123);
  I = R12 + Rs;  Cm = Rs - T121;
  for (m = 1; m <= 2; ++m) { Cm *= r123; I += Cm * 2.0*evalSensitivity(m*OPD, m*phi); }
  return max(I, 0.0);
  // evalSensitivity: phase = 2π·OPD·1e-9;
  //   val=(5.4856e-13,4.4201e-13,5.2481e-13) pos=(1.6810e6,1.7953e6,2.2084e6) var=(4.3278e9,9.3046e9,6.6121e9)
  //   xyz = val*sqrt(2π var)*cos(pos*phase+shift)*exp(-phase²·var);
  //   xyz.x += 9.7470e-14*sqrt(2π·4.5282e9)*cos(2.2399e6·phase+shift.x)*exp(-4.5282e9·phase²);
  //   xyz /= 1.0685e-7;  rgb = XYZ_TO_REC709 * xyz;
  ```
  — [KHR_materials_iridescence README](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_iridescence/README.md) [M]; derived from [Belcour & Barla 2017](https://history.siggraph.org/?p=102374) [S]
- There is a student-built real-time iridescence implementation from Saarland University's 2025 CG competition, which shows the technique is commonly reimplemented. I did not read its content. — [Saarland CG 2025 iridescence page](https://graphics.cg.uni-saarland.de/competition/cg-2025/original/ekans/iridescence.html) [S]

Sheen:
- Filament's cloth and sheen lobe uses the "Charlie" distribution from Estevez & Kulla 2017 with Neubelt & Pettineo's visibility [verify]:
  ```glsl
  float D_Charlie(float a, float NoH) {
      float invA = 1.0/a; float sin2h = max(1.0 - NoH*NoH, 0.0078125);
      return (2.0 + invA) * pow(sin2h, invA*0.5) / (2.0*PI); }
  float V_Neubelt(float NoV, float NoL) { return 1.0/(4.0*(NoL + NoV - NoL*NoV)); }
  ```
  The IBL integral for sheen goes in the DFG LUT's third channel — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]; [SIGGRAPH 2017 PBS course (Estevez & Kulla sheen)](https://blog.selfshadow.com/publications/s2017-shading-course/) [S]
- glTF KHR_materials_sheen (`sheenColorFactor`, `sheenRoughnessFactor`) layers sheen over the base with albedo scaling, roughly f = f_sheen + f_base·(1 − max(sheenColor)·E_sheen(NoV)), where E_sheen is a small precomputed directional-albedo table [verify] — [Khronos glTF PBR overview](https://www.khronos.org/gltf/pbr/) [S]

### Inferences
- **Material recipes** (my synthesis):
  - **Marble / varnished wood / lacquer:** dielectric base (diffuse albedo + specular f0 0.04, α 0.3–0.6 for honed stone and wood grain) plus clear coat 1.0 with coat α ≈ 0.02–0.08. Add Fdez-Agüera energy-conserving diffuse so the coat visibly "eats" base brightness at grazing angles.
  - **Lacquer:** saturated base color with very low coat roughness. Optionally add slight coat orange-peel as a low-frequency normal perturbation on the coat normal only.
  - **Pearl/nacre:** cream or white diffuse base with low specular, plus iridescence factor 0.6–1.0, film IOR ≈ 1.5–1.7, and thickness varying 250–500 nm via low-frequency noise. Optionally add clear coat for the "wet" lustre.
  - **Velvet tray lining:** Charlie sheen, sheen α 0.3–0.6.
  - **Jewel glass:** clear-coat-like specular plus refraction. Transmission and dispersion are outside this note.
- **Iridescence bake:** for a fixed film IOR and base, Airy reflectance depends only on (cosθ₁, thickness). Bake a 64×64 RGBA16F LUT at load (32 KB VRAM, zero download) to cut per-pixel cost to one fetch. The LUT is cheap enough to regenerate if the IOR slider changes.
- **Clear coat cost:** about +40 ALU and +1 cubemap fetch per pixel, plus a second LTC evaluation (2 fetches) if area lights are used. Skip the coat on metal rims (bare polished metal) unless you want a "lacquered brass" look.

### Gaps
- Nacre is physically a multilayer stack of aragonite platelets, which produces interference and diffraction ("orient"). A single thin film is an approximation. I found no source this session giving real-time multilayer nacre models or measured film thickness and IOR for pearls. The aragonite refractive index range of about 1.53–1.68 is from general knowledge and was not verified.
- I could not re-read the exact sheen albedo-scaling formula in the KHR_materials_sheen spec, or whether it uses min(E(NoV), E(NoL)).

---

## 5. Area lights with Linearly Transformed Cosines (LTC): strip-softbox highlights, WebGL2 feasibility, LUT sizes

### Takeaway
LTC gives exact-shaped, roughness-correct rectangular highlights from long strip softboxes, which is the hallmark of product and jewelry photography. It has run in WebGL2 for years (three.js `RectAreaLight`). It needs two 64×64 RGBA LUTs, about 64 KB at half-float, and roughly 100 ALU plus 2 fetches per light per pixel. That is affordable for 1–3 strip lights on integrated GPUs. LTC is isotropic only, so brushed metal needs an approximation.

### Cited Findings
- Heitz, Dupuy, Hill & Neubelt (SIGGRAPH 2016) approximate the GGX BRDF·cos lobe for a given (view angle, roughness) as a clamped cosine distribution warped by a 3×3 matrix M. Integrating over a polygonal light becomes: transform the polygon's vertices by M⁻¹, then use the closed-form polygon-to-cosine edge integral (Lambert's formula). Fitted M⁻¹ coefficients and a magnitude/Fresnel term live in LUTs indexed by (roughness, view angle). The method also supports textured polygon lights through a prefiltered light texture. — [Hill & Heitz, "Real-Time Area Lighting: a Journey from Research to Production" (SIGGRAPH 2016 Advances)](https://www.advances.realtimerendering.com/s2016/s2016_ltc_rnd.pdf) [S]; [s2016 Advances course page](https://blog.selfshadow.com/publications/s2016-advances/) [S]; paper copy [Real-Time Polygonal-Light Shading with LTC (PDF)](https://sgga.kaist.ac.kr/~sungeui/ICG_F18/Students/Real-Time%20Polygonal-Light%20Shading%20with%20Linearly%20Transformed%20Cosines.pdf) [S]; [Heitz research page](https://eheitzresearch.wordpress.com/415-2/) [M] (this fetch was attempted and permission timed out)
- In production, the horizon-clipping step (clipping the polygon to the upper hemisphere, which is branchy) is replaced by a "sphere approximation": compute the unclipped vector form factor F, then look up a pre-tabulated horizon-clipped value indexed by (F.z/|F|, |F|), stored in the second LUT's spare channel — [Hill & Heitz 2016 Advances talk](https://www.advances.realtimerendering.com/s2016/s2016_ltc_rnd.pdf) [S]
- Optimized edge integral used in three.js and production code [verify constants]:
  ```glsl
  vec3 LTC_EdgeVectorFormFactor(vec3 v1, vec3 v2) {
      float x = dot(v1, v2), y = abs(x);
      float a = 0.8543985 + (0.4965155 + 0.0145206*y)*y;
      float b = 3.4175940 + (4.1616724 + y)*y;
      float v = a / b;
      float theta_sintheta = (x > 0.0) ? v : 0.5*inversesqrt(max(1.0 - x*x, 1e-7)) - v;
      return cross(v1, v2) * theta_sintheta; }
  // Evaluate: build frame (T1,T2,N) with T1 = normalize(V - N*NoV);
  // mat3 Minv = mInv(texture(ltc_1, uv)) * transpose(mat3(T1,T2,N));
  // L_i = normalize(Minv * (corner_i - P)); F = Σ EdgeVectorFormFactor(L_i, L_{i+1});
  // len = length(F); z = F.z/len; scale = texture(ltc_2, vec2(z*0.5+0.5, len)).w; spec = len*scale;
  // uv = vec2(roughness, sqrt(1.0 - NoV)) * (63.0/64.0) + 0.5/64.0;   // 64x64 LUT
  // final: lightColor * (F0*t2.x + (1.0 - F0)*t2.y) * spec, where t2 = texture(ltc_2, uv)
  ```
  — [three.js RectAreaLight implementation in lights_physical_pars_fragment](https://github.com/mrdoob/three.js/blob/dev/src/renderers/shaders/ShaderChunk/lights_physical_pars_fragment.glsl.js) [M]; LUT data in [RectAreaLightUniformsLib.js](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/lights/RectAreaLightUniformsLib.js) [M]
- LUT size: two 64×64 RGBA tables. LTC1 holds the 4 non-trivial M⁻¹ coefficients; LTC2 holds magnitude, Fresnel and the horizon-clipping (sphere) term. Each is 64·64·4 = 16,384 values: 32 KB as half-float or 64 KB as float32, for 64 KB or 128 KB total. three.js provides both float and half-float versions. — [three.js RectAreaLightUniformsLib.js](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/lights/RectAreaLightUniformsLib.js) [M]; the byte arithmetic is mine.
- Follow-up work covers line and disk lights, both useful for thin tube-light streaks: [Heitz & Hill, "Real-Time Line- and Disk-Light Shading with LTC" (Unity blog)](https://blog.unity.com/cn/technology/real-time-line-and-disk-light-shading-with-linearly-transformed-cosines) [S]
- Accessible OpenGL tutorial implementations exist: [LearnOpenGL "Area Lights" (2022 guest article)](https://learnopengl.com/Guest-Articles/2022/Area-Lights) [S]; [Magnum blog "Area lights with LTCs"](https://blog.magnum.graphics/guest-posts/area-lights-with-ltcs) [S]. So does a textured-LTC "screen light" implementation for Unity: [LTCGI](https://github.com/pimaker/ltcgi) [S]
- A cheaper legacy alternative is Karis 2013's "representative point" method for sphere and tube lights. It shades with the point on the light closest to the reflection ray and multiplies by an energy-normalization factor (α/α′)², where α′ is α widened by the light's angular size [verify exact constant] — [Karis 2013](https://cgvr.informatik.uni-bremen.de/teaching/cg_literatur/Brian%20Karis%20-%20Real%20Shading%20in%20Unreal%20Engine%204,%202013%20Siggraph%20Course.pdf) [S]

### Inferences
- **Feasibility verdict:** yes for WebGL2. Use RGBA16F LUTs, which are filterable in core WebGL2. Shipping cost is about 64 KB binary, about 87 KB as base64 inline, or less with gzip/brotli. That is the only download in this whole note that can't be generated at runtime, because LTC requires an offline fit.
- **Placement strategy:** use LTC only for the hero key strip, which moves with the user's light azimuth and elevation, plus at most one rim or kicker strip. Bake the rest of the studio (fills, scrims, black flags) into the IBL from Section 1. LTC highlights then stay razor-sharp and move correctly without re-prefiltering. The procedural env should *omit* the LTC lights so they aren't double-counted, or keep them only in the diffuse SH.
- **Clear coat:** clear-coated floors need a second LTC evaluation at coat roughness (2 more fetches, about 60 ALU), weighted by Fc, with the base attenuated by (1 − Fc).
- **Anisotropic rims:** LTC tables are isotropic. Approximate by evaluating at α_eff = sqrt(at·ab) with the bent normal, or stretch the light polygon along the tangent. I did not verify an anisotropic-LTC paper this session (see Gaps).
- **Cost:** about 80–120 ALU plus 2 fetches per strip light per shaded pixel (my estimate). Three strips on 1440p at full coverage stay well inside the budget from Section 1.

### Gaps
- I could not verify the license of Heitz's LTC fitting code and tables (`selfshadow/ltc_code`); three.js redistributes LUT data under MIT, which suggests permissive terms, but this is unconfirmed.
- The anisotropic GGX LTC extension (I recall "Bringing Linearly Transformed Cosines to Anisotropic GGX", Kt et al. 2022) was not confirmed.
- A JCGT 11(1) 2022 paper appeared in the LTC search results, but I could not read it.

---

## 6. Specular anti-aliasing: avoiding sparkle and shimmer on high-frequency normals (Toksvig, Kaplanyan-Hill, Tokuyoshi, LEAN/CLEAN), applied to analytic SDF-profile normals

### Takeaway
Polished rims have high curvature over a few pixels, and with no TAA in a UI their highlights crawl and sparkle as trays move. The fix is geometric specular AA. Estimate the normal's variance over the pixel footprint and add it to α² (Kaplanyan-Hill 2016, Tokuyoshi-Kaplanyan 2019 and 2021, shipped in Filament). Our normals come from an analytic profile h(d), so the variance can be computed analytically from h″ and the isoline curvature. That avoids the blocky 2×2-quad noise of `dFdx(N)` for about 15 ALU.

### Cited Findings
- Kaplanyan, Hill, Patney & Lefohn (HPG 2016) filter the NDF over the pixel footprint in slope space. They estimate footprint normal variance from screen-space derivatives and convolve it into the roughness, giving temporally stable highlights. — [Kaplanyan et al. 2016, "Filtering Distributions of Normals for Shading Antialiasing"](https://research.nvidia.com/sites/default/files/pubs/2016-06_Filtering-Distributions-of/NDFFiltering.pdf) [S]
- Tokuyoshi & Kaplanyan (I3D 2019) simplify this into a few lines, with a recommended screen-space variance and a clamp [verify constants]:
  ```glsl
  float filteredAlpha2(vec3 N, float alpha2) {
      const float SIGMA2 = 0.15915494; // 1/(2π), screen-space filter variance
      const float KAPPA  = 0.18;       // clamp on added roughness²
      vec3 dndu = dFdx(N), dndv = dFdy(N);
      float kernelRoughness2 = 2.0*SIGMA2*(dot(dndu,dndu) + dot(dndv,dndv));
      return clamp(alpha2 + min(kernelRoughness2, KAPPA), 0.0, 1.0); }
  ```
  — [Tokuyoshi & Kaplanyan 2019, "Improved Geometric Specular Antialiasing"](https://www.jp.square-enix.com/tech/library/pdf/ImprovedGeometricSpecularAA.pdf) [S]
- Their 2021 JCGT follow-up does the filtering in projected (2D slope) space, producing anisotropic α and more stable results at grazing angles — [Tokuyoshi & Kaplanyan 2021, "Stable Geometric Specular Antialiasing with Projected-Space NDF Filtering", JCGT 10(2)](https://www.jcgt.org/published/0010/02/02/paper.pdf) [S]
- Filament ships this as `specularAntiAliasing` with material parameters `specularAntiAliasingVariance` (default 0.15) and `specularAntiAliasingThreshold` (default 0.2) [verify defaults], applied to α² in the same form — [Filament docs](https://google.github.io/filament/Filament.md.html) [S]
- Specular AA in WebGL engines is still an active topic. A PlayCanvas issue proposes adding both normal-map filtering and geometric specular AA. I did not read its content. — [PlayCanvas engine issue #9512](https://github.com/playcanvas/engine/issues/9512) [S]
- The older techniques are Toksvig 2004 (shorten the averaged normal across mip levels and use 1 − |N̄| to widen the lobe) and LEAN / CLEAN mapping (Olano & Baker 2010 / Baker 2011: store first and second slope moments in mipmapped textures and reconstruct a Gaussian/Beckmann lobe per texel). All three assume normals come from mipmapped normal-map textures. — background as summarized in [Kaplanyan et al. 2016](https://research.nvidia.com/sites/default/files/pubs/2016-06_Filtering-Distributions-of/NDFFiltering.pdf) [S]

### Inferences
- **Toksvig, LEAN and CLEAN are largely outdated for our case.** They need a texture mip chain of normals or moments, and our normals are analytic. Use geometric specular AA instead. The LEAN idea, carrying slope mean and variance, can still be reproduced analytically (below).
- **Analytic variance for z = h(d), d = SDF** (my derivation, consistent with the Tokuyoshi formula above):
  - The profile tilt is θ = atan(h′(d)), so the across-rim normal-rotation rate is dθ/dd = h″/(1 + h′²).
  - Along the rim, the normal rotates about Z at the isoline curvature κ = 1/(r_corner + d) on rounded corners and 0 on straight edges. Its magnitude is sinθ·κ per unit arc.
  - For an exact SDF, |∇d| = 1 and Σ(dFdx(d)² + dFdy(d)²) = px², where px is the pixel size in SDF units. So the Frobenius norm of dN per pixel is ‖dN‖² ≈ px²·[(h″/(1+h′²))² + (sinθ·κ)²].
  ```glsl
  float h1 = profileD1(d), h2 = profileD2(d);         // analytic h'(d), h''(d)
  float dThetaDd = h2 / (1.0 + h1*h1);
  float sinT = abs(h1) * inversesqrt(1.0 + h1*h1);
  float kappa = isCorner ? 1.0/max(rCorner + d, 1e-4) : 0.0;
  float px = length(vec2(dFdx(d), dFdy(d)));          // smooth: d is linear-ish per quad
  float var = px*px * (dThetaDd*dThetaDd + (sinT*kappa)*(sinT*kappa));
  alpha2 = clamp(alpha*alpha + min(2.0*SIGMA2*var, KAPPA), 0.0, 1.0);
  ```
  This is smooth across quads, costs about 15 ALU, and also gives the direction of maximum variance (across the rim). That makes the 2021 anisotropic variant easy: add the across term to α_b and the along term to α_t.
- **Practical WebGL2 rules:** take `dFdx`/`dFdy` in uniform control flow, before any `if (insideRim)` branch, because derivatives are undefined in non-uniform control flow. Keep a separate coverage AA for the SDF silhouette, e.g. `smoothstep(-fwidth(d), fwidth(d), -d)`. Apply the widened α to the direct lobe, the IBL LOD, the LTC lookup and the DFG/energy-compensation lookup so they all agree.
- **Profile design:** the sharpest "ridge" highlights come from small high-curvature beads in the profile. With AA they render as a stable line about 1 px wide instead of a crawling dotted line. Without AA, that thin-bead look is exactly what sparkles.

### Gaps
- I could not re-confirm the exact SIGMA2 and KAPPA constants (0.15915494 / 0.18 in the paper vs 0.15 / 0.2 Filament defaults, both from recall).
- No source covering analytic-profile (non-texture) specular AA specifically was found. The derivation above is mine and should be validated visually, for example with a slowly rotating tray at 1440p.

---

## 7. Physically correct metal F0, F82 / edge-tint models (Gulbrandsen, Hoffman, OpenPBR), spectral vs RGB

### Takeaway
Use measured linear-RGB F0 for pure metals (gold, silver, copper, aluminum and brass are tabulated). Upgrade Schlick to Hoffman's "F82-tint" Fresnel, which adds a cheap correction term matching the real reflectance dip near 82°. That is now the production standard in Adobe Standard Material, OpenPBR and Blender 4.x Principled, and it is what gives gold and copper their characteristic edge coloration. Rose gold, bronze and champagne are alloys or finishes without standard tables, so their values are art-directed approximations. Spectral rendering is unnecessary for a UI. Only thin-film iridescence needs spectral treatment, and Belcour-Barla already handles it analytically.

### Cited Findings
- Measured linear F0 values for metals. Real-Time Rendering 4th ed. Table 9.2 and Hoffman's PBS course notes report gold (1.000, 0.782, 0.344), silver (0.972, 0.960, 0.915), copper (0.955, 0.638, 0.538), aluminum (0.913, 0.922, 0.924), brass (0.910, 0.778, 0.423), iron (0.562, 0.565, 0.578), titanium (0.542, 0.497, 0.449), platinum (0.673, 0.637, 0.585), nickel (0.660, 0.609, 0.526), chromium (0.549, 0.556, 0.554) and zinc (0.664, 0.824, 0.850) [verify all]. Filament publishes a similar table, and its exact values differ slightly by source. — [Hoffman, SIGGRAPH PBS course "Background: Physics and Math of Shading" (s2015)](https://blog.selfshadow.com/publications/s2015-shading-course/) [M]; [Filament docs, metal f0 table](https://google.github.io/filament/Filament.md.html) [S]
- Hoffman's generalization of Adobe's Fresnel model is F(μ) = F_Schlick(F0, μ) − a·μ(1−μ)⁶. The scalar or RGB a is chosen so that reflectance at μ̄ = 1/7 (≈ 81.8°, "F82") hits a target edge color. Solving gives a = [F_Schlick(F0, μ̄) − F82]/(μ̄(1−μ̄)⁶) = [F_Schlick(F0, μ̄) − F82]·7⁷/6⁶. — [Hoffman, "Generalization of Adobe's Fresnel Model"](https://renderwonk.com/publications/wp-generalization-adobe/gen-adobe.pdf) [S]
- OpenPBR's metal Fresnel uses this F82-tint form. The `specular_color` input multiplies the Schlick value at μ̄ to set the 82° target, which is how OpenPBR represents edge tint. A Dec 2025 arXiv paper documents OpenPBR's novel features and implementation details. — [OpenPBR: Novel Features and Implementation Details (arXiv 2512.23696)](https://arxiv.org/pdf/2512.23696) [S]; [OpenPBR spec](https://academysoftwarefoundation.github.io/OpenPBR/) [M]
- Blender Cycles added "Metallic Tint" to the Principled BSDF using the F82-Tint model (Blender 4.0 era) — [Blender PR #112551](https://projects.blender.org/blender/blender/pulls/112551) [S]
- Hoffman (MAM 2019) argues against plugging RGB complex IORs (n, k at three wavelengths) into the full conductor Fresnel equations. Spectral-to-RGB conversion does not commute with the nonlinear Fresnel function, so the "physically exact" RGB-Fresnel approach is less accurate than a well-fitted Schlick-plus-correction model. — [Hoffman 2019, "Fresnel Equations Considered Harmful"](https://diglib.eg.org/handle/10.2312/mam20191305) [S]; [EG digital library PDF](https://diglib7.eg.org/bitstream/handle/10.2312/mam20191305/007-011.pdf) [S]
- Gulbrandsen's "Artist Friendly Metallic Fresnel" (JCGT 3(4), 2014) maps artist parameters r (reflectivity ≈ F0) and g (edge tint) to complex IOR [verify]: n = g·(1−r)/(1+r) + (1−g)·(1+√r)/(1−√r), k = sqrt((r(n+1)² − (n−1)²)/(1−r)). It then evaluates the exact unpolarized conductor Fresnel. Kulla & Conty used this parameterization at Imageworks. — [Gulbrandsen 2014, JCGT](https://jcgt.org/published/0003/04/03/) [M]; [Kulla & Conty 2017 slides](https://blog.selfshadow.com/publications/s2017-shading-course/imageworks/s2017_pbs_imageworks_slides.pdf) [S]

### Inferences
- **Drop-in F82-tint Fresnel** (from Hoffman's formula; algebra checked by hand, F(μ̄) = tint·F_Schlick(μ̄)):
  ```glsl
  vec3 F_SchlickF82(vec3 F0, vec3 tint, float mu) {           // tint = OpenPBR specular_color
      const float MU_BAR = 1.0/7.0;
      const float K = 823543.0/46656.0;                          // 7^7 / 6^6 = 1/(μ̄(1-μ̄)^6) ≈ 17.6513
      float om = 1.0 - mu;
      vec3 Fs    = F0 + (1.0 - F0)*(om*om*om*om*om);
      vec3 FsBar = F0 + (1.0 - F0)*0.4626655;                    // (6/7)^5 = 7776/16807
      vec3 a     = FsBar*(1.0 - tint)*K;
      return clamp(Fs - a*mu*(om*om*om*om*om*om), 0.0, 1.0); }
  ```
  The cost is about 15 ALU versus about 6 for plain Schlick.
- **IBL consistency:** split-sum assumes F is linear in F0, i.e. Schlick. Add a third or fourth DFG LUT channel, dfg.w = ∫ D·V·(v·h)(1−v·h)⁶·…, generated at load with the rest of the LUT, so the IBL is mix(dfg.x, dfg.y, F0) − a·dfg.w. Generating it costs nothing because the LUT is built on the GPU (Section 1).
- **Unmeasured alloys** (art-directed, not measured data):
  - **Rose gold:** start from a gold-copper blend of F0.
  - **Bronze:** start near copper with lowered and desaturated F0.
  - **Champagne:** typically a PVD- or anodized-coated finish; a pale warm F0 with neutral F82 tint.
  - Real alloy optical constants don't mix linearly, so treat these as starting points to be tuned by eye under the studio env.
  - F82 tint values (edge color) should be slightly desaturated or shifted relative to F0 for gold and copper. Tune visually; a source with measured F82 for these finishes was not found.
- **Spectral vs RGB:** RGB is fine for everything here except thin film, which Belcour-Barla handles in XYZ. Multiple-scattering compensation with RGB F_avg already produces the realistic "color deepening" of rough gold (Section 2).

### Gaps
- I could not re-verify the RTR4 and Filament F0 tables row by row; treat them as recall-quality and spot-check them.
- I recall physicallybased.info as a CC0 JSON database of measured material values, possibly including metal specular and F82 colors. It was not checked this session.
- No measured F0 or F82 data was found for rose gold, bronze or champagne finishes.
- I could not re-read OpenPBR's exact equation form, so whether `specular_color` scales F82 exactly as written above should be checked against the spec.

---

## 8. How product / jewelry / luxury-watch renders achieve the "expensive" metal look (strip softboxes, black flags, gradient reflectors)

### Takeaway
Polished metal has no color or form of its own beyond F0. It looks like whatever it reflects. Product photographers make metal look expensive by controlling what it reflects: long narrow strip softboxes give crisp elongated highlights that trace form, graduated diffusion panels give smooth tonal sweeps, and black flags or cards put dark bands into the reflection for contrast. Our procedural studio function should copy that layout. That means a mostly dark room, 1–3 HDR strips, one large gradient scrim and explicit black bands, placed within the band of directions the rim profile actually sees from a top-down camera.

### Cited Findings
- Strip softboxes are a standard product-lighting modifier with long, narrow aspect ratios. One example is the Elinchrom Rotalux Strip at 100×35 cm (about 3:1) — [Park Cameras listing, Elinchrom Rotalux Strip 100×35 cm](https://www.parkcameras.com/shop/Elinchrom-Rotalux-Strip-100x35cm-Softbox_E355141E) [S]; [Roberts Camera, Rotalux Stripbox 20"×51"](https://robertscamera.com/rotalux-stripbox-20-x-51) [S]
- "Gradient reflection" is a named product-photography technique, covered in dedicated tutorials. I confirmed the titles only, not the content. — [PetaPixel, "Tutorial: How to Create the Perfect Gradient Reflection for Product Photography" (2014)](https://petapixel.com/2014/04/02/tutorial-create-perfect-gradient-reflection-product-photography) [S]; [PictureCorrect, "How to Add a Gradient Reflection to Product Photography Shots"](https://picturecorrect.com/?p=43017) [S]
- Practitioner discussion of strip lighting for products — [DPReview forum "Strip Lighting?"](https://www.dpreview.com/forums/thread/3573920) [S]
- Khronos publishes the "PBR Neutral" tone mapper, designed for e-commerce and product rendering so base colors survive tone mapping while highlights roll off. This is relevant because "expensive" depends on HDR strip values compressing gracefully to white. — [KhronosGroup/ToneMapping](https://github.com/KhronosGroup/ToneMapping) [M]

### Inferences
These are my synthesis of standard photographic practice; I could not read the tutorial bodies this session.
- **Why the current look reads cheap:** an ad-hoc env that is uniformly bright or smoothly varying makes chrome look gray and flat, like plastic. Metal needs high dynamic range and hard-edged contrast in what it reflects.
- **Studio function recipe** (units relative to background):
  1. **Background / room:** near-black, 0.01–0.03. Make it slightly warm or cool to match the key Kelvin.
  2. **Key strip:** 1 rectangle, aspect about 1:3 to 1:6 (long axis roughly tangent to the dominant rim run), luminance 20–50× background. Give it a soft falloff edge of about 5–10% of its width so mid-roughness metals get a graded edge while mirrors still show a crisp line. Drive it from the key light's azimuth, elevation and Kelvin, and make it the LTC light from Section 5.
  3. **Kicker / rim strip:** opposite side, 0.3–0.6× key, possibly cooler Kelvin for warm/cool separation on silver.
  4. **Overhead gradient scrim:** a large panel near zenith with a linear or smoothstep ramp, about 2× to 0.2× across its width. This produces the "gradient sweep" on flat rim crests and floors.
  5. **Black flags:** explicit zero-luminance bands between the strips. These become the dark contour lines that define a polished bevel.
  6. **Floor bounce:** below the horizon, the tray-floor color at low intensity, so steep inner-fillet reflections pick up the lining color, as jewelry trays do.
- **Top-down placement rule (from Section 1):** a rim facet with slope θ reflects zenith angle 2θ toward the gradient azimuth. Put strips at zenith angles 2θ for the profile slopes where you want highlights.
  - Example: a profile peaking at 30° slope sees out to 60° zenith, so key strips at 35–55° zenith land on the shoulders of the profile.
  - Because the gradient azimuth rotates around the polygon, each tray side catches a different part of the studio. That variation is the main "it's real" cue.
- **Profile design for jewelry-style lines:** a crisp convex bead (small radius, high h″) produces a thin bright line where its slope crosses a strip's angle. A broad low-curvature cove produces a wide soft gradient. Alternating bead, cove and bead gives the classic "moulded frame" multi-line highlight. Specular AA (Section 6) is what keeps the thin lines stable.
- **Finishing:** use HDR output, a filmic or neutral tone mapper (Khronos PBR Neutral, AgX or ACES), and a light bloom threshold above about 1.0 so strip highlights glow slightly. Color-correct the key Kelvin before tone mapping, not after.
- **Rough relative cost of the whole stack per rim pixel** (my estimate): direct GGX + F82 + anisotropy + energy compensation ≈ 70 ALU; IBL (1–2 cubemap fetches + DFG fetch + SH) ≈ 40 ALU; one LTC strip ≈ 100 ALU + 2 fetches; specular AA ≈ 15 ALU. Total is about 250 ALU and 4–5 fetches, well within the integrated-GPU budget sketched in Section 1. Floors with clear coat and iridescence add about 150–200 ALU more.

### Gaps
- No primary source was retrieved on how luxury-watch or jewelry *UI* renders (as opposed to photography) are lit. Specific lighting rigs used by brands, such as multi-exposure compositing per component, are unverified and were not asserted.
- The tutorial content for gradient reflections and strip lighting was not read; only the titles and existence were confirmed. The principles above are my synthesis, not quotations.
- WebGPU availability across browsers as of late 2026 was not confirmed this session. My understanding is that Chrome/Edge shipped it in 2023 and Safari and Firefox (Windows) followed in 2025, but this is unverified. None of the techniques above require WebGPU. WebGPU mainly helps compute-based prefiltering and possibly `shader-f16` throughput on Intel Xe.
