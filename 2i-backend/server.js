/**
 * 2i BACKEND EXPRESS SERVER
 * Communication hub for entire Bella Faux Pas ecosystem
 * Handles message routing, LLM proxying, manuscript commits
 * 
 * Run: node server.js
 * Port: 8787 (configurable via .env)
 */

const express = require('express');
const cors = require('cors');
const axios = require('axios');
const crypto = require('crypto');
require('dotenv').config();

const app = express();
// Under the unified Foresight host, Python BotManager owns all character
// conversations. Keep standalone Node compatibility without also exposing a
// second active character registry from Reach's optional utility process.
if (process.env.PUBCAST_SIDECAR_ONLY === '1') {
  app.use((req, res, next) => {
    if (req.path === '/api/chat/character' || req.path === '/api/chat/characters') {
      return res.status(404).json({error: 'Characters are served by PubCast Reach'});
    }
    next();
  });
}
const PORT = process.env.PORT || 8787;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || 'claude-opus-4-8';
const PUBCAST_URL = process.env.PUBCAST_URL || 'http://localhost:8000';

// Outbound budget for the PubPartner compatibility call. A hardcoded 30s means
// a hung partner holds a writer's editor for half a minute before the local
// fallback engages; deployments need to tune that. Invalid or non-positive
// values fall back to the previous default rather than disabling the timeout,
// because "no timeout" is never the safe reading of a misconfigured field.
const PUBPARTNER_TIMEOUT_MS = (() => {
  const raw = Number.parseInt(process.env.PUBPARTNER_TIMEOUT_MS, 10);
  return Number.isFinite(raw) && raw > 0 ? raw : 30000;
})();

// ============================================================================
// STRUCTURED LOGGING
// ============================================================================

const LOG_LEVELS = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARN: 'WARN',
  ERROR: 'ERROR',
  CRITICAL: 'CRITICAL'
};

function log(level, component, message, data = null) {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    level,
    component,
    message,
    ...(data && { data })
  };
  
  const prefix = `[${timestamp}] [${level}] [${component}]`;
  
  switch (level) {
    case LOG_LEVELS.CRITICAL:
    case LOG_LEVELS.ERROR:
      console.error(prefix, message, data || '');
      break;
    case LOG_LEVELS.WARN:
      console.warn(prefix, message, data || '');
      break;
    default:
      console.log(prefix, message, data || '');
  }
}

// ============================================================================
// REQUEST VALIDATION UTILITIES
// ============================================================================

function validateRequiredFields(obj, fields) {
  const missing = fields.filter(f => !obj[f]);
  if (missing.length > 0) {
    throw new Error(`Missing required fields: ${missing.join(', ')}`);
  }
}

function validatePayloadSize(payload, maxSize = 10 * 1024 * 1024) {
  const size = JSON.stringify(payload).length;
  if (size > maxSize) {
    throw new Error(`Payload too large: ${(size / 1024 / 1024).toFixed(2)}MB exceeds ${(maxSize / 1024 / 1024).toFixed(2)}MB limit`);
  }
}

// ============================================================================
// RATE LIMITING
// ============================================================================

const rateLimitStore = new Map();
// The window was a hardcoded literal, so neither an operator nor a test could
// change it. A deployment behind a shared NAT may want a wider window; a test
// needs a narrow one to observe expiry without sleeping for a minute.
const RATE_LIMIT_WINDOW = (() => {
  const raw = Number.parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10);
  return Number.isFinite(raw) && raw > 0 ? raw : 60000; // 1 minute
})();
const RATE_LIMITS = {
  'api-claude': { requests: 30, window: RATE_LIMIT_WINDOW },
  'api-thesaurus': { requests: 60, window: RATE_LIMIT_WINDOW },
  'api-manuscript': { requests: 20, window: RATE_LIMIT_WINDOW },
  'default': { requests: 100, window: RATE_LIMIT_WINDOW }
};

function checkRateLimit(key, limit = RATE_LIMITS['default']) {
  const now = Date.now();
  
  if (!rateLimitStore.has(key)) {
    rateLimitStore.set(key, []);
  }
  
  const requests = rateLimitStore.get(key);
  
  // Remove old requests outside window
  while (requests.length > 0 && requests[0] < now - limit.window) {
    requests.shift();
  }
  
  if (requests.length >= limit.requests) {
    return false; // Rate limited
  }
  
  requests.push(now);
  return true; // OK
}

// The bucket map only ever grew: one entry per (ip, route) seen since boot,
// retained forever even after the window emptied. On a long-running host that
// is an unbounded leak driven by client addresses. Sweep expired buckets on a
// timer rather than on the request path, so a burst never pays for the scan.
// The interval is configurable so the sweep is testable in seconds rather than
// being asserted only by argument.
const RATE_LIMIT_SWEEP_INTERVAL = (() => {
  const raw = Number.parseInt(process.env.RATE_LIMIT_SWEEP_MS, 10);
  return Number.isFinite(raw) && raw > 0 ? raw : 5 * 60 * 1000;
})();
const rateLimitSweeper = setInterval(() => {
  const cutoff = Date.now() - RATE_LIMIT_WINDOW;
  for (const [key, requests] of rateLimitStore) {
    while (requests.length > 0 && requests[0] < cutoff) {
      requests.shift();
    }
    if (requests.length === 0) {
      rateLimitStore.delete(key);
    }
  }
}, RATE_LIMIT_SWEEP_INTERVAL);
rateLimitSweeper.unref(); // never hold the process open on this alone

function rateLimitMiddleware(limitKey) {
  return (req, res, next) => {
    const limit = RATE_LIMITS[limitKey] || RATE_LIMITS['default'];

    // Bucket per (ip, route). Keying on the IP alone put every route into one
    // shared window, so the tightest limit on the server became the effective
    // limit for all of them: sixty thesaurus lookups burned a writer's twenty
    // manuscript commits, and the per-route numbers above were decoration.
    if (!checkRateLimit(`${req.ip}|${limitKey}`, limit)) {
      log(LOG_LEVELS.WARN, 'RATE-LIMIT', `Rate limit exceeded for ${limitKey}`, { ip: req.ip });
      return res.status(429).json({
        error: 'Too many requests',
        message: `Rate limit: ${limit.requests} requests per ${limit.window / 1000}s`,
        retry_after: Math.ceil(limit.window / 1000)
      });
    }
    
    next();
  };
}

