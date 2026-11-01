// Minimal choreography preview with stick/mannequin render

const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
const room = 'pub';
const wsUrl = window.ReachAuth
  ? window.ReachAuth.websocketURL(`/ws/${room}`)
  : `${wsProto}://${location.host}/ws/${room}`; // Existing standalone dev embed.

const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const styleSelect = document.getElementById('style-select');
const startBtn = document.getElementById('start-demo');
const stopBtn = document.getElementById('stop-demo');

let socket;
let lastFrame = null;
let style = 'stick';
styleSelect.addEventListener('change', () => {
  style = styleSelect.value;
});

function connectWS() {
  socket = new WebSocket(wsUrl);
  socket.onopen = () => {
    statusEl.textContent = 'WS connected';
  };
  socket.onclose = () => {
    statusEl.textContent = 'WS disconnected';
    setTimeout(connectWS, 1000);
  };
  socket.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'choreo_frame' && msg.payload) {
        // Accept only our room frames if present
        if (msg.payload.room && msg.payload.room !== room) return;
        lastFrame = msg.payload;
        draw();
        statusEl.textContent = `t=${lastFrame.time.toFixed(2)}s avatars=${lastFrame.avatars.length}`;
      } else if (msg.type === 'choreo_stop') {
        lastFrame = null;
        draw();
        statusEl.textContent = 'stopped';
      }
    } catch {}
  };
}

connectWS();

async function startDemo() {
  const steps = [
    // Avatar a1 moves forward 2m over 3s
    {
      avatar_id: 'a1',
      animation_type: 'move',
      start_time: 0,
      duration: 3.0,
      target_position: [2, 0, 0],
    },
    // Avatar a2 turns 90 degrees over 2s
    {
      avatar_id: 'a2',
      animation_type: 'turn',
      start_time: 0.5,
      duration: 2.0,
      target_rotation: [0, Math.PI/2, 0],
    },
  ];
  const avatars = [
    { id: 'a1', position: [-1, 0, 0] },
    { id: 'a2', position: [1, 0, 0] },
  ];
  const res = await fetch('/api/choreo/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ room, tick_hz: 30, avatars, steps }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    statusEl.textContent = `Start failed: ${err.detail || res.status}`;
  }
}

async function stopDemo() {
  await fetch('/api/choreo/stop', { method: 'POST' });
}

startBtn.addEventListener('click', startDemo);
stopBtn.addEventListener('click', stopDemo);

function drawGrid() {
  const w = canvas.width;
  const h = canvas.height;
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= w; x += 40) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for (let y = 0; y <= h; y += 40) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  ctx.restore();
}

function worldToCanvas([x, _y, z]) {
  const w = canvas.width, h = canvas.height;
  const scale = 80; // meters to pixels
  const cx = w / 2 + x * scale;
  const cy = h / 2 - z * scale; // z forward becomes -y on canvas
  return [cx, cy];
}

function drawStick(pos, yaw, color='white') {
  const [cx, cy] = worldToCanvas(pos);
  const size = 50;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-yaw);
  ctx.strokeStyle = color; ctx.lineWidth = 3;
  // Spine
  ctx.beginPath(); ctx.moveTo(0, -size*0.6); ctx.lineTo(0, size*0.4); ctx.stroke();
  // Head
  ctx.beginPath(); ctx.arc(0, -size*0.8, size*0.2, 0, Math.PI*2); ctx.stroke();
  // Arms
  ctx.beginPath(); ctx.moveTo(-size*0.4, -size*0.2); ctx.lineTo(size*0.4, -size*0.2); ctx.stroke();
  // Legs
  ctx.beginPath(); ctx.moveTo(0, size*0.4); ctx.lineTo(-size*0.25, size*0.9); ctx.moveTo(0, size*0.4); ctx.lineTo(size*0.25, size*0.9); ctx.stroke();
  ctx.restore();
}

function drawMannequin(pos, yaw, variant='man_mannequin') {
  const [cx, cy] = worldToCanvas(pos);
  const size = 54;
  const shoulder = variant === 'woman_mannequin' ? 26 : 32;
  const hip = variant === 'woman_mannequin' ? 26 : 24;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-yaw);
  ctx.lineWidth = 2;
  ctx.strokeStyle = 'white';
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  // Torso (capsule)
  const top = -size*0.6, bottom = size*0.5;
  ctx.beginPath();
  ctx.moveTo(-shoulder/2, top);
  ctx.lineTo(shoulder/2, top);
  ctx.quadraticCurveTo(shoulder/2 + 8, top + 10, shoulder/2, top + 20);
  ctx.lineTo(hip/2, bottom - 10);
  ctx.quadraticCurveTo(0, bottom + 14, -hip/2, bottom - 10);
  ctx.lineTo(-shoulder/2, top + 20);
  ctx.quadraticCurveTo(-shoulder/2 - 8, top + 10, -shoulder/2, top);
  ctx.closePath();
  ctx.fill(); ctx.stroke();
  // Head
  ctx.beginPath(); ctx.arc(0, top - 16, 12, 0, Math.PI*2); ctx.stroke();
  // Limbs (simple hints)
  ctx.beginPath();
  ctx.moveTo(-shoulder/2, top + 24); ctx.lineTo(-shoulder/2 - 20, top + 50);
  ctx.moveTo(shoulder/2, top + 24); ctx.lineTo(shoulder/2 + 20, top + 50);
  ctx.moveTo(-hip/4, bottom - 2); ctx.lineTo(-hip/4 - 14, bottom + 34);
  ctx.moveTo(hip/4, bottom - 2); ctx.lineTo(hip/4 + 14, bottom + 34);
  ctx.stroke();
  ctx.restore();
}

function draw() {
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  drawGrid();
  if (!lastFrame) return;
  for (const a of lastFrame.avatars) {
    const pos = a.position || [0,0,0];
    const yaw = (a.rotation && a.rotation[1]) ? a.rotation[1] : 0;
    if (style === 'stick') {
      drawStick(pos, yaw);
    } else {
      drawMannequin(pos, yaw, style);
    }
  }
}

