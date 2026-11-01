
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { EtherealSkinMaterial, NeonColors } from '/static/ethereal_skin_shader_system_CORRECTED.js';

const SEGMENTS = {
  torso: { radius: 0.18, length: 0.55 },
  upperArm: { radius: 0.055, length: 0.28 },
  lowerArm: { radius: 0.045, length: 0.24 },
  upperLeg: { radius: 0.07, length: 0.36 },
  lowerLeg: { radius: 0.06, length: 0.34 },
  neck: { radius: 0.055, length: 0.08 },
  hand: { radius: 0.05, length: 0.08 },
  foot: { radius: 0.055, length: 0.14 },
};

function colorFromName(name) {
  const key = String(name || 'BLUE').toUpperCase();
  return NeonColors[key] || NeonColors.BLUE;
}

function capsule(length, radius, material) {
  const group = new THREE.Group();
  const cyl = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 10), material);
  cyl.rotation.z = Math.PI / 2;
  const left = new THREE.Mesh(new THREE.SphereGeometry(radius, 10, 10), material);
  const right = new THREE.Mesh(new THREE.SphereGeometry(radius, 10, 10), material);
  left.position.x = -length / 2;
  right.position.x = length / 2;
  group.add(cyl, left, right);
  return group;
}

function etherealMaterial(hexColor) {
  return new EtherealSkinMaterial({
    neonColor: new THREE.Color(hexColor || 0x4DC8FF),
    glowColor: new THREE.Color(hexColor || 0x4DC8FF).clone().multiplyScalar(1.3),
    opacity: 0.72,
    energyFlowEnabled: true,
    gestureIntensity: 1.8,
    glowIntensity: 2.5,
  });
}

class AvatarHumanoid {
  constructor(userId, opts = {}) {
    this.userId = userId;
    this.group = new THREE.Group();
    this.group.name = `avatar_humanoid_${userId}`;
    this.bones = {};
    this.materials = [];
    this._build(opts);
  }

  _addBone(name, parent, position) {
    const bone = new THREE.Group();
    bone.name = name;
    bone.position.fromArray(position || [0,0,0]);
    (parent || this.group).add(bone);
    this.bones[name] = bone;
    return bone;
  }

  _paint(material, ...meshes) {
    this.materials.push(material);
    meshes.forEach(m => {
      m.traverse?.(obj => {
        if (obj.isMesh) obj.material = material;
      });
      if (m.isMesh) m.material = material;
    });
  }

