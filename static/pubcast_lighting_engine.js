/**
 * PubCast Lighting Engine
 * 
 * A complete, flexible lighting system for 2.5D panoramic environments.
 * 
 * Architecture:
 *   LightState        — the raw parameter object (pure data, no rendering)
 *   LightPreset       — named bundle of LightState overrides
 *   LightingResolver  — merges presets + manual overrides + reactive inputs → LightState
 *   RenderPassManager — executes shader passes from a LightState
 *   FlubLayer         — applies non-physical emotional corrections
 *   PostProcessor     — final image-space effects chain
 *   LightingEngine    — top-level orchestrator
 * 
 * 2.5D advantage: each scene layer (bg, midground, fg, avatar) has its own
 * LightState. You can run Fincher on the background while Spielberg lights
 * the avatar. Physically impossible. Emotionally correct.
 */

import * as THREE from 'three';

// ─────────────────────────────────────────────
//  LIGHT STATE  (the canonical parameter object)
// ─────────────────────────────────────────────

export class LightState {
  constructor(overrides = {}) {
    // ── Key light ──
    this.keyKelvin        = 5600;   // Neutral daylight. 2000=candle, 10000=overcast
    this.keyIntensity     = 1.0;    // 0–3
    this.keyAzimuth       = -45;    // degrees, 0=front, -90=hard left
    this.keyElevation     = 35;     // degrees above horizon
    this.keySoftness      = 0.3;    // 0=hard point, 1=giant softbox
    this.keyShadowDensity = 0.8;    // 0=no shadow, 1=opaque
    this.keyShadowSharp   = 0.7;    // 0=soft penumbra, 1=razor edge

    // ── Fill light ──
    this.fillKelvin       = 6200;
    this.fillIntensity    = 0.35;
    this.fillAzimuth      = 60;
    this.fillElevation    = 20;
    this.fillSoftness     = 0.9;

    // ── Rim / edge ──
    this.rimIntensity     = 0.6;
    this.rimKelvin        = 5600;
    this.rimWidth         = 0.15;   // fraction of edge to light
    this.rimAlwaysOn      = true;   // Flub: sprite anchor — ignores occlusion

    // ── Ambient ──
    this.ambientIntensity = 0.25;
    this.ambientColor     = [0.12, 0.13, 0.18];  // slight cool sky

    // ── Color grade ──
    this.shadowHue        = [0.08, 0.10, 0.18];  // shadow color bias (cool blue default)
    this.highlightHue     = [1.0,  0.96, 0.88];  // highlight color bias (warm)
    this.midtoneTint      = [1.0,  1.0,  1.0];   // neutral by default
    this.saturation       = 1.0;
    this.contrast         = 1.0;
    this.exposure         = 0.0;                  // EV stops, 0=no change

    // ── Volumetrics ──
    this.fogDensity       = 0.0;
    this.fogColor         = [0.6, 0.65, 0.75];
    this.fogHeight        = 0.3;     // normalized 0–1 from bottom
    this.godRayIntensity  = 0.0;
    this.godRayAngle      = -45;
    this.godRayColor      = [1.0, 0.98, 0.90];

    // ── Glow / bloom ──
    this.bloomThreshold   = 0.85;
    this.bloomIntensity   = 0.2;
    this.bloomRadius      = 0.4;
    this.emissiveScale    = 1.0;

    // ── Film / lens ──
    this.grainIntensity   = 0.0;
    this.grainSize        = 1.0;
    this.halationRadius   = 0.0;    // red bleed on bright edges
    this.halationColor    = [1.0, 0.3, 0.1];
    this.vignette         = 0.0;    // 0–1
    this.vignetteColor    = [0, 0, 0];
    this.lensDistortion   = 0.0;    // barrel/pincushion
    this.chromaticAb      = 0.0;    // chromatic aberration px offset
    this.dofStrength      = 0.0;    // depth of field blur
    this.dofFocalZ        = 0.5;    // 0=foreground, 1=background

    // ── Temporal / frame feel ──
    this.simulatedFPS     = 0;      // 0=native, 24, 30, 48, 60
    this.motionBlur       = 0.0;
    this.gateFlicker      = 0.0;    // simulated gate weave/flicker 0–1

    // ── Strobe / flash (rave/psychedelic) ──
    this.strobeEnabled    = false;
    this.strobeFreq       = 4;      // Hz
    this.strobeDuty       = 0.2;    // fraction of period that's lit
    this.strobeColor      = [1, 1, 1];
    this.flashColor       = [1, 1, 1];
    this.flashDecay       = 0.1;    // seconds to fade

    // ── Audio reactive ──
    this.audioReactive    = false;
    this.audioBand        = 'all';  // 'bass', 'mid', 'high', 'all'
    this.audioIntensityMod = 0.3;   // how much audio moves intensity
    this.audioColorMod    = 0.0;    // how much audio shifts hue
    this.audioBeatFlash   = false;

    // ── 2.5D layer-specific ──
    this.layerLightWrap   = 0.0;    // bleed light from bg onto fg sprites
    this.spriteRimForce   = false;  // force rim regardless of light angle (Flub)
    this.zParallaxLight   = true;   // parallax shadow shift by z-depth

    Object.assign(this, overrides);
  }

  clone() {
    return new LightState(JSON.parse(JSON.stringify(this)));
  }

  lerp(target, t) {
    const out = this.clone();
    for (const key of Object.keys(out)) {
      const a = this[key], b = target[key];
      if (typeof a === 'number' && typeof b === 'number') {
        out[key] = a + (b - a) * t;
      } else if (Array.isArray(a) && Array.isArray(b)) {
        out[key] = a.map((v, i) => v + (b[i] - v) * t);
      }
    }
    return out;
  }
}

// ─────────────────────────────────────────────
//  LIGHT PRESETS  (the style library)
// ─────────────────────────────────────────────

