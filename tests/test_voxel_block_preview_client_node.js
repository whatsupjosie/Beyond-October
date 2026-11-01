const assert = require("assert");
const { VoxelBlockPreviewClient } = require("../static/voxel_block_preview_client.js");

const calls = [];
const fakeFetch = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.includes("capabilities")) {
    return { ok: true, status: 200, json: async () => ({ available: true, read_only: true, supported_previews: ["stage_floor"] }) };
  }
  return { ok: true, status: 200, json: async () => ({ ok: true, read_only: true, saved: false, preview_kind: "stage_floor" }) };
};

(async () => {
  const client = new VoxelBlockPreviewClient({ fetchImpl: fakeFetch });
  const caps = await client.capabilities();
  assert.strictEqual(caps.available, true);
  const preview = await client.preview("stage-floor", { width: 2, depth: 2 });
  assert.strictEqual(preview.saved, false);
  assert.strictEqual(client.status().hasLastPreview, true);
  assert.strictEqual(calls[0].url, "/api/voxel/block-kit/preview/capabilities");
  assert.strictEqual(calls[1].url, "/api/voxel/block-kit/preview");
  const body = JSON.parse(calls[1].options.body);
  assert.strictEqual(body.kind, "stage_floor");
  assert.deepStrictEqual(body.params, { width: 2, depth: 2 });
  console.log("test_voxel_block_preview_client_node.js passed");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});