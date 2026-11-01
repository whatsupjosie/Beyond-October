const assert = require("assert");
const { ProgramAudioRuntime } = require("../static/program_audio_runtime.js");

const runtime = new ProgramAudioRuntime({ maxDistance: 10, duckMusicTo: 0.25 });
const near = runtime.spatialGain({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 0 }, 1);
const far = runtime.spatialGain({ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }, 1);
assert(near.volume > far.volume);
assert.strictEqual(far.pan, 1);
assert.strictEqual(runtime.stopAll(), 0);
assert.strictEqual(runtime.status().activeSources, 0);
console.log("test_program_audio_runtime_node.js passed");