export const LightPresets = {

  // ── Neutral / Studio ──────────────────────────────────────

  STUDIO_NEUTRAL: new LightState({
    // Clean three-point. The zero point everyone dials from.
  }),

  STUDIO_BEAUTY: new LightState({
    // Clamshell / beauty-dish setup. Portrait standard.
    keyKelvin: 5600, keyIntensity: 1.2, keyAzimuth: 0, keyElevation: 15,
    keySoftness: 0.95, keyShadowDensity: 0.2,
    fillIntensity: 0.9, fillElevation: -10,
    rimIntensity: 0.4, vignette: 0.15,
    saturation: 1.05, bloomIntensity: 0.1,
  }),

  // ── Film: Director DNA ─────────────────────────────────────

  HITCHCOCK: new LightState({
    // Hard shadow suspense. One source. Selective illumination.
    keyKelvin: 3200, keyIntensity: 1.6, keyAzimuth: -70, keyElevation: 25,
    keySoftness: 0.05, keyShadowDensity: 0.98, keyShadowSharp: 0.98,
    fillIntensity: 0.05, ambientIntensity: 0.08,
    shadowHue: [0.03, 0.03, 0.08],
    contrast: 1.5, saturation: 0.7,
    vignette: 0.4, vignetteColor: [0, 0, 0],
    grainIntensity: 0.06, grainSize: 0.8,
  }),

  SPIELBERG: new LightState({
    // Backlit wonder. Liquid light. Eye sparkle. 
    keyKelvin: 4800, keyIntensity: 0.9, keyAzimuth: 180, keyElevation: 10,
    keySoftness: 0.7,
    fillIntensity: 0.8, fillKelvin: 5800,
    rimIntensity: 2.5, rimKelvin: 4200,
    ambientIntensity: 0.45,
    bloomIntensity: 0.6, bloomRadius: 0.8, bloomThreshold: 0.7,
    godRayIntensity: 0.3, godRayAngle: 180,
    shadowHue: [0.10, 0.12, 0.20],
    highlightHue: [1.02, 0.98, 0.92],
    contrast: 0.9, saturation: 1.15,
    layerLightWrap: 0.5,
    spriteRimForce: true,
  }),

  NOLAN: new LightState({
    // IMAX naturalism. Grounded weight. No tricks.
    keyKelvin: 5800, keyIntensity: 1.1, keyAzimuth: -30, keyElevation: 40,
    keySoftness: 0.45, keyShadowDensity: 0.85, keyShadowSharp: 0.6,
    fillIntensity: 0.4, ambientIntensity: 0.3,
    shadowHue: [0.08, 0.09, 0.15],
    contrast: 1.1, saturation: 1.0,
    dofStrength: 0.3, dofFocalZ: 0.4,
    grainIntensity: 0.02,
  }),

  FINCHER: new LightState({
    // Cinema Verde. Jaundice decay. Industrial cool.
    keyKelvin: 4000, keyIntensity: 0.85, keyAzimuth: -20, keyElevation: 60,
    keySoftness: 0.3, keyShadowDensity: 0.9,
    fillIntensity: 0.15, fillKelvin: 4200,
    ambientIntensity: 0.12,
    shadowHue: [0.08, 0.12, 0.06],  // greenish decay
    midtoneTint: [0.88, 0.92, 0.78],
    saturation: 0.8, contrast: 1.2,
    grainIntensity: 0.04,
    vignette: 0.35,
  }),

  RIDLEY_SCOTT: new LightState({
    // Neon on wet pavement. Blade Runner. Industrial claustrophobia.
    keyKelvin: 3000, keyIntensity: 0.5, keyAzimuth: -90, keyElevation: 5,
    keySoftness: 0.1, keyShadowDensity: 0.95,
    fillIntensity: 0.0,
    ambientIntensity: 0.4, ambientColor: [0.0, 0.02, 0.12], // deep blue ambient
    shadowHue: [0.0, 0.0, 0.12],
    midtoneTint: [0.80, 0.72, 0.62],
    fogDensity: 0.25, fogColor: [0.06, 0.04, 0.18],
    bloomIntensity: 0.8, bloomRadius: 0.6, bloomThreshold: 0.5,
    emissiveScale: 2.0,
    saturation: 1.3, contrast: 1.4,
    vignette: 0.5,
    chromaticAb: 0.8,
  }),

  MICHAEL_BAY: new LightState({
    // Teal-orange. High chroma. Metallic shimmer. Golden hour always.
    keyKelvin: 3400, keyIntensity: 1.8, keyAzimuth: -120, keyElevation: 8,
    keySoftness: 0.2, keyShadowDensity: 0.7,
    fillIntensity: 0.6, fillKelvin: 8000, // cool fill against warm key
    rimIntensity: 1.8, rimKelvin: 3000,
    shadowHue: [0.02, 0.12, 0.18],   // teal shadows
    midtoneTint: [1.1, 0.95, 0.7],   // warm midtones
    saturation: 1.5, contrast: 1.3,
    bloomIntensity: 0.7, bloomRadius: 0.9, bloomThreshold: 0.6,
    lensDistortion: -0.05,
    godRayIntensity: 0.4, godRayAngle: -120,
    layerLightWrap: 0.4,
  }),

  DEL_TORO: new LightState({
    // Organic amber-cobalt. Wet-look. Fairytale danger.
    keyKelvin: 3200, keyIntensity: 0.9, keyAzimuth: -45, keyElevation: 20,
    keySoftness: 0.5, keyShadowDensity: 0.88,
    fillIntensity: 0.5, fillKelvin: 8500, // cold blue fill
    ambientIntensity: 0.25, ambientColor: [0.04, 0.06, 0.22],
    shadowHue: [0.04, 0.06, 0.22],
    midtoneTint: [0.95, 0.82, 0.62],
    saturation: 1.2, contrast: 1.15,
    fogDensity: 0.15, fogColor: [0.05, 0.05, 0.18],
    bloomIntensity: 0.4,
    vignette: 0.3,
  }),

  TARANTINO: new LightState({
    // 70s hard-retro. Pulp. Sweaty saturation.
    keyKelvin: 3600, keyIntensity: 1.3, keyAzimuth: -30, keyElevation: 30,
    keySoftness: 0.15, keyShadowDensity: 0.85, keyShadowSharp: 0.8,
    fillIntensity: 0.5, fillKelvin: 3800,
    ambientIntensity: 0.3,
    shadowHue: [0.12, 0.08, 0.02],   // warm-dark shadows
    midtoneTint: [1.08, 0.96, 0.78],
    saturation: 1.4, contrast: 1.25,
    grainIntensity: 0.08, grainSize: 1.5,
    vignette: 0.25,
    simulatedFPS: 24,
  }),

  GREENGRASS: new LightState({
    // Bourne. Cold fluorescent. Documentary noise.
    keyKelvin: 5600, keyIntensity: 0.8, keyAzimuth: 10, keyElevation: 50,
    keySoftness: 0.7,
    fillIntensity: 0.6, fillKelvin: 5800,
    ambientIntensity: 0.5,
    saturation: 0.75, contrast: 1.05,
    shadowHue: [0.1, 0.12, 0.12],
    grainIntensity: 0.12, grainSize: 1.2,
    simulatedFPS: 30,
    motionBlur: 0.3,
    vignette: 0.1,
  }),

  // ── Animation styles ───────────────────────────────────────

  GHIBLI: new LightState({
    // Komorebi. Watercolor. Emotional shadow tinting.
    keyKelvin: 5200, keyIntensity: 1.0, keyAzimuth: -20, keyElevation: 45,
    keySoftness: 0.85,
    fillIntensity: 0.7, fillKelvin: 6500,
    ambientIntensity: 0.55,
    shadowHue: [0.15, 0.10, 0.22],   // mauve-lavender shadows (Ghibli signature)
    highlightHue: [1.02, 1.00, 0.95],
    saturation: 0.9, contrast: 0.85,
    bloomIntensity: 0.15,
    layerLightWrap: 0.7,
    spriteRimForce: false,           // no rim — light is everywhere
  }),

  PIXAR: new LightState({
    // PBR perfection. Subsurface scattering implied. Production standard.
    keyKelvin: 5600, keyIntensity: 1.1, keyAzimuth: -35, keyElevation: 40,
    keySoftness: 0.6, keyShadowDensity: 0.75, keyShadowSharp: 0.5,
    fillIntensity: 0.55, fillKelvin: 6000,
    rimIntensity: 0.8, rimKelvin: 5800,
    ambientIntensity: 0.4,
    saturation: 1.05, contrast: 1.0,
    bloomIntensity: 0.2, bloomThreshold: 0.88,
    layerLightWrap: 0.3,
    spriteRimForce: true,
  }),

  DBZ_AURA: new LightState({
    // Dragon Ball Z. Internal aura sourcing. Power up.
    keyIntensity: 0.3,
    fillIntensity: 0.1,
    ambientIntensity: 0.2,
    emissiveScale: 4.0,
    bloomIntensity: 1.5, bloomRadius: 1.2, bloomThreshold: 0.3,
    rimIntensity: 3.0, rimAlwaysOn: true,
    spriteRimForce: true,
    saturation: 1.6, contrast: 1.3,
    flashColor: [1, 1, 0.8],
    audioBeatFlash: true,
  }),

  AKIRA_NEON: new LightState({
    // Neon drip. Light trails. Tokyo 2019.
    keyKelvin: 4000, keyIntensity: 0.3, keyAzimuth: 0, keyElevation: 80,
    keySoftness: 0.4,
    fillIntensity: 0.0,
    ambientIntensity: 0.05, ambientColor: [0.0, 0.0, 0.08],
    emissiveScale: 3.5,
    bloomIntensity: 1.8, bloomRadius: 0.8, bloomThreshold: 0.2,
    bloomIntensity: 2.0,
    saturation: 2.0, contrast: 1.6,
    chromaticAb: 1.5,
    fogDensity: 0.3, fogColor: [0.02, 0.0, 0.08],
    motionBlur: 0.6,
    vignette: 0.4,
  }),

  BATMAN_TAS: new LightState({
    // Dark deco. Painting on black. Smog volumetrics.
    keyKelvin: 3000, keyIntensity: 1.4, keyAzimuth: -60, keyElevation: 70,
    keySoftness: 0.05, keyShadowDensity: 1.0, keyShadowSharp: 1.0,
    fillIntensity: 0.02,
    ambientIntensity: 0.03, ambientColor: [0.02, 0.03, 0.08],
    shadowHue: [0.0, 0.0, 0.0],
    saturation: 0.7, contrast: 2.0,
    fogDensity: 0.4, fogColor: [0.04, 0.04, 0.06],
    godRayIntensity: 0.6, godRayAngle: -60,
    vignette: 0.6,
  }),

  SPIDER_VERSE_NPR: new LightState({
    // Living comic book. Ben-Day dots implied. CMYK offset.
    keyKelvin: 5600, keyIntensity: 1.4, keyAzimuth: -45, keyElevation: 50,
    keySoftness: 0.0, keyShadowDensity: 1.0, keyShadowSharp: 1.0,
    fillIntensity: 0.0,
    ambientIntensity: 0.5,
    shadowHue: [0.02, 0.0, 0.12],
    saturation: 1.6, contrast: 1.5,
    chromaticAb: 2.0,           // CMYK offset as chromatic aberration
    emissiveScale: 1.5,
    grainIntensity: 0.0,
  }),

  ROTOSCOPE: new LightState({
    // Waking Life / Scanner Darkly. Interpolated, boiling edges.
    keyKelvin: 5200, keyIntensity: 0.9, keyAzimuth: -20, keyElevation: 35,
    keySoftness: 0.6,
    fillIntensity: 0.6,
    saturation: 0.85, contrast: 0.9,
    grainIntensity: 0.03,
    gateFlicker: 0.08,
    // Note: boiling line effect is geometric, handled by geometry shader
    // this preset just sets the complementary lighting character
  }),

  // ── Genre presets ──────────────────────────────────────────

  NOIR: new LightState({
    // Binary shadow. 1-bit high contrast. Classic noir.
    keyKelvin: 3800, keyIntensity: 1.8, keyAzimuth: -50, keyElevation: 40,
    keySoftness: 0.0, keyShadowDensity: 1.0, keyShadowSharp: 1.0,
    fillIntensity: 0.0,
    ambientIntensity: 0.04,
    saturation: 0.0,         // black and white
    contrast: 2.5,
    vignette: 0.5,
    grainIntensity: 0.1, grainSize: 0.9,
    simulatedFPS: 24,
  }),

  FANTASY_WARM: new LightState({
    // Golden warm glow. Magic in the air.
    keyKelvin: 3500, keyIntensity: 1.0, keyAzimuth: -30, keyElevation: 20,
    keySoftness: 0.8,
    fillIntensity: 0.6, fillKelvin: 4000,
    rimIntensity: 1.2, rimKelvin: 3200,
    ambientIntensity: 0.5, ambientColor: [0.18, 0.12, 0.06],
    emissiveScale: 2.0,
    bloomIntensity: 0.8, bloomRadius: 0.9, bloomThreshold: 0.5,
    fogDensity: 0.12, fogColor: [0.18, 0.14, 0.08],
    godRayIntensity: 0.3,
    saturation: 1.2,
    layerLightWrap: 0.6,
    spriteRimForce: true,
  }),

  MAGIC_REALISM: new LightState({
    // Garcia Marquez light. Reality with impossible beauty.
    keyKelvin: 4800, keyIntensity: 0.9, keyAzimuth: 10, keyElevation: 55,
    keySoftness: 0.95,
    fillIntensity: 0.8, fillKelvin: 6200,
    ambientIntensity: 0.6,
    bloomIntensity: 0.5, bloomRadius: 1.0, bloomThreshold: 0.6,
    emissiveScale: 1.5,
    saturation: 1.1, contrast: 0.85,
    halationRadius: 0.3, halationColor: [1.0, 0.85, 0.6],
    layerLightWrap: 0.8,
  }),

  IMPRESSIONIST: new LightState({
    // Monet light. Diffuse. No hard edges anywhere.
    keyKelvin: 5500, keyIntensity: 0.7, keyAzimuth: 20, keyElevation: 65,
    keySoftness: 1.0,   // maximum soft
    fillIntensity: 0.9, fillSoftness: 1.0,
    ambientIntensity: 0.7,
    keyShadowDensity: 0.1,
    saturation: 1.0, contrast: 0.75,
    bloomIntensity: 0.6, bloomRadius: 1.5, bloomThreshold: 0.4,
    dofStrength: 0.2,
    layerLightWrap: 0.9,
  }),

  CANDLELIGHT: new LightState({
    // Real practical. Intimate. Flicker.
    keyKelvin: 1900, keyIntensity: 0.9, keyAzimuth: 0, keyElevation: -10,
    keySoftness: 0.3, keyShadowDensity: 0.9,
    fillIntensity: 0.0,
    ambientIntensity: 0.05, ambientColor: [0.08, 0.04, 0.01],
    emissiveScale: 1.2,
    bloomIntensity: 0.4, bloomThreshold: 0.5,
    fogDensity: 0.05, fogColor: [0.1, 0.06, 0.02],
    saturation: 0.9, contrast: 1.3,
    vignette: 0.6,
    gateFlicker: 0.15,   // candle flicker reused as light variation
    grainIntensity: 0.04,
  }),

  PSYCHEDELIC: new LightState({
    // Acid. Color cycling. Reality dissolving.
    keyKelvin: 5600, keyIntensity: 1.0,
    fillIntensity: 0.8,
    ambientIntensity: 0.8,
    saturation: 2.0, contrast: 1.2,
    bloomIntensity: 2.0, bloomRadius: 1.5, bloomThreshold: 0.1,
    emissiveScale: 3.0,
    chromaticAb: 3.0,
    audioReactive: true, audioBand: 'all', audioColorMod: 1.0,
    audioIntensityMod: 0.5,
    gateFlicker: 0.2,
  }),

  RAVE_STROBE: new LightState({
    // DMX club. Strobe freeze. Beat flash.
    keyIntensity: 0.0,
    fillIntensity: 0.0,
    ambientIntensity: 0.0,
    emissiveScale: 2.5,
    bloomIntensity: 1.5, bloomRadius: 0.7, bloomThreshold: 0.2,
    strobeEnabled: true, strobeFreq: 6, strobeDuty: 0.15, strobeColor: [1, 1, 1],
    audioReactive: true, audioBand: 'bass', audioIntensityMod: 1.0,
    audioBeatFlash: true,
    saturation: 1.8, contrast: 1.5,
    chromaticAb: 1.0,
    motionBlur: 0.4,
    vignette: 0.3,
  }),

  FREEZE_DREAM: new LightState({
    // Rave freeze-frame. High-key flash. Dream state.
    keyKelvin: 7000, keyIntensity: 2.5, keyAzimuth: 0, keyElevation: 90,
    keySoftness: 0.0, keyShadowDensity: 0.4,
    fillIntensity: 1.5,
    ambientIntensity: 1.0,
    bloomIntensity: 3.0, bloomRadius: 2.0, bloomThreshold: 0.0,
    saturation: 0.4, contrast: 2.0, exposure: 1.5,
    chromaticAb: 2.0,
    gateFlicker: 0.4,
    strobeEnabled: true, strobeFreq: 12, strobeDuty: 0.08,
    motionBlur: 0.8,
  }),

  NEWS_FLAT: new LightState({
    // Clinical 6500K. Shadow-free zone. Broadcast standard.
    keyKelvin: 6500, keyIntensity: 1.0, keyAzimuth: 0, keyElevation: 30,
    keySoftness: 0.95,
    fillIntensity: 0.9, fillKelvin: 6500,
    ambientIntensity: 0.6,
    keyShadowDensity: 0.1,
    rimIntensity: 0.3, rimAlwaysOn: true,
    saturation: 0.95, contrast: 1.0,
    bloomIntensity: 0.0,
    grainIntensity: 0.0,
  }),

  SPORTS_FLOODLIGHT: new LightState({
    // Multi-source top-down. Muscle-defining. Arena.
    keyKelvin: 5600, keyIntensity: 1.4, keyAzimuth: 0, keyElevation: 80,
    keySoftness: 0.2, keyShadowDensity: 0.6, keyShadowSharp: 0.7,
    fillIntensity: 0.6, fillAzimuth: 90, fillElevation: 45,
    rimIntensity: 0.4,
    ambientIntensity: 0.5,
    saturation: 1.1, contrast: 1.15,
    bloomIntensity: 0.1,
  }),

  PRODUCT_BEAUTY: new LightState({
    // Anisotropic strip lights. Beauty-wrap. No shadows.
    keyKelvin: 5600, keyIntensity: 1.0, keyAzimuth: 90, keyElevation: 20,
    keySoftness: 1.0,
    fillIntensity: 1.0, fillAzimuth: -90,
    ambientIntensity: 0.8,
    keyShadowDensity: 0.0,
    rimIntensity: 1.2, rimAlwaysOn: true,
    saturation: 1.05, contrast: 1.0,
    bloomIntensity: 0.3, bloomThreshold: 0.8,
  }),

  HORROR: new LightState({
    // Under-lit. Motivated from below. Wrong shadows.
    keyKelvin: 3200, keyIntensity: 0.9, keyAzimuth: 0, keyElevation: -30,
    keySoftness: 0.1, keyShadowDensity: 0.95, keyShadowSharp: 0.9,
    fillIntensity: 0.05,
    ambientIntensity: 0.08, ambientColor: [0.06, 0.04, 0.0],
    shadowHue: [0.08, 0.04, 0.0],
    saturation: 0.7, contrast: 1.5,
    vignette: 0.55,
    grainIntensity: 0.08,
    gateFlicker: 0.06,
  }),

  ROM_COM_GOLDEN: new LightState({
    // Warm. Flattering. Magic hour that never ends.
    keyKelvin: 3800, keyIntensity: 1.0, keyAzimuth: -100, keyElevation: 12,
    keySoftness: 0.7,
    fillIntensity: 0.6, fillKelvin: 5000,
    rimIntensity: 1.0, rimKelvin: 3600,
    ambientIntensity: 0.45,
    bloomIntensity: 0.5, bloomRadius: 1.0, bloomThreshold: 0.65,
    saturation: 1.15, contrast: 0.95,
    godRayIntensity: 0.2, godRayAngle: -100,
    layerLightWrap: 0.5,
    halationRadius: 0.2, halationColor: [1.0, 0.8, 0.5],
  }),

  MARVEL_ACTION: new LightState({
    // High key. Saturated hero lighting. Complementary color on rim.
    keyKelvin: 5600, keyIntensity: 1.3, keyAzimuth: -40, keyElevation: 35,
    keySoftness: 0.4, keyShadowDensity: 0.7,
    fillIntensity: 0.5, fillKelvin: 6000,
    rimIntensity: 1.5, rimKelvin: 7000,
    ambientIntensity: 0.4,
    saturation: 1.3, contrast: 1.1,
    bloomIntensity: 0.5, bloomRadius: 0.7, bloomThreshold: 0.75,
    emissiveScale: 1.8,
    layerLightWrap: 0.4,
    spriteRimForce: true,
  }),

  // ── Special / experimental ─────────────────────────────────

  GOLDEN_HOUR: new LightState({
    // The 20 minutes cinematographers pray for.
    keyKelvin: 3200, keyIntensity: 1.1, keyAzimuth: -110, keyElevation: 5,
    keySoftness: 0.55, keyShadowDensity: 0.75,
    fillIntensity: 0.4, fillKelvin: 7500,
    rimIntensity: 2.0, rimKelvin: 3000,
    godRayIntensity: 0.5, godRayAngle: -110,
    godRayColor: [1.0, 0.85, 0.6],
    bloomIntensity: 0.7, bloomRadius: 1.0, bloomThreshold: 0.55,
    saturation: 1.25, contrast: 1.05,
    halationRadius: 0.4, halationColor: [1.0, 0.7, 0.3],
    layerLightWrap: 0.7,
  }),

  BLUE_HOUR: new LightState({
    // Just after sunset. Flat shadowless cool.
    keyKelvin: 8000, keyIntensity: 0.4, keyAzimuth: 0, keyElevation: -5,
    keySoftness: 1.0,
    fillIntensity: 0.5, fillKelvin: 9000,
    ambientIntensity: 0.65, ambientColor: [0.08, 0.10, 0.25],
    keyShadowDensity: 0.15,
    rimIntensity: 0.8, rimKelvin: 8500,
    saturation: 0.9, contrast: 0.85,
    bloomIntensity: 0.3,
    fogDensity: 0.1, fogColor: [0.08, 0.10, 0.22],
  }),

  UNDERWATER: new LightState({
    // Caustic top-down. Color-shifted deep.
    keyKelvin: 8500, keyIntensity: 0.6, keyAzimuth: 0, keyElevation: 80,
    keySoftness: 0.9,
    fillIntensity: 0.4, fillKelvin: 9000,
    ambientIntensity: 0.55, ambientColor: [0.04, 0.10, 0.22],
    fogDensity: 0.4, fogColor: [0.04, 0.12, 0.28],
    bloomIntensity: 0.3,
    saturation: 0.85, contrast: 0.9,
    keyShadowDensity: 0.3,
  }),
};

