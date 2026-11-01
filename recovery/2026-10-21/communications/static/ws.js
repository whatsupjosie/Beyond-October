/**
 * PubCast AI — ws.js
 * WSHub: thin WebSocket wrapper with auto-reconnect and event dispatch.
 * Exposes window.wsHub for use by ui.js and app.js.
 */
class WSHub {
  constructor(path, { onEvent, onOpen, onClose } = {}) {
    this._path     = path;
    this._onEvent  = onEvent  || (() => {});
    this._onOpen   = onOpen   || (() => {});
    this._onClose  = onClose  || (() => {});
    this._ws       = null;
    this._retries  = 0;
    this._maxRetry = 8;
    this._closed   = false;
    this._connect();
  }

  _connect() {
    if (this._closed) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = window.ReachAuth
      ? window.ReachAuth.websocketURL(this._path)
      : `${proto}://${location.host}${this._path}`;
    this._ws    = new WebSocket(url);

    this._ws.onopen = () => {
      this._retries = 0;
      this._onOpen();
    };

    this._ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        window.dispatchEvent(new CustomEvent("pubcast:server-event", {detail: ev}));
        this._onEvent(ev);
      } catch (_) { /* non-JSON frame — ignore */ }
    };

    this._ws.onclose = () => {
      this._onClose();
      if (!this._closed) this._scheduleReconnect();
    };

    this._ws.onerror = () => {
      this._ws.close();
    };
  }

  _scheduleReconnect() {
    if (this._retries >= this._maxRetry) return;
    const delay = Math.min(500 * 2 ** this._retries, 15000);
    this._retries++;
    setTimeout(() => this._connect(), delay);
  }

  send(obj) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  close() {
    this._closed = true;
    if (this._ws) this._ws.close();
  }
}

window.WSHub = WSHub;
