/*
 * PubCast Voxel Block Preview Client
 * Quiet browser bridge for dry-run PubBlock and visual-patch voxel previews.
 * No menus, no UI, no persistence. It only calls read-only/preview endpoints.
 */
(function initPubcastVoxelBlockPreview(global) {
  "use strict";

  const DEFAULT_ENDPOINTS = {
    capabilities: "/api/voxel/block-kit/preview/capabilities",
    preview: "/api/voxel/block-kit/preview",
  };

  function cleanKind(kind) {
    return String(kind || "stage_floor").trim().toLowerCase().replace(/-/g, "_");
  }

  function ensureObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  class VoxelBlockPreviewClient {
    constructor(options = {}) {
      this.endpoints = Object.assign({}, DEFAULT_ENDPOINTS, options.endpoints || {});
      this.fetchImpl = options.fetchImpl || global.fetch?.bind(global);
      this.lastPreview = null;
      this.lastCapabilities = null;
      this.lastError = null;
    }

    async capabilities() {
      const data = await this._request(this.endpoints.capabilities, { method: "GET" });
      this.lastCapabilities = data;
      this._emit("pubcast:voxel-block-preview-capabilities", data);
      return data;
    }

    async preview(kind = "stage_floor", params = {}) {
      const payload = { kind: cleanKind(kind), params: ensureObject(params) };
      const data = await this._request(this.endpoints.preview, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      this.lastPreview = data;
      this._emit("pubcast:voxel-block-preview", data);
      return data;
    }

    status() {
      return {
        available: typeof this.fetchImpl === "function",
        endpoints: Object.assign({}, this.endpoints),
        hasLastPreview: !!this.lastPreview,
        hasCapabilities: !!this.lastCapabilities,
        lastError: this.lastError,
      };
    }

    async _request(url, options) {
      if (typeof this.fetchImpl !== "function") {
        this.lastError = "fetch unavailable";
        throw new Error(this.lastError);
      }
      const response = await this.fetchImpl(url, options || {});
      const data = await response.json();
      if (!response.ok) {
        this.lastError = data?.detail || data?.error || `HTTP ${response.status}`;
        throw new Error(this.lastError);
      }
      this.lastError = null;
      return data;
    }

    _emit(name, detail) {
      if (!global || typeof global.dispatchEvent !== "function" || typeof global.CustomEvent !== "function") return;
      global.dispatchEvent(new global.CustomEvent(name, { detail }));
    }
  }

  const client = new VoxelBlockPreviewClient();
  global.PubcastVoxelBlockPreview = client;

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { VoxelBlockPreviewClient, DEFAULT_ENDPOINTS };
  }
})(typeof window !== "undefined" ? window : globalThis);