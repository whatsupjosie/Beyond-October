/*
 * PubCast GLB Motion Consumer
 * Browser-side bridge from PubCast avatar motion commands to loaded Three.js GLB bones.
 * No menus, no UI. Safe conservative defaults.
 */
(function initPubcastGLBMotionConsumer(global) {
  "use strict";

  const DEG_TO_RAD = Math.PI / 180;
  const DEFAULT_LIMIT_DEG = 35;
  const DEFAULT_OPTIONS = {
    motionScale: 1.0,
    overlayScale: 0.45,
    proceduralScale: 0.55,
    holdScale: 0.35,
    rotationUnit: "degrees",
    maxRotationDeg: DEFAULT_LIMIT_DEG,
    boneAliases: {},
  };

  const CANONICAL_ALIASES = {
    root: ["Root", "root", "Armature", "Armature|Root"],
    hips: ["Pelvis", "Hips", "hips", "Hip", "mixamorigHips", "Armature|Hips"],
    pelvis: ["Pelvis", "Hips", "hips", "mixamorigHips"],
    spine: ["Spine_01", "Spine", "spine", "spine_01", "Spine.001", "mixamorigSpine"],
    spine_01: ["Spine_01", "Spine", "spine_01"],
    spine_02: ["Spine_02", "Chest", "chest", "spine_02", "mixamorigSpine1"],
    chest: ["Spine_03", "Spine_04", "Chest", "chest", "mixamorigSpine2"],
    neck: ["Neck_01", "Neck_02", "Neck", "neck", "mixamorigNeck"],
    head: ["Head", "head", "mixamorigHead"],
    jaw: ["Jaw", "jaw"],
    left_shoulder: ["Clavicle_L", "LeftShoulder", "Shoulder.L", "left_shoulder", "mixamorigLeftShoulder"],
    right_shoulder: ["Clavicle_R", "RightShoulder", "Shoulder.R", "right_shoulder", "mixamorigRightShoulder"],
    left_arm: ["UpperArm_L", "LeftArm", "Upper Arm.L", "left_arm", "mixamorigLeftArm"],
    right_arm: ["UpperArm_R", "RightArm", "Upper Arm.R", "right_arm", "mixamorigRightArm"],
    left_forearm: ["LowerArm_L", "LeftForeArm", "Forearm.L", "left_forearm", "mixamorigLeftForeArm"],
    right_forearm: ["LowerArm_R", "RightForeArm", "Forearm.R", "right_forearm", "mixamorigRightForeArm"],
    left_hand: ["Hand_L", "LeftHand", "Hand.L", "left_hand", "mixamorigLeftHand"],
    right_hand: ["Hand_R", "RightHand", "Hand.R", "right_hand", "mixamorigRightHand"],
    left_leg: ["Thigh_L", "LeftUpLeg", "Upper Leg.L", "left_leg", "mixamorigLeftUpLeg"],
    right_leg: ["Thigh_R", "RightUpLeg", "Upper Leg.R", "right_leg", "mixamorigRightUpLeg"],
    left_knee: ["Calf_L", "LeftLeg", "Lower Leg.L", "left_knee", "mixamorigLeftLeg"],
    right_knee: ["Calf_R", "RightLeg", "Lower Leg.R", "right_knee", "mixamorigRightLeg"],
    left_foot: ["Foot_L", "LeftFoot", "Foot.L", "left_foot", "mixamorigLeftFoot"],
    right_foot: ["Foot_R", "RightFoot", "Foot.R", "right_foot", "mixamorigRightFoot"],
    left_toe: ["Toe_L", "Ball_L", "LeftToeBase", "mixamorigLeftToeBase"],
    right_toe: ["Toe_R", "Ball_R", "RightToeBase", "mixamorigRightToeBase"],
    tail_01: ["Tail_01", "tail_01"],
    tail_02: ["Tail_02", "tail_02"],
    tail_03: ["Tail_03", "tail_03"],
    tail_04: ["Tail_04", "tail_04"],
    tail_05: ["Tail_05", "tail_05"],
  };

  function clamp(value, min, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(min, Math.min(max, n));
  }

  function rotationArrayToRadians(rotation, options, scale) {
    const src = Array.isArray(rotation) ? rotation : [rotation?.x, rotation?.y, rotation?.z];
    const maxDeg = Math.max(1, Number(options.maxRotationDeg || DEFAULT_LIMIT_DEG));
    const unit = options.rotationUnit || "degrees";
    const out = [0, 0, 0];
    for (let i = 0; i < 3; i += 1) {
      const raw = Number(src[i] ?? 0);
      const deg = unit === "radians" ? raw / DEG_TO_RAD : raw;
      out[i] = clamp(deg * scale, -maxDeg, maxDeg) * DEG_TO_RAD;
    }
    return out;
  }

  function collectBones(root) {
    const bones = new Map();
    const stack = [root];
    while (stack.length) {
      const node = stack.pop();
      if (!node) continue;
      if (node.isBone || node.type === "Bone") bones.set(node.name, node);
      const children = node.children || [];
      for (let i = 0; i < children.length; i += 1) stack.push(children[i]);
    }
    return bones;
  }

  class AvatarBinding {
    constructor(avatarId, root, options) {
      this.avatarId = String(avatarId || "");
      this.root = root;
      this.options = Object.assign({}, DEFAULT_OPTIONS, options || {});
      this.bones = collectBones(root);
      this.aliases = Object.assign({}, CANONICAL_ALIASES, this.options.boneAliases || {});
      this.mappedBones = new Map();
      this.missingBones = [];
      this.appliedCommands = 0;
      this.lastError = null;
      this.rebuildMap();
    }

    rebuildMap() {
      this.mappedBones.clear();
      this.missingBones = [];
      for (const [canonical, aliases] of Object.entries(this.aliases)) {
        const bone = this.resolveBone(canonical, aliases);
        if (bone) this.mappedBones.set(canonical, bone);
        else this.missingBones.push(canonical);
      }
      return this.debugStatus();
    }

    resolveBone(canonical, aliases) {
      if (this.bones.has(canonical)) return this.bones.get(canonical);
      for (const name of aliases || []) if (this.bones.has(name)) return this.bones.get(name);
      const lowered = String(canonical).toLowerCase();
      for (const [name, bone] of this.bones.entries()) {
        if (String(name).toLowerCase() === lowered) return bone;
      }
      return null;
    }

    scaleForKind(kind) {
      if (kind === "overlay") return Number(this.options.overlayScale ?? 0.45);
      if (kind === "procedural_animation") return Number(this.options.proceduralScale ?? 0.55);
      if (kind === "hold") return Number(this.options.holdScale ?? 0.35);
      return Number(this.options.motionScale ?? 1.0);
    }

    applyBonePose(boneName, pose, command) {
      const bone = this.mappedBones.get(boneName) || this.resolveBone(boneName, this.aliases[boneName]);
      if (!bone || !pose) return false;
      const scale = this.scaleForKind(command.kind);
      if (pose.rotation !== undefined || pose.x !== undefined || pose.y !== undefined || pose.z !== undefined) {
        const rot = pose.rotation !== undefined ? pose.rotation : [pose.x, pose.y, pose.z];
        const [x, y, z] = rotationArrayToRadians(rot, this.options, scale * Number(command.weight ?? 1));
        if (bone.rotation) {
          bone.rotation.x = x;
          bone.rotation.y = y;
          bone.rotation.z = z;
        }
      }
      return true;
    }

    applyCommand(command) {
      if (!command || typeof command !== "object") return 0;
      const pose = command.pose || command;
      const bones = pose.bones || command.bones || {};
      let applied = 0;
      for (const [boneName, bonePose] of Object.entries(bones)) {
        if (this.applyBonePose(boneName, bonePose, command)) applied += 1;
      }
      this.appliedCommands += applied;
      return applied;
    }

    debugStatus() {
      return {
        avatarId: this.avatarId,
        totalBones: this.bones.size,
        mappedBones: Array.from(this.mappedBones.keys()).sort(),
        mappedBoneCount: this.mappedBones.size,
        missingBones: this.missingBones.slice().sort(),
        appliedCommands: this.appliedCommands,
        lastError: this.lastError,
      };
    }
  }

  const Consumer = {
    bindings: new Map(),
    aliases: CANONICAL_ALIASES,

    registerAvatar(avatarId, root, options) {
      if (!avatarId) throw new Error("registerAvatar requires avatarId");
      if (!root || !root.children) throw new Error("registerAvatar requires a loaded Three.js root scene/group");
      const binding = new AvatarBinding(avatarId, root, options || {});
      this.bindings.set(String(avatarId), binding);
      return binding.debugStatus();
    },

    unregisterAvatar(avatarId) {
      return this.bindings.delete(String(avatarId));
    },

    consumePayload(payload) {
      const avatarId = String(payload?.avatar_id || payload?.avatarId || payload?.target || "");
      const binding = this.bindings.get(avatarId);
      if (!binding) return { ok: false, error: "avatar_not_registered", avatarId };
      const commands = Array.isArray(payload.commands) ? payload.commands : [payload.command || payload];
      let applied = 0;
      try {
        for (const command of commands) applied += binding.applyCommand(command);
        return { ok: true, avatarId, commands: commands.length, applied, status: binding.debugStatus() };
      } catch (err) {
        binding.lastError = err && err.message ? err.message : String(err);
        return { ok: false, error: binding.lastError, avatarId };
      }
    },

    handleEvent(event) {
      return this.consumePayload(event?.detail || event || {});
    },

    debugStatus(avatarId) {
      if (avatarId) return this.bindings.get(String(avatarId))?.debugStatus() || null;
      return Array.from(this.bindings.values()).map((binding) => binding.debugStatus());
    },
  };

  if (global && global.addEventListener) {
    global.addEventListener("pubcast:avatar-motion-commands", (event) => Consumer.handleEvent(event));
    global.addEventListener("avatar_motion_commands", (event) => Consumer.handleEvent(event));
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { PubcastGLBMotionConsumer: Consumer, AvatarBinding, CANONICAL_ALIASES };
  }

  global.PubcastGLBMotionConsumer = Consumer;
})(typeof window !== "undefined" ? window : globalThis);