  _build(opts) {
    const color = opts.hex_color || opts.primary_color || '#4DC8FF';
    const material = etherealMaterial(color);
    const accent = etherealMaterial(color);

    const hips = this._addBone('hips', null, [0, 0.95, 0]);
    const spine = this._addBone('spine', hips, [0, 0.12, 0]);
    const chest = this._addBone('chest', spine, [0, 0.20, 0]);
    const neck = this._addBone('neck', chest, [0, 0.18, 0]);
    const head = this._addBone('head', neck, [0, 0.12, 0]);

    const lShoulder = this._addBone('left_shoulder', chest, [0.20, 0.11, 0]);
    const lUpperArm = this._addBone('left_upper_arm', lShoulder, [0.12, 0, 0]);
    const lLowerArm = this._addBone('left_lower_arm', lUpperArm, [0.28, 0, 0]);
    const lHand = this._addBone('left_hand', lLowerArm, [0.24, 0, 0]);

    const rShoulder = this._addBone('right_shoulder', chest, [-0.20, 0.11, 0]);
    const rUpperArm = this._addBone('right_upper_arm', rShoulder, [-0.12, 0, 0]);
    const rLowerArm = this._addBone('right_lower_arm', rUpperArm, [-0.28, 0, 0]);
    const rHand = this._addBone('right_hand', rLowerArm, [-0.24, 0, 0]);

    const lUpperLeg = this._addBone('left_upper_leg', hips, [0.10, -0.12, 0]);
    const lLowerLeg = this._addBone('left_lower_leg', lUpperLeg, [0, -0.36, 0]);
    const lFoot = this._addBone('left_foot', lLowerLeg, [0, -0.34, 0.05]);

    const rUpperLeg = this._addBone('right_upper_leg', hips, [-0.10, -0.12, 0]);
    const rLowerLeg = this._addBone('right_lower_leg', rUpperLeg, [0, -0.36, 0]);
    const rFoot = this._addBone('right_foot', rLowerLeg, [0, -0.34, 0.05]);

    const torsoMesh = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.55, 8, 12), material);
    torsoMesh.position.y = 0.34;
    hips.add(torsoMesh);
    const neckMesh = new THREE.Mesh(new THREE.CapsuleGeometry(0.05, 0.08, 4, 8), material);
    neckMesh.position.y = 0.04;
    neck.add(neckMesh);
    const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.16, 18, 18), accent);
    headMesh.position.y = 0.08;
    head.add(headMesh);

    const lUA = capsule(SEGMENTS.upperArm.length, SEGMENTS.upperArm.radius, material); lUA.position.x = 0.14; lUpperArm.add(lUA);
    const lLA = capsule(SEGMENTS.lowerArm.length, SEGMENTS.lowerArm.radius, material); lLA.position.x = 0.12; lLowerArm.add(lLA);
    const lHM = capsule(SEGMENTS.hand.length, SEGMENTS.hand.radius, material); lHM.position.x = 0.04; lHand.add(lHM);
    const rUA = capsule(SEGMENTS.upperArm.length, SEGMENTS.upperArm.radius, material); rUA.position.x = -0.14; rUpperArm.add(rUA);
    const rLA = capsule(SEGMENTS.lowerArm.length, SEGMENTS.lowerArm.radius, material); rLA.position.x = -0.12; rLowerArm.add(rLA);
    const rHM = capsule(SEGMENTS.hand.length, SEGMENTS.hand.radius, material); rHM.position.x = -0.04; rHand.add(rHM);

    const legGeo = new THREE.CapsuleGeometry(0.07, 0.28, 8, 12);
    const shinGeo = new THREE.CapsuleGeometry(0.06, 0.26, 8, 12);
    const footGeo = new THREE.BoxGeometry(0.10, 0.05, 0.22);
    const lThigh = new THREE.Mesh(legGeo, material); lThigh.position.y = -0.18; lUpperLeg.add(lThigh);
    const lShin = new THREE.Mesh(shinGeo, material); lShin.position.y = -0.17; lLowerLeg.add(lShin);
    const lFt = new THREE.Mesh(footGeo, accent); lFt.position.set(0, -0.03, 0.08); lFoot.add(lFt);
    const rThigh = new THREE.Mesh(legGeo, material); rThigh.position.y = -0.18; rUpperLeg.add(rThigh);
    const rShin = new THREE.Mesh(shinGeo, material); rShin.position.y = -0.17; rLowerLeg.add(rShin);
    const rFt = new THREE.Mesh(footGeo, accent); rFt.position.set(0, -0.03, 0.08); rFoot.add(rFt);

    this.headBone = head;
    this.chestBone = chest;
    this.handBones = { left: lHand, right: rHand };
  }

  setColor(hexColor) {
    this.materials.forEach(mat => {
      if (mat.uniforms?.uNeonColor) mat.uniforms.uNeonColor.value = new THREE.Color(hexColor);
      if (mat.uniforms?.uGlowColor) mat.uniforms.uGlowColor.value = new THREE.Color(hexColor).multiplyScalar(1.25);
    });
  }

  setGesture(name) {
    const map = { idle: 0, agreement: 1, excitement: 2, thinking: 3, welcoming: 4, welcome: 4 };
    const value = map[name] ?? 0;
    this.materials.forEach(mat => {
      if (mat.uniforms?.uCurrentGesture) mat.uniforms.uCurrentGesture.value = value;
      if (mat.uniforms?.uGestureStrength) mat.uniforms.uGestureStrength.value = value ? 0.8 : 0.0;
    });
  }

  updateSkeleton(frameData = {}) {
    for (const [jointName, pose] of Object.entries(frameData)) {
      const bone = this.bones[jointName];
      if (!bone) continue;
      if (Array.isArray(pose.position)) bone.position.fromArray(pose.position);
      if (Array.isArray(pose.rotation)) bone.quaternion.set(pose.rotation[0], pose.rotation[1], pose.rotation[2], pose.rotation[3]);
    }
  }

  getTrackingAnchor(kind = 'head') {
    const src = kind === 'chest' ? this.chestBone : this.headBone;
    const world = new THREE.Vector3();
    src.getWorldPosition(world);
    return world;
  }
}

export class AvatarHumanoidRuntime {
  constructor(scene, options = {}) {
    this.scene = scene;
    this.avatars = new Map();
    this.directorCamera = options.directorCamera || null;
    this.activeDirective = null;
  }

  spawn(data) {
    const userId = data.user_id || data.avatar_id;
    let avatar = this.avatars.get(userId);
    if (!avatar) {
      avatar = new AvatarHumanoid(userId, data);
      this.avatars.set(userId, avatar);
      this.scene.add(avatar.group);
    }
    if (data.position) avatar.group.position.fromArray(data.position);
    if (data.rotation) avatar.group.rotation.fromArray(data.rotation);
    if (data.hex_color) avatar.setColor(data.hex_color);
    if (data.current_gesture) avatar.setGesture(data.current_gesture);
    return avatar;
  }

  updateFromSkin(payload) {
    const avatar = this.spawn(payload);
    if (payload.hex_color) avatar.setColor(payload.hex_color);
    if (payload.current_gesture) avatar.setGesture(payload.current_gesture);
    return avatar;
  }

  updateSkeleton(userId, frameData) {
    const avatar = this.avatars.get(userId);
    if (!avatar) return;
    avatar.updateSkeleton(frameData);
  }

  applyCameraDirective(directive) {
    this.activeDirective = directive;
  }

  tick(delta) {
    for (const avatar of this.avatars.values()) {
      avatar.materials.forEach(mat => mat.update?.(delta));
    }
    if (this.directorCamera && this.activeDirective?.camera) {
      const targetPos = new THREE.Vector3().fromArray(this.activeDirective.camera.position);
      const lookAtPos = new THREE.Vector3().fromArray(this.activeDirective.camera.look_at);
      this.directorCamera.position.lerp(targetPos, 0.08);
      this.directorCamera.lookAt(lookAtPos);
      if (this.activeDirective.camera.fov) {
        this.directorCamera.fov += (this.activeDirective.camera.fov - this.directorCamera.fov) * 0.08;
        this.directorCamera.updateProjectionMatrix();
      }
    }
  }
}
