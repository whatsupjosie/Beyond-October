const assert = require("assert");
const { StudioConsoleHotspots, buildConfirmModel, readElementPayload, requiresConfirmation } = require("../static/studio_console_hotspots.js");

const calls = [];
const fakeFetch = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith("/api/studio/actions")) {
    return { ok: true, json: async () => ({ actions: [{ action_id: "studio.readiness" }] }) };
  }
  return { ok: true, json: async () => ({ ok: true, action_id: "camera.switch.program", result: { source_id: "medium_shot" } }) };
};

const fakeElement = {
  attributes: [
    { name: "data-studio-param-source-id", value: "medium_shot" },
    { name: "data-studio-param-confirm", value: "yes" },
  ],
  getAttribute(name) {
    if (name === "data-studio-payload") return '{"profile_id":"broadcast_mp4"}';
    return "";
  },
};

(async () => {
  const payload = readElementPayload(fakeElement);
  assert.strictEqual(payload.profile_id, "broadcast_mp4");
  assert.strictEqual(payload.sourceId, "medium_shot");
  assert.strictEqual(payload.confirm, "yes");
  assert.strictEqual(requiresConfirmation("recording.start", null, null), true);
  assert.strictEqual(requiresConfirmation("audio.stop_all", null, null), false);
  assert.strictEqual(buildConfirmModel("recording.stop", { session_id: "rec1" }, { label: "Stop recording" }).details[0], "Session: rec1");

  const confirmedClient = new StudioConsoleHotspots({ fetchImpl: fakeFetch, confirmImpl: async () => true });
  const canceledClient = new StudioConsoleHotspots({ fetchImpl: fakeFetch, confirmImpl: async () => false });
  const client = confirmedClient;
  const actions = await client.actions();
  const result = await client.execute("camera.switch.program", { source_id: "medium_shot" });
  const confirmed = await client.executeConfirmed("recording.start", { session_id: "rec1" }, { spec: { safety: "confirm", label: "Start recording" } });
  const canceled = await canceledClient.executeConfirmed("recording.start", { session_id: "rec2" }, { spec: { safety: "confirm", label: "Start recording" } });

  assert.strictEqual(actions[0].action_id, "studio.readiness");
  assert.strictEqual(result.result.source_id, "medium_shot");
  assert.strictEqual(confirmed.ok, true);
  assert.strictEqual(canceled.canceled, true);
  assert.strictEqual(calls[0].url, "/api/studio/actions");
  assert.strictEqual(calls[1].url, "/api/studio/actions/camera.switch.program");
  assert.strictEqual(JSON.parse(calls[1].options.body).source_id, "medium_shot");
  assert.strictEqual(calls[2].url, "/api/studio/actions/recording.start");
  assert.strictEqual(JSON.parse(calls[2].options.body).confirm, true);
  console.log("test_studio_console_hotspots_node.js passed");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
