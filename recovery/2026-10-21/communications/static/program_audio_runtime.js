/*
 * PubCast Program Audio Runtime
 * Lightweight browser mixer for dialogue, music, SFX, UI sounds, VTR, and spatial/proximity cues.
 * It does not autoplay by itself; audio starts only after caller/user action.
 */
(function initProgramAudio(global) {
  "use strict";

  const roomId = value => ({control: "controlroom", waiting_room: "waitingroom"}[value] || value);
  const announcementMedia = new WeakSet();
  const DEFAULT_BUS = { volume: 1, muted: false };
  const BUS_NAMES = ["dialogue", "music", "sfx", "ui", "vtr", "room"];

  function clamp(value, min, max, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  }

  class ProgramAudioRuntime {
    constructor(options = {}) {
      this.options = Object.assign({ maxDistance: 18, duckMusicTo: 0.35 }, options);
      this.context = null;
      this.master = null;
      this.buses = new Map();
      this.active = new Set();
      this.dialogueActive = 0;
      this.lastError = null;
      this.room = roomId(options.room || "controlroom");
      this.externalStops = new Set();
      this.seenCommands = new Set();
    }

    setRoom(room) {
      this.room = roomId(String(room || 'controlroom'));
      if (this.room === 'dressing') {
        this.stopAll();
        global.document?.querySelectorAll('audio,video').forEach(media => media.pause());
      }
    }

    allowed(options = {}) {
      return this.room !== 'dressing' || options.directorAnnouncement === true;
    }

    async consume(event) {
      if (event.event_id) {
        if (this.seenCommands.has(event.event_id)) return {duplicate: true};
        this.seenCommands.add(event.event_id);
        if (this.seenCommands.size > 512) this.seenCommands.delete(this.seenCommands.values().next().value);
      }
      if (event.action === 'disable_tts_autoplay') {
        global.tts?.setAutoplay(false); return;
      }
      if (event.room && roomId(event.room) !== this.room) return {skipped: true};
      const options = Object.assign({}, event, {directorAnnouncement: event.authorized_director === true});
      if (event.action === 'stop_all') return this.stopAll();
      if (event.action === 'stop') {
        for (const handle of Array.from(this.active)) if (handle.busName === event.bus) this.stopHandle(handle);
        return;
      }
      if (event.action === 'mute' || event.action === 'unmute') return this.setMuted(event.bus, event.action === 'mute');
      if (event.action === 'set_volume') return this.setBusVolume(event.bus, event.volume);
      if (event.action === 'play') {
        if (!this.allowed(options)) return {blocked: true};
        if (event.url) return this.playUrl(event.url, options);
        throw new Error('A playable audio URL is required');
      }
    }

    ensureContext() {
      if (this.context) return this.context;
      const AudioContextCtor = global.AudioContext || global.webkitAudioContext;
      if (!AudioContextCtor) throw new Error("Web Audio API unavailable");
      this.context = new AudioContextCtor();
      this.master = this.context.createGain();
      this.master.gain.value = 1;
      this.master.connect(this.context.destination);
      for (const name of BUS_NAMES) this.createBus(name);
      return this.context;
    }

    createBus(name) {
      const ctx = this.context;
      if (!ctx) return null;
      if (this.buses.has(name)) return this.buses.get(name);
      const gain = ctx.createGain();
      gain.gain.value = DEFAULT_BUS.volume;
      gain.connect(this.master);
      const bus = Object.assign({ name, gain, sources: new Set() }, DEFAULT_BUS);
      this.buses.set(name, bus);
      return bus;
    }

    setBusVolume(name, volume) {
      this.ensureContext();
      const bus = this.createBus(name);
      bus.volume = clamp(volume, 0, 1, 1);
      bus.gain.gain.value = bus.muted ? 0 : this.effectiveVolume(name);
      return bus.gain.gain.value;
    }

    setMuted(name, muted) {
      this.ensureContext();
      const bus = this.createBus(name);
      bus.muted = !!muted;
      if (name === "dialogue" && muted) { for (const stop of this.externalStops) stop(); global.speechSynthesis?.cancel?.(); }
      bus.gain.gain.value = bus.muted ? 0 : this.effectiveVolume(name);
      return bus.muted;
    }

    effectiveVolume(name) {
      const bus = this.buses.get(name);
      if (!bus) return 1;
      if (name === "music" && this.dialogueActive > 0) return bus.volume * this.options.duckMusicTo;
      return bus.volume;
    }

    updateDucking() {
      const music = this.buses.get("music");
      if (music) music.gain.gain.value = music.muted ? 0 : this.effectiveVolume("music");
    }

    spatialGain(listener, source, baseVolume = 1) {
      const lx = Number(listener?.x ?? 0), ly = Number(listener?.y ?? 0), lz = Number(listener?.z ?? 0);
      const sx = Number(source?.x ?? 0), sy = Number(source?.y ?? 0), sz = Number(source?.z ?? 0);
      const distance = Math.hypot(sx - lx, sy - ly, sz - lz);
      const maxDistance = Math.max(1, Number(this.options.maxDistance || 18));
      const volume = clamp(baseVolume, 0, 1, 1) * Math.max(0, 1 - distance / maxDistance);
      const pan = clamp((sx - lx) / maxDistance, -1, 1, 0);
      return { distance, volume, pan };
    }

    async playUrl(url, options = {}) {
      if (!this.allowed(options)) throw new Error('Dressing room permits direct director announcements only');
      this.ensureContext();
      await this.context.resume();
      const busName = options.bus || "sfx";
      const bus = this.createBus(busName);
      const audio = new Audio(url);
      if (options.directorAnnouncement) announcementMedia.add(audio);
      audio.crossOrigin = options.crossOrigin || "anonymous";
      audio.loop = !!options.loop;
      const source = this.context.createMediaElementSource(audio);
      const gain = this.context.createGain();
      gain.gain.value = clamp(options.volume, 0, 1, 1);
      let lastNode = source;
      let panner = null;
      if (options.spatial && this.context.createStereoPanner) {
        panner = this.context.createStereoPanner();
        const sg = this.spatialGain(options.listener, options.position, gain.gain.value);
        gain.gain.value = sg.volume;
        panner.pan.value = sg.pan;
        lastNode.connect(panner);
        lastNode = panner;
      }
      lastNode.connect(gain);
      gain.connect(bus.gain);
      const handle = { audio, source, gain, panner, busName, directorAnnouncement: options.directorAnnouncement === true, stop: () => this.stopHandle(handle) };
      this.active.add(handle);
      bus.sources.add(handle);
      if (busName === "dialogue") {
        this.dialogueActive += 1;
        this.updateDucking();
      }
      audio.onended = () => this.stopHandle(handle);
      try { await audio.play(); return handle; }
      catch (error) { this.lastError = error.message; this.stopHandle(handle); throw error; }
    }

    playUISound(kind = "click") {
      if (!this.allowed()) return null;
      this.ensureContext();
      const osc = this.context.createOscillator();
      const gain = this.context.createGain();
      const bus = this.createBus("ui");
      const frequency = kind === "error" ? 180 : kind === "confirm" ? 660 : 420;
      osc.frequency.value = frequency;
      gain.gain.value = 0.045;
      osc.connect(gain);
      gain.connect(bus.gain);
      osc.start();
      osc.stop(this.context.currentTime + 0.055);
      const handle = { oscillator: osc, gain, busName: "ui", stop: () => this.stopHandle(handle) };
      this.active.add(handle);
      bus.sources.add(handle);
      osc.onended = () => this.stopHandle(handle);
      return handle;
    }

    stopHandle(handle) {
      if (!handle || !this.active.has(handle)) return false;
      try { handle.audio?.pause?.(); } catch (_) {}
      try { handle.oscillator?.stop?.(); } catch (_) {}
      try { handle.source?.disconnect?.(); } catch (_) {}
      try { handle.gain?.disconnect?.(); } catch (_) {}
      try { handle.panner?.disconnect?.(); } catch (_) {}
      handle.onStop?.();
      this.active.delete(handle);
      const bus = this.buses.get(handle.busName);
      if (bus) bus.sources.delete(handle);
      if (handle.busName === "dialogue") {
        this.dialogueActive = Math.max(0, this.dialogueActive - 1);
        this.updateDucking();
      }
      return true;
    }

    stopAll() {
      const handles = Array.from(this.active);
      for (const handle of handles) this.stopHandle(handle);
      for (const stop of this.externalStops) stop();
      global.speechSynthesis?.cancel?.();
      this.dialogueActive = 0;
      this.updateDucking();
      return handles.length;
    }

    status() {
      const buses = {};
      for (const [name, bus] of this.buses.entries()) {
        buses[name] = { volume: bus.volume, muted: bus.muted, activeSources: bus.sources.size };
      }
      return {
        available: !!(global.AudioContext || global.webkitAudioContext),
        contextState: this.context?.state || "not_started",
        activeSources: this.active.size,
        dialogueActive: this.dialogueActive,
        buses,
        lastError: this.lastError,
      };
    }
  }

  const runtime = new ProgramAudioRuntime();
  global.PubcastProgramAudio = runtime;
  if (global.HTMLMediaElement) {
    const nativePlay = global.HTMLMediaElement.prototype.play;
    global.HTMLMediaElement.prototype.play = function (...args) {
      if (!runtime.allowed() && !announcementMedia.has(this)) return Promise.reject(new Error('Room audio blocked'));
      return nativePlay.apply(this, args);
    };
  }
  if (global.speechSynthesis) {
    const nativeSpeak = global.speechSynthesis.speak.bind(global.speechSynthesis);
    global.speechSynthesis.speak = utterance => {
      if (runtime.allowed() && !runtime.buses.get("dialogue")?.muted) nativeSpeak(utterance);
      else utterance.dispatchEvent?.(new Event('error'));
    };
  }
  if (global.location) {
    if (/dressing/.test(global.location.pathname)) runtime.setRoom('dressing');
    else if (/stage/.test(global.location.pathname)) runtime.setRoom(new URLSearchParams(global.location.search).get('room') || 'studio');
    let cursor = -1, polling = false, closed = false;
    async function commands() {
      if (polling || closed) return;
      polling = true;
      try {
        const response = await global.fetch('/api/program-audio/events?after=' + cursor);
        if (!response.ok) throw new Error('Audio commands HTTP ' + response.status);
        const result = await response.json();
        cursor = result.sequence;
        if (result.gap) {runtime.stopAll(); runtime.lastError = 'Audio command gap; stale playback stopped';}
        for (const event of result.events) {
          try {await runtime.consume(event);} catch (error) {runtime.lastError = error.message;}
        }
      } catch (error) {runtime.lastError = error.message;}
      finally {polling = false; if (!closed) global.setTimeout(commands, 1000);}
    }
    if (global.document?.readyState === 'loading') global.document.addEventListener('DOMContentLoaded', commands);
    else commands();
    global.addEventListener('pagehide', () => {closed = true; runtime.stopAll();});
    global.addEventListener('pubcast:room', event => runtime.setRoom(event.detail.room));
    global.addEventListener('pubcast:server-event', event => {
      if (event.detail.type === 'program_audio') runtime.consume(event.detail.payload).catch(error => {runtime.lastError = error.message;});
    });
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { ProgramAudioRuntime };
  }
})(typeof window !== "undefined" ? window : globalThis);