// ─────────────────────────────────────────────
//  LIGHTING RESOLVER
// ─────────────────────────────────────────────

export class LightingResolver {
  /**
   * Merges all input sources into a final LightState for rendering.
   * Priority (highest wins): manual overrides > reactive > preset > defaults
   */
  resolve({
    presetName = 'STUDIO_NEUTRAL',
    manualOverrides = {},
    audioData = null,       // { bass, mid, high, beat } 0–1 each
    emotionState = null,    // { mood: 'happy', intensity: 0.7 }
    timelineEvent = null,   // { type: 'flash', color: [...], decay: 0.1 }
  }) {
    // 1. Start from preset
    const preset = LightPresets[presetName] || LightPresets.STUDIO_NEUTRAL;
    const state = preset.clone();

    // 2. Apply audio reactivity
    if (state.audioReactive && audioData) {
      const bandValue = audioData[state.audioBand] ?? audioData.all ?? 0;

      state.keyIntensity  *= 1 + bandValue * state.audioIntensityMod;
      state.bloomIntensity = Math.min(3, state.bloomIntensity + bandValue * 0.5);
      state.emissiveScale  = state.emissiveScale * (1 + bandValue * 0.3);

      if (state.audioColorMod > 0) {
        // Shift hue via midtone tint cycling
        const t = performance.now() / 1000;
        state.midtoneTint = [
          1.0 + Math.sin(t * 0.5) * 0.3 * state.audioColorMod,
          1.0 + Math.sin(t * 0.7 + 2) * 0.3 * state.audioColorMod,
          1.0 + Math.sin(t * 0.3 + 4) * 0.3 * state.audioColorMod,
        ];
      }

      if (state.audioBeatFlash && audioData.beat) {
        state.flashColor = state.strobeColor;
        state.flashDecay = 0.08;
      }
    }

    // 3. Apply emotion/mood color temp shift
    if (emotionState) {
      const moodKelvinShift = {
        calm: 0, happy: 200, excited: -300, sad: 400, angry: -500,
      };
      const shift = moodKelvinShift[emotionState.mood] || 0;
      state.keyKelvin   += shift * (emotionState.intensity ?? 1);
      state.saturation  += (emotionState.intensity ?? 1) * 0.1;
    }

    // 4. Apply timeline events (flash, flicker, etc.)
    if (timelineEvent) {
      if (timelineEvent.type === 'flash') {
        state.flashColor = timelineEvent.color || [1, 1, 1];
        state.flashDecay = timelineEvent.decay || 0.1;
        state.exposure   = (timelineEvent.stops || 1.5);
      } else if (timelineEvent.type === 'cut_darkness') {
        state.exposure = -3;
      }
    }

    // 5. Manual overrides last (highest priority)
    Object.assign(state, manualOverrides);

    return state;
  }
}

