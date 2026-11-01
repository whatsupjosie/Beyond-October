/**
 * tts.js — Text-to-Speech panel
 * Uses Web Speech API (no server required for basic mode).
 * Server TTS mode posts to /api/tts/synthesize when PUBCAST_TTS_ENABLED=1.
 */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);

  let voices = [];
  let generation = 0;
  let controller = null;
  function stop() {generation++; controller?.abort(); controller = null; window.speechSynthesis?.cancel();}
  window.PubcastProgramAudio?.externalStops.add(stop);
  let autoplay = false;
  let botsOnly = false;
  let useServer = false;
  let humanize  = false;

  // ── Load voices ──────────────────────────────────────────────────────────
  function loadVoices() {
    if (!window.speechSynthesis) return;
    voices = speechSynthesis.getVoices();
    const sel = $('tts-voice');
    if (!sel) return;
    sel.innerHTML = '';
    voices.forEach((v, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${v.name} (${v.lang})`;
      if (v.default) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  if (window.speechSynthesis) {
    loadVoices();
    speechSynthesis.onvoiceschanged = loadVoices;
  }

  // ── Speak function ────────────────────────────────────────────────────────
  function speakText(text, isBot) {
    if (!text || !window.PubcastProgramAudio?.allowed()) return;
    if (botsOnly && !isBot) return;

    const clean = humanize ? humanizeText(text) : text;

    if (useServer) {
      speakServer(clean);
      return;
    }

    if (!window.speechSynthesis) return;
    const utter = new SpeechSynthesisUtterance(clean);
    const sel = $('tts-voice');
    const idx = sel ? parseInt(sel.value, 10) : 0;
    if (voices[idx]) utter.voice = voices[idx];
    utter.rate  = 1.0;
    utter.pitch = 1.0;
    speechSynthesis.speak(utter);
  }

  async function speakServer(text) {
    const mine = ++generation;
    controller?.abort();
    controller = new AbortController();
    try {
      const r = await fetch('/api/tts/synthesize', {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error("TTS HTTP " + r.status);
      if (!(r.headers.get("content-type") || "").startsWith("audio/")) throw new Error("TTS returned non-audio content");
      const blob = await r.blob();
      const url  = URL.createObjectURL(blob);
      if (mine !== generation) { URL.revokeObjectURL(url); return; }
      try {
        const handle = await window.PubcastProgramAudio.playUrl(url, {bus: 'dialogue'});
        handle.onStop = () => URL.revokeObjectURL(url);
        handle.audio.addEventListener('ended', () => URL.revokeObjectURL(url), {once: true});
      } catch (error) {URL.revokeObjectURL(url); throw error;}
    } catch (e) {
      console.warn('Server TTS failed', e);
    }
  }

  // ── Humanizer: flatten markdown / remove brackets etc ────────────────────
  function humanizeText(t) {
    return t
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`[^`]+`/g, match => match.slice(1,-1))
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/#+\s/g, '')
      .replace(/\n+/g, '. ')
      .trim();
  }

  // ── Expose globally so ws.js / app.js can call speakText on incoming chat ─
  window.tts = { speak: speakText, stop, setAutoplay: value => {autoplay = !!value; if ($('tts-autoplay')) $('tts-autoplay').checked = autoplay;} };

  // ── Controls ──────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const sayBtn     = $('tts-say');
    const autoChk    = $('tts-autoplay');
    const botsChk    = $('tts-bots-only');
    const serverChk  = $('tts-server');
    const humanChk   = $('tts-humanize');
    const ttsInput   = $('tts-text');

    if (sayBtn) sayBtn.addEventListener('click', () => {
      speakText(ttsInput?.value || '', false);
    });
    if (autoChk)   autoChk.addEventListener('change',   () => { autoplay = autoChk.checked; });
    if (botsChk)   botsChk.addEventListener('change',   () => { botsOnly = botsChk.checked; });
    if (serverChk) serverChk.addEventListener('change', () => { useServer = serverChk.checked; });
    if (humanChk)  humanChk.addEventListener('change',  () => { humanize = humanChk.checked; });
  });

  // ── Hook into incoming WS messages to autoplay chat ──────────────────────
  const _origOnMessage = window._wsOnMessage;
  window._wsOnMessage = function (data) {
    if (_origOnMessage) _origOnMessage(data);
    if (!autoplay) return;
    if (data.type === 'chat') {
      const isBot = String(data.payload?.user_id || '').startsWith('bot-');
      speakText(data.payload?.text || '', isBot);
    }
  };
})();
