/**
 * Ethereal Avatar Shader System for PubCast AI
 * 
 * Creates beautiful translucent, glowing avatars with:
 * - Translucent blue energy effect
 * - Flowing aura animations
 * - 5-color mood transitions
 * - Rim lighting and inner glow
 * - Real-time WebGL optimization
 */

import * as THREE from 'three';

/**
 * Ethereal Glow Material
 * Creates the translucent, energy-based appearance
 */
export class EtherealGlowMaterial extends THREE.ShaderMaterial {
  constructor(options = {}) {
    const uniforms = {
      // Base colors and opacity
      uBaseColor: { value: new THREE.Color(options.baseColor || 0x4DC8FF) },
      uGlowColor: { value: new THREE.Color(options.glowColor || 0x80E0FF) },
      uOpacity: { value: options.opacity || 0.75 },
      
      // Glow effects
      uGlowIntensity: { value: options.glowIntensity || 2.0 },
      uRimPower: { value: options.rimPower || 3.0 },
      uInnerGlow: { value: options.innerGlow || 0.8 },
      
      // Animation
      uTime: { value: 0.0 },
      uFlowSpeed: { value: options.flowSpeed || 1.0 },
      uEnergyFlow: { value: options.energyFlow || true },
      
      // Mood Ring System (5 colors)
      uMoodColors: { 
        value: [
          new THREE.Color(0x4DC8FF), // Calm (Blue) 
          new THREE.Color(0x80FF80), // Happy (Green)
          new THREE.Color(0xFFD84D), // Energetic (Yellow)
          new THREE.Color(0xFF8040), // Excited (Orange)  
          new THREE.Color(0xFF4D80)  // Passionate (Pink)
        ]
      },
      uCurrentMood: { value: 0.0 }, // 0-4 interpolated
      uMoodTransitionSpeed: { value: 2.0 },
      
      // Texture maps
      uEnergyTexture: { value: null },
      uFlowTexture: { value: null }
    };

    const vertexShader = `
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vWorldPosition;
      varying vec2 vUv;
      varying vec3 vViewDirection;
      
      uniform float uTime;
      uniform float uFlowSpeed;
      
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPosition = position;
        vUv = uv;
        
        // Subtle vertex animation for energy flow
        vec3 pos = position;
        pos += normal * sin(uTime * uFlowSpeed + position.y * 10.0) * 0.005;
        pos += normal * sin(uTime * uFlowSpeed * 1.3 + position.x * 8.0) * 0.003;
        
        vec4 worldPosition = modelMatrix * vec4(pos, 1.0);
        vWorldPosition = worldPosition.xyz;
        
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        vViewDirection = normalize(cameraPosition - worldPosition.xyz);
        
        gl_Position = projectionMatrix * mvPosition;
      }
    `;

    const fragmentShader = `
      uniform vec3 uBaseColor;
      uniform vec3 uGlowColor;
      uniform float uOpacity;
      uniform float uGlowIntensity;
      uniform float uRimPower;
      uniform float uInnerGlow;
      uniform float uTime;
      uniform float uFlowSpeed;
      uniform bool uEnergyFlow;
      
      // Mood Ring System
      uniform vec3 uMoodColors[5];
      uniform float uCurrentMood;
      uniform float uMoodTransitionSpeed;
      
      uniform sampler2D uEnergyTexture;
      uniform sampler2D uFlowTexture;
      
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vWorldPosition;
      varying vec2 vUv;
      varying vec3 vViewDirection;
      
      // Noise function for energy effects
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
      
      // Flowing energy pattern
      float energyPattern(vec2 uv, float time) {
        vec2 flowUv = uv + vec2(sin(time * 0.5), cos(time * 0.3)) * 0.1;
        float n1 = noise(flowUv * 8.0 + time * 2.0);
        float n2 = noise(flowUv * 16.0 - time * 1.5);
        float n3 = noise(flowUv * 32.0 + time * 3.0);
        
        return n1 * 0.5 + n2 * 0.3 + n3 * 0.2;
      }
      
      // Get current mood color with smooth transitions
      vec3 getMoodColor() {
        float mood = mod(uCurrentMood + uTime * uMoodTransitionSpeed * 0.1, 5.0);
        int index = int(floor(mood));
        float t = fract(mood);
        
        vec3 color1 = uMoodColors[index];
        vec3 color2 = uMoodColors[(index + 1) % 5];
        
        return mix(color1, color2, smoothstep(0.0, 1.0, t));
      }
      
      void main() {
        // Base surface calculations
        vec3 normal = normalize(vNormal);
        vec3 viewDir = normalize(vViewDirection);
        
        // Rim lighting effect
        float rimFactor = 1.0 - max(0.0, dot(normal, viewDir));
        float rimEffect = pow(rimFactor, uRimPower);
        
        // Inner glow based on surface angle
        float innerGlow = pow(max(0.0, dot(normal, viewDir)), 2.0) * uInnerGlow;
        
        // Energy flow effects
        float energyMask = 1.0;
        if (uEnergyFlow) {
          energyMask = energyPattern(vUv, uTime * uFlowSpeed);
          energyMask = smoothstep(0.3, 0.8, energyMask);
        }
        
        // Get mood-based color
        vec3 moodColor = getMoodColor();
        
        // Combine base color with mood
        vec3 baseColor = mix(uBaseColor, moodColor, 0.6);
        vec3 glowColor = mix(uGlowColor, moodColor * 1.2, 0.8);
        
        // Final color composition
        vec3 finalColor = baseColor;
        
        // Add rim glow
        finalColor += glowColor * rimEffect * uGlowIntensity;
        
        // Add inner glow  
        finalColor += baseColor * innerGlow * 0.5;
        
        // Apply energy flow
        finalColor = mix(finalColor * 0.7, finalColor * 1.3, energyMask);
        
        // Pulsing effect for aliveness
        float pulse = sin(uTime * 3.0) * 0.1 + 0.9;
        finalColor *= pulse;
        
        // Calculate final opacity with translucency
        float opacity = uOpacity;
        opacity *= (rimEffect * 0.3 + 0.7); // More opaque at edges
        opacity *= (energyMask * 0.2 + 0.8); // Vary with energy flow
        
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

  // Update animation time
  update(deltaTime) {
    this.uniforms.uTime.value += deltaTime;
  }

  // Set mood (0-4: Calm, Happy, Energetic, Excited, Passionate)
  setMood(moodIndex) {
    this.uniforms.uCurrentMood.value = moodIndex;
  }

  // Smooth mood transition
  transitionToMood(targetMood, duration = 2.0) {
    const currentMood = this.uniforms.uCurrentMood.value;
    const startTime = performance.now();
    
    const animate = () => {
      const elapsed = (performance.now() - startTime) / 1000;
      const progress = Math.min(elapsed / duration, 1.0);
      const eased = 1 - Math.pow(1 - progress, 3); // Ease out cubic
      
      this.uniforms.uCurrentMood.value = currentMood + (targetMood - currentMood) * eased;
      
      if (progress < 1.0) {
        requestAnimationFrame(animate);
      }
    };
    
    requestAnimationFrame(animate);
  }
}

/**
 * Ethereal Avatar Manager
 * Handles avatar creation, animation, and mood transitions
 */
export class EtherealAvatarManager {
  constructor(scene, renderer) {
    this.scene = scene;
    this.renderer = renderer;
    this.avatars = new Map();
    this.clock = new THREE.Clock();
    
    // Preload energy textures
    this.loadEnergyTextures();
  }

  loadEnergyTextures() {
    const loader = new THREE.TextureLoader();
    
    // Create procedural energy texture
    this.energyTexture = this.createEnergyTexture();
    this.flowTexture = this.createFlowTexture();
  }

  createEnergyTexture() {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    
    // Create flowing energy pattern
    const imageData = ctx.createImageData(size, size);
    const data = imageData.data;
    
    for (let i = 0; i < size; i++) {
      for (let j = 0; j < size; j++) {
        const x = i / size;
        const y = j / size;
        
        // Flowing energy pattern
        const pattern = 
          Math.sin(x * Math.PI * 4) * 0.5 +
          Math.cos(y * Math.PI * 6) * 0.3 +
          Math.sin((x + y) * Math.PI * 8) * 0.2;
        
        const intensity = Math.max(0, Math.min(1, (pattern + 1) * 0.5));
        
        const index = (i * size + j) * 4;
        data[index] = intensity * 100;     // R
        data[index + 1] = intensity * 200; // G  
        data[index + 2] = intensity * 255; // B
        data[index + 3] = intensity * 255; // A
      }
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.needsUpdate = true;
    
    return texture;
  }

  createFlowTexture() {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    
    // Create flow vectors
    const imageData = ctx.createImageData(size, size);
    const data = imageData.data;
    
    for (let i = 0; i < size; i++) {
      for (let j = 0; j < size; j++) {
        const x = (i / size) * 2 - 1;
        const y = (j / size) * 2 - 1;
        
        // Radial flow pattern
        const angle = Math.atan2(y, x);
        const flowX = Math.cos(angle + Math.PI * 0.5) * 0.5 + 0.5;
        const flowY = Math.sin(angle + Math.PI * 0.5) * 0.5 + 0.5;
        
        const index = (i * size + j) * 4;
        data[index] = flowX * 255;     // R
        data[index + 1] = flowY * 255; // G
        data[index + 2] = 0;           // B
        data[index + 3] = 255;         // A
      }
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.needsUpdate = true;
    
    return texture;
  }

  createEtherealAvatar(id, geometry, options = {}) {
    const material = new EtherealGlowMaterial({
      baseColor: options.baseColor || 0x4DC8FF,
      glowColor: options.glowColor || 0x80E0FF,
      opacity: options.opacity || 0.75,
      glowIntensity: options.glowIntensity || 2.0,
      rimPower: options.rimPower || 3.0,
      ...options
    });

    // Set textures
    material.uniforms.uEnergyTexture.value = this.energyTexture;
    material.uniforms.uFlowTexture.value = this.flowTexture;

    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.avatarId = id;
    mesh.userData.material = material;

    this.avatars.set(id, mesh);
    this.scene.add(mesh);

    return mesh;
  }

  updateAvatars() {
    const deltaTime = this.clock.getDelta();
    
    this.avatars.forEach((avatar) => {
      const material = avatar.userData.material;
      if (material && material.update) {
        material.update(deltaTime);
      }
    });
  }

  setAvatarMood(avatarId, moodIndex) {
    const avatar = this.avatars.get(avatarId);
    if (avatar && avatar.userData.material) {
      avatar.userData.material.setMood(moodIndex);
    }
  }

  transitionAvatarMood(avatarId, moodIndex, duration) {
    const avatar = this.avatars.get(avatarId);
    if (avatar && avatar.userData.material) {
      avatar.userData.material.transitionToMood(moodIndex, duration);
    }
  }

  removeAvatar(avatarId) {
    const avatar = this.avatars.get(avatarId);
    if (avatar) {
      this.scene.remove(avatar);
      avatar.userData.material.dispose();
      this.avatars.delete(avatarId);
    }
  }

  dispose() {
    this.avatars.forEach((avatar) => {
      this.scene.remove(avatar);
      avatar.userData.material.dispose();
    });
    this.avatars.clear();
    
    if (this.energyTexture) this.energyTexture.dispose();
    if (this.flowTexture) this.flowTexture.dispose();
  }
}

/**
 * Mood Ring System Integration
 * Maps emotional states to colors and transitions
 */
export const MoodRingSystem = {
  // Mood definitions with colors and characteristics
  moods: {
    CALM: { index: 0, color: 0x4DC8FF, name: 'Calm', energy: 0.3 },
    HAPPY: { index: 1, color: 0x80FF80, name: 'Happy', energy: 0.6 },
    ENERGETIC: { index: 2, color: 0xFFD84D, name: 'Energetic', energy: 0.8 },
    EXCITED: { index: 3, color: 0xFF8040, name: 'Excited', energy: 0.9 },
    PASSIONATE: { index: 4, color: 0xFF4D80, name: 'Passionate', energy: 1.0 }
  },

  // Get mood by name
  getMood(moodName) {
    return this.moods[moodName.toUpperCase()] || this.moods.CALM;
  },

  // Analyze text for emotional content (simple version)
  analyzeMoodFromText(text) {
    const lowerText = text.toLowerCase();
    
    if (/(love|passion|heart|romantic)/i.test(text)) return this.moods.PASSIONATE;
    if (/(excited|wow|amazing|incredible)/i.test(text)) return this.moods.EXCITED;
    if (/(energy|action|go|move|fast)/i.test(text)) return this.moods.ENERGETIC;
    if (/(happy|joy|smile|laugh|good)/i.test(text)) return this.moods.HAPPY;
    
    return this.moods.CALM; // Default
  }
};

// Usage example:
/*
const avatarManager = new EtherealAvatarManager(scene, renderer);

// Create ethereal avatar
const avatar = avatarManager.createEtherealAvatar('user1', avatarGeometry, {
  baseColor: 0x4DC8FF,
  glowIntensity: 2.5,
  opacity: 0.8
});

// Set mood
avatarManager.setAvatarMood('user1', MoodRingSystem.moods.HAPPY.index);

// Animate in render loop
function animate() {
  avatarManager.updateAvatars();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
*/
