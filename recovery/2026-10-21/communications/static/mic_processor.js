/**
 * mic_processor.js — Per-profile audio processing chains
 *
 * Extends mic_profiles.js with a full Web Audio processing chain per person:
 *
 *   MediaStream (getUserMedia)
 *     → MediaStreamSource
 *     → HighPassFilter   (cut rumble, adjustable gate)
 *     → LowShelfEQ       (bass ±15dB)
 *     → LowMidEQ         (250Hz peaking ±15dB)
 *     → MidEQ            (1kHz peaking ±15dB)
 *     → HighMidEQ        (3.5kHz peaking ±15dB)
 *     → HighShelfEQ      (10kHz air ±15dB)
 *     → LowPassFilter    (optional brilliance gate)
 *     → DynamicsCompressor (optional — tighten dynamic range)
 *     → PitchShifter     (AudioWorklet OLA — experimental)
 *     → GainNode         (input level + cough gate)
 *     → AnalyserNode     (level meter)
 *     → destination      (monitor output)
 *
 * Saved presets (per profile, in localStorage):
 *   Raw, Broadcast, Warm, Bright, Female Presence,
 *   Deep Character, Telephone, Lo-Fi + unlimited custom saves
 *
 * Pitch shifting note:
 *   Uses an AudioWorklet (OLA algorithm). Requires page served over
 *   HTTPS or localhost. Falls back silently if unavailable.
 *   Pitch range: -12 to +12 semitones.
 *
 * Integration:
 *   Replaces the stub GainNode in mic_profiles.js.
 *   Call window.micProcessor.attach(profileId) after a profile is added.
 *   window.micProcessor.detach(profileId) on removal.
 *   Cough gate still controlled by mic_profiles.js via the GainNode ref.
 */

