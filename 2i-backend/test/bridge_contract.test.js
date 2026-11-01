'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

const routes = new Map();
let axiosGet = async () => { throw new Error('axios.get not configured'); };
let axiosPost = async () => { throw new Error('axios.post not configured'); };

function register(method, routePath, handlers) {
  routes.set(`${method} ${routePath}`, handlers);
}

const app = {
  use() {},
  get(routePath, ...handlers) { register('GET', routePath, handlers); },
  post(routePath, ...handlers) { register('POST', routePath, handlers); },
  delete(routePath, ...handlers) { register('DELETE', routePath, handlers); },
  listen(_port, _host, onReady) {
    const cb = typeof _host === 'function' ? _host : onReady;
    if (typeof cb === 'function') cb();
    return { close(done) { if (done) done(); } };
  },
};

function express() { return app; }
express.json = () => (_req, _res, next) => next();
express.urlencoded = () => (_req, _res, next) => next();

const originalLoad = Module._load;
const originalSetInterval = global.setInterval;
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

Module._load = function(request, parent, isMain) {
  if (request === 'express') return express;
  if (request === 'cors') return () => (_req, _res, next) => next();
  if (request === 'axios') {
    return {
      get: (...args) => axiosGet(...args),
      post: (...args) => axiosPost(...args),
    };
  }
  if (request === 'dotenv') return { config() { return {}; } };
  return originalLoad.call(this, request, parent, isMain);
};

// server.js owns cleanup intervals. Avoid real timers in this isolated route-contract test.
global.setInterval = () => ({ unref() {} });
console.log = () => {};
console.warn = () => {};
console.error = () => {};

process.env.PORT = '8787';
process.env.PUBCAST_URL = process.env.LIVE_REACH_URL || 'http://localhost:8000';
const serverModule = require(path.join(__dirname, '..', 'server.js'));

Module._load = originalLoad;
global.setInterval = originalSetInterval;
console.log = originalConsoleLog;
console.warn = originalConsoleWarn;
console.error = originalConsoleError;

assert.ok(serverModule.app, 'server exports app');
assert.ok(serverModule.Message, 'server exports Message');

async function invoke(method, routePath, { body = {}, query = {}, ip = '127.0.0.1', headers = {} } = {}) {
  const handlers = routes.get(`${method} ${routePath}`);
  assert.ok(handlers, `route registered: ${method} ${routePath}`);

  const req = {
    body,
    query,
    ip,
    path: routePath,
    method,
    get(name) {
      const key = String(name).toLowerCase();
      if (key === 'content-length') return null;
      if (key === 'user-agent') return 'bridge-contract-test';
      return headers[key] || null;
    },
  };

  let statusCode = 200;
  let payload;
  let ended = false;
  const res = {
    status(code) { statusCode = code; return this; },
    json(value) { payload = value; ended = true; return this; },
    send(value) { payload = value; ended = true; return this; },
  };

  let index = 0;
  async function next(err) {
    if (err) throw err;
    if (ended || index >= handlers.length) return;
    const handler = handlers[index++];
    if (handler.length >= 3) {
      let nextCalled = false;
      let childPromise = null;
      await handler(req, res, (nextErr) => {
        nextCalled = true;
        childPromise = next(nextErr);
        return childPromise;
      });
      // Synchronous Express middleware commonly calls next() but does not
      // return/await its promise. The harness must still wait for the child
      // handler to finish before reading the response.
      if (childPromise) await childPromise;
      if (!nextCalled && !ended) return;
    } else {
      await handler(req, res);
      if (!ended) await next();
    }
  }

  await next();
  return { statusCode, payload };
}

test('8787 health identifies the 2i backend', async () => {
  const result = await invoke('GET', '/health');
  assert.equal(result.statusCode, 200);
  assert.equal(result.payload.status, 'healthy');
  assert.equal(result.payload.service, '2i-backend');
});

test('8787 character listing proxies and normalizes PubCast bots', async () => {
  let requestedUrl = null;
  axiosGet = async (url) => {
    requestedUrl = url;
    return {
      data: [
        { bot_id: 'pete', name: 'Pete', provider: 'ollama', model: 'gemma', rooms: ['studio'] },
        { bot_id: 'jeremy', name: 'Jeremy Cricket', provider: 'anthropic', model: 'claude', rooms: [] },
      ],
    };
  };

  const result = await invoke('GET', '/api/chat/characters');
  assert.equal(result.statusCode, 200);
  assert.equal(requestedUrl, `${process.env.PUBCAST_URL}/api/bots`);
  assert.equal(result.payload.ok, true);
  assert.deepEqual(result.payload.characters[0], {
    id: 'pete', name: 'Pete', provider: 'ollama', model: 'gemma', rooms: ['studio'],
  });
});

