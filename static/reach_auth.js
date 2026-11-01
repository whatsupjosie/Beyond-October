/* PubCast Reach shared browser auth adapter.
 * Same-origin requests inherit the current Reach bearer token and authenticated
 * client identity. Cross-origin requests are intentionally untouched.
 */
(function () {
  'use strict';

  const TOKEN_KEY = 'pubcast_token';
  const USER_KEY = 'pubcast_user';
  const CLIENT_KEY = 'pubcast.clientId';
  const nativeFetch = window.fetch.bind(window);

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || '';
  }

  function websocketURL(path) {
    // Browser WebSockets cannot set Authorization headers. Reach login/verify
    // issues a same-origin HttpOnly session cookie for the handshake instead,
    // keeping bearer JWTs out of URLs, browser history, proxy logs and traces.
    const url = new URL(path, location.href);
    if (url.origin !== location.origin) throw new Error('Cross-origin PubCast WebSocket blocked');
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.href;
  }

  function parseStoredUser() {
    try { return JSON.parse(sessionStorage.getItem(USER_KEY) || 'null'); }
    catch (_) { return null; }
  }

  function userName() {
    const user = parseStoredUser();
    if (user && typeof user === 'object') {
      return String(user.username || user.user_id || user.sub || '').trim();
    }
    return '';
  }

  function saveSession(data) {
    if (!data || !data.access_token) return;
    sessionStorage.setItem(TOKEN_KEY, data.access_token);
    const username = String(data.username || data.user_id || '').trim();
    const role = String(data.role || 'guest').trim() || 'guest';
    if (username) {
      sessionStorage.setItem(USER_KEY, JSON.stringify({username, user_id: username, role}));
      localStorage.setItem(CLIENT_KEY, username);
    }
  }

  function clearSession() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  }

  function redirectToLogin(next) {
    const target = next || (location.pathname + location.search + location.hash);
    const url = '/login?next=' + encodeURIComponent(target || '/foresight');
    try {
      if (window.top && window.top !== window) window.top.location.assign(url);
      else window.location.assign(url);
    } catch (_) {
      window.location.assign(url);
    }
  }

  function requestURL(input) {
    try {
      if (typeof input === 'string' || input instanceof URL) return new URL(String(input), location.href);
      if (input && input.url) return new URL(input.url, location.href);
    } catch (_) {}
    return null;
  }

  function authHeaders(baseHeaders) {
    const headers = new Headers(baseHeaders || {});
    const token = getToken();
    if (token) {
      headers.set('Authorization', 'Bearer ' + token);
      const username = userName();
      if (username) headers.set('X-Client-Id', username);
      // Legacy UI role hints must never compete with a verified JWT role.
      headers.delete('X-Dev-Role');
    }
    return headers;
  }

  window.fetch = async function reachAuthenticatedFetch(input, init) {
    const url = requestURL(input);
    const sameOrigin = !!url && url.origin === location.origin;
    if (!sameOrigin) return nativeFetch(input, init);

    let nextInput = input;
    let nextInit = Object.assign({}, init || {});
    if (typeof Request !== 'undefined' && input instanceof Request) {
      const merged = authHeaders((init && init.headers) || input.headers);
      nextInput = new Request(input, Object.assign({}, init || {}, {headers: merged}));
      nextInit = undefined;
    } else {
      nextInit.headers = authHeaders(nextInit.headers);
    }

    const response = await nativeFetch(nextInput, nextInit);
    const authPath = url.pathname.startsWith('/api/' + 'auth/');
    if (response.status === 401 && !authPath) {
      clearSession();
      redirectToLogin(location.pathname + location.search + location.hash);
    }
    return response;
  };

  async function status() {
    const response = await nativeFetch('/api/auth/status', {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error('Auth status HTTP ' + response.status);
    return response.json();
  }

  async function verify() {
    const token = getToken();
    if (!token) return null;
    const response = await nativeFetch('/api/auth/verify', {
      headers: {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
    });
    if (!response.ok) return null;
    const data = await response.json();
    const username = String(data.username || (data.payload && data.payload.sub) || '').trim();
    const role = String(data.role || (data.payload && data.payload.role) || 'guest').trim() || 'guest';
    if (username) {
      sessionStorage.setItem(USER_KEY, JSON.stringify({username, user_id: username, role}));
      localStorage.setItem(CLIENT_KEY, username);
    }
    return data;
  }

  async function requireSession(next) {
    let state;
    try { state = await status(); }
    catch (error) { throw error; }
    if (!state.auth_enforced) return {authenticated: false, status: state};
    if (state.setup_required) {
      redirectToLogin(next || '/foresight');
      return null;
    }
    const verified = await verify();
    if (!verified) {
      clearSession();
      redirectToLogin(next || '/foresight');
      return null;
    }
    return {authenticated: true, status: state, user: verified};
  }

  window.ReachAuth = Object.freeze({
    getToken,
    websocketURL,
    getUser: parseStoredUser,
    saveSession,
    clearSession,
    status,
    verify,
    requireSession,
    redirectToLogin,
    nativeFetch,
  });
})();
