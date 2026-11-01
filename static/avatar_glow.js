/**
 * static/avatar_glow.js
 * ═══════════════════════════════════════════════════════════════════════════
 * PubCast Holographic Avatar System
 * 
 * Features:
 * • Cyan edge-glow holographic shader (matches your reference images)
 * • GLB model loading with automatic glow material application
 * • Skeletal animation via Three.js AnimationMixer
 * • Choreography-driven movement (position, rotation, poses)
 * • WebSocket integration for real-time performance data
 * • Idle/walk/turn animations with smooth blending
 * 
 * Usage in viewer.html or world.html:
 *   import { HolographicAvatarSystem } from '/static/avatar_glow.js';
 *   const avatars = new HolographicAvatarSystem(scene, camera);
 *   await avatars.spawn('avatar-1', '/assets/avatar/sample.glb');
 *   avatars.connectChoreography('ws://localhost:8000/ws/green');
 */

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js';

// ══════════════════════════════════════════════════════════════════════════
// HOLOGRAPHIC GLOW SHADER
// ══════════════════════════════════════════════════════════════════════════

const HOLO_VERT = `
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vNormal = normalize(normalMatrix * normal);
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  vPosition = mvPos.xyz;
  gl_Position = projectionMatrix * mvPos;
}
`;

const HOLO_FRAG = `
uniform vec3 glowColor;
uniform float glowPower;
uniform float opacity;

varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vec3 viewDir = normalize(-vPosition);
  float fresnel = 1.0 - abs(dot(viewDir, vNormal));
  fresnel = pow(fresnel, glowPower);
  
  vec3 finalColor = glowColor * (0.3 + fresnel * 2.5);
  float alpha = (0.15 + fresnel * 0.85) * opacity;
  
  gl_FragColor = vec4(finalColor, alpha);
}
`;

class HoloMaterial extends THREE.ShaderMaterial {
  constructor(color = 0x00e0ff, power = 2.8, opacity = 1.0) {
    super({
      uniforms: {
        glowColor: { value: new THREE.Color(color) },
        glowPower: { value: power },
        opacity: { value: opacity },
      },
      vertexShader: HOLO_VERT,
      fragmentShader: HOLO_FRAG,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }
}

// ══════════════════════════════════════════════════════════════════════════
// AVATAR INSTANCE
// ══════════════════════════════════════════════════════════════════════════

class HolographicAvatar {
  constructor(id, gltf, glowColor) {
    this.id = id;
    this.root = new THREE.Group();
    this.root.name = `avatar_${id}`;
    
    // Apply holographic material to all meshes
    const holo = new HoloMaterial(glowColor);
    gltf.scene.traverse(child => {
      if (child.isMesh) {
        child.material = holo;
        child.castShadow = false;
        child.receiveShadow = false;
      }
    });
    
    this.model = gltf.scene;
    this.root.add(this.model);
    
    // Animation setup
    this.mixer = new THREE.AnimationMixer(this.model);
    this.animations = {};
    this.currentAction = null;
    
    if (gltf.animations && gltf.animations.length > 0) {
      gltf.animations.forEach(clip => {
        this.animations[clip.name] = this.mixer.clipAction(clip);
      });
    }
    
    // Choreography state
    this.choreographyStep = null;
    this.stepStartTime = 0;
  }

  playAnimation(name, loop = true, fadeTime = 0.3) {
    const action = this.animations[name];
    if (!action) {
      console.warn(`Animation "${name}" not found on avatar ${this.id}`);
      return;
    }

    if (this.currentAction && this.currentAction !== action) {
      this.currentAction.fadeOut(fadeTime);
    }

    action.reset()
      .setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity)
      .fadeIn(fadeTime)
      .play();

    this.currentAction = action;
  }

  stopAllAnimations(fadeTime = 0.2) {
    Object.values(this.animations).forEach(action => action.fadeOut(fadeTime));
    this.currentAction = null;
  }

  updateChoreography(currentTime, delta) {
    if (this.mixer) {
      this.mixer.update(delta);
    }

    if (!this.choreographyStep) return;

    const elapsed = currentTime - this.stepStartTime;
    const progress = Math.min(1.0, elapsed / this.choreographyStep.duration);
    const eased = this._easeInOutCubic(progress);

    // Lerp position
    if (this.choreographyStep.target_position) {
      const start = this.choreographyStep.initial_position;
      const end = this.choreographyStep.target_position;
      this.root.position.set(
        start[0] + (end[0] - start[0]) * eased,
        start[1] + (end[1] - start[1]) * eased,
        start[2] + (end[2] - start[2]) * eased
      );
    }

    // Lerp rotation
    if (this.choreographyStep.target_rotation) {
      const start = this.choreographyStep.initial_rotation;
      const end = this.choreographyStep.target_rotation;
      this.root.rotation.set(
        start[0] + (end[0] - start[0]) * eased,
        start[1] + (end[1] - start[1]) * eased,
        start[2] + (end[2] - start[2]) * eased
      );
    }

    // Auto-complete
    if (progress >= 1.0) {
      this.choreographyStep = null;
    }
  }

  setChoreographyStep(step, currentTime) {
    this.choreographyStep = {
      ...step,
      initial_position: [
        this.root.position.x,
        this.root.position.y,
        this.root.position.z
      ],
      initial_rotation: [
        this.root.rotation.x,
        this.root.rotation.y,
        this.root.rotation.z
      ],
    };
    this.stepStartTime = currentTime;

    // Auto-trigger walk animation if moving
    if (step.animation_type === 'walk' || step.animation_type === 'move') {
      this.playAnimation('walk' in this.animations ? 'walk' : 'idle', true);
    } else if (step.animation_type === 'turn') {
      this.playAnimation('turn' in this.animations ? 'turn' : 'idle', false);
    }
  }

  _easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// AVATAR SYSTEM
// ══════════════════════════════════════════════════════════════════════════

export class HolographicAvatarSystem {
  constructor(scene, camera) {
    this.scene = scene;
    this.camera = camera;
    this.avatars = new Map();
    this.loader = new GLTFLoader();
    this.ws = null;
    this.clock = new THREE.Clock();
    this.baseTime = 0;

    // Start update loop
    this._startUpdateLoop();
  }

  async spawn(id, glbPath, options = {}) {
    const glowColor = options.glowColor || 0x00e0ff;

    return new Promise((resolve, reject) => {
      this.loader.load(
        glbPath,
        (gltf) => {
          const avatar = new HolographicAvatar(id, gltf, glowColor);
          
          if (options.position) {
            avatar.root.position.set(...options.position);
          }
          if (options.rotation) {
            avatar.root.rotation.set(...options.rotation);
          }

          this.scene.add(avatar.root);
          this.avatars.set(id, avatar);

          console.log(`✓ Avatar ${id} spawned`);
          resolve(avatar);
        },
        undefined,
        (error) => {
          console.error(`Failed to load avatar ${id}:`, error);
          reject(error);
        }
      );
    });
  }

  despawn(id) {
    const avatar = this.avatars.get(id);
    if (avatar) {
      this.scene.remove(avatar.root);
      avatar.mixer?.stopAllAction();
      this.avatars.delete(id);
    }
  }

  get(id) {
    return this.avatars.get(id);
  }

  connectChoreography(wsUrl) {
    if (this.ws) this.ws.close();

    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('Choreography WebSocket connected');
      this.baseTime = this.clock.getElapsedTime();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'choreography_step') {
          this.handleChoreographyStep(msg.data);
        }
      } catch (err) {
        console.warn('WS parse error:', err);
      }
    };

