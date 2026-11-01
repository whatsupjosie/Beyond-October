(function () {
  'use strict';

  class PubcastFoleyEngine {
    constructor(manifestUrl = '/static/foley_manifest.json') {
      this.manifestUrl = manifestUrl;
      this.ctx = null;
      this.masterGain = null;
      this.sfxGain = null;
      this.buffers = new Map();
      this.loops = {};
      this.manifest = null;
      this.ready = false;
      this.enabled = false;
      this.surface = 'carpet';
      this.footwearMode = 'auto';
      this.customTrack = null;
      this.customTrackUrl = '';
      this.volume = {
        master: 0.78,
        music: 0.12,
        ambience: 0.2,
        sfx: 0.82,
      };
    }

    _ensureContext() {
      if (this.ctx) return this.ctx;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) throw new Error('WebAudio not supported in this browser');
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.sfxGain = this.ctx.createGain();
      this.sfxGain.connect(this.masterGain);
      this.masterGain.connect(this.ctx.destination);
      this._syncSfxVolume();
      return this.ctx;
    }

    async init() {
      if (this.ready) return this.getStatus();
      this._ensureContext();
      const response = await fetch(this.manifestUrl, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Failed to load foley manifest: ${response.status}`);
      }
      this.manifest = await response.json();
      const defaults = this.manifest.defaults || {};
      this.surface = String(defaults.surface || this.surface).toLowerCase();
      this.volume.master = this._clamp01(defaults.master_volume, this.volume.master);
      this.volume.music = this._clamp01(defaults.music_volume, this.volume.music);
      this.volume.ambience = this._clamp01(defaults.ambience_volume, this.volume.ambience);
      this.volume.sfx = this._clamp01(defaults.sfx_volume, this.volume.sfx);
      this._syncSfxVolume();

      const oneShots = this.manifest.one_shots || {};
      const loadJobs = Object.entries(oneShots).map(async ([name, cfg]) => {
        const buffer = await this._loadBuffer(cfg.url);
        this.buffers.set(name, {
          buffer,
          gain: Number(cfg.gain || 1),
        });
      });
      await Promise.all(loadJobs);

      const loops = this.manifest.loops || {};
      Object.entries(loops).forEach(([name, cfg]) => {
        const audio = new Audio(cfg.url);
        audio.loop = true;
        audio.preload = 'auto';
        audio.volume = 0;
        this.loops[name] = {
          audio,
          gain: Number(cfg.gain || 1),
          channel: cfg.channel === 'music' ? 'music' : 'ambience',
          enabled: false,
        };
      });

      this.ready = true;
      return this.getStatus();
    }

    async unlock() {
      this._ensureContext();
      if (this.ctx.state !== 'running') {
        await this.ctx.resume();
      }
      this.enabled = true;
      return this.getStatus();
    }

    async _loadBuffer(url) {
      const response = await fetch(url, { cache: 'force-cache' });
      if (!response.ok) throw new Error(`Failed to load audio: ${url}`);
      const bytes = await response.arrayBuffer();
      return await this.ctx.decodeAudioData(bytes);
    }

    _clamp01(value, fallback) {
      const n = Number(value);
      if (!Number.isFinite(n)) return Number(fallback || 0);
      return Math.max(0, Math.min(1, n));
    }

    _syncSfxVolume() {
      if (!this.masterGain || !this.sfxGain) return;
      this.masterGain.gain.value = this.volume.master;
      this.sfxGain.gain.value = this.volume.sfx;
      this._syncLoopVolumes();
    }

    _syncLoopVolumes() {
      Object.values(this.loops).forEach((loop) => {
        if (!loop?.audio) return;
        const channelVolume = loop.channel === 'music' ? this.volume.music : this.volume.ambience;
        loop.audio.volume = this.volume.master * channelVolume * loop.gain;
      });
      if (this.customTrack) {
        this.customTrack.volume = this.volume.master * this.volume.music;
      }
    }

    _playBuffer(key, opts = {}) {
      if (!this.ready || !this.enabled || !this.ctx) return false;
      const sample = this.buffers.get(key);
      if (!sample?.buffer) return false;
      const source = this.ctx.createBufferSource();
      source.buffer = sample.buffer;
      const gainNode = this.ctx.createGain();
      const baseGain = Number(opts.gain ?? 1);
      const pitch = Number(opts.pitch ?? 1);
      const jitter = Number(opts.jitter ?? 0);
      const variedPitch = pitch + ((Math.random() * 2 - 1) * jitter);
      source.playbackRate.value = Math.max(0.5, Math.min(1.8, variedPitch));
      gainNode.gain.value = sample.gain * Math.max(0, baseGain);
      source.connect(gainNode);
      gainNode.connect(this.sfxGain);
      source.start(0);
      return true;
    }

    setSurface(surface) {
      const value = String(surface || '').toLowerCase();
      if (value) this.surface = value;
    }

    setFootwearMode(mode) {
      const value = String(mode || 'auto').toLowerCase();
      this.footwearMode = ['auto', 'flats', 'heels'].includes(value) ? value : 'auto';
    }

    setMasterVolume(value) {
      this.volume.master = this._clamp01(value, this.volume.master);
      this._syncSfxVolume();
    }

    setMusicVolume(value) {
      this.volume.music = this._clamp01(value, this.volume.music);
      this._syncLoopVolumes();
    }

    setAmbienceVolume(value) {
      this.volume.ambience = this._clamp01(value, this.volume.ambience);
      this._syncLoopVolumes();
    }

    setSfxVolume(value) {
      this.volume.sfx = this._clamp01(value, this.volume.sfx);
      this._syncSfxVolume();
    }

    _resolveFootstepKey(surface, footwear) {
      const s = String(surface || this.surface || 'carpet').toLowerCase();
      const f = String(footwear || this.footwearMode || 'auto').toLowerCase();
      const normalizedFootwear = f === 'auto' ? 'flats' : f;
      const direct = `footstep_${s}_${normalizedFootwear}`;
      if (this.buffers.has(direct)) return direct;

      const surfaceFallback = {
        carpet: 'footstep_carpet_flats',
        hardwood: 'footstep_hardwood_heels',
        cement: 'footstep_cement_flats',
        tile: 'footstep_tile_heels',
      };
      if (surfaceFallback[s]) return surfaceFallback[s];
      return 'footstep_carpet_flats';
    }

    triggerFootstep(opts = {}) {
      const surface = opts.surface || this.surface;
      const footwear = opts.footwear || this.footwearMode;
      const key = this._resolveFootstepKey(surface, footwear);
      return this._playBuffer(key, {
        gain: Number(opts.gain ?? 1),
        pitch: Number(opts.pitch ?? 1),
        jitter: Number(opts.jitter ?? 0.03),
      });
    }

    triggerDoor(kind = 'open', opts = {}) {
      const key = String(kind).toLowerCase() === 'close' ? 'door_close' : 'door_open';
      return this._playBuffer(key, {
        gain: Number(opts.gain ?? 1),
        pitch: Number(opts.pitch ?? 1),
        jitter: Number(opts.jitter ?? 0.015),
      });
    }

    triggerTypewriter(opts = {}) {
      return this._playBuffer('typewriter_click', {
        gain: Number(opts.gain ?? 1),
        pitch: Number(opts.pitch ?? 1),
        jitter: Number(opts.jitter ?? 0.04),
      });
    }

    triggerBreath(opts = {}) {
      return this._playBuffer('breath_soft', {
        gain: Number(opts.gain ?? 0.8),
        pitch: Number(opts.pitch ?? 1),
        jitter: Number(opts.jitter ?? 0.02),
      });
    }

    triggerThroatClear(opts = {}) {
      return this._playBuffer('throat_clear', {
        gain: Number(opts.gain ?? 0.7),
        pitch: Number(opts.pitch ?? 1),
        jitter: Number(opts.jitter ?? 0.015),
      });
    }

    async startLoop(name) {
      const loop = this.loops[name];
      if (!loop?.audio || !this.enabled) return false;
      loop.enabled = true;
      this._syncLoopVolumes();
      try {
        await loop.audio.play();
        return true;
      } catch (_) {
        loop.enabled = false;
        return false;
      }
    }

    stopLoop(name) {
      const loop = this.loops[name];
      if (!loop?.audio) return;
      loop.enabled = false;
      loop.audio.pause();
      loop.audio.currentTime = 0;
    }

    setLoungeEnabled(enabled) {
      if (enabled) return this.startLoop('lounge_placeholder');
      this.stopLoop('lounge_placeholder');
      return Promise.resolve(false);
    }

    setProjectorEnabled(enabled) {
      if (enabled) return this.startLoop('projector');
      this.stopLoop('projector');
      return Promise.resolve(false);
    }

    async startDefaultBeds(opts = {}) {
      if (!this.enabled) return false;
      await this.startLoop('room_tone');
      if (opts.loungeEnabled !== false) {
        await this.startLoop('lounge_placeholder');
      }
      return true;
    }

    stopAllLoops() {
      Object.keys(this.loops).forEach((name) => this.stopLoop(name));
      if (this.customTrack) {
        this.customTrack.pause();
        this.customTrack.currentTime = 0;
      }
    }

    async setCustomTrackFromFile(file) {
      if (!(file instanceof File)) return false;
      if (this.customTrackUrl) {
        URL.revokeObjectURL(this.customTrackUrl);
      }
      this.customTrackUrl = URL.createObjectURL(file);
      const audio = new Audio(this.customTrackUrl);
      audio.loop = true;
      audio.preload = 'auto';
      audio.volume = this.volume.master * this.volume.music;
      this.customTrack = audio;
      if (this.enabled) {
        this.stopLoop('lounge_placeholder');
        try {
          await audio.play();
        } catch (_) {
          return false;
        }
      }
      return true;
    }

    clearCustomTrack() {
      if (this.customTrack) {
        this.customTrack.pause();
        this.customTrack.currentTime = 0;
      }
      this.customTrack = null;
      if (this.customTrackUrl) {
        URL.revokeObjectURL(this.customTrackUrl);
        this.customTrackUrl = '';
      }
    }

    async playCustomTrack() {
      if (!this.enabled || !this.customTrack) return false;
      this.stopLoop('lounge_placeholder');
      this._syncLoopVolumes();
      try {
        await this.customTrack.play();
        return true;
      } catch (_) {
        return false;
      }
    }

    getStatus() {
      return {
        ready: this.ready,
        enabled: this.enabled,
        surface: this.surface,
        footwear_mode: this.footwearMode,
        custom_track_loaded: !!this.customTrack,
        volume: { ...this.volume },
        loops: Object.fromEntries(
          Object.entries(this.loops).map(([name, loop]) => [name, !!loop.enabled])
        ),
      };
    }
  }

  window.PubcastFoleyEngine = PubcastFoleyEngine;
})();
