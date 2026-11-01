(() => {
  const $ = (id) => document.getElementById(id);
  const desk = $('desk');
  // Legacy compatibility: pubpartner.lanternDesk.v2.cinematic
  const legacyStoreKey = 'pubpartner.lanternDesk.v5.prelaunchRelationship';
  const storeKey = 'pubpartner.workspace.v1';
  const workspaceSchema = 'pubpartner.workspace.layout.v1';
  const themeKey = 'pubpartner.theme.v1';
  const legacyAuthTokenKey = 'pubpartner.auth.token.v1';
  const legacyAuthUserKey = 'pubpartner.auth.user.v1';
  let telemetryTimer = null;
  let last = null;
  let customizing = false;
  let sessionOpened = false;
  let zTop = 10;
  let lastTelemetry = null;
  let appStarted = false;
  let recentChat = [];
  let recentChatScope = "";
  let turnPending = false;
  let startupPromise = null;
  let localProvider = null;
  let activeTurnController = null;
  let chatEpoch = 0;

  function resetChat() {
    chatEpoch += 1;
    if (activeTurnController) activeTurnController.abort();
    recentChat = []; recentChatScope = ""; last = null;
    if ($('messages')) $('messages').replaceChildren();
  }

  // One-time migration from the pre-Foresight PubPartner token store. Never
  // leave bearer credentials in persistent localStorage after this point.
  if (window.ReachAuth) {
    const legacyToken = localStorage.getItem(legacyAuthTokenKey) || '';
    const legacyUser = localStorage.getItem(legacyAuthUserKey) || '';
    if (legacyToken && !window.ReachAuth.getToken()) {
      window.ReachAuth.saveSession({ access_token: legacyToken, username: legacyUser, role: 'guest' });
    }
    localStorage.removeItem(legacyAuthTokenKey);
    localStorage.removeItem(legacyAuthUserKey);
  }
  const sharedUser = window.ReachAuth ? (window.ReachAuth.getUser() || {}) : {};
  let authState = {
    token: window.ReachAuth ? window.ReachAuth.getToken() : '',
    user: sharedUser.username || sharedUser.user_id || '',
    role: sharedUser.role || '',
    enforced: false
  };

  function toast(text, ms = 2800) {
    const old = document.querySelector('.toast');
    if (old) old.remove();
    const d = document.createElement('div');
    d.className = 'toast';
    d.textContent = text;
    document.body.appendChild(d);
    setTimeout(() => d.remove(), ms);
  }

  async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (!headers.has('content-type') && options.body != null) headers.set('content-type', 'application/json');
    if (authState.token && !headers.has('authorization')) headers.set('authorization', `Bearer ${authState.token}`);
    const res = await fetch(url, { ...options, headers });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
    if (!res.ok) {
      if (res.status === 401 && authState.enforced && !url.startsWith('/api/' + 'auth/')) showAuthGate('login');
      const error = new Error(data.detail || data.provider_result?.error || res.statusText);
      error.status = res.status;
      throw error;
    }
    return data;
  }

  function msg(cls, text) {
    const box = $('messages');
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
  }

  function ids() {
    return {
      user_id: $('userId').value.trim() || 'anon',
      session_id: $('sessionId').value.trim() || 'pubpartner_live',
      friend: $('friendId').value || 'alex',
      provider: $('provider').value || 'ollama',
      model: $('modelName') ? $('modelName').value.trim() : '',
      host: $('providerHost') ? ($('providerHost').value.trim() || 'http://localhost:11434') : 'http://localhost:11434',
      allow_fallback: $('allowFallback') ? $('allowFallback').checked : false,
      knowledge_mode: $('knowledgeMode') ? $('knowledgeMode').value : 'off',
      knowledge_credential: $('knowledgeCredential') ? $('knowledgeCredential').value : '',
      provider_credential: $('providerCredential') ? $('providerCredential').value : '',
    };
  }


  function setAuthToken(result) {
    if (authState.token !== (result.access_token || "")) { resetChat(); sessionOpened = false; }
    authState.token = result.access_token || '';
    authState.user = result.username || '';
    authState.role = result.role || '';
    // An embedded PubPartner portal is the same signed-in Reach account.
    // Never send the old hard-coded display name as a different API actor.
    if (authState.user && $('userId')) {
      $('userId').value = authState.user;
      $('userId').readOnly = !!authState.token;
    }
    if (window.ReachAuth) {
      if (authState.token) window.ReachAuth.saveSession(result);
      else window.ReachAuth.clearSession();
    }
    if ($('accountName')) $('accountName').textContent = authState.user || 'Pub Partner';
    if ($('accountButton')) $('accountButton').textContent = authState.token ? 'Sign out' : 'Sign in';
  }

  function syncSharedIdentity() {
    if (!window.ReachAuth) return;
    const token = window.ReachAuth.getToken() || '';
    if (token !== authState.token) {
      const user = window.ReachAuth.getUser() || {};
      setAuthToken({ access_token: token, username: user.username || user.user_id || '', role: user.role || '' });
      if (!token && authState.enforced) showAuthGate('login');
    }
  }
  window.addEventListener('storage', syncSharedIdentity);

  function showAuthGate(mode) {
    const gate = $('authGate');
    if (!gate) return;
    const setup = mode === 'setup';
    gate.hidden = false;
    document.body.classList.add('auth-locked');
    $('authTitle').textContent = setup ? 'Secure your PubPartner' : 'Welcome back';
    $('authCopy').textContent = setup
      ? 'Create the one-time local owner account that protects relationship data and authority controls.'
      : 'Sign in to unlock your local relationship workspace.';
    $('authSubmit').textContent = setup ? 'Create owner account' : 'Sign in';
    $('authPassword').autocomplete = setup ? 'new-password' : 'current-password';
    $('authConfirmRow').hidden = !setup;
    $('authConfirm').required = setup;
    $('authHint').textContent = setup
      ? 'At least 12 characters and three character types. This password remains in your local database.'
      : 'Use the owner name and password created on this device.';
    $('authForm').dataset.mode = mode;
    $('authError').textContent = '';
    setTimeout(() => $('authUsername').focus(), 50);
  }

  function hideAuthGate() {
    const gate = $('authGate');
    if (gate) gate.hidden = true;
    document.body.classList.remove('auth-locked');
  }

  function startAppOnce() {
    if (appStarted) return Promise.resolve(true);
    if (startupPromise) return startupPromise;
    const token = authState.token;
    startupPromise = (async () => {
      try {
        const local = await api('/api/pubpartner/providers/local-config');
        if (token !== authState.token) return false;
        localProvider = local.enabled ? local.provider : null;
        if (localProvider) {
          $('provider').value = localProvider.provider;
          $('modelName').value = localProvider.model;
          $('providerHost').value = localProvider.base_url;
          if ($('allowFallback')) $('allowFallback').checked = false;
        }
        appStarted = true;
        startLivingTelemetry();
        refreshCartridges();
        refreshZenCredentials(false);
        refreshProviderCredentials(false);
        return true;
      } catch (error) {
        toast('Provider setup failed; sending is paused. Retry Send after checking the server. ' + error.message);
        return false;
      } finally { startupPromise = null; }
    })();
    return startupPromise;
  }

  async function bootstrapAuth() {
    try {
      const status = await api('/api/auth/status');
      authState.enforced = !!status.auth_enforced;
      if (status.setup_required) {
        showAuthGate('setup');
        return;
      }
      if (!authState.enforced) {
        hideAuthGate();
        setAuthToken({ access_token: '', username: 'Local owner', role: 'owner' });
        startAppOnce();
        return;
      }
      if (authState.token) {
        try {
          const verified = await api('/api/auth/verify');
          setAuthToken({ access_token: authState.token, username: verified.username, role: verified.role });
          hideAuthGate();
          startAppOnce();
          return;
        } catch {
          setAuthToken({ access_token: '', username: '', role: '' });
        }
      }
      showAuthGate('login');
    } catch (error) {
      showAuthGate('login');
      $('authError').textContent = `Authentication service unavailable: ${error.message}`;
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    const mode = $('authForm').dataset.mode || 'login';
    const button = $('authSubmit');
    button.disabled = true;
    $('authError').textContent = '';
    const payload = {
      username: $('authUsername').value.trim(),
      password: $('authPassword').value,
    };
    if (mode === 'setup') payload.confirm_password = $('authConfirm').value;
    try {
      const result = await api('/api/' + 'auth/' + mode, { method: 'POST', body: JSON.stringify(payload) });
      setAuthToken(result);
      $('userId').value = result.username || $('userId').value;
      hideAuthGate();
      startAppOnce();
      refreshStatus();
      toast(mode === 'setup' ? 'Owner account created locally.' : 'Signed in.');
      $('authPassword').value = '';
      $('authConfirm').value = '';
    } catch (error) {
      $('authError').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function toggleAccount() {
    if (authState.token) {
      try { await api('/api/auth/logout', { method: 'POST' }); } catch {}
      setAuthToken({ access_token: '', username: '', role: '' });
      if (telemetryTimer) { clearInterval(telemetryTimer); telemetryTimer = null; }
      appStarted = false;
      showAuthGate('login');
      return;
    }
    showAuthGate('login');
  }

  function providerConfig() {
    const x = ids();
    const cfg = { provider: x.provider, model: x.model };
    if (x.provider === 'ollama') {
      cfg.host = x.host;
      cfg.temperature = 0.72;
      cfg.max_tokens = 512;
      cfg.timeout = 60;
    } else if (x.provider === 'openai_compatible') {
      cfg.base_url = x.host;
      cfg.require_api_key = false;
      cfg.temperature = 0.72;
      cfg.timeout = 60;
    } else if (['openai','anthropic','gemini','mistral','groq','opencode_zen'].includes(x.provider)) {
      if (x.provider_credential) cfg.credential_model_id = x.provider_credential;
    }
    return cfg;
  }

  async function refreshProviderCredentials(showToast = false) {
    const x = ids();
    const select = $('providerCredential');
    if (!select) return;
    const cloud = ['openai','anthropic','gemini','mistral','groq','opencode_zen'].includes(x.provider);
    select.disabled = !cloud;
    if (!cloud) {
      select.innerHTML = '<option value="">Not required for this provider</option>';
      return;
    }
    try {
      const result = await api(`/api/pubpartner/providers/credentials?user_id=${encodeURIComponent(x.user_id)}&provider=${encodeURIComponent(x.provider)}`);
      if (ids().provider !== x.provider || ids().user_id !== x.user_id) return;
      const rows = Array.isArray(result.configured) ? result.configured : [];
      const previous = select.value;
      select.innerHTML = '<option value="">Use environment key</option>';
      for (const row of rows) {
        const opt = document.createElement('option');
        opt.value = row.model_id;
        opt.textContent = `${row.display_name || row.provider} · ${row.model_name || 'model'}`;
        select.appendChild(opt);
      }
      if (rows.some(row => row.model_id === previous)) select.value = previous;
      else if (rows.length === 1) select.value = rows[0].model_id;
      if (showToast) toast(rows.length ? `${rows.length} encrypted provider configuration${rows.length === 1 ? '' : 's'} found.` : 'No saved key for this provider.');
    } catch (error) {
      if (showToast) toast('Provider credentials unavailable: ' + error.message);
    }
  }

  async function saveProviderKey() {
    const x = ids();
    const input = $('providerApiKey');
    const key = input ? input.value.trim() : '';
    const allowed = ['openai','anthropic','gemini','mistral','groq','opencode_zen'];
    if (!allowed.includes(x.provider)) return toast('Choose a hosted provider before saving a key.');
    if (!x.model) return toast('Enter the exact provider model ID first.');
    if (!key) return toast('Paste the provider API key first.');
    try {
      const result = await api('/api/pubpartner/providers/credentials', {
        method: 'POST',
        body: JSON.stringify({
          user_id: x.user_id,
          provider: x.provider,
          model: x.model,
          api_key: key,
          display_name: `${x.provider} · ${x.model}`,
          run_fidelity: false,
        }),
      });
      input.value = '';
      await refreshProviderCredentials(false);
      if ($('providerCredential')) $('providerCredential').value = result.credential_model_id || '';
      sessionOpened = false;
      toast('Provider key stored encrypted. No live request was made.');
    } catch (error) {
      toast('Provider key setup failed: ' + error.message);
    }
  }

  function knowledgeConfig() {
    const x = ids();
    return {
      mode: x.knowledge_mode,
      provider: 'opencode_zen',
      model: 'big-pickle',
      credential_model_id: x.knowledge_credential,
      share_current_message: true,
      timeout: 18,
      max_tokens: 700,
      temperature: 0.2,
    };
  }

  async function refreshZenCredentials(showToast = false) {
    const x = ids();
    const select = $('knowledgeCredential');
    if (!select) return;
    try {
      const result = await api(`/api/pubpartner/knowledge/credentials?user_id=${encodeURIComponent(x.user_id)}`);
      if (ids().provider !== x.provider || ids().user_id !== x.user_id) return;
      const rows = Array.isArray(result.configured) ? result.configured : [];
      const previous = select.value;
      select.innerHTML = '';
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = rows.length ? 'Select a Zen key' : 'No Zen key configured';
      select.appendChild(empty);
      for (const row of rows) {
        const opt = document.createElement('option');
        opt.value = row.model_id;
        opt.textContent = `${row.display_name || 'OpenCode Zen'} · ${row.model_name || 'big-pickle'}`;
        select.appendChild(opt);
      }
      if (rows.some(row => row.model_id === previous)) select.value = previous;
      else if (rows.length === 1) select.value = rows[0].model_id;
      if ($('zenStatus')) {
        $('zenStatus').textContent = rows.length
          ? `Big Pickle key ready. Mode: ${ids().knowledge_mode}. Current question only; private Alex memory stays local.`
          : 'Off by default. Add an OpenCode Zen key to enable the reference desk.';
        $('zenStatus').className = `knowledge-note ${rows.length ? 'good' : 'warn'}`;
      }
      if (showToast) toast(rows.length ? 'Zen credential list refreshed.' : 'No Zen key configured yet.');
    } catch (error) {
      if ($('zenStatus')) { $('zenStatus').textContent = `Reference desk unavailable: ${error.message}`; $('zenStatus').className = 'knowledge-note warn'; }
    }
  }

  async function saveZenKey() {
    const input = $('zenApiKey');
    const key = input ? input.value.trim() : '';
    if (!key) return toast('Paste an OpenCode Zen API key first.');
    const x = ids();
    try {
      const result = await api('/api/pubpartner/knowledge/credentials', {
        method: 'POST',
        body: JSON.stringify({ user_id: x.user_id, api_key: key, display_name: 'OpenCode Zen — Big Pickle' }),
      });
      input.value = '';
      await refreshZenCredentials(false);
      if ($('knowledgeCredential')) $('knowledgeCredential').value = result.credential_model_id || '';
      toast('Big Pickle key stored encrypted.');
    } catch (error) {
      toast('Zen key setup failed: ' + error.message);
    }
  }

  async function testZen() {
    const x = ids();
    const message = ($('message') && $('message').value.trim()) || 'What was the capital of Zaire?';
    try {
      const result = await api('/api/pubpartner/knowledge/test', {
        method: 'POST',
        body: JSON.stringify({
          user_id: x.user_id,
          message,
          knowledge: { ...knowledgeConfig(), mode: 'shadow' },
          task: { mode: 'reference_desk_diagnostic' },
        }),
      });
      setDebug(result);
      const kr = result.knowledge_result || {};
      if ($('zenStatus')) {
        $('zenStatus').textContent = kr.ok
          ? `Big Pickle answered in ${kr.latency_ms || 0} ms. Shadow result was not used as Alex.`
          : `Big Pickle test failed: ${kr.error || 'unknown error'}`;
        $('zenStatus').className = `knowledge-note ${kr.ok ? 'good' : 'warn'}`;
      }
      toast(kr.ok ? 'Reference desk responded.' : 'Reference desk unavailable.');
    } catch (error) {
      toast('Reference desk test failed: ' + error.message);
    }
  }

  function setDebug(payload) {
    $('debugBox').textContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
  }


  function providerPayload(p) {
    if (!p) return null;
    if (p.providers && ids().provider !== 'all') return p.providers[ids().provider] || p;
    return p;
  }

  function updateModelDatalist(providerStatus) {
    const list = $('ollamaModels');
    if (!list || !providerStatus) return;
    const root = providerStatus.providers ? providerStatus.providers.ollama : providerStatus;
    const models = root && Array.isArray(root.models) ? root.models : [];
    // If the untouched example model is not installed, select a genuinely
    // available local model rather than make the owner type its name.
    const modelInput = $('modelName');
    if (ids().provider === 'ollama' && modelInput && modelInput.value === 'llama3.1'
        && models.length > 0 && !models.includes('llama3.1')) {
      modelInput.value = models[0];
      toast('Selected installed local model: ' + models[0]);
    }
    list.innerHTML = '';
    for (const model of models.slice(0, 80)) {
      const opt = document.createElement('option');
      opt.value = model;
      list.appendChild(opt);
    }
  }

  function renderRelationship(summary) {
    const counts = (summary && summary.counts) || {};
    const confirmed = Number(counts.confirmed || 0);
    const emerging = Number(counts.provisional || 0);
    if ($('confirmedCount')) $('confirmedCount').textContent = String(confirmed);
    if ($('emergingCount')) $('emergingCount').textContent = String(emerging);
    if ($('reviewCount')) $('reviewCount').textContent = String(emerging);
    const list = $('lessonList');
    if (!list) return;
    const lessons = [...((summary && summary.active) || []), ...((summary && summary.emerging) || [])].slice(0, 12);
    list.innerHTML = '';
    if (!lessons.length) {
      const p = document.createElement('p');
      p.className = 'empty-copy';
      p.textContent = 'No relationship lessons yet. Teach your friend naturally: “I prefer…”, “Never…”, or “When…, please…”.';
      list.appendChild(p);
      return;
    }
    for (const lesson of lessons) {
      const d = document.createElement('div');
      d.className = 'lesson-item';
      d.dataset.lessonId = lesson.lesson_id || '';
      const copy = document.createElement('span');
      copy.className = 'lesson-copy';
      copy.textContent = lesson.text || '(untitled lesson)';
      const meta = document.createElement('small');
      meta.textContent = `${lesson.status || 'provisional'} · ${lesson.kind || 'preference'} · ${Math.round(Number(lesson.confidence || 0) * 100)}%`;
      d.append(copy, meta);
      if (lesson.status === 'provisional' && lesson.lesson_id) {
        const actions = document.createElement('div');
        actions.className = 'lesson-review-actions';
        for (const [status, label] of [['confirmed', 'Keep'], ['rejected', 'Not me']]) {
          const button = document.createElement('button');
          button.type = 'button';
          button.dataset.lessonAction = status;
          button.dataset.lessonId = lesson.lesson_id;
          button.textContent = label;
          actions.appendChild(button);
        }
        d.appendChild(actions);
      } else if (lesson.lesson_id) {
        const reconsider = document.createElement('button');
        reconsider.type = 'button';
        reconsider.className = 'lesson-reconsider';
        reconsider.dataset.lessonAction = 'rejected';
        reconsider.dataset.lessonId = lesson.lesson_id;
        reconsider.textContent = 'Remove';
        reconsider.title = 'Reject this learned lesson without deleting its evidence history';
        d.appendChild(reconsider);
      }
      list.appendChild(d);
    }
  }

  function renderEncounters(payload) {
    const grid = $('encounterGrid');
    if (!grid) return;
    const rows = (payload && payload.encounters) || [];
    const verify = (payload && payload.verify) || {};
    if ($('encounterChain')) {
      $('encounterChain').textContent = verify.ok === false ? 'Chain needs attention' : `${verify.entries || 0} verified`;
      $('encounterChain').className = 'status-pill ' + (verify.ok === false ? 'warn' : 'good');
    }
    grid.innerHTML = '';
    if (!rows.length) {
      const a = document.createElement('article');
      a.className = 'encounter-card empty';
      a.innerHTML = '<strong>Your shared history begins here.</strong><small>Each live turn creates a verifiable encounter record without replacing your exact source text.</small>';
      grid.appendChild(a);
      return;
    }
    for (const row of rows.slice(-8).reverse()) {
      const a = document.createElement('article');
      a.className = 'encounter-card';
      const title = document.createElement('strong');
      title.textContent = row.user_excerpt || 'Encounter';
      const meta = document.createElement('span');
      meta.className = 'enc-meta';
      meta.textContent = `${row.provider || 'provider'} · ${row.model || 'model'}`;
      const receipt = document.createElement('small');
      receipt.textContent = row.receipt_id ? `receipt ${String(row.receipt_id).slice(0, 18)}…` : 'receipt pending';
      a.append(title, meta, receipt);
      grid.appendChild(a);
    }
  }

  async function reviewLesson(lessonId, status) {
    if (!lessonId || !['confirmed', 'rejected'].includes(status)) return;
    const x = ids();
    try {
      const result = await api(`/api/pubpartner/relationship/lessons/${encodeURIComponent(lessonId)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          user_id: x.user_id,
          friend_id: x.friend,
          status,
          confidence: status === 'confirmed' ? 1.0 : 0.0,
          metadata: { reviewed_in: 'pubpartner_ui' },
        }),
      });
      toast(status === 'confirmed' ? 'Lesson kept. Your friend will use it when relevant.' : 'Lesson rejected. It will no longer shape replies.');
      setDebug(result);
      await refreshRelationship(false);
    } catch (e) {
      toast('Relationship review failed: ' + e.message);
    }
  }

  async function refreshRelationship(showDebug = false) {
    const x = ids();
    try {
      const [summary, encounters] = await Promise.all([
        api(`/api/pubpartner/relationship/summary?user_id=${encodeURIComponent(x.user_id)}&friend_id=${encodeURIComponent(x.friend)}&project_id=pubpartner&session_id=${encodeURIComponent(x.session_id)}`),
        api(`/api/pubpartner/relationship/encounters?user_id=${encodeURIComponent(x.user_id)}&friend_id=${encodeURIComponent(x.friend)}&limit=16`),
      ]);
      renderRelationship(summary);
      renderEncounters(encounters);
      if (showDebug) setDebug({ relationship: summary, encounters });
      return { summary, encounters };
    } catch (e) {
      if (showDebug) setDebug('Relationship state unavailable: ' + e.message);
      return null;
    }
  }

  function updateLiving(living, providers) {
    const focused = providerPayload(providers);
    const ollama = providers && providers.providers ? providers.providers.ollama : (ids().provider === 'ollama' ? focused : null);
    const isOllama = ids().provider === 'ollama';
    const ollamaAvailable = !!(ollama && (ollama.alive || ollama.available));
    if ($('llamaStatus')) {
      if (isOllama) {
        const models = ollama && Array.isArray(ollama.models) ? ollama.models : [];
        $('llamaStatus').textContent = ollamaAvailable ? ('live' + (models.length ? ' · ' + models.slice(0,2).join(', ') : '')) : 'not reachable';
      } else {
        $('llamaStatus').textContent = ollamaAvailable ? 'available' : 'optional';
      }
    }
    const counts = (living && living.counts) || {};
    const chain = (living && living.receipt_chain) || {};
    const pulse = chain.ok === false ? 'check' : (counts.turns ? 'breathing · ' + counts.turns + ' turns' : 'idle glow');
    if ($('pulseStatus')) $('pulseStatus').textContent = pulse;
    document.body.dataset.live = isOllama && ollamaAvailable ? 'llama' : (counts.turns ? 'active' : 'idle');
    const meter = document.querySelector('.living-meter');
    if (meter) meter.title = `turns=${counts.turns || 0} receipts=${counts.receipts || 0} sources=${counts.sources || 0}`;
    if ($('telemetryCaption')) $('telemetryCaption').textContent = `${pulse} · sources ${counts.sources || 0} · receipts ${counts.receipts || 0} · lessons ${counts.relationship_lessons || 0}`;
    if ($('previewMode')) $('previewMode').textContent = isOllama && ollamaAvailable ? 'LLAMA' : 'LOCAL';
    if (living && living.relationship) renderRelationship(living.relationship);
    const sourceAudit = (living && living.source_audit) || {};
    const checks = [
      chain.ok !== false,
      sourceAudit.ok !== false,
      !!(living && living.relationship && living.relationship.ok),
      !isOllama || ollamaAvailable,
      !!(living && living.ok),
      !!(living && living.pub_manager && living.pub_manager.ok && Number(living.pub_manager.audit_failures || 0) === 0),
    ];
    const readiness = Math.round((checks.filter(Boolean).length / checks.length) * 100);
    if ($('healthScore')) $('healthScore').textContent = readiness + '%';
    if ($('jeremyLine')) {
      $('jeremyLine').textContent = chain.ok === false
        ? 'Receipt verification needs attention before the next release.'
        : `Continuity is intact: ${counts.turns || 0} turns, ${counts.relationship_lessons || 0} relationship lessons.`;
    }
  }

  function updateOutput(result) {
    if (!result) return;
    $('outputTitle').textContent = 'Live Turn Complete';
    $('outputText').textContent = result.friend_response || 'No friend response returned.';
    const receipt = result.receipt || {};
    $('receiptStatus').textContent = receipt.receipt_chain_hash ? receipt.receipt_chain_hash.slice(0, 16) + '…' : 'no receipt';
    const tc = result.token_comparison || result.token_accounting || {};
    $('tokenStatus').textContent = tc.estimated_prompt_tokens || tc.estimated_tokens || 'recorded';
    $('sourceStatus').textContent = result.source && result.source.id ? result.source.id : '—';
    $('chainStatus').textContent = result.receipt_chain && result.receipt_chain.ok ? 'verified' : 'recorded';
    $('jeremyLine').textContent = '“Turn received, source preserved, receipt written.”';
  }

  async function refreshStatus() {
    try {
      const [status, providers, launch, living, pubManager] = await Promise.all([
        api('/api/pubpartner/status'),
        api(`/api/pubpartner/providers/status?provider=${encodeURIComponent(ids().provider)}&model=${encodeURIComponent(ids().model)}&host=${encodeURIComponent(ids().host)}&base_url=${encodeURIComponent(ids().host)}&credential_model_id=${encodeURIComponent(ids().provider_credential)}&user_id=${encodeURIComponent(ids().user_id)}&require_api_key=${ids().provider === 'openai_compatible' ? 'false' : 'true'}`),
        api('/api/pubpartner/launch-check'),
        api(`/api/pubpartner/living/state?user_id=${encodeURIComponent(ids().user_id)}&session_id=${encodeURIComponent(ids().session_id)}&provider=${encodeURIComponent(ids().provider)}&model=${encodeURIComponent(ids().model)}&host=${encodeURIComponent(ids().host)}`),
        api('/api/pubmanager/health'),
      ]);
      $('agentStatus').textContent = status.ok ? 'Active' : 'Check';
      $('engineStatus').textContent = 'Live loop';
      $('vaultStatus').textContent = 'Verbatim';
      if ($('pubManagerStatus')) {
        const failures = Number(pubManager && pubManager.audit_failures || 0);
        $('pubManagerStatus').textContent = pubManager && pubManager.ok
          ? (failures ? `audit warning · ${failures}` : 'guarding · deterministic')
          : 'unavailable';
      }
      $('providerLabel').textContent = ids().provider + (ids().provider === 'ollama' ? ' · ' + ids().model : '');
      if (living && typeof living === 'object') living.pub_manager = pubManager;
      lastTelemetry = living;
      updateModelDatalist(providers);
      updateLiving(living, providers);
      setDebug({ status, providers, launch, living, pubManager });
    } catch (e) {
      $('agentStatus').textContent = 'Offline';
      $('engineStatus').textContent = 'API missing';
      $('vaultStatus').textContent = 'unknown';
      if ($('llamaStatus')) $('llamaStatus').textContent = 'unknown';
      if ($('pulseStatus')) $('pulseStatus').textContent = 'offline';
      if ($('pubManagerStatus')) $('pubManagerStatus').textContent = 'offline';
      document.body.dataset.live = 'offline';
      setDebug('API not ready: ' + e.message);
    }
  }

  async function ensureSession() {
    if (sessionOpened) return;
    const x = ids();
    const body = {
      user_id: x.user_id,
      session_id: x.session_id,
      friend: x.friend,
      provider: providerConfig(),
      project_id: 'pubpartner',
      room_id: 'phone',
    };
    const s = await api('/api/pubpartner/sessions', { method: 'POST', body: JSON.stringify(body) });
    sessionOpened = true;
    msg('sys', 'Session opened for ' + ((s.friend && s.friend.name) || x.friend));
    setDebug(s);
  }

  async function sendTurn() {
    const text = $('message').value;
    if (!text.trim() || turnPending) return;
    syncSharedIdentity();
    if (authState.enforced && !authState.token) { showAuthGate('login'); return; }
    turnPending = true;
    $('send').disabled = true;
    const epoch = chatEpoch;
    let timeout;
    try {
      if (!(await startAppOnce()) || epoch !== chatEpoch) return;
      await ensureSession();
      if (epoch !== chatEpoch) return;
      const x = ids();
      const scope = JSON.stringify([authState.token, x.session_id, x.friend]);
      if (scope !== recentChatScope) { recentChat = []; recentChatScope = scope; }
      const usingLocal = localProvider && x.provider === localProvider.provider
        && x.model === localProvider.model && x.host.replace(/\/$/, '') === localProvider.base_url;
      activeTurnController = new AbortController();
      timeout = setTimeout(() => activeTurnController?.abort(), 195000);
      msg('user', text);
      $('message').value = '';
      const body = {
        user_id: x.user_id, session_id: x.session_id, message: text, friend: x.friend,
        provider: providerConfig(), knowledge: knowledgeConfig(), project_id: 'pubpartner',
        room_id: 'phone', content_kind: $('kind').value, generate_response: true,
        history: recentChat.slice(), prompt_mode: usingLocal ? 'full' : 'auto',
        allow_fallback: x.allow_fallback,
      };
      const response = await api('/api/pubpartner/turns/live', {
        method: 'POST', body: JSON.stringify(body), signal: activeTurnController.signal
      });
      if (epoch !== chatEpoch || scope !== JSON.stringify([authState.token, ids().session_id, ids().friend])) return;
      if (!response.ok || !response.provider_result?.ok || !response.friend_response) {
        throw new Error('No live reply: ' + (response.provider_result?.error || 'the selected model did not answer. Your message and Alex’s memory remain saved.'));
      }
      last = response;
      if (['mock', 'echo', 'offline'].includes(last.provider_result?.provider)) {
        msg('sys', 'Diagnostic response (not a real AI): ' + last.friend_response);
      } else {
        msg('friend', last.friend_response);
        recentChat.push({role: 'user', content: text}, {role: 'assistant', content: last.friend_response});
        recentChat = recentChat.slice(-4);
      }
      updateOutput(last);
      const learned = (last.relationship && last.relationship.learned_lessons) || [];
      if (learned.length) toast(`Shared understanding updated: ${learned.length} explicit lesson${learned.length === 1 ? '' : 's'}.`);
      await refreshRelationship(false);
      if (epoch === chatEpoch) setDebug({ source: last.source, provider_result: last.provider_result,
        knowledge_result: last.knowledge_result, receipt: last.receipt, token_comparison: last.token_comparison,
        voice: last.voice_restoration, relationship: last.relationship });
    } catch (e) {
      if (epoch === chatEpoch) {
        const error = e.name === 'AbortError' ? 'Request interrupted or timed out. Check receipts before retrying; server work may have finished.' : e.message;
        msg('sys', 'Turn failed: ' + error);
        if (!$('message').value) $('message').value = text;
        setDebug('Turn failed: ' + error);
      }
    } finally {
      clearTimeout(timeout); activeTurnController = null; turnPending = false; $('send').disabled = false;
    }
  }

  async function restoreSource() {
    if (!last || !last.source || !last.source.id) return toast('No source yet.');
    const x = ids();
    try {
      const src = await api(`/api/pubpartner/sources/${encodeURIComponent(last.source.id)}?user_id=${encodeURIComponent(x.user_id)}&session_id=${encodeURIComponent(x.session_id)}`);
      setDebug(src);
      toast('Exact source restored into custody/debug drawer.');
    } catch (e) { toast('Restore failed: ' + e.message); }
  }

  async function showReceipts() {
    const x = ids();
    try { setDebug(await api(`/api/pubpartner/receipts?user_id=${encodeURIComponent(x.user_id)}&session_id=${encodeURIComponent(x.session_id)}`)); }
    catch (e) { toast('Receipt load failed: ' + e.message); }
  }

  async function providerTest() {
    const x = ids();
    try {
      const res = await api('/api/pubpartner/providers/test', { method: 'POST', body: JSON.stringify({ provider: providerConfig(), user_id: x.user_id, session_id: 'ui_provider_test', allow_fallback: x.allow_fallback, message: x.provider === 'ollama' ? 'Llama/Ollama diagnostic: answer in one short sentence as Craig.' : 'Provider diagnostic: answer in one short sentence.' }) });
      setDebug(res);
      toast((res.provider_result && res.provider_result.ok) ? 'Provider diagnostic completed.' : 'Provider diagnostic reported unavailable.');
      await startLivingTelemetry();
    } catch (e) { toast('Provider test failed: ' + e.message); }
  }

  async function scanModels() {
    try {
      const x = ids();
      const res = await api(`/api/pubpartner/providers/status?provider=ollama&model=${encodeURIComponent(x.model)}&host=${encodeURIComponent(x.host)}`);
      updateModelDatalist(res);
      setDebug(res);
      if (res.alive) {
        toast((res.models || []).length ? `Ollama live · ${(res.models || []).length} models found.` : 'Ollama live · no models listed.');
      } else {
        toast('Ollama not reachable: ' + (res.error || res.reason || 'unknown'));
      }
      updateLiving(lastTelemetry || {}, { providers: { ollama: res } });
    } catch (e) { toast('Model scan failed: ' + e.message); }
  }

  async function runPreflight() {
    try {
      const res = await api('/api/pubpartner/preflight');
      setDebug(res);
      toast(res.ok ? 'Preflight OK.' : 'Preflight found issues; see debug drawer.');
    } catch (e) { toast('Preflight failed: ' + e.message); }
  }

  async function saveGuidance() {
    const text = $('guidance').value;
    if (!text.trim()) return toast('Write guidance first.');
    const x = ids();
    try {
      const res = await api('/api/pubpartner/guidance', { method: 'POST', body: JSON.stringify({ user_id: x.user_id, friend_id: x.friend, project_id: 'pubpartner', kind: 'preference', priority: 8, text }) });
      $('guidance').value = '';
      setDebug(res);
      toast('Guidance saved into the friend primer.');
    } catch (e) { toast('Guidance failed: ' + e.message); }
  }

  async function showGuidance() {
    const x = ids();
    try {
      setDebug(await api(`/api/pubpartner/guidance?user_id=${encodeURIComponent(x.user_id)}&friend_id=${encodeURIComponent(x.friend)}&project_id=pubpartner`));
    } catch (e) { toast('Guidance load failed: ' + e.message); }
  }

  async function verifyReceipts() {
    const x = ids();
    try {
      const result = await api(`/api/pubpartner/receipts/verify?user_id=${encodeURIComponent(x.user_id)}&session_id=${encodeURIComponent(x.session_id)}`);
      setDebug(result);
      toast(result.ok ? 'Receipt chain verified.' : 'Receipt chain needs attention.');
    } catch (e) { toast('Receipt verification failed: ' + e.message); }
  }

  function focusPanel(name) {
    const panel = document.querySelector(`.panel[data-panel="${name}"]`);
    if (!panel) return;
    panel.classList.remove('is-collapsed');
    panel.style.zIndex = String(++zTop);
  }

  async function backupFriend() {
    const x = ids();
    try {
      const result = await api('/api/pubpartner/backup', { method: 'POST', body: JSON.stringify({ user_id: x.user_id, friend_id: x.friend }) });
      setDebug(result);
      if (result.download_url) {
        const headers = new Headers();
        if (authState.token) headers.set('authorization', `Bearer ${authState.token}`);
        const response = await fetch(result.download_url, { headers });
        if (!response.ok) throw new Error(`Backup download failed (${response.status})`);
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objectUrl;
        a.download = result.filename || 'PubPartner_Friend_Backup.zip';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      }
      toast(`Verified friend backup created · ${result.file_count || 0} files.`);
    } catch (e) { toast('Backup failed: ' + e.message); }
  }

  const WorkspaceRuntime = {
    history: [],
    defaults: new Map(),
    saveTimer: null,
    panels() { return [...document.querySelectorAll('.panel[data-panel]:not(.static-panel)')]; },
    capture() {
      const d = desk.getBoundingClientRect();
      return {
        schema: workspaceSchema,
        version: 1,
        saved_at: new Date().toISOString(),
        theme: document.documentElement.dataset.theme || 'lantern',
        motion: document.documentElement.dataset.motion || 'full',
        panels: this.panels().map((p) => {
          const r = p.getBoundingClientRect();
          return {
            id: p.dataset.panel,
            x: d.width ? (r.left - d.left) / d.width : 0,
            y: d.height ? (r.top - d.top) / d.height : 0,
            w: d.width ? r.width / d.width : 0.25,
            h: d.height ? r.height / d.height : 0.25,
            collapsed: p.classList.contains('is-collapsed'),
            material: p.dataset.material || 'sapphire',
            docked: p.dataset.docked || '',
            z: Number(p.style.zIndex || 1),
          };
        }),
      };
    },
    validate(value) {
      if (!value || value.schema !== workspaceSchema || !Array.isArray(value.panels)) throw new Error('Unsupported PubPartner layout file.');
      const known = new Set(this.panels().map((p) => p.dataset.panel));
      for (const row of value.panels) {
        if (!row || !known.has(row.id)) continue;
        for (const key of ['x','y','w','h']) if (!Number.isFinite(Number(row[key]))) throw new Error(`Invalid ${key} for tray ${row.id}.`);
      }
      return value;
    },
    apply(value, announce = false) {
      value = this.validate(value);
      const d = desk.getBoundingClientRect();
      for (const row of value.panels) {
        const p = document.querySelector(`.panel[data-panel="${CSS.escape(row.id)}"]`);
        if (!p) continue;
        const width = clamp(Number(row.w) * d.width, 210, Math.max(210, d.width - 12));
        const height = clamp(Number(row.h) * d.height, 120, Math.max(120, d.height - 12));
        p.style.width = `${width}px`; p.style.height = `${height}px`;
        p.style.left = `${clamp(Number(row.x) * d.width, 0, Math.max(0, d.width - width))}px`;
        p.style.top = `${clamp(Number(row.y) * d.height, 0, Math.max(0, d.height - height))}px`;
        p.style.zIndex = String(Number(row.z) || ++zTop);
        p.classList.toggle('is-collapsed', !!row.collapsed);
        if (row.material) p.dataset.material = row.material;
        if (row.docked) p.dataset.docked = row.docked; else delete p.dataset.docked;
      }
      if (value.theme) setTheme(value.theme, false);
      if (value.motion) setMotion(value.motion, false);
      if (announce) toast('Workspace layout restored.');
    },
    snapshot() { this.history.push(this.capture()); if (this.history.length > 30) this.history.shift(); },
    scheduleSave() { clearTimeout(this.saveTimer); this.saveTimer = setTimeout(() => this.save(), 180); },
    save(announce = false) {
      localStorage.setItem(storeKey, JSON.stringify(this.capture()));
      $('saveStatus').textContent = 'Workspace saved locally';
      if (announce) toast('Workspace saved locally.');
    },
    load() {
      try {
        const raw = localStorage.getItem(storeKey);
        if (raw) return this.apply(JSON.parse(raw));
        const legacy = JSON.parse(localStorage.getItem(legacyStoreKey) || '[]');
        if (Array.isArray(legacy) && legacy.length) {
          for (const row of legacy) {
            const p = document.querySelector(`.panel[data-panel="${CSS.escape(row.id === 'wardrobe' ? 'memory' : row.id)}"]`);
            if (!p) continue;
            for (const k of ['left','top','width','height']) if (row[k]) p.style[k] = row[k];
            p.classList.toggle('is-collapsed', !!row.collapsed);
          }
          this.save();
        }
      } catch (error) {
        localStorage.removeItem(storeKey);
        $('saveStatus').textContent = 'Corrupt layout ignored';
        toast('Saved layout was corrupt and has been ignored.');
      }
    },
    reset() {
      this.snapshot(); localStorage.removeItem(storeKey); localStorage.removeItem(legacyStoreKey);
      for (const p of this.panels()) {
        const value = this.defaults.get(p.dataset.panel); if (!value) continue;
        Object.assign(p.style, value.style); p.classList.remove('is-collapsed'); delete p.dataset.docked;
      }
      this.save(); toast('Workspace reset to the packaged layout.');
    },
    undo() { const state = this.history.pop(); if (!state) return toast('No earlier tray movement to restore.'); this.apply(state); this.save(); },
    compact() {
      this.snapshot(); const gap = 16, width = desk.clientWidth, columns = width < 760 ? 1 : width < 1120 ? 2 : 3;
      const colWidth = Math.max(240, (width - gap * (columns + 1)) / columns); const heights = Array(columns).fill(72);
      this.panels().forEach((p, index) => { const col = heights.indexOf(Math.min(...heights)); const h = clamp(p.offsetHeight, 150, 420); p.style.left = `${gap + col * (colWidth + gap)}px`; p.style.top = `${heights[col]}px`; p.style.width = `${colWidth}px`; p.style.height = `${h}px`; p.classList.remove('is-collapsed'); delete p.dataset.docked; heights[col] += h + gap; });
      this.save(); toast('Trays compacted.');
    },
    dock(panel) {
      this.snapshot(); const next = panel.dataset.docked === 'left' ? 'right' : panel.dataset.docked === 'right' ? '' : 'left';
      if (!next) { delete panel.dataset.docked; return this.save(); }
      panel.dataset.docked = next; panel.style.width = `${Math.max(260, desk.clientWidth * 0.32)}px`; panel.style.height = `${Math.max(180, desk.clientHeight - 100)}px`; panel.style.top = '72px'; panel.style.left = next === 'left' ? '12px' : `${desk.clientWidth - panel.offsetWidth - 12}px`; this.save();
    },
    exportLayout() {
      const blob = new Blob([JSON.stringify(this.capture(), null, 2)], { type: 'application/json' }); const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'pubpartner-workspace-v1.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    },
    async importLayout(file) { try { const value = this.validate(JSON.parse(await file.text())); this.snapshot(); this.apply(value); this.save(); toast('Workspace imported.'); } catch (error) { toast(`Layout import failed: ${error.message}`); } },
    initDefaults() { this.panels().forEach((p) => this.defaults.set(p.dataset.panel, { style: { left: p.style.left, top: p.style.top, width: p.style.width, height: p.style.height } })); },
  };

  function saveLayout() { WorkspaceRuntime.scheduleSave(); }
  function loadLayout() { WorkspaceRuntime.load(); }
  function resetLayout() { WorkspaceRuntime.reset(); }
  function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }

  function decorateTrays() {
    const materials = ['sapphire','pearl','emerald','amethyst','obsidian','copper'];
    WorkspaceRuntime.panels().forEach((panel, index) => {
      panel.dataset.material ||= materials[index % materials.length];
      const head = panel.querySelector('.panel-title'); if (!head || head.querySelector('.tray-tools')) return;
      head.tabIndex = 0; head.setAttribute('aria-label', `${head.querySelector('span')?.textContent || 'Tray'} drag handle`);
      const tools = document.createElement('div'); tools.className = 'tray-tools';
      tools.innerHTML = '<button type="button" title="Cycle material" aria-label="Cycle tray material">◈</button><button type="button" title="Dock tray" aria-label="Dock tray">⇥</button><button type="button" title="Bring forward" aria-label="Bring tray forward">↥</button>';
      head.appendChild(tools); const [material, dock, front] = tools.querySelectorAll('button');
      material.addEventListener('click', (e) => { e.stopPropagation(); const i = materials.indexOf(panel.dataset.material); panel.dataset.material = materials[(i + 1) % materials.length]; saveLayout(); });
      dock.addEventListener('click', (e) => { e.stopPropagation(); WorkspaceRuntime.dock(panel); });
      front.addEventListener('click', (e) => { e.stopPropagation(); panel.style.zIndex = String(++zTop); saveLayout(); });
      head.addEventListener('keydown', (e) => { if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) return; e.preventDefault(); WorkspaceRuntime.snapshot(); const step = e.shiftKey ? 24 : 8; let x = parseFloat(panel.style.left) || 0, y = parseFloat(panel.style.top) || 0; if (e.key === 'ArrowLeft') x -= step; if (e.key === 'ArrowRight') x += step; if (e.key === 'ArrowUp') y -= step; if (e.key === 'ArrowDown') y += step; panel.style.left = `${clamp(x,0,desk.clientWidth-panel.offsetWidth)}px`; panel.style.top = `${clamp(y,0,desk.clientHeight-panel.offsetHeight)}px`; saveLayout(); });
    });
  }

  function enablePanelEditing() {
    let active = null;
    desk.addEventListener('pointerdown', (e) => {
      const panel = e.target.closest('.panel[data-panel]:not(.static-panel)'); if (panel) panel.style.zIndex = String(++zTop);
      if (!panel || !customizing || e.target.closest('button,input,select,textarea')) return;
      const resizing = e.target.classList.contains('resize-handle'); if (!resizing && !e.target.closest('.drag-handle')) return;
      const r = panel.getBoundingClientRect(), d = desk.getBoundingClientRect(); WorkspaceRuntime.snapshot();
      active = { panel, resizing, sx:e.clientX, sy:e.clientY, left:r.left-d.left, top:r.top-d.top, w:r.width, h:r.height, d };
      panel.setPointerCapture(e.pointerId); e.preventDefault();
    });
    desk.addEventListener('pointermove', (e) => { if (!active) return; const dx=e.clientX-active.sx, dy=e.clientY-active.sy;
      if (active.resizing) { active.panel.style.width=clamp(active.w+dx,210,active.d.width-active.left-12)+'px'; active.panel.style.height=clamp(active.h+dy,120,active.d.height-active.top-12)+'px'; }
      else { active.panel.style.left=clamp(active.left+dx,0,active.d.width-active.w)+'px'; active.panel.style.top=clamp(active.top+dy,0,active.d.height-active.h)+'px'; }
    });
    desk.addEventListener('pointerup', (e) => { if (!active) return; try { active.panel.releasePointerCapture(e.pointerId); } catch {} active=null; WorkspaceRuntime.save(); });
    document.querySelectorAll('[data-panel-action="collapse"]').forEach((btn) => btn.addEventListener('click', (e) => { const p=e.target.closest('.panel'); WorkspaceRuntime.snapshot(); p.classList.toggle('is-collapsed'); WorkspaceRuntime.save(); }));
  }

  const CommandRegistry = new Map();
  function registerCommand(name, handler) { CommandRegistry.set(name, handler); }

  // ---------- cartridges: new friends made here and kept on the host (modules/pubpartner_cartridges.py)
  let cartridges = [];
  function addFriendOption(c) {
    const sel = $('friendId');
    let opt = [...sel.options].find((o) => o.value === c.id);
    if (!opt) { opt = document.createElement('option'); opt.value = c.id; sel.appendChild(opt); }
    opt.textContent = c.name || c.id; opt.dataset.cartridge = '1';
  }
  async function refreshCartridges() {
    try { const r = await api('/api/pubpartner/cartridges'); cartridges = r.cartridges || []; cartridges.forEach(addFriendOption); }
    catch (error) { toast('Could not load your cartridges: ' + error.message); }
  }
  async function fillAvatarChoices(selected) {
    const sel = $('cartridgeAvatar');
    sel.replaceChildren(new Option('No avatar', ''));
    try {
      const r = await api('/api/avatars/imports');
      for (const a of r.avatars || []) sel.appendChild(new Option(a.name || a.id, a.id));
    } catch (error) { $('cartridgeError').textContent = 'Avatar library unavailable: ' + error.message; }
    sel.value = selected || '';
  }
  async function openCartridgeGate(mode) {
    const gate = $('cartridgeGate'), current = cartridges.find((c) => c.id === $('friendId').value);
    if (mode === 'avatar' && !current) return toast('Pick a cartridge friend first. Built-in friends keep their own look.');
    gate.dataset.mode = mode; $('cartridgeError').textContent = '';
    $('cartridgeTitle').textContent = mode === 'avatar' ? 'Avatar for ' + (current.name || current.id) : 'New cartridge';
    $('cartridgeSubmit').textContent = mode === 'avatar' ? 'Save avatar' : 'Create cartridge';
    $('cartridgeCopy').textContent = mode === 'avatar' ? 'Choose from your avatar library. The Bella Faux Pas Studio uses the same library.'
      : 'A new friend, saved as a portable cartridge. You can talk to them as soon as it is made.';
    if (mode !== 'avatar') ['cartridgeName', 'cartridgeSummary', 'cartridgeCadence', 'cartridgeVocabulary'].forEach((id) => { $(id).value = ''; });
    $('cartridgeName').required = $('cartridgeSummary').required = mode !== 'avatar';
    gate.hidden = false;
    await fillAvatarChoices(mode === 'avatar' ? current.avatar_id : '');
    (mode === 'avatar' ? $('cartridgeAvatar') : $('cartridgeName')).focus();
  }
  async function submitCartridge(event) {
    event.preventDefault();
    const gate = $('cartridgeGate'), button = $('cartridgeSubmit');
    button.disabled = true; $('cartridgeError').textContent = '';
    try {
      let c;
      if (gate.dataset.mode === 'avatar') {
        const id = $('friendId').value;
        c = (await api(`/api/pubpartner/cartridges/${encodeURIComponent(id)}/avatar`, { method: 'PUT', body: JSON.stringify({ avatar_id: $('cartridgeAvatar').value || null }) })).cartridge;
        toast(c.avatar_id ? `Avatar saved for ${c.name}.` : `${c.name} has no avatar now.`);
      } else {
        c = (await api('/api/pubpartner/cartridges', { method: 'POST', body: JSON.stringify({
          name: $('cartridgeName').value, summary: $('cartridgeSummary').value, cadence: $('cartridgeCadence').value,
          vocabulary: $('cartridgeVocabulary').value, avatar_id: $('cartridgeAvatar').value || null }) })).cartridge;
        toast(`${c.name} is saved as a cartridge. Say hello.`);
      }
      cartridges = cartridges.filter((x) => x.id !== c.id).concat([c]);
      addFriendOption(c);
      if ($('friendId').value !== c.id) { $('friendId').value = c.id; $('friendId').dispatchEvent(new Event('change')); }
      gate.hidden = true;
    } catch (error) { $('cartridgeError').textContent = error.message; }
    finally { button.disabled = false; }
  }
  async function runCommand(name) { const handler=CommandRegistry.get(name); if (!handler) return toast(`Command not available: ${name}`); try { await handler(); } catch (error) { toast(`${name} failed: ${error.message}`); } }
  // The top bar's notched shape is a clip-path, which also hides anything that drops out below it, so an open menu
  // is shown outside the bar (fixed, under its button) and put back when it closes. The bar itself is unchanged.
  function floatMenu(root) {
    const pop = root.querySelector('.menu-pop'); if (!pop) return null;
    const r = root.getBoundingClientRect();
    pop.__home = root; document.body.appendChild(pop); pop.classList.add('floating');
    pop.style.top = (r.bottom + 7) + 'px';
    if (pop.classList.contains('menu-pop-right')) { pop.style.left = 'auto'; pop.style.right = Math.max(0, innerWidth - r.right) + 'px'; }
    else pop.style.left = r.left + 'px';
    return pop;
  }
  function closeMenus() {
    document.querySelectorAll('.menu-pop.floating').forEach((pop) => { pop.classList.remove('floating'); pop.style.top = pop.style.left = pop.style.right = ''; pop.__home?.appendChild(pop); });
    document.querySelectorAll('.menu-root.open').forEach((root) => { root.classList.remove('open'); root.querySelector('[data-menu]')?.setAttribute('aria-expanded','false'); });
  }
  function enablePanelFocus() {
    WorkspaceRuntime.panels().forEach((panel) => panel.addEventListener('pointerdown', () => { panel.style.zIndex=String(++zTop); }, {passive:true}));
    document.querySelectorAll('[data-menu]').forEach((btn) => btn.addEventListener('click', (e) => { e.stopPropagation(); const root=btn.closest('.menu-root'), opening=!root.classList.contains('open'); closeMenus(); if (opening) { root.classList.add('open'); btn.setAttribute('aria-expanded','true'); floatMenu(root)?.querySelector('[role="menuitem"]')?.focus(); } }));
    document.querySelectorAll('.menu-pop').forEach((pop) => pop.addEventListener('click',(e)=>e.stopPropagation())); document.addEventListener('click',closeMenus);
    document.querySelectorAll('[data-command]').forEach((btn)=>btn.addEventListener('click',()=>{closeMenus();runCommand(btn.dataset.command);}));
    document.querySelectorAll('[data-theme-value]').forEach((btn)=>btn.addEventListener('click',()=>{closeMenus();setTheme(btn.dataset.themeValue,true);}));
    document.addEventListener('keydown',(e)=>{const tag=e.target?.tagName?.toLowerCase(); if (e.key==='Escape') closeMenus(); if (['input','textarea','select'].includes(tag)) return; if ((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();runCommand('save-workspace');} if ((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();runCommand('undo-layout');} if (e.altKey&&/^[1-9]$/.test(e.key)){const names=['conversation','preview','files','output','status','memory','tools','knowledge','setup'];e.preventDefault();focusPanel(names[Number(e.key)-1]);}});
  }

  function setTheme(value, persist=true) { const allowed=['lantern','glass','emerald','violet']; if (!allowed.includes(value)) return; document.documentElement.dataset.theme=value; if (persist) { localStorage.setItem(themeKey,value); WorkspaceRuntime.scheduleSave(); } }
  function setMotion(value, persist=true) { document.documentElement.dataset.motion=value==='reduced'?'reduced':'full'; if (persist) { localStorage.setItem('pubpartner.motion.v1',document.documentElement.dataset.motion); WorkspaceRuntime.scheduleSave(); } }
  function configureCommands() {
    const focus=(name)=>()=>{focusPanel(name);document.querySelector(`.panel[data-panel="${name}"]`)?.scrollIntoView({behavior:document.documentElement.dataset.motion==='reduced'?'auto':'smooth',block:'center',inline:'center'});};
    registerCommand('new-session',()=>$('newSession').click()); registerCommand('backup-friend',backupFriend); registerCommand('save-workspace',()=>WorkspaceRuntime.save(true)); registerCommand('import-layout',()=>$('layoutImport').click()); registerCommand('export-layout',()=>WorkspaceRuntime.exportLayout()); registerCommand('undo-layout',()=>WorkspaceRuntime.undo()); registerCommand('reset-layout',()=>WorkspaceRuntime.reset()); registerCommand('compact-layout',()=>WorkspaceRuntime.compact()); registerCommand('toggle-motion',()=>{setMotion(document.documentElement.dataset.motion==='reduced'?'full':'reduced');toast(document.documentElement.dataset.motion==='reduced'?'Reduced motion enabled.':'Full motion enabled.');}); registerCommand('toggle-customize',toggleCustomize);
    for (const name of ['conversation','preview','files','output','status','tools','knowledge','setup']) registerCommand(`focus-${name}`,focus(name)); registerCommand('focus-memory',focus('wardrobe'));
    registerCommand('verify-receipts',verifyReceipts); registerCommand('restore-source',restoreSource); registerCommand('provider-test',providerTest); registerCommand('preflight',runPreflight); registerCommand('refresh-relationship',()=>refreshRelationship(true)); registerCommand('show-encounters',()=>refreshRelationship(true)); registerCommand('show-guidance',showGuidance); registerCommand('new-cartridge',()=>openCartridgeGate('new')); registerCommand('cartridge-avatar',()=>openCartridgeGate('avatar'));
  }

  function toggleCustomize() {
    customizing = !customizing;
    desk.classList.toggle('customizing', customizing);
    $('toggleCustomize').textContent = customizing ? 'Lock Layout' : 'Customize Layout';
    toast(customizing ? 'Drag panels by their headers. Resize from the lower-right corners.' : 'Layout locked.');
  }

  function startLivingTelemetry() {
    refreshStatus();
    refreshRelationship(false);
    if (!telemetryTimer) telemetryTimer = setInterval(refreshStatus, 6500);
    setInterval(() => {
      const c = document.querySelector('.preview-art');
      if (c) c.style.setProperty('--breath-seed', String(Date.now() % 1000));
    }, 1800);
  }

  function setupTheme() {
    setTheme(localStorage.getItem(themeKey) || 'lantern', false);
    setMotion(localStorage.getItem('pubpartner.motion.v1') || (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full'), false);
    $('themeToggle').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'glass' ? 'lantern' : 'glass'));
  }

  function tickClock() {
    const start = Date.now();
    setInterval(() => {
      const sec = Math.floor((Date.now() - start) / 1000);
      const h = String(Math.floor(sec / 3600)).padStart(2, '0');
      const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
      const s = String(sec % 60).padStart(2, '0');
      $('clock').textContent = `${h}:${m}:${s}`;
    }, 1000);
  }

  $('send').addEventListener('click', sendTurn);
  $('message').addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') sendTurn(); });
  $('newSession').addEventListener('click', async () => { resetChat(); $('sessionId').value = 'chat-' + (window.crypto?.randomUUID?.() || Date.now().toString(36)); sessionOpened = false; try { await ensureSession(); } catch (e) { toast('Session failed: ' + e.message); } });
  $('restoreSource').addEventListener('click', restoreSource);
  $('showReceipts').addEventListener('click', showReceipts);
  $('showFcp1').addEventListener('click', () => setDebug(last || 'No turn yet.'));
  $('providerTest').addEventListener('click', providerTest);
    ['provider','modelName','providerHost','providerCredential'].forEach(id => { const el = $(id); if (el) el.addEventListener('change', async () => { sessionOpened = false; if (id === 'provider') await refreshProviderCredentials(false); refreshStatus(); }); });
  $('saveGuidance').addEventListener('click', saveGuidance);
  const refreshRelationshipBtn = $('refreshRelationship'); if (refreshRelationshipBtn) refreshRelationshipBtn.addEventListener('click', () => refreshRelationship(true));
  const showEncountersBtn = $('showEncounters'); if (showEncountersBtn) showEncountersBtn.addEventListener('click', () => refreshRelationship(true));
  const lessonList = $('lessonList');
  if (lessonList) lessonList.addEventListener('click', (event) => {
    const button = event.target.closest('[data-lesson-action]');
    if (!button) return;
    reviewLesson(button.dataset.lessonId, button.dataset.lessonAction);
  });
  const toolRelationship = $('toolRelationship'); if (toolRelationship) toolRelationship.addEventListener('click', () => { focusPanel('wardrobe'); refreshRelationship(true); });
  const toolGuidance = $('toolGuidance'); if (toolGuidance) toolGuidance.addEventListener('click', showGuidance);
  const toolReceipts = $('toolReceipts'); if (toolReceipts) toolReceipts.addEventListener('click', verifyReceipts);
  const toolSource = $('toolSource'); if (toolSource) toolSource.addEventListener('click', restoreSource);
  const toolProvider = $('toolProvider'); if (toolProvider) toolProvider.addEventListener('click', providerTest);
  const toolPreflight = $('toolPreflight'); if (toolPreflight) toolPreflight.addEventListener('click', runPreflight);
  const scanBtn = $('scanModels'); if (scanBtn) scanBtn.addEventListener('click', scanModels);
  const saveZenKeyBtn = $('saveZenKey'); if (saveZenKeyBtn) saveZenKeyBtn.addEventListener('click', saveZenKey);
  const testZenBtn = $('testZen'); if (testZenBtn) testZenBtn.addEventListener('click', testZen);
  const knowledgeMode = $('knowledgeMode'); if (knowledgeMode) knowledgeMode.addEventListener('change', () => {
    const note = $('zenStatus');
    if (note) note.textContent = knowledgeMode.value === 'off'
      ? 'Reference desk off. No online knowledge request will be made.'
      : `${knowledgeMode.value === 'shadow' ? 'Shadow' : 'Assisted'} mode: only the sanitized current question is sent.`;
  });
  const preflightBtn = $('runPreflight'); if (preflightBtn) preflightBtn.addEventListener('click', runPreflight);
  $('resetLayout').addEventListener('click', resetLayout);
  $('toggleCustomize').addEventListener('click', toggleCustomize);
  const backupBtn = $('backupFriend'); if (backupBtn) backupBtn.addEventListener('click', backupFriend);
  $('provider').addEventListener('change', () => {
    sessionOpened = false;
    const provider = ids().provider;
    const defaults = {openai:'gpt-4o-mini',anthropic:'claude-haiku-4-5-20251001',ollama:'llama3.1'};
    $('modelName').value = defaults[provider] || '';
    $('modelName').placeholder = 'Exact model ID available to your account';
    $('providerLabel').textContent = provider;
  });
  $('cartridgeForm').addEventListener('submit', submitCartridge);
  $('cartridgeCancel').addEventListener('click', () => { $('cartridgeGate').hidden = true; });
  const authForm = $('authForm'); if (authForm) authForm.addEventListener('submit', submitAuth);
  const accountButton = $('accountButton'); if (accountButton) accountButton.addEventListener('click', toggleAccount);
  $('friendId').addEventListener('change', () => { resetChat(); sessionOpened = false; });
  $('sessionId').addEventListener('change', () => { resetChat(); sessionOpened = false; });

  WorkspaceRuntime.initDefaults();
  decorateTrays();
  configureCommands();
  loadLayout();
  enablePanelEditing();
  enablePanelFocus();
  const layoutImport = $('layoutImport'); if (layoutImport) layoutImport.addEventListener('change', () => { if (layoutImport.files?.[0]) WorkspaceRuntime.importLayout(layoutImport.files[0]); layoutImport.value=''; });
  let resizeTimer; window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer=setTimeout(() => { try { WorkspaceRuntime.apply(WorkspaceRuntime.capture()); } catch {} }, 180); });
  setupTheme();
  tickClock();
  bootstrapAuth();
})();
