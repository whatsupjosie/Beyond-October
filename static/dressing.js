/* ═══════════════════════════════════════════════════════════════
   PubCast Dressing Room — Wooden Stage → Foundry Platform
   ═══════════════════════════════════════════════════════════════ */

// ── STATE ──────────────────────────────────────────────────────
const state = {
  foundryActive: false,
  photos: {},
  quality: 'TRACK',
  fineFace: true,
  baking: false,
  baked: false,
  mood: 'ELEVATED',
  glowColor: '#00d4ff',
};

const QUALITY_RES = { 
  SURFACE: 48, 
  TRACK: 64, 
  ORBITAL: 96 
};

// ═══════════════════════════════════════════════════════════════
// FOUNDRY ACTIVATION / DEACTIVATION
// ═══════════════════════════════════════════════════════════════

function activateFoundry() {
  state.foundryActive = true;
  
  // Hide wooden stage, show foundry platform
  document.getElementById('wooden-stage').style.opacity = '0';
  setTimeout(() => {
    document.getElementById('wooden-stage').style.display = 'none';
    document.getElementById('foundry-platform').style.display = 'flex';
    setTimeout(() => {
      document.getElementById('foundry-platform').style.opacity = '1';
    }, 50);
  }, 400);
  
  // Switch button visibility
  document.getElementById('activate-foundry').style.display = 'none';
  document.getElementById('deactivate-foundry').style.display = 'block';
  
  // Switch panel to foundry mode
  document.getElementById('customizer-panel').style.display = 'none';
  document.getElementById('foundry-panel').style.display = 'block';
  document.getElementById('panel-title').textContent = 'Avatar Foundry';
  
  // Auto-open panel
  const panel = document.getElementById('wardrobe-panel');
  if (!panel.classList.contains('open')) {
    panel.classList.add('open');
  }
  
  toast('FOUNDRY ENGAGED — UPLOAD PHOTOS TO BEGIN');
}

function deactivateFoundry() {
  state.foundryActive = false;
  
  // Hide foundry platform, show wooden stage
  document.getElementById('foundry-platform').style.opacity = '0';
  setTimeout(() => {
    document.getElementById('foundry-platform').style.display = 'none';
    document.getElementById('wooden-stage').style.display = 'flex';
    setTimeout(() => {
      document.getElementById('wooden-stage').style.opacity = '1';
    }, 50);
  }, 400);
  
  // Switch button visibility
  document.getElementById('deactivate-foundry').style.display = 'none';
  document.getElementById('activate-foundry').style.display = 'block';
  
  // Switch panel back to customizer
  document.getElementById('foundry-panel').style.display = 'none';
  document.getElementById('customizer-panel').style.display = 'block';
  document.getElementById('panel-title').textContent = 'Avatar Customizer';
}

// Make functions globally available
window.activateFoundry = activateFoundry;
window.deactivateFoundry = deactivateFoundry;

// ═══════════════════════════════════════════════════════════════
// WARDROBE PANEL
// ═══════════════════════════════════════════════════════════════

function toggleWardrobe() {
  const panel = document.getElementById('wardrobe-panel');
  panel.classList.toggle('open');
}

function closePanel() {
  const panel = document.getElementById('wardrobe-panel');
  panel.classList.remove('open');
}

window.toggleWardrobe = toggleWardrobe;
window.closePanel = closePanel;

// ═══════════════════════════════════════════════════════════════
// FOUNDRY TABS
// ═══════════════════════════════════════════════════════════════

window.switchTab = function(id, btn) {
  document.querySelectorAll('.panel-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
};

// ═══════════════════════════════════════════════════════════════
// PHOTO UPLOAD
// ═══════════════════════════════════════════════════════════════

window.fileChosen = function(evt, part) {
  const file = evt.target.files[0];
  if (file) loadPhoto(file, part);
};

window.dragOver = function(evt, el) {
  evt.preventDefault();
  el.classList.add('dragging');
};

window.dragLeave = function(el) {
  el.classList.remove('dragging');
};

window.dropFile = function(evt, part) {
  evt.preventDefault();
  const el = document.getElementById('slot-' + part);
  el.classList.remove('dragging');
  const file = evt.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    loadPhoto(file, part);
  }
};

