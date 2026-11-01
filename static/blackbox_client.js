/* Control-room capture and two independent indicators. No media browsing API. */
(function () {
  'use strict';
  const captureEnabled = document.currentScript?.dataset.capture !== 'false';
  let socket, node, source, micStream, captureId, restarting = false, stopping = false;
  let captureError = '', retryTimer, pollTimer;
  const connections = new Map();
  let healthSequence = 0, flushed;
  function paint(which, state) {
    const light = document.getElementById('bb-' + which);
    if (!light) return;
    light.dataset.state = state;
    light.title = which + ': ' + state;
    light.setAttribute('aria-label', which + ': ' + state);
  }
  async function poll() {
    const sequence = ++healthSequence;
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 1500);
    try {
      const r = await fetch('/api/operator/blackbox/health', {signal: controller.signal});
      if (!r.ok) throw new Error('Health check HTTP ' + r.status);
      const status = await r.json();
      if (sequence !== healthSequence) return;
      paint('connection', status.connection);
      paint('recording', captureError ? 'crashed' : restarting ? 'restarting' : status.recording);
      const message = document.getElementById('bb-message');
      if (message) message.textContent = captureError || (status.recording === 'running' ? 'Audio capture active' : 'Audio capture inactive');
    } catch (error) {
      if (sequence !== healthSequence) return;
      paint('connection', restarting ? 'restarting' : 'crashed');
      paint('recording', 'crashed');
    } finally {clearTimeout(deadline);}
  }
  function attachProcessed(profileId, stream) {
    const ctx = window.PubcastProgramAudio?.context;
    const master = window.PubcastProgramAudio?.master;
    if (!ctx || !master) return;
    connections.get(profileId)?.disconnect();
    const input = ctx.createMediaStreamSource(stream);
    // Feed capture only. Monitoring the microphone is a separate opt-in.
    const capture = window.PubcastProgramAudio.captureMix;
    input.connect(capture);
    connections.set(profileId, input);
  }
  async function start() {
    if (socket || stopping) return;
    clearTimeout(retryTimer);
    restarting = !!captureError; captureError = ''; await poll();
    try {
      const audio = window.PubcastProgramAudio;
      const ctx = audio.ensureContext();
      await ctx.resume();
      if (ctx.state !== 'running') throw new Error('Enable audio to start recording');
      // Program output and active processed microphone outputs share one sink.
      if (!audio.captureMix) {
        audio.captureMix = ctx.createGain();
        audio.master.connect(audio.captureMix);
      }
      await ctx.audioWorklet.addModule('/static/blackbox_pcm_worklet.js');
      const configured = window.micDevicePicker?.selected()?.deviceId;
      const active = window.micProcessor?.activeStreams?.() || [];
      if (active.length) {
        for (const entry of active) attachProcessed(entry.profileId, entry.stream);
      } else {
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: configured ? {deviceId: {exact: configured}} : true, video: false
        });
        source = ctx.createMediaStreamSource(micStream);
        source.connect(audio.captureMix);
        for (const track of micStream.getAudioTracks()) track.onended = () => fail('Microphone disconnected');
      }
      const url = new URL('/api/operator/blackbox/capture', location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(url.href);
      socket.binaryType = 'arraybuffer';
      await new Promise((resolve, reject) => {
        socket.onopen = () => socket.send(JSON.stringify({source: 'control-room-mix', encoding: 'pcm-s16le', sample_rate: ctx.sampleRate, channels: 1}));
        socket.onerror = () => reject(new Error('Capture connection failed'));
        socket.onclose = () => reject(new Error('Capture source rejected'));
        socket.onmessage = event => {
          const receipt = JSON.parse(event.data);
          if (!receipt.ok) { reject(new Error('Capture not acknowledged')); return; }
          captureId = receipt.capture_id;
          resolve();
        };
      });
      node = new AudioWorkletNode(ctx, 'blackbox-pcm');
      audio.captureMix.connect(node);
      // The worklet emits silence to the speaker; its input is sent only to the sink.
      node.connect(ctx.destination);
      node.port.onmessage = event => {
        if (event.data === 'flushed') {flushed?.(); return;}
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        if (socket.bufferedAmount > ctx.sampleRate * 4) { fail('Recording connection is too slow'); return; }
        socket.send(event.data);
      };
      socket.onclose = () => { if (!stopping) fail('Recording disconnected'); };
      socket.onerror = () => fail('Recording connection failed');
      restarting = false; await poll();
    } catch (error) { fail(error.message); }
  }
  function release() {
    if (node) {
      try { window.PubcastProgramAudio.captureMix.disconnect(node); } catch (_) {}
      node.disconnect(); node.port.onmessage = null; node = null;
    }
    source?.disconnect(); source = null;
    micStream?.getTracks().forEach(t => {t.onended = null; t.stop();}); micStream = null;
    for (const input of connections.values()) input.disconnect();
    connections.clear();
    if (socket) {socket.onclose = null; socket.onerror = null; socket.close(); socket = null;}
    captureId = null;
  }
  function fail(message) {
    release(); captureError = message; restarting = false; poll();
    // Authentication/permission/device recovery is explicit through Enable audio.
  }
  async function stop() {
    stopping = true;
    if (node) {
      await Promise.race([new Promise(resolve => {flushed = resolve; node.port.postMessage('flush');}),
        new Promise(resolve => setTimeout(resolve, 500))]);
      flushed = null;
    }
    if (socket?.readyState === WebSocket.OPEN) socket.send('stop');
    release(); clearTimeout(retryTimer); clearInterval(pollTimer);
  }
  window.addEventListener('pubcast:mic-stream', event => {
    if (!socket) return;
    // A processed mic replaces the unprocessed default to avoid a doubled voice.
    source?.disconnect(); source = null;
    micStream?.getTracks().forEach(t => {t.onended = null; t.stop();}); micStream = null;
    attachProcessed(event.detail.profileId, event.detail.stream);
  });
  window.addEventListener('pubcast:mic-stopped', event => {
    connections.get(event.detail.profileId)?.disconnect(); connections.delete(event.detail.profileId);
    if (!connections.size) fail('No microphone is active');
  });
  function init() {
    const box = document.createElement('div'); box.id = 'blackbox-indicators';
    box.innerHTML = '<span id="bb-connection" class="bb-light" data-state="inactive" role="status"></span> Connection <span id="bb-recording" class="bb-light" data-state="inactive" role="status"></span> Recording <button id="bb-enable" type="button">Enable audio</button> <span id="bb-message"></span>';
    document.body.prepend(box);
    const style = document.createElement('style');
    style.textContent = '#blackbox-indicators{display:flex;align-items:center;gap:8px;padding:8px;font-size:12px}.bb-light{display:inline-block;width:11px;height:11px;border-radius:50%;background:#cf3030}.bb-light[data-state="running"],.bb-light[data-state="restarting"]{background:#28bd62}.bb-light[data-state="crashed"],.bb-light[data-state="restarting"]{animation:bb-blink .7s infinite alternate}@keyframes bb-blink{to{opacity:.15}}';
    document.head.appendChild(style);
    document.getElementById('bb-enable').onclick = start;
    if (!captureEnabled) {
      document.getElementById('bb-enable').remove();
      box.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:1000;background:#171717;color:#eee;border-radius:8px';
    }
    poll(); pollTimer = setInterval(poll, 2000);
    if (captureEnabled) start(); // Browser permission/autoplay failures remain visible and retryable.
  }
  window.PubcastBlackbox = {start, stop, captureId: () => captureId};
  window.addEventListener('pagehide', stop);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
