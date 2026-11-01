# Material Surface Realism for a Real-Time WebGL2 Renderer: Procedural vs Scanned PBR

> How this was verified. Web search confirmed that every URL cited below exists and has the expected title in this session. Page bodies could NOT be fetched: WebFetch permission was not granted, and direct HTTPS was refused by the egress proxy with CONNECT 403. Search returned only titles and URLs. What each source says therefore comes from the researcher's prior knowledge of these well-known publications (knowledge cutoff mid-2026). It has not been re-read this session. Items tagged (verify) are numbers or details held with lower confidence. Cost and size estimates under "Inferences" are the researcher's own engineering arithmetic, not measured benchmarks.

## 1. Better procedural noise for realism (noise choice, warping, anisotropy, ridged multifractals, anti-aliasing)

### Takeaway
Value noise is the main reason the current textures look "CG": it has lattice-aligned blobs and lumpy spectral energy. Moving to gradient or simplex noise (Gustavson/McEwan psrdnoise or OpenSimplex2) fixes that. Two-level domain warping and ridged multifractal octaves then supply the flowing, branching structure that real stone and wood have. Every periodic or fbm term must also be band-limited with fwidth(): fcos() for sine-based veins and per-octave frequency clamping for fbm. Without that, fine detail shimmers into aliasing, and the shimmer reads as cheap.