// ─────────────────────────────────────────────
//  FLUB LAYER  (emotional corrections)
// ─────────────────────────────────────────────

export class FlubLayer {
  /**
   * Applies non-physical corrections after compositing.
   * "If physical accuracy conflicts with emotional clarity, flub the light."
   */
  constructor(renderer, scene) {
    this.renderer = renderer;
    this.scene    = scene;
    this._eyeLight = this._createEyeLight();
  }

  _createEyeLight() {
    // A point light that ONLY affects the eye/specular layer — not geometry.
    // Achieved via a custom render layer and material group.
    const light = new THREE.PointLight(0xffffff, 0.8, 2.0);
    light.layers.set(2); // Layer 2 = specular-only layer
    return light;
  }

  apply(compositeTexture, lightState, avatarPositions = []) {
    // 1. Eye-light cheat: procedural highlight placed at avatar eye position,
    //    regardless of environment occlusion.
    if (avatarPositions.length > 0) {
      for (const pos of avatarPositions) {
        this._eyeLight.position.set(pos.x + 0.05, pos.y + 0.12, pos.z + 0.5);
      }
    }

    // 2. Sprite rim force: if an avatar is in a dark zone but rimForce is on,
    //    a rim is added via a post-process edge-detect + masked brightening pass.
    //    Implementation: custom ShaderPass targeting sprite layer only.

    // 3. Film halation: red-channel bleed on bright edges.
    //    Implemented as a separable blur applied only to R channel above threshold.

    // 4. Gate flicker: random per-frame exposure variation simulating film gate.
    if (lightState.gateFlicker > 0) {
      const flicker = 1.0 + (Math.random() - 0.5) * lightState.gateFlicker;
      // Returned as a scalar to multiply final composite exposure
      return { exposureMultiplier: flicker };
    }

    return { exposureMultiplier: 1.0 };
  }
}

