/**
 * CORRECTED Ethereal Skin Shader System for PubCast AI
 * 
 * Works with ethereal SKINS that attach to existing skeleton system.
 * Features:
 * - Neon color palette (pink, purple, green, yellow, white, black)
 * - Toggleable energy flow effects
 * - Enhanced visual communication for faceless avatars
 * - Amplified gesture visualization
 * - Compatible with existing PubCast choreography system
 */

import * as THREE from 'three';

/**
 * Neon Color Palette for Ethereal Skins
 */
export const NeonColors = {
  BLUE: new THREE.Color(0x4DC8FF),
  PINK: new THREE.Color(0xFF4DC8),
  PURPLE: new THREE.Color(0xC84DFF), 
  GREEN: new THREE.Color(0x4DFF4D),
  YELLOW: new THREE.Color(0xFFFF4D),
  WHITE: new THREE.Color(0xFFFFFF),
  BLACK: new THREE.Color(0x111111)  // Neon black = very dark with bright edges
};

/**
 * Enhanced Ethereal Skin Material
 * Designed for faceless avatars with enhanced visual communication
 */
export class EtherealSkinMaterial extends THREE.ShaderMaterial {
  constructor(options = {}) {
    const uniforms = {
      // Neon color system
      uNeonColor: { value: options.neonColor || NeonColors.BLUE },
      uGlowColor: { value: options.glowColor || NeonColors.BLUE.clone().multiplyScalar(1.3) },
      uOpacity: { value: options.opacity || 0.75 },
      
      // Energy flow system (toggleable)
      uEnergyFlowEnabled: { value: options.energyFlowEnabled !== false },
      uFlowSpeed: { value: options.flowSpeed || 1.0 },
      uFlowIntensity: { value: options.flowIntensity || 1.0 },
      
      // Glow and rim effects
      uGlowIntensity: { value: options.glowIntensity || 2.5 },
      uRimPower: { value: options.rimPower || 3.0 },
      uInnerGlow: { value: options.innerGlow || 0.8 },
      
      // Enhanced communication for faceless avatars
      uGestureIntensity: { value: options.gestureIntensity || 1.8 },
      uEmotionAmplifier: { value: options.emotionAmplifier || 2.0 },
      uAuraRadius: { value: options.auraRadius || 1.2 },
      uParticleDensity: { value: options.particleDensity || 1.0 },
      
      // Animation
      uTime: { value: 0.0 },
      
      // Current gesture/emotion state
      uCurrentGesture: { value: 0.0 }, // 0=idle, 1=agreement, 2=excitement, etc.
      uGestureStrength: { value: 0.0 },
      uEmotionIntensity: { value: 0.0 }
    };

    const vertexShader = `
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vWorldPosition;
      varying vec2 vUv;
      varying vec3 vViewDirection;
      varying float vDistanceFromCenter;
      
      uniform float uTime;
      uniform float uFlowSpeed;
      uniform float uGestureIntensity;
      uniform float uCurrentGesture;
      uniform float uGestureStrength;
      uniform bool uEnergyFlowEnabled;
      
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPosition = position;
        vUv = uv;
        
        // Calculate distance from center for aura effects
        vDistanceFromCenter = length(position);
        
        // Enhanced vertex animation for faceless communication
        vec3 pos = position;
        
        if (uEnergyFlowEnabled) {
          // Base energy flow
          pos += normal * sin(uTime * uFlowSpeed + position.y * 10.0) * 0.005;
          pos += normal * sin(uTime * uFlowSpeed * 1.3 + position.x * 8.0) * 0.003;
          
          // Gesture-enhanced animations
          float gestureEffect = uGestureStrength * uGestureIntensity;
          
          if (uCurrentGesture == 1.0) { // Agreement - vertical pulse
            pos += normal * sin(uTime * 8.0) * gestureEffect * 0.02;
          } else if (uCurrentGesture == 2.0) { // Excitement - all-over sparkle
            pos += normal * (sin(uTime * 15.0 + position.x * 20.0) + 
                           cos(uTime * 12.0 + position.y * 18.0)) * gestureEffect * 0.008;
          } else if (uCurrentGesture == 3.0) { // Thinking - head focus
            float headWeight = smoothstep(1.5, 1.8, position.y);
            pos += normal * sin(uTime * 4.0) * headWeight * gestureEffect * 0.01;
          } else if (uCurrentGesture == 4.0) { // Welcoming - arm emphasis
            float armWeight = smoothstep(0.8, 1.5, abs(position.x));
            pos += normal * sin(uTime * 6.0) * armWeight * gestureEffect * 0.015;
          }
        }
        
        vec4 worldPosition = modelMatrix * vec4(pos, 1.0);
        vWorldPosition = worldPosition.xyz;
        
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        vViewDirection = normalize(cameraPosition - worldPosition.xyz);
        
        gl_Position = projectionMatrix * mvPosition;
      }
    `;

    const fragmentShader = `
      uniform vec3 uNeonColor;
      uniform vec3 uGlowColor;
      uniform float uOpacity;
      uniform float uGlowIntensity;
      uniform float uRimPower;
      uniform float uInnerGlow;
      uniform float uTime;
      uniform bool uEnergyFlowEnabled;
      uniform float uFlowSpeed;
      uniform float uFlowIntensity;
      
      // Enhanced communication uniforms
      uniform float uGestureIntensity;
      uniform float uEmotionAmplifier;
      uniform float uAuraRadius;
      uniform float uParticleDensity;
      uniform float uCurrentGesture;
      uniform float uGestureStrength;
      uniform float uEmotionIntensity;
      
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vWorldPosition;
      varying vec2 vUv;
      varying vec3 vViewDirection;
      varying float vDistanceFromCenter;
      
      // Enhanced noise for more dynamic effects
      float random(vec2 st) {
        return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
      }
      
      float noise(vec2 st) {
        vec2 i = floor(st);
        vec2 f = fract(st);
        
        float a = random(i);
        float b = random(i + vec2(1.0, 0.0));
        float c = random(i + vec2(0.0, 1.0));
        float d = random(i + vec2(1.0, 1.0));
        
        vec2 u = f * f * (3.0 - 2.0 * f);
        
        return mix(a, b, u.x) + (c - a)* u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
      }
      
      // Multi-layer energy pattern for richer effects
      float energyPattern(vec2 uv, float time) {
        if (!uEnergyFlowEnabled) return 0.8;
        
        vec2 flowUv = uv + vec2(sin(time * 0.5), cos(time * 0.3)) * 0.1;
        float n1 = noise(flowUv * 8.0 + time * 2.0);
        float n2 = noise(flowUv * 16.0 - time * 1.5);
        float n3 = noise(flowUv * 32.0 + time * 3.0);
        
        float base = n1 * 0.5 + n2 * 0.3 + n3 * 0.2;
        
        // Add gesture-specific patterns
        if (uCurrentGesture == 1.0) { // Agreement - wave pattern
          base += sin(uv.y * 20.0 - time * 8.0) * uGestureStrength * 0.3;
        } else if (uCurrentGesture == 2.0) { // Excitement - rapid sparkles
          base += (noise(uv * 40.0 + time * 10.0) * 0.5 + 0.5) * uGestureStrength * 0.4;
        } else if (uCurrentGesture == 3.0) { // Thinking - slow spiral
          vec2 center = vec2(0.5, 0.8); // Head area
          vec2 toCenter = uv - center;
          float angle = atan(toCenter.y, toCenter.x) + time * 2.0;
          base += sin(angle * 6.0) * smoothstep(0.5, 0.0, length(toCenter)) * uGestureStrength * 0.3;
        }
        
        return base * uFlowIntensity;
      }
      
      // Aura calculation for enhanced presence
      float calculateAura() {
        float distanceEffect = smoothstep(uAuraRadius, 0.0, vDistanceFromCenter);
        float timeEffect = sin(uTime * 3.0) * 0.1 + 0.9;
        float emotionEffect = 1.0 + uEmotionIntensity * uEmotionAmplifier * 0.5;
        
        return distanceEffect * timeEffect * emotionEffect;
      }
      
      void main() {
        // Base surface calculations
        vec3 normal = normalize(vNormal);
        vec3 viewDir = normalize(vViewDirection);
        
        // Enhanced rim lighting for better visibility
        float rimFactor = 1.0 - max(0.0, dot(normal, viewDir));
        float rimEffect = pow(rimFactor, uRimPower);
        
        // Inner glow for ethereal effect
        float innerGlow = pow(max(0.0, dot(normal, viewDir)), 2.0) * uInnerGlow;
        
        // Energy flow pattern
        float energyMask = energyPattern(vUv, uTime * uFlowSpeed);
        energyMask = smoothstep(0.3, 0.8, energyMask);
        
        // Aura calculation
        float auraEffect = calculateAura();
        
        // Start with neon color
        vec3 baseColor = uNeonColor;
        vec3 glowColor = uGlowColor;
        
        // Special handling for neon black
        if (length(uNeonColor) < 0.5) { // Very dark color (neon black)
          // Make edges very bright while keeping interior dark
          baseColor = mix(vec3(0.05), vec3(0.8), rimEffect);
          glowColor = vec3(0.9, 0.9, 1.0); // Bright blue-white glow
        }
        
        // Build final color
        vec3 finalColor = baseColor;
        
        // Add rim glow (enhanced for visibility)
        finalColor += glowColor * rimEffect * uGlowIntensity * (1.0 + uGestureStrength);
        
        // Add inner glow
        finalColor += baseColor * innerGlow * 0.5;
        
        // Apply energy flow
        finalColor = mix(finalColor * 0.6, finalColor * 1.4, energyMask);
        
        // Add aura effect
        finalColor += glowColor * auraEffect * 0.3;
        
        // Enhanced pulsing for "aliveness" - varies by gesture
        float pulseSpeed = 3.0 + uCurrentGesture * 2.0; // Faster pulse during gestures
        float pulse = sin(uTime * pulseSpeed) * 0.15 + 0.85;
        pulse *= 1.0 + uGestureStrength * 0.3; // Brighter during gestures
        finalColor *= pulse;
        
        // Particle effect overlay for enhanced communication
        float particles = 0.0;
        if (uParticleDensity > 0.0) {
          vec2 particleUv = vUv * 20.0;
          particles = step(0.98, noise(particleUv + uTime * 2.0)) * uParticleDensity;
          finalColor += particles * glowColor * 0.8;
        }
        
        // Calculate final opacity with enhanced edges
        float opacity = uOpacity;
        opacity *= (rimEffect * 0.4 + 0.6); // More opaque at edges
        opacity *= (energyMask * 0.3 + 0.7); // Vary with energy flow
        opacity *= (1.0 + auraEffect * 0.2); // Enhanced by aura
        
        gl_FragColor = vec4(finalColor, opacity);
      }
    `;

    super({
      uniforms,
      vertexShader,
      fragmentShader,
      transparent: true,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    this.needsUpdate = true;
  }

  // Update animation
  update(deltaTime) {
    this.uniforms.uTime.value += deltaTime;
  }

  // Change neon color
  setNeonColor(colorName) {
    if (NeonColors[colorName.toUpperCase()]) {
      this.uniforms.uNeonColor.value = NeonColors[colorName.toUpperCase()];
      this.uniforms.uGlowColor.value = NeonColors[colorName.toUpperCase()].clone().multiplyScalar(1.3);
    }
  }

  // Toggle energy flow effects
  toggleEnergyFlow() {
    this.uniforms.uEnergyFlowEnabled.value = !this.uniforms.uEnergyFlowEnabled.value;
    return this.uniforms.uEnergyFlowEnabled.value;
  }

  // Set enhanced gesture for faceless communication
  setGesture(gestureType, intensity = 1.0) {
    const gestureMap = {
      'idle': 0.0,
      'agreement': 1.0,
      'excitement': 2.0, 
      'thinking': 3.0,
      'welcoming': 4.0,
      'disagreement': 5.0
    };

    this.uniforms.uCurrentGesture.value = gestureMap[gestureType] || 0.0;
    this.uniforms.uGestureStrength.value = intensity;
    
    // Auto-fade gesture after duration
    setTimeout(() => {
      this.uniforms.uGestureStrength.value = 0.0;
    }, 3000);
  }

  // Set emotion intensity for enhanced aura
  setEmotionIntensity(intensity) {
    this.uniforms.uEmotionIntensity.value = Math.max(0.0, Math.min(2.0, intensity));
  }
}

/**
 * Ethereal Skin Manager for PubCast Integration
 * Works with existing skeleton system
 */
export class EtherealSkinRenderer {
  constructor(scene, renderer) {
    this.scene = scene;
    this.renderer = renderer;
    this.skins = new Map();
    this.clock = new THREE.Clock();
  }

  createEtherealSkin(avatarId, skinGeometry, options = {}) {
    const material = new EtherealSkinMaterial({
      neonColor: NeonColors[options.neonColor?.toUpperCase()] || NeonColors.BLUE,
      energyFlowEnabled: options.energyFlowEnabled !== false,
      gestureIntensity: options.gestureIntensity || 1.8,
      glowIntensity: options.glowIntensity || 2.5,
      ...options
    });

    const mesh = new THREE.Mesh(skinGeometry, material);
    mesh.userData.avatarId = avatarId;
    mesh.userData.material = material;

    // Set up skeleton binding if provided
    if (options.skeleton) {
      mesh.bind(options.skeleton);
    }

    this.skins.set(avatarId, mesh);
    this.scene.add(mesh);

    return mesh;
  }

  updateSkinsFromSkeletonData(skeletonData) {
    // This gets called with data from existing PubCast choreography system
    // skeletonData format: { avatarId: { jointName: [x,y,z,rx,ry,rz], ... } }
    
    this.skins.forEach((skinMesh, avatarId) => {
      if (skeletonData[avatarId]) {
        // Update skin mesh based on skeleton joint positions
        // This integrates with your existing get_full_skeleton_data() system
        this.updateSkinFromSkeleton(skinMesh, skeletonData[avatarId]);
      }
    });
  }

  updateSkinFromSkeleton(skinMesh, jointData) {
    // Update mesh vertices based on joint positions and weights
    // This is where the skin deformation happens based on skeleton
    if (skinMesh.geometry && skinMesh.userData.jointWeights) {
      // Apply skeletal deformation to vertices
      // (This would use the joint_weights from the skin to transform vertices)
    }
  }

  changeSkinColor(avatarId, neonColor) {
    const skin = this.skins.get(avatarId);
    if (skin && skin.userData.material) {
      skin.userData.material.setNeonColor(neonColor);
    }
  }

  toggleSkinEnergyFlow(avatarId) {
    const skin = this.skins.get(avatarId);
    if (skin && skin.userData.material) {
      return skin.userData.material.toggleEnergyFlow();
    }
    return false;
  }

  setSkinGesture(avatarId, gestureType, intensity) {
    const skin = this.skins.get(avatarId);
    if (skin && skin.userData.material) {
      skin.userData.material.setGesture(gestureType, intensity);
    }
  }

  setSkinEmotion(avatarId, emotionIntensity) {
    const skin = this.skins.get(avatarId);
    if (skin && skin.userData.material) {
      skin.userData.material.setEmotionIntensity(emotionIntensity);
    }
  }

  updateSkins() {
    const deltaTime = this.clock.getDelta();
    
    this.skins.forEach((skin) => {
      const material = skin.userData.material;
      if (material && material.update) {
        material.update(deltaTime);
      }
    });
  }

  removeSkin(avatarId) {
    const skin = this.skins.get(avatarId);
    if (skin) {
      this.scene.remove(skin);
      skin.userData.material.dispose();
      this.skins.delete(avatarId);
    }
  }

  dispose() {
    this.skins.forEach((skin) => {
      this.scene.remove(skin);
      skin.userData.material.dispose();
    });
    this.skins.clear();
  }
}

/**
 * Integration with existing PubCast choreography system
 */
export class PubCastEtherealIntegration {
  constructor(skinRenderer) {
    this.skinRenderer = skinRenderer;
  }

  // Called from existing choreography update loop
  onChoreographyUpdate(avatars) {
    // Convert avatar data to skeleton data format
    const skeletonData = {};
    
    avatars.forEach(avatar => {
      if (avatar.get_full_skeleton_data) {
        skeletonData[avatar.id] = avatar.get_full_skeleton_data();
      }
    });
    
    // Update all ethereal skins based on skeleton data
    this.skinRenderer.updateSkinsFromSkeletonData(skeletonData);
  }

  // Enhanced gesture communication for faceless avatars
  triggerGestureFromText(avatarId, text, emotionIntensity = 1.0) {
    // Analyze text for gesture cues
    const lowerText = text.toLowerCase();
    
    let gestureType = 'idle';
    if (/(yes|agree|nod|right)/i.test(text)) {
      gestureType = 'agreement';
    } else if (/(no|disagree|wrong)/i.test(text)) {
      gestureType = 'disagreement'; 
    } else if (/(excited|wow|amazing)/i.test(text)) {
      gestureType = 'excitement';
    } else if (/(think|hmm|consider)/i.test(text)) {
      gestureType = 'thinking';
    } else if (/(hello|welcome|greet)/i.test(text)) {
      gestureType = 'welcoming';
    }
    
    this.skinRenderer.setSkinGesture(avatarId, gestureType, emotionIntensity);
    this.skinRenderer.setSkinEmotion(avatarId, emotionIntensity);
  }
}

// Usage example for integration:
/*
// In your existing PubCast system:
const skinRenderer = new EtherealSkinRenderer(scene, renderer);
const integration = new PubCastEtherealIntegration(skinRenderer);

// Create ethereal skin for user
const skin = skinRenderer.createEtherealSkin('user1', skinGeometry, {
  neonColor: 'PINK',
  energyFlowEnabled: true,
  gestureIntensity: 1.8
});

// In your existing choreography update loop:
function choreographyUpdate(avatars) {
  // Your existing choreography code...
  
  // Update ethereal skins
  integration.onChoreographyUpdate(avatars);
  
  // Update skin animations
  skinRenderer.updateSkins();
}

// For enhanced communication:
integration.triggerGestureFromText('user1', "Yes, I agree with that!", 1.5);
*/
