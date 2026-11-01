// PubCast AI — avatar.js
// Compatibility bridge for legacy pages. Maintained implementation: avatar_glow.js.
(function () {
  const modulePath = "/static/avatar_glow.js";
  window.__pubcastAvatarModuleReady = false;
  window.__pubcastAvatarModuleReason = "loading " + modulePath;
  import(modulePath).then((mod) => {
    if (typeof mod.HolographicAvatarSystem !== "function") {
      throw new Error("avatar_glow.js did not export HolographicAvatarSystem");
    }
    window.HolographicAvatarSystem = mod.HolographicAvatarSystem;
    if (mod.StandaloneAvatarRenderer) window.StandaloneAvatarRenderer = mod.StandaloneAvatarRenderer;
    window.__pubcastAvatarModuleReady = true;
    window.__pubcastAvatarModuleReason = "ready";
  }).catch((error) => {
    window.__pubcastAvatarModuleReady = false;
    window.__pubcastAvatarModuleReason = String(error && error.message ? error.message : error);
    console.error("PubCast avatar compatibility loader failed", error);
  });
})();