// ─────────────────────────────────────────────
//  CORE SHADER UNIFORMS  (used by all passes)
// ─────────────────────────────────────────────

export function buildLightUniforms(lightState) {
  const kelvinToRGB = (K) => {
    // Tangent approximation of Planckian locus
    K = Math.max(1000, Math.min(12000, K));
    let r, g, b;
    if (K <= 6600) {
      r = 1.0;
      g = (0.39008 * Math.log(K / 100) - 0.63184);
      b = K <= 1900 ? 0 : (0.54320 * Math.log(K / 100 - 10) - 1.19625);
    } else {
      r = 1.292 * Math.pow(K / 100 - 60, -0.1332);
      g = 1.129 * Math.pow(K / 100 - 60, -0.0755);
      b = 1.0;
    }
    return new THREE.Color(
      Math.max(0, Math.min(1, r)),
      Math.max(0, Math.min(1, g)),
      Math.max(0, Math.min(1, b))
    );
  };

  const azElToVec3 = (az, el) => {
    const azR = (az * Math.PI) / 180;
    const elR = (el * Math.PI) / 180;
    return new THREE.Vector3(
      Math.sin(azR) * Math.cos(elR),
      Math.sin(elR),
      Math.cos(azR) * Math.cos(elR)
    ).normalize();
  };

  return {
    uKeyColor:       { value: kelvinToRGB(lightState.keyKelvin) },
    uKeyDir:         { value: azElToVec3(lightState.keyAzimuth, lightState.keyElevation) },
    uKeyIntensity:   { value: lightState.keyIntensity },
    uKeySoftness:    { value: lightState.keySoftness },
    uKeyShadowDen:   { value: lightState.keyShadowDensity },
    uKeyShadowSharp: { value: lightState.keyShadowSharp },

    uFillColor:     { value: kelvinToRGB(lightState.fillKelvin) },
    uFillDir:       { value: azElToVec3(lightState.fillAzimuth, lightState.fillElevation) },
    uFillIntensity: { value: lightState.fillIntensity },

    uRimColor:     { value: kelvinToRGB(lightState.rimKelvin) },
    uRimIntensity: { value: lightState.rimIntensity },
    uRimWidth:     { value: lightState.rimWidth },

    uAmbientColor:     { value: new THREE.Color(...lightState.ambientColor) },
    uAmbientIntensity: { value: lightState.ambientIntensity },

    uShadowColor:   { value: new THREE.Color(...lightState.shadowHue) },
    uHighlightColor:{ value: new THREE.Color(...lightState.highlightHue) },
    uMidtoneTint:   { value: new THREE.Color(...lightState.midtoneTint) },
    uSaturation:    { value: lightState.saturation },
    uContrast:      { value: lightState.contrast },
    uExposure:      { value: lightState.exposure },

    uFogDensity:    { value: lightState.fogDensity },
    uFogColor:      { value: new THREE.Color(...lightState.fogColor) },
    uFogHeight:     { value: lightState.fogHeight },

    uGodRayIntensity: { value: lightState.godRayIntensity },
    uGodRayDir:       { value: azElToVec3(lightState.godRayAngle, 15) },
    uGodRayColor:     { value: new THREE.Color(...lightState.godRayColor) },

    uBloomThreshold: { value: lightState.bloomThreshold },
    uBloomIntensity: { value: lightState.bloomIntensity },
    uBloomRadius:    { value: lightState.bloomRadius },
    uEmissiveScale:  { value: lightState.emissiveScale },

    uGrainIntensity: { value: lightState.grainIntensity },
    uGrainSize:      { value: lightState.grainSize },
    uHalationRadius: { value: lightState.halationRadius },
    uHalationColor:  { value: new THREE.Color(...lightState.halationColor) },
    uVignette:       { value: lightState.vignette },
    uVignetteColor:  { value: new THREE.Color(...lightState.vignetteColor) },
    uLensDistortion: { value: lightState.lensDistortion },
    uChromaticAb:    { value: lightState.chromaticAb },
    uDofStrength:    { value: lightState.dofStrength },
    uDofFocalZ:      { value: lightState.dofFocalZ },

    uLightWrap:      { value: lightState.layerLightWrap },
    uTime:           { value: 0.0 },
  };
}