(function () {
  'use strict';

  // ── AudioWorklet source (pitch shifter — OLA algorithm) ──────────────────
  // Loaded as a blob URL so no separate file needed.
  const PITCH_WORKLET_SRC = `
class PitchShifterProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [{ name: 'pitch', defaultValue: 1.0, minValue: 0.25, maxValue: 4.0 }];
  }

  constructor() {
    super();
    this._bufSize   = 2048;
    this._hopSize   = 512;
    this._inputBuf  = new Float32Array(this._bufSize * 2);
    this._outputBuf = new Float32Array(this._bufSize * 2);
    this._writePtr  = 0;
    this._readPtr   = 0.0;
    this._window    = new Float32Array(this._bufSize);
    for (let i = 0; i < this._bufSize; i++) {
      this._window[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / this._bufSize);
    }
  }

  process(inputs, outputs, parameters) {
    const input  = inputs[0]?.[0];
    const output = outputs[0]?.[0];
    if (!input || !output) return true;

    const pitch = parameters.pitch[0] ?? 1.0;
    const len   = input.length;

    // Write input into ring buffer
    for (let i = 0; i < len; i++) {
      this._inputBuf[this._writePtr % this._inputBuf.length] = input[i];
      this._writePtr++;
    }

    // Read at pitch-shifted rate
    for (let i = 0; i < len; i++) {
      const pos    = this._readPtr % this._inputBuf.length;
      const posInt = Math.floor(pos);
      const frac   = pos - posInt;
      const a      = this._inputBuf[posInt % this._inputBuf.length];
      const b      = this._inputBuf[(posInt + 1) % this._inputBuf.length];
      output[i]    = a + frac * (b - a);  // linear interpolation
      this._readPtr += pitch;
    }

    // Keep read pointer from drifting too far behind write
    const lag = this._writePtr - this._readPtr;
    if (lag > this._bufSize * 1.5) this._readPtr += this._hopSize;
    if (lag < this._hopSize)       this._readPtr -= this._hopSize;

    return true;
  }
}
registerProcessor('pitch-shifter', PitchShifterProcessor);
`;

  // ── Built-in presets ──────────────────────────────────────────────────────
  // Each preset: { hp, ls, lm, mid, hm, hs, lp, gain, compress, pitch }
  // hp = high-pass freq (Hz), lp = low-pass freq (Hz)
  // ls/lm/mid/hm/hs = { freq, gain } for EQ bands
  // pitch = semitones (-12..+12)

  const BUILTIN_PRESETS = {
    'Raw': {
      label: 'Raw', icon: '◦',
      hp: 20, lp: 20000,
      ls:  { freq: 100,  gain: 0  },
      lm:  { freq: 250,  gain: 0  },
      mid: { freq: 1000, gain: 0  },
      hm:  { freq: 3500, gain: 0  },
      hs:  { freq: 10000,gain: 0  },
      gain: 1.0, compress: false, pitch: 0,
    },
    'Broadcast': {
      label: 'Broadcast', icon: '📡',
      hp: 80, lp: 16000,
      ls:  { freq: 100,  gain: -2  },
      lm:  { freq: 300,  gain: -3  },
      mid: { freq: 1000, gain: 1   },
      hm:  { freq: 3000, gain: 3   },
      hs:  { freq: 10000,gain: 2   },
      gain: 1.1, compress: true, pitch: 0,
      desc: 'Classic radio voice — tight, present, authoritative',
    },
    'Warm': {
      label: 'Warm', icon: '🌅',
      hp: 60, lp: 14000,
      ls:  { freq: 120,  gain: 4   },
      lm:  { freq: 280,  gain: 2   },
      mid: { freq: 800,  gain: -1  },
      hm:  { freq: 3000, gain: -2  },
      hs:  { freq: 9000, gain: -3  },
      gain: 1.0, compress: true, pitch: 0,
      desc: 'Rich and warm — good for intimate conversation',
    },
    'Bright': {
      label: 'Bright', icon: '✦',
      hp: 100, lp: 18000,
      ls:  { freq: 100,  gain: -3  },
      lm:  { freq: 250,  gain: -4  },
      mid: { freq: 1200, gain: 1   },
      hm:  { freq: 4000, gain: 5   },
      hs:  { freq: 12000,gain: 6   },
      gain: 1.0, compress: false, pitch: 0,
      desc: 'Crisp and airy — cuts through a mix',
    },
    'Female Presence': {
      label: 'Female Presence', icon: '◈',
      hp: 120, lp: 16000,
      ls:  { freq: 150,  gain: -5  },
      lm:  { freq: 300,  gain: -4  },
      mid: { freq: 1500, gain: 2   },
      hm:  { freq: 4000, gain: 6   },
      hs:  { freq: 10000,gain: 5   },
      gain: 1.05, compress: true, pitch: 3,
      desc: 'EQ + +3 semitones — brightens and lifts the voice',
    },
    'Deep Character': {
      label: 'Deep Character', icon: '▾',
      hp: 50, lp: 12000,
      ls:  { freq: 80,   gain: 7   },
      lm:  { freq: 200,  gain: 4   },
      mid: { freq: 900,  gain: 0   },
      hm:  { freq: 3000, gain: -3  },
      hs:  { freq: 8000, gain: -4  },
      gain: 1.0, compress: true, pitch: -4,
      desc: 'Full-bodied and low — great for narrator characters',
    },
    'Telephone': {
      label: 'Telephone', icon: '☎',
      hp: 300, lp: 3000,
      ls:  { freq: 100,  gain: -8  },
      lm:  { freq: 400,  gain: 3   },
      mid: { freq: 1200, gain: 4   },
      hm:  { freq: 2500, gain: 2   },
      hs:  { freq: 8000, gain: -10 },
      gain: 0.9, compress: true, pitch: 0,
      desc: 'Classic phone call — 300Hz–3kHz band',
    },
    'Lo-Fi': {
      label: 'Lo-Fi', icon: '◉',
      hp: 200, lp: 5000,
      ls:  { freq: 100,  gain: -6  },
      lm:  { freq: 350,  gain: 5   },
      mid: { freq: 1000, gain: 3   },
      hm:  { freq: 2500, gain: 0   },
      hs:  { freq: 6000, gain: -8  },
      gain: 0.85, compress: true, pitch: 0,
      desc: 'Vintage cassette feel — warm and degraded',
    },
  };

  // ── State ─────────────────────────────────────────────────────────────────
  let _audioCtx     = null;
  let _workletReady = false;
  let _workletFailed = false;
  const _chains     = {};   // { profileId -> ProcessingChain }

  // ── AudioContext ──────────────────────────────────────────────────────────
  async function getCtx() {
    if (!_audioCtx) {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (_audioCtx.state === 'suspended') {
      await _audioCtx.resume();
    }
    return _audioCtx;
  }

  async function loadWorklet() {
    if (_workletReady || _workletFailed) return;
    try {
      const blob = new Blob([PITCH_WORKLET_SRC], { type: 'application/javascript' });
      const url  = URL.createObjectURL(blob);
      const ctx  = await getCtx();
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      _workletReady = true;
    } catch (e) {
      console.warn('[MicProcessor] AudioWorklet unavailable (pitch shift disabled):', e.message);
      _workletFailed = true;
    }
  }

  // ── ProcessingChain ───────────────────────────────────────────────────────
  class ProcessingChain {
    constructor(profileId) {
      this.profileId    = profileId;
      this.stream       = null;
      this.source       = null;
      this.nodes        = {};     // named Web Audio nodes
      this.analyser     = null;
      this.meterRaf     = null;
      this.activePreset = 'Raw';
      this.customPresets = this._loadCustomPresets();
      this._settings    = { ...BUILTIN_PRESETS['Raw'] };
    }

    // ── Build chain ─────────────────────────────────────────────────────────
    async activate() {
      this.deactivate();
      const ctx = await getCtx();
      await loadWorklet();

      try {
        const picker = window.micDevicePicker;
        if (picker) {
          const selected = await new Promise(resolve => picker.showPicker(this.profileId, this.profileId,
            (deviceId, label, type) => resolve({deviceId, label, type})));
          if (selected.type === "cancelled") throw new Error("Microphone selection cancelled");
          this.stream = await picker.openStream(selected.deviceId, selected.label);
        } else {
          this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        }
      } catch (e) {
        console.warn(`[MicProcessor] Mic access denied for ${this.profileId}:`, e.message);
        this._updateStatus('No mic access — check browser permissions', 'error');
        return false;
      }

      this.source = ctx.createMediaStreamSource(this.stream);

      // High-pass
      const hp = ctx.createBiquadFilter();
      hp.type = 'highpass'; hp.frequency.value = 80; hp.Q.value = 0.7;

      // EQ bands
      const ls = ctx.createBiquadFilter();
      ls.type = 'lowshelf';  ls.frequency.value = 100;

      const lm = ctx.createBiquadFilter();
      lm.type = 'peaking'; lm.frequency.value = 250; lm.Q.value = 1.4;

      const mid = ctx.createBiquadFilter();
      mid.type = 'peaking'; mid.frequency.value = 1000; mid.Q.value = 1.4;

      const hm = ctx.createBiquadFilter();
      hm.type = 'peaking'; hm.frequency.value = 3500; hm.Q.value = 1.4;

      const hs = ctx.createBiquadFilter();
      hs.type = 'highshelf'; hs.frequency.value = 10000;

      // Low-pass
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 20000; lp.Q.value = 0.7;

      // Compressor
      const comp = ctx.createDynamicsCompressor();
      comp.threshold.value = -24; comp.knee.value = 12;
      comp.ratio.value     = 4;   comp.attack.value = 0.003;
      comp.release.value   = 0.25;

      // Gain (also the cough gate — replaces mic_profiles stub)
      const gain = ctx.createGain();
      gain.gain.value = 1.0;

      // Analyser for meter
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      this.analyser = analyser;

      // Pitch shifter (optional)
      let pitchNode = null;
      if (_workletReady) {
        try {
          pitchNode = new AudioWorkletNode(ctx, 'pitch-shifter');
        } catch (e) {
          console.warn('[MicProcessor] PitchShifter node failed:', e.message);
        }
      }

      // Store nodes
      this.nodes = { hp, ls, lm, mid, hm, hs, lp, comp, gain, pitch: pitchNode };

      // Connect chain
      let last = this.source;
      const chain = [hp, ls, lm, mid, hm, hs, lp];
      chain.forEach(n => { last.connect(n); last = n; });
      last.connect(comp); last = comp;
      if (pitchNode) { last.connect(pitchNode); last = pitchNode; }
      last.connect(gain);
      gain.connect(analyser);
      this.output = ctx.createMediaStreamDestination();
      gain.connect(this.output);
      window.dispatchEvent(new CustomEvent("pubcast:mic-stream", {detail: {profileId: this.profileId, stream: this.output.stream}}));
      // Not connecting to destination by default — monitor is opt-in
      // (prevents feedback when host has speakers + mic in same room)

      // Expose gain node to mic_profiles cough system
      if (window.micProfiles) {
        window._micProcessorGains = window._micProcessorGains || {};
        window._micProcessorGains[this.profileId] = gain;
      }

      // Load saved settings
      const saved = this._loadSettings();
      if (saved) {
        this._settings = saved;
        this._applySettings(saved);
      }

      this._startMeter();
      this._updateStatus('Active', 'ok');
      return true;
    }

    deactivate() {
      if (this.utterance?.state === 'recording') this.utterance.stop();
      if (this.output) {
        this.output.stream.getTracks().forEach(t => t.stop());
        this.output = null;
        window.dispatchEvent(new CustomEvent('pubcast:mic-stopped', {detail: {profileId: this.profileId}}));
      }
      this._stopMeter();
      if (this.stream) {
        this.stream.getTracks().forEach(t => t.stop());
        this.stream = null;
      }
      if (this.source) { try { this.source.disconnect(); } catch (_) {} }
      Object.values(this.nodes).forEach(n => { if (n) try { n.disconnect(); } catch (_) {} });
      this.nodes   = {};
      this.source  = null;
      this.analyser = null;
      if (window._micProcessorGains) delete window._micProcessorGains[this.profileId];
    }

    // ── Settings application ────────────────────────────────────────────────
    _applySettings(s) {
      const { nodes } = this;
      if (!nodes.hp) return;

      const ctx = _audioCtx;
      const now = ctx ? ctx.currentTime : 0;

      nodes.hp.frequency.setTargetAtTime(s.hp  ?? 80,    now, 0.05);
      nodes.lp.frequency.setTargetAtTime(s.lp  ?? 20000, now, 0.05);

      nodes.ls.frequency.setTargetAtTime(s.ls?.freq  ?? 100,   now, 0.05);
      nodes.ls.gain.setTargetAtTime(     s.ls?.gain  ?? 0,     now, 0.05);

      nodes.lm.frequency.setTargetAtTime(s.lm?.freq  ?? 250,   now, 0.05);
      nodes.lm.gain.setTargetAtTime(     s.lm?.gain  ?? 0,     now, 0.05);

      nodes.mid.frequency.setTargetAtTime(s.mid?.freq ?? 1000,  now, 0.05);
      nodes.mid.gain.setTargetAtTime(     s.mid?.gain ?? 0,     now, 0.05);

      nodes.hm.frequency.setTargetAtTime(s.hm?.freq  ?? 3500,  now, 0.05);
      nodes.hm.gain.setTargetAtTime(     s.hm?.gain  ?? 0,     now, 0.05);

      nodes.hs.frequency.setTargetAtTime(s.hs?.freq  ?? 10000, now, 0.05);
      nodes.hs.gain.setTargetAtTime(     s.hs?.gain  ?? 0,     now, 0.05);

      nodes.gain.gain.setTargetAtTime(s.gain ?? 1.0, now, 0.05);

      if (nodes.comp) {
        nodes.comp.threshold.value = s.compress ? -24 : 0;
        nodes.comp.ratio.value     = s.compress ? 4   : 1;
      }

      // Pitch: semitones → ratio
      if (nodes.pitch) {
        const semitones = s.pitch ?? 0;
        const ratio     = Math.pow(2, semitones / 12);
        nodes.pitch.parameters.get('pitch').setTargetAtTime(ratio, now, 0.1);
      }

      this._settings = { ...s };
      this._saveSettings(s);
      this._updateUI();
    }

    applyPreset(presetName) {
      const preset = BUILTIN_PRESETS[presetName] || this.customPresets[presetName];
      if (!preset) return;
      this.activePreset = presetName;
      this._applySettings({ ...preset });
    }

    // ── Persistence ─────────────────────────────────────────────────────────
    _settingsKey()      { return `pubcast_mic_proc_${this.profileId}`; }
    _customPresetsKey() { return `pubcast_mic_presets_${this.profileId}`; }

    _saveSettings(s) {
      try { localStorage.setItem(this._settingsKey(), JSON.stringify(s)); } catch (_) {}
    }
    _loadSettings() {
      try {
        const raw = localStorage.getItem(this._settingsKey());
        return raw ? JSON.parse(raw) : null;
      } catch (_) { return null; }
    }
    _loadCustomPresets() {
      try {
        const raw = localStorage.getItem(this._customPresetsKey());
        return raw ? JSON.parse(raw) : {};
      } catch (_) { return {}; }
    }
    _saveCustomPresets() {
      try { localStorage.setItem(this._customPresetsKey(), JSON.stringify(this.customPresets)); } catch (_) {}
    }

    saveAsPreset(name) {
      if (!name) return;
      this.customPresets[name] = { ...this._settings, label: name, icon: '★' };
      this._saveCustomPresets();
      this._renderPresetButtons();
    }

    deleteCustomPreset(name) {
      delete this.customPresets[name];
      this._saveCustomPresets();
      this._renderPresetButtons();
    }

    // ── Meter ────────────────────────────────────────────────────────────────
    _startMeter() {
      if (!this.analyser) return;
      const buf = new Uint8Array(this.analyser.frequencyBinCount);
      const tick = () => {
        this.meterRaf = requestAnimationFrame(tick);
        this.analyser.getByteFrequencyData(buf);
        const avg = buf.reduce((s, v) => s + v, 0) / buf.length;
        const pct = Math.round((avg / 255) * 100);
        this._updateMeter(pct);
      };
      tick();
    }

    _stopMeter() {
      if (this.meterRaf) { cancelAnimationFrame(this.meterRaf); this.meterRaf = null; }
    }

    _updateMeter(pct) {
      const el = document.getElementById(`proc-meter-${this.profileId}`);
      if (!el) return;
      el.style.width = pct + '%';
      el.style.background = pct > 85 ? '#e03e3e' : pct > 65 ? '#f0a500' : '#00e5cc';
    }

    _updateStatus(msg, type) {
      const el = document.getElementById(`proc-status-${this.profileId}`);
      if (!el) return;
      el.textContent = msg;
      el.style.color = type === 'ok' ? '#00cc88' : type === 'error' ? '#e03e3e' : '#aaa';
    }

    // ── UI rendering ─────────────────────────────────────────────────────────
    buildPanel() {
      const allPresets = { ...BUILTIN_PRESETS, ...this.customPresets };
      const s = this._settings;

      const pitchNote = _workletFailed
        ? '<span class="muted small" style="color:#f0a500;">⚠ Pitch shift unavailable (requires HTTPS or localhost)</span>'
        : '';

      return `
        <div class="proc-panel" id="proc-panel-${this.profileId}">
          <div class="proc-header" data-toggle="proc-body-${this.profileId}">
            <span class="proc-title">🎛 Voice Processing</span>
            <div class="proc-meter-wrap">
              <div class="proc-meter-bar">
                <div class="proc-meter-fill" id="proc-meter-${this.profileId}" style="width:0%"></div>
              </div>
            </div>
            <span class="proc-status muted small" id="proc-status-${this.profileId}">Inactive</span>
            <button class="proc-activate ghost" data-pid="${this.profileId}">Activate Mic</button>
            <button class="proc-transcribe ghost" type="button">Transcribe</button>
            <span class="proc-chevron">▾</span>
          </div>

          <div class="proc-body" id="proc-body-${this.profileId}" style="display:none;">

            <pre id="proc-transcript-${this.profileId}" aria-label="Raw microphone transcript" style="white-space:pre-wrap"></pre>
            <!-- Presets -->
            <div class="proc-section">
              <div class="proc-section-label">Presets</div>
              <div class="proc-presets" id="proc-presets-${this.profileId}"></div>
              <div class="proc-save-row" style="margin-top:6px;">
                <input class="proc-preset-name" id="proc-preset-name-${this.profileId}"
                  placeholder="Save current as…" style="min-width:160px;" />
                <button class="ghost proc-save-btn" data-pid="${this.profileId}">Save</button>
              </div>
            </div>

            <!-- Input gain -->
            <div class="proc-section">
              <div class="proc-section-label">Input Gain</div>
              <div class="proc-row">
                <input type="range" class="proc-slider" id="proc-gain-${this.profileId}"
                  min="0" max="3" step="0.05" value="${(s.gain ?? 1.0).toFixed(2)}" />
                <span class="proc-val" id="proc-gain-val-${this.profileId}">${Math.round((s.gain ?? 1.0) * 100)}%</span>
                <label class="proc-check"><input type="checkbox" id="proc-comp-${this.profileId}"
                  ${s.compress ? 'checked' : ''} /> Compress</label>
                <label class="proc-check"><input type="checkbox" id="proc-monitor-${this.profileId}" />
                  Monitor</label>
              </div>
            </div>

            <!-- High-pass / Low-pass gates -->
            <div class="proc-section">
              <div class="proc-section-label">Frequency Gates</div>
              <div class="proc-row">
                <label class="muted small">High-pass</label>
                <input type="range" class="proc-slider" id="proc-hp-${this.profileId}"
                  min="20" max="500" step="5" value="${s.hp ?? 80}" />
                <span class="proc-val" id="proc-hp-val-${this.profileId}">${s.hp ?? 80}Hz</span>
                <label class="muted small" style="margin-left:12px;">Low-pass</label>
                <input type="range" class="proc-slider" id="proc-lp-${this.profileId}"
                  min="2000" max="20000" step="100" value="${s.lp ?? 20000}" />
                <span class="proc-val" id="proc-lp-val-${this.profileId}">${Math.round((s.lp ?? 20000)/1000)}kHz</span>
              </div>
            </div>

            <!-- EQ -->
            <div class="proc-section">
              <div class="proc-section-label">Equaliser</div>
              ${this._eqBandHTML('ls',  'Bass',       100,    s.ls?.gain  ?? 0, this.profileId)}
              ${this._eqBandHTML('lm',  'Low-Mid',    250,    s.lm?.gain  ?? 0, this.profileId)}
              ${this._eqBandHTML('mid', 'Mid',        1000,   s.mid?.gain ?? 0, this.profileId)}
              ${this._eqBandHTML('hm',  'High-Mid',   3500,   s.hm?.gain  ?? 0, this.profileId)}
              ${this._eqBandHTML('hs',  'Air',        10000,  s.hs?.gain  ?? 0, this.profileId)}
            </div>

            <!-- Pitch -->
            <div class="proc-section">
              <div class="proc-section-label">Pitch Shift <span class="muted small">(semitones)</span></div>
              ${pitchNote}
              <div class="proc-row">
                <span class="muted small proc-val">-12</span>
                <input type="range" class="proc-slider" id="proc-pitch-${this.profileId}"
                  min="-12" max="12" step="1" value="${s.pitch ?? 0}"
                  ${_workletFailed ? 'disabled' : ''} />
                <span class="muted small proc-val">+12</span>
                <span class="proc-val" id="proc-pitch-val-${this.profileId}" style="min-width:52px;text-align:center;">
                  ${s.pitch >= 0 ? '+' : ''}${s.pitch ?? 0} st
                </span>
                <button class="ghost" id="proc-pitch-reset-${this.profileId}" style="font-size:.7rem;">0</button>
              </div>
            </div>

          </div>
        </div>
      `;
    }

    _eqBandHTML(band, label, defaultFreq, gainVal, pid) {
      const display = gainVal >= 0 ? `+${gainVal}` : `${gainVal}`;
      return `
        <div class="proc-eq-band">
          <span class="proc-eq-label">${label}</span>
          <span class="proc-eq-freq muted small">${defaultFreq >= 1000 ? (defaultFreq/1000)+'k' : defaultFreq}Hz</span>
          <input type="range" class="proc-slider proc-eq-slider"
            id="proc-${band}-${pid}" min="-15" max="15" step="0.5"
            value="${gainVal}" />
          <span class="proc-val proc-eq-val" id="proc-${band}-val-${pid}">${display}dB</span>
        </div>
      `;
    }

    _renderPresetButtons() {
      const container = document.getElementById(`proc-presets-${this.profileId}`);
      if (!container) return;
      container.innerHTML = '';
      const allPresets = { ...BUILTIN_PRESETS, ...this.customPresets };
      Object.entries(allPresets).forEach(([name, preset]) => {
        const isActive  = name === this.activePreset;
        const isCustom  = !!this.customPresets[name];
        const btn = document.createElement('button');
        btn.className = `proc-preset-btn ghost${isActive ? ' active' : ''}`;
        btn.title     = preset.desc || name;
        btn.innerHTML = `${preset.icon || '◦'} ${preset.label || name}`;
        btn.addEventListener('click', () => {
          this.applyPreset(name);
          container.querySelectorAll('.proc-preset-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
        });
        if (isCustom) {
          const del = document.createElement('span');
          del.textContent = '✕';
          del.className   = 'proc-del-preset';
          del.title       = 'Delete preset';
          del.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`Delete preset "${name}"?`)) this.deleteCustomPreset(name);
          });
          btn.appendChild(del);
        }
        container.appendChild(btn);
      });
    }

    _updateUI() {
      const s   = this._settings;
      const pid = this.profileId;
      const get = id => document.getElementById(id);

      const setVal = (id, v) => { const el = get(id); if (el) el.value = v; };
      const setTxt = (id, t) => { const el = get(id); if (el) el.textContent = t; };

      setVal(`proc-gain-${pid}`, (s.gain ?? 1.0).toFixed(2));
      setTxt(`proc-gain-val-${pid}`, Math.round((s.gain ?? 1.0) * 100) + '%');
      setVal(`proc-hp-${pid}`, s.hp ?? 80);
      setTxt(`proc-hp-val-${pid}`, (s.hp ?? 80) + 'Hz');
      setVal(`proc-lp-${pid}`, s.lp ?? 20000);
      setTxt(`proc-lp-val-${pid}`, Math.round((s.lp ?? 20000) / 1000) + 'kHz');

      [['ls','Bass'],['lm','Low-Mid'],['mid','Mid'],['hm','High-Mid'],['hs','Air']].forEach(([band]) => {
        const g = s[band]?.gain ?? 0;
        setVal(`proc-${band}-${pid}`, g);
        setTxt(`proc-${band}-val-${pid}`, (g >= 0 ? '+' : '') + g + 'dB');
      });

      const pt = s.pitch ?? 0;
      setVal(`proc-pitch-${pid}`, pt);
      setTxt(`proc-pitch-val-${pid}`, (pt >= 0 ? '+' : '') + pt + ' st');

      const comp = get(`proc-comp-${pid}`);
      if (comp) comp.checked = !!s.compress;
    }

    wireControls() {
      const pid = this.profileId;
      const get = id => document.getElementById(id);
      const on  = (id, ev, fn) => { const el = get(id); if (el) el.addEventListener(ev, fn); };

      const pushChange = () => this._applySettings({ ...this._settings });

      on(`proc-panel-${pid}`, 'click', async e => {
        if (!e.target.classList.contains('proc-transcribe')) return;
        if (this.utterance?.state === 'recording') { this.utterance.stop(); return; }
        if (!this.output) { this._updateStatus('Activate a microphone first', 'error'); return; }
        const button = e.target, chunks = [];
        try {
          this.utterance = new MediaRecorder(this.output.stream);
          this.utterance.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
          this.utterance.onstop = async () => {
            clearTimeout(this.utteranceTimeout); button.textContent = 'Transcribing…'; button.disabled = true;
            try {
              const blob = new Blob(chunks, {type: this.utterance.mimeType});
              const response = await fetch('/api/stt/transcribe', {method: 'POST', headers: {'Content-Type': blob.type}, body: blob});
              const result = await response.json();
              if (!response.ok) throw new Error(result.detail || 'Transcription failed');
              const transcript = get(`proc-transcript-${pid}`);
              if (transcript) transcript.textContent = result.text;
              this._updateStatus('Raw transcript ready', 'ok');
            } catch (error) { this._updateStatus(error.message, 'error'); }
            finally { button.textContent = 'Transcribe'; button.disabled = false; }
          };
          this.utterance.start(); button.textContent = 'Stop transcription';
          this.utteranceTimeout = setTimeout(() => { if (this.utterance.state === 'recording') this.utterance.stop(); }, 60000);
        } catch (error) { this._updateStatus(error.message, 'error'); }
      });

      // Activate button
      on(`proc-panel-${pid}`, 'click', (e) => {
        if (e.target.classList.contains('proc-activate')) {
          e.target.textContent = 'Activating…';
          e.target.disabled    = true;
          this.activate().then(ok => {
            e.target.textContent = ok ? 'Active ✓' : 'Failed ✗';
            e.target.disabled    = !!ok;
          }).catch(error => { this._updateStatus(error.message, 'error'); e.target.disabled = false; });
        }
      });

      // Collapse toggle
      on(`proc-panel-${pid}`, 'click', (e) => {
        if (!e.target.closest('.proc-header')) return;
        if (e.target.closest('button')) return;
        const body = get(`proc-body-${pid}`);
        if (body) body.style.display = body.style.display === 'none' ? '' : 'none';
      });

      // Input gain slider
      on(`proc-gain-${pid}`, 'input', (e) => {
        const v = parseFloat(e.target.value);
        const el = get(`proc-gain-val-${pid}`); if (el) el.textContent = Math.round(v * 100) + '%';
        this._settings.gain = v;
        if (this.nodes.gain) this.nodes.gain.gain.setTargetAtTime(v, _audioCtx.currentTime, 0.05);
        this._saveSettings(this._settings);
      });

      // Compress
      on(`proc-comp-${pid}`, 'change', (e) => {
        this._settings.compress = e.target.checked;
        pushChange();
      });

      // Monitor
      on(`proc-monitor-${pid}`, 'change', (e) => {
        if (!this.nodes.gain) return;
        if (e.target.checked) {
          this.nodes.gain.connect(_audioCtx.destination);
        } else {
          try { this.nodes.gain.disconnect(_audioCtx.destination); } catch (_) {}
        }
      });

      // HP / LP
      on(`proc-hp-${pid}`, 'input', (e) => {
        const v = parseInt(e.target.value);
        const el = get(`proc-hp-val-${pid}`); if (el) el.textContent = v + 'Hz';
        this._settings.hp = v;
        if (this.nodes.hp) this.nodes.hp.frequency.setTargetAtTime(v, _audioCtx.currentTime, 0.05);
        this._saveSettings(this._settings);
      });
      on(`proc-lp-${pid}`, 'input', (e) => {
        const v = parseInt(e.target.value);
        const el = get(`proc-lp-val-${pid}`);
        if (el) el.textContent = Math.round(v/1000) + 'kHz';
        this._settings.lp = v;
        if (this.nodes.lp) this.nodes.lp.frequency.setTargetAtTime(v, _audioCtx.currentTime, 0.05);
        this._saveSettings(this._settings);
      });

      // EQ bands
      [['ls','Bass'],['lm','Low-Mid'],['mid','Mid'],['hm','High-Mid'],['hs','Air']].forEach(([band]) => {
        on(`proc-${band}-${pid}`, 'input', (e) => {
          const v   = parseFloat(e.target.value);
          const lbl = get(`proc-${band}-val-${pid}`);
          if (lbl) lbl.textContent = (v >= 0 ? '+' : '') + v + 'dB';
          if (!this._settings[band]) this._settings[band] = {};
          this._settings[band].gain = v;
          if (this.nodes[band]) this.nodes[band].gain.setTargetAtTime(v, _audioCtx.currentTime, 0.05);
          this._saveSettings(this._settings);
        });
      });

      // Pitch
      on(`proc-pitch-${pid}`, 'input', (e) => {
        const semitones = parseInt(e.target.value);
        const el = get(`proc-pitch-val-${pid}`);
        if (el) el.textContent = (semitones >= 0 ? '+' : '') + semitones + ' st';
        this._settings.pitch = semitones;
        if (this.nodes.pitch) {
          const ratio = Math.pow(2, semitones / 12);
          this.nodes.pitch.parameters.get('pitch').setTargetAtTime(ratio, _audioCtx.currentTime, 0.1);
        }
        this._saveSettings(this._settings);
      });
      on(`proc-pitch-reset-${pid}`, 'click', () => {
        const slider = get(`proc-pitch-${pid}`);
        if (slider) { slider.value = 0; slider.dispatchEvent(new Event('input')); }
      });

      // Save preset
      on(`proc-save-btn-${pid}`, 'click', () => {
        // Note: the button id is set in buildPanel — wire by class query
      });
      const saveBtn = document.querySelector(`#proc-panel-${pid} .proc-save-btn`);
      if (saveBtn) {
        saveBtn.addEventListener('click', () => {
          const nameEl = get(`proc-preset-name-${pid}`);
          const name   = nameEl?.value.trim();
          if (!name) return;
          this.saveAsPreset(name);
          if (nameEl) nameEl.value = '';
        });
      }

      // Render preset buttons
      this._renderPresetButtons();
    }
  }

  // ── Public API ────────────────────────────────────────────────────────────
  function attach(profileId) {
    if (_chains[profileId]) return _chains[profileId];
    const chain = new ProcessingChain(profileId);
    _chains[profileId] = chain;

    // Inject processing panel into the existing mic card
    const card = document.getElementById(`mic-card-${profileId}`);
    if (card) {
      const el = document.createElement('div');
      el.innerHTML = chain.buildPanel();
      card.appendChild(el.firstElementChild);
      chain.wireControls();
    }
    return chain;
  }

  function detach(profileId) {
    const chain = _chains[profileId];
    if (!chain) return;
    chain.deactivate();
    delete _chains[profileId];
    const panel = document.getElementById(`proc-panel-${profileId}`);
    if (panel) panel.remove();
  }

  function getChain(profileId) {
    return _chains[profileId] || null;
  }

  // ── Hook into mic_profiles new card renders ───────────────────────────────
  // mic_profiles.js calls renderProfiles() which rebuilds all cards.
  // We intercept by observing the list container.
  function observeProfileList() {
    const list = document.getElementById('mic-profiles-list');
    if (!list) return;

    const observer = new MutationObserver(() => {
      // Re-attach processors for any card that doesn't have a proc panel yet
      Object.keys(_chains).forEach(pid => {
        const card  = document.getElementById(`mic-card-${pid}`);
        const panel = document.getElementById(`proc-panel-${pid}`);
        if (card && !panel) {
          // Card was re-rendered — rebuild the proc panel
          const chain = _chains[pid];
          const el = document.createElement('div');
          el.innerHTML = chain.buildPanel();
          card.appendChild(el.firstElementChild);
          chain.wireControls();
          chain._renderPresetButtons();
        }
      });

      // Attach new cards that have no chain yet
      list.querySelectorAll('[id^="mic-card-"]').forEach(card => {
        const pid = card.id.replace('mic-card-', '');
        if (!_chains[pid]) attach(pid);
      });
    });

    observer.observe(list, { childList: true, subtree: false });
  }

  // ── Styles ────────────────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('mic-proc-styles')) return;
    const style = document.createElement('style');
    style.id = 'mic-proc-styles';
    style.textContent = `
      .proc-panel {
        border-top: 1px solid rgba(255,255,255,0.07);
        margin-top: 10px;
        padding-top: 8px;
      }
      .proc-header {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        padding: 4px 0;
        user-select: none;
      }
      .proc-title {
        font-size: .78rem;
        font-weight: 600;
        color: #c9a84c;
        letter-spacing: .08em;
        white-space: nowrap;
      }
      .proc-meter-wrap {
        flex: 1;
        max-width: 120px;
      }
      .proc-meter-bar {
        height: 6px;
        background: rgba(255,255,255,0.08);
        border-radius: 3px;
        overflow: hidden;
      }
      .proc-meter-fill {
        height: 100%;
        width: 0%;
        background: #00e5cc;
        border-radius: 3px;
        transition: width .05s, background .2s;
      }
      .proc-status { font-size: .68rem; white-space: nowrap; }
      .proc-chevron { font-size: .7rem; color: rgba(255,255,255,0.3); }
      .proc-activate { font-size: .7rem; padding: 3px 10px; white-space: nowrap; }

      .proc-body {
        padding: 10px 0 4px;
      }
      .proc-section {
        margin-bottom: 12px;
      }
      .proc-section-label {
        font-size: .68rem;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.35);
        margin-bottom: 6px;
      }
      .proc-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      .proc-slider {
        flex: 1;
        min-width: 80px;
        max-width: 200px;
        accent-color: #00e5cc;
        cursor: pointer;
      }
      .proc-val {
        font-family: 'Share Tech Mono', monospace;
        font-size: .72rem;
        color: #00e5cc;
        white-space: nowrap;
        min-width: 38px;
      }
      .proc-check {
        font-size: .72rem;
        color: rgba(255,255,255,0.55);
        display: flex;
        align-items: center;
        gap: 4px;
        cursor: pointer;
        white-space: nowrap;
      }

      /* EQ bands */
      .proc-eq-band {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 5px;
      }
      .proc-eq-label {
        font-size: .72rem;
        width: 62px;
        color: rgba(255,255,255,0.65);
        flex-shrink: 0;
      }
      .proc-eq-freq {
        width: 36px;
        text-align: right;
        flex-shrink: 0;
      }
      .proc-eq-slider {
        flex: 1;
        max-width: none;
        accent-color: #c9a84c;
      }
      .proc-eq-val {
        min-width: 46px;
        text-align: right;
        color: #c9a84c;
      }

      /* Presets */
      .proc-presets {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        margin-bottom: 4px;
      }
      .proc-preset-btn {
        font-size: .7rem;
        padding: 3px 9px;
        border-radius: 4px;
        position: relative;
        border-color: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.6);
        transition: border-color .15s, color .15s;
      }
      .proc-preset-btn.active {
        border-color: #c9a84c;
        color: #c9a84c;
        background: rgba(201,168,76,0.1);
      }
      .proc-preset-btn:hover { border-color: rgba(255,255,255,0.3); color: #fff; }
      .proc-del-preset {
        margin-left: 5px;
        font-size: .6rem;
        opacity: 0.4;
        cursor: pointer;
        transition: opacity .1s;
      }
      .proc-del-preset:hover { opacity: 1; color: #e03e3e; }
      .proc-save-row {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .proc-preset-name {
        font-size: .75rem;
        padding: 3px 8px;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  function init() {
    injectStyles();
    observeProfileList();

    // Attach to any profiles already rendered
    const list = document.getElementById('mic-profiles-list');
    if (list) {
      list.querySelectorAll('[id^="mic-card-"]').forEach(card => {
        const pid = card.id.replace('mic-card-', '');
        attach(pid);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.micProcessor = { attach, detach, getChain, presets: BUILTIN_PRESETS, activeStreams: () => Object.values(_chains).filter(c => c.output).map(c => ({profileId: c.profileId, stream: c.output.stream})) };
})();
