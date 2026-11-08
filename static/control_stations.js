/**
 * PubCast AI — control_stations.js (Phase 1 hardened)
 * Hooks into app.js via window.__pubcastStationsHook and window.__pubcastRecHandler.
 * Add to control.html: <script type="module" src="/static/control_stations.js"></script>
 */

// ── Station tab switcher ──────────────────────────────────────────────────────
(function initStations() {
  const bar = document.getElementById('stations-bar');
  if (!bar) return;
  bar.addEventListener('click', e => {
    const btn = e.target.closest('[data-station]'); if (!btn) return;
    const target = btn.dataset.station;
    document.querySelectorAll('[id^="station-"]').forEach(el => el.classList.add('hidden'));
    bar.querySelectorAll('[data-station]').forEach(b => b.classList.remove('active'));
    const panel = document.getElementById(`station-${target}`);
    if (panel) panel.classList.remove('hidden');
    btn.classList.add('active');
    // This page shares keys with the studio switcher. Keep the switcher
    // disarmed in the editor: SPACE must PLAY, never cut live Program.
    const controlKeys = window.PubCastControlKeys?.km;
    if (controlKeys) {
      if (target === 'director') controlKeys.open('switcher');
      else controlKeys.close();
    }
    if (target === 'recorder') loadRecorderStation();
  });
  // Default to director on load
  const dir = bar.querySelector('[data-station="director"]');
  if (dir) dir.click();
})();

// ── Recording station ─────────────────────────────────────────────────────────
let _timerInterval = null, _recStartTs = null;

async function loadRecorderStation() {
  await refreshStorage();
}

async function refreshStorage() {
  const el = document.getElementById('rec-storage'); if (!el) return;
  try {
    const response = await fetch('/api/recording/storage');
    if (!response.ok) throw new Error('Storage status HTTP ' + response.status);
    const s = await response.json();
    el.textContent = `Local free: ${s.local_free_gb??'—'} GB · Recorded: ${s.recorded_gb??'—'} GB · Cloud: ${s.cloud_used_gb??'—'} GB · Backup: ${s.backup_status??'—'}`;
  } catch(_) { el.innerText = 'Storage info unavailable.'; }
}
document.getElementById('rec-storage-refresh')?.addEventListener('click', refreshStorage);

function startRecTimer(startedAt) {
  _recStartTs = startedAt || (Date.now() / 1000);
  stopRecTimer(); // clear any existing
  setBadge('REC', '#c22');
  const panel = document.getElementById('rec-active-panel'); if (panel) panel.style.display = 'block';
  _timerInterval = setInterval(() => {
    const sec = Math.floor(Date.now()/1000 - _recStartTs);
    const t = document.getElementById('rec-active-timer');
    if (t) t.innerText = `${pad(Math.floor(sec/3600))}:${pad(Math.floor((sec%3600)/60))}:${pad(sec%60)}`;
  }, 1000);
}
function stopRecTimer() {
  if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }
  setBadge('IDLE', '#555');
  const panel = document.getElementById('rec-active-panel'); if (panel) panel.style.display = 'none';
}
function setBadge(text, color) {
  const b = document.getElementById('rec-status-badge'); if (!b) return;
  b.innerText = text; b.style.background = color;
}
function pad(n) { return String(n).padStart(2,'0'); }

// Register as the recording event handler for app.js to call
window.__pubcastRecHandler = function(ev) {
  if (ev.type === 'recording_started') {
    startRecTimer(ev.payload.started_at);
    const idEl = document.getElementById('rec-active-id');
    if (idEl) idEl.innerText = ev.payload.session_id;
  }
  if (ev.type === 'recording_stopped' || ev.type === 'recording_archived') stopRecTimer();
  if (ev.type === 'recording_paused')  setBadge('PAUSED', '#a80');
  if (ev.type === 'recording_resumed') setBadge('REC', '#c22');
};

// General WS hook (receives all events from app.js onWsEvent)
window.__pubcastStationsHook = function(ev) {
  // Forward recording events to the rec handler
  if (ev.type.startsWith('recording_') && typeof window.__pubcastRecHandler === 'function') {
    window.__pubcastRecHandler(ev);
  }
};

// ── Shared production-state controls ────────────────────────────────────────
// A UI action is not completed merely because fetch() resolved: both HTTP and
// the authoritative saved fields must confirm what the director requested.
function stationFeedback(station, message, failed = false) {
  const panel = document.getElementById('station-' + station);
  if (!panel) return;
  let output = panel.querySelector('[data-production-feedback]');
  if (!output) {
    output = document.createElement('output');
    output.dataset.productionFeedback = '';
    output.setAttribute('role', 'status');
    output.style.cssText = 'display:block;margin-top:8px;font-size:12px';
    panel.appendChild(output);
  }
  output.textContent = message;
  output.style.color = failed ? '#ff8080' : '#89d7a6';
}

async function prodPatch(patch) {
  const response = await fetch('/api/state/production', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(patch)
  });
  let data = null;
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'HTTP ' + response.status;
    throw Error('Production command rejected: ' + detail);
  }
  if (!data || typeof data !== 'object' ||
      Object.entries(patch).some(([key, value]) => data[key] !== value)) {
    throw Error('Production command was not confirmed by the host');
  }
  return data;
}

