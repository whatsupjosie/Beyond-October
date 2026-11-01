const assert = require("assert");
const { PubcastGLBMotionConsumer } = require("../static/avatar_glb_motion_consumer.js");

function bone(name) {
  return { name, type: "Bone", isBone: true, rotation: { x: 123, y: 123, z: 123 }, children: [] };
}

function rootWithBones(names) {
  return { name: "root", children: names.map(bone) };
}

function near(actual, expected, epsilon = 1e-6) {
  assert(Math.abs(actual - expected) < epsilon, `${actual} != ${expected}`);
}

PubcastGLBMotionConsumer.bindings.clear();
const root = rootWithBones(["Root", "Pelvis", "Spine_01", "Head", "UpperArm_L"]);
const status = PubcastGLBMotionConsumer.registerAvatar("manny", root, { maxRotationDeg: 35 });
assert(status.mappedBoneCount >= 4);

let result = PubcastGLBMotionConsumer.consumePayload({
  avatar_id: "manny",
  commands: [{
    kind: "mocap_pose",
    weight: 1,
    pose: { bones: { head: { rotation: [10, 5, 0] }, spine: { rotation: [0, 4, 0] } } },
  }],
});
assert.strictEqual(result.ok, true);
assert.strictEqual(result.applied, 2);
near(root.children.find((b) => b.name === "Head").rotation.z, 0);
near(root.children.find((b) => b.name === "Spine_01").rotation.x, 0);

result = PubcastGLBMotionConsumer.consumePayload({
  avatar_id: "manny",
  commands: [{ kind: "overlay", pose: { bones: { unknown_bone: { rotation: [30, 30, 30] } } } }],
});
assert.strictEqual(result.ok, true);
assert.strictEqual(result.applied, 0);

result = PubcastGLBMotionConsumer.consumePayload({ avatar_id: "missing", commands: [] });
assert.strictEqual(result.ok, false);
assert.strictEqual(result.error, "avatar_not_registered");

console.log("test_avatar_glb_motion_consumer_node.js passed");
