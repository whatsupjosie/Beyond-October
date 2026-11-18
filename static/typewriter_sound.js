/*
 * Typewriter sound for the typewriter hotspots.
 *
 * Every key heard on the "pubcast:key" event gets its own strike: a letter
 * key, the heavier space bar, the softer shift, backspace, and the carriage
 * return (ratchet then clunk). The page can also ring the margin bell.
 * Sound is optional: a button marked [data-typewriter-sound] turns it on and
 * off, and the choice is kept in this browser.
 *
 * The sounds are made in the browser with Web Audio, from noise and tones, so
 * nothing is downloaded and the page works offline. The repo's foley manifest
 * names a typewriter_click_01.wav, but that file is not in the repository or
 * in Drive (checked 2026-11-17), so it cannot be used.
 *
 * Timing: a strike is scheduled at the moment the key goes down. Browsers only
 * let sound start after a touch is lifted (a mouse press or a key press is
 * enough), so on a touch screen the very first key of a visit sounds a moment
 * late; every key after it is on time.
 */
(function () {
  "use strict";

  const STORE_KEY = "pubcast.typewriter.sound";
  const MASTER_LEVEL = 0.55;

  let enabled = readPreference();
  let ctx = null;
  let master = null;
  let played = 0;
  let lastKind = "";

  function readPreference() {
    try {
      const stored = localStorage.getItem(STORE_KEY);
      if (stored === "on" || stored === "off") return stored === "on";
      const embedded = new URLSearchParams(location.search).get("embedded") === "2i";
      if (embedded) {
        // Respect the older 2i click/bell preference when upgrading to Claude's sound system.
        const old = JSON.parse(localStorage.getItem("twoi.typewriter.audio.v1") || "null");
        return Boolean(old && (old.click === true || old.bell === true));
      }
      return true; // Claude's standalone console retains its original default.
    } catch (_err) {
      // Blocked or corrupt storage must not switch embedded 2i audio on.
      return new URLSearchParams(location.search).get("embedded") !== "2i";
    }
  }

  function writePreference(on) {
    try {
      localStorage.setItem(STORE_KEY, on ? "on" : "off");
    } catch (_err) {
      /* storage blocked: the choice lasts for this visit only */
    }
  }

  // Fixed-seed white noise: the raw material of every strike.
  function makeNoise(audio) {
    const length = Math.floor(audio.sampleRate * 0.25);
    const buffer = audio.createBuffer(1, length, audio.sampleRate);
    const data = buffer.getChannelData(0);
    let seed = 0x2545f491;
    for (let i = 0; i < length; i += 1) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      data[i] = seed / 0x3fffffff - 1;
    }
    return buffer;
  }

  const noiseFor = new WeakMap();
  function noiseOf(audio) {
    if (!noiseFor.has(audio)) noiseFor.set(audio, makeNoise(audio));
    return noiseFor.get(audio);
  }

  function envelope(audio, t, peak, attack, decay) {
    const gain = audio.createGain();
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0002), t + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay);
    return gain;
  }

  function noiseBurst(audio, out, t, filterType, frequency, q, peak, decay) {
    const source = audio.createBufferSource();
    source.buffer = noiseOf(audio);
    const filter = audio.createBiquadFilter();
    filter.type = filterType;
    filter.frequency.value = frequency;
    filter.Q.value = q;
    const gain = envelope(audio, t, peak, 0.0015, decay);
    source.connect(filter).connect(gain).connect(out);
    source.start(t, Math.random() * 0.15);
    source.stop(t + 0.0015 + decay + 0.02);
  }

  function thock(audio, out, t, frequency, peak, decay) {
    const osc = audio.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(frequency * 1.35, t);
    osc.frequency.exponentialRampToValueAtTime(frequency, t + 0.02);
    const gain = envelope(audio, t, peak, 0.002, decay);
    osc.connect(gain).connect(out);
    osc.start(t);
    osc.stop(t + 0.002 + decay + 0.02);
  }

  // One strike: the typebar's click, the bright snap of metal and the thock
  // of the key reaching the bottom. vary keeps repeated keys from sounding
  // machine-identical.
  function strike(audio, out, t, tone, body, level, vary) {
    noiseBurst(audio, out, t, "bandpass", tone * vary, 1.4, level, 0.034);
    noiseBurst(audio, out, t, "highpass", 4200, 0.7, level * 0.45, 0.012);
    thock(audio, out, t + 0.004, body * vary, level * 0.6, 0.06);
  }

  const voices = {
    key(audio, out, t, vary) { strike(audio, out, t, 2300, 165, 0.9, vary); },
    space(audio, out, t, vary) {
      strike(audio, out, t, 1150, 95, 0.95, vary);
      thock(audio, out, t + 0.01, 70 * vary, 0.5, 0.11);
    },
    shift(audio, out, t, vary) { strike(audio, out, t, 1500, 120, 0.55, vary); },
    backspace(audio, out, t, vary) { strike(audio, out, t, 1750, 140, 0.7, vary); },
    // The carriage running back: a ratchet that slows, then the clunk home.
    return(audio, out, t, vary) {
      for (let i = 0; i < 8; i += 1) {
        noiseBurst(audio, out, t + i * 0.026 + i * i * 0.0015, "bandpass", 3100 * vary, 2.2, 0.42 - i * 0.03, 0.01);
      }
      strike(audio, out, t + 0.27, 900, 78, 1.0, vary);
    },
    // The margin bell: a small brass bell, two slightly unrelated partials.
    bell(audio, out, t) {
      [[2093, 0.22], [5290, 0.07]].forEach(([frequency, peak]) => {
        const osc = audio.createOscillator();
        osc.type = "sine";
        osc.frequency.value = frequency;
        const gain = envelope(audio, t, peak, 0.003, 1.3);
        osc.connect(gain).connect(out);
        osc.start(t);
        osc.stop(t + 1.35);
      });
    },
  };

  function kindFor(char) {
    if (char === "SPACE") return "space";
    if (char === "RETURN") return "return";
    if (char === "SHIFT") return "shift";
    if (char === "BACKSPACE") return "backspace";
    return "key";
  }

  function ensureContext() {
    if (ctx) return ctx;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    ctx = new AudioCtx({ latencyHint: "interactive" });
    // Many quick keys stack up; the limiter keeps a burst from clipping.
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -9;
    limiter.knee.value = 6;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.002;
    limiter.release.value = 0.08;
    master = ctx.createGain();
    master.gain.value = MASTER_LEVEL;
    master.connect(limiter).connect(ctx.destination);
    return ctx;
  }

  function wake() {
    if (!enabled) return;
    const audio = ensureContext();
    if (audio && audio.state === "suspended") audio.resume().catch(() => {});
  }

  function play(kind) {
    if (!enabled || !voices[kind]) return false;
    const audio = ensureContext();
    if (!audio) return false;
    if (audio.state === "suspended") audio.resume().catch(() => {});
    voices[kind](audio, master, audio.currentTime + 0.002, 0.94 + Math.random() * 0.12);
    played += 1;
    lastKind = kind;
    return true;
  }

  function setEnabled(on) {
    enabled = Boolean(on);
    writePreference(enabled);
    if (enabled) wake();
    else if (ctx && ctx.state === "running") ctx.suspend().catch(() => {});
    syncButtons();
  }

  function syncButtons() {
    document.querySelectorAll("[data-typewriter-sound]").forEach((button) => {
      button.setAttribute("aria-pressed", String(enabled));
      button.textContent = enabled ? "Sound on" : "Sound off";
    });
  }

  document.addEventListener("pubcast:key", (event) => {
    play(kindFor(event.detail && event.detail.char));
  });

  // The gestures that let a browser start sound. Touch only counts once the
  // finger lifts, which is why pointerup and touchend are here.
  ["pointerup", "touchend", "keydown", "mousedown"].forEach((name) => {
    document.addEventListener(name, wake, { capture: true, passive: true });
  });

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-typewriter-sound]").forEach((button) => {
      button.addEventListener("click", () => setEnabled(!enabled));
    });
    syncButtons();
  });

  window.PubCastTypewriterSound = {
    bell: () => play("bell"),
    isEnabled: () => enabled,
    setEnabled: setEnabled,
    status: () => ({ enabled: enabled, played: played, lastKind: lastKind, state: ctx ? ctx.state : "none" }),
    voices: voices,
  };
})();
