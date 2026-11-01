/**
 * mic_device_picker.js — Browser-side audio input device enumeration.
 *
 * Best practices implemented (from MDN + WebRTC research):
 *   1. Request getUserMedia first (broad) to unlock real device labels —
 *      before permission, enumerateDevices returns empty labels only.
 *   2. Store label/name preferences — not raw deviceIds — because
 *      deviceIds can change between sessions.
 *   3. Listen for `devicechange` event to detect hot-plug.
 *   4. Use deviceId constraint in getUserMedia to open the chosen device.
 *   5. Feature-detect everything. Degrade gracefully.
 *
 * Integration:
 *   Extends mic_processor.js. When a user clicks "Activate Mic" in a
 *   profile card, this module intercepts and shows a device picker first
 *   if more than one input device is available.
 *
 *   Also adds a standalone "Audio Devices" section to the audio station
 *   showing all available input devices with their connection type and
 *   a "Refresh" button for hot-plug detection.
 */

(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────────────
  let _permissionGranted  = false;
  let _deviceList         = [];          // [ MediaDeviceInfo ]
  let _selectedDeviceId   = null;        // currently chosen deviceId
  let _selectedDeviceName = null;        // label stored for persistence

  // ── Preference storage ────────────────────────────────────────────────────
  // Store name/label, not raw deviceId — IDs are session-stable but not
  // cross-session stable in all browsers.
  function savePreference(profileId, label, deviceId) {
    try {
      const prefs = JSON.parse(localStorage.getItem('pubcast_device_prefs') || '{}');
      prefs[profileId] = { label, deviceId, saved_at: Date.now() };
      localStorage.setItem('pubcast_device_prefs', JSON.stringify(prefs));
    } catch (_) {}
  }

  function loadPreference(profileId) {
    try {
      const prefs = JSON.parse(localStorage.getItem('pubcast_device_prefs') || '{}');
      return prefs[profileId] || null;
    } catch (_) { return null; }
  }

  // ── Device enumeration ────────────────────────────────────────────────────
  async function requestPermission() {
    if (_permissionGranted) return true;
    try {
      // Broad request just to unlock labels
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true, video: false
      });
      // Stop all tracks immediately — we just needed the permission grant
      stream.getTracks().forEach(t => t.stop());
      _permissionGranted = true;
      return true;
    } catch (e) {
      console.warn('[DevicePicker] Permission denied:', e.message);
      return false;
    }
  }

  async function enumerateInputDevices() {
    if (!navigator.mediaDevices?.enumerateDevices) {
      console.warn('[DevicePicker] enumerateDevices not supported');
      return [];
    }
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      _deviceList = all.filter(d => d.kind === 'audioinput');
      return _deviceList;
    } catch (e) {
      console.warn('[DevicePicker] enumerateDevices failed:', e.message);
      return [];
    }
  }

  function classifyDevice(label) {
    const l = (label || '').toLowerCase();
    if (!l || l === 'default' || l.startsWith('communications')) return { type: 'unknown', icon: '🔊' };
    if (l.includes('bluetooth') || l.includes('airpods') || l.includes('bose') ||
        l.includes('jabra') || l.includes('sony wh')) return { type: 'bluetooth', icon: '🎧' };
    if (l.includes('blackhole') || l.includes('vb-audio') || l.includes('virtual') ||
        l.includes('loopback') || l.includes('pipewire')) return { type: 'virtual', icon: '💻' };
    if (l.includes('scarlett') || l.includes('focusrite') || l.includes('apollo') ||
        l.includes('universal audio') || l.includes('presonus') || l.includes('motu') ||
        l.includes('steinberg') || l.includes('audient') || l.includes('ssl')) return { type: 'xlr', icon: '🎚' };
    if (l.includes('yeti') || l.includes('rode') || l.includes('samson') ||
        l.includes('at2020') || l.includes('elgato') || l.includes('hyperx') ||
        l.includes('razer') || l.includes('usb')) return { type: 'usb', icon: '🎙' };
    if (l.includes('built-in') || l.includes('internal') || l.includes('macbook') ||
        l.includes('laptop') || l.includes('realtek')) return { type: 'builtin', icon: '📻' };
    return { type: 'unknown', icon: '🎤' };
  }

  // ── Device picker modal ───────────────────────────────────────────────────
  function showDevicePicker(profileId, profileName, onSelect) {
    // Remove any existing picker
    const existing = document.getElementById('device-picker-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'device-picker-modal';
    modal.innerHTML = `
      <div class="dp-backdrop"></div>
      <div class="dp-panel">
        <div class="dp-header">
          <span class="dp-title">Choose Mic — <em>${escHtml(profileName)}</em></span>
          <button class="dp-close">✕</button>
        </div>
        <p class="dp-desc muted small">
          Select the microphone for this profile. Hold-to-mute and all
          processing settings will apply to the chosen device.
        </p>
        <div class="dp-device-list" id="dp-device-list">
          <div class="dp-loading">Scanning devices…</div>
        </div>
        <div class="dp-footer">
          <button class="dp-refresh ghost">⟳ Refresh</button>
          <span class="dp-hotplug muted small">Plug in a new device and click Refresh</span>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // Wire close
    modal.querySelector('.dp-close').addEventListener('click', () => {modal.remove(); onSelect(null, null, 'cancelled');});
    modal.querySelector('.dp-backdrop').addEventListener('click', () => {modal.remove(); onSelect(null, null, 'cancelled');});

    // Wire refresh
    modal.querySelector('.dp-refresh').addEventListener('click', async () => {
      const list = document.getElementById('dp-device-list');
      if (list) list.innerHTML = '<div class="dp-loading">Rescanning…</div>';
      await requestPermission();
      await enumerateInputDevices();
      renderDeviceList(modal, profileId, onSelect);
      // Also notify backend
      fetch('/api/audio/devices/refresh', { method: 'POST' }).catch(() => {});
    });

    // Initial render
    requestPermission().then(() => {
      enumerateInputDevices().then(() => {
        renderDeviceList(modal, profileId, onSelect);
      });
    });
  }

  function renderDeviceList(modal, profileId, onSelect) {
    const list = document.getElementById('dp-device-list');
    if (!list) return;
    list.innerHTML = '';

    // Load saved preference for this profile
    const pref = loadPreference(profileId);

    if (!_deviceList.length) {
      list.innerHTML = `
        <div class="dp-empty">
          <p>No microphones found.</p>
          <p class="muted small">Check browser permissions: click the 🔒 in your address bar → Allow Microphone.</p>
        </div>
      `;
      return;
    }

    _deviceList.forEach((device, i) => {
      const { type, icon } = classifyDevice(device.label);
      const label          = device.label || `Microphone ${i + 1}`;
      const isPreferred    = pref && (device.deviceId === pref.deviceId || label === pref.label);
      const isDefault      = device.deviceId === 'default' || i === 0;

      const btn = document.createElement('button');
      btn.className = `dp-device-btn${isPreferred ? ' preferred' : ''}`;
      btn.innerHTML = `
        <span class="dp-device-icon">${icon}</span>
        <span class="dp-device-info">
          <span class="dp-device-name">${escHtml(label)}</span>
          <span class="dp-device-meta muted small">${type}${isDefault ? ' · system default' : ''}${isPreferred ? ' · last used' : ''}</span>
        </span>
        ${isPreferred ? '<span class="dp-pref-badge">✓</span>' : ''}
      `;
      btn.addEventListener('click', () => {
        _selectedDeviceId   = device.deviceId;
        _selectedDeviceName = label;
        savePreference(profileId, label, device.deviceId);
        modal.remove();
        onSelect(device.deviceId, label, type);
      });
      list.appendChild(btn);
    });
  }

  // ── Open stream with chosen device ────────────────────────────────────────
  async function openDeviceStream(deviceId, label) {
    const constraints = {
      audio: {
        deviceId:           deviceId ? { exact: deviceId } : true,
        echoCancellation:   false,   // let the user control this via EQ
        noiseSuppression:   false,   // same — don't let browser pre-process
        autoGainControl:    false,   // we have our own gain node
        sampleRate:         { ideal: 48000 },
        channelCount:       { ideal: 1, max: 2 },
        latency:            { ideal: 0.01 },
      },
      video: false,
    };

    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      logger(`Opened: ${label || deviceId || 'default mic'}`);
      return stream;
    } catch (e) {
      throw e;
    }
  }

  function logger(msg) {
    if (window.pubConsole) window.pubConsole.ok('MIC', msg);
    else console.log('[DevicePicker]', msg);
  }

  // ── Hot-plug listener ─────────────────────────────────────────────────────
  function installDeviceChangeListener() {
    if (!navigator.mediaDevices?.addEventListener) return;
    navigator.mediaDevices.addEventListener('devicechange', async () => {
      logger('Device change detected — refreshing device list');
      await enumerateInputDevices();
      renderGlobalDevicePanel();
      // Notify backend
      fetch('/api/audio/devices/refresh', { method: 'POST' }).catch(() => {});
    });
  }

  // ── Global device panel (audio station) ──────────────────────────────────
  function injectGlobalDevicePanel() {
    const audioStation = document.getElementById('station-audio');
    if (!audioStation || document.getElementById('global-device-panel')) return;

    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id        = 'global-device-panel';
    panel.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <h3 style="margin:0;flex:1;">Audio Input Devices</h3>
        <button class="ghost" id="gdp-refresh" style="font-size:.72rem;padding:3px 10px;">⟳ Refresh</button>
        <button class="ghost" id="gdp-guide" style="font-size:.72rem;padding:3px 10px;">Setup Guide</button>
      </div>
      <p class="muted small" style="margin-bottom:10px;">
        Detected on this computer. Plug in a new device and click Refresh.
      </p>
      <div id="gdp-device-list" class="gdp-list">
        <div class="muted small" style="padding:8px 0;">Loading…</div>
      </div>
      <div id="gdp-guide-panel" style="display:none;margin-top:12px;"></div>
    `;

    // Insert at top of audio station
    audioStation.insertBefore(panel, audioStation.firstChild);

    // Wire buttons
    document.getElementById('gdp-refresh')?.addEventListener('click', async () => {
      const list = document.getElementById('gdp-device-list');
      if (list) list.innerHTML = '<div class="muted small" style="padding:8px 0;">Scanning…</div>';
      await requestPermission();
      await enumerateInputDevices();
      renderGlobalDevicePanel();
      fetch('/api/audio/devices/refresh', { method: 'POST' }).catch(() => {});
    });

    document.getElementById('gdp-guide')?.addEventListener('click', () => {
      const guide = document.getElementById('gdp-guide-panel');
      if (!guide) return;
      if (guide.style.display === 'none') {
        fetchInstallGuide().then(html => {
          guide.innerHTML = html;
          guide.style.display = '';
        });
      } else {
        guide.style.display = 'none';
      }
    });

    // Initial scan
    requestPermission().then(() => {
      enumerateInputDevices().then(renderGlobalDevicePanel);
    });
  }

  function renderGlobalDevicePanel() {
    const list = document.getElementById('gdp-device-list');
    if (!list) return;
    list.innerHTML = '';

    if (!_deviceList.length) {
      list.innerHTML = `<p class="muted small">No input devices found. Check browser permissions.</p>`;
      return;
    }

    _deviceList.forEach((device, i) => {
      const { type, icon } = classifyDevice(device.label);
      const label          = device.label || `Microphone ${i + 1}`;

      const row = document.createElement('div');
      row.className = 'gdp-device-row';
      row.innerHTML = `
        <span class="gdp-device-icon">${icon}</span>
        <span class="gdp-device-name">${escHtml(label)}</span>
        <span class="gdp-device-type muted small">${type}</span>
        <button class="ghost gdp-test-btn" data-id="${escHtml(device.deviceId)}"
          style="font-size:.7rem;padding:2px 8px;" title="Test this device">Test</button>
      `;
      list.appendChild(row);
    });

    // Wire test buttons
    list.querySelectorAll('.gdp-test-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        btn.textContent   = '…';
        btn.disabled      = true;
        const deviceId    = btn.dataset.id;
        const name        = btn.closest('.gdp-device-row')?.querySelector('.gdp-device-name')?.textContent || '';
        try {
          const stream = await openDeviceStream(deviceId, name);
          stream.getTracks().forEach(t => t.stop());
          btn.textContent  = '✓ OK';
          btn.style.color  = '#00cc88';
        } catch (e) {
          btn.textContent  = '✗ Fail';
          btn.style.color  = '#e03e3e';
          console.warn('[DevicePicker] Test failed:', e.message);
        }
        setTimeout(() => {
          btn.textContent  = 'Test';
          btn.style.color  = '';
          btn.disabled     = false;
        }, 3000);
      });
    });
  }

  async function fetchInstallGuide() {
    try {
      const r = await fetch('/api/audio/devices/install-guide');
      const d = await r.json();
      const p = d.platform || {};
      const types = d.connection_types || {};

      let html = `<div class="gdp-guide">`;
      html += `<p class="muted small" style="margin-bottom:8px;"><strong>${p.platform || 'Your platform'}</strong></p>`;

      if (p.virtual_routing) {
        const vr = p.virtual_routing;
        html += `
          <div class="gdp-guide-item">
            <strong>${escHtml(vr.name)}</strong>
            <span class="muted small"> — ${escHtml(vr.license)}</span><br/>
            <span class="muted small">${escHtml(vr.description)}</span><br/>
            <code class="muted small">${escHtml(vr.install || '')}</code>
          </div>
        `;
      }

      Object.values(types).forEach(t => {
        html += `
          <div class="gdp-guide-item">
            <strong>${escHtml(t.label)}</strong><br/>
            <span class="muted small">${escHtml(t.examples?.join(', ') || '')}</span><br/>
            <span class="muted small">${escHtml(t.setup || '')}</span>
          </div>
        `;
      });

      html += `</div>`;
      return html;
    } catch (_) {
      return '<p class="muted small">Could not load guide.</p>';
    }
  }

  // ── Public API ────────────────────────────────────────────────────────────
  /**
   * Called by mic_processor.js when user clicks "Activate Mic".
   * Shows device picker, then returns a stream for the chosen device.
   */
  window.micDevicePicker = {
    showPicker: showDevicePicker,
    openStream: openDeviceStream,
    enumerate:  enumerateInputDevices,
    devices:    () => _deviceList,
    selected:   () => ({ deviceId: _selectedDeviceId, label: _selectedDeviceName }),
  };

  // ── Styles ────────────────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('dp-styles')) return;
    const style = document.createElement('style');
    style.id = 'dp-styles';
    style.textContent = `
      /* Modal */
      #device-picker-modal {
        position: fixed; inset: 0; z-index: 9000;
        display: flex; align-items: center; justify-content: center;
      }
      .dp-backdrop {
        position: absolute; inset: 0;
        background: rgba(0,0,0,0.72);
        backdrop-filter: blur(4px);
      }
      .dp-panel {
        position: relative; z-index: 1;
        background: #0c0d10;
        border: 1px solid rgba(201,168,76,0.25);
        border-radius: 12px;
        width: min(480px, 94vw);
        max-height: 80vh;
        display: flex; flex-direction: column;
        box-shadow: 0 20px 60px rgba(0,0,0,0.7);
      }
      .dp-header {
        display: flex; align-items: center; gap: 10px;
        padding: 16px 20px 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
      }
      .dp-title {
        flex: 1; font-size: .88rem; font-weight: 600;
        color: #e8e8e8; letter-spacing: .05em;
      }
      .dp-title em { color: #c9a84c; font-style: normal; }
      .dp-close {
        background: none; border: none; color: rgba(255,255,255,0.4);
        cursor: pointer; font-size: 1rem; padding: 0;
        transition: color .15s;
      }
      .dp-close:hover { color: #fff; }
      .dp-desc { padding: 10px 20px 0; line-height: 1.5; }
      .dp-device-list {
        padding: 10px 16px;
        overflow-y: auto;
        flex: 1;
      }
      .dp-loading { color: rgba(255,255,255,0.4); font-size: .8rem; padding: 12px 0; }
      .dp-empty { padding: 12px 0; }
      .dp-device-btn {
        width: 100%;
        display: flex; align-items: center; gap: 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 6px;
        cursor: pointer;
        text-align: left;
        transition: background .15s, border-color .15s;
        color: #e8e8e8;
      }
      .dp-device-btn:hover { background: rgba(255,255,255,0.07); border-color: rgba(255,255,255,0.15); }
      .dp-device-btn.preferred { border-color: rgba(201,168,76,0.4); background: rgba(201,168,76,0.06); }
      .dp-device-icon { font-size: 1.4rem; flex-shrink: 0; }
      .dp-device-info { display: flex; flex-direction: column; flex: 1; }
      .dp-device-name { font-size: .83rem; font-weight: 500; }
      .dp-device-meta { font-size: .7rem; margin-top: 2px; }
      .dp-pref-badge { color: #c9a84c; font-size: .9rem; margin-left: auto; }
      .dp-footer {
        display: flex; align-items: center; gap: 8px;
        padding: 10px 20px;
        border-top: 1px solid rgba(255,255,255,0.06);
      }
      .dp-hotplug { font-size: .7rem; }

      /* Global device panel */
      .gdp-list { display: flex; flex-direction: column; gap: 6px; }
      .gdp-device-row {
        display: flex; align-items: center; gap: 8px;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
      }
      .gdp-device-icon { font-size: 1.1rem; flex-shrink: 0; }
      .gdp-device-name { flex: 1; font-size: .8rem; color: #ddd; }
      .gdp-device-type {
        font-size: .68rem; letter-spacing: .1em;
        text-transform: uppercase;
        min-width: 60px; text-align: right;
      }

      /* Guide */
      .gdp-guide { margin-top: 4px; }
      .gdp-guide-item {
        background: rgba(255,255,255,0.03);
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 6px;
        font-size: .78rem;
        line-height: 1.5;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Utility ───────────────────────────────────────────────────────────────
  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  function init() {
    injectStyles();
    installDeviceChangeListener();
    injectGlobalDevicePanel();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