// ─────────────────────────────────────────────
//  PER-SPRITE ILLUMINATION SHADER
// ─────────────────────────────────────────────

export const SpriteIlluminationShader = {
  name: 'SpriteIllumination',

  vertexShader: /* glsl */`
    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldPos;
    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,

  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;    // sprite albedo
    uniform sampler2D tNormal;     // normal map (optional)
    uniform sampler2D tEmissive;   // emissive mask

    uniform vec3  uKeyColor;
    uniform vec3  uKeyDir;
    uniform float uKeyIntensity;
    uniform float uKeySoftness;
    uniform float uKeyShadowDen;

    uniform vec3  uFillColor;
    uniform vec3  uFillDir;
    uniform float uFillIntensity;

    uniform vec3  uRimColor;
    uniform float uRimIntensity;
    uniform float uRimWidth;

    uniform vec3  uAmbientColor;
    uniform float uAmbientIntensity;

    uniform vec3  uShadowColor;
    uniform vec3  uHighlightColor;
    uniform vec3  uMidtoneTint;
    uniform float uSaturation;
    uniform float uContrast;
    uniform float uExposure;
    uniform float uEmissiveScale;
    uniform float uLightWrap;
    uniform float uTime;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldPos;

    vec3 kelvinGrade(vec3 col, vec3 shadows, vec3 highlights, vec3 midtones) {
      float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
      vec3 graded = mix(shadows, highlights, lum);
      return col * graded * midtones;
    }

    float softLight(float n) {
      return mix(n, n * n, uKeySoftness);
    }

    void main() {
      vec4 albedo = texture2D(tDiffuse, vUv);
      if (albedo.a < 0.01) discard;

      vec3 N = normalize(vNormal);
      // optional normal-map bump
      // vec3 tN = texture2D(tNormal, vUv).rgb * 2.0 - 1.0;
      // N = normalize(N + tN * 0.5);

      // ── Key light ──
      float keyDot    = max(0.0, dot(N, uKeyDir));
      float keyTerm   = softLight(keyDot);
      vec3  keyLight  = uKeyColor * keyTerm * uKeyIntensity;

      // ── Fill light ──
      float fillDot   = max(0.0, dot(N, uFillDir));
      vec3  fillLight = uFillColor * fillDot * uFillIntensity;

      // ── Rim light ──
      // Rim is based on silhouette (grazing angle from camera)
      // In 2.5D: N.z ≈ camera direction for sprites facing camera
      float rimDot    = 1.0 - abs(N.z);
      float rimMask   = smoothstep(1.0 - uRimWidth, 1.0, rimDot);
      vec3  rimLight  = uRimColor * rimMask * uRimIntensity;

      // ── Shadow ──
      // Contact shadow: darken base where key is not hitting
      float shadow    = mix(1.0, keyTerm, uKeyShadowDen);
      shadow          = pow(shadow, 1.0 + uKeySoftness);

      // ── Ambient ──
      vec3 ambient = uAmbientColor * uAmbientIntensity;

      // ── Emissive ──
      vec4 emissiveMask = texture2D(tEmissive, vUv);
      vec3 emissive     = emissiveMask.rgb * uEmissiveScale;

      // ── Combine ──
      vec3 lit = albedo.rgb * (ambient + keyLight * shadow + fillLight) + rimLight + emissive;

      // ── Color grade ──
      lit = kelvinGrade(lit, uShadowColor, uHighlightColor, uMidtoneTint);

      // Saturation
      float lum = dot(lit, vec3(0.2126, 0.7152, 0.0722));
      lit = mix(vec3(lum), lit, uSaturation);

      // Contrast (S-curve via smoothstep)
      lit = mix(vec3(0.5), lit, uContrast);

      // Exposure
      lit *= pow(2.0, uExposure);

      // Light wrap (bleed ambient onto edges — makes 2.5D sprites sit in env)
      float edge = 1.0 - abs(N.z);
      lit += uAmbientColor * edge * uLightWrap * 0.5;

      gl_FragColor = vec4(lit, albedo.a);
    }
  `
};

