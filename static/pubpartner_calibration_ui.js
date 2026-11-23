/* PubPartner calibration workspace. One shared API for standalone and embedded hosts.
   No invented EQ verdicts. Questions are based on user reports or selected evidence. */
(() => {
  const $ = id => document.getElementById(id);
  const gate = $('calibrationGate');
  if (!gate) return;
  const state = { doc: null, asked: 0, moment: null, moments: [], currentId: null, followup: false, saved: false };
  const userQuestions = [
    "How are you feeling today? Tell me a little about your day.",
    "Thinking about this moment, were you upset, excited, or feeling something else?",
    "Was there anything in that exchange that I misunderstood?",
    "Was something I said bothering you, or was it something else?",
    "Is there anything important about that moment I still haven't understood?"
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
    return state.moment ? { session_id: state.moment.session_id, turn_id: state.moment.turn_id || '', source_id: state.moment.source_id || '' } : {};
  }
  async function loadMoments() {
    state.moments = [];
    const selector = $('calibrationMoment');
    selector.replaceChildren(new Option('No archived moment selected', ''));
    const sessionId = $('sessionId')?.value || 'pubpartner_live';
    try {
      const result = await call('/calibration/moments?session_id=' + encodeURIComponent(sessionId));
      state.moments = result.moments || [];
      state.moments.forEach((moment, index) => {
        selector.add(new Option('Moment ' + (index+1) + ': ' + (moment.user_excerpt || '').slice(0,70), String(index)));
      });
    } catch (e) {
      say('Archive review unavailable: ' + errText(e) + '. You can still calibrate from your own account.');
    }
    selectMoment();
  }
  function selectMoment() {
    const v = $('calibrationMoment').value;
    state.moment = v === '' ? null : state.moments[Number(v)] || null;
    $('calibrationExcerpt').textContent = state.moment
      ? 'You: ' + (state.moment.user_excerpt || '') + '\nPartner: ' + (state.moment.partner_excerpt || '')
      : 'Select an archived moment if you want to discuss a specific exchange.';
  }
  function questionText() {
    const list = state.doc.mode === 'user' ? userQuestions : systemQuestions;
    const n = Math.min(state.asked, list.length - 1);
    if (!state.moment && state.doc.mode === 'user' && n === 1)
      return "Was there a recent moment when you felt strongly about something? Tell me what happened.";
    if (!state.moment && state.doc.mode === 'system' && n === 0)
      return "How have I been coming across lately? Is there a particular moment you want me to look at?";
    return list[n];
  }
  function renderQuestion() {
    $('calibrationProgress').textContent = 'Main question ' + (state.asked + 1) + ' of up to 5 (aiming for 3)';
    $('calibrationQuestion').textContent = questionText();
    $('calibrationAnswer').value = '';
    $('calibrationFollowup').value = '';
    state.currentId = null; state.followup = false; state.saved = false;
    show('calibrationFollowupBlock', false);
    show('calibrationNext', false);
    $('calibrationSubmit').disabled = false;
    $('calibrationSubmit').textContent = 'Save answer';
    $('calibrationAskFollowup').disabled = false;
    $('calibrationAskFollowup').textContent = 'Ask follow-up';
    $('calibrationNext').textContent = state.asked >= 2 ? 'Another question (optional)' : 'Next question';
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
      action, text, question_id: question_id || '', evidence: selectedEvidence(), modality: 'text'
    });
  }
  async function saveAnswer() {
    const answer = $('calibrationAnswer').value.trim();
    if (!answer) { say('Enter a response, or finish the interview.'); return; }
    if (!state.currentId) {
      const first = await event('main_question', questionText());
      state.currentId = first.questions[first.questions.length - 1].id;
      state.asked = first.main_questions_asked;
    }
    await event('answer', answer, state.currentId);
    state.saved = true;
    $('calibrationSubmit').disabled = true;
    show('calibrationFollowupBlock', true);
    show('calibrationNext', state.asked < 5);
    $('calibrationProgress').textContent = state.asked + ' main questions recorded.';
    say('Saved. An optional follow-up can clarify this answer, or you can continue or finish.');
  }
  async function followup() {
    if (!state.saved || !state.currentId) { say('Save the main answer first.'); return; }
    const text = $('calibrationFollowup').value.trim();
    if (!text) { say('Write a follow-up if you need one.'); return; }
    if (state.followup) { say('One follow-up per main question.'); return; }
    await event('follow_up', text, state.currentId);
    state.followup = true;
    $('calibrationFollowup').placeholder = 'Answer the follow-up here';
    $('calibrationFollowup').value = '';
    $('calibrationAskFollowup').textContent = 'Save follow-up answer';
    say('Follow-up saved. Respond below if you want.');
  }
  async function followupAnswer() {
    const text = $('calibrationFollowup').value.trim();
    if (!text) { say('Enter your answer.'); return; }
    await event('follow_up_answer', text, state.currentId);
    $('calibrationAskFollowup').disabled = true;
    say('Follow-up answer saved.');
  }
  async function finish() {
    if (!state.doc) return;
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
    if (state.doc) await call('/calibration/interviews/' + state.doc.id + '/close', 'POST', {});
    state.doc = null;
    gate.hidden = true;
    show('calibrationSetup', true);
    show('calibrationInterview', false);
    show('calibrationContinuation', false);
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
  });
  $('calibrationDismiss').addEventListener('click', () => { gate.hidden = true; });
  $('calibrationStart').addEventListener('click', wrap(start));
  $('calibrationMoment').addEventListener('change', selectMoment);
  $('calibrationSubmit').addEventListener('click', wrap(saveAnswer));
  $('calibrationAskFollowup').addEventListener('click', wrap(() => state.followup ? followupAnswer() : followup()));
  $('calibrationNext').addEventListener('click', wrap(() => {
    if (!state.saved) { say('Save the answer before moving on.'); return; }
    if (state.asked >= 5) return finish();
    renderQuestion();
  }));
  $('calibrationFinish').addEventListener('click', wrap(finish));
  $('calibrationSaveExtra').addEventListener('click', wrap(saveExtra));
  $('calibrationApplyLesson').addEventListener('click', wrap(approveLesson));
  $('calibrationCloseSession').addEventListener('click', wrap(closeSession));
  $('calibrationDictate').addEventListener('click', dictate);
})();