async function stationAction(station, buttonId, task, success) {
  const button = document.getElementById(buttonId);
  if (!button || button.disabled) return;
  button.disabled = true;
  try {
    await task();
    stationFeedback(station, success);
  } catch (error) {
    stationFeedback(station, error.message || 'The command failed', true);
  } finally {
    button.disabled = false;
  }
}

// ── Chyron ────────────────────────────────────────────────────────────────────
document.getElementById('chy-apply')?.addEventListener('click', () => stationAction(
  'chyron', 'chy-apply', () => {
    const patch = {lower_third: document.getElementById('chy-lower')?.value || ''};
    const bug = document.getElementById('chy-bug');
    if (bug) patch.bug = bug.value.trim();
    return prodPatch(patch);
  }, 'Graphics confirmed in the shared production state'
));

// ── Teleprompter ──────────────────────────────────────────────────────────────
let _proTimer = null;
document.getElementById('pro-start')?.addEventListener('click', () => {
  const el = document.getElementById('pro-script');
  if (!el || !el.value.trim()) {
    stationFeedback('prompter', 'Enter a script before starting', true);
    return;
  }
  const inputSpeed = Number(document.getElementById('pro-speed')?.value || 5);
  const speed = Number.isFinite(inputSpeed) ? Math.max(1, Math.min(20, inputSpeed)) : 5;
  if (_proTimer) clearInterval(_proTimer);
  _proTimer = setInterval(() => { el.scrollTop += speed * 0.4; }, 50);
  stationFeedback('prompter', 'Local teleprompter scrolling');
});
document.getElementById('pro-stop')?.addEventListener('click', () => {
  if (_proTimer) { clearInterval(_proTimer); _proTimer = null; }
  stationFeedback('prompter', 'Teleprompter stopped');
});
window.addEventListener('pagehide', () => {
  if (_proTimer) { clearInterval(_proTimer); _proTimer = null; }
});

