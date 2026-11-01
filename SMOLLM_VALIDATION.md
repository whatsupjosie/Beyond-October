# Adapter audit validation — October 10, 2026

117 selected Python regression tests passed with one dependency deprecation
warning. This is a focused integration suite, not the entire repository suite.
23 of those cover hosted adapters. Run pytest from the application root: an
initial parent-directory invocation had one static-file test failure because
that legacy route uses a relative static directory. Normal launchers set cwd.

The actual Linux runtime and GGUF passed authenticated greeting, arithmetic,
short-history recall and manuscript generation with fallback disabled. The
latest greeting was "Hello."; arithmetic was correct. The manuscript produced
new prose. The source hash and served JS hash were checked. Anonymous access
returned 401; a 77,734-token request returned 503 without truncation. Sending
SIGTERM to the supervisor stopped both services and closed both ports.
See validation/smollm_live_results.json for exact synthetic requests/results.

Eight jsdom flows passed: configuration gate, duplicate send, exact source and
history, new session ID, late reply isolation, draft recovery, safe error display
and button recovery. This executes the actual page/scripts in a DOM simulation.
It is not a real-browser visual or click-through test: Chromium downloads failed.
Windows, Android, physical studio devices and user hardware remain untested.

Local transport checks cover real-template token preflight, total deadline,
malformed SSE, partial EOF, length stops, credential boundaries and precise
message hashes. Other selected checks cover CARE, Alex memory, Writer's Room,
privacy, source preservation, authentication and prior four-round contracts.
Hosted tests verify public Responses/Claude/Gemini request and failure contracts
using mock HTTP, not live provider accounts. No cloud credentials were available.

Reproduce local live checks using `python tools/smollm_live_check.py` in your
installed environment; ports 8100/8101 must be free. It uses temporary synthetic
owner data and writes results in a timestamped output folder. For UI simulation,
install jsdom 30 in a separate developer folder, set NODE_PATH to that folder's
node_modules and run `node tests/smollm_browser_dom.cjs .` from the app root.

SmolLM is a small model. These checks demonstrate this limited functionality,
not broad reasoning quality, long-document reliability or production certification.
Earlier reports are historical; they do not certify the new integration.