### Cited Findings
- Survey of the field (Lagae, Lefebvre, Cook, DeRose, Drettakis, Ebert, Lewis, Perlin, Zwicker, CGF 2010). It compares lattice noises (value, gradient/Perlin, simplex), wavelet noise and sparse-convolution noise (Gabor) on spectral control and band-limitedness. Its central point is that noise is only filterable/anti-aliasable to the degree that it is band-limited. Perlin/gradient noise is "approximately" band-limited; value noise is worse. Gabor noise gives precise control of spectrum and orientation (true anisotropy), at higher evaluation cost (sum of many Gabor kernels per cell). — [Lagae et al., A Survey of Procedural Noise Functions (EG DL)](https://diglib.eg.org:443/handle/10.2312/CGF.v29i8pp2579-2600); [PDF mirror](https://scribblethink.org/Work/LLCDDELPZ10SPNF.pdf); [HAL](https://hal.archives-ouvertes.fr/hal-00920177)
- A later "State of the Art in Procedural Noise Functions" report also exists in the Eurographics digital library. It was not read. — [EG DL STAR](https://diglib.eg.org/items/104b3068-e6ed-48f8-93ad-4e4e2b3dd5b6)
- psrdnoise (Gustavson & McEwan, JCGT 11(1), 2022), "Tiling simplex flow noise in two and three dimensions", provides:
  - 2D and 3D simplex noise with optional periodic tiling
  - a rotating-gradient "flow" parameter (animated swirl without the cost of domain warping)
  - analytic gradients returned alongside the value
  - published GLSL source

  Simplex noise evaluates 3 corners in 2D and 4 in 3D, against 4 and 8 for classic lattice noise. That makes 3D solid textures notably cheaper. — [JCGT paper (low-res PDF)](https://jcgt.org/published/0011/01/02/paper-lowres.pdf)
- The LYGIA shader library (GLSL/HLSL/MSL/WGSL) ships ports of psrdnoise and IQ's fcos and "untile" (texture-repetition breaking). It is a drop-in GLSL source for these functions. — [LYGIA psrdnoise mirror](https://git.gay/kaneraZh/lygia/src/tag/1.4.1/generative/psrdnoise.msl); [LYGIA fcos.glsl](https://git.gay/kaneraZh/lygia/src/tag/1.4.1/math/fcos.glsl); [LYGIA untile.glsl](https://git.gay/kaneraZh/lygia/src/tag/1.4.1/sample/untile.glsl)
- OpenSimplex2 (by KdotJPG) is the successor to OpenSimplex. It was designed as a patent-free simplex-type noise with fewer directional artifacts, and has 2D/3D/4D variants, including "S" (smoother) and "F" (faster) flavors (verify). Ports exist in several languages. — [opensimplex2 CRAN README](https://cran.nics.utk.edu/cran/web/packages/opensimplex2/readme/README.html); [rdrr.io opensimplex2](https://rdrr.io/cran/opensimplex2)
- Domain warping (Inigo Quilez):
  - Basic form: f(p) = fbm(p + fbm(p + fbm(p))).
  - Canonical two-level version: q = (fbm(p), fbm(p + (5.2, 1.3))); r = (fbm(p + 4q + (1.7, 9.2)), fbm(p + 4q + (8.3, 2.8))); result = fbm(p + 4r).
  - Coloring: the intermediate vectors q and r are reused as extra color-mix parameters. This is what gives the marbled, folded, geological look.

  Cost is 5 fbm evaluations per pixel. — [IQ, Domain Warping](https://iquilezles.org/articles/warp/); [example port](https://github.com/FradSer/30-days-of-shaders/blob/master/16-shaders-generative-designs-fractal-brownian-motion-2/domain-warping-by-inigo-quilez.frag)
- The Book of Shaders ch. 13 covers fbm, "turbulence" (sum of |noise|) and "ridge" (offset − |noise|, squared, so octaves form sharp creases), plus domain warping. Ridged/turbulent variants make vein-like creases; plain fbm makes clouds. — [The Book of Shaders: Fractal Brownian Motion](https://thebookofshaders.com/13/)
- IQ "Filtering procedural textures": analytic box-filtering of patterns over the pixel footprint, which is estimated from dFdx/dFdy of the texture coordinate. The canonical example is the closed-form filtered checkerboard and grid. It also covers when to fall back to supersampling. — [IQ, filterable procedurals](https://iquilezles.org/articles/filterableprocedurals/) (URL from task brief; search-confirmed domain only)
- IQ "Bandlimited synthesis":
  - Replace cos(x) with fcos(x) = cos(x)·sin(w/2)/(w/2), where w = fwidth(x).
  - Cheaper approximation: cos(x)·smoothstep(2π, 0, w).
  - Effect: any cosine/sine term fades to its mean when its frequency exceeds what the pixel can represent.

  This applies directly to sine-warped marble veins and ring-based wood (both are sin/fract of a phase). — [IQ, Bandlimiting](https://iquilezles.org:443/articles/bandlimiting/); [LYGIA fcos](https://git.gay/kaneraZh/lygia/src/tag/1.4.1/math/fcos.glsl)
- Classic Perlin-era noise references (implementation, anti-aliasing) are available as teaching material from Utah and Linköping. The Linköping TNM084 course also has lectures on Voronoi noise, distance maps and anti-aliasing. — [Utah noise.pdf](https://my.eng.utah.edu/~cs6965/papers/noise.pdf); [TNM084 Voronoi noise, distance maps, anti-aliasing (2023)](https://computer-graphics.se/TNM084/Files/pdf23/4.%20Voronoi%20noise,%20distance%20maps,%20anti-aliasing.pdf)

### Inferences
- **Why value noise looks "not substantive"**
  - Its features cluster on the integer lattice, so the eye sees faint axis-aligned blockiness.
  - With cubic smoothstep interpolation its derivative is only C1. Lighting from derived normals then shows creases at cell borders.
  - Fix: switch to gradient noise with a quintic fade (6t⁵−15t⁴+10t³) or to simplex noise. Rotate each octave by about 37° (a fixed 2x2 rotation) and use a lacunarity of about 2.01 rather than exactly 2.0, so octave lattices never line up. This is a widely used IQ/Shadertoy convention, consistent with the warp article's fbm.
- **Per-pixel cost on integrated GPUs** (rough arithmetic, verify on target hardware)
  - Building blocks:
    - 2D gradient or simplex noise ≈ 40–80 ALU ops.
    - 6-octave fbm ≈ 300–500 ops.
    - IQ two-level warp (5 fbm) ≈ 1,500–2,500 ops.
    - Finite-difference normals multiply that by 3–5×.
  - Budget: an Intel Iris Xe-class iGPU peaks around 2 TFLOPS FP32. At 1080p and 60 fps, a 4 ms shading budget allows about 3,900 peak ops per pixel, perhaps 1,500 sustained.
  - Conclusion: a full-screen warped-fbm marble with derived normals at 60 fps every frame is at or past the edge.
  - Recommendation: the bench and tray surfaces are static, so generate the procedural material once on the GPU into textures (WebGL2 render-to-texture, then generateMipmap). Then sample those textures per frame. This keeps download at zero bytes and puts runtime cost at texture fetches. Re-bake only on resize or a material change.
- **Frequency clamping for fbm** (standard practice from Texturing & Modeling; consistent with the band-limiting argument in the Lagae survey)
  - Compute w = fwidth(p) (or max of |dFdx| and |dFdy|).
  - For octave i with frequency fᵢ, multiply its amplitude by 1 − smoothstep(0.25, 0.5, fᵢ·w). 0.5 cycles per pixel is the Nyquist limit.
  - Break out of the loop once the weight reaches 0.
  - This both removes shimmer and makes distant or small surfaces cheaper.
- **Brushed and spun metal does not need Gabor noise.**
  - Use a highly anisotropic domain scale, e.g. noise(vec2(u·400, v·2)) along the brush direction.
  - For spun or circular brushing on tray rims, use noise of (radius·k, angle·small) in polar coordinates.
  - Pair the noise with an anisotropic GGX lobe whose tangent follows the brush direction (see §5).
  - Gabor noise is only worth it if exact oriented spectra are needed. It is markedly more expensive.
- **Ridged multifractal** (Musgrave form: signal = (offset − |n|)², each octave weighted by the previous octave's signal) gives branching crease networks. It is the cheapest procedural source of convincing marble veins and cracks.

### Gaps
- Could not retrieve IQ's articles, Book of Shaders or psrdnoise text to quote exact code or measured timings. Formulas above are from prior knowledge of those sources.
- No published, measured per-noise ALU or timing numbers for current integrated GPUs (Intel Xe/Arc iGPU, AMD 680M/780M) under WebGL2/ANGLE were found. The cost figures are estimates.
- Gabor noise speed-ups (e.g. later "fast and normalized" Gabor work) were not verified this session.

## 2. State-of-the-art procedural recipes (marble, wood, granite/terrazzo, nacre/MOP, tortoiseshell, lacquer/enamel, Substance-style graphs)

### Takeaway
The convincing recipes come from material physics:
- **Wood:** a 3D growth field around a pith axis, sliced by the board plane. This yields cathedral figure on flat-sawn boards and ray fleck on quarter-sawn boards for free. Add pores and a fiber-direction field that drives a sub-finish anisotropic highlight (chatoyant "figure").
- **Marble:** layered vein networks (ridged/warped + Voronoi-edge cracks) at several widths, plus a parallax-offset "deep" vein layer for translucency.
- **Nacre:** a thin-film interference Fresnel term (Belcour–Barla) whose film thickness is driven by banded, warped noise.

All of these can be baked once to textures on the GPU.

### Cited Findings
- **Procedural wood (Liu, Dong, Hašan, Marschner).** "Procedural wood textures" (arXiv 1511.04224, Graphics Interface 2016) and "Simulating the structure and texture of solid wood" (ACM TOG / SIGGRAPH Asia 2016) model wood as a 3D solid:
  - growth rings as a perturbed distance field from the pith axis, with an earlywood→latewood color profile per ring
  - pores (vessels) as small elongated features along the fiber direction
  - rays as thin radial structures
  - a 3D fiber-direction field

  Parameters are fitted to photographs. Rendering uses a finished-wood BRDF with fiber highlights. — [arXiv 1511.04224](https://arxiv.org/pdf/1511.04224); [Cornell wood project page](https://www.cs.cornell.edu/projects/wood/index.html); [SIGGRAPH history entry](https://history.siggraph.org/?p=210600); [supplemental](https://cs.cornell.edu/projects/wood/supplemental.html)
- **Knots (Larsson et al., ACM TOG / SIGGRAPH 2022).** "Procedural Texturing of Solid Wood with Knots" extends procedural wood with knots, modeled from skeleton geometry and time-of-growth fields (live vs dead knots). As the researcher recalls it, the method is implemented as a real-time fragment shader (verify). — [Maria Larsson procedural knots page](https://github.com/marialarsson/marialarsson.github.io/blob/main/procedural_knots.html); [SIGGRAPH history](https://history.siggraph.org/?p=117819)
- **2025 language-driven wood.** "From words to wood" (Hafidi et al., EG 2025) is a recent text-driven procedural wood pipeline. It is relevant as a 2025 state-of-the-art pointer; content not read. — [Hafidi 2025 PDF](https://cgg.mff.cuni.cz/wp-content/uploads/2025/07/Hafidi2025_EG2025_From_words_to_wood.pdf)
- **Finished-wood appearance (Marschner, Westin, Arbree, Moon, SIGGRAPH 2005).** "Measuring and modeling the appearance of finished wood" shows that the "figure" of wood comes from an anisotropic subsurface highlight produced by fibers beneath the clear finish. That highlight moves with view and light direction (chatoyancy in curly or quilted maple and similar woods). The model is: smooth finish layer (specular) + diffuse + a fiber-highlight lobe parameterized by fiber direction, lobe width and highlight color. — [Marschner SG05 wood page](https://www.cs.cornell.edu/~srm/publications/SG05-wood.html); [PDF](https://www.graphics.cornell.edu/pubs/2005/MWAM05.pdf)
- **Thin-film iridescence (Belcour & Barla, SIGGRAPH 2017).** "A Practical Extension to Microfacet Theory for the Modeling of Varying Iridescence" replaces the Fresnel term of a microfacet BRDF with an Airy-summation thin-film reflectance. It is evaluated with spectral anti-aliasing in closed form, so RGB rendering needs no spectral sampling. The film thickness is a spatially varying parameter. This is the physical basis for nacre and mother-of-pearl, oil-slick, anodized and heat-tinted metals. — [Unity blog by Belcour & Barla](https://blog.unity.com/es/technology/a-practical-extension-to-microfacet-theory-for-the-modeling-of-varying-iridescence); [SIGGRAPH history](https://history.siggraph.org/?p=102374)
- **glTF iridescence and clear coat.** KHR_materials_iridescence is the glTF standardization of this thin-film model (factor, film IOR, thickness texture remapped between min/max thickness). Khronos lists it with KHR_materials_clearcoat, anisotropy, sheen, transmission and volume in its PBR extension set. — [Khronos glTF PBR](https://www.khronos.org/gltf/pbr/); [notes on KHR_materials_iridescence](https://scrapbox.io/0b5vr/glTF:%20KHR_materials_iridescence)
- **three.js MeshPhysicalMaterial** implements the same layers:
  - clearcoat, clearcoatRoughness and clearcoatNormalMap (clear-coat-only normal, the hook for orange peel)
  - iridescence, iridescenceIOR and iridescenceThicknessRange (default about [100, 400] nm, verify), plus iridescenceThicknessMap
  - anisotropy and sheen
  - transmission/thickness

  — [three.js MeshPhysicalMaterial docs](https://threejs.org/docs/api/en/materials/MeshPhysicalMaterial.html)
- **Filament** (Google) documents a production clear-coat model (a second isotropic GGX specular lobe with fixed IOR 1.5, base layer attenuated by the coat's Fresnel), anisotropy and cloth/sheen. Its shader code is a reference implementation for GLSL ES. — [Filament materials](https://google.github.io/filament/main/materials.html); [Filament PBR doc](https://google.github.io/filament/main/filament.html)
- **Voronoi noise and distance maps** (crack networks, cell IDs for granite and terrazzo): Linköping TNM084 lecture notes. IQ's "Voronoi edges" technique gives exact distance to cell borders, unlike F2−F1, which is not a true distance, so vein width stays uniform. — [TNM084 Voronoi noise and distance maps (2022)](https://computer-graphics.se/TNM084/Files/pdf22/4.%20Voronoi%20noise%20and%20distance%20maps.pdf)
- **ML procedural graphs.** VLMaterial (2025) generates Blender procedural material node graphs from images with vision-language models. It shows procedural node graphs remain the industry representation for materials, but it is not a runtime technique. — [HF paper page 2501.18623](https://huggingface.co/papers/2501.18623)

### Inferences
These are implementation recipes. They were synthesized by the researcher from the cited models and are not quoted from a single source.

- **Polished white marble (Carrara/Calacatta, "elevated")**
  - Base: warm-white albedo (~0.80–0.88 linear) with very low-amplitude fbm cloudiness (±3%).
  - Vein layer A (primary): ridged multifractal of a 2-level domain-warped p, sharpened with pow(r, 6–12). Gray-gold color, width varied by a low-frequency noise.
  - Vein layer B (hairline): Voronoi-edge distance on a warped domain, 1 − smoothstep(0, w, d), w ≈ 0.5–1.5 px after filtering.
  - Depth layer: evaluate layer A again at p − V_t.xy/V_t.z·depth (V_t = tangent-space view vector; depth ≈ 2–5 mm in world units), with 2 fewer octaves and 40–60% contrast. Mix it under the surface veins. This parallax "subsurface" layer is the single most effective cheap cue for stone depth.
  - Specular: F0 0.04, roughness 0.03–0.08, with roughness slightly higher (+0.05) inside veins. Polish differs between minerals, which sells the material.
  - Add a soft wrap-diffuse term (N·L remapped as (N·L + 0.3)/1.3) to fake light bleed.
  - Calcite's refractive index is about 1.49–1.66 (birefringent), so F0 = 0.04 is acceptable (verify).
- **Dark violet stone** (bench option). Two physically grounded directions:
  - Imperial-porphyry-like: deep purple-red matrix plus Worley-F1 phenocryst speckles in cream or pink, at 2 scales.
  - Charoite-like: swirling purple fibers. Warped anisotropic noise plus an anisotropic highlight following the warp's tangent produces chatoyant sheen. This is the more "hyper-real" choice.
- **Walnut**
  - Evaluate a 3D ring field: d = length(P.xy − pith(P.z)) + A·fbm(P·k), with ring phase φ = d·ringsPerCm.
  - Ring profile: smooth earlywood ramp, then a sharp latewood edge (asymmetric sawtooth through smoothstep). Band-limit it with fwidth(φ).
  - Flat-sawn cathedral arches: tilt the pith axis 1–3° relative to the board plane and offset it a few cm below the board. The planar slice then produces nested parabolic arches automatically.
  - Quarter-sawn ray fleck: place the board plane through the pith axis. Rays become Worley cells stretched about 20:1 along the radial direction, lighter and slightly glossier.
  - Pores: Worley F1 dots stretched about 15–30:1 along the fiber, darkened, with roughness +0.1. Walnut is semi-ring-porous, with pores fairly evenly distributed.
  - Finish: clear coat (roughness 0.05–0.15 for satin oil, about 0.02 for gloss) over the Marschner fiber highlight, implemented as an anisotropic lobe with its tangent along the fiber direction.
- **Granite and terrazzo**
  - Granite: 2-scale Worley F1. Use the cell ID hash to choose a mineral from a weighted palette (e.g. ~55% feldspar, ~30% quartz, ~15% biotite/mica). Add small-scale fbm inside cells, and slightly lower polish on quartz.
  - Granite sparkle: give a hashed subset of mica cells a random micro-normal, and add a glint when it aligns with H (see §5).
  - Terrazzo: Voronoi cells with a hash dropout for chip density. The chip mask is F2−F1 > threshold, so boundaries are irregular. Each chip gets a palette color, over a fine-fbm cement base.
- **Mother-of-pearl and abalone**
  - Film thickness t(p) = mix(tmin, tmax, bands(warp(p))), where bands() quantizes warped noise into 6–12 terraces with soft edges. The terraces mimic stacked aragonite platelet layers.
  - Feed t into a Belcour–Barla or KHR iridescence Fresnel.
  - Base color: cream/white for pearl-oyster MOP; dark green-blue for abalone.
  - Add a fine anisotropic fibrous normal following the warp direction, and a high-gloss clear coat on top.
  - Pearl "orient": low-intensity iridescence plus a soft sheen lobe.
- **Tortoiseshell** (no authoritative procedural source found)
  - Base: honey or amber.
  - Spots: dark brown/black from thresholded, domain-warped fbm.
  - Depth: evaluate the spots at 2–3 parallax depths, with more blur and less opacity deeper down.
  - Translucency: warm emissive-like lift in thin, light areas.
  - Finish: glossy clear coat.
- **Lacquer and enamel**
  - Base: pigment, optionally with metallic flakes. Coat: GGX, F0 0.04, roughness 0.005–0.03.
  - Orange peel = clearcoatNormal from low-amplitude gradient noise (about 0.5–2° normal tilt, wavelength ~3–10 mm at bench scale). It must be subtle: it should be visible only in the reflection of a straight softbox edge.
  - Urushi-style depth: near-black base with slight colored absorption, which reads as "deep".
  - Enamel: same as lacquer, but lighter at thin edges.
- **Substance Designer node equivalents in GLSL**
  - Histogram Scan → smoothstep(pos − c, pos + c, x)
  - Warp / Directional Warp → domain warp by noise or by the gradient of another field
  - Tile Sampler / Flood Fill → Worley cell loop with per-cell hash IDs
  - Slope Blur → several taps along the gradient direction (expensive; bake only)
  - Curvature/AO → Laplacian of height (cavity darkening)
  - Edge Detect → |∇h| threshold

### Gaps
- Could not verify exact parameter values, ring profiles or code from the Liu et al. and Larsson et al. papers.
- No authoritative published procedural model for tortoiseshell was found. Searches were limited and fetches blocked.
- No authoritative physical data (platelet thickness ranges, terrace spacing) for nacre was retrieved. The "aragonite platelets of about visible-wavelength thickness" description is prior knowledge (verify).
- Shadertoy could not be searched or fetched, so no specific Shadertoy shader IDs for marble, wood, nacre or glints are given.

## 3. Scanned/photogrammetry PBR textures: sources, licensing, sizes, KTX2/Basis in WebGL2, hybrid de-tiling

### Takeaway
ambientCG and Poly Haven are the two primary CC0 sources: free for commercial use with no attribution. Both offer 1K–8K sets with OpenGL-convention normal maps. A 1K set encoded as KTX2 can plausibly ship at roughly 0.4–1 MB (an estimate, not measured), using ETC1S for color/roughness and UASTC with RDO+Zstd for normals, and it uses ~4–8× less VRAM than PNG/JPEG decoded to RGBA8. Scanned marble with long veins tiles badly; stochastic tiling helps only with stationary textures such as granite, terrazzo and fine stone grain. For this project the best ratio of quality to bytes is hybrid: procedural macro structure (veins, rings) plus at most one tiny scanned micro-detail map, or zero assets.

### Cited Findings
- **Licensing**
  - ambientCG assets are released under CC0 1.0 (public domain dedication): commercial use allowed, attribution not required. A third-party license guide summarizes ambientCG's CC0 terms. — [licenseorg ambientCG guide](https://licenseorg.com/guide/3d-assets/ambientcg); license page per task brief: [ambientCG license](https://docs.ambientcg.com/license/) (not fetched)
  - Poly Haven assets (textures, HDRIs, models) are CC0. — [Poly Haven license](https://polyhaven.com/license) (not fetched; URL from brief)
- **Aggregator.** A 2026 guide surveys free PBR texture/HDRI sources for games and is useful for alternative CC0 sources. — [Cinevva, Free PBR Textures, Materials and HDRIs for Games (2026)](https://app.cinevva.com/guides/free-textures-hdris-materials)
- **ambientCG in Godot.** An ambientCG integration exists in the Godot asset library, showing its API and asset use in engines. — [Godot asset library: AmbientCG](https://godotengine.org/asset-library/asset/5152)
- **TextureCan** offers numbered free PBR marble sets, e.g. Calacatta-like "Glossy Black and White Marble 0012" and "Jade Marble 0017". License terms were not verified. — [TextureCan Marble 0012](https://texturecan.com/details/106); [Marble 0017](https://www.texturecan.com/details/415/)
- **Basis Universal and KTX2**
  - Basis Universal (Binomial) supercompressed GPU texture codec, stored in KTX2 (glTF: KHR_texture_basisu).
  - ETC1S mode: smallest files, lower quality. UASTC mode: high quality, 8 bpp before RDO plus Zstandard supercompression.
  - Transcodes at load time in the browser to whichever native format the GPU supports: BC1/BC3/BC7 on desktop, ETC1/ETC2/ASTC on mobile.
  - The repository has a v2.0 tag (2025). Later versions added HDR modes; details not verified.

  — [basis_universal README (v2_0 tag mirror)](https://skia.googlesource.com/external/github.com/BinomialLLC/basis_universal/+/refs/tags/v2_0); [v1_60 snapshot](https://skia.googlesource.com/external/github.com/BinomialLLC/basis_universal/+/refs/tags/v1_60_snapshot_final)
- **Encoding tools**
  - Browser-based KTX2 compression tools exist (useful for someone without a heavy local toolchain). — [Cinevva KTX2 Texture Compressor](https://app.cinevva.com/tools/ktx2-compressor)
  - glTF-Transform provides CLI/JS tooling for KTX2 (etc1s/uastc commands via KTX-Software) and glTF material extensions such as KHR_materials_anisotropy. — [gltf-transform KHRMaterialsAnisotropy](https://gltf-transform.dev/modules/extensions/classes/KHRMaterialsAnisotropy)
  - ktx-parse (Don McCurdy) parses KTX2 in JS. — [ktx-parse](https://awesome.ecosyste.ms/projects/github.com%2Fdonmccurdy%2Fktx-parse)
- **Histogram-preserving blending (Heitz & Neyret, HPG 2018 / PACMCGIT, DOI 10.1145/3233304).**
  - Method: tile the texture on a triangle grid, take 3 random patches per pixel, and blend with variance-preserving weights in a Gaussianized histogram space, then invert with a precomputed LUT.
  - Repetition disappears while contrast and histogram are kept.
  - Works for stochastic or stationary textures only; not structured ones.
  - Runtime: 3 texture fetches + 1 LUT fetch plus a little ALU. Precompute is a per-texture CPU histogram transform.

  — [Crossref DOI record](https://api.crossref.org/works/10.1145%2F3233304)
- **Unity Labs implementation.** Unity Labs published an open implementation ("Procedural Stochastic Texturing") with a blog explanation; community Shader Graph nodes exist. — [Unity blog](https://unity.com/blog/engine-platform/procedural-stochastic-texturing-in-unity); [UnityLabs GitHub README](https://github.com/UnityLabs/procedural-stochastic-texturing/blob/master/README.md); [Unity discussion](https://discussions.unity.com/t/procedural-stochastic-texturing-prototype/732031)
- **Simpler variant (Burley, JCGT 8(4), 2019).** "On Histogram-Preserving Blending for Randomized Texture Tiling" removes the need for the Gaussianizing LUT by using a simpler contrast-restoring blend operator. It is simpler and cheaper for WebGL. — [JCGT 0008/04/02 PDF](https://www.jcgt.org/published/0008/04/02/paper.pdf)
- **Laplacian blending (2025).** "GPU-Friendly Laplacian Texture Blending" (arXiv 2502.13945) is a newer de-tiling/blending approach that uses a Laplacian pyramid, built from GPU mip levels per the title, to blend without contrast loss. Content not read. — [arXiv 2502.13945](https://arxiv.org/pdf/2502.13945)
- **Cheapest de-tiling option.** IQ's "texture repetition" technique is available as LYGIA `untile.glsl`. It uses per-tile random offsets or rotations with a virtual-pattern blend. — [LYGIA untile.glsl](https://git.gay/kaneraZh/lygia/src/tag/1.4.1/sample/untile.glsl)

### Inferences
- **VRAM per 1024² texture with mips** (format arithmetic):
  - RGBA8: ≈ 5.3 MB
  - BC7/ASTC4x4 (8 bpp): ≈ 1.4 MB
  - BC1 (4 bpp): ≈ 0.7 MB

  Windows laptops running Chrome/Edge (ANGLE over D3D11) normally expose S3TC and BPTC (BC7) to WebGL2, but usually not ETC2 or ASTC. KTX2Loader would therefore transcode UASTC→BC7 and ETC1S→BC1/BC3 there (verify on the target machine via `renderer.extensions` / `gl.getSupportedExtensions()`).
- **Download estimate for a 1K marble set as KTX2** (not measured; verify by encoding a test set):
  - albedo ETC1S: ~100–250 KB
  - roughness ETC1S (single channel): ~50–150 KB
  - normal UASTC + RDO + Zstd: ~300–600 KB
  - Total: ≈ 0.5–1 MB. The original ambientCG 1K-JPG zip is likely several MB.
- **Transcoder overhead.** The Basis transcoder (JS + WASM) is a one-time download, probably a few hundred KB (verify the exact size). Under severe data limits this overhead alone can exceed the cost of a fully procedural approach.
- **Recommendation under severe bandwidth limits**
  - Default: fully procedural, baked on GPU at load (0 bytes of assets).
  - Optional: a single 512² or 1K tileable micro-detail normal/roughness map (stone grain, wood pore micro-normal, brushed-metal streaks). Ship it as KTX2-UASTC, or as an 8-bit PNG with a Basis-free path (~200–400 KB). Tile it at world scale, and apply Heitz–Neyret or Burley de-tiling only on stationary layers.
  - Never stochastically tile the vein layer. Veins are long-range structures and blending visibly breaks them.
- **Scanned versus procedural.** Scanned marble at 1K over a ~1 m bench gives about 1 mm per texel. That is under-resolved for a close-up, hyper-real desktop view, so procedural veins (infinite resolution) plus scanned micro-detail is the stronger combination.

### Gaps
- Could not fetch the ambientCG or Poly Haven license pages or their download listings. Exact per-set file sizes (1K/2K JPG and PNG zips) are not reported here, and the CC0 status comes from prior knowledge plus the third-party guide.
- No measured ETC1S/UASTC bitrates or transcoder WASM size were retrieved (verify against the Basis README and three.js `examples/jsm/libs/basis/`).
- The Khronos KTX Artist Guide (UASTC for normal maps, ETC1S for color) is known to the researcher, but its URL was not search-confirmed this session.
- Other CC0 sources (ShareTextures, 3dtextures.me, Poly Haven's API) were not verified.

## 4. Normal and height detail: analytic vs finite-difference vs dFdx/dFdy normals; detail-normal blending; micro-detail that sells scale

### Takeaway
Do not derive normals from screen-space dFdx/dFdy of a procedural height. It is constant per 2x2 quad, which gives blocky, view-dependent faceting and aliasing. Prefer, in order:
1. Bake height and normals in a load-time GPU pass with central differences (best quality, zero runtime cost).
2. Analytic noise derivatives (psrdnoise / IQ derivative noise), at about 1.3–2× the cost of the value alone.
3. Finite differences at runtime (3–5× cost).

Compose layers (macro bump, micro-detail normal, clear-coat orange peel) with the surface-gradient framework or Reoriented Normal Mapping, not by adding normals. Pair fine normals with geometric specular anti-aliasing, so polished surfaces do not sparkle or alias.

### Cited Findings
- **Reoriented Normal Mapping (Barré-Brisebois & Hill, 2012).**
  - Rotates the detail normal into the base normal's frame, which preserves detail on tilted base normals.
  - Compared in the same article against linear, overlay, partial-derivative, whiteout and UDN blends.
  - Compact GLSL: t = n1·(2,2,2) + (−1,−1,0); u = n2·(−2,−2,2) + (1,1,−1); r = t·dot(t,u)/t.z − u.
  - "Whiteout" (normalize(vec3(n1.xy + n2.xy, n1.z·n2.z))) is the cheaper near-equivalent.

  — [Self Shadow, Blending in Detail](https://blog.selfshadow.com/publications/blending-in-detail); [reference implementation repo](https://git.tdem.in/zigguratvertigo/ReorientedNormalMapping); [Unigine node doc](https://developer.unigine.com/ru/docs/future/content/materials/graph/node_library/misc/reorient_normal_blend)
- **Surface gradient framework (Mikkelsen, JCGT 9(3), 2020).** "Surface Gradient–Based Bump Mapping Framework" converts every bump source (tangent-space normal maps, height maps, procedural bumps, triplanar, decals) into a surface gradient. The gradients add linearly and are resolved once into a normal. This is the correct way to stack many detail layers. Unity documents using it in Shader Graph. — [JCGT 0009/03/04](https://jcgt.org/published/0009/03/04/paper.pdf); [Unity blog: normal map compositing using the surface gradient framework](https://blog.unity.com/cn/technology/normal-map-compositing-using-the-surface-gradient-framework-in-shader-graph); [Unity HLSL implementation](https://plastichub.unity.cn/unity-tech-cn/ScriptableRenderPipeline/src/branch/culling...ScriptableRenderPipeline/Core/ShaderLibrary/NormalSurfaceGradient.hlsl)
- **Tangent-free bump mapping (Mikkelsen 2010).** "Bump Mapping Unparametrized Surfaces on the GPU" derives a perturbed normal from screen-space derivatives of position and height, needing no tangents. Its quality is limited by quad-granular derivatives. Earlier thesis: "Simulation of wrinkled surfaces revisited" (2008). — [Mikkelsen 2010 (Unreal docs mirror)](https://docs.unrealengine.com/4.27/Attachments/RenderingAndGraphics/Materials/BumpMappingWithoutTangentSpace/mm_sfgrad_bump.pdf); [Mikkelsen 2008](https://page.mi.fu-berlin.de/block/htw-lehre/wise2012_2013/bel_und_rend/skripte/mikkelsen2008.pdf); [gamedev.net discussion](https://gamedev.net/forums/topic/704383-surface-gradient-based-bump-mapping-framework/)
- **Analytic derivatives.** psrdnoise returns analytic gradients with the noise value. Gustavson's course notes cover procedural bump mapping with analytic derivatives. — [JCGT psrdnoise](https://jcgt.org/published/0011/01/02/paper-lowres.pdf); [Gustavson TNM084 bump mapping notes](https://itn-web.it.liu.se/~stegu76/TNM084-2019/bumpmapping/bumpmapping.pdf)
- **Geometric specular anti-aliasing**
  - Kaplanyan, Hill, Patney, Lefohn (HPG 2016), "Filtering Distributions of Normals for Shading Antialiasing", and Tokuyoshi & Kaplanyan (JCGT 10(2), 2021), "Stable Geometric Specular Antialiasing with Projected-Space NDF Filtering".
  - Mechanism: widen roughness by the screen-space variance of the normal (from dFdx/dFdy of the normal), which removes specular shimmer on fine normal detail. Cost: a few ALU ops.

  — [NVIDIA NDF filtering PDF](https://research.nvidia.com/sites/default/files/pubs/2016-06_Filtering-Distributions-of/NDFFiltering.pdf); [JCGT 0010/02/02](https://www.jcgt.org/published/0010/02/02/paper-lowres.pdf)
- **three.js community demand.** The three.js forum has an open request for better geometric specular AA, so a custom WebGL2 renderer gains by implementing it directly. — [three.js forum thread](https://discourse.threejs.org/t/having-geometric-specular-antialiasing-would-be-incredible/74816)

### Inferences
- **dFdx/dFdy normals.** Derivatives are computed per 2x2 pixel quad, so derived normals are piecewise constant over 2x2 blocks. On high-frequency procedural height that produces visible stair-stepping in highlights, and it changes with zoom. Acceptable only for very low-frequency bumps.
- **Finite differences.** Central differences need 4 extra height evaluations in 2D (forward differences need 2). With warped fbm that is 3–5× the base cost per frame unless baked.
- **Analytic derivatives** through domain warping need the Jacobian chain rule: ∇f(p + w(p)) = (I + J_w)ᵀ ∇f. Doable but error-prone. Baking avoids it.
- **Bake pipeline (WebGL2)**
  - Render the procedural height into an R16F target (EXT_color_buffer_float is widely available on WebGL2), or into RGBA8 with packed height.
  - A second pass computes normals by central differences at bake resolution and writes RG8 (two-channel normal; reconstruct z).
  - Then call generateMipmap.
  - This also gives correct mip-filtered normals. Optionally store per-mip normal variance in roughness (Toksvig-style) for specular AA.
- **Micro-detail that sells scale** for a desk-scale scene (~1 m bench, close camera):
  - Detail frequency must be anchored in world units, not UV: marble micro-pits at ~0.1–0.5 mm, wood pores ~0.1–0.3 mm wide, brushed-metal streak spacing ~10–50 µm (rendered as anisotropy rather than geometry).
  - Most of the "expensive" read comes from roughness variation (polish differs in veins, pores and wear), not from normal amplitude.
  - Keep micro-normal amplitude tiny, and let it appear mainly in specular reflections of large light sources.

### Gaps
- No measured comparison (images or timings) of dFdx-based versus analytic versus finite-difference procedural normals on integrated GPUs was retrieved.
- The exact Tokuyoshi–Kaplanyan formula (kernel width, clamping constants) was not re-read.

## 5. What makes surfaces read as "expensive": polish, clear coat and orange peel, stone depth, chatoyancy, glints, edge wear, smudges

### Takeaway
"Expensive" comes from several things together:
- layered specular: a sharp clear coat over a softer base with distinct roughness, plus a subtle orange peel visible only in reflections of straight light edges
- depth cues under the surface: parallax vein layers, wood-fiber highlights
- view-dependent effects: anisotropic chatoyancy, thin-film iridescence on nacre
- controlled sparkle: stable, anti-aliased glints for mica, granite and metallic-flake lacquer

Wear and smudges must be nearly invisible, in roughness only. Glint research has moved from Zirr–Kaplanyan (2016) to Chermain (2020–2021) to Deliot–Belcour (2023, no dictionary textures, real-time). A cheap hashed-cell glint is enough for the UI if it is LOD-faded.

### Cited Findings
- **Zirr & Kaplanyan (I3D 2016), "Real-time Rendering of Procedural Multiscale Materials".** A procedural, stochastic microstructure model for glinty surfaces (sparkling metallic paints and similar). It counts reflecting microfacets within the pixel footprint across scales using a biscale/multiscale NDF, so glints stay temporally stable and converge to the smooth BRDF at distance. No textures are needed. — [NVIDIA publication page](https://research.nvidia.com/publication/real-time-rendering-procedural-multiscale-materials); [PDF](https://research.nvidia.com/sites/default/files/pubs/2016-02_Real-time-Rendering-of/ZirrKaplanyan_MultiscaleI3D2016.pdf)
- **Chermain, Lucas, Sauvage, Dischler, Dachsbacher (I3D 2021 / PACMCGIT, DOI 10.1145/3451257), "Real-Time Geometric Glint Anti-Aliasing with Normal Map Filtering".** Combines a procedural glint BRDF with normal-map filtering, so glints on normal-mapped surfaces neither alias nor vanish. Builds on Chermain et al. 2020 ("Procedural Physically based BRDF for Real-Time Rendering of Glints", Pacific Graphics 2020), which used a precomputed dictionary of 1D distributions (verify). — [ICube PDF](https://publis.icube.unistra.fr/docs/15022/Chermain2021RealTime.pdf); [ICube record](https://publis.icube.unistra.fr/4-CLSD21); [Crossref](https://api.crossref.org/works/10.1145%2F3451257); [I3D 2021 papers list](https://www.realtimerendering.com/kesen/i3d2021Papers.htm)
- **Deliot & Belcour (EGSR 2023 / CGF 42(4)), "Real-Time Rendering of Glinty Appearances using Distributed Binomial Laws on Anisotropic Grids".** Removes the dictionary of earlier work by distributing binomial microfacet-count laws over anisotropic grids aligned to the pixel footprint. The result is stable, anti-aliased glints at low memory and real-time cost. — [arXiv 2306.05051](https://arxiv.org/pdf/2306.05051); [EG DL](https://diglib.eg.org/handle/10.1111/cgf14866)
- **Newer glint work, likely beyond the iGPU budget**
  - "Constant-Cost Spatio-Angular Prefiltering of Glinty Appearance Using Tensor Decomposition" (arXiv 2109.14807).
  - "Position-Normal Manifold for Efficient Glint Rendering on High-Resolution Normal Maps" (arXiv 2505.08985, 2025), aimed at high-resolution normal-map glints.
  - A 2024 "Real-time Image-based Lighting of Glints" paper also exists (review page only).

  — [arXiv 2109.14807](https://arxiv.org/pdf/2109.14807); [arXiv 2505.08985](https://arxiv.org/html/2505.08985v1); [review of IBL glints](https://www.themoonlight.io/review/real-time-image-based-lighting-of-glints)
- **Finished-wood chatoyancy.** The Marschner et al. 2005 sub-finish fiber highlight is the physical model for the shimmering "figure" of wood and the closest analogue for tiger's-eye and satin chatoyancy. — [Marschner SG05](https://www.cs.cornell.edu/~srm/publications/SG05-wood.html)
- **Woodworking reference.** A woodworking-press article on color-changing chatoyance in wood confirms the practitioner-side phenomenon. — [The Woodworker: Colour-changing chatoyance](https://www.thewoodworkermag.com/node/608885)
- **Clear coat, anisotropy, sheen and iridescence in the standard material models.** glTF PBR extensions (KHR_materials_clearcoat / anisotropy / iridescence / sheen) and three.js MeshPhysicalMaterial (clearcoat + clearcoatNormalMap for orange peel; anisotropy with direction; iridescence). Filament's clear coat is a second GGX lobe with fixed IOR 1.5. — [Khronos glTF PBR](https://www.khronos.org/gltf/pbr/); [three.js MeshPhysicalMaterial](https://threejs.org/docs/api/en/materials/MeshPhysicalMaterial.html); [Filament materials](https://google.github.io/filament/main/materials.html); [gltf-transform KHR_materials_anisotropy](https://gltf-transform.dev/modules/extensions/classes/KHRMaterialsAnisotropy)
- **Thin-film interference for nacre, anodized and heat-tinted metal rims.** Belcour & Barla 2017, closed-form and real-time. — [Unity blog](https://blog.unity.com/es/technology/a-practical-extension-to-microfacet-theory-for-the-modeling-of-varying-iridescence)

### Inferences
- **Cheap glint for an iGPU** (researcher's recipe; zero assets; about 30–60 ALU)
  - Grid in world space at flake density ρ (e.g. 2–8 cells/mm for mica or metallic flakes). Per cell: hash → isFlake (probability p), random flake normal n_c within a cone of half-angle θ around N.
  - glint = isFlake · pow(saturate(dot(n_c, H)), k) · intensity.
  - Fade the glint term out when cell size < ~1.5 px (use fwidth of the world position). Fold its energy back into the base specular by raising roughness slightly.
  - This is a non-physical approximation of the Zirr/Deliot behavior. Use Deliot–Belcour only if stability under camera motion becomes a visible problem.
- **Polish ladder per material**, so materials read distinct and "expensive" side by side:
  - polished stone: 0.03–0.08
  - lacquer coat: ≈0.01–0.03
  - satin-oiled walnut: 0.25–0.4 base under a 0.08–0.15 coat
  - polished metal rim: 0.05–0.1
  - brushed rim: anisotropic, αx ≈ 0.05 / αy ≈ 0.3
- **Edge wear** on tray rims: drive it with a curvature/edge mask (from the SDF of the rim profile or mesh curvature). Raise roughness and slightly brighten the metal at edges. Keep it under ~10% of the rim area. Never add color change on luxury items.
- **Fingerprints and smudges:** roughness only, at most ±0.03–0.08, with very low spatial frequency patches, visible only at grazing angles or in a highlight. If they are visible in diffuse light, the result reads dirty, not real.
- **Stone depth:** use the parallax deep-vein layer from §2 plus a slight darkening of veins at grazing angles. Real subsurface (diffusion profiles) is unnecessary at desk scale for marble and too costly for an iGPU.

### Gaps
- No measured millisecond costs of Zirr–Kaplanyan, Chermain 2021 or Deliot–Belcour on integrated GPUs or under WebGL2 were retrieved. The papers report desktop-GPU timings that were not re-read.
- Whether Deliot–Belcour released GLSL/WebGL code (vs Unity HLSL) was not verified.
- No authoritative source was found for edge-wear or fingerprint subtlety values. The numbers above are judgment.

## 6. Hyper-real vs photoreal: how luxury product renders "elevate" reality

### Takeaway
Luxury product visuals are not more physically accurate. They are more controlled:
- large, clean studio light sources that give long, gradient reflections on metal and lacquer
- black flags that define edges
- surfaces cleaner and more polished than real objects
- materials pushed toward their most characteristic look (deeper veins, richer wood figure, more saturated nacre)
- a tone mapper that keeps base colors faithful

In a real-time UI this translates into a curated environment map (softbox strips on a dark studio HDRI), physically layered materials with exaggerated but plausible parameters, and restraint with wear.

### Cited Findings
- **Lighting presets.** KeyShot, a standard product-visualization renderer, recommends lighting presets and studio HDRIs as the core of product and jewelry rendering. — [KeyShot: Using Lighting Presets](https://www.keyshot.com/blog/using-lighting-presets-in-keyshot); [KeyShot: 5 rendering goals](https://www.keyshot.com/blog/5-keyshot-3d-rendering-goals-to-ring-in-the-new-year/)
- **Watch lighting.** A watch-rendering lighting tutorial for KeyShot (luxury metal/glass product) covers studio light placement for controlled reflections. — [GrabCAD: KeyShot Lighting Tutorial, Realistic Watch Renders](https://cad.grabcad.com/tutorials/keyshot-lighting-tutorial-how-to-create-realistic-watch-renders)
- **Jewelry visualization.** Jewelry and luxury-goods visualization relies on dedicated studio HDRIs and lighting setups (DOSCH Design + KeyShot), and Rhino jewelry rendering guidance covers polished presentation. — [DOSCH Design: 3D in jewelry design](https://doschdesign.com/contentpage/3d-in-jewelry-design); [Novedge: Rhino jewelry rendering tips](https://novedge.com/blogs/design-news/rhino-3d-tip-rhino-jewelry-rendering-tips-for-polished-presentations)

### Inferences
These are the researcher's synthesis of product-viz practice; page contents not verified.

- **Environment is half of the material.** Polished marble, lacquer, metal rims and nacre are mostly specular, so they show their environment. A procedurally generated "studio" environment costs zero bytes and is fully controllable:
  - a dark gradient background
  - 2–3 large rectangular softbox strips with soft falloff
  - one warm key and one cool rim

  Prefilter it once into a small cubemap or octahedral map (e.g. 128–256² with GGX-prefiltered mips). This will raise perceived quality more than any texture upgrade. Area-light-shaped highlights (LTC area lights) are the real-time analogue of softboxes, if direct lights are used.
- **Push materials toward their archetype, within physical bounds:**
  - marble: whiter base, crisper and fewer but bolder primary veins, more depth layering
  - walnut: richer chocolate, with stronger fiber-highlight figure
  - nacre: higher iridescence factor and saturation
  - metal: cleaner anisotropy, with no grime
- **Tone mapping.** Prefer a hue-preserving, product-oriented tone mapper (e.g. Khronos "PBR Neutral", or AgX) over ACES filmic, which shifts saturated hues. The goal is that a deliberately chosen base color appears on screen as chosen. Khronos PBR Neutral was designed for commerce/product display (prior knowledge; verify).
- **Restraint rules:** wear and smudges only in roughness and below the threshold of conscious notice; shallow contrast in diffuse; drama reserved for specular. Pristine but subtly imperfect surfaces read as "more real than real".
- **Bake procedural materials once at a higher internal resolution** (e.g. 2048² for the bench and 512–1K for rims and trays). This allows richer, more octave-heavy recipes (3-level warps, multiple vein layers, Voronoi edges) than per-frame shading could afford on an iGPU. Supersample during the bake for free anti-aliasing. This is the single most important architectural decision for the "hyper-real" target under the bandwidth and iGPU constraints.

### Gaps
- No authoritative written source (brand style guide, academic paper) defining "elevated reality" or "hyper-real" product-render stylization was retrieved. The KeyShot, GrabCAD and DOSCH pages were confirmed by title only.
- Khronos PBR Neutral and AgX tone mapper documentation URLs were not search-confirmed this session.
- No user-perception studies on what reads as "expensive" in materials were found.