function loadPhoto(file, part) {
  state.photos[part] = file;
  const slot = document.getElementById('slot-' + part);
  
  const reader = new FileReader();
  reader.onload = e => {
    let img = slot.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      slot.appendChild(img);
    }
    img.src = e.target.result;
    slot.classList.add('has-photo');
  };
  reader.readAsDataURL(file);
  
  log(`Photo loaded: ${part.toUpperCase()} (${(file.size / 1024).toFixed(0)}KB)`, 'ok');
  updateBakeBtn();
}

function updateBakeBtn() {
  const btn = document.getElementById('bake-btn');
  if (btn) {
    btn.disabled = !state.photos.face;
  }
}

// ═══════════════════════════════════════════════════════════════
// QUALITY, FINE FACE, MOOD
// ═══════════════════════════════════════════════════════════════

window.setQuality = function(q, btn) {
  state.quality = q;
  document.querySelectorAll('.quality-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
};

window.toggleFineFace = function(btn) {
  btn.classList.toggle('on');
  state.fineFace = btn.classList.contains('on');
  const detail = document.getElementById('fine-face-detail');
  if (detail) {
    detail.style.opacity = state.fineFace ? '1' : '0.3';
  }
};

window.setMood = function(m, btn) {
  state.mood = m;
  document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
};

// ═══════════════════════════════════════════════════════════════
// GLOW COLOR SWATCHES
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.swatch').forEach(sw => {
    sw.addEventListener('click', () => {
      document.querySelectorAll('.swatch').forEach(s => s.classList.remove('active'));
      sw.classList.add('active');
      state.glowColor = sw.dataset.color;
    });
  });
  
  // Wire up event listeners
  document.getElementById('wardrobe-toggle')?.addEventListener('click', toggleWardrobe);
  document.getElementById('close-panel')?.addEventListener('click', closePanel);
  document.getElementById('activate-foundry')?.addEventListener('click', activateFoundry);
  document.getElementById('deactivate-foundry')?.addEventListener('click', deactivateFoundry);
  
  // Initialize
  updateBakeBtn();
});

// ═══════════════════════════════════════════════════════════════
// BAKE SEQUENCE
// ═══════════════════════════════════════════════════════════════

window.startBake = async function() {
  if (state.baking || !state.photos.face) return;
  state.baking = true;

  const btn = document.getElementById('bake-btn');
  btn.disabled = true;
  document.getElementById('progress-wrap').classList.add('visible');
  document.getElementById('stats-grid').classList.remove('visible');
  clearLog();

  const parts = Object.keys(state.photos);
  const res = QUALITY_RES[state.quality];
  const faceRes = state.fineFace ? res * 2 : res;

  const steps = [
    { label: 'Connecting to Sculptor…', pct: 5 },
    state.fineFace
      ? { label: `Fine-voxel face sculpt @ ${faceRes}px…`, pct: 18, fn: () => simulateBakePart('FACE', faceRes, 1.2) }
      : null,
    state.fineFace
      ? { label: 'Mesh-baking face to geometry…', pct: 32, fn: () => sleep(600) }
      : null,
    parts.includes('torso')
      ? { label: `Sculpting TORSO @ ${res}px…`, pct: 48, fn: () => simulateBakePart('TORSO', res, 1.5) }
      : null,
    { label: 'Generating weight maps…', pct: 82, fn: () => sleep(400) },
    { label: 'Baking 3D normals + AO…', pct: 90, fn: () => sleep(500) },
    { label: 'Sending to Avatar Bridge…', pct: 96, fn: () => uploadToServer() },
    { label: 'Forge complete.', pct: 100 },
  ].filter(Boolean);

  for (const step of steps) {
    setProgress(step.label, step.pct);
    if (step.fn) await step.fn();
    await sleep(80);
  }

  state.baking = false;
  state.baked = true;
  btn.disabled = false;
  btn.textContent = '⬡ RE-FORGE AVATAR';

  const totalVoxels = estimateVoxels(parts, res, faceRes);
  document.getElementById('sv').textContent = totalVoxels.toLocaleString();
  document.getElementById('sg').textContent = (Math.random() * 0.4 + 0.5).toFixed(3);
  document.getElementById('sm').textContent = state.quality;
  document.getElementById('stats-grid').classList.add('visible');

  log('AVATAR MANIFESTED AT ORBITAL VELOCITY', 'ok');
  toast('✓ Avatar baked and mounted to skeleton');
};