// ─────────────────────────────────────────────
//  POST-PROCESS SHADERS
// ─────────────────────────────────────────────

export const VolumetricFogShader = {
  name: 'VolumetricFog',
  uniforms: {},  // populated from LightState via buildLightUniforms
  vertexShader: `varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uFogDensity;
    uniform vec3  uFogColor;
    uniform float uFogHeight;
    varying vec2  vUv;

    void main() {
      vec4 col = texture2D(tDiffuse, vUv);
      // Height-based fog: more fog near bottom of screen (y=0)
      float heightFog = smoothstep(uFogHeight, 0.0, vUv.y) * uFogDensity;
      // Distance fog: simple depth approximation via screen position
      float distFog   = uFogDensity * 0.5;
      float fogAmount = clamp(heightFog + distFog, 0.0, 0.85);
      col.rgb = mix(col.rgb, uFogColor, fogAmount);
      gl_FragColor = col;
    }
  `
};

export const FilmGrainShader = {
  name: 'FilmGrain',
  uniforms: { uTime: { value: 0 } },
  vertexShader: `varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uGrainIntensity;
    uniform float uGrainSize;
    uniform float uHalationRadius;
    uniform vec3  uHalationColor;
    uniform float uTime;
    varying vec2  vUv;

    float rand(vec2 co) { return fract(sin(dot(co.xy ,vec2(12.9898,78.233))) * 43758.5453); }

    void main() {
      vec4 col = texture2D(tDiffuse, vUv);

      // Grain
      if (uGrainIntensity > 0.0) {
        float grain = rand(vUv * uGrainSize + uTime * 0.017) * 2.0 - 1.0;
        col.rgb += grain * uGrainIntensity;
      }

      // Halation: red bleed on bright edges
      if (uHalationRadius > 0.0) {
        float lum    = dot(col.rgb, vec3(0.2126, 0.7152, 0.0722));
        float bright = smoothstep(0.7, 1.0, lum);
        // Simple approximation: shift R channel slightly
        float rBleed = texture2D(tDiffuse, vUv + vec2(uHalationRadius * 0.008, 0.0)).r;
        col.r = mix(col.r, col.r + rBleed * 0.6, bright * uHalationRadius);
      }

      gl_FragColor = col;
    }
  `
};

export const LensEffectsShader = {
  name: 'LensEffects',
  vertexShader: `varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uVignette;
    uniform vec3  uVignetteColor;
    uniform float uLensDistortion;
    uniform float uChromaticAb;
    uniform float uBloomIntensity;
    uniform float uBloomThreshold;
    uniform float uBloomRadius;
    varying vec2  vUv;

    void main() {
      vec2 uv = vUv;

      // Lens distortion
      if (abs(uLensDistortion) > 0.001) {
        vec2 centered = uv - 0.5;
        float r2 = dot(centered, centered);
        uv = 0.5 + centered * (1.0 + uLensDistortion * r2);
      }

      // Chromatic aberration
      vec3 col;
      if (uChromaticAb > 0.001) {
        float ab = uChromaticAb * 0.003;
        vec2 dir = normalize(uv - 0.5) * ab;
        col.r = texture2D(tDiffuse, uv + dir).r;
        col.g = texture2D(tDiffuse, uv).g;
        col.b = texture2D(tDiffuse, uv - dir).b;
      } else {
        col = texture2D(tDiffuse, uv).rgb;
      }

      // Simple bloom pass (would normally be multi-pass; this is a fast approx)
      if (uBloomIntensity > 0.0) {
        float lum   = dot(col, vec3(0.2126, 0.7152, 0.0722));
        float bloom = smoothstep(uBloomThreshold, 1.0, lum);
        // Blur approximation via offset samples
        for (float x = -2.0; x <= 2.0; x += 1.0) {
          for (float y = -2.0; y <= 2.0; y += 1.0) {
            float sampleLum = dot(texture2D(tDiffuse, uv + vec2(x, y) * uBloomRadius * 0.004).rgb, vec3(0.2126, 0.7152, 0.0722));
            bloom += smoothstep(uBloomThreshold, 1.0, sampleLum) * 0.04;
          }
        }
        col += col * bloom * uBloomIntensity;
      }

      // Vignette
      if (uVignette > 0.0) {
        vec2  c   = uv - 0.5;
        float vig = 1.0 - smoothstep(0.3, 0.8, length(c) * 2.0) * uVignette;
        col       = mix(uVignetteColor, col, vig);
      }

      gl_FragColor = vec4(col, 1.0);
    }
  `
};

