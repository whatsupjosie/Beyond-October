/**
 * tts.js — Text-to-Speech panel
 * Local speech uses the shared program dialogue bus.
 * Browser speech is an explicit listening-only alternative.
 */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);

  let voices = [], localVoices = {}, preferences = null;
  let autoplay = false, botsOnly = false, useServer = true, humanize = false;
  let preferenceGeneration = 0, speechGeneration = 0, loading = true;
  const status = message => { if ($('tts-status')) $('tts-status').textContent = message; };
  function stop() { speechGeneration++; window.PubcastSpeech?.stop(); window.speechSynthesis?.cancel(); status('Speech stopped'); }
  window.PubcastProgramAudio?.externalStops.add(() => window.speechSynthesis?.cancel());
  function loadVoices() {
    const select = $('tts-voice'); if (!select) return;
    const chosen = select.value;
    select.replaceChildren();
    if (useServer) {
      for (const [id, voice] of Object.entries(localVoices)) {
        const option = new Option(voice.name + ' (' + voice.language + ')', id);
        select.add(option);
      }
      const desired = preferences?.voice_id;
      if (desired && localVoices[desired]) select.value = desired;
      else if (localVoices[chosen]) select.value = chosen;
      else if (localVoices.af_heart) select.value = 'af_heart';
      select.disabled = !select.options.length || loading;
    } else {
      voices = window.speechSynthesis?.getVoices() || [];
      voices.forEach((voice, index) => select.add(new Option(voice.name + ' (' + voice.lang + ')', String(index))));
      select.disabled = !voices.length;
    }
  }
  async function saveChoice() {
    if (!useServer || !preferences || loading) return;
    const mine = ++preferenceGeneration, select = $('tts-voice'); select.disabled = true;
    try {
      preferences = await window.PubcastSpeech.savePreferences({
        voice_id: select.value, speed: preferences.speed, language: preferences.language,
        expected_revision: preferences.revision
      });
      if (mine === preferenceGeneration) status('Voice choice saved on this host');
    } catch (error) {
      status(error.message);
      try { preferences = await window.PubcastSpeech.preferences(); loadVoices(); } catch (_) {}
    } finally { if (mine === preferenceGeneration) select.disabled = false; }
  }
  async function speakText(text, isBot) {
    if (!text || !window.PubcastProgramAudio?.allowed() || (botsOnly && !isBot)) return;
    const clean = humanize ? humanizeText(text) : text;
    stop(); const mine = ++speechGeneration; status('Preparing speech…');
    if (useServer) {
      try {
        const result = await window.PubcastSpeech.speak(clean, {
          voice_id: $('tts-voice')?.value || undefined,
          onStart: () => { if (mine === speechGeneration) status('Speaking through program dialogue'); }
        });
        if (mine === speechGeneration) status(result.canceled ? 'Speech stopped' : 'Speech finished');
      } catch (error) { if (mine === speechGeneration) status(error.message); }
    } else {
      if (!window.speechSynthesis) { status('Browser speech is unavailable'); return; }
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.voice = voices[Number($('tts-voice')?.value)] || null;
      utterance.onstart = () => status('Browser speech — not captured by the program recording');
      utterance.onend = () => status('Browser speech finished');
      utterance.onerror = () => status('Browser speech stopped or failed');
      window.speechSynthesis.speak(utterance);
    }
  }
  window.speechSynthesis?.addEventListener('voiceschanged', () => { if (!useServer) loadVoices(); });

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

    $('tts-stop')?.addEventListener('click', stop);
    $('tts-voice')?.addEventListener('change', saveChoice);
    if (sayBtn) sayBtn.addEventListener('click', () => {
      speakText(ttsInput?.value || '', false);
    });
    if (autoChk)   autoChk.addEventListener('change',   () => { autoplay = autoChk.checked; });
    if (botsChk)   botsChk.addEventListener('change',   () => { botsOnly = botsChk.checked; });
    if (serverChk) serverChk.addEventListener('change', () => { stop(); useServer = serverChk.checked; loadVoices(); status(useServer ? 'Local speech uses program dialogue' : 'Browser speech — not captured by program recordings'); });
    if (humanChk) humanChk.addEventListener('change', () => { humanize = humanChk.checked; });
    window.PubcastSpeech.bindDictation($('chat-dictate'), $('chat-input'));
    status('Checking local speech…');
    Promise.all([window.PubcastSpeech.voices(), window.PubcastSpeech.preferences()]).then(([catalogue, saved]) => {
      localVoices = catalogue.voices || {}; preferences = saved; loading = false; loadVoices();
      status(catalogue.available ? 'Local ' + catalogue.engine + ' speech configured' : catalogue.reason || 'Local speech is unavailable');
    }).catch(error => { loading = false; loadVoices(); status(error.message); });
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