async function simulateBakePart(label, res, thick) {
  await sleep(Math.random() * 300 + 200);
  log(`${label}: ${res}³ vol · ×${thick} thick · shell-culled`, 'active');
}

async function uploadToServer() {
  if (!state.photos.face) return;
  
  try {
    const form = new FormData();
    form.append('file', state.photos.face);
    form.append('mode', state.quality);
    
    const r = await fetch('/api/avatars/me/bake', { 
      method: 'POST', 
      body: form 
    });
    
    if (r.ok) {
      const d = await r.json();
      if (d.ok && d.bake) {
        document.getElementById('sv').textContent = d.bake.voxel_count.toLocaleString();
        document.getElementById('sg').textContent = d.bake.grit_index.toFixed(3);
        log('Bridge sync: CONFIRMED', 'ok');
      }
    }
  } catch (e) {
    log('Bridge offline — local bake saved', 'warn');
  }
}

function estimateVoxels(parts, res, faceRes) {
  let v = Math.floor(faceRes * faceRes * faceRes * 0.18);
  parts.forEach(p => {
    if (p !== 'face') v += Math.floor(res * res * res * 0.15);
  });
  return v;
}

// ═══════════════════════════════════════════════════════════════
// PROGRESS & LOG
// ═══════════════════════════════════════════════════════════════

function setProgress(label, pct) {
  document.getElementById('progress-stage').textContent = label;
  document.getElementById('progress-pct').textContent = pct + '%';
  document.getElementById('progress-fill').style.width = pct + '%';
  log(label, pct === 100 ? 'ok' : 'active');
}

function log(msg, type = '') {
  const el = document.getElementById('forge-log');
  if (!el) return;
  
  const line = document.createElement('span');
  line.className = 'log-line' + (type ? ' log-' + type : '');
  line.textContent = `> ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function clearLog() {
  const el = document.getElementById('forge-log');
  if (el) el.innerHTML = '';
}

// ═══════════════════════════════════════════════════════════════
// SAVE IDENTITY
// ═══════════════════════════════════════════════════════════════

window.saveLook = async function() {
  const payload = {
    display_name: document.getElementById('foundry-display-name')?.value?.trim() || 'New Avatar',
    gender: document.getElementById('foundry-gender')?.value || 'neutral',
    mood: state.mood,
    primary_color: state.glowColor,
  };
  
  try {
    const r = await fetch('/api/avatars/me', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    
    const fb = document.getElementById('save-feedback');
    if (fb) {
      fb.textContent = r.ok ? '✓ SAVED' : 'SAVE FAILED';
      setTimeout(() => { fb.textContent = ''; }, 2500);
    }
  } catch (e) {
    const fb = document.getElementById('save-feedback');
    if (fb) fb.textContent = 'OFFLINE';
  }
};

// ═══════════════════════════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════════════════════════

function toast(msg) {
  const el = document.getElementById('toast');
  if (!el) return;
  
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

console.info('[PubCast] Dressing room with wooden stage → foundry platform loaded');