test('8787 character chat sends the documented PubCast contract and returns reply metadata', async () => {
  let call = null;
  axiosPost = async (url, body, options) => {
    call = { url, body, options };
    return {
      data: {
        reply: 'Hello from Pete.',
        bot_name: 'Pete',
        provider: 'ollama',
        model: 'gemma',
      },
    };
  };

  const result = await invoke('POST', '/api/chat/character', {
    body: { character_id: 'pete', message: '  hello  ', room_id: 'studio', user_id: 'josie' },
    ip: '127.0.0.2',
  });

  assert.equal(result.statusCode, 200);
  assert.equal(call.url, `${process.env.PUBCAST_URL}/api/bots/pete/chat`);
  assert.deepEqual(call.body, { message: 'hello', room_id: 'studio', user_id: 'josie' });
  assert.equal(result.payload.ok, true);
  assert.equal(result.payload.character_id, 'pete');
  assert.equal(result.payload.character_name, 'Pete');
  assert.equal(result.payload.reply, 'Hello from Pete.');
  assert.equal(result.payload.provider, 'ollama');
});

test('8787 forwards the incoming Reach bearer without exposing it in response data', async () => {
  let getOptions = null;
  let postOptions = null;
  axiosGet = async (_url, options) => {
    getOptions = options;
    return { data: [] };
  };
  axiosPost = async (_url, _body, options) => {
    postOptions = options;
    return { data: { reply: 'ok', bot_name: 'Pete', provider: 'local', model: 'test' } };
  };

  const auth = 'Bearer secret-test-token';
  const listing = await invoke('GET', '/api/chat/characters', {headers:{authorization:auth}});
  assert.equal(listing.statusCode, 200);
  assert.equal(getOptions.headers.Authorization, auth);

  const chat = await invoke('POST', '/api/chat/character', {
    headers:{authorization:auth},
    body:{character_id:'pete', message:'hello', room_id:'studio', user_id:'josie'}
  });
  assert.equal(chat.statusCode, 200);
  assert.equal(postOptions.headers.Authorization, auth);
  assert.equal(chat.payload.reply, 'ok');
  assert.equal(JSON.stringify(chat.payload).includes('secret-test-token'), false);
});

test('8787 character chat rejects missing character id before touching PubCast', async () => {
  let touched = false;
  axiosPost = async () => { touched = true; throw new Error('should not be called'); };
  const result = await invoke('POST', '/api/chat/character', {
    body: { message: 'hello' },
    ip: '127.0.0.3',
  });
  assert.equal(result.statusCode, 400);
  assert.equal(touched, false);
  assert.match(result.payload.error, /character_id is required/);
});

test('8787 propagates character-not-found as a clean 404', async () => {
  axiosPost = async () => {
    const err = new Error('not found');
    err.response = { status: 404, data: { detail: "Bot 'missing' not found" } };
    throw err;
  };
  const result = await invoke('POST', '/api/chat/character', {
    body: { character_id: 'missing', message: 'hello' },
    ip: '127.0.0.4',
  });
  assert.equal(result.statusCode, 404);
  assert.match(result.payload.error, /missing/);
});


async function fetchAsAxios(method, url, body, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data;
  const raw = await response.text();
  try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
  if (!response.ok) {
    const err = new Error(`HTTP ${response.status}`);
    err.response = { status: response.status, data };
    throw err;
  }
  return { status: response.status, data };
}

test('live Reach transport: 8787 bridge discovers real bots and preserves real upstream failures', {
  skip: !process.env.LIVE_REACH_URL,
}, async () => {
  axiosGet = (url, options) => fetchAsAxios('GET', url, undefined, options);
  axiosPost = (url, body, options) => fetchAsAxios('POST', url, body, options);
  const liveHeaders = process.env.LIVE_REACH_TOKEN
    ? { authorization: `Bearer ${process.env.LIVE_REACH_TOKEN}` }
    : {};

  const listing = await invoke('GET', '/api/chat/characters', { ip: '127.0.1.1', headers: liveHeaders });
  assert.equal(listing.statusCode, 200);
  assert.equal(listing.payload.ok, true);
  assert.ok(listing.payload.characters.some(c => c.id === 'pete' && c.name === 'Pete'));

  const missing = await invoke('POST', '/api/chat/character', {
    body: { character_id: 'definitely_missing', message: 'hello', user_id: 'bridge-test' },
    ip: '127.0.1.2', headers: liveHeaders,
  });
  assert.equal(missing.statusCode, 404);
  assert.match(missing.payload.error, /definitely_missing/);

  // The fixture Pete has no host API key in this isolated run. That is useful:
  // it proves a real request crossed the 8787 handler into Reach and that the
  // bridge translates Reach's 503 into its documented clean no-key response.
  const pete = await invoke('POST', '/api/chat/character', {
    body: { character_id: 'pete', message: 'bridge transport test', user_id: 'bridge-test' },
    ip: '127.0.1.3', headers: liveHeaders,
  });
  assert.equal(pete.statusCode, 503);
  assert.match(pete.payload.error, /no API key configured/i);
});
