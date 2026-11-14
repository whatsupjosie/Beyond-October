/* Shared local speech transport. Transcripts are reviewed, never auto-sent. */
(function (global) {
  'use strict';
  if (global.PubcastSpeech) return;
  let generation = 0, controller = null, playing = null;
  async function request(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = global.ReachAuth?.getToken();
    if (token) headers.set('Authorization', 'Bearer ' + token);
    const response = await fetch(url, {...options, headers});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Local speech request failed (' + response.status + ')');
    }
    return response;
  }
  const json = async (url, options) => (await request(url, options)).json();
  function stop() {
    generation++;
    controller?.abort(); controller = null;
    playing?.stop(); playing = null;
  }
  function chunks(text) {
    const result = [];
    while (text.length > 1800) {
      let end = text.lastIndexOf(' ', 1800);
      if (end < 900) end = 1800;
      result.push(text.slice(0, end)); text = text.slice(end);
    }
    if (text) result.push(text);
    return result;
  }
  async function speak(text, options = {}) {
    stop();
    const mine = generation, abort = controller = new AbortController();
    try {
      const mixer = global.PubcastProgramAudio;
      if (!mixer?.allowed()) throw new Error('Speech is unavailable in this room');
      // Resume in the initiating click gesture, before network/model work.
      mixer.ensureContext(); await mixer.context.resume();
      for (const part of chunks(String(text || ''))) {
        if (mine !== generation) return {canceled: true};
        let url = null, handle = null, metadata = null, onError = null, ended = false;
        try {
          const payload = {text: part};
          for (const key of ['voice_id', 'character_id', 'speed', 'language']) {
            if (options[key] != null) payload[key] = options[key];
          }
          const response = await request('/api/tts/synthesize', {
            method: 'POST', signal: abort.signal, headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });
          if (!(response.headers.get('content-type') || '').startsWith('audio/wav')) throw new Error('The speech provider returned no WAV');
          const blob = await response.blob();
          if (mine !== generation) return {canceled: true};
          url = URL.createObjectURL(blob);
          const playbackMetadata = {
            characterId: payload.character_id || 'default', voiceId: response.headers.get('X-Voice'),
            engine: response.headers.get('X-Engine'), duration: Number(response.headers.get('X-Duration')),
            sampleRate: Number(response.headers.get('X-Sample-Rate')), sampleCount: Number(response.headers.get('X-Audio-Samples'))
          };
          handle = await mixer.playUrl(url, {bus: 'dialogue', signal: abort.signal});
          if (mine !== generation) { handle.stop(); return {canceled: true}; }
          playing = handle;
          const completed = new Promise((resolve, reject) => {
            handle.onStop = () => resolve(handle.audio.ended);
            onError = () => reject(new Error('Speech playback failed'));
            handle.audio.addEventListener('error', onError, {once: true});
            if (handle.audio.ended) resolve(true);
          });
          // Observed browser playback metadata, not a sample-accurate lip-sync clock.
          metadata = {...playbackMetadata, observedStart: performance.now()};
          global.dispatchEvent(new CustomEvent('pubcast:speech-start', {detail: metadata}));
          options.onStart?.(metadata);
          ended = await completed;
          if (!ended || mine !== generation) return {canceled: true};
        } catch (error) {
          if (error.name === 'AbortError' || mine !== generation) return {canceled: true};
          throw error;
        } finally {
          if (onError) handle.audio.removeEventListener('error', onError);
          handle?.stop();
          if (playing === handle) playing = null;
          if (url) URL.revokeObjectURL(url);
          if (metadata) {
            global.dispatchEvent(new CustomEvent('pubcast:speech-end', {
              detail: {...metadata, ended, observedEnd: performance.now()}
            }));
          }
        }
      }
      return {canceled: false};
    } finally {
      if (controller === abort) controller = null;
    }
  }

  class Dictation {
    constructor(callbacks = {}) { this.callbacks = callbacks; this.generation = 0; this.state = 'idle'; }
    setState(state) { this.state = state; this.callbacks.onState?.(state); }
    release() {
      clearTimeout(this.timer);
      if (this.owned) this.stream?.getTracks().forEach(track => track.stop());
      this.stream = null; this.owned = false;
    }
    cancel() {
      this.generation++; this.abort?.abort(); this.abort = null;
      if (this.recorder) {
        this.recorder.onstop = null;
        if (this.recorder.state !== 'inactive') this.recorder.stop();
      }
      this.recorder = null; this.release(); this.setState('idle');
    }
    finish() { if (this.recorder?.state === 'recording') this.recorder.stop(); }
    async start(stream = null) {
      this.cancel(); const mine = this.generation;
      this.setState('checking');
      try {
        this.abort = new AbortController();
        const availability = await json('/api/stt/status', {signal: this.abort.signal});
        if (mine !== this.generation) return;
        this.abort = null;
        if (!availability.available) throw new Error(availability.reason || 'Local recognition is unavailable');
        this.setState('permission');
        if (!global.MediaRecorder || (!stream && !navigator.mediaDevices?.getUserMedia)) throw new Error('Microphone recording requires a supported browser on HTTPS or localhost');
        const source = stream || await navigator.mediaDevices.getUserMedia({audio: true});
        if (mine !== this.generation) { if (!stream) source.getTracks().forEach(track => track.stop()); return; }
        this.stream = source; this.owned = !stream;
        const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find(value => MediaRecorder.isTypeSupported(value));
        const recorder = this.recorder = new MediaRecorder(source, mime ? {mimeType: mime} : {});
        const parts = []; let bytes = 0;
        recorder.ondataavailable = event => {
          if (mine !== this.generation) return;
          bytes += event.data.size;
          if (bytes > 8 * 1024 * 1024) { this.cancel(); this.callbacks.onError?.(new Error('Dictation exceeds 8 MiB; record a shorter passage')); }
          else if (event.data.size) parts.push(event.data);
        };
        recorder.onerror = () => { this.cancel(); this.callbacks.onError?.(new Error('Microphone recording failed')); };
        recorder.onstop = async () => {
          if (mine !== this.generation) return;
          this.release(); this.recorder = null; this.setState('transcribing');
          this.abort = new AbortController();
          try {
            const blob = new Blob(parts, {type: recorder.mimeType || 'audio/webm'});
            if (!blob.size) throw new Error('No microphone audio was captured');
            const result = await json('/api/stt/transcribe', {method: 'POST', signal: this.abort.signal,
              headers: {'Content-Type': blob.type}, body: blob});
            if (mine === this.generation) this.callbacks.onTranscript?.(result);
          } catch (error) { if (mine === this.generation && error.name !== 'AbortError') this.callbacks.onError?.(error); }
          finally { if (mine === this.generation) { this.abort = null; this.setState('idle'); } }
        };
        recorder.start(1000); this.setState('recording');
        this.timer = setTimeout(() => this.finish(), 55000);
      } catch (error) {
        if (mine === this.generation) { this.cancel(); this.callbacks.onError?.(error); }
      }
    }
  }
  function bindDictation(button, input) {
    if (!button || !input) return null;
    const review = document.createElement('div'); review.hidden = true; review.dataset.dictationReview = '';
    const status = document.createElement('span'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const draft = document.createElement('textarea'); draft.setAttribute('aria-label', 'Review dictated text'); draft.rows = 3; draft.style.width = '100%';
    const insert = document.createElement('button'); insert.type = 'button'; insert.textContent = 'Insert';
    const discard = document.createElement('button'); discard.type = 'button'; discard.textContent = 'Discard';
    review.append(draft, insert, discard); button.parentElement.after(status, review);
    const original = button.textContent;
    const dictation = new Dictation({
      onState(state) {
        button.classList.toggle('listening', state === 'recording');
        button.textContent = state === 'recording' ? 'Finish dictation' : state === 'idle' ? original : 'Cancel dictation';
        button.setAttribute('aria-pressed', String(state !== 'idle'));
        if (state !== 'idle') status.textContent = state === 'recording' ? 'Listening — finish within 55 seconds' : state === 'checking' ? 'Checking local recognition…' : state === 'permission' ? 'Waiting for microphone permission' : 'Transcribing locally…';
      },
      onTranscript(result) {
        draft.value = result.text || ''; review.hidden = !draft.value;
        status.textContent = draft.value ? 'Review the transcript, then Insert or Discard' : 'No speech recognized';
      },
      onError(error) { status.textContent = error.message; }
    });
    button.disabled = false; button.title = 'Dictate locally; review before inserting';
    button.onclick = () => {
      if (dictation.state === 'recording') dictation.finish();
      else if (dictation.state === 'idle') dictation.start();
      else { dictation.cancel(); status.textContent = 'Dictation canceled'; }
    };
    insert.onclick = () => {
      const text = draft.value;
      if (text) {
        const start = input.selectionStart ?? input.value.length, end = input.selectionEnd ?? start;
        // Insert at the current caret. Existing text is never replaced by recognition.
        const prefix = start > 0 && !/\s/.test(input.value[start - 1]) ? ' ' : '';
        const suffix = end < input.value.length && !/\s/.test(input.value[end]) ? ' ' : '';
        input.setRangeText(prefix + text + suffix, start, start, 'end');
        input.dispatchEvent(new Event('input', {bubbles: true})); input.focus();
      }
      review.hidden = true; draft.value = ''; status.textContent = 'Inserted; ready for you to send';
    };
    discard.onclick = () => { review.hidden = true; draft.value = ''; status.textContent = 'Dictation discarded'; };
    global.addEventListener('pagehide', () => dictation.cancel());
    return dictation;
  }
  global.PubcastSpeech = {speak, stop, Dictation, bindDictation,
    status: () => Promise.all([json('/api/stt/status'), json('/api/tts/status')]),
    voices: () => json('/api/tts/voices'), preferences: () => json('/api/tts/preferences'),
    savePreferences: value => json('/api/tts/preferences', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)})};
  global.PubcastProgramAudio?.externalStops.add(stop);
  global.addEventListener('pagehide', stop);
})(window);