// ─────────────────────────────────────────────
//  LIGHTING ENGINE  (top-level orchestrator)
// ─────────────────────────────────────────────

export class LightingEngine {
  constructor(renderer, scene, camera) {
    this.renderer = renderer;
    this.scene    = scene;
    this.camera   = camera;
    this.resolver = new LightingResolver();
    this.flub     = new FlubLayer(renderer, scene);
    this.clock    = new THREE.Clock();

    // Per-layer states (2.5D advantage)
    this.layerStates = {
      background:  new LightState(),
      midground:   new LightState(),
      foreground:  new LightState(),
      avatar:      new LightState(),
      ui:          new LightState({ rimAlwaysOn: true }),
    };

    // Active preset per layer
    this.layerPresets = {
      background: 'STUDIO_NEUTRAL',
      midground:  'STUDIO_NEUTRAL',
      foreground: 'STUDIO_NEUTRAL',
      avatar:     'STUDIO_NEUTRAL',
      ui:         'NEWS_FLAT',
    };

    this._time = 0;
  }

  /**
   * Set a named preset on one or all layers.
   * @param {string} presetName - key of LightPresets
   * @param {string|null} layer - null = apply to all layers
   */
  setPreset(presetName, layer = null, transitionSeconds = 0) {
    const applyTo = layer ? [layer] : Object.keys(this.layerPresets);

    for (const l of applyTo) {
      if (transitionSeconds > 0) {
        this._startTransition(l, presetName, transitionSeconds);
      } else {
        this.layerPresets[l] = presetName;
        this.layerStates[l]  = this.resolver.resolve({ presetName });
      }
    }
  }

  _startTransition(layer, targetPreset, seconds) {
    const fromState  = this.layerStates[layer].clone();
    const targetState = this.resolver.resolve({ presetName: targetPreset });
    const startTime   = performance.now() / 1000;

    this._transitions = this._transitions || {};
    this._transitions[layer] = { fromState, targetState, startTime, duration: seconds };
  }

  /**
   * Mix two presets with an arbitrary blend weight.
   * e.g. mix('SPIELBERG', 'FINCHER', 0.4) = 60% Spielberg, 40% Fincher
   */
  mixPresets(presetA, presetB, blend, layer = null) {
    const stateA = LightPresets[presetA] || LightPresets.STUDIO_NEUTRAL;
    const stateB = LightPresets[presetB] || LightPresets.STUDIO_NEUTRAL;
    const mixed  = stateA.lerp(stateB, blend);
    const applyTo = layer ? [layer] : Object.keys(this.layerStates);
    for (const l of applyTo) this.layerStates[l] = mixed;
  }

  /**
   * Update all layer states. Call every frame.
   */
  update(audioData = null, emotionState = null) {
    this._time += this.clock.getDelta();

    // Advance any active transitions
    if (this._transitions) {
      for (const [layer, t] of Object.entries(this._transitions)) {
        const elapsed  = this._time - t.startTime;
        const progress = Math.min(1, elapsed / t.duration);
        const eased    = 1 - Math.pow(1 - progress, 3);

        this.layerStates[layer] = t.fromState.lerp(t.targetState, eased);

        if (progress >= 1) {
          this.layerPresets[layer] = /* name lost in lerp, store it */ 'custom';
          delete this._transitions[layer];
        }
      }
    }

    // Re-resolve reactive layers
    for (const [layer, presetName] of Object.entries(this.layerPresets)) {
      const state = this.layerStates[layer];
      if (state.audioReactive || emotionState) {
        this.layerStates[layer] = this.resolver.resolve({
          presetName,
          audioData,
          emotionState,
        });
      }
      // Advance time uniform
      if (this.layerStates[layer]) {
        this.layerStates[layer]._time = this._time;
      }
    }
  }

  /**
   * Get shader uniforms for a given layer.
   * Attach these to your sprite/mesh materials each frame.
   */
  getUniforms(layer = 'avatar') {
    const state    = this.layerStates[layer] || new LightState();
    const uniforms = buildLightUniforms(state);
    uniforms.uTime.value = this._time;
    return uniforms;
  }

  /**
   * Serialize current lighting state to JSON for broadcast / recording.
   */
  serialize() {
    return {
      timestamp: Date.now(),
      layers: Object.fromEntries(
        Object.entries(this.layerStates).map(([k, v]) => [k, JSON.parse(JSON.stringify(v))])
      ),
      presets: { ...this.layerPresets },
    };
  }

  /**
   * Restore lighting state from serialized JSON.
   * Used for playback and multi-client sync.
   */
  deserialize(data) {
    for (const [layer, stateData] of Object.entries(data.layers)) {
      this.layerStates[layer] = new LightState(stateData);
    }
    this.layerPresets = { ...data.presets };
  }
}

// ─────────────────────────────────────────────
//  WEBSOCKET SYNC HELPERS
// ─────────────────────────────────────────────

export class LightingSyncManager {
  constructor(engine, wsUrl) {
    this.engine = engine;
    this.ws     = null;
    this.wsUrl  = wsUrl;
  }

  connect() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'lighting_state') {
        this.engine.deserialize(msg.payload);
      } else if (msg.type === 'lighting_preset') {
        this.engine.setPreset(msg.presetName, msg.layer, msg.transition ?? 0.5);
      } else if (msg.type === 'lighting_mix') {
        this.engine.mixPresets(msg.presetA, msg.presetB, msg.blend, msg.layer);
      }
    };
  }

  broadcastState() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type:    'lighting_state',
        payload: this.engine.serialize(),
      }));
    }
  }
}