// ============================================================================
// STARTUP VALIDATION
// ============================================================================

// Only /api/claude needs the Anthropic key. Thesaurus, manuscript, messages,
// and health do not. Killing the process punishes five working endpoints for
// one missing credential, and makes local development impossible without
// paying for a key first. Degrade the one endpoint instead.
const LLM_AVAILABLE = !!ANTHROPIC_API_KEY;

if (!LLM_AVAILABLE) {
  log(LOG_LEVELS.WARN, 'STARTUP', 'ANTHROPIC_API_KEY not set — /api/claude disabled, all other endpoints operational');
  log(LOG_LEVELS.WARN, 'STARTUP', 'Set ANTHROPIC_API_KEY in .env to enable LLM routing');
}

// Middleware - JSON/URL parsing with size limits
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

// CORS - restrictive by default
const ALLOWED_ORIGINS = new Set([
  'http://localhost:3000',
  'http://localhost:8000',
  'http://localhost:8080',
  'http://127.0.0.1:3000',
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8080'
]);
try { ALLOWED_ORIGINS.add(new URL(PUBCAST_URL).origin); } catch (_) {}
for (const origin of String(process.env.CORS_ALLOWED_ORIGINS || '').split(',')) {
  const trimmed = origin.trim();
  if (trimmed) ALLOWED_ORIGINS.add(trimmed);
}

