/*
 * PubCast studio console hotspot adapter.
 *
 * This creates no visible UI. It lets future console art bind click/touch
 * hotspots to stable backend studio action IDs.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.PubCastStudioConsoleHotspots = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  "use strict";

  function parseJsonObject(value, fallback) {
    if (!value) return fallback || {};
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback || {};
    } catch (_err) {
      return fallback || {};
    }
  }

  function readElementPayload(element) {
    const payload = parseJsonObject(element.getAttribute("data-studio-payload"), {});
    const attrs = element.attributes || [];
    for (let index = 0; index < attrs.length; index += 1) {
      const attr = attrs[index];
      if (!attr || !attr.name || !attr.name.startsWith("data-studio-param-")) continue;
      const key = attr.name.slice("data-studio-param-".length).replace(/-([a-z])/g, function (_match, char) {
        return char.toUpperCase();
      });
      payload[key] = attr.value;
    }
    return payload;
  }

  function emitTargetEvent(target, name, detail) {
    if (!target || typeof target.dispatchEvent !== "function" || typeof CustomEvent !== "function") return;
    target.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail }));
  }

  function requiresConfirmation(actionId, element, spec) {
    const attr = element && typeof element.getAttribute === "function"
      ? String(element.getAttribute("data-studio-confirm") || "").toLowerCase()
      : "";
    if (attr === "false" || attr === "off" || attr === "0") return false;
    if (attr === "true" || attr === "yes" || attr === "1") return true;
    if (spec && spec.safety === "confirm") return true;
    return actionId === "recording.start" || actionId === "recording.stop";
  }

  function buildConfirmModel(actionId, payload, spec) {
    const label = spec && spec.label ? spec.label : actionId;
    const sources = Array.isArray(payload && payload.sources) ? payload.sources.join(", ") : "";
    const details = [];
    if (payload && payload.session_id) details.push("Session: " + payload.session_id);
    if (payload && payload.source_id) details.push("Source: " + payload.source_id);
    if (sources) details.push("Sources: " + sources);
    return {
      actionId: actionId,
      label: label,
      title: actionId === "recording.stop" ? "Stop Recording" : "Confirm Studio Action",
      message: "Confirm " + label + ".",
      details: details,
      confirmText: actionId === "recording.stop" ? "Stop" : "Confirm",
      cancelText: "Cancel",
    };
  }

  function defaultConfirm(model) {
    if (typeof document === "undefined") return Promise.resolve(true);
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "pubcast-studio-confirm";
      overlay.innerHTML = [
        '<div class="pubcast-studio-confirm__panel" role="dialog" aria-modal="true">',
        '<div class="pubcast-studio-confirm__eyebrow">Studio Control</div>',
        '<h2>' + escapeHtml(model.title) + "</h2>",
        '<p>' + escapeHtml(model.message) + "</p>",
        model.details.length ? '<ul>' + model.details.map((item) => '<li>' + escapeHtml(item) + "</li>").join("") + "</ul>" : "",
        '<div class="pubcast-studio-confirm__actions">',
        '<button type="button" data-confirm-cancel>' + escapeHtml(model.cancelText) + "</button>",
        '<button type="button" data-confirm-ok>' + escapeHtml(model.confirmText) + "</button>",
        "</div>",
        "</div>",
      ].join("");
      ensureConfirmStyles();
      document.body.appendChild(overlay);
      const done = (value) => {
        document.removeEventListener("keydown", onKey);
        overlay.remove();
        resolve(value);
      };
      const onKey = (event) => {
        if (event.key === "Escape") done(false);
        if (event.key === "Enter") done(true);
      };
      overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => done(false));
      overlay.querySelector("[data-confirm-ok]").addEventListener("click", () => done(true));
      document.addEventListener("keydown", onKey);
      overlay.querySelector("[data-confirm-ok]").focus();
    });
  }

  function ensureConfirmStyles() {
    if (typeof document === "undefined" || document.getElementById("pubcast-studio-confirm-styles")) return;
    const style = document.createElement("style");
    style.id = "pubcast-studio-confirm-styles";
    style.textContent = [
      ".pubcast-studio-confirm{position:fixed;inset:0;z-index:9999;display:grid;place-items:center;background:rgba(3,4,8,.72);backdrop-filter:blur(8px);padding:18px}",
      ".pubcast-studio-confirm__panel{width:min(420px,100%);background:#101217;color:#f4efe2;border:1px solid rgba(232,255,71,.38);border-radius:8px;padding:20px;box-shadow:0 24px 80px rgba(0,0,0,.55);font-family:Segoe UI,system-ui,sans-serif}",
      ".pubcast-studio-confirm__eyebrow{font:700 11px Consolas,monospace;letter-spacing:.16em;text-transform:uppercase;color:#e8ff47;margin-bottom:10px}",
      ".pubcast-studio-confirm h2{font-size:22px;line-height:1.15;margin:0 0 10px}",
      ".pubcast-studio-confirm p{margin:0 0 12px;color:#c9d0dc;line-height:1.4}",
      ".pubcast-studio-confirm ul{margin:0 0 16px;padding-left:18px;color:#9ca3af;font:12px Consolas,monospace}",
      ".pubcast-studio-confirm__actions{display:flex;justify-content:flex-end;gap:10px}",
      ".pubcast-studio-confirm button{border:1px solid #343a46;background:#181c24;color:#f4efe2;border-radius:6px;padding:9px 13px;font-weight:700;cursor:pointer}",
      ".pubcast-studio-confirm button[data-confirm-ok]{border-color:#ff6b6b;background:rgba(255,107,107,.18);color:#ffd2d2}",
      ".pubcast-studio-confirm button:focus{outline:2px solid #47c8ff;outline-offset:2px}",
    ].join("");
    document.head.appendChild(style);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  class StudioConsoleHotspots {
    constructor(options) {
      const config = options || {};
      this.fetchImpl = config.fetchImpl || (typeof fetch === "function" ? fetch.bind(globalThis) : null);
      this.baseUrl = String(config.baseUrl || "").replace(/\/$/, "");
      this.confirmImpl = config.confirmImpl || defaultConfirm;
      this._actionsPromise = null;
      this.lastAction = null;
    }

    async actions() {
      const response = await this._fetch("/api/studio/actions", { method: "GET" });
      return response.actions || [];
    }

    async actionSpec(actionId) {
      this._actionsPromise = this._actionsPromise || this.actions().catch(() => []);
      const actions = await this._actionsPromise;
      return actions.find((item) => item.action_id === actionId) || null;
    }

    async execute(actionId, payload) {
      const cleanActionId = String(actionId || "").trim();
      if (!cleanActionId) throw new Error("studio action_id is required");
      const response = await this._fetch("/api/" + "studio/actions/" + encodeURIComponent(cleanActionId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
      this.lastAction = response;
      return response;
    }

    async executeConfirmed(actionId, payload, context) {
      const body = Object.assign({}, payload || {});
      const spec = (context && context.spec) || await this.actionSpec(actionId);
      if (requiresConfirmation(actionId, context && context.element, spec)) {
        const approved = await this.confirmImpl(buildConfirmModel(actionId, body, spec));
        if (!approved) {
          return { ok: false, canceled: true, action_id: actionId };
        }
        body.confirm = true;
      }
      return this.execute(actionId, body);
    }

    bind(rootElement) {
      const rootNode = rootElement || (typeof document !== "undefined" ? document : null);
      if (!rootNode || typeof rootNode.querySelectorAll !== "function") return 0;
      const nodes = rootNode.querySelectorAll("[data-studio-action]");
      nodes.forEach((node) => {
        if (node.__pubcastStudioHotspotBound) return;
        node.__pubcastStudioHotspotBound = true;
        node.addEventListener("click", async (event) => {
          event.preventDefault();
          const actionId = node.getAttribute("data-studio-action");
          const payload = readElementPayload(node);
          emitTargetEvent(node, "pubcast:studio-action-start", { actionId: actionId, payload: payload });
          try {
            const result = await this.executeConfirmed(actionId, payload, { element: node });
            if (result && result.canceled) {
              emitTargetEvent(node, "pubcast:studio-action-cancel", { actionId: actionId, payload: payload });
              return;
            }
            emitTargetEvent(node, "pubcast:studio-action-success", { actionId: actionId, payload: payload, result: result });
          } catch (err) {
            emitTargetEvent(node, "pubcast:studio-action-error", {
              actionId: actionId,
              payload: payload,
              message: err && err.message ? err.message : String(err),
            });
          }
        });
      });
      return nodes.length;
    }

    async _fetch(path, options) {
      if (!this.fetchImpl) throw new Error("fetch is not available for studio console hotspots");
      const response = await this.fetchImpl(this.baseUrl + path, options || {});
      const data = response && typeof response.json === "function" ? await response.json() : {};
      if (!response || !response.ok) {
        const message = data && data.detail ? data.detail : "Studio console request failed";
        throw new Error(message);
      }
      return data;
    }
  }

  return {
    StudioConsoleHotspots: StudioConsoleHotspots,
    buildConfirmModel: buildConfirmModel,
    readElementPayload: readElementPayload,
    requiresConfirmation: requiresConfirmation,
  };
});