    this.ws.onerror = (err) => console.error('Choreography WS error:', err);
    this.ws.onclose = () => console.log('Choreography WS closed');
  }

  handleChoreographyStep(data) {
    // data: { avatar_id, step: { animation_type, start_time, duration, target_position, ... } }
    const avatar = this.avatars.get(data.avatar_id);
    if (!avatar) {
      console.warn(`Avatar ${data.avatar_id} not found for choreography`);
      return;
    }

    const currentTime = this.baseTime + this.clock.getElapsedTime();
    avatar.setChoreographyStep(data.step, currentTime);
  }

  _startUpdateLoop() {
    const animate = () => {
      requestAnimationFrame(animate);

      const delta = this.clock.getDelta();
      const currentTime = this.baseTime + this.clock.getElapsedTime();

      this.avatars.forEach(avatar => {
        avatar.updateChoreography(currentTime, delta);
      });
    };
    animate();
  }

  dispose() {
    if (this.ws) this.ws.close();
    this.avatars.forEach(avatar => this.despawn(avatar.id));
  }
}

// ══════════════════════════════════════════════════════════════════════════
// STANDALONE RENDERER (for testing)
// ══════════════════════════════════════════════════════════════════════════

export class StandaloneAvatarRenderer {
  constructor(container) {
    this.container = container;
    
    // Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0a0f);
    
    // Camera
    this.camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    this.camera.position.set(0, 1.6, 4);
    this.camera.lookAt(0, 1, 0);
    
    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(this.renderer.domElement);
    
    // Lighting
    const ambient = new THREE.AmbientLight(0x404060, 0.4);
    this.scene.add(ambient);

    const key = new THREE.DirectionalLight(0xffffff, 0.6);
    key.position.set(5, 8, 5);
    this.scene.add(key);

    // Grid floor
    const grid = new THREE.GridHelper(20, 20, 0x00e0ff, 0x333344);
    grid.material.opacity = 0.2;
    grid.material.transparent = true;
    this.scene.add(grid);

    // Avatar system
    this.avatars = new HolographicAvatarSystem(this.scene, this.camera);
    
    // Render loop
    this._startRenderLoop();
    this._handleResize();
  }

  _startRenderLoop() {
    const animate = () => {
      requestAnimationFrame(animate);
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  _handleResize() {
    window.addEventListener('resize', () => {
      const w = this.container.clientWidth;
      const h = this.container.clientHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    });
  }
}