app.use(cors({
  origin: (origin, callback) => {
    // Allow requests with no origin (like mobile apps or curl)
    if (!origin) return callback(null, true);
    
    if (ALLOWED_ORIGINS.has(origin) || process.env.NODE_ENV === 'development') {
      callback(null, true);
    } else {
      log(LOG_LEVELS.WARN, 'CORS', 'Request from disallowed origin', { origin });
      callback(new Error('CORS not allowed'));
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Structured logging middleware
app.use((req, res, next) => {
  // Validate payload size early
  const contentLength = req.get('content-length');
  if (contentLength && parseInt(contentLength) > 10 * 1024 * 1024) {
    log(LOG_LEVELS.WARN, 'HTTP', 'Payload too large', {
      method: req.method,
      path: req.path,
      size: contentLength
    });
    return res.status(413).json({
      error: 'Payload too large',
      message: 'Maximum payload size is 10MB'
    });
  }
  
  log(LOG_LEVELS.DEBUG, 'HTTP', `${req.method} ${req.path}`, {
    ip: req.ip,
    userAgent: req.get('user-agent')?.substring(0, 50)
  });
  
  next();
});

// ============================================================================
// MESSAGE SYSTEM - Core communication protocol
// ============================================================================

/**
 * Message Envelope
 * Every message flowing through 2i carries this structure
 * RIGOROUS VALIDATION - fails fast on invalid input
 */
class Message {
  static VALID_SOURCES = ['user', 'llm-online', 'llm-local', 'system', 'character', 'alex-core', 'error'];
  static VALID_DESTINATIONS = ['tray', 'pubpartner', 'character', 'alex-core', 'system'];
  static VALID_PRIORITIES = ['critical', 'urgent', 'high', 'normal', 'low'];

  constructor(config = {}) {
    // Input validation
    if (!config || typeof config !== 'object') {
      throw new Error('[MESSAGE] Config must be an object');
    }

    // REQUIRED: content
    if (!config.content || typeof config.content !== 'string' || config.content.trim() === '') {
      throw new Error('[MESSAGE] content required (non-empty string)');
    }

    // REQUIRED: source (must be valid enum)
    if (!config.source || typeof config.source !== 'string') {
      throw new Error('[MESSAGE] source required (string)');
    }
    if (!Message.VALID_SOURCES.includes(config.source)) {
      throw new Error(`[MESSAGE] source must be one of: ${Message.VALID_SOURCES.join(', ')}`);
    }

    // OPTIONAL: destination (validate if provided)
    if (config.destination && !Message.VALID_DESTINATIONS.includes(config.destination)) {
      throw new Error(`[MESSAGE] destination must be one of: ${Message.VALID_DESTINATIONS.join(', ')}`);
    }

    // OPTIONAL: priority (validate if provided)
    if (config.priority && !Message.VALID_PRIORITIES.includes(config.priority)) {
      throw new Error(`[MESSAGE] priority must be one of: ${Message.VALID_PRIORITIES.join(', ')}`);
    }

    // OPTIONAL: context and metadata (must be objects if provided)
    if (config.context && typeof config.context !== 'object') {
      throw new Error('[MESSAGE] context must be an object');
    }
    if (config.metadata && typeof config.metadata !== 'object') {
      throw new Error('[MESSAGE] metadata must be an object');
    }

    // Assign fields after all validation passes
    this.id = config.id || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    this.timestamp = config.timestamp || new Date().toISOString();
    this.source = config.source;
    this.destination = config.destination || 'tray';
    this.priority = config.priority || 'normal';
    this.content = config.content.trim();
    this.context = config.context || {};
    this.metadata = config.metadata || {};
    this.response_required = config.response_required !== false;
  }

  isValid() {
    return !!(this.content && this.source && this.timestamp);
  }

  toJSON() {
    return {
      id: this.id,
      timestamp: this.timestamp,
      source: this.source,
      destination: this.destination,
      priority: this.priority,
      content: this.content,
      context: this.context,
      metadata: this.metadata,
      response_required: this.response_required
    };
  }
}

// Message history (in-memory for now, could persist to DB)
const messageHistory = [];
const MAX_HISTORY = 1000;

function addToHistory(message) {
  messageHistory.push(message);
  if (messageHistory.length > MAX_HISTORY) {
    messageHistory.shift();
  }
}

// ============================================================================
// ROUTE: Health Check
// ============================================================================

app.get('/health', (req, res) => {
  try {
    const health = {
      status: 'healthy',
      service: '2i-backend',
      timestamp: new Date().toISOString(),
      uptime: Math.floor(process.uptime()),
      environment: {
        node_version: process.version,
        anthropic_api: !!ANTHROPIC_API_KEY ? '✓ configured' : '✗ missing',
        anthropic_model: ANTHROPIC_MODEL,
        memory_usage: {
          rss: `${Math.round(process.memoryUsage().rss / 1024 / 1024)}MB`,
          heap_used: `${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)}MB`,
          heap_total: `${Math.round(process.memoryUsage().heapTotal / 1024 / 1024)}MB`
        }
      },
      services: {
        message_history: messageHistory.length,
        rate_limit_entries: rateLimitStore.size
      }
    };
    
    log(LOG_LEVELS.DEBUG, 'HEALTH', 'Health check', health);
    res.json(health);
  } catch (error) {
    log(LOG_LEVELS.ERROR, 'HEALTH', 'Health check failed', { error: error.message });
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});

// ============================================================================
// ROUTE: LLM Proxy (Online - Anthropic)
// ============================================================================

/**
 * POST /api/claude
 * Proxy to Anthropic API
 * Frontend sends request, backend handles key (never exposed to browser)
 */
app.post('/api/claude', rateLimitMiddleware('api-claude'), async (req, res) => {
  let messageEnvelope = null;
  let startTime = Date.now();
  
  try {
    // Service availability check — clear, actionable, not a crash
    if (!LLM_AVAILABLE) {
      log(LOG_LEVELS.WARN, 'CLAUDE', 'LLM request rejected — no API key configured', { ip: req.ip });
      return res.status(503).json({
        error: 'LLM unavailable',
        message: 'ANTHROPIC_API_KEY is not configured on the server. Other endpoints remain available.',
        timestamp: new Date().toISOString()
      });
    }

    // Validate payload size early
    validatePayloadSize(req.body);

    const { prompt, messages, max_tokens = 1000, temperature = 0.7, system = null } = req.body;

    // Validate input
    if (!prompt && !messages) {
      log(LOG_LEVELS.WARN, 'CLAUDE', 'Missing prompt and messages', { ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'Must provide either prompt or messages array'
      });
    }

    // Validate max_tokens
    if (max_tokens < 1 || max_tokens > 4096) {
      log(LOG_LEVELS.WARN, 'CLAUDE', 'Invalid max_tokens', { max_tokens, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'max_tokens must be between 1 and 4096'
      });
    }

    // Validate temperature
    if (temperature < 0 || temperature > 1) {
      log(LOG_LEVELS.WARN, 'CLAUDE', 'Invalid temperature', { temperature, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'temperature must be between 0 and 1'
      });
    }

    // Build message array for Anthropic
    const anthropicMessages = messages || [{ role: 'user', content: prompt }];

    // Create 2i message record
    try {
      messageEnvelope = new Message({
        source: 'user',
        destination: 'tray',
        content: prompt || (messages && messages[messages.length - 1]?.content),
        context: req.body.context || {},
        metadata: { 
          type: 'llm-request',
          model: ANTHROPIC_MODEL,
          max_tokens,
          temperature,
          ip: req.ip
        }
      });
      addToHistory(messageEnvelope);
    } catch (msgError) {
      log(LOG_LEVELS.ERROR, 'CLAUDE', 'Failed to create message envelope', { error: msgError.message });
      return res.status(400).json({
        error: 'Invalid message format',
        message: msgError.message
      });
    }

    log(LOG_LEVELS.DEBUG, 'CLAUDE', 'Forwarding to Anthropic API', {
      message_id: messageEnvelope.id,
      tokens: max_tokens,
      temp: temperature
    });

    // Call Anthropic API (with timeout)
    const anthropicResponse = await axios.post('https://api.anthropic.com/v1/messages', {
      model: ANTHROPIC_MODEL,
      max_tokens: max_tokens,
      temperature: temperature,
      system: system || 'You are a helpful assistant.',
      messages: anthropicMessages
    }, {
      headers: {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json'
      },
      timeout: 30000 // 30 second timeout
    });

    // Extract response - validate structure
    if (!anthropicResponse.data || !Array.isArray(anthropicResponse.data.content) || anthropicResponse.data.content.length === 0) {
      log(LOG_LEVELS.ERROR, 'CLAUDE', 'Invalid response structure from Anthropic', {
        message_id: messageEnvelope?.id,
        response_data: JSON.stringify(anthropicResponse.data).substring(0, 200)
      });
      return res.status(502).json({
        error: 'Invalid API response',
        message: 'Anthropic API returned malformed response',
        message_id: messageEnvelope?.id
      });
    }

    const firstContent = anthropicResponse.data.content[0];
    if (!firstContent || firstContent.type !== 'text' || typeof firstContent.text !== 'string') {
      log(LOG_LEVELS.ERROR, 'CLAUDE', 'Content not text type', {
        message_id: messageEnvelope?.id,
        content_type: firstContent?.type
      });
      return res.status(502).json({
        error: 'Invalid content type',
        message: 'Expected text content from API',
        message_id: messageEnvelope?.id
      });
    }

    const llmResponse = firstContent.text;

    // Create response message
    const responseEnvelope = new Message({
      source: 'llm-online',
      destination: 'tray',
      content: llmResponse,
      context: messageEnvelope.context,
      metadata: {
        type: 'llm-response',
        model: ANTHROPIC_MODEL,
        usage: anthropicResponse.data.usage,
        parent_message_id: messageEnvelope.id,
        processing_time_ms: Date.now() - startTime
      }
    });
    addToHistory(responseEnvelope);

    log(LOG_LEVELS.INFO, 'CLAUDE', 'Response generated successfully', {
      message_id: responseEnvelope.id,
      processing_ms: Date.now() - startTime,
      usage: anthropicResponse.data.usage
    });

    res.json({
      message_id: responseEnvelope.id,
      response: llmResponse,
      model: ANTHROPIC_MODEL,
      usage: anthropicResponse.data.usage,
      timestamp: responseEnvelope.timestamp,
      processing_time_ms: Date.now() - startTime
    });

  } catch (error) {
    const processingTime = Date.now() - startTime;
    
    if (error.response?.status === 401) {
      log(LOG_LEVELS.CRITICAL, 'CLAUDE', 'Anthropic API authentication failed', {
        message_id: messageEnvelope?.id,
        processing_ms: processingTime
      });
      return res.status(500).json({
        error: 'API authentication failed',
        message: 'Anthropic API key invalid or expired'
      });
    }

    if (error.response?.status === 429) {
      log(LOG_LEVELS.WARN, 'CLAUDE', 'Anthropic API rate limited', {
        message_id: messageEnvelope?.id,
        processing_ms: processingTime
      });
      return res.status(429).json({
        error: 'Rate limited',
        message: 'Anthropic API rate limit exceeded, try again later'
      });
    }

    if (error.code === 'ECONNABORTED') {
      log(LOG_LEVELS.ERROR, 'CLAUDE', 'Anthropic API timeout', {
        message_id: messageEnvelope?.id,
        processing_ms: processingTime
      });
      return res.status(504).json({
        error: 'Gateway timeout',
        message: 'Anthropic API did not respond in time'
      });
    }

    log(LOG_LEVELS.ERROR, 'CLAUDE', 'Anthropic API error', {
      message_id: messageEnvelope?.id,
      processing_ms: processingTime,
      status: error.response?.status,
      error: error.response?.data?.error?.message || error.message
    });

    res.status(error.response?.status || 500).json({
      error: 'LLM request failed',
      message: error.response?.data?.error?.message || error.message,
      message_id: messageEnvelope?.id
    });
  }
});

// ============================================================================
// ROUTE: Thesaurus (Datamuse API)
// ============================================================================

/**
 * GET /api/thesaurus
 * Word suggestions via Datamuse API
 * Modes: synonyms, rhymes, related
 */
app.get('/api/thesaurus', rateLimitMiddleware('api-thesaurus'), async (req, res) => {
  let messageEnvelope = null;
  let startTime = Date.now();
  
  try {
    const { word, mode = 'synonyms' } = req.query;

    // Validate input
    if (!word || typeof word !== 'string' || word.trim() === '') {
      log(LOG_LEVELS.WARN, 'THESAURUS', 'Missing or invalid word parameter', { ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'word parameter required (non-empty string)'
      });
    }

    const cleanWord = word.trim().toLowerCase();

    // Validate mode
    const modeMap = {
      synonyms: 'ml',      // means-like
      rhymes: 'rel_rhy',   // relates-rhyme
      related: 'rel_jja'   // related-adjective-variant
    };

    if (!modeMap[mode]) {
      log(LOG_LEVELS.WARN, 'THESAURUS', 'Invalid mode', { mode, word: cleanWord, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: `mode must be one of: ${Object.keys(modeMap).join(', ')}`
      });
    }

    const dataMuseMode = modeMap[mode];

    // Create message record
    try {
      messageEnvelope = new Message({
        source: 'system',
        destination: 'tray',
        content: `Thesaurus lookup: ${cleanWord} (${mode})`,
        metadata: { 
          type: 'thesaurus-request',
          mode,
          word: cleanWord,
          ip: req.ip
        }
      });
      addToHistory(messageEnvelope);
    } catch (msgError) {
      log(LOG_LEVELS.ERROR, 'THESAURUS', 'Failed to create message envelope', { error: msgError.message });
      return res.status(400).json({
        error: 'Invalid message format',
        message: msgError.message
      });
    }

    log(LOG_LEVELS.DEBUG, 'THESAURUS', 'Querying Datamuse', {
      message_id: messageEnvelope.id,
      word: cleanWord,
      mode
    });

    // Call Datamuse (with timeout)
    const response = await axios.get('https://api.datamuse.com/words', {
      params: {
        [dataMuseMode]: cleanWord,
        max: 10
      },
      timeout: 10000 // 10 second timeout
    });

    const words = response.data.map(item => item.word);

    // Create response message
    const responseEnvelope = new Message({
      source: 'system',
      destination: 'tray',
      content: `Found ${words.length} ${mode} for "${cleanWord}"`,
      metadata: {
        type: 'thesaurus-response',
        mode,
        word: cleanWord,
        results: words,
        parent_message_id: messageEnvelope.id,
        processing_time_ms: Date.now() - startTime
      }
    });
    addToHistory(responseEnvelope);

    log(LOG_LEVELS.INFO, 'THESAURUS', 'Lookup successful', {
      message_id: responseEnvelope.id,
      word: cleanWord,
      mode,
      count: words.length,
      processing_ms: Date.now() - startTime
    });

    res.json({
      word: cleanWord,
      mode,
      results: words,
      count: words.length,
      timestamp: responseEnvelope.timestamp,
      processing_time_ms: Date.now() - startTime
    });

  } catch (error) {
    const processingTime = Date.now() - startTime;
    
    if (error.code === 'ECONNABORTED') {
      log(LOG_LEVELS.ERROR, 'THESAURUS', 'Datamuse API timeout', {
        message_id: messageEnvelope?.id,
        processing_ms: processingTime
      });
      return res.status(504).json({
        error: 'Gateway timeout',
        message: 'Datamuse API did not respond in time'
      });
    }

    log(LOG_LEVELS.ERROR, 'THESAURUS', 'Thesaurus lookup failed', {
      message_id: messageEnvelope?.id,
      processing_ms: processingTime,
      error: error.message
    });

    res.status(error.response?.status || 500).json({
      error: 'Thesaurus lookup failed',
      message: error.message,
      message_id: messageEnvelope?.id
    });
  }
});

// ============================================================================
// ROUTE: Manuscript Commit (2i → PubPartner)
// ============================================================================

/**
 * POST /api/manuscript/commit
 * Writer submits chapter/manuscript changes
 * Payload goes to PubPartner for indexing/storage
 * 
 * Awaiting PubPartner endpoint configuration in .env:
 * PUBPARTNER_URL=http://localhost:9999
 * PUBPARTNER_API_KEY=<key>
 */
app.post('/api/manuscript/commit', rateLimitMiddleware('api-manuscript'), async (req, res) => {
  let commitMessage = null;
  let startTime = Date.now();
  
  try {
    // Validate payload size
    validatePayloadSize(req.body);

    const {
      project_id,
      chapter_id,
      content,
      character_names = [],
      plot_elements = [],
      style_notes = [],
      user_id = 'josie',
      base_version = null
    } = req.body;

    // Rigorous validation
    try {
      validateRequiredFields(req.body, ['project_id', 'chapter_id', 'content']);
    } catch (e) {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'Missing required fields', { ip: req.ip, error: e.message });
      return res.status(400).json({
        error: 'Invalid request',
        message: e.message
      });
    }

    // Validate project_id format
    if (typeof project_id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(project_id)) {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'Invalid project_id format', { project_id, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'project_id must contain only alphanumeric, underscore, and hyphen characters'
      });
    }

    // Validate chapter_id format
    if (typeof chapter_id !== 'string' || chapter_id.trim() === '') {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'Invalid chapter_id', { chapter_id, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'chapter_id must be a non-empty string'
      });
    }

    // Validate content
    if (typeof content !== 'string' || content.trim() === '') {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'Invalid content', { ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'content must be a non-empty string'
      });
    }

    // Validate optional arrays
    if (!Array.isArray(character_names)) {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'character_names not array', { ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'character_names must be an array'
      });
    }

    if (!Array.isArray(plot_elements)) {
      log(LOG_LEVELS.WARN, 'MANUSCRIPT', 'plot_elements not array', { ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'plot_elements must be an array'
      });
    }

    // Create commit message
    try {
      commitMessage = new Message({
        source: 'user',
        destination: 'pubpartner',
        content: `Manuscript commit: ${project_id}/${chapter_id}`,
        context: {
          project_id,
          chapter_id,
          user_id
        },
        metadata: {
          type: 'manuscript-commit',
          content_length: content.length,
          characters: character_names,
          plot_elements: plot_elements,
          style_notes: style_notes,
          ip: req.ip
        },
        priority: 'high',
        response_required: true
      });
      addToHistory(commitMessage);
    } catch (msgError) {
      log(LOG_LEVELS.ERROR, 'MANUSCRIPT', 'Failed to create message', { error: msgError.message });
      return res.status(400).json({
        error: 'Invalid message format',
        message: msgError.message
      });
    }

    log(LOG_LEVELS.DEBUG, 'MANUSCRIPT', 'Manuscript commit received', {
      message_id: commitMessage.id,
      project_id,
      chapter_id,
      content_bytes: content.length,
      characters: character_names.length,
      plots: plot_elements.length
    });

    // Route to PubPartner when PUBPARTNER_URL is configured; otherwise retain the commit in the local queue
    const PUBPARTNER_URL = process.env.PUBPARTNER_URL;
    let pubpartnerAttemptFailed = false;
    if (PUBPARTNER_URL) {
      try {
        log(LOG_LEVELS.DEBUG, 'MANUSCRIPT', 'Routing to PubPartner', {
          message_id: commitMessage.id,
          url: PUBPARTNER_URL
        });

        const pubpartnerResponse = await axios.post(`${PUBPARTNER_URL}/api/manuscript/commit`, {
          message_id: commitMessage.id,
          project_id,
          chapter_id,
          content,
          character_names,
          plot_elements,
          style_notes,
          user_id,
          // Forwarded verbatim. This is the manuscript version the editor last
          // saw; PubPartner uses it to tell a deliberate revert apart from a
          // stale copy of a field a peer has since changed. 2i does not hold
          // manuscript authority and must not invent or cache this value — an
          // editor that omits it gets the older, unprotected behaviour.
          ...(base_version && typeof base_version === 'object' && !Array.isArray(base_version)
            ? { base_version }
            : {}),
          timestamp: commitMessage.timestamp
        }, {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${process.env.PUBPARTNER_API_KEY || 'not-configured'}`
          },
          timeout: PUBPARTNER_TIMEOUT_MS
        });

        // A 200 is not the contract. The contract is a 200 carrying a string
        // manuscript_id. Without this check a partner that answers
        // {"status":"committed"} — or an HTML error page from a proxy that
        // axios could not parse — produced a response with manuscript_id
        // undefined, which JSON.stringify silently drops. The writer then saw
        // a commit that looked identical to a real one and had no
        // pubpartner_status to contradict it. Treat a broken contract as a
        // routing failure and fall through to the local queue.
        const routedId = pubpartnerResponse?.data?.manuscript_id;
        if (typeof routedId !== 'string' || routedId.trim() === '') {
          throw new Error(
            `PubPartner returned ${pubpartnerResponse.status} without a usable manuscript_id`
          );
        }

        log(LOG_LEVELS.INFO, 'MANUSCRIPT', 'Successfully routed to PubPartner', {
          message_id: commitMessage.id,
          pubpartner_id: routedId
        });

        return res.json({
          status: 'committed',
          message_id: commitMessage.id,
          manuscript_id: routedId,
          project_id,
          chapter_id,
          timestamp: commitMessage.timestamp,
          processing_time_ms: Date.now() - startTime
        });

      } catch (pubpartnerError) {
        log(LOG_LEVELS.ERROR, 'MANUSCRIPT', 'PubPartner routing failed', {
          message_id: commitMessage.id,
          error: pubpartnerError.message,
          processing_ms: Date.now() - startTime
        });

        // Continue with local acknowledgment even if PubPartner fails
        // (can retry later). Record that an attempt was made and failed —
        // this fallback block is otherwise indistinguishable from "never
        // configured", which previously made the response falsely claim
        // pubpartner_status: 'routed' on a connection that had just thrown.
        pubpartnerAttemptFailed = true;
      }
    }

    // Local acknowledgment (when PubPartner not configured or failed)
    log(LOG_LEVELS.INFO, 'MANUSCRIPT', 'Commit acknowledged locally', {
      message_id: commitMessage.id,
      project_id,
      chapter_id,
      content_bytes: content.length,
      processing_ms: Date.now() - startTime,
      pubpartner_configured: !!PUBPARTNER_URL,
      pubpartner_attempt_failed: pubpartnerAttemptFailed
    });

    res.json({
      status: 'committed',
      message_id: commitMessage.id,
      project_id,
      chapter_id,
      timestamp: commitMessage.timestamp,
      processing_time_ms: Date.now() - startTime,
      // This block is only ever reached when PubPartner did NOT succeed
      // (the success path above returns early with manuscript_id instead).
      // 'routed' must never appear here — it would claim success on a
      // request that either was never attempted or just threw.
      pubpartner_status: pubpartnerAttemptFailed
        ? 'queued-locally-pubpartner-unreachable'
        : 'queued-locally'
    });

  } catch (error) {
    const processingTime = Date.now() - startTime;
    
    log(LOG_LEVELS.ERROR, 'MANUSCRIPT', 'Manuscript commit failed', {
      message_id: commitMessage?.id,
      processing_ms: processingTime,
      error: error.message
    });

    res.status(500).json({
      error: 'Commit failed',
      message: error.message,
      message_id: commitMessage?.id
    });
  }
});


// ============================================================================
// ROUTE: Character Chat (Talk to Pete, Sir Purfluous, RePete, etc. via PubCast)
// ============================================================================

/**
 * POST /api/chat/character
 * Send a message to a named PubCast character and get their reply.
 * Routes through PubCast's bot endpoint — full character voice, system prompt,
 * Jeremy Cricket memory enrichment, provider routing all handled PubCast-side.
 *
 * Body: {
 *   character_id: "pete" | "sir_purfluous" | "repeat" | ...
 *   message:      string
 *   room_id:      string  (default: "studio")
 *   user_id:      string  (default: "user")
 * }
 *
 * Environment: PUBCAST_URL=http://localhost:8000 (required)
 */
app.post('/api/chat/character', rateLimitMiddleware('api-claude'), async (req, res) => {
  const startTime = Date.now();
  const { character_id, message, room_id = 'studio', user_id = 'user' } = req.body || {};

  // Validate
  if (!character_id || typeof character_id !== 'string') {
    return res.status(400).json({ error: 'character_id is required', valid_characters: ['pete', 'sir_purfluous', 'repeat', 'jeremy'] });
  }
  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required' });
  }

  log(LOG_LEVELS.INFO, 'CHARACTER_CHAT', `Message to ${character_id}`, {
    character_id, room_id, user_id,
    message_preview: message.substring(0, 80),
    ip: req.ip
  });

  try {
    const pubcastResponse = await axios.post(
      `${PUBCAST_URL}/api/bots/${character_id}/chat`,
      { message: message.trim(), room_id, user_id },
      {
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
          ...(req.get('authorization') ? { Authorization: req.get('authorization') } : {})
        }
      }
    );

    const data = pubcastResponse.data;
    const latency = Date.now() - startTime;

    // Log to message history so 2i's full audit trail includes this exchange
    try {
      const outMsg = new Message({
        source: 'user',
        destination: 'character',
        content: message.trim(),
        priority: 'normal',
        metadata: { character_id, room_id, user_id, type: 'character_chat' }
      });
      messageHistory.push(outMsg);

      const replyMsg = new Message({
        source: 'character',
        destination: 'tray',
        content: data.reply,
        priority: 'normal',
        metadata: {
          character_id,
          character_name: data.bot_name,
          provider: data.provider,
          model: data.model,
          room_id,
          type: 'character_reply',
          latency_ms: latency
        }
      });
      messageHistory.push(replyMsg);

      // Trim history if needed
      if (messageHistory.length > MAX_HISTORY) {
        messageHistory.splice(0, messageHistory.length - MAX_HISTORY);
      }
    } catch (histErr) {
      log(LOG_LEVELS.WARN, 'CHARACTER_CHAT', 'Failed to log to message history', { error: histErr.message });
    }

    log(LOG_LEVELS.INFO, 'CHARACTER_CHAT', `Reply from ${data.bot_name}`, {
      character_id,
      provider: data.provider,
      latency_ms: latency,
      reply_preview: data.reply?.substring(0, 80)
    });

    return res.json({
      ok: true,
      character_id,
      character_name: data.bot_name,
      provider: data.provider,
      model: data.model,
      room_id,
      message,
      reply: data.reply,
      latency_ms: latency
    });

  } catch (err) {
    const latency = Date.now() - startTime;
    const status = err.response?.status || 503;
    const detail = err.response?.data?.detail || err.message;

    log(LOG_LEVELS.ERROR, 'CHARACTER_CHAT', `Failed: ${character_id}`, {
      status, detail, latency_ms: latency, ip: req.ip
    });

    if (status === 404) {
      return res.status(404).json({ error: `Character '${character_id}' not found in PubCast` });
    }
    if (status === 503) {
      return res.status(503).json({ error: `${character_id} has no API key configured. Set the key on the PubCast host.`, detail });
    }
    return res.status(status).json({ error: 'Character chat failed', detail, latency_ms: latency });
  }
});

/**
 * GET /api/chat/characters
 * List available characters and their provider/key status.
 */
app.get('/api/chat/characters', async (req, res) => {
  try {
    const response = await axios.get(`${PUBCAST_URL}/api/bots`, {
      timeout: 5000,
      headers: req.get('authorization') ? { Authorization: req.get('authorization') } : {}
    });
    const bots = Array.isArray(response.data) ? response.data : [];
    return res.json({
      ok: true,
      characters: bots.map(b => ({
        id:       b.bot_id,
        name:     b.name,
        provider: b.provider,
        model:    b.model,
        rooms:    b.rooms || []
      }))
    });
  } catch (err) {
    return res.status(503).json({
      ok: false,
      error: 'Could not reach PubCast',
      detail: err.message,
      pubcast_url: PUBCAST_URL
    });
  }
});

// ============================================================================
// ROUTE: Message History (Debugging/Review)
// ============================================================================

/**
 * GET /api/messages
 * Retrieve message history (latest N messages)
 * Query params: limit (default 50), source (filter by source), type (filter by type)
 */
app.get('/api/messages', (req, res) => {
  try {
    const { limit = 50, source = null, type = null } = req.query;

    // Validate limit
    let parsedLimit = parseInt(limit);
    if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 1000) {
      log(LOG_LEVELS.WARN, 'MESSAGES', 'Invalid limit parameter', { limit, ip: req.ip });
      return res.status(400).json({
        error: 'Invalid request',
        message: 'limit must be between 1 and 1000'
      });
    }

    let filtered = messageHistory;

    // Filter by source if specified
    if (source && typeof source === 'string') {
      filtered = filtered.filter(msg => msg.source === source);
    }

    // Filter by type if specified
    if (type && typeof type === 'string') {
      filtered = filtered.filter(msg => msg.metadata?.type === type);
    }

    // Return latest N
    const recent = filtered.slice(-parsedLimit);

    log(LOG_LEVELS.DEBUG, 'MESSAGES', 'History retrieved', {
      requested: parsedLimit,
      returned: recent.length,
      total: messageHistory.length,
      filters: { source: !!source, type: !!type },
      ip: req.ip
    });

    res.json({
      count: recent.length,
      total_in_history: messageHistory.length,
      max_history: MAX_HISTORY,
      messages: recent.map(msg => msg.toJSON())
    });

  } catch (error) {
    log(LOG_LEVELS.ERROR, 'MESSAGES', 'Failed to retrieve history', { error: error.message, ip: req.ip });
    res.status(500).json({
      error: 'Failed to retrieve history',
      message: error.message
    });
  }
});

// ============================================================================
// ROUTE: Clear History (Admin)
// ============================================================================

/**
 * DELETE /api/messages/clear
 * Clear all message history (requires admin check)
 */
app.delete('/api/messages/clear', (req, res) => {
  try {
    // FAIL CLOSED. An unset ADMIN_KEY must never mean "everyone is admin".
    // The previous form (adminKey !== process.env.ADMIN_KEY) evaluated
    // undefined !== undefined => false when ADMIN_KEY was unset, silently
    // granting every anonymous caller destructive access.
    const configuredKey = process.env.ADMIN_KEY;
    const presentedKey = req.get('x-admin-key');

    if (!configuredKey || typeof configuredKey !== 'string' || configuredKey.trim() === '') {
      log(LOG_LEVELS.ERROR, 'ADMIN', 'Clear refused — ADMIN_KEY not configured on server', { ip: req.ip });
      return res.status(503).json({
        error: 'Admin operations disabled',
        message: 'ADMIN_KEY is not configured on the server. Destructive operations are unavailable.',
        timestamp: new Date().toISOString()
      });
    }

    if (!presentedKey || typeof presentedKey !== 'string') {
      log(LOG_LEVELS.WARN, 'ADMIN', 'Unauthorized clear attempt — no key presented', { ip: req.ip });
      return res.status(403).json({
        error: 'Forbidden',
        message: 'Admin key required',
        timestamp: new Date().toISOString()
      });
    }

    // Constant-time comparison — prevents timing oracle on the key
    const a = Buffer.from(presentedKey);
    const b = Buffer.from(configuredKey);
    const keyMatches = a.length === b.length && crypto.timingSafeEqual(a, b);

    if (!keyMatches) {
      log(LOG_LEVELS.WARN, 'ADMIN', 'Unauthorized clear attempt — bad key', { ip: req.ip });
      return res.status(403).json({
        error: 'Forbidden',
        message: 'Admin key required',
        timestamp: new Date().toISOString()
      });
    }

    const count = messageHistory.length;
    messageHistory.length = 0;
    
    log(LOG_LEVELS.WARN, 'ADMIN', 'Message history cleared', {
      count_deleted: count,
      ip: req.ip
    });

    res.json({
      status: 'cleared',
      messages_deleted: count,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    log(LOG_LEVELS.ERROR, 'ADMIN', 'Failed to clear history', { error: error.message, ip: req.ip });
    res.status(500).json({
      error: 'Clear failed',
      message: error.message
    });
  }
});

// ============================================================================
// ERROR HANDLING
// ============================================================================

// 404 handler
app.use((req, res) => {
  log(LOG_LEVELS.WARN, 'HTTP', 'Not found', {
    method: req.method,
    path: req.path,
    ip: req.ip
  });

  res.status(404).json({
    error: 'Not found',
    message: `${req.method} ${req.path} does not exist`,
    path: req.path,
    method: req.method,
    timestamp: new Date().toISOString()
  });
});

// Global error handler
app.use((err, req, res, next) => {
  // CORS errors
  if (err.message && err.message.includes('CORS')) {
    log(LOG_LEVELS.WARN, 'CORS', 'CORS error', { error: err.message, ip: req.ip });
    return res.status(403).json({
      error: 'CORS error',
      message: err.message,
      timestamp: new Date().toISOString()
    });
  }

  // Payload too large
  if (err.type === 'entity.too.large') {
    log(LOG_LEVELS.WARN, 'HTTP', 'Payload too large', { ip: req.ip });
    return res.status(413).json({
      error: 'Payload too large',
      message: 'Request body exceeds 10MB limit',
      timestamp: new Date().toISOString()
    });
  }

  // JSON parse errors
  if (err instanceof SyntaxError && 'body' in err) {
    log(LOG_LEVELS.WARN, 'HTTP', 'Invalid JSON', { error: err.message, ip: req.ip });
    return res.status(400).json({
      error: 'Invalid JSON',
      message: err.message,
      timestamp: new Date().toISOString()
    });
  }

  // Unhandled errors
  log(LOG_LEVELS.CRITICAL, 'UNHANDLED', 'Unhandled error', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method,
    ip: req.ip
  });

  res.status(500).json({
    error: 'Server error',
    message: 'An unexpected error occurred',
    timestamp: new Date().toISOString(),
    request_id: req.ip // Use IP as request identifier for now
  });
});

// ============================================================================
// MESSAGE HISTORY CLEANUP
// ============================================================================

/**
 * Periodically clean up old messages to prevent memory bloat
 * Run every 5 minutes
 */
setInterval(() => {
  if (messageHistory.length > MAX_HISTORY * 0.8) {
    const before = messageHistory.length;
    
    // Keep recent messages, remove old ones
    const cutoff = MAX_HISTORY * 0.6;
    messageHistory.splice(0, messageHistory.length - cutoff);
    
    const after = messageHistory.length;
    log(LOG_LEVELS.INFO, 'CLEANUP', 'Message history cleanup', {
      before,
      after,
      removed: before - after
    });
  }
}, 5 * 60 * 1000); // Every 5 minutes

// ============================================================================
// RATE LIMIT STORE CLEANUP
// ============================================================================

/**
 * Periodically remove stale rate-limit entries to prevent memory bloat.
 *
 * checkRateLimit() only trims an IP's own request array when that same
 * IP calls again — an IP that stops calling keeps its (now-stale) array
 * in the Map forever. Proven by stress test: 50,000 distinct one-shot
 * IPs produced 50,000 permanent Map entries that did not shrink even
 * ten rate-limit windows later with zero further activity. Same shape
 * of leak as the toastHistory issue fixed on the frontend — here it's
 * the backend's turn.
 *
 * Run every 5 minutes, same cadence as the message history cleanup.
 */
setInterval(() => {
  const now = Date.now();
  const before = rateLimitStore.size;
  let entriesTrimmed = 0;

  for (const [key, requests] of rateLimitStore.entries()) {
    // Trim requests outside the window, same logic checkRateLimit uses
    // reactively — window is uniform across all RATE_LIMITS entries,
    // so a single global window is correct here regardless of which
    // endpoint(s) this IP has called.
    while (requests.length > 0 && requests[0] < now - RATE_LIMIT_WINDOW) {
      requests.shift();
      entriesTrimmed++;
    }

    // An IP with no requests left in its window is done — remove the
    // Map entry entirely rather than leaving an empty array forever.
    if (requests.length === 0) {
      rateLimitStore.delete(key);
    }
  }

  const after = rateLimitStore.size;
  if (before !== after || entriesTrimmed > 0) {
    log(LOG_LEVELS.INFO, 'CLEANUP', 'Rate limit store cleanup', {
      before,
      after,
      keys_removed: before - after,
      stale_requests_trimmed: entriesTrimmed
    });
  }
}, 5 * 60 * 1000); // Every 5 minutes

// ============================================================================
// SERVER START
// ============================================================================

const server = app.listen(PORT, process.env.HOST || '127.0.0.1', () => {
  log(LOG_LEVELS.INFO, 'STARTUP', '2i Backend Server Starting', {
    port: PORT,
    node_version: process.version,
    environment: process.env.NODE_ENV || 'development',
    anthropic_configured: !!ANTHROPIC_API_KEY,
    pubpartner_configured: !!process.env.PUBPARTNER_URL
  });

  console.log(`
  ╔══════════════════════════════════════════╗
  ║      2i BACKEND - BELLA FAUX PAS        ║
  ║                                          ║
  ║  Status: ✓ Running                       ║
  ║  Port:   ${PORT}                                ║
  ║  URL:    http://localhost:${PORT}          ║
  ║  Health: http://localhost:${PORT}/health   ║
  ║                                          ║
  ║  Configuration:                          ║
  ║  - Node: ${process.version}              ║
  ║  - Anthropic: ${ANTHROPIC_API_KEY ? '✓ configured' : '✗ MISSING'}  ║
  ║  - PubPartner: ${process.env.PUBPARTNER_URL ? '✓ configured' : '○ not configured'}  ║
  ║  - CORS: ${process.env.NODE_ENV === 'development' ? 'permissive' : 'restrictive'}       ║
  ║                                          ║
  ║  Endpoints:                              ║
  ║  - GET  /health                          ║
  ║  - POST /api/claude                      ║
  ║  - GET  /api/thesaurus                   ║
  ║  - POST /api/manuscript/commit           ║
  ║  - GET  /api/messages                    ║
  ║  - DELETE /api/messages/clear (admin)    ║
  ║                                          ║
  ╚══════════════════════════════════════════╝
  `);

  log(LOG_LEVELS.INFO, 'STARTUP', '2i backend ready for messages');
});

// Graceful shutdown
process.on('SIGTERM', () => {
  log(LOG_LEVELS.WARN, 'SHUTDOWN', 'SIGTERM received, gracefully shutting down');
  server.close(() => {
    log(LOG_LEVELS.INFO, 'SHUTDOWN', 'Server closed');
    process.exit(0);
  });
  
  // Force close after 10 seconds
  setTimeout(() => {
    log(LOG_LEVELS.CRITICAL, 'SHUTDOWN', 'Force closing after timeout');
    process.exit(1);
  }, 10000);
});

process.on('SIGINT', () => {
  log(LOG_LEVELS.WARN, 'SHUTDOWN', 'SIGINT received, gracefully shutting down');
  server.close(() => {
    log(LOG_LEVELS.INFO, 'SHUTDOWN', 'Server closed');
    process.exit(0);
  });
  
  // Force close after 10 seconds
  setTimeout(() => {
    log(LOG_LEVELS.CRITICAL, 'SHUTDOWN', 'Force closing after timeout');
    process.exit(1);
  }, 10000);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  log(LOG_LEVELS.CRITICAL, 'UNCAUGHT', 'Uncaught exception', {
    error: error.message,
    stack: error.stack
  });
  process.exit(1);
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  log(LOG_LEVELS.CRITICAL, 'REJECTION', 'Unhandled promise rejection', {
    reason: reason instanceof Error ? reason.message : String(reason),
    promise: String(promise)
  });
});

// Export for testing
module.exports = { app, Message };