// ── VTR ───────────────────────────────────────────────────────────────────────
// Replay assets must actually live under /assets/. Remote URLs and traversal
// are not silently converted into fictitious local media paths.
function replayAsset(raw) {
  const input = String(raw || '').trim().replace(/^\/?assets\//i, '');
  if (!input || input.startsWith('/') || input.includes('\\') ||
      /^[a-z][a-z\d+.-]*:/i.test(input) || /[?#\x00-\x1f]/.test(input)) {
    throw Error('Choose a local replay path such as vod/clip.mp4');
  }
  const parts = input.split('/');
  if (parts.some(part => !part || part === '.' || part === '..') ||
      !/\.(mp4|webm|ogv)$/i.test(input)) {
    throw Error('Replay requires an MP4, WebM or Ogg video under /assets/');
  }
  return input;
}
async function requireReplayAsset(asset) {
  const url = '/assets/' + asset.split('/').map(encodeURIComponent).join('/');
  const response = await fetch(url, {method: 'HEAD', cache: 'no-store'});
  if (!response.ok) throw Error('Replay asset not found: ' + asset + ' (HTTP ' + response.status + ')');
  const type = response.headers?.get('content-type') || '';
  if (type && !type.toLowerCase().startsWith('video/')) {
    throw Error('Replay asset is not served as video');
  }
}
async function readProductionState() {
  const response = await fetch('/api/state/production', {cache: 'no-store'});
  if (!response.ok) throw Error('Cannot read production state (HTTP ' + response.status + ')');
  const result = await response.json();
  if (!result || typeof result !== 'object') throw Error('Invalid production state');
  return result;
}
document.getElementById('vtr-load')?.addEventListener('click', () => stationAction(
  'vtr', 'vtr-load', async () => {
    const path = replayAsset(document.getElementById('vtr-asset')?.value);
    await requireReplayAsset(path);
    await prodPatch({mode: 'REPLAY', replay_asset: path, on_air: false});
    document.getElementById('vtr-asset').value = path;
  }, 'Replay asset verified and loaded; press Play to put it on air'
));
document.getElementById('vtr-play')?.addEventListener('click', () => stationAction(
  'vtr', 'vtr-play', async () => {
    const state = await readProductionState();
    if (state.mode !== 'REPLAY' || !state.replay_asset) throw Error('Load a replay asset first');
    await requireReplayAsset(replayAsset(state.replay_asset));
    await prodPatch({on_air: true});
  }, 'Replay on air (browser playback may require interaction)'
));
document.getElementById('vtr-stop')?.addEventListener('click', () => stationAction(
  'vtr', 'vtr-stop', () => prodPatch({on_air: false}), 'Replay taken off air'
));

// ── Shared program audio mixer ───────────────────────────────────────────────
// The 2.5D television production and the walkable studio use ONE /api/program-audio
// state and runtime. Never report a successful mix without successful HTTP responses.
const MIXER_CONTROLS = {master:'mixer-program',dialogue:'mixer-hosts',music:'mixer-music'};
function mixerFeedback(text, failed = false) {
  const apply = document.getElementById('mixer-apply');
  if (!apply) return;
  let node = document.getElementById('mixer-feedback');
  if (!node) {
    node = document.createElement('output');
    node.id = 'mixer-feedback';
    node.style.cssText = 'display:block;margin-top:7px;font-size:12px';
    apply.insertAdjacentElement('afterend', node);
  }
  node.textContent = text;
  node.style.color = failed ? '#ff8080' : '#89d7a6';
}
async function readMixerState() {
  const response = await fetch('/api/program-audio/status', {cache:'no-store'});
  if (!response.ok) throw Error('Audio state HTTP ' + response.status);
  const data = await response.json();
  if (!data.ok || !data.status?.buses) throw Error('Audio state response missing buses');
  return data.status;
}
async function loadMixerState() {
  try {
    const state = await readMixerState();
    for (const [bus,id] of Object.entries(MIXER_CONTROLS)) {
      const el = document.getElementById(id);
      if (!el) continue;
      const value = bus === 'master' ? state.master_volume : state.buses[bus]?.volume;
      if (Number.isFinite(Number(value))) el.value = Math.round(Number(value)*100);
    }
    mixerFeedback('Audio controls synchronized with shared program mixer');
  } catch (error) { mixerFeedback('Audio mixer unavailable: ' + error.message,true); }
}
async function applyMixer() {
  const btn = document.getElementById('mixer-apply');
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  const failures = [];
  try {
    for (const [bus,id] of Object.entries(MIXER_CONTROLS)) {
      const input = document.getElementById(id);
      if (!input) continue;
      const volume = Number(input.value) / 100;
      if (!Number.isFinite(volume) || volume < 0 || volume > 1) {
        failures.push(bus + ': invalid volume');
        continue;
      }
      try {
        const response = await fetch('/api/program-audio/event',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({action:'set_volume',bus,volume})
        });
        if (!response.ok) throw Error('HTTP ' + response.status);
        const result = await response.json();
        if (!result.ok || !result.status) throw Error('missing mixer confirmation');
      } catch (error) { failures.push(bus + ': ' + error.message); }
    }
    if (failures.length) mixerFeedback('Audio update incomplete: '+failures.join('; '),true);
    else mixerFeedback('Program, dialogue and music volumes applied to shared audio engine');
  } finally { btn.disabled = false; }
}
// Program monitoring is a separate, explicitly local listen path. It controls
// the existing Program video element, never changes the broadcast's master mix.
const localProgramMonitor = document.getElementById('pgm-monitor');
const monitorSwitch = document.getElementById('mixer-monitor');
const monitorLevel = document.getElementById('mixer-monitor-level');
function updateLocalProgramMonitor() {
  if (!monitorSwitch || !monitorLevel) return;
  if (!localProgramMonitor) {
    monitorSwitch.checked = false;
    mixerFeedback('Program monitor video is unavailable on this page', true);
    return;
  }
  const value = Number(monitorLevel.value);
  localProgramMonitor.volume = Number.isFinite(value) ? Math.max(0, Math.min(1, value / 100)) : 0.8;
  localProgramMonitor.muted = !monitorSwitch.checked;
  if (monitorSwitch.checked) {
    mixerFeedback(localProgramMonitor.srcObject || localProgramMonitor.currentSrc ?
      'Local Program monitor enabled — use headphones to prevent feedback' :
      'Local Program monitor armed; waiting for a live feed');
  } else mixerFeedback('Local Program monitor muted');
}
monitorSwitch?.addEventListener('change', updateLocalProgramMonitor);
monitorLevel?.addEventListener('input', updateLocalProgramMonitor);
if (localProgramMonitor) localProgramMonitor.muted = true;
// No shared AFV/VTR music-ducking contract exists yet. Never accept an inert
// checkbox as an active production effect.
const afvControl = document.getElementById('mixer-afv');
if (afvControl) {
  afvControl.checked = false;
  afvControl.disabled = true;
  afvControl.title = 'Unavailable: VTR-triggered music ducking requires shared mixer routing and verified recording';
}
document.getElementById('mixer-apply')?.addEventListener('click', () => applyMixer().catch(e => mixerFeedback(e.message,true)));
document.querySelector('[data-station="mixer"]')?.addEventListener('click', () => {loadMixerState();});
document.querySelector('[data-station="audio"]')?.addEventListener('click', () => {loadMixerState();});

// ── Keyboard shortcuts (Space/C = Cut, F = Fade) ──────────────────────────────
// Pages that load the shared key map (static/control_keys.js) get their keys from it, so this fixed set steps aside there.
if (!window.PubCastControlKeys) document.addEventListener('keydown', e => {
  if (document.getElementById('station-director')?.classList.contains('hidden')) return;
  if (e.ctrlKey || e.altKey || e.metaKey || ['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName)) return;
  if (e.code==='Space'||e.key==='c'||e.key==='C') { e.preventDefault(); document.getElementById('vm-cut')?.click(); }
  if (e.key==='f'||e.key==='F') { e.preventDefault(); document.getElementById('vm-take')?.click(); }
});
