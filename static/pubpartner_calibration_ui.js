/* PubPartner calibration workspace. One shared API for standalone and embedded hosts.
   No invented EQ verdicts. Questions are based on user reports or selected evidence. */
(() => {
  const $ = id => document.getElementById(id);
  const gate = $('calibrationGate');
  if (!gate) return;
  const state = { doc: null, asked: 0, moment: null, moments: [], currentId: null, followup: false, saved: false, audioRef: '', recorder: null, recordingTimer: null, audioUrl: null, audioUploading: false, discardRecording: false };
  // Never supply a proposed emotion before hearing the person's own account.
  // An archived moment is evidence, not an emotional verdict.
  const userQuestions = [
    "Can you tell me what you were feeling at this time, and what made you feel that way?",
    "Is there anything else about what was happening then that would help me understand?",
    "Did I understand what you meant, or is there something I missed?",
    "Was there something going on outside this conversation that matters here?",
    "Is there anything you'd like me to remember about that experience?"
  ];
  const systemQuestions = [
    "How did I come across in this moment? Did I sound like myself?",
    "Was my response helpful, or did I miss what you needed?",
    "Did my personality or tone feel off here?",
    "Did I handle your correction well?",
    "What should I do differently next time?"
  ];
  const errText = e => typeof e === 'string' ? e : (e.message || String(e));
  function say(message) { $('calibrationMessage').textContent = message; }
  function user() {
    const auth = window.ReachAuth?.getUser?.() || {};
    return auth.user_id || auth.username || $('userId')?.value || 'anon';
  }
  function token() { return window.ReachAuth?.getToken?.() || ''; }
  async function call(path, method='GET', payload) {
    const headers = {};
    if (payload !== undefined) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = 'Bearer ' + token();
    headers['X-Client-Id'] = user();
    const res = await fetch('/api/pubpartner' + path, {
      method, headers, body: payload === undefined ? undefined : JSON.stringify(payload)
    });
    const raw = await res.text();
    let data;
    try { data = JSON.parse(raw); } catch { data = { detail: raw }; }
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
    return data;
  }
  function show(id, visible) { $(id).hidden = !visible; }
  function selectedEvidence() {
    return { ...(state.moment ? { session_id: state.moment.session_id, turn_id: state.moment.turn_id || '', source_id: state.moment.source_id || '' } : {}), ...(state.audioRef ? { audio_ref: state.audioRef } : {}) };
  }
  async function loadMoments() {
    state.moments = [];
    const selector = $('calibrationMoment');
    selector.replaceChildren(new Option('No archived moment selected', ''));
    const sessionId = $('sessionId')?.value || 'pubpartner_live';
    try {
      const result = await call('/calibration/moments?session_id=' + encodeURIComponent(sessionId) + '&friend_id=' + encodeURIComponent(state.doc?.partner_id || $('calibrationPartner').value));
      state.moments = result.moments || [];
      state.moments.forEach((moment, index) => {
        selector.add(new Option('Moment ' + (index+1) + ' · ' + (moment.session_id || '') + ': ' + (moment.user_excerpt || '').slice(0,60), String(index)));
      });
    } catch (e) {
      say('Archive review unavailable: ' + errText(e) + '. You can still calibrate from your own account.');
    }
    selectMoment();
  }
  function selectMoment() {
    const v = $('calibrationMoment').value;
    state.moment = v === '' ? null : state.moments[Number(v)] || null;
    if (state.doc?.state === 'formal' && !state.currentId) {
      $('calibrationQuestion').textContent = questionText();
    }
    $('calibrationExcerpt').textContent = state.moment
      ? 'You: ' + (state.moment.user_excerpt || '') + '\nPartner: ' + (state.moment.partner_excerpt || '')
      : 'Select an archived moment if you want to discuss a specific exchange.';
  }
  function questionText() {
    const n = Math.min(state.asked, 4);
    if (state.doc.mode === 'user') {
      if (!state.moment && n === 0)
        return "How are you feeling today? Tell me what's been happening.";
      if (!state.moment && n === 1)
        return "Is there a particular experience you'd like to talk through?";
      return userQuestions[n];
    }
    if (!state.moment && n === 0)
      return "How have I been coming across lately? Is there a particular moment you want me to look at?";
    return systemQuestions[n];
  }
  function renderQuestion() {
    $('calibrationProgress').textContent = 'Main question ' + (state.asked + 1) + ' of up to 5 (aiming for 3)';
    $('calibrationQuestion').textContent = questionText();
    $('calibrationAnswer').value = '';
    $('calibrationFollowup').value = '';
    state.currentId = null; state.followup = false; state.saved = false;
    state.audioRef = ''; clearAudioPreview();
    show('calibrationFollowupBlock', false);
    show('calibrationOfferFollowup', false);
    show('calibrationNext', false);
    $('calibrationSubmit').disabled = false;
    $('calibrationSubmit').textContent = 'Save answer';
    $('calibrationAskFollowup').disabled = false;
    $('calibrationFollowupQuestion').textContent = '';
    $('calibrationNext').textContent = state.asked >= 2 ? 'Another question (optional)' : 'Next question';
  }
  async function playExistingAudio(audioRef) {
    if (!audioRef || !state.doc) return;
    const headers = {};
    if (token()) headers.Authorization = 'Bearer ' + token();
    headers['X-Client-Id'] = user();
    const url = '/api/pubpartner/calibration/interviews/' + state.doc.id + '/audio/' + encodeURIComponent(audioRef);
    const response = await fetch(url, {headers});
    if (!response.ok) throw new Error('Could not load saved voice sample');
    const blob = await response.blob();
    clearAudioPreview();
    state.audioUrl = URL.createObjectURL(blob);
    const player = $('calibrationAudioPreview');
    player.src = state.audioUrl;
    player.hidden = false;
    state.audioRef = audioRef;
  }
  async function listPrevious() {
    const data = await call('/calibration/interviews');
    const list = $('calibrationResumeList');
    list.replaceChildren(new Option('Choose previous session', ''));
    (data.interviews || []).filter(d => d.state !== 'closed').forEach(d => {
      list.add(new Option(d.partner_id + ' · ' + d.mode + ' · ' + d.state + ' · ' + new Date(d.created_at * 1000).toLocaleDateString(), d.id));
    });
  }
  async function resume() {
    const id = $('calibrationResumeList').value;
    if (!id) { say('Select an interview to resume.'); return; }
    state.doc = await call('/calibration/interviews/' + id);
    state.asked = state.doc.main_questions_asked || 0;
    $('calibrationPartner').value = state.doc.partner_id;
    $('calibrationMode').value = state.doc.mode;
    show('calibrationSetup', false);
    await loadMoments();
    if (state.doc.state === 'formal') {
      show('calibrationInterview', true);
      show('calibrationContinuation', false);
      const previous = state.doc.questions?.[state.doc.questions.length - 1];
      if (previous && previous.answer === null) {
        renderQuestion();
        $('calibrationProgress').textContent = 'Main question ' + state.asked + ' of up to 5 (resumed)';
        state.currentId = previous.id;
        $('calibrationQuestion').textContent = previous.text;
      } else if (previous && previous.follow_up && previous.follow_up_answer === null) {
        renderQuestion();
        state.currentId = previous.id;
        state.saved = true;
        state.followup = true;
        $('calibrationQuestion').textContent = previous.text;
        $('calibrationAnswer').value = previous.answer?.text || '';
        $('calibrationSubmit').disabled = true;
        $('calibrationFollowupQuestion').textContent = previous.follow_up.text;
        show('calibrationFollowupBlock', true);
        show('calibrationNext', state.asked < 5);
        if (previous.answer?.evidence?.audio_ref) await playExistingAudio(previous.answer.evidence.audio_ref);
      } else if (state.asked >= 5) {
        await finish();
      } else renderQuestion();
    } else {
      show('calibrationInterview', false);
      show('calibrationContinuation', true);
    }
    say('Calibration resumed from saved interview.');
  }
  async function start() {
    const mode = $('calibrationMode').value;
    const partner_id = $('calibrationPartner').value;
    state.doc = await call('/calibration/interviews', 'POST', { mode, partner_id });
    state.asked = 0; state.currentId = null; state.moment = null;
    show('calibrationSetup', false);
    show('calibrationInterview', true);
    show('calibrationContinuation', false);
    $('calibrationStatus').textContent = mode === 'user'
      ? 'Helping your partner understand you better.'
      : 'Refining your partner’s behavior and presentation.';
    await loadMoments();
    renderQuestion();
    say('You can type or dictate. The microphone is optional.');
  }
  async function event(action, text, question_id) {
    return call('/calibration/interviews/' + state.doc.id + '/events', 'POST', {
      action, text, question_id: question_id || '', evidence: selectedEvidence(),
      modality: state.audioRef && (action === 'answer' || action === 'follow_up_answer') ? 'voice' : 'text'
    });
  }
  async function saveAnswer() {
    if (state.recorder || state.audioUploading) { say('Stop the recording and let it finish saving first.'); return; }
    const answer = $('calibrationAnswer').value.trim() || (state.audioRef ? '[Voice response recorded; no transcript provided]' : '');
    if (!answer) { say('Type, dictate, or record a response, or finish the interview.'); return; }
    if (!state.currentId) {
      const first = await event('main_question', questionText());
      state.currentId = first.questions[first.questions.length - 1].id;
      state.asked = first.main_questions_asked;
    }
    await event('answer', answer, state.currentId);
    state.saved = true;
    $('calibrationSubmit').disabled = true;
    show('calibrationOfferFollowup', true);
    show('calibrationNext', state.asked < 5);
    $('calibrationProgress').textContent = state.asked + ' main questions recorded.';
    say('Saved. An optional follow-up can clarify this answer, or you can continue or finish.');
  }
  function suggestedFollowup() {
    return state.doc.mode === 'system'
      ? 'What would you have preferred me to do differently?'
      : 'Is there anything else you want to tell me about what was happening?';
  }
  async function followup() {
    if (!state.saved || !state.currentId) { say('Save the main answer first.'); return; }
    if (state.followup) { say('One follow-up per main question.'); return; }
    const follow = suggestedFollowup();
    await event('follow_up', follow, state.currentId);
    state.followup = true;
    $('calibrationFollowupQuestion').textContent = follow;
    $('calibrationFollowup').value = '';
    show('calibrationFollowupBlock', true);
    show('calibrationOfferFollowup', false);
    say('Optional follow-up. You may answer, move on, or finish.');
  }
  async function followupAnswer() {
    const text = $('calibrationFollowup').value.trim();
    if (!text) { say('Enter your answer, or skip it.'); return; }
    await event('follow_up_answer', text, state.currentId);
    $('calibrationAskFollowup').disabled = true;
    say('Follow-up answer saved.');
  }
  async function finish() {
    if (!state.doc) return;
    if (state.recorder || state.audioUploading) { say('Stop and save the voice sample before finishing.'); return; }
    state.doc = await call('/calibration/interviews/' + state.doc.id + '/finish', 'POST', {});
    show('calibrationInterview', false);
    show('calibrationContinuation', true);
    $('calibrationStatus').textContent = 'The formal interview is complete. You can keep talking.';
    say('Anything else you want your partner to understand can still be saved.');
  }
  async function saveExtra() {
    const text = $('calibrationExtra').value.trim();
    if (!text) { say('There is no additional feedback to save.'); return; }
    await event('continuation', text);
    $('calibrationExtra').value = '';
    say('Additional feedback saved with your interview.');
  }
  async function approveLesson() {
    const text = $('calibrationLesson').value.trim();
    if (!text) { say('Write the specific correction you want your partner to retain.'); return; }
    const evidence_ids = [state.doc.id, state.moment?.source_id].filter(Boolean);
    await call('/relationship/lessons', 'POST', {
      friend_id: state.doc.partner_id, text,
      kind: state.doc.mode === 'system' ? 'identity' : 'workflow',
      scope: 'global', status: 'confirmed', confidence: 1,
      evidence_ids, metadata: { calibration_id: state.doc.id, calibration_mode: state.doc.mode }
    });
    $('calibrationLesson').value = '';
    say('Approved correction saved in the existing Relationship Engine. It can inform future turns.');
  }
  async function closeSession() {
    abortRecording();
    if (state.doc) await call('/calibration/interviews/' + state.doc.id + '/close', 'POST', {});
    state.doc = null;
    gate.hidden = true;
    show('calibrationSetup', true);
    show('calibrationInterview', false);
    show('calibrationContinuation', false);
  }
  function clearAudioPreview() {
    if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
    state.audioUrl = null;
    const player = $('calibrationAudioPreview');
    player.hidden = true;
    player.removeAttribute('src');
    player.load();
  }
  async function recordAudio() {
    if (!state.doc || state.doc.state !== 'formal') { say('Start an interview first.'); return; }
    if (state.recorder) { say('A recording is already in progress.'); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      say('Voice recording is unavailable in this browser. You can type instead.');
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    try {
      const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
      const mime = candidates.find(m => MediaRecorder.isTypeSupported(m));
      if (!mime) throw new Error('No compatible audio recording format');
      const recorder = new MediaRecorder(stream, {mimeType: mime, audioBitsPerSecond: 24000});
      const chunks = [];
      recorder.ondataavailable = e => { if (e.data?.size) chunks.push(e.data); };
      recorder.onerror = e => say('Recording failed: ' + (e.error?.message || 'unknown error'));
      recorder.onstop = async () => {
        clearTimeout(state.recordingTimer);
        state.recordingTimer = null;
        state.recorder = null;
        stream.getTracks().forEach(t => t.stop());
        show('calibrationStopAudio', false);
        if (state.discardRecording) { state.discardRecording = false; say('Recording discarded.'); return; }
        const blob = new Blob(chunks, {type:mime});
        if (!blob.size) { say('No audio was captured.'); return; }
        if (blob.size > 4 * 1024 * 1024) { say('Recording exceeds the 4 MB storage limit.'); return; }
        state.audioUploading = true;
        try {
          const headers = {'Content-Type':mime};
          if (token()) headers.Authorization = 'Bearer ' + token();
          headers['X-Client-Id'] = user();
          const reply = await fetch('/api/pubpartner/calibration/interviews/' + state.doc.id + '/audio', {
            method:'POST', headers, body:blob
          });
          if (!reply.ok) throw new Error('Audio upload failed: ' + reply.status);
          const stored = await reply.json();
          state.audioRef = stored.audio_ref;
          clearAudioPreview();
          state.audioUrl = URL.createObjectURL(blob);
          const player = $('calibrationAudioPreview');
          player.src = state.audioUrl;
          player.hidden = false;
          say('Voice sample saved. You can play it back, add text, and save your answer.');
        } catch(e) { say('Audio was not saved: ' + errText(e)); }
        finally { state.audioUploading = false; }
      };
      state.recorder = recorder;
      state.discardRecording = false;
      state.audioRef = '';
      clearAudioPreview();
      recorder.start(250);
      show('calibrationStopAudio', true);
      state.recordingTimer = setTimeout(() => recorder.state === 'recording' && recorder.stop(), 60000);
      say('Recording your voice. It will stop automatically at 60 seconds.');
    } catch(e) {
      stream.getTracks().forEach(t => t.stop());
      say('Microphone error: ' + errText(e));
    }
  }
  function stopAudio() {
    if (state.recorder?.state === 'recording') state.recorder.stop();
  }
  function abortRecording() {
    if (state.recorder?.state === 'recording') {
      state.discardRecording = true;
      state.recorder.stop();
    }
  }
  function dictate() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      say('Speech dictation is not available in this browser. Type your response instead. Audio capture is not enabled in this version.');
      return;
    }
    const recognition = new Recognition();
    recognition.lang = navigator.language || 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = e => {
      const words = Array.from(e.results).map(r => r[0]?.transcript || '').join(' ');
      $('calibrationAnswer').value += ($('calibrationAnswer').value ? ' ' : '') + words;
      say('Dictation inserted. Please review the transcription before saving.');
    };
    recognition.onerror = e => say('Microphone dictation: ' + e.error + '. You can type instead.');
    recognition.start();
  }
  function wrap(fn) {
    return () => Promise.resolve().then(fn).catch(e => say('Calibration error: ' + errText(e)));
  }
  $('openCalibrationMenu')?.addEventListener('click', () => {
    gate.hidden = false;
    const current = $('friendId')?.value;
    if (current && [...$('calibrationPartner').options].some(o=>o.value===current)) $('calibrationPartner').value = current;
    listPrevious().catch(e => say('Could not load previous calibrations: ' + errText(e)));
  });
  $('calibrationDismiss').addEventListener('click', () => { abortRecording(); gate.hidden = true; });
  $('calibrationStart').addEventListener('click', wrap(start));
  $('calibrationResume').addEventListener('click', wrap(resume));
  $('calibrationMoment').addEventListener('change', selectMoment);
  $('calibrationSubmit').addEventListener('click', wrap(saveAnswer));
  $('calibrationOfferFollowup').addEventListener('click', wrap(followup));
  $('calibrationAskFollowup').addEventListener('click', wrap(followupAnswer));
  $('calibrationNext').addEventListener('click', wrap(() => {
    if (!state.saved) { say('Save the answer before moving on.'); return; }
    if (state.asked >= 5) return finish();
    renderQuestion();
  }));
  $('calibrationFinish').addEventListener('click', wrap(finish));
  $('calibrationSaveExtra').addEventListener('click', wrap(saveExtra));
  $('calibrationClarify').addEventListener('click', wrap(async () => {
    const question = 'Is there anything else you want me to understand about that experience?';
    await event('clarification', question);
    $('calibrationClarificationText').textContent = question;
    say('You can answer in additional feedback, or simply continue talking.');
  }));
  $('calibrationApplyLesson').addEventListener('click', wrap(approveLesson));
  $('calibrationCloseSession').addEventListener('click', wrap(closeSession));
  $('calibrationDictate').addEventListener('click', dictate);
  $('calibrationRecordAudio').addEventListener('click', wrap(recordAudio));
  $('calibrationStopAudio').addEventListener('click', stopAudio);
})();
